from typing import Optional

from sqlalchemy import Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.users import Base


# ==================== 00_字典 ====================
class DictIndicator(Base):
    __tablename__ = "dict_indicators"

    indicator_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    indicator_name: Mapped[str] = mapped_column(String(255), nullable=False)
    theme_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    theme_name: Mapped[str] = mapped_column(String(128), nullable=False)
    curriculum_scope: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    textbook_scope: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    questions_in_bank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    question_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class DictExam(Base):
    __tablename__ = "dict_exams"

    exam_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    exam_date: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    taught_themes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    available_questions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class DictCurriculum(Base):
    __tablename__ = "dict_curriculum"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    section_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    theme_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    section_title: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    clause_no: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    used_indicators: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    doc_page: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    text_page: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)


class DictQuestion(Base):
    __tablename__ = "dict_questions"

    material_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    material_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    theme_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    theme_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    indicator_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    indicator_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    question_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    full_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rubric_points: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reference_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_file: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)


# ==================== 01_按学生 ====================
class StudentProfile(Base):
    __tablename__ = "student_profiles"

    student_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    class_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    grade: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    record_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    distinct_question_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    available_question_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    score_total: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    full_score_total: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    score_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    attended_exams: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class StudentOverview(Base):
    __tablename__ = "student_overview"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    row_type: Mapped[str] = mapped_column(String(32), nullable=False)
    theme_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    theme_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    indicator_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    indicator_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    total_bank_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    eligible_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    done_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    threshold: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    coverage_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    full_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    score_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tier: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    tier_note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    curriculum_scope: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    textbook_scope: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    recommended_questions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class StudentQuestionRecord(Base):
    __tablename__ = "student_question_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    student_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    exam_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    question_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    theme_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    indicator_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    full_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    score_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rubric_scores: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    counted_in_denominator: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    grading_flag: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


# ==================== 02_按班级 ====================
class ClassStudentSummary(Base):
    __tablename__ = "class_student_summary"

    student_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    class_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    record_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    distinct_question_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    available_question_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    full_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    score_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    theme_rates_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ClassThemeSummary(Base):
    __tablename__ = "class_theme_summary"
    __table_args__ = (Index("idx_cts_group_theme", "group_name", "theme_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_name: Mapped[str] = mapped_column(String(64), nullable=False)
    student_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    theme_id: Mapped[str] = mapped_column(String(32), nullable=False)
    theme_name: Mapped[str] = mapped_column(String(128), nullable=False)
    done_questions_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    full_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    score_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recorded_students: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class ClassIndicatorSummary(Base):
    __tablename__ = "class_indicator_summary"
    __table_args__ = (Index("idx_cis_group_ind", "group_name", "indicator_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_name: Mapped[str] = mapped_column(String(64), nullable=False)
    student_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    theme_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    indicator_id: Mapped[str] = mapped_column(String(32), nullable=False)
    indicator_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    eligible_questions_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    done_questions_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    full_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    score_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recorded_students: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


# ==================== 03_按主题 ====================
class ThemeStudentScore(Base):
    __tablename__ = "theme_student_scores"
    __table_args__ = (UniqueConstraint("theme_id", "student_id", name="uk_tss_theme_student"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    theme_id: Mapped[str] = mapped_column(String(32), nullable=False)
    theme_name: Mapped[str] = mapped_column(String(128), nullable=False)
    student_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    class_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    eligible_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    done_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    full_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    score_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ind1_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ind2_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ind3_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


# ==================== 04_质量与剔除 ====================
class QualityGradingSuspect(Base):
    __tablename__ = "quality_grading_suspects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    student_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    question_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    grading_flag: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class QualityMultiVersion(Base):
    __tablename__ = "quality_multi_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attempt_event: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    student_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    question_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    revision: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    grading_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_adopted: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)


class QualityExcludedRecord(Base):
    __tablename__ = "quality_excluded_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    student_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    question_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    exam_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    revision: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    grading_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    full_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    exclude_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class QualityChecklist(Base):
    __tablename__ = "quality_checklist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    severity: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    record_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sample_records: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    handling: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    affects_denominator: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)


class QualityBenchmark(Base):
    __tablename__ = "quality_benchmarks"

    name: Mapped[str] = mapped_column(String(128), primary_key=True)
    expected: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    actual: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
