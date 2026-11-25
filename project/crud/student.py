import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import dataset_dir, students_data_dir
from models.dataset import (
    DictIndicator,
    DictQuestion,
    StudentOverview,
    StudentProfile,
    StudentQuestionRecord,
)
from utils.file_tools import read_csv_file, read_json_file, to_float, to_int
from utils.knowledge_graph import load_knowledge_graph


def _model_to_row_dict(row: StudentOverview) -> dict:
    """把 ORM 对象转成和 速览.csv 一致的字典格式"""
    return {
        "行类型": row.row_type,
        "主题编号": row.theme_id,
        "主题名称": row.theme_name,
        "指标编号": row.indicator_id,
        "指标名称": row.indicator_name,
        "全库题数": row.total_bank_count,
        "他能考到": row.eligible_count,
        "做过不同题目": row.done_count,
        "判定线": row.threshold,
        "覆盖率": row.coverage_rate,
        "得分": row.score,
        "满分": row.full_score,
        "得分率": row.score_rate,
        "档位": row.tier,
        "档位说明": row.tier_note,
        "课标范围": row.curriculum_scope,
        "教材范围": row.textbook_scope,
        "可补练习题": row.recommended_questions,
    }


async def get_student_overview_rows_from_db(db: AsyncSession, student_id: str) -> list[dict]:
    stmt = (
        select(StudentOverview)
        .where(StudentOverview.student_id == student_id)
        .order_by(StudentOverview.id)
    )
    result = await db.execute(stmt)
    return [_model_to_row_dict(row) for row in result.scalars().all()]


# 查询某个学生的速览表（优先查 MySQL，查不到时读本地 CSV 兜底）
async def get_student_overview_rows(db: AsyncSession, student_id: str) -> list[dict]:
    try:
        rows = await get_student_overview_rows_from_db(db, student_id)
        if rows:
            return rows
    except Exception:
        pass

    csv_path = students_data_dir / student_id / f"{student_id}_速览.csv"
    return read_csv_file(csv_path)


def _split_question_ids(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in re.split(r"[、,，;；\s]+", str(raw).strip()) if part.strip()]


def _load_question_content_map() -> dict[str, dict]:
    items = read_json_file(dataset_dir / "06_题目内容.json")
    if not isinstance(items, list):
        return {}
    return {
        str(item.get("material_id", "")).strip(): item
        for item in items
        if isinstance(item, dict) and item.get("material_id")
    }


async def get_student_tasks(db: AsyncSession, student_id: str) -> dict | None:
    sid = student_id.strip().upper()
    content_map = _load_question_content_map()

    indicators_raw: list[dict] = []
    questions_meta: dict[str, dict] = {}
    answered_map: dict[str, dict] = {}
    student_exists = False

    # 1. 优先查询 MySQL
    try:
        ind_rows = (
            await db.execute(select(DictIndicator).order_by(DictIndicator.indicator_id))
        ).scalars().all()
        if ind_rows:
            indicators_raw = [
                {
                    "indicator_id": r.indicator_id,
                    "indicator_name": r.indicator_name,
                    "theme_id": r.theme_id,
                    "theme_name": r.theme_name,
                    "textbook_scope": r.textbook_scope or "",
                    "question_ids": _split_question_ids(r.question_ids),
                }
                for r in ind_rows
            ]

        q_rows = (await db.execute(select(DictQuestion))).scalars().all()
        for q in q_rows:
            questions_meta[q.material_id] = {
                "question_type": q.question_type or "",
                "full_score": q.full_score,
            }

        ov_check = await db.scalar(
            select(StudentOverview.id).where(StudentOverview.student_id == sid).limit(1)
        )
        if ov_check is not None:
            student_exists = True

        rec_rows = (
            await db.execute(
                select(StudentQuestionRecord).where(StudentQuestionRecord.student_id == sid)
            )
        ).scalars().all()
        for rec in rec_rows:
            if not rec.question_id:
                continue
            student_exists = True
            answered_map[rec.question_id] = {
                "score": rec.score,
                "full_score": rec.full_score,
                "score_rate": rec.score_rate,
            }
    except Exception:
        pass

    # 2. CSV / JSON 本地数据层兜底
    if not indicators_raw:
        for row in read_csv_file(dataset_dir / "00_字典" / "指标字典.csv"):
            indicators_raw.append(
                {
                    "indicator_id": row.get("指标编号", "").strip(),
                    "indicator_name": row.get("指标名称", "").strip(),
                    "theme_id": row.get("主题编号", "").strip(),
                    "theme_name": row.get("主题名称", "").strip(),
                    "textbook_scope": row.get("教材范围", "").strip(),
                    "question_ids": _split_question_ids(row.get("题号列表")),
                }
            )

    if not questions_meta:
        for row in read_csv_file(dataset_dir / "00_字典" / "题目字典.csv"):
            qid = row.get("材料编号", "").strip()
            if qid:
                questions_meta[qid] = {
                    "question_type": row.get("题型", "").strip(),
                    "full_score": to_float(row.get("满分")),
                }

    if not answered_map:
        student_json = read_json_file(students_data_dir / sid / f"{sid}.json")
        if isinstance(student_json, dict):
            student_exists = True
            for rec in student_json.get("question_records") or []:
                qid = str(rec.get("question_id") or "").strip()
                if qid:
                    answered_map[qid] = {
                        "score": to_float(rec.get("score")),
                        "full_score": to_float(rec.get("full_score")),
                        "score_rate": to_float(rec.get("score_rate")),
                    }

    if not student_exists and not (students_data_dir / sid).exists():
        return None

    indicators_out = []
    total_questions = 0
    done_questions = 0

    for ind in indicators_raw:
        q_list = []
        ind_done = 0
        for qid in ind["question_ids"]:
            c_info = content_map.get(qid, {})
            m_info = questions_meta.get(qid, {})
            ans = answered_map.get(qid)
            is_done = ans is not None
            if is_done:
                ind_done += 1
                done_questions += 1
            total_questions += 1

            q_list.append(
                {
                    "question_id": qid,
                    "question_type": c_info.get("question_type") or m_info.get("question_type") or "题目",
                    "stem": c_info.get("stem") or "",
                    "options": c_info.get("options"),
                    "full_score": ans["full_score"] if ans and ans.get("full_score") is not None else m_info.get("full_score"),
                    "done": is_done,
                    "score": ans.get("score") if ans else None,
                    "score_rate": ans.get("score_rate") if ans else None,
                }
            )

        indicators_out.append(
            {
                "indicator_id": ind["indicator_id"],
                "indicator_name": ind["indicator_name"],
                "theme_id": ind["theme_id"],
                "theme_name": ind["theme_name"],
                "textbook_scope": ind["textbook_scope"],
                "done_count": ind_done,
                "total_count": len(q_list),
                "questions": q_list,
            }
        )

    return {
        "student_id": sid,
        "total_questions": total_questions,
        "done_questions": done_questions,
        "indicators": indicators_out,
    }


def _question_sort_key(question_id: str) -> tuple[int, str]:
    nums = re.findall(r"\d+", question_id or "")
    return (int(nums[0]) if nums else 10**9, question_id or "")


async def get_student_learning_report(db: AsyncSession, student_id: str) -> dict | None:
    """组装学生端「学情报告」数据：总得分率 + 动态全部知识点得分率 + 全量错题题号列表。"""
    sid = student_id.strip().upper()
    overview_rows = await get_student_overview_rows(db, sid)

    profile_obj = None
    dict_indicators: list[dict] = []
    raw_records: list[dict] = []

    # 1. 优先从 MySQL 读取学生档案、指标字典和作答明细
    try:
        profile_obj = await db.scalar(select(StudentProfile).where(StudentProfile.student_id == sid))

        ind_rows = (
            await db.execute(select(DictIndicator).order_by(DictIndicator.indicator_id))
        ).scalars().all()
        dict_indicators = [
            {
                "indicator_id": r.indicator_id,
                "indicator_name": r.indicator_name,
                "theme_name": r.theme_name or "",
                "textbook_scope": r.textbook_scope or "",
            }
            for r in ind_rows
        ]

        rec_rows = (
            await db.execute(
                select(StudentQuestionRecord)
                .where(StudentQuestionRecord.student_id == sid)
                .order_by(StudentQuestionRecord.id)
            )
        ).scalars().all()
        raw_records = [
            {
                "question_id": (r.question_id or "").strip(),
                "exam_id": (r.exam_id or "").strip(),
                "indicator_id": (r.indicator_id or "").strip(),
                "score": r.score,
                "full_score": r.full_score,
            }
            for r in rec_rows
            if r.question_id
        ]
    except Exception:
        if db.in_transaction():
            await db.rollback()

    # 2. 本地数据层文件兜底
    student_json = None
    if profile_obj is None or not raw_records:
        student_json = read_json_file(students_data_dir / sid / f"{sid}.json")

    profile_dict = {}
    if profile_obj is not None:
        profile_dict = {
            "class_id": profile_obj.class_id or "",
            "score_total": profile_obj.score_total,
            "full_score_total": profile_obj.full_score_total,
            "score_rate": profile_obj.score_rate,
            "distinct_question_count": profile_obj.distinct_question_count,
            "available_question_count": profile_obj.available_question_count,
        }
    elif isinstance(student_json, dict) and isinstance(student_json.get("student"), dict):
        st = student_json["student"]
        profile_dict = {
            "class_id": st.get("class_id") or "",
            "score_total": to_float(st.get("score_total")),
            "full_score_total": to_float(st.get("full_score_total")),
            "score_rate": to_float(st.get("score_rate")),
            "distinct_question_count": to_int(st.get("distinct_question_count")),
            "available_question_count": to_int(st.get("available_question_count")),
        }

    if not dict_indicators:
        for row in read_csv_file(dataset_dir / "00_字典" / "指标字典.csv"):
            iid = (row.get("指标编号") or "").strip()
            if iid:
                dict_indicators.append(
                    {
                        "indicator_id": iid,
                        "indicator_name": (row.get("指标名称") or "").strip(),
                        "theme_name": (row.get("主题名称") or "").strip(),
                        "textbook_scope": (row.get("教材范围") or "").strip(),
                    }
                )

    if not raw_records and isinstance(student_json, dict):
        for rec in student_json.get("question_records") or []:
            qid = str(rec.get("question_id") or "").strip()
            if qid:
                raw_records.append(
                    {
                        "question_id": qid,
                        "exam_id": str(rec.get("exam_id") or "").strip(),
                        "indicator_id": str(rec.get("indicator_id") or "").strip(),
                        "score": to_float(rec.get("score")),
                        "full_score": to_float(rec.get("full_score")),
                    }
                )

    if not overview_rows and not profile_dict and not raw_records and not (students_data_dir / sid).exists():
        return None

    # 3. 动态汇总全部知识点（合并速览指标、指标字典与知识图谱新增知识点，绝不写死数量）
    graph_data = load_knowledge_graph()
    graph_nodes = graph_data.get("nodes") if isinstance(graph_data, dict) else []
    graph_by_id = {
        str(n.get("id") or "").strip(): n
        for n in (graph_nodes or [])
        if isinstance(n, dict) and str(n.get("id") or "").strip()
    }

    knowledge_points: list[dict] = []
    seen_ids: set[str] = set()
    seen_names: set[str] = set()

    for row in overview_rows:
        if str(row.get("行类型") or "").strip().lower() == "theme":
            continue
        ind_id = str(row.get("指标编号") or "").strip()
        raw_name = str(row.get("指标名称") or "").strip()
        g_node = graph_by_id.get(ind_id)
        display_name = (str(g_node.get("name") or "").strip() if g_node else "") or raw_name or ind_id
        theme_name = (
            (str(g_node.get("theme") or "").strip() if g_node else "")
            or str(row.get("主题名称") or "").strip()
        )

        score = to_float(row.get("得分"))
        full_score = to_float(row.get("满分"))
        has_record = score is not None and full_score is not None and full_score > 0
        score_rate = (
            round(score / full_score, 4)
            if has_record
            else to_float(row.get("得分率"))
        )
        done_count = to_int(row.get("做过不同题目")) or 0
        eligible_count = to_int(row.get("他能考到")) or 0

        knowledge_points.append(
            {
                "id": ind_id or display_name,
                "name": display_name,
                "theme_name": theme_name,
                "score": score,
                "full_score": full_score,
                "score_rate": score_rate,
                "done_count": done_count,
                "eligible_count": eligible_count,
                "has_record": has_record,
                "textbook_scope": str(row.get("教材范围") or "").strip(),
                "recommended_questions": _split_question_ids(row.get("可补练习题")),
            }
        )
        if ind_id:
            seen_ids.add(ind_id)
        if display_name:
            seen_names.add(display_name)
        if raw_name:
            seen_names.add(raw_name)

    # 补充指标字典中新增但尚未出现在旧速览表里的指标
    for d_ind in dict_indicators:
        iid = d_ind["indicator_id"]
        iname = d_ind["indicator_name"]
        if iid in seen_ids or (iname and iname in seen_names):
            continue
        g_node = graph_by_id.get(iid)
        display_name = (str(g_node.get("name") or "").strip() if g_node else "") or iname or iid
        knowledge_points.append(
            {
                "id": iid,
                "name": display_name,
                "theme_name": d_ind["theme_name"],
                "score": None,
                "full_score": None,
                "score_rate": None,
                "done_count": 0,
                "eligible_count": 0,
                "has_record": False,
                "textbook_scope": d_ind["textbook_scope"],
                "recommended_questions": [],
            }
        )
        seen_ids.add(iid)
        seen_names.add(display_name)

    # 补充教师在「知识图谱」中新创建的知识点节点
    for n in graph_nodes or []:
        if not isinstance(n, dict):
            continue
        nid = str(n.get("id") or "").strip()
        nname = str(n.get("name") or "").strip()
        if not nname or nid in seen_ids or nname in seen_names:
            continue
        knowledge_points.append(
            {
                "id": nid or nname,
                "name": nname,
                "theme_name": str(n.get("theme") or "").strip(),
                "score": None,
                "full_score": None,
                "score_rate": None,
                "done_count": 0,
                "eligible_count": 0,
                "has_record": False,
                "textbook_scope": "",
                "recommended_questions": [],
            }
        )
        if nid:
            seen_ids.add(nid)
        seen_names.add(nname)

    # 4. 计算总得分与总得分率
    scored_kps = [kp for kp in knowledge_points if kp["has_record"]]
    sum_score = round(sum(kp["score"] for kp in scored_kps), 2) if scored_kps else 0.0
    sum_full = round(sum(kp["full_score"] for kp in scored_kps), 2) if scored_kps else 0.0

    total_score = profile_dict.get("score_total")
    if total_score is None:
        total_score = sum_score
    total_full_score = profile_dict.get("full_score_total")
    if total_full_score is None:
        total_full_score = sum_full

    overall_score_rate = (
        round(float(total_score) / float(total_full_score), 4)
        if total_score is not None and total_full_score and float(total_full_score) > 0
        else profile_dict.get("score_rate")
    )

    done_questions = profile_dict.get("distinct_question_count")
    if done_questions is None:
        done_questions = sum(kp["done_count"] for kp in knowledge_points)
    available_questions = profile_dict.get("available_question_count")
    if available_questions is None:
        available_questions = sum(kp["eligible_count"] for kp in knowledge_points)

    # 5. 提取全部错题题号（score < full_score，去重并按题号自然排序，绝不截断）
    ind_name_lookup = {kp["id"]: kp["name"] for kp in knowledge_points}
    wrong_map: dict[str, dict] = {}
    for rec in raw_records:
        qid = rec["question_id"]
        score = to_float(rec.get("score"))
        full_score = to_float(rec.get("full_score"))
        if not qid or score is None or full_score is None or full_score <= 0:
            continue
        if score < full_score:
            wrong_map[qid] = {
                "question_id": qid,
                "exam_id": rec.get("exam_id") or "",
                "indicator_name": ind_name_lookup.get(rec.get("indicator_id") or "", ""),
                "score": score,
                "full_score": full_score,
            }

    wrong_questions = sorted(wrong_map.values(), key=lambda item: _question_sort_key(item["question_id"]))

    return {
        "student_id": sid,
        "class_id": profile_dict.get("class_id") or "",
        "overall": {
            "score": total_score,
            "full_score": total_full_score,
            "score_rate": overall_score_rate,
            "done_questions": done_questions,
            "available_questions": available_questions,
            "knowledge_point_count": len(knowledge_points),
            "wrong_question_count": len(wrong_questions),
        },
        "knowledge_points": knowledge_points,
        "wrong_questions": wrong_questions,
        "wrong_question_ids": [w["question_id"] for w in wrong_questions],
    }
