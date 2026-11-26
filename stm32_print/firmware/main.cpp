// ============================================================
//  RC522 刷卡识别 v8
//  与 v7 的区别：默认只"读"，不写卡；写卡要显式指令
//  串口输出全是 ASCII，方便上位机（Python）解析
// ------------------------------------------------------------
//  默认（QUIET_OUTPUT = 1，给上位机直接吃）：
//      刷一下卡，串口只吐一行：D14
//      也就是卡里块 4 的文字本身，不加任何前缀；写卡时不打印。
//  调试模式（QUIET_OUTPUT = 0，原来的行为）：
//      EVT BOOT v9 VersionReg=0x92
//      EVT CARD B09D762F        每次刷卡（UID 8 位大写十六进制）
//      EVT TAG "D14"            卡里块 4 的文字
//      EVT ALIVE 42 rx=0        心跳
//  无论哪种模式，写卡进程都会打印：
//      EVT ARM WRITE "D14"      已就绪，等贴卡
//      EVT WBLOCK 4 OK/TimeOut  逐块写结果
//      EVT WROTE "D14" PASS 483ms
//  上位机发下来的只有两种，其余一律忽略：
//      W:D14       给下一张卡写 "D14"（写一次后自动回到只读）
//      R           取消待写（回到只读）
// ============================================================

#include <Arduino.h>
#include <SPI.h>
#include <MFRC522.h>
#include <HardwareSerial.h>
#include <string.h>

// RST 由硬件直接接 3.3 V（见 接线图.png 第一行），不占用 GPIO，
// 因此这里传 UNUSED_PIN，让库跳过复位脚操作。
#define RST_PIN  MFRC522::UNUSED_PIN
#define SS_PIN   PA4
// ---------- 声光（红绿灯 + 蜂鸣器）----------
#define LED_GREEN_PIN    PA1     // 绿灯
#define LED_RED_PIN      PA2     // 红灯
#define BUZZER_PIN       PB12    // 蜂鸣器：一端接 PB12，另一端接 GND

#define LED_USE_PWM      1       // 用 PWM 降平均电流（LED 没串限流电阻时更安全）
#define LED_DUTY         160     // PWM 占空比 0~255，160 约 63%（比 96 亮，数字量兜底时也不会被判成 LOW）
#define SIGNAL_MS        800     // 灯亮多久（毫秒）
#define BEEP_OK_MS       100     // 放行：短促一声
#define BEEP_FAIL_MS     400     // 拒绝：长一声
#define BUZZER_PASSIVE   1       // 1=无源蜂鸣器（方波驱动） 0=有源（直流驱动）
#define BUZZER_TONE_HZ   2700    // 无源蜂鸣器谐振频率

// ---------- 串口输出模式 ----------
// 1 = 只输出卡里的文字（给上位机 bat 直接当学号吃），不输出心跳/UID/自检等调试行
// 0 = 保留原来全部 EVT 调试行
// 只影响串口打印，与 SPI、复位时序、红绿灯、蜂鸣器都无关。
#define QUIET_OUTPUT 1


HardwareSerial Serial1(PA10, PA9);
MFRC522 mfrc522(SS_PIN, RST_PIN);
MFRC522::MIFARE_Key key;

// 扇区 1 = 块 4,5,6（数据块）+ 块 7（扇区尾块：密钥 + 访问位）
const byte FIRST_BLOCK  = 4;
const byte LAST_BLOCK   = 6;
const byte SECTOR_BYTES = 48;

const unsigned long POST_WRITE_WAIT_MS = 150;
const unsigned long RECHARGE_WAIT_MS   = 400;
const unsigned long FIELD_OFF_MS       = 300;
const unsigned long HEARTBEAT_MS       = 3000;
const unsigned long CARD_COOLDOWN_MS   = 800;

static char pending[49];
static bool writeOnce = false;   // 只有收到 "W:..." 才置 true，写一次后清掉

static char lineBuf[65];
static byte lineLen = 0;

static unsigned long rxTotal  = 0;
static unsigned long beatTime = 0;
static unsigned long beatNo   = 0;
// ---------- 声光状态 ----------
static unsigned long sigOnTime  = 0;
static unsigned long beepOnTime = 0;
static uint16_t      beepMs     = 0;
static bool          sigActive  = false;
static bool          beepActive = false;

static void ledWrite(uint8_t pin, bool on) {
#if LED_USE_PWM
  analogWrite(pin, on ? LED_DUTY : 0);
#else
  digitalWrite(pin, on ? HIGH : LOW);
#endif
}

// 无源蜂鸣器必须用方波（tone）驱动：直接通直流只会"哒"一下，而且线圈
// 直流电阻只有十几欧，长时间通电会把 GPIO 拉爆。有源的才用直流。
static void buzzerWrite(bool on) {
#if BUZZER_PASSIVE
  if (on) {
    tone(BUZZER_PIN, BUZZER_TONE_HZ);
  } else {
    noTone(BUZZER_PIN);              // noTone 只停定时器，引脚电平会保持原状
    digitalWrite(BUZZER_PIN, LOW);   // 主动拉低，别让线圈一直通电
  }
#else
  digitalWrite(BUZZER_PIN, on ? HIGH : LOW);
#endif
}

static void startBeep(uint16_t ms, unsigned long now) {
  buzzerWrite(true);
  beepMs     = ms;
  beepOnTime = now;
  beepActive = true;
}

static void signalInit() {
  pinMode(LED_GREEN_PIN, OUTPUT);
  pinMode(LED_RED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  ledWrite(LED_GREEN_PIN, false);
  ledWrite(LED_RED_PIN, false);
  sigActive  = false;
  beepActive = false;
}

// 放行：绿灯亮 + 短促一声
static void signalPass(unsigned long now) {
  ledWrite(LED_GREEN_PIN, true);
  ledWrite(LED_RED_PIN,   false);
  startBeep(BEEP_OK_MS, now);
  sigOnTime = now;
  sigActive = true;
}

// 拒绝：红灯亮 + 长一声
static void signalFail(unsigned long now) {
  ledWrite(LED_GREEN_PIN, false);
  ledWrite(LED_RED_PIN,   true);
  startBeep(BEEP_FAIL_MS, now);
  sigOnTime = now;
  sigActive = true;
}

// 到点就把灯和蜂鸣器收掉，绝不阻塞主循环（delay 会害得刷不上卡）
static void signalUpdate(unsigned long now) {
  if (beepActive && (long)(now - beepOnTime) >= (long)beepMs) {
    buzzerWrite(false);
    beepActive = false;
  }
  if (sigActive && (long)(now - sigOnTime) >= (long)SIGNAL_MS) {
    ledWrite(LED_GREEN_PIN, false);
    ledWrite(LED_RED_PIN,   false);
    sigActive = false;
  }
}

// 开机自检：绿灯 400ms -> 红灯 400ms。
// 只要这两步能看到灯，就说明引脚、极性和接线都是对的；
// 刷卡时灯还是不亮，那就是逻辑问题，不再是硬件问题。
static void ledSelfTest() {
  if (!QUIET_OUTPUT) Serial1.println("EVT SELFTEST green");
  ledWrite(LED_GREEN_PIN, true);
  ledWrite(LED_RED_PIN, false);
  delay(400);

  if (!QUIET_OUTPUT) Serial1.println("EVT SELFTEST red");
  ledWrite(LED_GREEN_PIN, false);
  ledWrite(LED_RED_PIN, true);
  delay(400);

  ledWrite(LED_GREEN_PIN, false);
  ledWrite(LED_RED_PIN, false);
  if (!QUIET_OUTPUT) Serial1.println("EVT SELFTEST done");
}


// ---------- 打印工具 ----------
static void printHex(const byte *p, byte n) {
  for (byte i = 0; i < n; i++) {
    if (p[i] < 0x10) Serial1.print('0');
    Serial1.print(p[i], HEX);
  }
}

static void printAscii(const byte *p, byte n) {
  for (byte i = 0; i < n; i++) {
    char c = (char)p[i];
    Serial1.print((c >= 0x20 && c <= 0x7E) ? c : '.');
  }
}

// ---------- 串口输入 ----------
static void pollSerial() {
  while (Serial1.available()) {
    char c = (char)Serial1.read();
    rxTotal++;

    // 连调时想看到逐字节回显，就把下面这行放开
    // Serial1.print("[rx] 0x"); Serial1.print((byte)c, HEX); Serial1.println();

    if (c == '\r' || c == '\n') {
      if (lineLen > 0) {
        lineBuf[lineLen] = '\0';
        bool isWrite = (lineBuf[0] == 'W' && lineBuf[1] == ':');
        if (strcmp(lineBuf, "R") == 0 || strcmp(lineBuf, "r") == 0) {
          writeOnce = false;
          Serial1.println("EVT ARM OFF");
        } else if (isWrite) {
          strncpy(pending, lineBuf + 2, sizeof(pending) - 1);
          pending[sizeof(pending) - 1] = '\0';
          writeOnce = true;
          Serial1.print("EVT ARM WRITE \"");
          Serial1.print(pending);
          Serial1.println("\"");
        } else {
          // 不是 W: 指令就吞掉。
          // 上位机读卡后会回 OK:D14 / BUSY:D14 / ERR:... 这类反馈行；
          // 以前这里会把它们当成"待写文本"再回显 EVT ARM ...，
          // 上位机又把回显当成新的 ID，于是两边来回刷屏。现在直接忽略。
        }
      }
      lineLen = 0;
      continue;
    }
    if (lineLen < sizeof(lineBuf) - 1) lineBuf[lineLen++] = c;
  }
  lineBuf[lineLen] = '\0';
}

static void heartbeat() {
  if (millis() - beatTime < HEARTBEAT_MS) return;
  beatTime = millis();
  beatNo++;
  if (QUIET_OUTPUT) return;
  Serial1.print("EVT ALIVE ");
  Serial1.print(beatNo);
  Serial1.print(" rx=");
  Serial1.println(rxTotal);
}

// 把待写文字撑成严格 48 字节，不足补空格
static void buildSectorPayload(byte *out48) {
  const char *s = pending;
  memset(out48, ' ', SECTOR_BYTES);
  size_t len = strlen(s);
  if (len > SECTOR_BYTES) len = SECTOR_BYTES;
  memcpy(out48, s, len);
}

// ---------- 卡操作 ----------
static bool authBlock(byte block) {
  return mfrc522.PCD_Authenticate(MFRC522::PICC_CMD_MF_AUTH_KEY_A, block,
                                  &key, &(mfrc522.uid)) == MFRC522::STATUS_OK;
}

static MFRC522::StatusCode writeBlock(byte block, byte *data16) {
  if ((block % 4) == 3) {
    Serial1.println("  [guard] sector trailer, refused");
    return MFRC522::STATUS_ERROR;
  }
  byte cmd[2];
  cmd[0] = (byte)MFRC522::PICC_CMD_MF_WRITE;
  cmd[1] = block;
  MFRC522::StatusCode st = mfrc522.PCD_MIFARE_Transceive(cmd, 2);
  if (st != MFRC522::STATUS_OK) return st;
  return mfrc522.PCD_MIFARE_Transceive(data16, 16);
}

static bool tryRead(byte block, byte *out16) {
  byte buf[18];
  byte size = sizeof(buf);
  if (mfrc522.MIFARE_Read(block, buf, &size) != MFRC522::STATUS_OK) return false;
  memcpy(out16, buf, 16);
  return true;
}

static bool recoverCard() {
  mfrc522.PCD_StopCrypto1();
  mfrc522.PCD_AntennaOff();
  delay(FIELD_OFF_MS);

  for (byte round = 1; round <= 3; round++) {
    mfrc522.PCD_Init();
    delay(80);
    if (mfrc522.PICC_IsNewCardPresent() && mfrc522.PICC_ReadCardSerial()) {
      Serial1.println("EVT RECOVER OK");
      return true;
    }
    delay(150);
  }
  Serial1.println("EVT RECOVER FAIL");
  return false;
}

static bool readBlock(byte block, byte *out16) {
  if (tryRead(block, out16)) return true;

  delay(30);
  mfrc522.PCD_StopCrypto1();
  if (authBlock(block) && tryRead(block, out16)) return true;

  delay(RECHARGE_WAIT_MS);
  mfrc522.PCD_StopCrypto1();
  if (authBlock(block) && tryRead(block, out16)) return true;

  if (recoverCard() && authBlock(block) && tryRead(block, out16)) return true;

  return false;
}

// ---------- setup ----------
void setup() {
  Serial1.begin(115200);
  signalInit();
  ledSelfTest();

  delay(2000);

  // 模块 RST 已由硬件固定接 3.3 V，这里不再操作复位脚；
  // PCD_Init 见到 UNUSED_PIN 也不会去动它。
  SPI.begin();
  mfrc522.PCD_Init();
  delay(50);

  byte v = mfrc522.PCD_ReadRegister(MFRC522::VersionReg);
  if (!QUIET_OUTPUT) {
    Serial1.print("EVT BOOT v9 VersionReg=0x");
    Serial1.println(v, HEX);
  }

  for (byte i = 0; i < 6; i++) key.keyByte[i] = 0xFF;
}

// ---------- loop ----------
void loop() {
  heartbeat();
  pollSerial();
  signalUpdate(millis());


  if (!mfrc522.PICC_IsNewCardPresent()) return;
  if (!mfrc522.PICC_ReadCardSerial()) return;

  // 1. 机器可读：UID（静默模式下不输出）
  if (!QUIET_OUTPUT) {
    Serial1.print("EVT CARD ");
    printHex(mfrc522.uid.uidByte, mfrc522.uid.size);
    Serial1.println();
  }

  if (!authBlock(FIRST_BLOCK)) {
    Serial1.println("EVT AUTH FAIL");
    signalFail(millis());
    mfrc522.PICC_HaltA();
    mfrc522.PCD_StopCrypto1();
    delay(CARD_COOLDOWN_MS);
    return;
  }

  // 2. 机器可读：卡里写的标签（块 4 的文字，去掉尾部空格）
  byte b4[16];
  if (readBlock(FIRST_BLOCK, b4)) {
    byte n = 16;
    while (n > 0 && (b4[n - 1] == 0x20 || b4[n - 1] == 0x00)) n--;
    if (QUIET_OUTPUT) {
      // 只把卡里的文字原样吐出去（如 D14），上位机直接当 ID 用。
      // 写卡流程中不打印，免得贴卡写的时候顺手触发一次报告打印。
      if (!writeOnce) {
        printAscii(b4, n);
        Serial1.println();
      }
    } else {
      Serial1.print("EVT TAG \"");
      printAscii(b4, n);
      Serial1.println("\"");
    }
    signalPass(millis());
  } else {
    if (!QUIET_OUTPUT) Serial1.println("EVT TAG <unreadable>");
    signalFail(millis());
  }

  // 3. 没收到 W: 指令就到此为止——只读，不动卡
  if (!writeOnce) {
    mfrc522.PICC_HaltA();
    mfrc522.PCD_StopCrypto1();
    delay(CARD_COOLDOWN_MS);
    return;
  }

  // 4. 写卡（沿用 v7 的"写前读、逐块写、回读校验"）
  unsigned long t0 = millis();

  byte before[SECTOR_BYTES];
  for (byte i = 0; i < 3; i++) {
    byte b = FIRST_BLOCK + i;
    if (!readBlock(b, before + i * 16)) memset(before + i * 16, 0, 16);
  }

  byte target[SECTOR_BYTES];
  buildSectorPayload(target);

  if (!authBlock(FIRST_BLOCK)) {
    Serial1.println("EVT AUTH FAIL before write");
    mfrc522.PICC_HaltA();
    mfrc522.PCD_StopCrypto1();
    delay(CARD_COOLDOWN_MS);
    return;
  }

  for (byte b = FIRST_BLOCK; b <= LAST_BLOCK; b++) {
    byte chunk[16];
    memcpy(chunk, target + (b - FIRST_BLOCK) * 16, 16);
    MFRC522::StatusCode st = writeBlock(b, chunk);
    bool ok = (st == MFRC522::STATUS_OK);
    Serial1.print("EVT WBLOCK ");
    Serial1.print(b);
    Serial1.print(ok ? " OK" : " BAD");
    Serial1.print(" ");
    Serial1.println(mfrc522.GetStatusCodeName(st));
    delay(POST_WRITE_WAIT_MS);
  }

  byte after[SECTOR_BYTES];
  bool afterOk = true;
  for (byte i = 0; i < 3; i++) {
    byte b = FIRST_BLOCK + i;
    if (!readBlock(b, after + i * 16)) { afterOk = false; memset(after + i * 16, 0, 16); }
  }

  bool pass = afterOk && (memcmp(after, target, SECTOR_BYTES) == 0);
  Serial1.print("EVT WROTE \"");
  Serial1.print(pending);
  Serial1.print("\" ");
  Serial1.print(pass ? "PASS" : "FAIL");
  Serial1.print(" ");
  Serial1.print(millis() - t0);
  Serial1.println("ms");

  writeOnce = false;

  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
  delay(CARD_COOLDOWN_MS);
}