from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import students_data_dir
from models.dataset import StudentOverview
from utils.file_tools import read_csv_file


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
