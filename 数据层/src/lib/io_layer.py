"""读数据层：只负责把 5 张 CSV 读成 DataFrame，不做任何清洗与判断。

设计约束（口径卡 R1）：
- 固定编码 utf-8-sig，**不猜编码**（禁止 chardet），保证任何机器结果一致。
- 全部按字符串读入，数值列显式转换，避免 pandas 自动把 "001" 变 1。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ENC = "utf-8-sig"

FILES = {
    "curriculum": "课程要求.csv",
    "materials": "题目与材料.csv",
    "students": "模拟学生.csv",
    "nodes": "测验节点.csv",
    "records": "作答记录.csv",
}

NUMERIC_RECORD_COLS = ["修订版本", "得分", "满分"]


@dataclass
class Dataset:
    curriculum: pd.DataFrame
    materials: pd.DataFrame
    students: pd.DataFrame
    nodes: pd.DataFrame
    records: pd.DataFrame
    data_dir: Path


def _read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False, encoding=ENC)


def load_datasets(data_dir: str | Path) -> Dataset:
    data_dir = Path(data_dir)
    missing = [f for f in FILES.values() if not (data_dir / f).exists()]
    if missing:
        raise FileNotFoundError(f"缺少数据文件：{missing}（目录 {data_dir}）")

    frames = {key: _read(data_dir / name) for key, name in FILES.items()}

    rec = frames["records"]
    for col in NUMERIC_RECORD_COLS:
        rec[col] = pd.to_numeric(rec[col], errors="coerce")

    return Dataset(data_dir=data_dir, **frames)
