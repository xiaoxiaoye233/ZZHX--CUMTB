# -*- coding: utf-8 -*-
"""上传体检层：四道门，一关一关过。

门 1 文件层   —— 五张表在不在、空不空
门 2 结构层   —— 表头逐字对、主键不重复、外键都能对上
门 3 内容层   —— 编号格式、分数是否合法、状态取值、日期格式
门 4 身份层   —— 声明和实际对不对、和已有数据重不重

判完只给两档：
- **硬拦**（hard）：错到没法用，必须改原表重传；
- **提示**（soft）：能用，但要人看一眼再决定（超满分、重复上传、数量异常）。

这一层不改任何分数。超满分、负数这类记录在 clean 阶段会按 R1 剔除并记账，
这里只负责把"有几条、是哪几条"摆出来让人确认。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from ingest import BY_KEY, ENC, TABLES, TableSpec

# 编号格式
ID_PATTERNS = {
    "students": ("学生编号", re.compile(r"^D\d{2}$")),
    "records": ("记录编号", re.compile(r"^DR\d{4}$")),
    "nodes": ("节点编号", re.compile(r"^N\d{2}$")),
    "materials": ("材料编号", re.compile(r"^[QLB]\d{2,3}$")),
}
STUDENT_PATTERN = re.compile(r"^D\d{2}$")
CLASS_PATTERN = re.compile(r"^(DC\d{2}|全年级)$")
THEME_PATTERN = re.compile(r"^T\d{2}$")
INDICATOR_PATTERN = re.compile(r"^T\d{2}I\d$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?)?(Z|[+-]\d{2}:?\d{2})?$")
SCORING_STATUS = {"已评分", "待评分", "未作答", ""}   # 空 = 未作答（R11：交白卷不是"没做"）
GRADE_OK = {"7", "七年级"}
GRADE_WORDS = {"优", "良", "中", "及格", "不及格", "差", "合格", "不合格",
               "A", "B", "C", "D", "E", "甲", "乙", "丙", "丁"}

OVERLAP_DUPLICATE = 0.95        # 重叠到这个程度，基本是同一份数据传了两次
OVERLAP_LOW = 0.10              # 低于这个，提醒确认是不是传错了表
SIZE_RATIO_MAX = 3.0            # 新数据是基准的 3 倍以上，提醒看一眼


def _load(data_dir: Path) -> dict[str, pd.DataFrame]:
    frames = {}
    for spec in TABLES:
        path = data_dir / spec.filename
        if path.exists():
            frames[spec.key] = pd.read_csv(path, dtype=str, keep_default_na=False, encoding=ENC)
    return frames


def _issue(code, severity, message, samples=None, must_confirm=False) -> dict:
    return {"code": code, "severity": severity, "message": message,
            "samples": samples or [], "must_confirm": must_confirm}


SPLIT_RE = re.compile(r"[、,，;；/\s]+")


def _split_ids(value) -> list[str]:
    """一格里有好几个编号时（学习卡、可用题目），拆开再逐个对。"""
    return [x for x in SPLIT_RE.split(str(value)) if x]


def _sample(series: pd.Series, n: int = 5) -> list[str]:
    values = [str(x) for x in series.dropna().unique() if str(x).strip()]
    return values[:n]


# --------------------------------------------------------------------------
# 门 1 + 门 2
# --------------------------------------------------------------------------
def check_presence(frames: dict) -> list[dict]:
    issues = []
    for spec in TABLES:
        frame = frames.get(spec.key)
        if frame is None:
            issues.append(_issue("file_missing", "硬拦", f"缺少《{spec.filename}》"))
        elif len(frame) == 0:
            issues.append(_issue("table_empty", "硬拦", f"《{spec.filename}》一行数据都没有"))
    return issues


def check_schema(frames: dict) -> list[dict]:
    issues = []
    for spec in TABLES:
        frame = frames.get(spec.key)
        if frame is None:
            continue
        have = list(frame.columns)
        missing = [c for c in spec.columns if c not in have]
        extra = [c for c in have if c not in spec.columns]
        if missing:
            issues.append(_issue("column_missing", "硬拦",
                                 f"《{spec.filename}》缺列：{'、'.join(missing)}"))
        if extra:
            issues.append(_issue("column_extra", "提示",
                                 f"《{spec.filename}》多出列（已忽略）：{'、'.join(extra)}"))
        key = spec.key_columns[0]
        if key in have:
            dup = frame[frame[key].duplicated(keep=False)][key]
            if len(dup):
                issues.append(_issue("duplicate_key", "硬拦",
                                     f"《{spec.filename}》主键 {key} 有 {len(dup)} 行重复",
                                     _sample(dup)))
    return issues


def check_foreign_keys(frames: dict) -> list[dict]:
    issues = []
    rules = [
        ("records", "学生编号", "students", "学生编号", "作答记录里的学生不在名单里", False),
        ("records", "材料编号", "materials", "材料编号", "作答题目的编号不在题目表里", False),
        ("records", "节点编号", "nodes", "节点编号", "作答记录的考试编号不在考试安排里", False),
        ("records", "主题编号", "curriculum", "主题编号", "作答记录的主题编号不在课程要求里", False),
        ("materials", "指标编号", "curriculum", "指标编号", "题目的指标编号不在课程要求里", True),
    ]
    for left, lcol, right, rcol, message, multi in rules:
        lf, rf = frames.get(left), frames.get(right)
        if lf is None or rf is None or lcol not in lf.columns or rcol not in rf.columns:
            continue
        known = set(rf[rcol])
        if multi:      # 一格多个编号：拆开逐个对
            bad_values = [x for cell in lf[lcol] for x in _split_ids(cell) if x not in known]
            bad = pd.Series(bad_values, dtype=str)
        else:
            bad = lf[(lf[lcol] != "") & (~lf[lcol].isin(known))][lcol]
        if len(bad):
            issues.append(_issue("orphan_foreign_key", "硬拦",
                                 f"{message}（{len(bad)} 行）", _sample(bad)))
    # 考试安排的可用题号也得在题目表里
    nodes, mats = frames.get("nodes"), frames.get("materials")
    if nodes is not None and mats is not None and "可用题目编号" in nodes.columns:
        known = set(mats["材料编号"])
        bad = []
        for value in nodes["可用题目编号"]:
            for qid in _split_ids(value):
                if qid not in known:
                    bad.append(qid)
        if bad:
            issues.append(_issue("unknown_question_in_node", "硬拦",
                                 f"考试安排里引用了不存在的题目（{len(bad)} 个）", bad[:5]))
    return issues


# --------------------------------------------------------------------------
# 门 3
# --------------------------------------------------------------------------
def check_values(frames: dict) -> list[dict]:
    issues = []
    for key, (column, pattern) in ID_PATTERNS.items():
        frame = frames.get(key)
        if frame is None or column not in frame.columns:
            continue
        bad = frame[~frame[column].astype(str).str.match(pattern)][column]
        if len(bad):
            issues.append(_issue("bad_id_format", "硬拦",
                                 f"《{BY_KEY[key].filename}》{column} 格式不对（{len(bad)} 行）",
                                 _sample(bad)))

    rec = frames.get("records")
    if rec is not None and "主题编号" in rec.columns:
        bad = rec[~rec["主题编号"].astype(str).str.match(THEME_PATTERN)]["主题编号"]
        if len(bad):
            issues.append(_issue("bad_theme_format", "硬拦",
                                 f"作答记录 主题编号 格式不对（{len(bad)} 行）", _sample(bad)))

    mat = frames.get("materials")
    if mat is not None and "指标编号" in mat.columns:
        bad_ids = []
        for value in mat["指标编号"].astype(str):
            for one in _split_ids(value):
                if not INDICATOR_PATTERN.match(one):
                    bad_ids.append(one)
        if bad_ids:
            issues.append(_issue("bad_indicator_format", "硬拦",
                                 f"题目与材料 指标编号 格式不对（{len(bad_ids)} 处）",
                                 sorted(set(bad_ids))[:5]))

    # 下面五项只看作答记录这张表，所以先单独判 None：
    # 门 1 已经为"缺表"报了硬拦，这里不能再抛 AttributeError，
    # 否则最需要报告的那次校验反而出不来。
    if rec is not None:
        if "评分状态" in rec.columns:
            bad = rec[~rec["评分状态"].isin(SCORING_STATUS)]["评分状态"]
            if len(bad):
                issues.append(_issue("bad_scoring_status", "硬拦",
                                     "评分状态只认 已评分 / 待评分 / 未作答（空着也算未作答），"
                                     f"有 {len(bad)} 行不是", _sample(bad)))

        if "模拟提交时间" in rec.columns:
            bad = rec[~rec["模拟提交时间"].astype(str).str.match(DATE_RE)]["模拟提交时间"]
            if len(bad):
                issues.append(_issue("bad_date", "提示",
                                     f"提交时间不是 YYYY-MM-DD 的有 {len(bad)} 行", _sample(bad)))

        for column in ("得分", "满分"):
            if column not in rec.columns:
                continue
            text = rec[column].astype(str)
            non_numeric = text[(text != "") & (~text.str.fullmatch(r"-?\d+(\.\d+)?"))]
            if len(non_numeric):
                # 等级制/文字分数：绝不猜，直接拦
                words = {str(x).strip().upper() for x in non_numeric}
                severity = "硬拦" if words & GRADE_WORDS else "提示"
                issues.append(_issue("score_not_numeric", severity,
                                     f"{column} 有 {len(non_numeric)} 行不是数字", _sample(non_numeric)))
        if {"得分", "满分"} <= set(rec.columns):
            score = pd.to_numeric(rec["得分"], errors="coerce")
            full = pd.to_numeric(rec["满分"], errors="coerce")
            over = rec[(score > full) & full.notna()]
            if len(over):
                issues.append(_issue("score_over_full", "提示",
                                     f"得分超过满分的有 {len(over)} 条：会按 R1 剔除并记账，"
                                     f"确认后可以继续", _sample(over["记录编号"]), must_confirm=True))
            negative = rec[(score < 0) | (full <= 0)]
            if len(negative):
                issues.append(_issue("score_negative", "提示",
                                     f"得分是负数或满分不是正数的有 {len(negative)} 条",
                                     _sample(negative["记录编号"]), must_confirm=True))

    stu = frames.get("students")
    if stu is not None and "模拟班级编号" in stu.columns:
        bad = stu[~stu["模拟班级编号"].astype(str).str.match(CLASS_PATTERN)]["模拟班级编号"]
        if len(bad):
            issues.append(_issue("bad_class_format", "硬拦",
                                 f"班级编号只认 DC01 这样，有 {len(bad)} 行不对", _sample(bad)))
    return issues


# --------------------------------------------------------------------------
# 门 4
# --------------------------------------------------------------------------
def check_identity(frames: dict, base_frames: dict | None, declare: dict | None) -> tuple[list[dict], dict]:
    issues: list[dict] = []
    facts: dict = {}
    rec, stu = frames.get("records"), frames.get("students")

    if declare and declare.get("class_id") and stu is not None and "模拟班级编号" in stu.columns:
        classes = sorted(set(stu["模拟班级编号"]))
        facts["declared_class"] = declare["class_id"]
        facts["classes_in_data"] = classes
        if declare["class_id"] not in classes:
            issues.append(_issue("class_mismatch", "硬拦",
                                 f"说的是 {declare['class_id']} 的数据，表里出现的是 {'、'.join(classes)}"))
        elif len(classes) > 1:
            issues.append(_issue("class_mixed", "提示",
                                 f"声明的 {declare['class_id']} 在表里，但这份数据里还有 "
                                 f"{'、'.join(c for c in classes if c != declare['class_id'])}"
                                 "（如果这是全年级导出，忽略这条）"))

    if stu is not None and "年级" in stu.columns:
        grades = sorted(set(stu["年级"]))
        facts["grades"] = grades
        if not set(grades) <= GRADE_OK:
            issues.append(_issue("grade_mismatch", "提示",
                                 f"年级是 {'、'.join(grades)}，和前面数据的七年级不一样"))

    if rec is None or base_frames is None or "records" not in base_frames:
        return issues, facts

    base = base_frames["records"]
    key = BY_KEY["records"].key_columns[0]
    if key not in rec.columns or key not in base.columns:
        return issues, facts
    new_keys = set(rec[key])
    base_keys = set(base[key])
    if base_keys:
        overlap = len(new_keys & base_keys) / len(base_keys)
        facts["record_overlap"] = round(overlap, 4)
        facts["new_records"] = len(rec)
        facts["base_records"] = len(base)
        facts["size_ratio"] = round(len(rec) / len(base), 2)
        if overlap >= OVERLAP_DUPLICATE:
            issues.append(_issue("looks_duplicate", "提示",
                                 f"和当前数据重了 {overlap:.1%}：如果这是老师重新导出的一份完整数据，正常；"
                                 "如果本意只是补新增的记录，说明传的不是增量",
                                 must_confirm=True))
        elif overlap < OVERLAP_LOW:
            issues.append(_issue("overlap_low", "提示",
                                 f"和已有数据只重了 {overlap:.1%}，确认一下是不是传错了表",
                                 must_confirm=True))
        if facts["size_ratio"] > SIZE_RATIO_MAX:
            issues.append(_issue("size_anomaly", "提示",
                                 f"这次 {len(rec)} 行，是已有数据（{len(base)} 行）的 "
                                 f"{facts['size_ratio']} 倍，确认一下", must_confirm=True))
    return issues, facts


# --------------------------------------------------------------------------
# 主入口
# --------------------------------------------------------------------------
def validate_dir(data_dir: str | Path, base_dir: str | Path | None = None,
                 declare: dict | None = None, out_path: str | Path | None = None) -> dict:
    data_dir = Path(data_dir)
    frames = _load(data_dir)
    base_frames = _load(Path(base_dir)) if base_dir else None

    hard: list[dict] = []
    soft: list[dict] = []
    for issues in (check_presence(frames), check_schema(frames), check_foreign_keys(frames),
                   check_values(frames)):
        for issue in issues:
            (hard if issue["severity"] == "硬拦" else soft).append(issue)
    identity_issues, facts = check_identity(frames, base_frames, declare)
    for issue in identity_issues:
        (hard if issue["severity"] == "硬拦" else soft).append(issue)

    stats = {}
    for spec in TABLES:
        frame = frames.get(spec.key)
        stats[spec.key] = {"filename": spec.filename, "rows": 0 if frame is None else int(len(frame))}
    rec = frames.get("records")
    if rec is not None and "评分状态" in rec.columns:
        stats["records"]["scoring_status"] = rec["评分状态"].value_counts().to_dict()
        stats["records"]["students"] = int(rec["学生编号"].nunique())

    report = {
        "data_dir": str(data_dir),
        "base_dir": str(base_dir) if base_dir else None,
        "passed": not hard,
        "confirm_required": any(i["must_confirm"] for i in soft),
        "hard": hard,
        "soft": soft,
        "facts": facts,
        "stats": stats,
    }
    if out_path:
        Path(out_path).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return report
