import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import dataset_dir, students_data_dir
from models.dataset import DictIndicator, DictQuestion, StudentOverview, StudentQuestionRecord
from utils.file_tools import read_csv_file, read_json_file, to_float, to_int


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
