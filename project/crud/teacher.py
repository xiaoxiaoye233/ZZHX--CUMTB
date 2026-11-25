import asyncio
import json
from pathlib import Path
import sys

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

# 支持直接运行 python crud/teacher.py 手动建库建表并导入 00-04 数据
PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from config.db_conf import (  # noqa: E402
    async_database_url,
    AsyncSessionLocal,
    dataset_dir,
    mysql_database,
    mysql_host,
    mysql_port,
    mysql_user,
    raw_mysql_password,
    students_data_dir,
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
    dir_00 = dataset_dir / "00_字典"

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

    if students_data_dir.exists():
        for folder in sorted(students_data_dir.iterdir()):
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
    dir_02 = dataset_dir / "02_按班级"

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
    dir_03 = dataset_dir / "03_按主题"
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
    dir_04 = dataset_dir / "04_质量与剔除"

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

    # 学情和学生账号在同一个事务中提交。
    counts["users"] = await users_crud.sync_users_from_folders(db)
    await db.commit()
    return counts


# 从 CSV 兜底组装教师端展示数据（当 MySQL 尚未启动或没数据时使用）
def get_teacher_overview_from_csv() -> dict:
    themes = []
    student_theme_map = {}

    dir_03 = dataset_dir / "03_按主题"
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
    for r in read_csv_file(dataset_dir / "02_按班级" / "班级总表.csv"):
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
    for r in read_csv_file(dataset_dir / "02_按班级" / "班级_主题汇总.csv"):
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


def get_class_report_card_from_files(class_id: str | None) -> dict | None:
    """当 MySQL 未启动时，从本地 01_按学生 目录兜底组装班级成绩单。"""
    if not students_data_dir.is_dir():
        return {"classes": [], "class_id": None, "questions": [], "students": []}

    class_set: set[str] = set()
    student_blobs: list[dict] = []
    for folder in sorted(students_data_dir.iterdir()):
        if not folder.is_dir():
            continue
        data = read_json_file(folder / f"{folder.name}.json")
        if not isinstance(data, dict) or not isinstance(data.get("student"), dict):
            continue
        st = data["student"]
        cid = str(st.get("class_id") or "").strip()
        if cid:
            class_set.add(cid)
            student_blobs.append(data)

    classes = sorted(class_set)
    if class_id is not None and class_id not in classes:
        return None
    if not classes:
        return {"classes": [], "class_id": None, "questions": [], "students": []}

    selected_class = class_id or classes[0]
    questions: set[tuple[str, str]] = set()
    rows: dict[str, tuple[float | None, dict[tuple[str, str], float]]] = {}

    for blob in student_blobs:
        st = blob["student"]
        if str(st.get("class_id") or "").strip() != selected_class:
            continue
        sid = str(st.get("student_id") or "").strip()
        total = to_float(st.get("score_total"))
        scores: dict[tuple[str, str], float] = {}
        for rec in blob.get("question_records") or []:
            qid = str(rec.get("question_id") or "").strip()
            sc = to_float(rec.get("score"))
            if not qid or sc is None:
                continue
            key = (str(rec.get("exam_id") or "").strip(), qid)
            questions.add(key)
            scores[key] = scores.get(key, 0.0) + sc
        rows[sid] = (total, scores)

    columns = sorted(questions)
    return {
        "classes": classes,
        "class_id": selected_class,
        "questions": [{"exam_id": eid, "question_id": qid} for eid, qid in columns],
        "students": [
            {
                "student_id": sid,
                "total_score": total,
                "scores": [scores.get(key) for key in columns],
            }
            for sid, (total, scores) in sorted(rows.items())
        ],
    }


async def get_class_report_card(db: AsyncSession, class_id: str | None) -> dict | None:
    try:
        profile = StudentProfile
        record = StudentQuestionRecord
        class_query = (
            select(profile.class_id)
            .where(profile.class_id.is_not(None), profile.class_id != "")
            .distinct()
            .order_by(profile.class_id)
        )
        classes = list((await db.scalars(class_query)).all())
        if not classes:
            return get_class_report_card_from_files(class_id)
        if class_id is not None and class_id not in classes:
            return None
        selected_class = class_id or classes[0]

        # 从班级名册出发，确保没有有效作答记录的学生也出现在成绩单上。
        score_query = (
            select(profile.student_id, profile.score_total, record.exam_id, record.question_id, record.score)
            .select_from(profile)
            .outerjoin(record, and_(
                record.student_id == profile.student_id,
                record.question_id.is_not(None),
                record.question_id != "",
                record.score.is_not(None),
            ))
            .where(profile.class_id == selected_class)
            .order_by(profile.student_id)
        )
        questions = set()
        rows = {}
        for student_id, total_score, exam_id, question_id, score in await db.execute(score_query):
            total, scores = rows.setdefault(student_id, (total_score, {}))
            if question_id is not None:
                key = (exam_id or "", question_id)
                questions.add(key)
                scores[key] = scores.get(key, 0) + score

        columns = sorted(questions)
        return {
            "classes": classes,
            "class_id": selected_class,
            "questions": [{"exam_id": exam_id, "question_id": question_id} for exam_id, question_id in columns],
            "students": [
                {
                    "student_id": student_id,
                    "total_score": total,
                    "scores": [scores.get(key) for key in columns],
                }
                for student_id, (total, scores) in rows.items()
            ],
        }
    except Exception:
        if db.in_transaction():
            await db.rollback()
        return get_class_report_card_from_files(class_id)


def _format_teacher_tasks_rows(raw_rows: list[dict], ind_meta: dict[str, dict]) -> dict:
    groups_order: list[str] = []
    by_class: dict[str, list[dict]] = {}
    group_counts: dict[str, int] = {}

    for row in raw_rows:
        group = str(row.get("group_name") or "").strip()
        ind_id = str(row.get("indicator_id") or "").strip()
        if not group or not ind_id:
            continue
        if group not in by_class:
            groups_order.append(group)
            by_class[group] = []
        if row.get("student_count") is not None:
            group_counts[group] = int(row["student_count"])

        meta = ind_meta.get(ind_id, {})
        by_class[group].append(
            {
                "indicator_id": ind_id,
                "indicator_name": row.get("indicator_name") or meta.get("indicator_name") or ind_id,
                "theme_id": row.get("theme_id") or meta.get("theme_id") or "",
                "theme_name": meta.get("theme_name") or row.get("theme_id") or "",
                "textbook_scope": meta.get("textbook_scope") or "",
                "questions_in_bank": meta.get("questions_in_bank"),
                "student_count": row.get("student_count"),
                "recorded_students": row.get("recorded_students"),
                "eligible_questions_total": row.get("eligible_questions_total"),
                "done_questions_total": row.get("done_questions_total"),
                "score": row.get("score"),
                "full_score": row.get("full_score"),
                "score_rate": row.get("score_rate"),
            }
        )

    # 让「全年级」排在最前面作为“全部班级”，其余班级按名称排序
    sorted_groups = sorted(
        groups_order,
        key=lambda g: (0 if g == "全年级" else 1, g),
    )
    classes = [
        {
            "key": g,
            "label": "全部班级" if g == "全年级" else f"{g} 班",
            "student_count": group_counts.get(g, 0),
        }
        for g in sorted_groups
    ]
    return {"classes": classes, "by_class": by_class}


def get_teacher_tasks_from_csv() -> dict:
    ind_meta: dict[str, dict] = {}
    for row in read_csv_file(dataset_dir / "00_字典" / "指标字典.csv"):
        iid = row.get("指标编号", "").strip()
        if iid:
            ind_meta[iid] = {
                "indicator_name": row.get("指标名称", "").strip(),
                "theme_id": row.get("主题编号", "").strip(),
                "theme_name": row.get("主题名称", "").strip(),
                "textbook_scope": row.get("教材范围", "").strip(),
                "questions_in_bank": to_int(row.get("全库题数")),
            }

    raw_rows = []
    for row in read_csv_file(dataset_dir / "02_按班级" / "班级_指标汇总.csv"):
        raw_rows.append(
            {
                "group_name": row.get("群体", "").strip(),
                "student_count": to_int(row.get("人数")),
                "theme_id": row.get("主题", "").strip(),
                "indicator_id": row.get("指标", "").strip(),
                "indicator_name": row.get("指标名称", "").strip(),
                "eligible_questions_total": to_int(row.get("可考题数合计")),
                "done_questions_total": to_int(row.get("做过题数合计")),
                "score": to_float(row.get("得分")),
                "full_score": to_float(row.get("满分")),
                "score_rate": to_float(row.get("得分率")),
                "recorded_students": to_int(row.get("有记录人数")),
            }
        )
    return _format_teacher_tasks_rows(raw_rows, ind_meta)


async def get_teacher_tasks(db: AsyncSession) -> dict:
    try:
        ind_rows = (await db.execute(select(DictIndicator))).scalars().all()
        ind_meta = {
            r.indicator_id: {
                "indicator_name": r.indicator_name,
                "theme_id": r.theme_id,
                "theme_name": r.theme_name,
                "textbook_scope": r.textbook_scope or "",
                "questions_in_bank": r.questions_in_bank,
            }
            for r in ind_rows
        }
        summary_rows = (
            await db.execute(
                select(ClassIndicatorSummary).order_by(
                    ClassIndicatorSummary.group_name, ClassIndicatorSummary.indicator_id
                )
            )
        ).scalars().all()
        if not summary_rows:
            return get_teacher_tasks_from_csv()

        raw_rows = [
            {
                "group_name": r.group_name,
                "student_count": r.student_count,
                "theme_id": r.theme_id,
                "indicator_id": r.indicator_id,
                "indicator_name": r.indicator_name,
                "eligible_questions_total": r.eligible_questions_total,
                "done_questions_total": r.done_questions_total,
                "score": r.score,
                "full_score": r.full_score,
                "score_rate": r.score_rate,
                "recorded_students": r.recorded_students,
            }
            for r in summary_rows
        ]
        return _format_teacher_tasks_rows(raw_rows, ind_meta)
    except Exception:
        return get_teacher_tasks_from_csv()


def _ensure_database_exists() -> None:
    import pymysql

    with pymysql.connect(
        host=mysql_host,
        port=mysql_port,
        user=mysql_user,
        password=raw_mysql_password,
        charset="utf8mb4",
        connect_timeout=2,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{mysql_database}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()


# 自动建库 + 建表 + 同步 00-04 数据和学生账号
async def init_db_and_sync() -> dict:
    await asyncio.to_thread(_ensure_database_exists)
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        return await sync_dataset_to_db(session)


if __name__ == "__main__":
    print("连接数据库:", async_database_url)
    summary = asyncio.run(init_db_and_sync())
    print("建库建表并导入 00-04 数据完成:")
    for table_name, count in summary.items():
        print(f"  {table_name}: {count} 行")
