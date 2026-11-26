"""清洗层：806 条原始记录 → 788 条有效记录，每一处处置都必须留痕。

口径（完整版见仓库根 `数据口径卡.md`，R1–R13）：
- R1 有效记录 = 已评分 + 得分不超过满分 + 同一作答事件只取最大修订版本
- R2 多版本：取最大版本，但全部披露（改分 / 改答案都要记）
- R4 三态单列：待评分、未作答各自单列，禁止代填为 0 分
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

QUESTION_RE = re.compile(r"Q\d{3}")
RUBRIC_SCORE_RE = re.compile(r"(\d+)\s*分")
# 作答记录表里的评分点得分写法：Q015P1=1；Q015P2=1；Q015P3=0
RUBRIC_PAIR_RE = re.compile(r"P\d+\s*[=＝]\s*(\d+)")

# 严重度：error=必须剔除才能算分 / warning=保留但标记 / info=仅留痕
SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"


@dataclass
class CleanResult:
    records_clean: pd.DataFrame
    issues: list[dict] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    multi_version_events: list[dict] = field(default_factory=list)
    cross_node_duplicates: list[dict] = field(default_factory=list)


def parse_question_ids(text: str) -> list[str]:
    return sorted(set(QUESTION_RE.findall(str(text))))


def parse_rubric_sum(text: str) -> int | None:
    """把评分点得分加起来。

    数据里存在两种写法，必须都吃：
    1. 作答记录.评分点得分：``Q015P1=1；Q015P2=1；Q015P3=0``
    2. 题目与材料.评分点：``Q043P2 除以负数时反向 1分``（每行一个评分点）
    """
    if not str(text).strip():
        return None
    pairs = RUBRIC_PAIR_RE.findall(str(text))
    if pairs:
        return sum(int(v) for v in pairs)
    total, found = 0, False
    for line in str(text).splitlines():
        nums = RUBRIC_SCORE_RE.findall(line)
        if nums:
            total += int(nums[-1])
            found = True
    return total if found else None


def _normalize_answer(text: str) -> str:
    return re.sub(r"\s+", "", str(text)).replace("＝", "=")


def _issue(code, severity, count, record_ids, description, handling) -> dict:
    return {
        "issue_code": code,
        "severity": severity,
        "count": int(count),
        "sample_record_ids": "、".join(record_ids[:8]),
        "description": description,
        "handling": handling,
    }


def clean_records(ds) -> CleanResult:
    rec = ds.records.copy()
    raw_count = len(rec)
    mat = ds.materials
    nodes = ds.nodes

    issues: list[dict] = []
    multi_version_events: list[dict] = []

    # 材料 → 主题 / 指标 / 满分（以材料表为真值）
    mat_theme = dict(zip(mat["材料编号"], mat["主题编号"]))
    mat_indicator = dict(zip(mat["材料编号"], mat["指标编号"]))
    mat_full = dict(zip(mat["材料编号"], pd.to_numeric(mat["满分"], errors="coerce")))

    # 节点 → 可用题目集合
    node_available = {
        row["节点编号"]: set(parse_question_ids(row["可用题目编号"]))
        for _, row in nodes.iterrows()
    }
    node_taught = dict(zip(nodes["节点编号"], nodes["已教及测量主题"]))

    # ---------- 检查 1：外键完整性 ----------
    student_ids = set(ds.students["学生编号"])
    bad_student = rec[~rec["学生编号"].isin(student_ids)]
    if len(bad_student):
        issues.append(_issue(
            "orphan_student", SEVERITY_ERROR, len(bad_student),
            bad_student["记录编号"].tolist(), "学生编号不在模拟学生表中", "剔除"))

    bad_material = rec[~rec["材料编号"].isin(set(mat["材料编号"]))]
    if len(bad_material):
        issues.append(_issue(
            "orphan_material", SEVERITY_ERROR, len(bad_material),
            bad_material["记录编号"].tolist(), "材料编号不在题目与材料表中", "剔除"))

    # ---------- 检查 2：多版本（同一作答事件多次提交） ----------
    dup_groups = rec.groupby("作答事件编号", sort=True).size()
    dup_events = dup_groups[dup_groups > 1].index.tolist()

    for event_id in dup_events:
        grp = rec[rec["作答事件编号"] == event_id].sort_values("修订版本")
        versions = grp["修订版本"].astype(int).tolist()
        first, last = grp.iloc[0], grp.iloc[-1]
        score_changed = first["得分"] != last["得分"]
        answer_changed = _normalize_answer(first["学生最终作答"]) != _normalize_answer(
            last["学生最终作答"]
        )
        multi_version_events.append({
            "作答事件编号": event_id,
            "学生编号": last["学生编号"],
            "材料编号": last["材料编号"],
            "修订版本": "/".join(str(v) for v in versions),
            "旧记录编号": first["记录编号"],
            "旧得分": first["得分"],
            "新记录编号": last["记录编号"],
            "新得分": last["得分"],
            "改分": bool(score_changed),
            "改答案": bool(answer_changed),
        })

    after_dedup = len(rec)
    if dup_events:
        rec = (rec.sort_values(["作答事件编号", "修订版本"])
                  .drop_duplicates(subset=["作答事件编号"], keep="last"))
        after_dedup = len(rec)
        changed = sum(1 for e in multi_version_events if e["改分"])
        issues.append(_issue(
            "multi_version", SEVERITY_WARNING, len(dup_events),
            [e["新记录编号"] for e in multi_version_events],
            f"同一作答事件有多个修订版本，其中 {changed} 例得分发生变化",
            "按最大修订版本保留一条，全部版本在 quality_report 中披露"))

    # ---------- 检查 3：主题错标 ----------
    rec["材料主题真值"] = rec["材料编号"].map(mat_theme)
    theme_mismatch = rec[
        rec["材料主题真值"].notna() & (rec["主题编号"] != rec["材料主题真值"])]
    if len(theme_mismatch):
        issues.append(_issue(
            "theme_mismatch", SEVERITY_WARNING, len(theme_mismatch),
            theme_mismatch["记录编号"].tolist(),
            "记录里的主题编号与题目与材料表不一致",
            "以材料表为准，记录保留"))

    # ---------- 检查 4：未教先测 ----------
    not_taught_rows = []
    for _, row in rec.iterrows():
        available = node_available.get(row["节点编号"], set())
        if available and row["材料编号"] not in available:
            not_taught_rows.append(row)
    if not_taught_rows:
        ids = [r["记录编号"] for r in not_taught_rows]
        issues.append(_issue(
            "question_not_in_node", SEVERITY_WARNING, len(ids), ids,
            "该题不在本次测验节点的可用题目清单内（未教先测）",
            "保留记录，但在指标判定中标记 teaching_covered_status=未教"))

    # ---------- 检查 5：评分点合计与得分不一致 ----------
    rubric_bad = []
    for _, row in rec.iterrows():
        if row["评分状态"] != "已评分":
            continue
        total = parse_rubric_sum(row["评分点得分"])
        if total is not None and pd.notna(row["得分"]) and int(row["得分"]) != total:
            rubric_bad.append(row["记录编号"])
    if rubric_bad:
        issues.append(_issue(
            "rubric_sum_mismatch", SEVERITY_WARNING, len(rubric_bad), rubric_bad,
            "各评分点得分之和与记录总分不一致",
            "以记录总分为准，异常留痕"))

    # ---------- 检查 6：满分但答案与参考答案不同 ----------
    answer_mismatch = []
    ref = dict(zip(mat["材料编号"], mat["参考答案"]))
    for _, row in rec.iterrows():
        if row["评分状态"] != "已评分":
            continue
        if pd.isna(row["满分"]) or pd.isna(row["得分"]):
            continue
        if int(row["得分"]) != int(row["满分"]):
            continue
        expected = ref.get(row["材料编号"], "")
        if expected and _normalize_answer(row["学生最终作答"]) != _normalize_answer(expected):
            answer_mismatch.append(row["记录编号"])
    if answer_mismatch:
        issues.append(_issue(
            "answer_text_differs", SEVERITY_INFO, len(answer_mismatch), answer_mismatch,
            "满分记录的作答文本与参考答案写法不同（如 x=9 与 9）",
            "不得按文本比对判分，一律采用记录总分"))

    # ---------- 检查 7：得分超过满分 ----------
    over = rec[(rec["得分"].notna()) & (rec["满分"].notna()) & (rec["得分"] > rec["满分"])]
    if len(over):
        issues.append(_issue(
            "score_over_full", SEVERITY_ERROR, len(over),
            over["记录编号"].tolist(),
            "得分大于满分，数据错误",
            "剔除，不进入任何统计"))

    # ---------- 检查 8/9：待评分、未作答（三态单列） ----------
    pending = rec[rec["评分状态"] == "待评分"]
    blank = rec[rec["评分状态"] == "未作答"]
    if len(pending):
        issues.append(_issue(
            "pending_score", SEVERITY_ERROR, len(pending), pending["记录编号"].tolist(),
            "有作答内容但尚未评分", "不计入统计，也不按 0 分处理"))
    if len(blank):
        issues.append(_issue(
            "blank_attempt", SEVERITY_ERROR, len(blank), blank["记录编号"].tolist(),
            "学生未作答（答案与得分皆空）", "不计入统计，也不按 0 分处理"))

    # ---------- 执行剔除 ----------
    rec = rec[rec["评分状态"] == "已评分"]
    rec = rec[~(rec["得分"] > rec["满分"])]
    rec = rec[rec["得分"].notna() & rec["满分"].notna()]
    rec = rec[rec["学生编号"].isin(student_ids)]
    rec = rec[rec["材料编号"].isin(set(mat["材料编号"]))]
    records_clean = rec.copy()

    # ---------- 检查 10：跨节点重复作答（同一学生同一题做了两次） ----------
    cross = (records_clean.groupby(["学生编号", "材料编号"], sort=True).size()
             .reset_index(name="次数"))
    cross = cross[cross["次数"] > 1]
    cross_node_duplicates = cross.to_dict("records")
    if len(cross):
        issues.append(_issue(
            "cross_node_duplicate", SEVERITY_INFO, len(cross), [],
            f"同一学生同一题目在多个测验节点作答（共 {len(cross)} 对，涉及 "
            f"{cross['学生编号'].nunique()} 人）",
            "计入证据时按不同题目去重，同题只算 1 条"))

    # ---------- 落上派生列 ----------
    records_clean["指标编号"] = records_clean["材料编号"].map(mat_indicator)
    records_clean["主题编号"] = records_clean["材料主题真值"].fillna(records_clean["主题编号"])
    records_clean["是否本节点可考"] = [
        row["材料编号"] in node_available.get(row["节点编号"], set())
        for _, row in records_clean.iterrows()
    ]

    stats = {
        "raw_records": raw_count,
        "after_dedup_events": after_dedup,
        "clean_records": len(records_clean),
        "students": int(records_clean["学生编号"].nunique()),
        "students_total": len(ds.students),
        "earned_score": int(records_clean["得分"].sum()),
        "full_score": int(records_clean["满分"].sum()),
        "correct_rate": round(float(records_clean["得分"].sum() / records_clean["满分"].sum()), 4),
    }

    issues_sorted = sorted(issues, key=lambda x: (x["severity"] != "error", x["issue_code"]))
    return CleanResult(
        records_clean=records_clean.sort_values("记录编号").reset_index(drop=True),
        issues=issues_sorted,
        stats=stats,
        multi_version_events=multi_version_events,
        cross_node_duplicates=cross_node_duplicates,
    )
