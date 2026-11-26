# -*- coding: utf-8 -*-
"""数据接入层：把老师上传的 Excel / CSV 变成五张规范 CSV。

这一层只做"文件 → 表"的搬运与格式统一，**一分一毫都不改分数**：
- 认表：按文件名猜，猜不出就按表头对；
- 找表头：前 10 行里找那一行，能容忍上面有标题、日期、合计行；
- 统一格式：全角转半角、去前后空格（含全角空格）、日期三种写法归一、
  "缺考/未交/-" 这类占位词统一成空；
- 存规范 CSV：`_normalized/<原文件名>`，编码 utf-8-sig，空值就是空。

为什么要有这一层：老师发来的东西不可控（合并单元格、多 sheet、合计行、
公式、里外一堆空格）。让 `io_layer` 直接读原始文件，等于把不确定性带进
整条数据线。中间的规范 CSV 是内部格式，跟着版本一起存，出问题能倒查。
"""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
ENC = "utf-8-sig"
HEADER_SCAN_ROWS = 10          # 表头最多往下找 10 行
# 空值占位词只在这些列上换算成空：得分、满分。
# 别的列不能套——「未作答」是评分状态的合法取值，套上去就把它吃掉了。
MARKER_COLUMNS = {"得分", "满分"}
# 全角转半角只在这类列上做：编号、分数、日期、状态。说明性的文字列（主题名、
# 课标范围、教材页、题干）一律不转——「上册110-148；下册87-119」里的分号
# 是全角还是半角，是老师原文的一部分，不该被我们改掉。
NFKC_KEYWORDS = ("编号", "版本", "得分", "满分", "日期", "时间", "状态", "年级",
                 "题型", "类型", "题数")
EMPTY_MARKERS = {
    "", "-", "—", "/", "\\", "缺", "无", "缺考", "未交", "未考", "未批", "待批",
    "na", "n/a", "nan", "none", "null", "空",
}
DATE_PATTERN = [
    re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$"),      # 2026-01-20
    re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})日?$"),          # 2026年1月20日
    re.compile(r"^(\d{4})(\d{2})(\d{2})$"),                     # 20260120
]
DATE_COLUMNS = {"模拟提交时间", "模拟测验日期"}


# --------------------------------------------------------------------------
# 表规格
# --------------------------------------------------------------------------
@dataclass
class TableSpec:
    key: str                 # 内部键
    filename: str            # 规范文件名
    columns: list[str]       # 必须有的列（逐字）
    key_columns: list[str]   # 主键（判重、合并用）
    keywords: list[str]      # 文件名里出现这些词，就当是这张表
    flow: bool = False       # 是不是流水表（只追加、不整表替换）
    answer_columns: list[str] = field(default_factory=list)  # 不能动格式的自由文本


TABLES: list[TableSpec] = [
    TableSpec("curriculum", "课程要求.csv",
              ["主题编号", "主题", "主题目标", "指标编号", "观察指标",
               "课标整理编号", "课标文件页／正文页", "教材正文页"],
              ["指标编号"], ["课程", "要求", "课标"]),
    TableSpec("materials", "题目与材料.csv",
              ["材料编号", "主题编号", "材料类型", "题型", "题干或内容", "选项",
               "参考答案", "参考解析", "满分", "评分点", "指标编号", "来源或资料文件"],
              ["材料编号"], ["题目", "材料"],
              answer_columns=["题干或内容", "选项", "参考答案", "参考解析", "评分点"]),
    TableSpec("students", "模拟学生.csv",
              ["学生编号", "模拟班级编号", "年级"],
              ["学生编号"], ["学生", "名单", "花名册"]),
    TableSpec("nodes", "测验节点.csv",
              ["节点编号", "模拟测验日期", "已教及测量主题", "说明", "可用题目编号"],
              ["节点编号"], ["节点", "测验", "考试安排"]),
    TableSpec("records", "作答记录.csv",
              ["记录编号", "学生编号", "材料编号", "主题编号", "节点编号", "作答事件编号",
               "修订版本", "模拟提交时间", "评分状态", "得分", "满分", "学生最终作答",
               "解答过程", "评分点得分"],
              ["记录编号"], ["作答", "记录", "成绩"],
              flow=True,
              answer_columns=["学生最终作答", "解答过程", "评分点得分"]),
]

BY_KEY = {t.key: t for t in TABLES}


# --------------------------------------------------------------------------
# 单元格格式统一
# --------------------------------------------------------------------------
def _to_halfwidth(text: str) -> str:
    """全角转半角（含全角空格）。只做字符层面，不改语义。"""
    return unicodedata.normalize("NFKC", text)


def _normalize_date(text: str) -> str:
    for pattern in DATE_PATTERN:
        m = pattern.match(text)
        if m:
            y, mo, d = (int(x) for x in m.groups())
            return f"{y:04d}-{mo:02d}-{d:02d}"
    return text


def clean_cell(value, column: str, spec: TableSpec) -> str:
    """把一个单元格洗成规范字符串。answer_columns 只去边空格，不动内容。"""
    if value is None:
        return ""
    text = str(value)
    if column in spec.answer_columns:
        return text.replace("\u3000", " ").strip()
    if any(word in column for word in NFKC_KEYWORDS):
        text = _to_halfwidth(text)
    text = text.replace("\u3000", " ").strip()
    text = re.sub(r"\s+", " ", text)
    if column in MARKER_COLUMNS and text.lower() in EMPTY_MARKERS:
        return ""
    if column in DATE_COLUMNS:
        return _normalize_date(text)
    return text


# --------------------------------------------------------------------------
# 读文件（csv 四种编码 / xlsx 走 openpyxl，公式取算好的值）
# --------------------------------------------------------------------------
def _read_csv_rows(path: Path) -> list[list[str]]:
    last_error: Exception | None = None
    for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            with path.open(encoding=enc, newline="") as f:
                return [row for row in csv.reader(f)]
        except UnicodeDecodeError as exc:     # 编码不对，换下一个
            last_error = exc
    raise ValueError(f"读不出来（编码都试过了）：{path.name}：{last_error}")


def _read_xlsx_rows(path: Path) -> dict[str, list[list[object]]]:
    from openpyxl import load_workbook

    workbook = load_workbook(path, data_only=True, read_only=True)  # data_only：公式取计算结果
    sheets: dict[str, list[list[object]]] = {}
    for name in workbook.sheetnames:
        sheet = workbook[name]
        rows = [list(row) for row in sheet.iter_rows(values_only=True)]
        sheets[name] = rows
    workbook.close()
    return sheets


def read_upload(path: Path) -> dict[str, list[list[object]]]:
    """返回 {sheet 名: 二维表}。csv 只有一个 sheet。"""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return {path.stem: _read_csv_rows(path)}
    if suffix in (".xlsx", ".xlsm"):
        return _read_xlsx_rows(path)
    if suffix == ".xls":
        raise ValueError(f"{path.name} 是老式 .xls，请用 Excel 另存为 .xlsx 再传")
    raise ValueError(f"不认识的文件类型：{path.name}（只收 .csv / .xlsx）")


# --------------------------------------------------------------------------
# 认表 + 找表头
# --------------------------------------------------------------------------
def _canon(text: str) -> str:
    """表头比对用的规范形：全角转半角后比较，输出仍用规格里的原名。"""
    return _to_halfwidth(str(text)).replace("\u3000", " ").strip()


def _aliases(spec: TableSpec) -> dict[str, str]:
    """规范形 → 规格列名。老师表里写全角斜杠、全角括号都认。"""
    table = {_canon(c): c for c in spec.columns}
    table.update({c: c for c in spec.columns})
    return table


def _score_header(cells: list[str], spec: TableSpec) -> int:
    seen = {c for c in cells if c}
    return len(seen & set(_aliases(spec)))


def guess_spec(filename: str, sheets: dict[str, list[list[object]]]) -> tuple[TableSpec | None, str]:
    """认表：先按表头打分（更可信），表头看不清才拿文件名兜底。

    返回 (规格, 依据)，依据是 "表头" / "文件名" / ""。
    """
    best, best_score = None, 0
    for rows in sheets.values():
        for row in rows[:HEADER_SCAN_ROWS]:
            cells = [_to_halfwidth(str(c)).strip() for c in row if c is not None]
            for spec in TABLES:
                score = _score_header(cells, spec)
                if score > best_score:
                    best, best_score = spec, score
    if best is not None and best_score >= 3:
        return best, "表头"
    stem = Path(filename).stem
    for spec in TABLES:
        if any(k in stem for k in spec.keywords):
            return spec, "文件名"
    return None, ""


def locate_header(rows: list[list[object]], spec: TableSpec) -> tuple[int, list[str], list[str]]:
    """在前 10 行里找表头。返回 (行号, 找到的列, 缺的列)。"""
    alias = _aliases(spec)
    best_idx, best_hit, best_cells = -1, -1, []
    for idx, row in enumerate(rows[:HEADER_SCAN_ROWS]):
        cells = [_canon(c) if c is not None else "" for c in row]
        hit = len({c for c in cells if c} & set(alias))
        if hit > best_hit:
            best_idx, best_hit, best_cells = idx, hit, cells
    if best_idx < 0:
        return -1, [], list(spec.columns)
    found = [alias[c] for c in best_cells if c in alias]
    missing = [c for c in spec.columns if c not in found]
    return best_idx, found, missing


def build_frame(rows: list[list[object]], header_idx: int, spec: TableSpec) -> tuple[pd.DataFrame, list[str]]:
    """按表头取列，多余列丢掉并记下来，缺列由调用方判错。"""
    alias = _aliases(spec)
    header = [_canon(c) if c is not None else "" for c in rows[header_idx]]
    index_of = {}
    extra: list[str] = []
    for pos, name in enumerate(header):
        if name in alias and alias[name] not in index_of:
            index_of[alias[name]] = pos
        elif name and name not in alias:
            extra.append(name)
    data = []
    for row in rows[header_idx + 1:]:
        if not any(str(c).strip() for c in row if c is not None):   # 空行
            continue
        data.append({
            col: clean_cell(row[pos] if pos < len(row) else "", col, spec)
            for col, pos in index_of.items()
        })
    frame = pd.DataFrame(data, columns=[c for c in spec.columns if c in index_of])
    return frame, extra


def _looks_like_total_row(frame: pd.DataFrame, spec: TableSpec) -> pd.Series:
    """合计行/小计行：主键那列空着，或者写着"合计/小计/总计"。"""
    key = spec.key_columns[0]
    if key not in frame.columns:
        return pd.Series([False] * len(frame))
    text = frame[key].astype(str).str.strip()
    return text.eq("") | text.str.contains("合计|小计|总计|共计", na=False)


# --------------------------------------------------------------------------
# 接入主流程
# --------------------------------------------------------------------------
def ingest(upload_dir: str | Path, out_root: str | Path | None = None) -> dict:
    """把一个上传目录里的文件全部收下，写成规范 CSV。

    返回报告：{batch_dir, normalized_dir, tables{key: {...}}, errors[], warnings[]}
    只要有一张表认不出来或缺列，errors 里会写清楚，调用方据此判"硬拦"。
    """
    upload_dir = Path(upload_dir)
    if not upload_dir.is_dir():
        raise FileNotFoundError(f"上传目录不存在：{upload_dir}")
    batch_dir = Path(out_root) / upload_dir.name if out_root else upload_dir
    if out_root:                      # 同名批次再来一次：另起一个目录，不覆盖上一次
        base_batch, n = batch_dir, 1
        while batch_dir.exists() and any(batch_dir.iterdir()):
            n += 1
            batch_dir = base_batch.with_name(f"{base_batch.name}-{n}")
    normalized = batch_dir / "_normalized"
    normalized.mkdir(parents=True, exist_ok=True)

    report = {"batch_dir": str(batch_dir), "normalized_dir": str(normalized),
              "tables": {}, "errors": [], "warnings": [], "skipped": []}
    files = sorted(p for p in upload_dir.iterdir() if p.is_file() and not p.name.startswith("_"))

    for path in files:
        # .xls 也放进来，让 read_upload 明确拒绝并给"另存为 .xlsx"的提示
        if path.suffix.lower() not in (".csv", ".xlsx", ".xlsm", ".xls"):
            report["skipped"].append({"file": path.name, "reason": "不是表格文件（只收 .csv / .xlsx）"})
            continue
        try:
            sheets = read_upload(path)
        except ValueError as exc:
            report["errors"].append({"file": path.name, "problem": str(exc)})
            continue

        spec, matched_by = guess_spec(path.name, sheets)
        if spec is None:
            report["errors"].append({"file": path.name,
                                     "problem": "认不出这是哪张表（表头对不上五张表里的任何一张）"})
            continue
        if spec.key in report["tables"]:
            first = report["tables"][spec.key]["source_file"]
            report["warnings"].append({"file": path.name,
                                       "warning": f"这张表和「{first}」是同一张，已忽略，只认先出现的那份"})
            continue

        sheet_name, rows = next(iter(sheets.items()))
        header_idx, found, missing = locate_header(rows, spec)
        if len(sheets) > 1:                       # 多 sheet：挑表头最像的那个
            best = max(sheets.items(),
                       key=lambda kv: len(set(locate_header(kv[1], spec)[1]) & set(spec.columns)))
            sheet_name, rows = best
            header_idx, found, missing = locate_header(rows, spec)
            report["warnings"].append({"file": path.name,
                                       "warning": f"这个工作簿有 {len(sheets)} 个 sheet，用的是「{sheet_name}」"})
        if missing:
            report["errors"].append({"file": path.name, "table": spec.filename,
                                     "problem": f"表头缺列：{'、'.join(missing)}"})
            continue

        frame, extra = build_frame(rows, header_idx, spec)
        total_mask = _looks_like_total_row(frame, spec)
        dropped = int(total_mask.sum())
        if dropped:
            frame = frame[~total_mask].reset_index(drop=True)
            report["warnings"].append({"file": path.name, "warning": f"丢掉了 {dropped} 行合计/空主键行"})

        out_path = normalized / spec.filename
        frame.to_csv(out_path, index=False, encoding=ENC)
        report["tables"][spec.key] = {
            "filename": spec.filename,
            "source_file": path.name,
            "matched_by": matched_by,
            "sheet": sheet_name,
            "header_row": header_idx + 1,
            "rows": int(len(frame)),
            "dropped_total_rows": dropped,
            "extra_columns": extra,
            "normalized": str(out_path.relative_to(batch_dir).as_posix()),
        }
        if extra:
            report["warnings"].append({"file": path.name,
                                       "warning": f"多出的列已忽略：{'、'.join(extra)}"})

    (batch_dir / "转换日志.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return report


def merge(base_dir: str | Path, normalized_dir: str | Path, mode: str = "append") -> dict:
    """把这一批的规范 CSV 合到基准数据上。

    mode="full"   ：五张表按这一批的整表替换（老师导出的是一份完整数据）
    mode="append" ：主数据（学生/题目/节点/课标）整表替换；作答记录按主键追加去重
    合并结果写进 `_merged/`，仍然是五张规范的 CSV，后面所有步骤只认这个目录。
    """
    base_dir, normalized_dir = Path(base_dir), Path(normalized_dir)
    merged_dir = normalized_dir.parent / "_merged"
    merged_dir.mkdir(parents=True, exist_ok=True)

    result = {"mode": mode, "tables": {}, "warnings": []}
    for spec in TABLES:
        src_new = normalized_dir / spec.filename
        src_base = base_dir / spec.filename
        new = pd.read_csv(src_new, dtype=str, keep_default_na=False, encoding=ENC) if src_new.exists() else None
        base = pd.read_csv(src_base, dtype=str, keep_default_na=False, encoding=ENC) if src_base.exists() else None

        if new is not None and len(new) == 0:
            report_warning = {"table": spec.filename,
                              "warning": "这一批这张表只有表头、没有数据行，已忽略（沿用基准）"}
            new = None
            result["warnings"].append(report_warning)

        if new is None:                     # 这一批没带这张表：沿用基准
            if base is None:
                result["warnings"].append({"table": spec.filename, "warning": "这一批没带，基准里也没有"})
                continue
            out, added, changed = base, 0, 0
        elif base is None or mode == "full" or not spec.flow:
            out, added, changed = new, len(new), 0
        else:
            key = spec.key_columns
            merged = pd.concat([base, new], ignore_index=True)
            before = len(merged)
            merged = merged.drop_duplicates(subset=key, keep="last")
            out = merged.reset_index(drop=True)
            added, changed = len(out) - len(base), before - len(out)

        out.to_csv(merged_dir / spec.filename, index=False, encoding=ENC)
        result["tables"][spec.key] = {"rows": int(len(out)),
                                      "base_rows": 0 if base is None else int(len(base)),
                                      "new_rows": 0 if new is None else int(len(new)),
                                      "added": added, "duplicates_replaced": changed}
    result["merged_dir"] = str(merged_dir)
    (merged_dir / "合并说明.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                              encoding="utf-8")
    return result
