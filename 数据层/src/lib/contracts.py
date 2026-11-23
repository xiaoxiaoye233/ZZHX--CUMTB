"""契约层：与数据集字段（dataset/数据字典.md）对应的 Pydantic 模型。

规则：
- 本文件不含任何计算逻辑，只定义"数据长什么样"。
- 只有 F 层（事实）与 T 层（工具出入参）；卡片层、证据单、学习建议这些结论层已撤出。
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

# ---------- 枚举（字段表 §4） ----------

ConclusionLevel = Literal["证据充足", "证据偏少", "证据不足"]
# 证据强度按"有效不同题目数"分档（口径卡 R5）：>=15 充足 / 8-14 偏少 / <8 不足
EvidenceStrength = Literal["充足", "偏少", "不足"]
ReasonCode = Literal[
    "not_taught",
    "not_in_scope",
    "no_attempt",
    "evidence_short",
    "pending_score",
    "cross_node_dup",
]
# 教学覆盖按"指标级"判定（口径卡 R10）：节点表只给到主题级，主题级不足以说明某个指标教没教。
# 部分教到 = 该节点只覆盖了这个指标的一部分情形（N01 只涉及一元一次方程的列式，不涉及方程组）。
# 未提供 = 这一场既没有手写记录、也没出过这个指标的题，推断不出来；不声称"未教"，也不声称"已教"。
TeachingStatus = Literal["已教", "部分教到", "未教", "未提供"]
ScoringStatus = Literal["已评分", "待评分", "未作答"]
# 判分可靠性（口径卡 R8）：只标注，绝不改分；现在写进数据集的 判分存疑.csv 与 grading_flag 字段
GradingReliability = Literal[
    "正常", "答案一致但判0", "总分与分项不符", "得分超满分", "已改判"
]


# ---------- F 层 ----------

class ThemeLevel(BaseModel):
    theme_identifier: str
    theme_display_name: str
    distinct_attempted_question_count: int
    earned_score_total: int = 0
    attempted_full_score_total: int = 0
    theme_correct_score_rate: Optional[float] = None
    conclusion_level: ConclusionLevel
    # 主题级判定线固定 3 道不同题（facts.THEME_THRESHOLD）；写出来是为了页面能显示"做了 2 道、要 3 道"
    evidence_threshold: int = 3


class ExamNodeIndicatorRecord(BaseModel):
    """同一个指标在"某一场考试"里的表现（口径卡 R10）。

    存在的理由：只给合计会让读者看不出"这场抽了几道题、他答得怎么样"，
    也无法区分"没参加这场考试"与"参加了但一道没做"。结论仍只看合计，
    这张表只做解释与下钻。
    """

    node_identifier: str
    node_date_text: str
    student_participated_flag: bool
    questions_available_in_node: int
    distinct_attempted_count: int
    attempt_event_count: int
    earned_score_total: int = 0
    attempted_full_score: int = 0
    correct_score_rate: Optional[float] = None
    teaching_status_in_node: TeachingStatus
    repeated_question_identifiers: list[str] = Field(default_factory=list)
    plain_language_note_text: str


class IndicatorLevel(BaseModel):
    indicator_identifier: str
    indicator_description_text: str
    total_question_count_for_indicator: int
    # 该生实际能考到的该指标题数（他参加过的所有考试的并集，去重）——门槛与分母都按它封顶
    available_question_count: int = 0
    evidence_threshold_for_conclusion: int
    distinct_attempted_count: int
    counted_evidence_record_count: int
    earned_score_total: int = 0
    attempted_full_score: int = 0
    indicator_correct_score_rate: Optional[float] = None
    conclusion_level: ConclusionLevel
    insufficiency_reason_code: Optional[ReasonCode] = None
    teaching_covered_status: TeachingStatus
    supporting_record_identifiers: list[str] = Field(default_factory=list)
    exam_node_record_list: list[ExamNodeIndicatorRecord] = Field(default_factory=list)


class ClassThemeOverview(BaseModel):
    theme_identifier: str
    theme_display_name: str
    student_count_with_evidence: int
    class_correct_score_rate: float


class ClassIndicatorOverview(BaseModel):
    indicator_identifier: str
    indicator_description_text: str
    student_count_determined: int
    student_count_tendency: int
    student_count_unobserved: int
    class_distinct_attempted_count: int
    class_correct_score_rate: float


class FollowupTask(BaseModel):
    followup_task_identifier: str
    target_indicator_identifier: str
    suggested_question_identifiers: list[str]
    current_conclusion_level: ConclusionLevel
    target_conclusion_level: ConclusionLevel
    requires_all_correct_flag: bool


class StudentFacts(BaseModel):
    student_identifier: str
    class_identifier: str
    grade_level: int
    valid_record_count: int
    distinct_attempted_question_count: int
    available_question_count: int
    attempted_question_coverage_ratio: float
    coverage_plain_language_text: str
    correct_score_rate: float
    earned_score_total: int
    attempted_full_score_total: int
    evidence_strength_level: EvidenceStrength
    theme_level_summary_list: list[ThemeLevel]
    indicator_level_detail_list: list[IndicatorLevel]
    data_quality_flags: list[str] = Field(default_factory=list)
    attended_node_identifiers: list[str] = Field(default_factory=list)
    # 他参加过的考试里出现过的题目（R10 的"能考到"）：只在这里算一次，别处只读
    available_question_identifiers: list[str] = Field(default_factory=list)


class ClassFacts(BaseModel):
    class_identifier: str
    student_count: int
    valid_record_count: int
    class_correct_score_rate: float
    conclusion_level_distribution: dict[str, int]
    indicator_level_overview_list: list[ClassIndicatorOverview]
    theme_level_overview_list: list[ClassThemeOverview]
    priority_attention_student_list: list[str] = Field(default_factory=list)


# ---------- T 层：工具出入参（给 LLM / 后端用，不含任何措辞） ----------

class ToolMeta(BaseModel):
    """每次工具返回都带上的血缘信息，用于"这个数怎么来的"当场回答。"""

    tool_name: str
    argument_summary_text: str
    result_count: int
    data_source_file_list: list[str] = Field(default_factory=list)
    computation_note_text: str = ""


class EvidenceItem(BaseModel):
    """一条可引用的作答证据。跟 RecordFact 的区别：只保留"支撑结论"需要的字段，且标明是否计入判定。"""

    record_identifier: str
    student_identifier: str
    question_identifier: str
    indicator_identifier: str
    theme_identifier: str
    node_identifier: str
    earned_score: int
    full_score: int
    student_final_answer_text: str = ""
    rubric_point_scores: list[tuple[str, str, int, int]] = Field(default_factory=list)
    grading_reliability: GradingReliability = "正常"
    grading_note_text: str = ""
    counted_for_conclusion: bool = True


class CandidateMaterial(BaseModel):
    """一道候选材料（只收真实题目 Qxxx；学习卡与教材条目不进候选池）。"""

    material_identifier: str
    indicator_identifier: str
    theme_identifier: str
    question_type: str
    full_score: int
    stem_excerpt_text: str
    reference_answer_text: str = ""
    already_attempted_by_target_student: bool = False
    source_or_file_text: str = ""


class StudentToolResult(BaseModel):
    tool_meta: ToolMeta
    student_facts: StudentFacts
    evidence_sheet_identifier: str
    # 按问题筛过时，这里是筛掉的维度，方便调用方说明"只给了 T02 三行"
    filtered_by_text: str = ""


class GroupToolResult(BaseModel):
    tool_meta: ToolMeta
    group_facts: ClassFacts
    weakest_theme_identifiers: list[str] = Field(default_factory=list)
    weakest_indicator_identifiers: list[str] = Field(default_factory=list)


class EvidenceToolResult(BaseModel):
    tool_meta: ToolMeta
    student_identifier: str
    indicator_identifier: str
    evidence_item_list: list[EvidenceItem]
    grading_caveat_text: str = ""


class CandidateToolResult(BaseModel):
    tool_meta: ToolMeta
    indicator_identifier: str
    exclude_student_identifier: Optional[str] = None
    candidate_material_list: list[CandidateMaterial]


class ToolDescriptor(BaseModel):
    """给前端与 langchain 队友看的工具声明，不参与计算。"""

    tool_name: str
    one_line_purpose_text: str
    parameter_schema_text: str
    return_contract_name: str
    when_to_call_text: str
    when_not_to_call_text: str = ""
    is_mutating: bool = False


class ClassIndicatorStudentRow(BaseModel):
    """班级下钻到指标后，某个学生在这一格上的情况（前端画"三堆人"用）。"""

    student_identifier: str
    class_identifier: str
    conclusion_level: ConclusionLevel
    earned_score: int
    full_score: int
    correct_score_rate: Optional[float] = None
    distinct_attempted_count: int
    insufficiency_reason_code: Optional[ReasonCode] = None
    record_identifiers: list[str] = Field(default_factory=list)
    one_line_hint_text: str = ""


class ClassIndicatorDetailResult(BaseModel):
    """班级 × 指标 的下钻结果：一个格子里到底是谁、为什么、还差多少。"""

    tool_meta: ToolMeta
    class_identifier: str
    indicator_identifier: str
    indicator_description_text: str
    theme_identifier: str
    class_earned_score_total: int
    class_attempted_full_score_total: int
    class_correct_score_rate: Optional[float] = None
    student_count_determined: int
    student_count_tendency: int
    student_count_unobserved: int
    is_safe_as_class_conclusion: bool
    not_mastered_students: list[ClassIndicatorStudentRow] = Field(default_factory=list)
    mastered_students: list[ClassIndicatorStudentRow] = Field(default_factory=list)
    insufficient_students: list[ClassIndicatorStudentRow] = Field(default_factory=list)
    prerequisite_hint_list: list[str] = Field(default_factory=list)
    small_sample_warning_text: str = ""
