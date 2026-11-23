# -*- coding: utf-8 -*-
"""把五张原始表整合成一份干净数据集（JSON + CSV）。

个人层三张表（逻辑三张，物理装在一个人一个 JSON 的三块里）：
    1. question_records   一人一次作答
    2. indicator_summary  一人一指标（9 行）+ 三行主题小计
    3. exam_comparison    一人 × 每场考试 × 每指标

再外加：班级三张、按主题三张、质量与剔除四张、三张字典、一份索引。

铁律
    · 只出数字与出处，不出一句结论（结论由队友的 LLM 做）。
    · 空值一律 None（JSON 里 null），绝不用 0 或空串代替。
    · CSV 与 JSON 由同一份内存数据生成，字段一一对应。
    · 出处只到主题级范围（课标条目区间 + 教材页码范围），不下沉到逐题页码。
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from content_map import CURRICULUM_CITATIONS, CURRICULUM_SECTION_TEXT, quote_of
from tools import FactStore, load_facts

THEME_ORDER = ["T01", "T02", "T03"]
INDICATOR_ORDER = [f"{t}I{i}" for t in THEME_ORDER for i in (1, 2, 3)]


# --------------------------------------------------------------------------
# 小工具
# --------------------------------------------------------------------------

def _num(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _r4(value):
    value = _num(value)
    if value is None:
        return None
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _int(value):
    value = _num(value)
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _text(value):
    value = _num(value)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, float):
        text = f"{value:.4f}".rstrip("0").rstrip(".")
        return text or "0"
    text = str(value).replace('"', '""')
    return f'"{text}"' if ("," in text or '"' in text or "\n" in text) else text


def write_csv(path: Path, rows: list[dict], headers: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = [k for k, _ in headers]
    lines = [",".join(label for _, label in headers)]
    for row in rows:
        lines.append(",".join(_cell(row.get(k)) for k in keys))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# 主题级出处（一次算好，全库共用）
# --------------------------------------------------------------------------

def build_theme_citations(store: FactStore) -> dict[str, str]:
    """主题 → 「CR01 （3）代数式 ②③⑤（文件P62／正文P55）」这种主题级范围。"""
    req = store.datasets.curriculum.drop_duplicates("主题编号").set_index("主题编号")
    out = {}
    for theme in THEME_ORDER:
        row = req.loc[theme]
        cr = str(row["课标整理编号"])
        heading = ""
        file_page = str(row["课标文件页／正文页"]).split("／")[0]
        body_page = str(row["课标文件页／正文页"]).split("／")[-1]
        items: list[str] = []
        for i in (1, 2, 3):
            for cite in CURRICULUM_CITATIONS.get(f"{theme}I{i}", []):
                heading = heading or cite["section_heading"]
                file_page = str(cite["file_page"])
                body_page = str(cite["body_page"])
                if cite["item_label"] not in items:
                    items.append(cite["item_label"])
        items.sort()
        out[theme] = (
            f"{cr} {''.join(items)} P{file_page}/{body_page}"
            if items
            else f"{cr} P{file_page}/{body_page}"
        )
    return out


def build_textbook_scope(store: FactStore) -> dict[str, str]:
    req = store.datasets.curriculum.drop_duplicates("主题编号").set_index("主题编号")
    return {theme: str(req.loc[theme]["教材正文页"]).replace("—", "-") for theme in THEME_ORDER}


def build_question_index(store: FactStore) -> dict[str, dict]:
    """材料编号 → {indicator, full, type, theme}；只收题目（Q 开头）。"""
    idx = {}
    for _, r in store.datasets.materials.iterrows():
        mid = str(r["材料编号"])
        if not mid.startswith("Q"):
            continue
        idx[mid] = {
            "indicator": _text(r["指标编号"]),
            "full": _int(r["满分"]),
            "type": _text(r["题型"]),
            "theme": _text(r["主题编号"]),
        }
    return idx


def questions_of_indicator(store: FactStore) -> dict[str, list[str]]:
    qmap: dict[str, list[str]] = {ind: [] for ind in INDICATOR_ORDER}
    for qid, meta in build_question_index(store).items():
        ind = meta["indicator"]
        if ind in qmap:
            qmap[ind].append(qid)
    return {k: sorted(v) for k, v in qmap.items()}


# --------------------------------------------------------------------------
# 三张字典
# --------------------------------------------------------------------------

def build_indicator_dict(store: FactStore) -> list[dict]:
    cats = store.catalogs
    cites = build_theme_citations(store)
    books = build_textbook_scope(store)
    qmap = questions_of_indicator(store)
    rows = []
    for ind in INDICATOR_ORDER:
        theme = cats.indicator_theme[ind]
        rows.append(
            {
                "indicator_id": ind,
                "indicator_name": cats.indicator_names[ind],
                "theme_id": theme,
                "theme_name": cats.theme_names[theme],
                "curriculum_scope": cites[theme],
                "textbook_scope": books[theme],
                "questions_in_bank": len(qmap[ind]),
                "question_ids": "、".join(qmap[ind]),
            }
        )
    return rows


def build_question_dict_full(store: FactStore) -> list[dict]:
    """完整版：含题干、参考答案、解析。只用于写 CSV（给人看）。"""
    cats = store.catalogs
    rows = []
    for _, r in store.datasets.materials.iterrows():
        theme = _text(r["主题编号"])
        ind = _text(r["指标编号"])
        rows.append(
            {
                "material_id": str(r["材料编号"]),
                "material_type": str(r["材料类型"]),
                "theme_id": theme,
                "theme_name": cats.theme_names.get(theme) if theme in cats.theme_names else None,
                "indicator_id": ind,
                "indicator_name": INDICATOR_NAME(store, ind),
                "question_type": _text(r["题型"]),
                "full_score": _int(r["满分"]),
                "rubric_points": _text(r["评分点"]),
                "reference_answer": _text(r["参考答案"]),
                "source_file": _text(r["来源或资料文件"]),
            }
        )
    return rows


def build_question_dict(store: FactStore) -> list[dict]:
    """瘦身版（给程序读）：只有"这道题属于谁、几分"，题干与答案不在这里。"""
    cats = store.catalogs
    rows = []
    for _, r in store.datasets.materials.iterrows():
        qid = str(r["材料编号"])
        if not qid.startswith("Q"):
            continue
        theme = _text(r["主题编号"])
        rows.append(
            {
                "material_id": qid,
                "theme_id": theme,
                "indicator_id": _text(r["指标编号"]),
                "question_type": _text(r["题型"]),
                "full_score": _int(r["满分"]),
                "rubric_point_count": len(_split_rubric_points(r["评分点"])),
            }
        )
    return sorted(rows, key=lambda x: x["material_id"])


def _split_rubric_points(text) -> list[str]:
    """把"Q014P1 ...\\nQ014P2 ..."拆成列表，只为数个数。"""
    raw = _text(text)
    if not raw:
        return []
    return [ln for ln in str(raw).splitlines() if ln.strip()]


def build_question_content(store: FactStore) -> list[dict]:
    """内容层：题干、选项、参考答案、解析。与"数据"分开，按需加载。"""
    rows = []
    for _, r in store.datasets.materials.iterrows():
        qid = str(r["材料编号"])
        if not qid.startswith("Q"):
            continue
        rows.append(
            {
                "material_id": qid,
                "question_type": _text(r["题型"]),
                "stem": _text(r["题干或内容"]),
                "options": _text(r["选项"]),
                "reference_answer": _text(r["参考答案"]),
                "explanation": _text(r["参考解析"]),
                "source_file": _text(r["来源或资料文件"]),
            }
        )
    return sorted(rows, key=lambda x: x["material_id"])


def build_citation_text(store: FactStore) -> dict:
    """课标原文：三段小节的全部条目（一字不改）+ 指标到条目的对应。

    为什么单出一份：数据集里 `curriculum_scope` 只写编号（`CR01 ①②③⑤ P62/55`），
    评委或队友拿到编号要能翻到原文，所以原文单独放在 `00_字典/课标原文.*`。
    """
    names = store.catalogs.indicator_names
    sections = []
    for group in ("CR01", "CR02", "CR03"):
        sec = CURRICULUM_SECTION_TEXT[group]
        sections.append(
            {
                "group": group,
                "theme_id": sec["theme_id"],
                "theme_name": store.catalogs.theme_names[sec["theme_id"]],
                "heading_path": sec["heading_path"],
                "file_pages": sec["file_pages"],
                "body_pages": sec["body_pages"],
                "note": sec["note"],
                "item_count": len(sec["items"]),
            }
        )
    items = []
    for group in ("CR01", "CR02", "CR03"):
        sec = CURRICULUM_SECTION_TEXT[group]
        for no, text, used in sec["items"]:
            items.append(
                {
                    "group": group,
                    "theme_id": sec["theme_id"],
                    "section_heading": sec["section_heading"],
                    "item_label": no,
                    "text": text,
                    "used_by_indicators": "、".join(used) if used else None,
                    "file_page": sec["file_pages"][0] if no != "⑧" and no != "⑨" else sec["file_pages"][-1],
                    "body_page": sec["body_pages"][0] if no != "⑧" and no != "⑨" else sec["body_pages"][-1],
                }
            )
    mapping = []
    for ind in INDICATOR_ORDER:
        for cite in CURRICULUM_CITATIONS.get(ind, []):
            mapping.append(
                {
                    "indicator_id": ind,
                    "indicator_name": names.get(ind),
                    "citation": cite["citation_identifier"],
                    "item_label": cite["item_label"],
                    "used_part": cite["used_part"],
                    "quote_full": quote_of(cite["item_label"], cite["group"]),
                    "file_page": cite["file_page"],
                    "body_page": cite["body_page"],
                }
            )
    return {
        "说明": "课标原文逐条照抄，只去掉句末标点；`used_part` 写清这个指标用的是哪半句。"
        "三段小节的全部条目都列在这里，没被任何指标用到的也留着，方便核对。"
        "原件是零文字层扫描件，两页截图在 `05_出处截图/kb_p62.png`、`kb_p63.png`。",
        "小节": sections,
        "原文条目": items,
        "指标对应": mapping,
    }


def INDICATOR_NAME(store: FactStore, ind):
    if not ind or ind not in store.catalogs.indicator_names:
        return None
    return store.catalogs.indicator_names[ind]


def build_exam_dict(store: FactStore) -> list[dict]:
    cats = store.catalogs
    rows = []
    for _, r in store.datasets.nodes.iterrows():
        nid = str(r["节点编号"])
        rows.append(
            {
                "exam_id": nid,
                "exam_date": str(r["模拟测验日期"]),
                "taught_themes": str(r["已教及测量主题"]),
                "questions_available": len(cats.node_available[nid]),
                "note": _text(r["说明"]),
            }
        )
    return sorted(rows, key=lambda x: x["exam_id"])


# --------------------------------------------------------------------------
# 个人三块
# --------------------------------------------------------------------------

def _reason_note(code) -> str | None:
    return {
        "not_taught": "这部分学校还没教到",
        "not_in_scope": "他参加过的考试里没出过这个指标的题",
        "no_attempt": "这场出了这个指标的题，他没做",
        "pending_score": "做了但老师还没判分",
        "evidence_short": "做过的题还不够多，先记下",
    }.get(code)


def build_question_records(store: FactStore, student_id: str, qidx: dict) -> list[dict]:
    rec = store.records_by_student.get(student_id)
    if rec is None or len(rec) == 0:
        return []
    flags = store.grading_flags
    flag_map = dict(zip(flags["记录编号"], flags["判分可靠性"])) if len(flags) else {}
    cats = store.catalogs
    rows = []
    for _, r in rec.iterrows():
        qid = str(r["材料编号"])
        meta = qidx.get(qid, {})
        theme = meta.get("theme") or _text(r["主题编号"])
        score, full = _int(r["得分"]), _int(r["满分"])
        rows.append(
            {
                "record_id": r["记录编号"],
                "exam_id": r["节点编号"],
                "question_id": qid,
                "theme_id": theme,
                "indicator_id": meta.get("indicator"),
                "full_score": full,
                "score": score,
                "score_rate": _r4(score / full) if (score is not None and full) else None,
                "rubric_scores": _text(r["评分点得分"]),
                "counted_in_denominator": True,
                "grading_flag": flag_map.get(r["记录编号"]),
            }
        )
    return sorted(rows, key=lambda x: (x["exam_id"], x["question_id"]))


def _supplementary(store: FactStore, student_id: str, indicator_id: str, qidx: dict, qmap: dict) -> list[str]:
    available = set(store.node_availability_by_student.get(student_id, set()))
    rec = store.records_by_student.get(student_id)
    done = set(rec["材料编号"]) if rec is not None and len(rec) else set()
    raw = store.datasets.records
    pending = set(raw[(raw["学生编号"] == student_id) & (raw["评分状态"] == "待评分")]["材料编号"])
    return sorted(
        [q for q in qmap.get(indicator_id, []) if q in available and q not in done and q not in pending],
        key=lambda q: (qidx.get(q, {}).get("full") or 0, q),
    )


def build_indicator_summary(store: FactStore, student_id: str) -> list[dict]:
    facts = store.student_facts[student_id]
    cats = store.catalogs
    cites = build_theme_citations(store)
    books = build_textbook_scope(store)
    qidx = build_question_index(store)
    qmap = questions_of_indicator(store)
    rows = []
    for ind in facts.indicator_level_detail_list:
        iid = ind.indicator_identifier
        theme = cats.indicator_theme[iid]
        cands = _supplementary(store, student_id, iid, qidx, qmap)
        touched = ind.distinct_attempted_count > 0
        rows.append(
            {
                "row_type": "indicator",
                "indicator_id": iid,
                "theme_id": theme,
                "questions_in_bank": ind.total_question_count_for_indicator,
                "questions_available": ind.available_question_count,
                "distinct_attempted": ind.distinct_attempted_count,
                "evidence_threshold": ind.evidence_threshold_for_conclusion,
                "coverage_rate": _r4(
                    ind.distinct_attempted_count / ind.available_question_count
                    if ind.available_question_count
                    else None
                ),
                "score": ind.earned_score_total if touched else None,
                "full_score": ind.attempted_full_score if touched else None,
                "score_rate": _r4(ind.indicator_correct_score_rate) if touched else None,
                "conclusion_level": ind.conclusion_level,
                "reason": _reason_note(ind.insufficiency_reason_code),
                "curriculum_scope": cites[theme],
                "textbook_scope": books[theme],
                "supplementary_question_ids": "、".join(
                    f"{q}({qidx.get(q, {}).get('full')}分)" for q in cands
                )
                or None,
            }
        )
    # 主题小计的"能考到"＝该主题三个指标之和（否则主题表只有得分没有覆盖率）
    theme_scope = {}
    for r in rows:
        t = r["theme_id"]
        bank, avail = theme_scope.get(t, (0, 0))
        theme_scope[t] = (
            bank + (r["questions_in_bank"] or 0),
            avail + (r["questions_available"] or 0),
        )
    for th in facts.theme_level_summary_list:
        theme = th.theme_identifier
        touched = th.distinct_attempted_question_count > 0
        bank_total, avail_total = theme_scope.get(theme, (0, 0))
        rows.append(
            {
                "row_type": "theme",
                "indicator_id": f"{theme} 小计",
                "theme_id": theme,
                "questions_in_bank": bank_total,
                "questions_available": avail_total,
                "distinct_attempted": th.distinct_attempted_question_count,
                "evidence_threshold": th.evidence_threshold,
                "coverage_rate": _r4(th.distinct_attempted_question_count / avail_total)
                if avail_total
                else None,
                "score": th.earned_score_total if touched else None,
                "full_score": th.attempted_full_score_total if touched else None,
                "score_rate": _r4(th.theme_correct_score_rate) if touched else None,
                "conclusion_level": th.conclusion_level,
                "reason": None,
                "curriculum_scope": cites[theme],
                "textbook_scope": books[theme],
                "supplementary_question_ids": None,
            }
        )
    return rows


def build_exam_comparison(store: FactStore, student_id: str) -> list[dict]:
    facts = store.student_facts[student_id]
    cats = store.catalogs
    qmap = questions_of_indicator(store)
    exams = sorted(cats.node_date)
    attended = set(facts.attended_node_identifiers or [])
    by_key = {}
    for ind in facts.indicator_level_detail_list:
        for row in ind.exam_node_record_list:
            by_key[(row.node_identifier, ind.indicator_identifier)] = row
    rows = []
    for exam in exams:
        if exam not in attended:
            # 没参加的考试只在小计里说明，不逐指标占行
            continue
        for iid in INDICATOR_ORDER:
            theme = cats.indicator_theme[iid]
            rec = by_key.get((exam, iid))
            in_exam = len(cats.node_available[exam] & set(qmap[iid]))
            if in_exam == 0:
                # 这场没出这个指标的题：不占行
                continue
            if rec is None:
                continue
            rows.append(
                {
                    "row_type": "indicator",
                    "exam_id": exam,
                    "theme_id": theme,
                    "indicator_id": iid,
                    "participated": bool(rec.student_participated_flag),
                    "questions_in_exam": rec.questions_available_in_node,
                    "distinct_attempted": rec.distinct_attempted_count,
                    "score": rec.earned_score_total if rec.distinct_attempted_count else None,
                    "full_score": rec.attempted_full_score if rec.distinct_attempted_count else None,
                    "score_rate": _r4(rec.correct_score_rate) if rec.distinct_attempted_count else None,
                    "teaching_status": rec.teaching_status_in_node,
                    "note": rec.plain_language_note_text,
                }
            )
    for exam in exams:
        block = [r for r in rows if r["exam_id"] == exam]
        scores = [r["score"] for r in block if r["score"] is not None]
        fulls = [r["full_score"] for r in block if r["full_score"] is not None]
        total_score = sum(scores) if scores else None
        total_full = sum(fulls) if fulls else None
        rows.append(
            {
                "row_type": "exam_total",
                "exam_id": exam,
                "theme_id": None,
                "indicator_id": f"{exam} 小计",
                "participated": exam in attended,
                "questions_in_exam": len(cats.node_available[exam]),
                "distinct_attempted": sum(
                    r["distinct_attempted"] for r in block if r.get("distinct_attempted")
                )
                or None,
                "score": total_score,
                "full_score": total_full,
                "score_rate": _r4(total_score / total_full) if (total_score is not None and total_full) else None,
                "teaching_status": None,
                "note": _exam_total_note(exam, attended, cats, qmap, block),
            }
        )
    return rows


def _exam_total_note(exam: str, attended: set, cats, qmap, block: list[dict]) -> str:
    if exam not in attended:
        return "没有参加这场考试"
    missing = [i for i in INDICATOR_ORDER if cats.node_available[exam] & set(qmap[i]) and i not in {b["indicator_id"] for b in block}]
    if missing:
        return "另有这些指标这场出了题但没有有效记录：" + "、".join(missing)
    return "这场有记录的指标都列在上面了"


def build_student_package(store: FactStore, student_id: str) -> dict:
    facts = store.student_facts[student_id]
    return {
        "student": {
            "student_id": facts.student_identifier,
            "class_id": facts.class_identifier,
            "grade": facts.grade_level,
            "record_count": facts.valid_record_count,
            "distinct_question_count": facts.distinct_attempted_question_count,
            "available_question_count": facts.available_question_count,
            "score_total": facts.earned_score_total,
            "full_score_total": facts.attempted_full_score_total,
            "score_rate": _r4(facts.correct_score_rate),
            "attended_exams": list(facts.attended_node_identifiers or []),
        },
        "question_records": build_question_records(store, student_id, build_question_index(store)),
        "indicator_summary": build_indicator_summary(store, student_id),
        "exam_comparison": build_exam_comparison(store, student_id),
    }


# --------------------------------------------------------------------------
# 班级层 / 主题层
# --------------------------------------------------------------------------

def build_class_overview(store: FactStore) -> list[dict]:
    rows = []
    for sid in sorted(store.student_facts):
        facts = store.student_facts[sid]
        themes = {th.theme_identifier: th for th in facts.theme_level_summary_list}
        rows.append(
            {
                "student_id": sid,
                "class_id": facts.class_identifier,
                "record_count": facts.valid_record_count,
                "distinct_question_count": facts.distinct_attempted_question_count,
                "available_question_count": facts.available_question_count,
                "score": facts.earned_score_total,
                "full_score": facts.attempted_full_score_total,
                "score_rate": _r4(facts.correct_score_rate),
                "t01_score_rate": _r4(themes["T01"].theme_correct_score_rate),
                "t02_score_rate": _r4(themes["T02"].theme_correct_score_rate),
                "t03_score_rate": _r4(themes["T03"].theme_correct_score_rate),
            }
        )
    return rows


def _groups(store: FactStore) -> list[tuple[str, list[str]]]:
    classes = sorted({f.class_identifier for f in store.student_facts.values()})
    groups = [(c, [s for s in sorted(store.student_facts) if store.student_facts[s].class_identifier == c]) for c in classes]
    groups.append(("全年级", sorted(store.student_facts)))
    return groups


def build_class_indicator_table(store: FactStore) -> list[dict]:
    cats = store.catalogs
    rows = []
    for label, sids in _groups(store):
        for iid in INDICATOR_ORDER:
            score = full = attempted = available = holders = 0
            for sid in sids:
                for ind in store.student_facts[sid].indicator_level_detail_list:
                    if ind.indicator_identifier != iid:
                        continue
                    score += ind.earned_score_total
                    full += ind.attempted_full_score
                    attempted += ind.distinct_attempted_count
                    available += ind.available_question_count
                    if ind.distinct_attempted_count:
                        holders += 1
            rows.append(
                {
                    "group": label,
                    "student_count": len(sids),
                    "theme_id": cats.indicator_theme[iid],
                    "indicator_id": iid,
                    "indicator_name": cats.indicator_names[iid],
                    "questions_available_total": available or None,
                    "distinct_attempted_total": attempted or None,
                    "score": score,
                    "full_score": full,
                    "score_rate": _r4(score / full) if full else None,
                    "students_with_records": holders,
                }
            )
    return rows


def build_class_theme_table(store: FactStore) -> list[dict]:
    cats = store.catalogs
    rows = []
    for label, sids in _groups(store):
        for theme in THEME_ORDER:
            score = full = attempted = holders = 0
            for sid in sids:
                for th in store.student_facts[sid].theme_level_summary_list:
                    if th.theme_identifier != theme:
                        continue
                    score += th.earned_score_total
                    full += th.attempted_full_score_total
                    attempted += th.distinct_attempted_question_count
                    if th.distinct_attempted_question_count:
                        holders += 1
            rows.append(
                {
                    "group": label,
                    "student_count": len(sids),
                    "theme_id": theme,
                    "theme_name": cats.theme_names[theme],
                    "distinct_attempted_total": attempted or None,
                    "score": score,
                    "full_score": full,
                    "score_rate": _r4(score / full) if full else None,
                    "students_with_records": holders,
                }
            )
    return rows


def build_theme_student_table(store: FactStore, theme: str) -> list[dict]:
    rows = []
    for sid in sorted(store.student_facts):
        facts = store.student_facts[sid]
        th = next((x for x in facts.theme_level_summary_list if x.theme_identifier == theme), None)
        if th is None:
            continue
        per = {ind.indicator_identifier: ind for ind in facts.indicator_level_detail_list}
        row = {
            "student_id": sid,
            "class_id": facts.class_identifier,
            "questions_available": sum(per[f"{theme}I{i}"].available_question_count for i in (1, 2, 3)),
            "distinct_attempted": th.distinct_attempted_question_count,
            "score": th.earned_score_total,
            "full_score": th.attempted_full_score_total,
            "score_rate": _r4(th.theme_correct_score_rate),
        }
        for i in (1, 2, 3):
            row[f"i{i}_score_rate"] = _r4(per[f"{theme}I{i}"].indicator_correct_score_rate)
        rows.append(row)
    return rows


# --------------------------------------------------------------------------
# 质量与剔除
# --------------------------------------------------------------------------

def build_quality_tables(store: FactStore) -> dict[str, list[dict]]:
    issues = [
        {
            "issue_code": it["issue_code"],
            "severity": it["severity"],
            "record_count": it["count"],
            "sample_record_ids": it["sample_record_ids"],
            "description": it["description"],
            "handling": it["handling"],
            "affects_denominator": "是" if it["severity"] == "error" else "否",
        }
        for it in store.clean.issues
    ]

    raw = store.datasets.records
    kept = set(store.clean.records_clean["记录编号"])
    # 被判"旧修订版本"的判定要和 clean.py 的减法顺序一致：多版本去重最先做，
    # 所以同一作答事件里被更高修订版本取代的那条，原因就是"旧修订版本"，
    # 不能因为它同时还带"待评分"就改标成待评分（DR0018 / DR0199 就是这么标错的）。
    max_revision = {
        str(r["作答事件编号"]): _int(r["修订版本"])
        for _, r in raw[raw["记录编号"].isin(kept)].iterrows()
    }
    excluded = []
    for _, r in raw.iterrows():
        if r["记录编号"] in kept:
            continue
        status = str(r["评分状态"])
        score = pd.to_numeric(r["得分"], errors="coerce")
        full = pd.to_numeric(r["满分"], errors="coerce")
        event = str(r["作答事件编号"])
        if event in max_revision and _int(r["修订版本"]) < max_revision[event]:
            reason = "旧修订版本（已被更高版本替代）"
        elif status == "待评分":
            reason = "待评分（老师还没判分）"
        elif status == "未作答":
            reason = "未作答（空答案）"
        elif not pd.isna(score) and not pd.isna(full) and score > full:
            reason = "得分超满分（录入错误）"
        else:
            reason = "旧修订版本（已被更高版本替代）"
        excluded.append(
            {
                "record_id": r["记录编号"],
                "student_id": r["学生编号"],
                "question_id": r["材料编号"],
                "exam_id": r["节点编号"],
                "revision_version": _int(r["修订版本"]),
                "scoring_status": status,
                "score": _int(score) if not pd.isna(score) else None,
                "full_score": _int(full) if not pd.isna(full) else None,
                "exclusion_reason": reason,
            }
        )

    by_event: dict[str, list] = {}
    for _, r in raw.iterrows():
        by_event.setdefault(str(r["作答事件编号"]), []).append(r)
    multi = []
    for event, rows in by_event.items():
        if len(rows) < 2:
            continue
        rows = sorted(rows, key=lambda x: _int(x["修订版本"]) or 0)
        last = rows[-1]["记录编号"]
        for r in rows:
            s = pd.to_numeric(r["得分"], errors="coerce")
            multi.append(
                {
                    "event_id": event,
                    "student_id": r["学生编号"],
                    "question_id": r["材料编号"],
                    "revision_version": _int(r["修订版本"]),
                    "scoring_status": r["评分状态"],
                    "score": _int(s) if not pd.isna(s) else None,
                    "is_final": r["记录编号"] == last,
                }
            )
    multi.sort(key=lambda x: (x["event_id"], x["revision_version"] or 0))

    suspect = [
        {
            "record_id": r["记录编号"],
            "student_id": r["学生编号"],
            "question_id": r["材料编号"],
            "grading_flag": r["判分可靠性"],
            "note": r["说明"],
        }
        for _, r in store.grading_flags[store.grading_flags["判分可靠性"] != "正常"].iterrows()
    ]

    return {
        "质量检查清单": issues,
        "被剔除记录": excluded,
        "多版本明细": multi,
        "判分存疑": suspect,
    }
