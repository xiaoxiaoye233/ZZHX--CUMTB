# STM32 刷卡终端（监听打印客户端 + 固件）

本文件夹 `stm32_print/` **完全独立自包含**（内置串口监听、HTTP PDF 下载与 Windows 无弹窗静默打印模块），既可以直接在本项目目录下双击运行，也可以把整个 `stm32_print` 文件夹单独复制到任何连接了 STM32 与打印机的 Windows 电脑上独立使用。

## 目录结构

- `stm32_auto_print.py`：主程序（监听 STM32 串口 / 控制台输入 → 映射学号 → 请求后端下载 PDF → 调用打印）
- `stm32_config.json`：配置文件（自定义串口、波特率、后端地址、打印机名称、ID 与学生映射表，支持**保存即热生效**）
- `print_pdf_file.py`：内置 Windows GDI 静默打印模块（不弹窗、不依赖外部 PDF 阅读器）
- `requirements.txt`：独立运行所需的最小依赖清单
- `启动监听.bat`：Windows 双击一键启动脚本
- `downloads/`：自动下载保存的学情报告 PDF 目录（运行后自动生成）
- `firmware/main.cpp`：STM32 固件源码
- `firmware/接线图.png`：接线示意图

## 1. 修改配置（`stm32_config.json`）

```json
{
  "serial_port": "AUTO",
  "baudrate": 115200,
  "backend_url": "http://127.0.0.1:8000",
  "printer_name": "",
  "include_advice": true,
  "dry_run": false,
  "cooldown_seconds": 10,
  "allow_direct_student_id": true,
  "id_to_student": {
    "1": "D01",
    "2": "D02",
    "3": "D03",
    "4": "D04",
    "5": "D05",
    "01": "D01",
    "02": "D02",
    "CARD_001": "D01",
    "CARD_002": "D14"
  }
}
```

- `serial_port`：`"AUTO"` 自动识别 STM32 串口（CH340 / CP210x / ST-Link 等），也可固定填 `"COM3"`。
- `baudrate`：自定义波特率（如 `115200`、`9600`）。
- `backend_url`：后端服务地址（本机填 `http://127.0.0.1:8000`，跨电脑运行填后端电脑的局域网 IP 如 `http://192.168.1.100:8000`）。
- `printer_name`：留空 `""` 自动使用当前电脑的系统默认打印机，也可填写具体打印机名称。
- `id_to_student`：手动定义 ID 对应哪位学生学号（运行期间修改保存立即生效，也可在程序窗口输入 `map <ID> <学号>` 实时添加）。

## 2. 启动方式

### 在本仓库中直接运行
直接双击 `启动监听.bat`，或在终端执行：

```powershell
cd d:\Learing\ZJHX--CUMTB\stm32_print
..\project\venv\Scripts\python.exe stm32_auto_print.py
```

无纸测试模式（正常请求后端生成下载真 PDF 到 `downloads/` 并渲染校验，但不实际出纸）：

```powershell
..\project\venv\Scripts\python.exe stm32_auto_print.py --dry
```

### 单独拷贝到另一台电脑运行
1. 将 `stm32_print` 整个文件夹拷到目标电脑；
2. 安装轻量依赖：`pip install -r requirements.txt`；
3. 将 `stm32_config.json` 里的 `backend_url` 改为后端所在电脑的地址；
4. 双击 `启动监听.bat` 或执行 `python stm32_auto_print.py`。

## 3. 固件（`firmware/main.cpp`）

烧在 STM32 里的那一端：读卡里写入的字符串，从串口发出去。判定、打印、生成报告都在电脑端，这一端不做业务判断。

**硬件**

| 部件 | 型号 |
| --- | --- |
| 主控 | STM32F103C8T6 |
| 读卡模块 | RC522（MFRC522，13.56 MHz，MIFARE Classic 卡） |
| 串口 | CH340 USB 转 TTL |
| 供电 | STM32-Type-C |
| 烧录 | ST-Link（SWD） |

**接线**：见 `firmware/接线图.png`，按模块排针自上而下逐行对接，GND 全部共地。RC522 的 `IRQ` 悬空不接；`RST` 与 `3.3V` 都接 3.3 V，因此 RST 不占 GPIO，固件里 `RST_PIN` 传的是 `MFRC522::UNUSED_PIN`。CH340 的 `RXD` 接 `PA9`（USART1_TX）、`TXD` 接 `PA10`（USART1_RX）。

**软件栈**

| 层 | 组成 | 版本 |
| --- | --- | --- |
| 框架 | Arduino for STM32（`Arduino_Core_STM32`） | **2.10.0** |
| 读卡库 | `MFRC522` | 1.4.11 |
| 板级接口 | SPI1、USART1（115200 8-N-1） | 随框架 |

版本是硬约束：4.x / 4.5 下写卡会返回 `WBLOCK 4 BAD Timeout in communication`。

**串口协议**

| 方向 | 内容 |
| --- | --- |
| 电脑 → 单片机 | `W:<文字>` 写下一张卡；`R` 取消待写 |
| 单片机 → 电脑 | `QUIET_OUTPUT 1`（默认）只发卡里的文字，如 `D14`；`0` 发全部 `EVT` 调试行 |

写卡过程的输出两种模式都保留：`EVT ARM WRITE "..."`、`EVT WBLOCK 4 OK`、`EVT WROTE "..." PASS <ms>`。

**代码结构**

| 函数 | 职责 |
| --- | --- |
| `setup` | 串口、灯与蜂鸣器、SPI、RC522 初始化 |
| `pollSerial` | 收下行指令，`W:` 置待写、`R` 取消 |
| `pollCard` | 读卡（认证 → 读块 4 → 上报），或写卡（逐块写并回读校验） |
| `authBlock` / `readBlock` / `writeBlock` | 块级读写，Key A |
| `heartbeat` | 每 3 秒心跳（静默模式不输出） |
| `signalPass` / `signalFail` | 声光反馈 |

**注意事项**

1. RC522 的 RST 直接接 3.3 V（见图第一行）；若让它悬空，芯片停在复位态，读出来恒为 `0xFF`。
2. 块 4 只有 16 字节，超长会截断；写卡是覆盖，不可逆。
3. 板子不判重：重复刷卡的抑制在电脑端按学生维度做（`cooldown_seconds`，默认 10 秒）。
