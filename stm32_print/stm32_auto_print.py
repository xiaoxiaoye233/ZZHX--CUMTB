r"""STM32 串口监听 → 自动向后端请求生成并下载学情报告 PDF → 自动静默打印程序（完全独立文件夹版）。

本文件夹完全自包含，可直接在本机运行，也可将整个 stm32_print 文件夹单独复制到任意连接了 STM32 与打印机的 Windows 电脑运行。

运行方式：
    双击 `启动监听.bat`
    或命令行：
    ..\project\venv\Scripts\python.exe stm32_auto_print.py
    python stm32_auto_print.py --port COM3 --baudrate 9600 --backend http://192.168.1.10:8000
    python stm32_auto_print.py --dry          # 无纸演练（下载真 PDF 到 downloads/ 并渲染校验，不出纸）
    python stm32_auto_print.py --list-ports   # 查看当前电脑可用串口
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None  # type: ignore[assignment]
    list_ports = None  # type: ignore[assignment]


HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = HERE / "stm32_config.json"
PRINT_SCRIPT = HERE / "print_pdf_file.py"
DOWNLOAD_DIR = HERE / "downloads"

STM32_USB_KEYWORDS = (
    "ch340",
    "ch341",
    "cp210",
    "stlink",
    "st-link",
    "stmicro",
    "ftdi",
    "usb-serial",
    "usb serial",
    "uart",
)

DEFAULT_CONFIG = {
    "serial_port": "AUTO",
    "baudrate": 115200,
    "backend_url": "http://127.0.0.1:8000",
    "printer_name": "",
    "include_advice": True,
    "dry_run": False,
    "cooldown_seconds": 10,
    "allow_direct_student_id": True,
    "id_to_student": {
        "1": "D01",
        "2": "D02",
        "01": "D01",
        "CARD_001": "D01",
    },
}


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _normalize_id_token(raw: str) -> str:
    """清洗串口或终端传来的原始字符串，兼容 'ID:1'、'UID=AA 11 BB 22'、JSON 等格式。"""
    text = str(raw or "").strip().strip("\x00\r\n\t ")
    if not text:
        return ""

    if text.startswith("{") and text.endswith("}"):
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                for k in ("id", "uid", "card", "student_id", "code"):
                    if obj.get(k) is not None:
                        text = str(obj[k]).strip()
                        break
        except ValueError:
            pass

    prefix_match = re.match(r"^(?:id|uid|card|stu|student)\s*[:=]\s*(.+)$", text, flags=re.IGNORECASE)
    if prefix_match:
        text = prefix_match.group(1).strip()

    return text


class ConfigManager:
    """管理并热加载 stm32_config.json 配置（修改映射保存后即时生效，无需重启）。"""

    def __init__(self, config_path: Path, cli_overrides: dict):
        self.config_path = config_path
        self.cli_overrides = cli_overrides
        self._mtime: float = -1.0
        self._data: dict = dict(DEFAULT_CONFIG)
        self._lock = threading.Lock()
        self.reload_if_needed(force=True)

    def reload_if_needed(self, *, force: bool = False) -> dict:
        with self._lock:
            if self.config_path.is_file():
                mtime = self.config_path.stat().st_mtime
                if force or mtime != self._mtime:
                    try:
                        loaded = json.loads(self.config_path.read_text(encoding="utf-8-sig"))
                        if isinstance(loaded, dict):
                            merged = {**DEFAULT_CONFIG, **loaded}
                            if isinstance(loaded.get("id_to_student"), dict):
                                merged["id_to_student"] = {
                                    str(k).strip(): str(v).strip().upper()
                                    for k, v in loaded["id_to_student"].items()
                                    if str(k).strip() and str(v).strip()
                                }
                            self._data = merged
                            self._mtime = mtime
                            if not force:
                                print(f"[{_now()}] [配置热更新] 已重新加载 {self.config_path.name}")
                    except (OSError, ValueError) as exc:
                        print(f"[{_now()}] [警告] 读取配置文件失败（沿用上次有效配置）：{exc}")
            elif force:
                self.save_mapping_dict(DEFAULT_CONFIG["id_to_student"])

            effective = dict(self._data)
            for k, v in self.cli_overrides.items():
                if v is not None:
                    effective[k] = v
            return effective

    def update_student_mapping(self, raw_id: str, student_id: str) -> None:
        clean_id = _normalize_id_token(raw_id)
        clean_stu = str(student_id or "").strip().upper()
        if not clean_id or not clean_stu:
            raise ValueError("ID 和学生学号均不能为空")

        with self._lock:
            current = dict(self._data)
            mapping = dict(current.get("id_to_student") or {})
            mapping[clean_id] = clean_stu
            current["id_to_student"] = mapping
            self._data = current
            self.config_path.write_text(
                json.dumps(current, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            self._mtime = self.config_path.stat().st_mtime

    def save_mapping_dict(self, mapping: dict) -> None:
        payload = {**DEFAULT_CONFIG, "id_to_student": mapping}
        self.config_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self._mtime = self.config_path.stat().st_mtime

    def resolve_student_id(self, raw_id: str) -> str | None:
        token = _normalize_id_token(raw_id)
        if not token:
            return None

        cfg = self.reload_if_needed()
        mapping: dict[str, str] = cfg.get("id_to_student") or {}

        if token in mapping:
            return mapping[token]

        compact_upper = re.sub(r"[\s:-]+", "", token).upper()
        for k, stu in mapping.items():
            k_compact = re.sub(r"[\s:-]+", "", str(k)).upper()
            if compact_upper == k_compact:
                return str(stu).strip().upper()

        if token.isdigit():
            stripped_num = str(int(token))
            if stripped_num in mapping:
                return mapping[stripped_num]

        if cfg.get("allow_direct_student_id", True) and re.fullmatch(r"[A-Za-z]{1,4}\d{1,6}", token):
            return token.upper()

        return None


def detect_serial_port(configured_port: str) -> str | None:
    if list_ports is None:
        return None

    clean = str(configured_port or "AUTO").strip()
    if clean and clean.upper() != "AUTO":
        return clean

    ports = list(list_ports.comports())
    if not ports:
        return None

    for p in ports:
        desc = f"{p.device} {p.description} {p.manufacturer or ''} {p.hwid or ''}".lower()
        if any(kw in desc for kw in STM32_USB_KEYWORDS):
            return p.device

    return ports[0].device


def list_available_ports() -> list[str]:
    if list_ports is None:
        return []
    return [f"{p.device}\t{p.description} ({p.hwid})" for p in list_ports.comports()]


def download_student_report_pdf(
    backend_url: str,
    student_id: str,
    *,
    include_advice: bool = True,
    timeout: float = 30.0,
) -> Path:
    """请求后端接口生成并下载指定学生的学情报告 PDF，保存在当前文件夹的 downloads/ 下。"""
    base = str(backend_url or "http://127.0.0.1:8000").rstrip("/")
    sid = student_id.strip().upper()
    query = urlencode({"include_advice": "true" if include_advice else "false"})
    url = f"{base}/api/students/{quote(sid)}/learning-report/pdf?{query}"

    req = Request(url, method="GET", headers={"Accept": "application/pdf"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            pdf_bytes = resp.read()
    except HTTPError as exc:
        detail = ""
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
            parsed = json.loads(err_body)
            detail = (
                parsed.get("message")
                or parsed.get("detail", {}).get("error", {}).get("message")
                or str(parsed.get("detail") or "")
            )
        except Exception:
            pass
        raise RuntimeError(f"后端返回 HTTP {exc.code}：{detail or exc.reason}") from exc
    except URLError as exc:
        raise RuntimeError(f"无法连接后端 {base}（请确认 FastAPI 后端已启动）：{exc.reason}") from exc

    if not pdf_bytes.startswith(b"%PDF-"):
        raise RuntimeError("后端返回的数据不是有效的 PDF 文件")

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path = DOWNLOAD_DIR / f"学情报告_{sid}_{stamp}.pdf"
    pdf_path.write_bytes(pdf_bytes)
    return pdf_path


def invoke_printer(pdf_path: Path, *, printer_name: str = "", dry_run: bool = False) -> tuple[bool, str]:
    """调用同目录内置的 print_pdf_file.py 静默打印该 PDF。"""
    if not PRINT_SCRIPT.is_file():
        return False, f"找不到打印脚本：{PRINT_SCRIPT}"

    cmd = [sys.executable, str(PRINT_SCRIPT), str(pdf_path)]
    if printer_name.strip():
        cmd.extend(["--printer", printer_name.strip()])
    if dry_run:
        cmd.append("--dry")

    result = subprocess.run(
        cmd,
        cwd=str(HERE),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        timeout=90,
    )
    output = (result.stdout or "").strip()
    return result.returncode == 0, output


def send_serial_feedback(ser_conn, message: str) -> None:
    if ser_conn is None:
        return
    try:
        if getattr(ser_conn, "is_open", False):
            ser_conn.write((message.strip() + "\r\n").encode("utf-8"))
            ser_conn.flush()
    except Exception:
        pass


def process_incoming_id(
    raw_input: str,
    source_label: str,
    cfg_mgr: ConfigManager,
    last_printed_at: dict[str, float],
    ser_conn=None,
) -> bool:
    token = _normalize_id_token(raw_input)
    if not token:
        return False

    cfg = cfg_mgr.reload_if_needed()
    student_id = cfg_mgr.resolve_student_id(token)
    if not student_id:
        print(
            f"[{_now()}] [{source_label}] 收到未知 ID「{token}」，未在 stm32_config.json 的 id_to_student 中找到对应学生！"
        )
        print("           提示：可直接在此窗口输入 `map 你的ID 学号`（如 `map 88 D05`）立即绑定。")
        send_serial_feedback(ser_conn, f"ERR:UNMAPPED:{token}")
        return False

    cooldown = float(cfg.get("cooldown_seconds") or 0)
    now_ts = time.monotonic()
    prev_ts = last_printed_at.get(student_id)
    if prev_ts is not None and (now_ts - prev_ts) < cooldown:
        remain = cooldown - (now_ts - prev_ts)
        print(
            f"[{_now()}] [{source_label}] ID「{token}」→ 学生 {student_id} 处于防重打冷却中（剩余 {remain:.1f}s），已跳过。"
        )
        return False

    print(f"[{_now()}] [{source_label}] 识别成功：ID「{token}」 → 学生「{student_id}」")
    print(f"[{_now()}] 正在请求后端 {cfg['backend_url']} 生成并下载 {student_id} 的学情报告 PDF...")
    send_serial_feedback(ser_conn, f"BUSY:{student_id}")

    try:
        pdf_path = download_student_report_pdf(
            backend_url=cfg["backend_url"],
            student_id=student_id,
            include_advice=bool(cfg.get("include_advice", True)),
        )
    except Exception as exc:
        print(f"[{_now()}] [下载失败] {exc}")
        send_serial_feedback(ser_conn, f"ERR:DOWNLOAD:{student_id}")
        return False

    size_kb = pdf_path.stat().st_size / 1024
    print(f"[{_now()}] [下载完成] 已保存至 {pdf_path}（{size_kb:.1f} KB）")

    dry_mode = bool(cfg.get("dry_run", False))
    printer = str(cfg.get("printer_name") or "").strip()
    mode_tag = "无纸演练模式 (--dry)" if dry_mode else f"发送至打印机（{printer or '系统默认打印机'}）"
    print(f"[{_now()}] 正在调用打印程序：{mode_tag}...")

    ok, out_log = invoke_printer(pdf_path, printer_name=printer, dry_run=dry_mode)
    if out_log:
        for line in out_log.splitlines():
            print(f"           {line}")

    if ok:
        last_printed_at[student_id] = time.monotonic()
        print(f"[{_now()}] [流程完成] 学生 {student_id} 的学情报告已成功{'校验渲染' if dry_mode else '提交打印'}！\n")
        send_serial_feedback(ser_conn, f"OK:{student_id}")
        return True

    print(f"[{_now()}] [打印未完成] PDF 已保存在 {pdf_path}，请检查打印机连接状态。\n")
    send_serial_feedback(ser_conn, f"ERR:PRINT:{student_id}")
    return False


def _start_console_reader(event_queue: queue.Queue[tuple[str, str]]) -> None:
    def _worker() -> None:
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                stripped = line.strip()
                if stripped:
                    event_queue.put(("控制台", stripped))
            except Exception:
                break

    thread = threading.Thread(target=_worker, name="console-input", daemon=True)
    thread.start()


def _handle_console_command(cmd_text: str, cfg_mgr: ConfigManager) -> bool:
    parts = cmd_text.strip().split()
    if not parts:
        return True
    head = parts[0].lower()

    if head in ("quit", "exit", "q"):
        print(f"[{_now()}] 收到退出指令，程序结束。")
        raise KeyboardInterrupt

    if head in ("list", "ls", "map") and len(parts) == 1:
        cfg = cfg_mgr.reload_if_needed()
        mp = cfg.get("id_to_student") or {}
        print(f"[{_now()}] 当前 ID → 学生映射表（共 {len(mp)} 条，保存在 {cfg_mgr.config_path.name}）：")
        for k, v in mp.items():
            print(f"    {k}  ->  {v}")
        return True

    if head == "map" and len(parts) == 3:
        raw_id, stu_id = parts[1], parts[2]
        cfg_mgr.update_student_mapping(raw_id, stu_id)
        print(f"[{_now()}] [映射已保存] ID「{raw_id}」 → 学生「{stu_id.upper()}」（已写入 {cfg_mgr.config_path.name}）")
        return True

    if head in ("ports", "com"):
        ports = list_available_ports()
        print(f"[{_now()}] 当前可用串口：" + ("\n    " + "\n    ".join(ports) if ports else "未检测到任何串口"))
        return True

    if head in ("help", "?"):
        print(
            "可用快捷指令：\n"
            "  直接输入任意 ID（如 1 或 CARD_001 或 D01）回车  -> 立即触发下载并打印该生学情报告\n"
            "  map <ID> <学号>（如 map 6 D08）                 -> 新增或修改 ID 与学生的对应关系并保存\n"
            "  list                                            -> 查看当前全部 ID 映射表\n"
            "  ports                                           -> 查看当前电脑连接的串口列表\n"
            "  quit                                            -> 退出程序"
        )
        return True

    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="STM32 串口监听自动下载并打印学生学情报告")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="配置文件路径（默认 stm32_config.json）")
    parser.add_argument("--port", default=None, help="串口号（如 COM3，或 AUTO 自动识别）")
    parser.add_argument("--baudrate", type=int, default=None, help="串口波特率（如 115200、9600）")
    parser.add_argument("--backend", default=None, help="FastAPI 后端地址（如 http://127.0.0.1:8000）")
    parser.add_argument("--printer", default=None, help="指定打印机名称（留空使用系统默认打印机）")
    parser.add_argument("--no-advice", action="store_true", help="生成的学情报告不包含个性化建议")
    parser.add_argument("--dry", action="store_true", help="无纸测试模式：正常下载 PDF 并校验渲染，但不实际出纸")
    parser.add_argument("--console", action="store_true", help="纯控制台输入模式（不打开串口，仅用键盘输入 ID 测试）")
    parser.add_argument("--once", default="", help="单次执行指定 ID 后立即退出（如 --once 1）")
    parser.add_argument("--list-ports", action="store_true", help="列出当前电脑所有串口并退出")
    args = parser.parse_args()

    if args.list_ports:
        ports = list_available_ports()
        if not ports:
            print("当前未检测到可用串口。")
        else:
            print("检测到以下串口：")
            for line in ports:
                print("  ", line)
        return 0

    overrides = {
        "serial_port": args.port,
        "baudrate": args.baudrate,
        "backend_url": args.backend,
        "printer_name": args.printer,
        "include_advice": False if args.no_advice else None,
        "dry_run": True if args.dry else None,
    }
    cfg_mgr = ConfigManager(Path(args.config), overrides)
    cfg = cfg_mgr.reload_if_needed()
    last_printed_at: dict[str, float] = {}

    if args.once.strip():
        ok = process_incoming_id(args.once.strip(), "单次指令", cfg_mgr, last_printed_at)
        return 0 if ok else 1

    serial_desc = (
        "纯控制台模式 (--console)"
        if args.console
        else f"{cfg['serial_port']} @ {cfg['baudrate']} bps"
    )
    print_desc = (
        "无纸测试 (--dry)"
        if cfg.get("dry_run")
        else (cfg.get("printer_name") or "系统默认打印机")
    )
    print("=" * 68)
    print("  智教慧学 · STM32 串口监听自动下载打印客户端")
    print(f"  配置文件 : {cfg_mgr.config_path}")
    print(f"  下载目录 : {DOWNLOAD_DIR}")
    print(f"  后端地址 : {cfg['backend_url']}")
    print(f"  串口设置 : {serial_desc}")
    print(f"  打印模式 : {print_desc}")
    print(f"  已配映射 : {len(cfg.get('id_to_student') or {})} 条（随时可修改保存配置文件或输入 `map ID 学号`）")
    print("  提示：随时可在本窗口输入 ID 回车测试，输入 help 查看命令，Ctrl+C 退出。")
    print("=" * 68)

    event_queue: queue.Queue[tuple[str, str]] = queue.Queue()
    _start_console_reader(event_queue)

    ser_conn = None
    last_wait_tip = 0.0

    try:
        while True:
            cfg = cfg_mgr.reload_if_needed()

            while not event_queue.empty():
                src, text = event_queue.get_nowait()
                if not _handle_console_command(text, cfg_mgr):
                    process_incoming_id(text, src, cfg_mgr, last_printed_at, ser_conn=ser_conn)

            if args.console:
                time.sleep(0.1)
                continue

            if serial is None:
                print(f"[{_now()}] [错误] 当前环境未安装 pyserial，请执行 pip install -r requirements.txt")
                return 2

            if ser_conn is not None and ser_conn.is_open:
                if ser_conn.baudrate != int(cfg["baudrate"]):
                    ser_conn.baudrate = int(cfg["baudrate"])
                    print(f"[{_now()}] [串口] 波特率已动态调整为 {ser_conn.baudrate} bps")
            else:
                target_port = detect_serial_port(cfg["serial_port"])
                if not target_port:
                    if time.monotonic() - last_wait_tip >= 8.0:
                        print(f"[{_now()}] [等待串口] 暂未检测到 STM32 串口，插入设备后将自动连接（也可直接在此输入 ID 测试）...")
                        last_wait_tip = time.monotonic()
                    time.sleep(0.5)
                    continue

                try:
                    ser_conn = serial.Serial(
                        port=target_port,
                        baudrate=int(cfg["baudrate"]),
                        timeout=0.15,
                    )
                    ser_conn.reset_input_buffer()
                    print(f"[{_now()}] [串口已连接] {target_port} @ {cfg['baudrate']} bps，正在监听 STM32 发来的 ID...")
                except Exception as exc:
                    if time.monotonic() - last_wait_tip >= 8.0:
                        print(f"[{_now()}] [串口连接重试] 无法打开 {target_port}（{exc}），将继续重试...")
                        last_wait_tip = time.monotonic()
                    ser_conn = None
                    time.sleep(0.8)
                    continue

            try:
                raw_bytes = ser_conn.readline()
                if raw_bytes:
                    decoded = raw_bytes.decode("utf-8", errors="ignore").strip()
                    if decoded:
                        process_incoming_id(
                            decoded,
                            f"STM32({ser_conn.port})",
                            cfg_mgr,
                            last_printed_at,
                            ser_conn=ser_conn,
                        )
            except Exception as exc:
                print(f"[{_now()}] [串口断开] 读取异常（{exc}），等待重新连接...")
                try:
                    ser_conn.close()
                except Exception:
                    pass
                ser_conn = None
                time.sleep(1.0)
    except KeyboardInterrupt:
        print(f"\n[{_now()}] 监听服务已停止。")
    finally:
        if ser_conn is not None:
            try:
                ser_conn.close()
            except Exception:
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
