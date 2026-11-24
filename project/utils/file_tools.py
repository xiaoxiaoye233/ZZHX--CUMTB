import csv
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

from config.db_conf import data_layer_root, steps_dir, upload_target_dir


def to_int(value):
    """把字符串转成 int，空字符串返回 None"""
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    return int(float(text))


def to_float(value):
    """把字符串转成 float，空字符串返回 None"""
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    return float(text)


def read_csv_file(file_path: Path) -> list[dict]:
    """读取 CSV 文件，返回字典列表"""
    if not file_path.exists():
        return []
    with file_path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_json_file(file_path: Path):
    """读取 JSON 文件"""
    if not file_path.exists():
        return None
    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_uploaded_bytes(content: bytes, filename: str, target_name: str) -> Path:
    """
    保存教师上传的文件字节到 模拟学情数据 目录：
    - target_name: '模拟学生' 或 '作答记录'
    - 如果已有同名文件，先删除旧文件再保存；若浏览器正直接上传目标目录里的同一文件导致无法 unlink，则直接原地覆盖
    """
    upload_target_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(filename or "").suffix.lower() or ".csv"
    save_path = upload_target_dir / f"{target_name}{ext}"

    # 1. 删除已有的同名文件（如 模拟学生.csv / 模拟学生.xlsx）
    for old_file in upload_target_dir.glob(f"{target_name}.*"):
        if not old_file.is_file():
            continue
        try:
            old_file.unlink()
        except PermissionError as exc:
            # 如果删不掉的是不同后缀的旧文件，说明被外部程序占用，明确提示
            if old_file.resolve() != save_path.resolve():
                raise PermissionError(
                    f"旧文件「{old_file.name}」正被 Excel/WPS 或其他程序占用，请关闭后重试"
                ) from exc

    # 2. 写入新内容（若目标文件未能 unlink，尝试原地覆盖）
    try:
        save_path.write_bytes(content)
    except PermissionError as exc:
        # 浏览器直接选中目标目录里的同一个原文件上传时，请求结束前浏览器会短暂持有读锁；
        # 如果内容完全一致，直接视为已替换保存成功
        if save_path.is_file() and save_path.read_bytes() == content:
            return save_path
        raise PermissionError(
            f"文件「{save_path.name}」正被 Excel/WPS 或其他程序占用，请关闭后重试（或将待上传文件放到其他文件夹后再上传）"
        ) from exc

    return save_path


def _pick_script_python() -> str:
    """选择能运行 steps 脚本的 Python（如果当前 venv 没装 pandas，就从系统 PATH 里找装了 pandas 的 python）"""
    if importlib.util.find_spec("pandas") is not None:
        return sys.executable

    current_exe = Path(sys.executable).resolve()
    candidates = []
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        if not folder:
            continue
        exe = Path(folder) / "python.exe"
        if exe.is_file() and exe.resolve() != current_exe:
            candidates.append(str(exe))

    for exe in candidates:
        check = subprocess.run(
            [exe, "-c", "import pandas"],
            capture_output=True,
            text=True,
        )
        if check.returncode == 0:
            return exe

    return sys.executable


def run_steps_scripts() -> list[str]:
    """依次运行 数据层/src/steps 文件夹里的所有 .py 脚本"""
    python_exe = _pick_script_python()
    executed = []

    for script in sorted(steps_dir.glob("*.py")):
        if script.name.startswith("__"):
            continue
        result = subprocess.run(
            [python_exe, str(script)],
            cwd=str(data_layer_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise RuntimeError(f"运行脚本 {script.name} 失败：{result.stderr or result.stdout}")
        executed.append(script.name)
    return executed
