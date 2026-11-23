from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import STUDENTS_DATA_DIR
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


# 查询某个学生的速览表（优先查 MySQL，查不到时读本地 CSV 兜底）
async def get_student_overview_rows(db: AsyncSession, student_id: str) -> list[dict]:
    try:
        stmt = (
            select(StudentOverview)
            .where(StudentOverview.student_id == student_id)
            .order_by(StudentOverview.id)
        )
        result = await db.execute(stmt)
        db_rows = result.scalars().all()
        if db_rows:
            return [_model_to_row_dict(r) for r in db_rows]
    except Exception:
        pass

    csv_path = STUDENTS_DATA_DIR / student_id / f"{student_id}_速览.csv"
    return read_csv_file(csv_path)


# 根据学生速览数据生成个性化建议（后续接入大模型时替换这里即可）
def build_student_advice(student_id: str, rows: list[dict]) -> str:
    total_score = 0.0
    total_full = 0.0
    weak_list = []
    unanswered_list = []

    for r in rows:
        if r.get("行类型") == "theme":
            continue
        score = r.get("得分")
        full = r.get("满分")
        if score is not None and score != "" and full is not None and full != "":
            s = float(score)
            f = float(full)
            total_score += s
            total_full += f
            if f > 0 and s / f < 0.6:
                weak_list.append((s / f, r))
        else:
            unanswered_list.append(r)

    rate_pct = round(total_score / total_full * 100, 1) if total_full > 0 else 0
    lines = [
        f"你好（学号 {student_id}），当前总得分 {total_score:g}/{total_full:g} 分（总得分率 {rate_pct}%），以下是为你生成的个性化学习建议："
    ]

    weak_list.sort(key=lambda item: item[0])
    if weak_list:
        lines.append("\n1. 优先巩固薄弱知识点：")
        for rate, r in weak_list[:3]:
            practice = r.get("可补练习题") or ""
            extra = f"，可补练：{practice}" if practice else ""
            lines.append(
                f"• 【{r.get('主题名称')}】{r.get('指标名称')}（{r.get('得分')}/{r.get('满分')} 分，得分率 {round(rate * 100, 1)}%，教材 {r.get('教材范围') or '对应章节'}）{extra}"
            )

    if unanswered_list:
        first = unanswered_list[0]
        lines.append(
            f"\n2. 未作答知识点：还有 {len(unanswered_list)} 项暂未作答（如「{first.get('主题名称')} · {first.get('指标名称')}」），建议先补做对应练习题。"
        )

    lines.append("\n3. 如果哪道题不会做，直接在下方问我即可。")
    return "\n".join(lines)
