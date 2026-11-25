# STM32 串口监听自动下载并打印客户端（独立文件夹版）

本文件夹 `stm32_print/` **完全独立自包含**（内置串口监听、HTTP PDF 下载与 Windows 无弹窗静默打印模块），既可以直接在本项目目录下双击运行，也可以把整个 `stm32_print` 文件夹单独复制到任何连接了 STM32 与打印机的 Windows 电脑上独立使用。

## 目录结构

- `stm32_auto_print.py`：主程序（监听 STM32 串口 / 控制台输入 → 映射学号 → 请求后端下载 PDF → 调用打印）
- `stm32_config.json`：配置文件（自定义串口、波特率、后端地址、打印机名称、ID 与学生映射表，支持**保存即热生效**）
- `print_pdf_file.py`：内置 Windows GDI 静默打印模块（不弹窗、不依赖外部 PDF 阅读器）
- `requirements.txt`：独立运行所需的最小依赖清单
- `启动监听.bat`：Windows 双击一键启动脚本
- `downloads/`：自动下载保存的学情报告 PDF 目录（运行后自动生成）

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
