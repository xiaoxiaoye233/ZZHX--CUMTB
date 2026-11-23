"""工具层（T 层）：给 LLM 和后端调用的 6 个只读函数。

三条设计约束，改代码前先读：

1. **入口只吃 id，不吃整张表**。模型不许传 DataFrame、不许传筛选条件表达式，
   只能传 `student_id` / `class_id` / `indicator_id` 这类受控枚举。
2. **返回结构化事实对象，不返回句子**。措辞是 LLM 的活，事实是代码的活。
   这里返回的每个对象都带着 `记录编号`，能在 `dataset/01_按学生/` 里查到那一条。
3. **只读、无状态、可重放**。不写盘、不取当前时间、不用随机数，
   同样参数调用一百次结果完全一致。

六个函数：

| 函数 | 回答什么问题 | 典型调用 |
|---|---|---|
| `load_facts` | 把全部数据装配成内存里的只读仓库 | 服务启动时调一次 |
| `get_student` | 这个学生现在什么情况（全部事实） | "看看 D03" |
| `get_group` | 这个班整体什么情况、谁该先看 | "二班怎么样" |
| `get_evidence` | 这个学生这个指标的每一条作答证据 | "凭什么说 D03 不等式没掌握" |
| `get_candidates` | 这个指标还有哪些题可以做（排除已做过的） | "他还能练什么" |
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from clean import CleanResult, clean_records
from contracts import (
    CandidateMaterial,
    CandidateToolResult,
    ClassFacts,
    ClassIndicatorDetailResult,
    ClassIndicatorOverview,
    ClassIndicatorStudentRow,
    ClassThemeOverview,
    EvidenceItem,
    EvidenceToolResult,
    GroupToolResult,
    StudentFacts,
    StudentToolResult,
    ToolDescriptor,
    ToolMeta,
)
from content_map import PREREQUISITE_EDGES
from facts import (
    LEVEL_PARTIAL,
    LEVEL_SCANT,
    LEVEL_SUFFICIENT,
    STRENGTH_RANK,
    THEME_ORDER,
    Catalogs,
    build_catalogs,
    build_class_facts,
    build_student_facts,
    dedupe_cross_node,
)
from grading import flag_grading, grading_caveat_for
from io_layer import Dataset, load_datasets

QUESTION_RE = re.compile(r"^Q\d{3}$")

DATA_SOURCE_FILES = [
    "赛题数据/赛题资料包/4_赛题数据/模拟学情数据/作答记录.csv",
    "赛题数据/赛题资料包/4_赛题数据/模拟学情数据/题目与材料.csv",
    "赛题数据/赛题资料包/4_赛题数据/模拟学情数据/模拟学生.csv",
    "赛题数据/赛题资料包/4_赛题数据/模拟学情数据/测验节点.csv",
    "赛题数据/赛题资料包/4_赛题数据/模拟学情数据/课程要求.csv",
]


@dataclass
class FactStore:
    """只读事实仓库。装配一次，之后所有工具调用都从这里取。"""

    data_dir: Path
    datasets: Dataset
    clean: CleanResult
    catalogs: Catalogs
    grading_flags: pd.DataFrame
    student_facts: dict[str, StudentFacts]
    class_facts: dict[str, ClassFacts]
    records_by_student: dict[str, pd.DataFrame]
    node_availability_by_student: dict[str, set[str]]
    question_rows: dict[str, dict]
    total_question_count: int
    _class_facts_overall: ClassFacts | None = field(default=None, repr=False)


def _meta(tool_name: str, arguments: str, count: int, note: str) -> ToolMeta:
    return ToolMeta(
        tool_name=tool_name,
        argument_summary_text=arguments,
        result_count=count,
        data_source_file_list=DATA_SOURCE_FILES,
        computation_note_text=note,
    )


def load_facts(data_dir: str | Path) -> FactStore:
    """装配事实仓库。纯内存计算，不读 `outputs/` 里的旧 JSON，避免用到过期数字。"""
    data_dir = Path(data_dir)
    ds = load_datasets(data_dir)
    clean = clean_records(ds)
    cats = build_catalogs(ds)
    facts = build_student_facts(ds, clean, cats)
    class_facts = build_class_facts(ds, clean, cats, facts)
    flags = flag_grading(ds, clean)

    rec = clean.records_clean
    records_by_student = {sid: g for sid, g in rec.groupby("学生编号")}

    # 能考到哪些题由 facts 算一次、存在学生事实里；这里只读，避免两处算法各自漂移
    node_avail: dict[str, set[str]] = {
        f.student_identifier: set(f.available_question_identifiers) for f in facts
    }

    q = ds.materials
    q_rows = {
        str(r["材料编号"]): dict(r)
        for _, r in q[q["材料编号"].astype(str).str.match(QUESTION_RE)].iterrows()
    }

    return FactStore(
        data_dir=data_dir,
        datasets=ds,
        clean=clean,
        catalogs=cats,
        grading_flags=flags,
        student_facts={f.student_identifier: f for f in facts},
        class_facts={c.class_identifier: c for c in class_facts},
        records_by_student=records_by_student,
        node_availability_by_student=node_avail,
        question_rows=q_rows,
        total_question_count=len(q_rows),
    )


def _flag_map(store: FactStore) -> dict[str, str]:
    return {str(r["记录编号"]): str(r["判分可靠性"]) for _, r in store.grading_flags.iterrows()}


def pending_question_identifiers(raw_records: pd.DataFrame, student_identifier: str) -> set[str]:
    """这个学生「已经交了、但老师还没判分」的题目编号集合（口径 R12）。

    这些题不能再当成"还能练"推荐出去——他已经做过一遍，只是没有分数。
    """
    if raw_records is None or len(raw_records) == 0:
        return set()
    sub = raw_records[
        (raw_records["学生编号"].astype(str) == str(student_identifier))
        & (raw_records["评分状态"].astype(str) == "待评分")
    ]
    return set(sub["材料编号"].astype(str))


# ---------- 工具 1：get_student ----------

def get_student(
    store: FactStore,
    student_id: str,
    theme_id: str | None = None,
    indicator_id: str | None = None,
) -> StudentToolResult:
    """查一个学生的学情事实（指标、主题、每场考试、记录编号）。

    按问题筛在**参数层**：老师问"他方程怎么样"，传 `theme_id="T02"` 就只回主题与三行指标，
    不必把 12 行都吐出来给模型（吐得多，模型越容易挑错行）。
    不传参数 = 全部，行为与以前一致。

    注意：`valid_record_count`、`correct_score_rate` 这些合计字段仍是**该学生整体**的数，
    不是筛出来的那几行的合计；筛出来的每一行自己带 `correct_score_rate`。

    措辞不在这儿——这里只回事实对象，怎么说由调用方决定。
    """
    sid = student_id.strip().upper()
    if sid not in store.student_facts:
        raise KeyError(f"没有这个学生：{student_id}（可用范围 D01–D40）")

    facts = store.student_facts[sid]
    theme = (theme_id or "").strip().upper() or None
    ind = (indicator_id or "").strip().upper() or None
    if theme is not None and theme not in THEME_ORDER:
        raise KeyError(f"没有这个主题：{theme_id}（可用范围 T01 / T02 / T03）")
    if ind is not None:
        if ind not in store.catalogs.indicator_names:
            raise KeyError(f"没有这个指标：{indicator_id}（可用范围 T01I1–T03I3）")
        theme = ind[:3]                      # 指定指标时，主题由指标推出来，避免两个参数打架

    filters = []
    if theme:
        filters.append(f"theme_id={theme}")
    if ind:
        filters.append(f"indicator_id={ind}")

    if filters:
        facts = facts.model_copy(
            update={
                "theme_level_summary_list": (
                    [t for t in facts.theme_level_summary_list if t.theme_identifier == theme]
                    if theme
                    else facts.theme_level_summary_list
                ),
                "indicator_level_detail_list": [i for i in facts.indicator_level_detail_list if (not ind or i.indicator_identifier == ind) and (not theme or i.indicator_identifier.startswith(theme))],
            }
        )

    scope = f"（只给 {theme}）" if theme and not ind else (f"（只给 {ind}）" if ind else "")
    return StudentToolResult(
        tool_meta=_meta(
            "get_student",
            f"student_id={sid}" + (f", {', '.join(filters)}" if filters else ""),
            1,
            "事实由 src/lib/facts.py 现场计算；本函数不含任何措辞或建议，也不涉及 LLM"
            + (f"；本次按 {', '.join(filters)} 筛过，只回这一块{scope}" if filters else ""),
        ),
        student_facts=facts,
        evidence_sheet_identifier=f"ES-{sid}",
        filtered_by_text=", ".join(filters),
    )


# ---------- 工具 2：get_group ----------

def _overall_class_facts(store: FactStore) -> ClassFacts:
    if store._class_facts_overall is not None:
        return store._class_facts_overall

    facts = list(store.student_facts.values())
    earned = sum(f.earned_score_total for f in facts)
    full = sum(f.attempted_full_score_total for f in facts)
    dist: dict[str, int] = {LEVEL_SUFFICIENT: 0, LEVEL_PARTIAL: 0, LEVEL_SCANT: 0}
    for f in facts:
        for ind in f.indicator_level_detail_list:
            dist[ind.conclusion_level] = dist.get(ind.conclusion_level, 0) + 1

    theme_rows: list[ClassThemeOverview] = []
    for theme in THEME_ORDER:
        with_ev = sum(1 for f in facts if (t := next((x for x in f.theme_level_summary_list if x.theme_identifier == theme), None)) and t.theme_correct_score_rate is not None)
        te = sum(t.earned_score_total for f in facts for t in f.theme_level_summary_list if t.theme_identifier == theme)
        tf = sum(t.attempted_full_score_total for f in facts for t in f.theme_level_summary_list if t.theme_identifier == theme)
        name = store.catalogs.theme_names.get(theme, theme)
        theme_rows.append(
            ClassThemeOverview(
                theme_identifier=theme,
                theme_display_name=name,
                student_count_with_evidence=with_ev,
                class_correct_score_rate=round(te / tf, 4) if tf else 0.0,
            )
        )

    ind_rows: list[ClassIndicatorOverview] = []
    for ind_id in store.catalogs.indicator_names:
        levels = [i for f in facts for i in f.indicator_level_detail_list if i.indicator_identifier == ind_id]
        ie = sum(i.earned_score_total for i in levels)
        ifu = sum(i.attempted_full_score for i in levels)
        ind_rows.append(
            ClassIndicatorOverview(
                indicator_identifier=ind_id,
                indicator_description_text=store.catalogs.indicator_names[ind_id],
                student_count_determined=sum(1 for i in levels if i.conclusion_level == LEVEL_SUFFICIENT),
                student_count_tendency=sum(1 for i in levels if i.conclusion_level == LEVEL_PARTIAL),
                student_count_unobserved=sum(1 for i in levels if i.conclusion_level == LEVEL_SCANT),
                class_distinct_attempted_count=sum(i.distinct_attempted_count for i in levels),
                class_correct_score_rate=round(ie / ifu, 4) if ifu else 0.0,
            )
        )

    ordered = sorted(
        facts,
        key=lambda f: (
            STRENGTH_RANK.get(f.evidence_strength_level, 3),
            f.correct_score_rate,
            f.student_identifier,
        ),
    )
    overall = ClassFacts(
        class_identifier="ALL",
        student_count=len(facts),
        valid_record_count=sum(f.valid_record_count for f in facts),
        class_correct_score_rate=round(earned / full, 4) if full else 0.0,
        conclusion_level_distribution=dist,
        indicator_level_overview_list=ind_rows,
        theme_level_overview_list=theme_rows,
        priority_attention_student_list=[f.student_identifier for f in ordered],
    )
    store._class_facts_overall = overall
    return overall


def get_group(store: FactStore, class_identifier: str | None = None) -> GroupToolResult:
    """查一个班（DC01 / DC02）或全年级（class_identifier=None）的群体事实。"""
    if class_identifier is None or class_identifier.strip().upper() in {"ALL", "全体", "全年级"}:
        cid = "ALL"
        cf = _overall_class_facts(store)
    else:
        cid = class_identifier.strip().upper()
        if cid not in store.class_facts:
            raise KeyError(f"没有这个班：{class_identifier}（可用 DC01、DC02，或留空看全年级）")
        cf = store.class_facts[cid]

    themes = sorted(
        [t for t in cf.theme_level_overview_list if t.class_correct_score_rate is not None],
        key=lambda t: (t.class_correct_score_rate, t.theme_identifier),
    )
    inds = sorted(
        [i for i in cf.indicator_level_overview_list if i.class_distinct_attempted_count > 0],
        key=lambda i: (i.class_correct_score_rate, i.indicator_identifier),
    )
    return GroupToolResult(
        tool_meta=_meta(
            "get_group",
            f"class_id={cid}",
            1,
            "群体事实由 src/lib/facts.py 现场聚合；排序均为得分率升序，最前面的最薄弱",
        ),
        group_facts=cf,
        weakest_theme_identifiers=[t.theme_identifier for t in themes[:2]],
        weakest_indicator_identifiers=[i.indicator_identifier for i in inds[:3]],
    )


# ---------- 工具 3：get_evidence ----------

def get_evidence(store: FactStore, student_id: str, indicator_identifier: str) -> EvidenceToolResult:
    """查某学生某指标的逐条作答证据，并标明哪些计入判定（R6 去重后）。"""
    sid = student_id.strip().upper()
    ind_id = indicator_identifier.strip().upper()
    if sid not in store.student_facts:
        raise KeyError(f"没有这个学生：{student_id}（可用范围 D01–D40）")
    if ind_id not in store.catalogs.indicator_names:
        raise KeyError(f"没有这个指标：{indicator_identifier}（可用 9 个：T01I1–T03I3）")

    rec = store.records_by_student.get(sid)
    if rec is None or rec.empty:
        return EvidenceToolResult(
            tool_meta=_meta("get_evidence", f"student_id={sid}, indicator_id={ind_id}", 0, "该生无有效记录"),
            student_identifier=sid,
            indicator_identifier=ind_id,
            evidence_item_list=[],
        )

    sub = rec[rec["指标编号"].astype(str) == ind_id]
    if sub.empty:
        return EvidenceToolResult(
            tool_meta=_meta("get_evidence", f"student_id={sid}, indicator_id={ind_id}", 0, "该生在该指标下没有有效作答"),
            student_identifier=sid,
            indicator_identifier=ind_id,
            evidence_item_list=[],
        )

    # 与判定档位同一口径：同题跨节点只算最新的一条
    counted = set(dedupe_cross_node(sub)["记录编号"].astype(str))
    flag_map = _flag_map(store)
    items: list[EvidenceItem] = []
    for _, r in sub.sort_values(["材料编号", "记录编号"]).iterrows():
        rid = str(r["记录编号"])
        items.append(
            EvidenceItem(
                record_identifier=rid,
                student_identifier=sid,
                question_identifier=str(r["材料编号"]),
                indicator_identifier=ind_id,
                theme_identifier=str(r["材料主题真值"]),
                node_identifier=str(r["节点编号"]),
                earned_score=int(r["得分"]),
                full_score=int(r["满分"]),
                student_final_answer_text=str(r.get("学生最终作答", "")),
                rubric_point_scores=_parse_rubric(r.get("评分点得分", "")),
                grading_reliability=flag_map.get(rid, "正常"),
                grading_note_text=_grading_note(store, rid),
                counted_for_conclusion=rid in counted,
            )
        )
    caveat = grading_caveat_for([i.record_identifier for i in items], store.grading_flags)
    return EvidenceToolResult(
        tool_meta=_meta(
            "get_evidence",
            f"student_id={sid}, indicator_id={ind_id}",
            len(items),
            "counted_for_conclusion=False 的是同题重复作答的旧记录，计入判定但不重复计数",
        ),
        student_identifier=sid,
        indicator_identifier=ind_id,
        evidence_item_list=items,
        grading_caveat_text=caveat,
    )


def _parse_rubric(text) -> list[tuple[str, str, int, int]]:
    """'Q015P1=1；Q015P2=1；Q015P3=0' → [(编号, 要求, 满分, 得分)]。"""
    s = str(text or "").strip()
    if not s:
        return []
    out: list[tuple[str, str, int, int]] = []
    for part in re.split(r"[；;]", s):
        m = re.match(r"\s*([A-Z]\d{3}P\d+)\s*[=＝]\s*(\d+)", part)
        if m:
            out.append((m.group(1), "", 1, int(m.group(2))))
    return out


def _grading_note(store: FactStore, record_id: str) -> str:
    row = store.grading_flags[store.grading_flags["记录编号"].astype(str) == record_id]
    if row.empty:
        return ""
    flag = str(row.iloc[0]["判分可靠性"])
    return "" if flag == "正常" else str(row.iloc[0]["说明"])


# ---------- 工具 4：get_candidates ----------

def get_candidates(
    store: FactStore,
    indicator_identifier: str,
    exclude_student: str | None = None,
    limit: int = 5,
) -> CandidateToolResult:
    """查某指标下还能用的题（先易后难）。给 exclude_student 就排除该生已做过的题。"""
    ind_id = indicator_identifier.strip().upper()
    if ind_id not in store.catalogs.indicator_names:
        raise KeyError(f"没有这个指标：{indicator_identifier}（可用 9 个：T01I1–T03I3）")
    sid = exclude_student.strip().upper() if exclude_student else None

    attempted: set[str] = set()
    if sid:
        rec = store.records_by_student.get(sid)
        if rec is not None and not rec.empty:
            attempted = set(rec["材料编号"].astype(str))
        # R12：已交但老师还没判分的题不算"还能用"，不能再推荐他去重做一遍。
        attempted |= pending_question_identifiers(store.datasets.records, sid)

    rows = [
        (qid, row)
        for qid, row in store.question_rows.items()
        if str(row.get("指标编号", "")).strip() == ind_id
    ]
    rows.sort(key=lambda kv: (int(kv[1].get("满分", 1)), kv[0]))

    cands: list[CandidateMaterial] = []
    for qid, row in rows:
        if sid and qid in attempted:
            continue
        stem = str(row.get("题干或内容", "")).replace("\n", " ").strip()
        cands.append(
            CandidateMaterial(
                material_identifier=qid,
                indicator_identifier=ind_id,
                theme_identifier=str(row.get("主题编号", "")),
                question_type=str(row.get("题型", "")),
                full_score=int(row.get("满分", 1)),
                stem_excerpt_text=stem[:80],
                reference_answer_text=str(row.get("参考答案", "")).replace("\n", " ").strip(),
                already_attempted_by_target_student=qid in attempted,
                source_or_file_text=str(row.get("来源或资料文件", "")),
            )
        )
        if len(cands) >= limit:
            break

    return CandidateToolResult(
        tool_meta=_meta(
            "get_candidates",
            f"indicator_id={ind_id}, exclude_student={sid or '无'}",
            len(cands),
            "候选池只含真实题目（Qxxx），学习卡 L01–L03 与教材条目不参与推荐",
        ),
        indicator_identifier=ind_id,
        exclude_student_identifier=sid,
        candidate_material_list=cands,
    )


# ---------- 工具声明（给前端与 langchain 队友） ----------

def _students_for(store: FactStore, class_identifier: str | None) -> list[str]:
    if class_identifier is None or str(class_identifier).strip().upper() in {"ALL", "全体", "全年级", ""}:
        return sorted(store.student_facts)
    key = str(class_identifier).strip().upper()
    if key not in store.class_facts:
        raise KeyError(f"没有这个班级：{class_identifier}（可用 DC01 / DC02，或留空表示全年级）")
    return sorted(s for s, f in store.student_facts.items() if f.class_identifier == key)


def get_class_indicator_detail(
    store: FactStore,
    class_identifier: str | None,
    indicator_identifier: str,
) -> ClassIndicatorDetailResult:
    """班级 × 指标下钻：这一格到底是谁、为什么、还差多少。

    前端屏 4（知识点下钻树）就靠这一个调用把「三堆人」画出来。
    """
    ind_id = indicator_identifier.strip().upper()
    if ind_id not in store.catalogs.indicator_names:
        raise KeyError(f"没有这个指标：{indicator_identifier}（可用 9 个：T01I1–T03I3）")
    students = _students_for(store, class_identifier)
    label = "全年级" if len(students) == len(store.student_facts) and (
        class_identifier is None or str(class_identifier).strip().upper() in {"ALL", "全体", "全年级", ""}
    ) else str(class_identifier).strip().upper()

    theme = ind_id[:3]
    level_map: dict[str, object] = {}
    for sid in students:
        for lvl in store.student_facts[sid].indicator_level_detail_list:
            if lvl.indicator_identifier == ind_id:
                level_map[sid] = lvl
                break

    rec_needed = store.clean.records_clean
    sub_all = rec_needed[rec_needed["指标编号"].astype(str) == ind_id]
    sub_all = sub_all[sub_all["学生编号"].astype(str).isin(students)]
    class_earned = int(sub_all["得分"].sum())
    class_full = int(sub_all["满分"].sum())
    class_rate = round(class_earned / class_full, 4) if class_full else None

    not_mastered: list[ClassIndicatorStudentRow] = []
    mastered: list[ClassIndicatorStudentRow] = []
    insufficient: list[ClassIndicatorStudentRow] = []
    n_det = n_ten = n_un = 0

    for sid in students:
        lvl = level_map.get(sid)
        if lvl is None:
            continue
        rate = lvl.indicator_correct_score_rate
        rec = store.records_by_student.get(sid)
        rids = sorted(rec[rec["指标编号"].astype(str) == ind_id]["记录编号"].astype(str)) if rec is not None else []
        row = ClassIndicatorStudentRow(
            student_identifier=sid,
            class_identifier=store.student_facts[sid].class_identifier,
            conclusion_level=lvl.conclusion_level,
            earned_score=lvl.earned_score_total,
            full_score=lvl.attempted_full_score,
            correct_score_rate=rate,
            distinct_attempted_count=lvl.distinct_attempted_count,
            insufficiency_reason_code=lvl.insufficiency_reason_code,
            record_identifiers=rids,
        )
        if lvl.conclusion_level == LEVEL_SUFFICIENT:
            n_det += 1
            if rate is not None and rate < 0.4:
                row.one_line_hint_text = "已能判断：得分率低于 40%，属于没掌握，需要重讲"
                not_mastered.append(row)
            else:
                row.one_line_hint_text = "已能判断：得分率不低于 40%，可以做对，不必重讲"
                mastered.append(row)
        elif lvl.conclusion_level == LEVEL_PARTIAL:
            n_ten += 1
            need = max(1, lvl.evidence_threshold_for_conclusion - lvl.distinct_attempted_count)
            row.one_line_hint_text = f"证据不足：做过 {lvl.distinct_attempted_count} 道，再做 {need} 道同指标题就能下判断"
            insufficient.append(row)
        else:
            n_un += 1
            reason = str(lvl.insufficiency_reason_code or "")
            row.one_line_hint_text = (
                "还没教到，等教到再测" if reason == "not_taught"
                else "教过但一道没做" if reason == "no_attempt"
                else "待评分，暂无可用分数" if reason == "pending_score"
                else "还没有可用证据"
            )
            insufficient.append(row)

    safe = n_det >= 3
    warning = (
        ""
        if safe
        else f"能下判断的只有 {n_det} 人，这个得分率不能当作全班结论，只能进「证据不足」。"
    )

    hints: list[str] = []
    for edge in PREREQUISITE_EDGES:
        if str(edge.get("to_indicator")) != ind_id:
            continue
        src = str(edge.get("from_indicator"))
        src_ids = {s for s in students}
        sub_src = rec_needed[rec_needed["指标编号"].astype(str) == src]
        sub_src = sub_src[sub_src["学生编号"].astype(str).isin(src_ids)]
        e = int(sub_src["得分"].sum())
        f = int(sub_src["满分"].sum())
        judged = [
            s
            for s in students
            if any(
                l.indicator_identifier == src and l.conclusion_level == LEVEL_SUFFICIENT
                for l in store.student_facts[s].indicator_level_detail_list
            )
        ]
        weak = [
            s
            for s in judged
            if any(
                l.indicator_identifier == src
                and l.conclusion_level == LEVEL_SUFFICIENT
                and (l.indicator_correct_score_rate or 0) < 0.4
                for l in store.student_facts[s].indicator_level_detail_list
            )
        ]
        rate_txt = f"{e / f * 100:.2f}%" if f else "无数据"
        hints.append(
            f"讲 {ind_id} 之前先看 {src}：{label} {rate_txt}，能判断 {len(judged)} 人，其中 {len(weak)} 人明确没掌握"
        )

    return ClassIndicatorDetailResult(
        tool_meta=_meta(
            "get_class_indicator_detail",
            f"class_id={label}, indicator_id={ind_id}",
            len(not_mastered) + len(mastered) + len(insufficient),
            "按 R5 三档分堆；能下判断人数 <3 时不给全班结论（小样本门槛）",
        ),
        class_identifier=label,
        indicator_identifier=ind_id,
        indicator_description_text=str(store.catalogs.indicator_names.get(ind_id, "")),
        theme_identifier=theme,
        class_earned_score_total=class_earned,
        class_attempted_full_score_total=class_full,
        class_correct_score_rate=class_rate,
        student_count_determined=n_det,
        student_count_tendency=n_ten,
        student_count_unobserved=n_un,
        is_safe_as_class_conclusion=safe,
        not_mastered_students=not_mastered,
        mastered_students=mastered,
        insufficient_students=insufficient,
        prerequisite_hint_list=hints,
        small_sample_warning_text=warning,
    )


def tool_descriptors() -> list[ToolDescriptor]:
    """六个工具的对外声明。不参与计算，改签名时同步改这里。"""
    return [
        ToolDescriptor(
            tool_name="get_student",
            one_line_purpose_text="查一个学生的全部学情事实（指标档位、主题、每场考试、记录编号）",
            parameter_schema_text="student_id: str（形如 D03）",
            return_contract_name="StudentToolResult",
            when_to_call_text="教师问到某个具体学生，或前端点开某个学生的个人卡",
            when_not_to_call_text="问的是全班情况时不要逐个调用，用 get_group",
        ),
        ToolDescriptor(
            tool_name="get_group",
            one_line_purpose_text="查一个班或全年级的群体学情，含最薄弱主题与需要优先关注的学生顺序",
            parameter_schema_text="class_id: str | None（DC01 / DC02 / 留空表示全年级）",
            return_contract_name="GroupToolResult",
            when_to_call_text="教师问班级整体、比较两个班、问谁最需要关注",
        ),
        ToolDescriptor(
            tool_name="get_evidence",
            one_line_purpose_text="查某学生某指标的逐条作答证据（含判分存疑标注）",
            parameter_schema_text="student_id: str, indicator_id: str（如 T03I1）",
            return_contract_name="EvidenceToolResult",
            when_to_call_text="需要引用具体记录编号支撑结论时；教师要追问依据时",
            when_not_to_call_text="只需要结论时用 get_student，不必拉明细",
        ),
        ToolDescriptor(
            tool_name="get_candidates",
            one_line_purpose_text="查某指标下还能用的题目，可按学生排除已做过的题，先易后难",
            parameter_schema_text="indicator_id: str, exclude_student: str | None, limit: int = 5",
            return_contract_name="CandidateToolResult",
            when_to_call_text="要给补练题、要安排后测题时",
            when_not_to_call_text="不要用它编造题目编号；返回池子为空时必须如实说明",
        ),
        ToolDescriptor(
            tool_name="get_class_indicator_detail",
            one_line_purpose_text="班级 × 指标下钻：这一格是谁、为什么、还差多少（前端把学生分三堆）",
            parameter_schema_text="class_id: str | None（DC01 / DC02 / 留空全年级）, indicator_id: str",
            return_contract_name="ClassIndicatorDetailResult",
            when_to_call_text="教师问「二班不等式到底谁不会」「这个知识点该讲给谁听」时",
            when_not_to_call_text="只问班级整体排名时用 get_group；学生能下判断不足 3 人时不得当全班结论",
        ),
        ToolDescriptor(
            tool_name="load_facts",
            one_line_purpose_text="把五张 CSV 装配成只读事实仓库（内部用，不直接面向教师）",
            parameter_schema_text="data_dir: str | Path",
            return_contract_name="FactStore",
            when_to_call_text="服务启动时调用一次，之后所有工具共用这一个仓库",
            when_not_to_call_text="不要在每次请求里都调用，806 条记录全量重算虽然只要百毫秒但没必要",
        ),
    ]
