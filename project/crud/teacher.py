import asyncio
import json
from pathlib import Path
import sys

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

# 支持直接运行 python crud/teacher.py 手动建库建表并导入 00-04 数据
PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from config.db_conf import (  # noqa: E402
    ASYNC_DATABASE_URL,
    AsyncSessionLocal,
    DATASET_DIR,
    STUDENTS_DATA_DIR,
    async_engine,
)
from crud import users as users_crud  # noqa: E402
from models.dataset import (  # noqa: E402
    ClassIndicatorSummary,
    ClassStudentSummary,
    ClassThemeSummary,
    DictCurriculum,
    DictExam,
    DictIndicator,
    DictQuestion,
    QualityBenchmark,
    QualityChecklist,
    QualityExcludedRecord,
    QualityGradingSuspect,
    QualityMultiVersion,
    StudentOverview,
    StudentProfile,
    StudentQuestionRecord,
    ThemeStudentScore,
)
from models.users import Base  # noqa: E402
from utils.file_tools import read_csv_file, read_json_file, to_float, to_int  # noqa: E402


# 把 00_字典 ~ 04_质量与剔除 的数据全量写入 MySQL 数据库
async def sync_dataset_to_db(db: AsyncSession) -> dict:
    # 1. 先清空 00-04 旧数据
    models_to_clear = [
        DictIndicator,
        DictExam,
        DictCurriculum,
        DictQuestion,
        StudentProfile,
        StudentOverview,
        StudentQuestionRecord,
        ClassStudentSummary,
        ClassThemeSummary,
        ClassIndicatorSummary,
        ThemeStudentScore,
        QualityGradingSuspect,
        QualityMultiVersion,
        QualityExcludedRecord,
        QualityChecklist,
        QualityBenchmark,
    ]
    for model in models_to_clear:
        await db.execute(delete(model))

    counts = {}

    # 2. 导入 00_字典
    dir_00 = DATASET_DIR / "00_字典"

    rows = read_csv_file(dir_00 / "指标字典.csv")
    for r in rows:
        db.add(
            DictIndicator(
                indicator_id=r["指标编号"],
                indicator_name=r["指标名称"],
                theme_id=r["主题编号"],
                theme_name=r["主题名称"],
                curriculum_scope=r["课标范围"],
                textbook_scope=r["教材范围"],
                questions_in_bank=to_int(r["全库题数"]),
                question_ids=r["题号列表"],
            )
        )
    counts["dict_indicators"] = len(rows)

    rows = read_csv_file(dir_00 / "考试字典.csv")
    for r in rows:
        db.add(
            DictExam(
                exam_id=r["考试编号"],
                exam_date=r["考试日期"],
                taught_themes=r["已教主题"],
                available_questions=to_int(r["可用题数"]),
                description=r["说明"],
            )
        )
    counts["dict_exams"] = len(rows)

    rows = read_csv_file(dir_00 / "课标原文.csv")
    for r in rows:
        db.add(
            DictCurriculum(
                section_code=r["小节"],
                theme_id=r["主题"],
                section_title=r["课标小节"],
                clause_no=r["条目"],
                content=r["课标原文"],
                used_indicators=r["用于指标"],
                doc_page=r["文件页"],
                text_page=r["正文页"],
            )
        )
    counts["dict_curriculum"] = len(rows)

    rows = read_csv_file(dir_00 / "题目字典.csv")
    for r in rows:
        db.add(
            DictQuestion(
                material_id=r["材料编号"],
                material_type=r["材料类型"],
                theme_id=r["主题"],
                theme_name=r["主题名称"],
                indicator_id=r["指标"],
                indicator_name=r["指标名称"],
                question_type=r["题型"],
                full_score=to_float(r["满分"]),
                rubric_points=r["评分点"],
                reference_answer=r["参考答案"],
                source_file=r["来源文件"],
            )
        )
    counts["dict_questions"] = len(rows)

    # 3. 导入 01_按学生
    profile_count = 0
    overview_count = 0
    record_count = 0

    if STUDENTS_DATA_DIR.exists():
        for folder in sorted(STUDENTS_DATA_DIR.iterdir()):
            if not folder.is_dir():
                continue
            sid = folder.name

            ov_rows = read_csv_file(folder / f"{sid}_速览.csv")
            for r in ov_rows:
                db.add(
                    StudentOverview(
                        student_id=sid,
                        row_type=r["行类型"],
                        theme_id=r["主题编号"],
                        theme_name=r["主题名称"],
                        indicator_id=r["指标编号"],
                        indicator_name=r["指标名称"],
                        total_bank_count=to_int(r["全库题数"]),
                        eligible_count=to_int(r["他能考到"]),
                        done_count=to_int(r["做过不同题目"]),
                        threshold=to_int(r["判定线"]),
                        coverage_rate=to_float(r["覆盖率"]),
                        score=to_float(r["得分"]),
                        full_score=to_float(r["满分"]),
                        score_rate=to_float(r["得分率"]),
                        tier=r["档位"],
                        tier_note=r["档位说明"],
                        curriculum_scope=r["课标范围"],
                        textbook_scope=r["教材范围"],
                        recommended_questions=r["可补练习题"],
                    )
                )
            overview_count += len(ov_rows)

            data = read_json_file(folder / f"{sid}.json")
            if data:
                st = data.get("student") or {}
                if st:
                    db.add(
                        StudentProfile(
                            student_id=st.get("student_id", sid),
                            class_id=st.get("class_id"),
                            grade=to_int(st.get("grade")),
                            record_count=to_int(st.get("record_count")),
                            distinct_question_count=to_int(st.get("distinct_question_count")),
                            available_question_count=to_int(st.get("available_question_count")),
                            score_total=to_float(st.get("score_total")),
                            full_score_total=to_float(st.get("full_score_total")),
                            score_rate=to_float(st.get("score_rate")),
                            attended_exams=json.dumps(
                                st.get("attended_exams", []), ensure_ascii=False
                            ),
                        )
                    )
                    profile_count += 1

                for q in data.get("question_records", []):
                    db.add(
                        StudentQuestionRecord(
                            record_id=q.get("record_id"),
                            student_id=sid,
                            exam_id=q.get("exam_id"),
                            question_id=q.get("question_id"),
                            theme_id=q.get("theme_id"),
                            indicator_id=q.get("indicator_id"),
                            full_score=to_float(q.get("full_score")),
                            score=to_float(q.get("score")),
                            score_rate=to_float(q.get("score_rate")),
                            rubric_scores=q.get("rubric_scores"),
                            counted_in_denominator=1 if q.get("counted_in_denominator") else 0,
                            grading_flag=q.get("grading_flag"),
                        )
                    )
                    record_count += 1

    counts["student_profiles"] = profile_count
    counts["student_overview"] = overview_count
    counts["student_question_records"] = record_count

    # 4. 导入 02_按班级
    dir_02 = DATASET_DIR / "02_按班级"

    rows = read_csv_file(dir_02 / "班级总表.csv")
    for r in rows:
        theme_rates = {}
        for k, v in r.items():
            if k.endswith("得分率") and k != "得分率":
                theme_id = k.replace("得分率", "").strip()
                theme_rates[theme_id] = to_float(v)

        db.add(
            ClassStudentSummary(
                student_id=r["学生"],
                class_id=r["班级"],
                record_count=to_int(r["记录数"]),
                distinct_question_count=to_int(r["不同题目"]),
                available_question_count=to_int(r["他能考到"]),
                score=to_float(r["得分"]),
                full_score=to_float(r["满分"]),
                score_rate=to_float(r["得分率"]),
                theme_rates_json=json.dumps(theme_rates, ensure_ascii=False),
            )
        )
    counts["class_student_summary"] = len(rows)

    rows = read_csv_file(dir_02 / "班级_主题汇总.csv")
    for r in rows:
        db.add(
            ClassThemeSummary(
                group_name=r["群体"],
                student_count=to_int(r["人数"]),
                theme_id=r["主题"],
                theme_name=r["主题名称"],
                done_questions_total=to_int(r["做过题数合计"]),
                score=to_float(r["得分"]),
                full_score=to_float(r["满分"]),
                score_rate=to_float(r["得分率"]),
                recorded_students=to_int(r["有记录人数"]),
            )
        )
    counts["class_theme_summary"] = len(rows)

    rows = read_csv_file(dir_02 / "班级_指标汇总.csv")
    for r in rows:
        db.add(
            ClassIndicatorSummary(
                group_name=r["群体"],
                student_count=to_int(r["人数"]),
                theme_id=r["主题"],
                indicator_id=r["指标"],
                indicator_name=r["指标名称"],
                eligible_questions_total=to_int(r["可考题数合计"]),
                done_questions_total=to_int(r["做过题数合计"]),
                score=to_float(r["得分"]),
                full_score=to_float(r["满分"]),
                score_rate=to_float(r["得分率"]),
                recorded_students=to_int(r["有记录人数"]),
            )
        )
    counts["class_indicator_summary"] = len(rows)

    # 5. 导入 03_按主题
    dir_03 = DATASET_DIR / "03_按主题"
    theme_score_count = 0
    if dir_03.exists():
        for csv_file in sorted(dir_03.glob("*.csv")):
            parts = csv_file.stem.split("_", 1)
            theme_id = parts[0]
            theme_name = parts[1] if len(parts) > 1 else parts[0]
            t_rows = read_csv_file(csv_file)
            for r in t_rows:
                db.add(
                    ThemeStudentScore(
                        theme_id=theme_id,
                        theme_name=theme_name,
                        student_id=r["学生"],
                        class_id=r["班级"],
                        eligible_count=to_int(r["本主题可考"]),
                        done_count=to_int(r["做过"]),
                        score=to_float(r["得分"]),
                        full_score=to_float(r["满分"]),
                        score_rate=to_float(r["得分率"]),
                        ind1_rate=to_float(r.get("指标一得分率")),
                        ind2_rate=to_float(r.get("指标二得分率")),
                        ind3_rate=to_float(r.get("指标三得分率")),
                    )
                )
            theme_score_count += len(t_rows)
    counts["theme_student_scores"] = theme_score_count

    # 6. 导入 04_质量与剔除
    dir_04 = DATASET_DIR / "04_质量与剔除"

    rows = read_csv_file(dir_04 / "判分存疑.csv")
    for r in rows:
        db.add(
            QualityGradingSuspect(
                record_id=r["记录编号"],
                student_id=r["学生"],
                question_id=r["题目"],
                grading_flag=r["判分标记"],
                description=r["说明"],
            )
        )
    counts["quality_grading_suspects"] = len(rows)

    rows = read_csv_file(dir_04 / "多版本明细.csv")
    for r in rows:
        db.add(
            QualityMultiVersion(
                attempt_event=r["作答事件"],
                student_id=r["学生"],
                question_id=r["题目"],
                revision=to_int(r["修订版本"]),
                grading_status=r["评分状态"],
                score=to_float(r["得分"]),
                is_adopted=r["是否采用"],
            )
        )
    counts["quality_multi_versions"] = len(rows)

    rows = read_csv_file(dir_04 / "被剔除记录.csv")
    for r in rows:
        db.add(
            QualityExcludedRecord(
                record_id=r["记录编号"],
                student_id=r["学生"],
                question_id=r["题目"],
                exam_id=r["考试"],
                revision=to_int(r["修订版本"]),
                grading_status=r["评分状态"],
                score=to_float(r["得分"]),
                full_score=to_float(r["满分"]),
                exclude_reason=r["剔除原因"],
            )
        )
    counts["quality_excluded_records"] = len(rows)

    rows = read_csv_file(dir_04 / "质量检查清单.csv")
    for r in rows:
        db.add(
            QualityChecklist(
                issue_code=r["问题代码"],
                severity=r["严重程度"],
                record_count=to_int(r["记录数"]),
                sample_records=r["样例记录"],
                description=r["说明"],
                handling=r["处置"],
                affects_denominator=r["影响分母"],
            )
        )
    counts["quality_checklist"] = len(rows)

    bench = read_json_file(dir_04 / "基准数字.json") or {}
    bench_items = bench.get("数字", [])
    for item in bench_items:
        db.add(
            QualityBenchmark(
                name=str(item["name"]),
                expected=str(item.get("expected", "")),
                actual=str(item.get("actual", "")),
                unit=str(item.get("unit", "")),
                description=str(item.get("description", "")),
                source=str(item.get("source", "")),
            )
        )
    counts["quality_benchmarks"] = len(bench_items)

    await db.commit()

    # 7. 同步学生文件夹账号到 users 表
    counts["users"] = await users_crud.sync_users_from_folders(db)
    return counts


# 从 CSV 兜底组装教师端展示数据（当 MySQL 尚未启动或没数据时使用）
def get_teacher_overview_from_csv() -> dict:
    themes = []
    student_theme_map = {}

    dir_03 = DATASET_DIR / "03_按主题"
    if dir_03.exists():
        for csv_file in sorted(dir_03.glob("*.csv")):
            parts = csv_file.stem.split("_", 1)
            tid = parts[0]
            tname = parts[1] if len(parts) > 1 else parts[0]
            themes.append({"theme_id": tid, "theme_name": tname})

            for r in read_csv_file(csv_file):
                sid = r["学生"].strip()
                score = to_float(r["得分"])
                full = to_float(r["满分"])
                rate = round(score / full, 4) if score is not None and full else to_float(r["得分率"])
                student_theme_map.setdefault(sid, {})[tid] = {
                    "score": score,
                    "full_score": full,
                    "rate": rate,
                }

    students = []
    class_members = {}
    for r in read_csv_file(DATASET_DIR / "02_按班级" / "班级总表.csv"):
        sid = r["学生"].strip()
        cid = r["班级"].strip()
        total_score = to_float(r["得分"])
        total_full = to_float(r["满分"])
        total_rate = (
            round(total_score / total_full, 4)
            if total_score is not None and total_full
            else to_float(r["得分率"])
        )
        item = {
            "id": sid,
            "class_name": cid,
            "total_score": total_score,
            "total_full_score": total_full,
            "total_rate": total_rate,
            "theme_scores": student_theme_map.get(sid, {}),
        }
        students.append(item)
        class_members.setdefault(cid, []).append(item)

    class_theme_map = {}
    for r in read_csv_file(DATASET_DIR / "02_按班级" / "班级_主题汇总.csv"):
        group = r["群体"].strip()
        if group == "全年级":
            continue
        score = to_float(r["得分"])
        full = to_float(r["满分"])
        rate = round(score / full, 4) if score is not None and full else to_float(r["得分率"])
        class_theme_map.setdefault(group, []).append(
            {
                "theme_id": r["主题"].strip(),
                "theme_name": r["主题名称"].strip(),
                "score": score,
                "full_score": full,
                "rate": rate,
            }
        )

    classes = []
    for cid, members in class_members.items():
        scores = [m["total_score"] for m in members if m["total_score"] is not None]
        fulls = [m["total_full_score"] for m in members if m["total_full_score"] is not None]
        avg_score = round(sum(scores) / len(scores), 2) if scores else None
        avg_rate = round(sum(scores) / sum(fulls), 4) if sum(fulls) > 0 else None

        c_themes = class_theme_map.get(cid, [])
        valid_themes = [t for t in c_themes if t["rate"] is not None]
        lowest_theme = min(valid_themes, key=lambda t: t["rate"]) if valid_themes else None

        classes.append(
            {
                "class_name": cid,
                "student_count": len(members),
                "avg_score": avg_score,
                "avg_rate": avg_rate,
                "lowest_theme": lowest_theme,
                "themes": c_themes,
            }
        )

    return {"themes": themes, "classes": classes, "students": students}


# 从 MySQL 读取教师首页和数据详情页的数据（读不到自动走 CSV 兜底）
async def get_teacher_overview(db: AsyncSession) -> dict:
    try:
        stmt1 = select(ClassStudentSummary).order_by(ClassStudentSummary.student_id)
        student_rows = (await db.execute(stmt1)).scalars().all()
        if not student_rows:
            return get_teacher_overview_from_csv()

        stmt2 = select(ThemeStudentScore).order_by(
            ThemeStudentScore.theme_id, ThemeStudentScore.student_id
        )
        theme_score_rows = (await db.execute(stmt2)).scalars().all()

        stmt3 = select(ClassThemeSummary).order_by(
            ClassThemeSummary.group_name, ClassThemeSummary.theme_id
        )
        class_theme_rows = (await db.execute(stmt3)).scalars().all()

        # 整理主题列表与学生各主题得分
        themes_dict = {}
        student_theme_map = {}
        for row in theme_score_rows:
            themes_dict[row.theme_id] = row.theme_name
            student_theme_map.setdefault(row.student_id, {})[row.theme_id] = {
                "score": row.score,
                "full_score": row.full_score,
                "rate": row.score_rate,
            }
        themes = [{"theme_id": tid, "theme_name": tname} for tid, tname in sorted(themes_dict.items())]

        # 整理学生总分和各主题得分
        students = []
        class_members = {}
        for row in student_rows:
            item = {
                "id": row.student_id,
                "class_name": row.class_id,
                "total_score": row.score,
                "total_full_score": row.full_score,
                "total_rate": row.score_rate,
                "theme_scores": student_theme_map.get(row.student_id, {}),
            }
            students.append(item)
            class_members.setdefault(row.class_id, []).append(item)

        # 整理每个班的平均分和总得分率最低主题
        class_theme_map = {}
        for row in class_theme_rows:
            if row.group_name == "全年级":
                continue
            class_theme_map.setdefault(row.group_name, []).append(
                {
                    "theme_id": row.theme_id,
                    "theme_name": row.theme_name,
                    "score": row.score,
                    "full_score": row.full_score,
                    "rate": row.score_rate,
                }
            )

        classes = []
        for cid, members in class_members.items():
            scores = [m["total_score"] for m in members if m["total_score"] is not None]
            fulls = [m["total_full_score"] for m in members if m["total_full_score"] is not None]
            avg_score = round(sum(scores) / len(scores), 2) if scores else None
            avg_rate = round(sum(scores) / sum(fulls), 4) if sum(fulls) > 0 else None

            c_themes = class_theme_map.get(cid, [])
            valid_themes = [t for t in c_themes if t["rate"] is not None]
            lowest_theme = min(valid_themes, key=lambda t: t["rate"]) if valid_themes else None

            classes.append(
                {
                    "class_name": cid,
                    "student_count": len(members),
                    "avg_score": avg_score,
                    "avg_rate": avg_rate,
                    "lowest_theme": lowest_theme,
                    "themes": c_themes,
                }
            )

        return {"themes": themes, "classes": classes, "students": students}
    except Exception:
        return get_teacher_overview_from_csv()


# 建表 + 同步 00-04 数据和学生账号（前提：已在 MySQL 手动建好 zjhx_teaching 库）
async def init_db_and_sync() -> dict:
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        return await sync_dataset_to_db(session)


if __name__ == "__main__":
    print("连接数据库:", ASYNC_DATABASE_URL)
    summary = asyncio.run(init_db_and_sync())
    print("建库建表并导入 00-04 数据完成:")
    for table_name, count in summary.items():
        print(f"  {table_name}: {count} 行")
