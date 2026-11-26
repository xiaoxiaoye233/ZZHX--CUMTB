"""事实层：把 788 条有效记录算成 40 张学生事实 + 2 张班级事实。

铁律（完整版见仓库根 `数据口径卡.md`，R1–R13）：
- R1 只用已评分且不超过满分的记录
- R2 多版本已由 clean.py 处理（取最大修订版本）
- R3 不做"掌握度"合成：做对率与覆盖率分开报
- R5 指标级阈值 = min(3, 该指标题库题数)
- R6 证据独立性：同一道题在多个节点各做一次，只算 1 条证据
- R10 阈值与分母都按"这个学生实际能考到的题数"封顶；教学状态按指标级判定

结论档位只表达"证据够不够"，不表达"学得好不好"：
    证据充足 = 证据量达到阈值；证据偏少 = 有证据但不足；证据不足 = 没有可用证据
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

from contracts import (
    ClassFacts,
    ClassIndicatorOverview,
    ClassThemeOverview,
    ExamNodeIndicatorRecord,
    IndicatorLevel,
    StudentFacts,
    ThemeLevel,
)

THEME_ORDER = ["T01", "T02", "T03"]
QUESTION_TYPES = ("填空", "选择", "解答")

# 证据强度分档：有效题目数
STRENGTH_SUFFICIENT = 15   # >=15 充足
STRENGTH_LOW = 8           # 8-14 偏少；<8 不足
STRENGTH_RANK = {"不足": 0, "偏少": 1, "充足": 2}

THEME_THRESHOLD = 3        # 主题级达到"证据充足"所需的不同题目数

# 三档的名字说的是"证据够不够"，不是"学得好不好"——叫"确定"会被读成掌握程度。
LEVEL_SUFFICIENT = "证据充足"
LEVEL_PARTIAL = "证据偏少"
LEVEL_SCANT = "证据不足"

QUESTION_RE = re.compile(r"^Q\d{3}$")
INDICATOR_ORDER = [f"{t}I{i}" for t in THEME_ORDER for i in (1, 2, 3)]

# ---- 教学进度：指标级（口径卡 R10）----
# 来源是 测验节点.csv 的「说明」列原文，不是「已教及测量主题」列 —— 那一列只到主题级。
# N01 说明：「模拟上学期期末：T01 及 T02 中的一元一次方程；方程组和不等式尚未教学。」
#   已教：T01 三项、T02I1（一元一次方程）
#   部分教到：T02I3（只涉及一元一次方程的列式，还没到方程组）
#   未教：T02I2（消元法解二元一次方程组）、T03 三项（不等式）
# N02 说明：「模拟下学期期末：复习T01，新增T02方程组及T03不等式。」→ 九项全部教到
NODE_INDICATOR_TEACHING_STATUS: dict[str, dict[str, str]] = {
    "N01": {
        "T01I1": "已教",
        "T01I2": "已教",
        "T01I3": "已教",
        "T02I1": "已教",
        "T02I2": "未教",
        "T02I3": "部分教到",
        "T03I1": "未教",
        "T03I2": "未教",
        "T03I3": "未教",
    },
}
# 手写表只覆盖确实读过说明的场次（N01）。表里没写的场次按题目推断：
#   这场出过这个指标的题 → 已教（有题就是教到了，能做证据）
#   一道都没出           → 未提供（说不清，既不声称未教、也不声称已教）
UNKNOWN_TEACHING = "未提供"
TEACHING_RANK = {UNKNOWN_TEACHING: -1, "未教": 0, "部分教到": 1, "已教": 2}
# 下结论的绝对下限：1 道题太容易蒙对，任何情况下都不允许"做对 1 道就算确定"
CONCLUSIONS_FLOOR = 2


@dataclass
class Catalogs:
    theme_names: dict[str, str]
    theme_goal: dict[str, str]
    indicator_names: dict[str, str]
    indicator_theme: dict[str, str]
    indicator_question_count: dict[str, int]
    indicator_threshold: dict[str, int]
    question_theme: dict[str, str]
    question_indicator: dict[str, str]
    question_full: dict[str, int]
    node_available: dict[str, set]
    node_taught: dict[str, set]
    node_date: dict[str, str]


def _split_themes(text: str) -> set[str]:
    return {t for t in THEME_ORDER if t in str(text)}


def build_catalogs(ds) -> Catalogs:
    cur = ds.curriculum
    theme_names = dict(zip(cur["主题编号"], cur["主题"]))
    theme_goal = dict(zip(cur["主题编号"], cur["主题目标"]))
    indicator_names = dict(zip(cur["指标编号"], cur["观察指标"]))
    indicator_theme = dict(zip(cur["指标编号"], cur["主题编号"]))

    mat = ds.materials
    questions = mat[mat["材料编号"].str.match(QUESTION_RE)].copy()
    questions["满分"] = pd.to_numeric(questions["满分"], errors="coerce").fillna(0).astype(int)
    question_theme = dict(zip(questions["材料编号"], questions["主题编号"]))
    question_indicator = dict(zip(questions["材料编号"], questions["指标编号"]))
    question_full = dict(zip(questions["材料编号"], questions["满分"]))

    counts = questions.groupby("指标编号").size().to_dict()
    indicator_question_count = {ind: int(counts.get(ind, 0)) for ind in indicator_names}
    indicator_threshold = {ind: min(3, n) for ind, n in indicator_question_count.items()}

    node_available = {
        row["节点编号"]: set(re.findall(r"Q\d{3}", row["可用题目编号"]))
        for _, row in ds.nodes.iterrows()
    }
    node_taught = {
        row["节点编号"]: _split_themes(row["已教及测量主题"])
        for _, row in ds.nodes.iterrows()
    }
    node_date = {
        row["节点编号"]: str(row["模拟测验日期"])
        for _, row in ds.nodes.iterrows()
    }

    return Catalogs(
        theme_names=theme_names,
        theme_goal=theme_goal,
        indicator_names=indicator_names,
        indicator_theme=indicator_theme,
        indicator_question_count=indicator_question_count,
        indicator_threshold=indicator_threshold,
        question_theme=question_theme,
        question_indicator=question_indicator,
        question_full=question_full,
        node_available=node_available,
        node_taught=node_taught,
        node_date=node_date,
    )


def dedupe_cross_node(records: pd.DataFrame) -> pd.DataFrame:
    """同一学生同一题目在多个节点作答 → 只保留较晚节点的那一条（R6）。

    "较晚"按节点号里的数字比，不能按字符串比：字符串会把 N10 排到 N2 前面。
    """
    ordered = records.copy()
    ordered["_节点序"] = ordered["节点编号"].map(
        lambda n: int(re.sub(r"\D", "", str(n)) or 0))
    ordered = ordered.sort_values(["_节点序", "记录编号"])
    kept = ordered.drop_duplicates(subset=["学生编号", "材料编号"], keep="last")
    return kept.drop(columns=["_节点序"])


def _strength(distinct_count: int) -> str:
    if distinct_count >= STRENGTH_SUFFICIENT:
        return "充足"
    if distinct_count >= STRENGTH_LOW:
        return "偏少"
    return "不足"


def _rate(earned: int, full: int) -> float | None:
    return round(earned / full, 4) if full else None


def _node_indicator_question_count(cats: Catalogs, node: str, ind: str) -> int:
    """这一场里，落在这个指标上的题有几道（用来在没手写记录时推断教到没有）。"""
    available = cats.node_available.get(node, set())
    return sum(1 for q in available if cats.question_indicator.get(q) == ind)


def _node_teaching_status(cats: Catalogs, node: str, ind: str) -> str:
    """某一场考试里，这个指标教到没有（口径卡 R10）。

    手写的 NODE_INDICATOR_TEACHING_STATUS 优先（它读的是节点说明原文）；
    表里没写这场，就按这场有没有出这个指标的题推断，推不出来记「未提供」。
    """
    explicit = NODE_INDICATOR_TEACHING_STATUS.get(node, {}).get(ind)
    if explicit:
        return explicit
    if _node_indicator_question_count(cats, node, ind) > 0:
        return "已教"
    return UNKNOWN_TEACHING


def _indicator_teaching_status(cats: Catalogs, node_ids: list[str], ind: str) -> str:
    """该生参加过的考试里，这个指标最好被教到什么程度。"""
    best = UNKNOWN_TEACHING
    for node in node_ids:
        status = _node_teaching_status(cats, node, ind)
        if TEACHING_RANK[status] > TEACHING_RANK[best]:
            best = status
    return best


def _exam_node_records(
    cats: Catalogs, ind: str, node_ids: list[str], r_all: pd.DataFrame,
    raw_student: pd.DataFrame | None = None,
) -> list[ExamNodeIndicatorRecord]:
    """这个指标在每一场考试里的表现，包括"没参加这场"的行。结论不从这里取。

    raw_student 是这位学生的**原始**记录（含待评分、未作答）。r_all 只含有效记录，
    所以"有效记录为空"不等于"他没做"——必须回原始记录里看有没有交过卷子。
    """
    all_nodes = sorted(cats.node_date)
    attempted_by_node = {
        n: set(r_all.loc[r_all["节点编号"] == n, "材料编号"]) for n in all_nodes
    }
    raw_by_node: dict[str, pd.DataFrame | None] = (
        {n: raw_student[raw_student["节点编号"] == n] for n in all_nodes}
        if raw_student is not None
        else {n: None for n in all_nodes}
    )
    rows: list[ExamNodeIndicatorRecord] = []
    for node in all_nodes:
        in_node_scope = {
            q for q in cats.node_available.get(node, set())
            if cats.question_indicator.get(q) == ind
        }
        participated = node in node_ids
        sub = r_all[(r_all["节点编号"] == node) & (r_all["指标编号"] == ind)]
        distinct = sorted(set(sub["材料编号"]))
        # 原始记录里属于本指标、但没进有效记录的那些（待评分 / 未作答）
        raw_node = raw_by_node.get(node)
        pending_qids: list[str] = []
        blank_qids: list[str] = []
        if raw_node is not None and len(raw_node):
            pending_qids = sorted({
                q for q, st in zip(raw_node["材料编号"], raw_node["评分状态"])
                if cats.question_indicator.get(q) == ind and st == "待评分"
            })
            blank_qids = sorted({
                q for q, st in zip(raw_node["材料编号"], raw_node["评分状态"])
                if cats.question_indicator.get(q) == ind and st == "未作答"
            })
        others: set = set()
        for o in all_nodes:
            if o != node:
                others |= attempted_by_node[o]
        repeated = sorted(q for q in distinct if q in others)
        earned = int(sub["得分"].sum()) if len(sub) else 0
        full = int(sub["满分"].sum()) if len(sub) else 0
        teaching = _node_teaching_status(cats, node, ind)

        if not participated:
            note = "没参加这场考试"
        elif not in_node_scope:
            note = f"参加了这场，但卷子没出这个指标的题（当时教学状态：{teaching}）"
        elif distinct:
            note = (f"这场出了 {len(in_node_scope)} 道，他做了 {len(distinct)} 道，"
                    f"得 {earned}/{full} 分")
            if pending_qids:
                note += f"；另有 {len(pending_qids)} 道已经作答、但老师还没判分"
        elif pending_qids:
            # 关键修正：交了卷子但没有分数，不能说"一道都没做"
            note = (f"这场出了 {len(in_node_scope)} 道，他做了 {len(pending_qids)} 道"
                    f"（{'、'.join(pending_qids)}），老师还没判分")
        elif blank_qids:
            note = (f"这场出了 {len(in_node_scope)} 道，他交了 {len(blank_qids)} 道空答案"
                    f"（{'、'.join(blank_qids)}，未作答），不能算作答错")
        else:
            note = f"这场出了 {len(in_node_scope)} 道，他一道都没做"
        rows.append(ExamNodeIndicatorRecord(
            node_identifier=node,
            node_date_text=cats.node_date.get(node, ""),
            student_participated_flag=participated,
            questions_available_in_node=len(in_node_scope),
            distinct_attempted_count=len(distinct),
            attempt_event_count=len(sub),
            earned_score_total=earned,
            attempted_full_score=full,
            correct_score_rate=_rate(earned, full),
            teaching_status_in_node=teaching,
            repeated_question_identifiers=repeated,
            plain_language_note_text=note,
        ))
    return rows


def build_student_facts(ds, clean_result, cats: Catalogs) -> list[StudentFacts]:
    rec = clean_result.records_clean.copy()
    dedup = dedupe_cross_node(rec)

    # 待评分记录的 (学生, 指标)，用于"为什么没证据"的理由码
    raw = ds.records
    pending = raw[raw["评分状态"] == "待评分"]
    pending_indicator_pairs = {
        (r["学生编号"], cats.question_indicator.get(r["材料编号"]))
        for _, r in pending.iterrows()
    }

    students = ds.students
    facts: list[StudentFacts] = []

    for _, srow in students.sort_values("学生编号").iterrows():
        sid = srow["学生编号"]
        r_all = rec[rec["学生编号"] == sid]
        r = dedup[dedup["学生编号"] == sid]

        node_ids = sorted(r_all["节点编号"].unique())
        available: set[str] = set()
        for n in node_ids:
            available |= cats.node_available.get(n, set())
        attempted = set(r["材料编号"])

        earned = int(r_all["得分"].sum())
        full = int(r_all["满分"].sum())
        distinct_count = len(attempted)

        # 主题级
        themes: list[ThemeLevel] = []
        for t in THEME_ORDER:
            qids = [q for q in attempted if cats.question_theme.get(q) == t]
            sub = r_all[r_all["主题编号"] == t]
            te, tf = int(sub["得分"].sum()), int(sub["满分"].sum())
            n = len(qids)
            level = (
                LEVEL_SUFFICIENT if n >= THEME_THRESHOLD
                else (LEVEL_PARTIAL if n >= 1 else LEVEL_SCANT)
            )
            themes.append(ThemeLevel(
                theme_identifier=t,
                theme_display_name=cats.theme_names.get(t, t),
                distinct_attempted_question_count=n,
                earned_score_total=te,
                attempted_full_score_total=tf,
                theme_correct_score_rate=_rate(te, tf),
                conclusion_level=level,
                evidence_threshold=THEME_THRESHOLD,
            ))

        # 指标级
        indicators: list[IndicatorLevel] = []
        for ind in cats.indicator_names:
            qids = sorted(q for q in attempted if cats.question_indicator.get(q) == ind)
            n = len(qids)
            # 他实际能考到的该指标题数（参加过的所有考试的并集，去重）
            available_ind = sum(
                1 for q in available if cats.question_indicator.get(q) == ind)
            # R10：门槛按"能考的题数"封顶，但下结论至少 2 道（1 道太容易蒙对）。
            # 可考题数为 0 时门槛保持题库上限，只作展示（这一格本来就到不了"证据充足"）。
            if available_ind == 0:
                threshold = cats.indicator_threshold[ind]
            else:
                threshold = max(
                    CONCLUSIONS_FLOOR,
                    min(cats.indicator_threshold[ind], available_ind),
                )
            rate_sub = r_all[r_all["指标编号"] == ind]
            ie, ifull = int(rate_sub["得分"].sum()), int(rate_sub["满分"].sum())
            evidence_sub = r[r["指标编号"] == ind]  # R6：同一道题只算一条证据

            taught = _indicator_teaching_status(cats, node_ids, ind)

            reason = None
            if available_ind == 0:
                # 他能参加的所有考试里都没出过这个指标的题
                level = LEVEL_SCANT
                if (sid, ind) in pending_indicator_pairs:
                    reason = "pending_score"
                elif taught == "未教":
                    reason = "not_taught"
                else:
                    reason = "not_in_scope"
            elif n >= threshold:
                level = LEVEL_SUFFICIENT
            elif n >= 1:
                level = LEVEL_PARTIAL
                reason = "evidence_short"
            else:
                level = LEVEL_SCANT
                if (sid, ind) in pending_indicator_pairs:
                    reason = "pending_score"
                elif taught == "未教":
                    reason = "not_taught"
                else:
                    reason = "no_attempt"

            indicators.append(IndicatorLevel(
                indicator_identifier=ind,
                indicator_description_text=cats.indicator_names[ind],
                total_question_count_for_indicator=cats.indicator_question_count[ind],
                available_question_count=available_ind,
                evidence_threshold_for_conclusion=threshold,
                distinct_attempted_count=n,
                counted_evidence_record_count=len(evidence_sub),
                earned_score_total=ie,
                attempted_full_score=ifull,
                indicator_correct_score_rate=_rate(ie, ifull),
                conclusion_level=level,
                insufficiency_reason_code=reason,
                teaching_covered_status=taught,
                supporting_record_identifiers=sorted(evidence_sub["记录编号"].tolist()),
                exam_node_record_list=_exam_node_records(
                    cats, ind, node_ids, r_all,
                    raw[raw["学生编号"] == sid]),
            ))

        flags: list[str] = []
        if len(r_all) > len(r):
            flags.append("cross_node_dup")
        if "是否本节点可考" in r_all.columns:
            if (r_all["是否本节点可考"].astype(str).str.lower() == "false").any():
                flags.append("administered_before_teaching")

        facts.append(StudentFacts(
            student_identifier=sid,
            class_identifier=srow["模拟班级编号"],
            grade_level=int(srow["年级"]),
            valid_record_count=int(len(r_all)),
            distinct_attempted_question_count=distinct_count,
            available_question_count=len(available),
            attempted_question_coverage_ratio=round(
                distinct_count / len(available), 4) if available else 0.0,
            coverage_plain_language_text=(
                f"{len(available)} 道可考题里做过 {distinct_count} 道" if available else "无可用题目"),
            correct_score_rate=_rate(earned, full) or 0.0,
            earned_score_total=earned,
            attempted_full_score_total=full,
            evidence_strength_level=_strength(distinct_count),
            theme_level_summary_list=themes,
            indicator_level_detail_list=indicators,
            data_quality_flags=sorted(flags),
            attended_node_identifiers=node_ids,
            available_question_identifiers=sorted(available),
        ))

    return facts


def build_class_facts(ds, clean_result, cats: Catalogs, facts: list[StudentFacts]) -> list[ClassFacts]:
    rec = clean_result.records_clean.copy()
    dedup = dedupe_cross_node(rec)
    students = ds.students.sort_values("学生编号")

    out: list[ClassFacts] = []
    for cls in sorted(students["模拟班级编号"].unique()):
        sids = students.loc[students["模拟班级编号"] == cls, "学生编号"].tolist()
        class_facts = [f for f in facts if f.class_identifier == cls]
        class_rec = dedup[dedup["学生编号"].isin(sids)]
        class_rec_all = rec[rec["学生编号"].isin(sids)]

        dist = {LEVEL_SUFFICIENT: 0, LEVEL_PARTIAL: 0, LEVEL_SCANT: 0}
        for f in class_facts:
            for ind in f.indicator_level_detail_list:
                dist[ind.conclusion_level] += 1

        ind_overview: list[ClassIndicatorOverview] = []
        for ind in cats.indicator_names:
            d = t = u = 0
            for f in class_facts:
                for x in f.indicator_level_detail_list:
                    if x.indicator_identifier == ind:
                        if x.conclusion_level == LEVEL_SUFFICIENT:
                            d += 1
                        elif x.conclusion_level == LEVEL_PARTIAL:
                            t += 1
                        else:
                            u += 1
            sub = class_rec[class_rec["指标编号"] == ind]
            rate_sub = class_rec_all[class_rec_all["指标编号"] == ind]
            ind_overview.append(ClassIndicatorOverview(
                indicator_identifier=ind,
                indicator_description_text=cats.indicator_names[ind],
                student_count_determined=d,
                student_count_tendency=t,
                student_count_unobserved=u,
                class_distinct_attempted_count=int(sub["材料编号"].nunique()),
                class_correct_score_rate=_rate(int(rate_sub["得分"].sum()),
                                               int(rate_sub["满分"].sum())) or 0.0,
            ))

        theme_overview: list[ClassThemeOverview] = []
        for t in THEME_ORDER:
            sub = class_rec[class_rec["主题编号"] == t]
            rate_sub = class_rec_all[class_rec_all["主题编号"] == t]
            theme_overview.append(ClassThemeOverview(
                theme_identifier=t,
                theme_display_name=cats.theme_names.get(t, t),
                student_count_with_evidence=int(
                    sub.groupby("学生编号")["材料编号"].nunique().shape[0]),
                class_correct_score_rate=_rate(int(rate_sub["得分"].sum()),
                                               int(rate_sub["满分"].sum())) or 0.0,
            ))

        priority = sorted(
            class_facts,
            key=lambda f: (STRENGTH_RANK[f.evidence_strength_level], f.correct_score_rate,
                           f.student_identifier),
        )

        out.append(ClassFacts(
            class_identifier=cls,
            student_count=len(sids),
            valid_record_count=int(len(class_rec_all)),
            class_correct_score_rate=_rate(int(class_rec_all["得分"].sum()),
                                          int(class_rec_all["满分"].sum())) or 0.0,
            conclusion_level_distribution=dist,
            indicator_level_overview_list=ind_overview,
            theme_level_overview_list=theme_overview,
            priority_attention_student_list=[f.student_identifier for f in priority],
        ))

    return out

