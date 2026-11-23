-- 智能教学系统（zjhx--cumtb）mysql 8.0 建库与建表脚本
-- 覆盖登录用户表 users 及数据层 00_字典 ~ 04_质量与剔除 全部产物

create database if not exists `zjhx_teaching`
  default character set utf8mb4
  default collate utf8mb4_unicode_ci;

use `zjhx_teaching`;

-- ==================== 登录用户表 ====================
create table if not exists `users` (
  `id` int not null auto_increment comment '自增主键',
  `account` varchar(64) not null comment '登录账号（学生为文件夹名如 d01，教师为 123）',
  `password` varchar(128) not null comment '登录密码',
  `role` varchar(20) not null default 'student' comment '角色：student / teacher',
  `student_id` varchar(64) default null comment '关联学号（教师为 null）',
  `created_at` datetime not null default current_timestamp comment '创建时间',
  `updated_at` datetime not null default current_timestamp on update current_timestamp comment '更新时间',
  primary key (`id`),
  unique key `uk_users_account` (`account`),
  key `idx_users_student_id` (`student_id`)
) engine=innodb default charset=utf8mb4 comment='登录账号表';

-- ==================== 00_字典 ====================
create table if not exists `dict_indicators` (
  `indicator_id` varchar(32) not null comment '指标编号（如 t01i1）',
  `indicator_name` varchar(255) not null comment '指标名称',
  `theme_id` varchar(32) not null comment '主题编号（如 t01）',
  `theme_name` varchar(128) not null comment '主题名称',
  `curriculum_scope` varchar(255) default null comment '课标范围',
  `textbook_scope` varchar(255) default null comment '教材范围',
  `questions_in_bank` int default null comment '全库题数',
  `question_ids` text default null comment '题号列表',
  primary key (`indicator_id`),
  key `idx_dict_ind_theme` (`theme_id`)
) engine=innodb default charset=utf8mb4 comment='00_字典：指标字典';

create table if not exists `dict_exams` (
  `exam_id` varchar(32) not null comment '考试编号（如 n01）',
  `exam_date` varchar(32) default null comment '考试日期',
  `taught_themes` varchar(255) default null comment '已教主题',
  `available_questions` int default null comment '可用题数',
  `description` text default null comment '说明',
  primary key (`exam_id`)
) engine=innodb default charset=utf8mb4 comment='00_字典：考试字典';

create table if not exists `dict_curriculum` (
  `id` int not null auto_increment comment '自增主键',
  `section_code` varchar(32) default null comment '小节编号',
  `theme_id` varchar(32) default null comment '主题编号',
  `section_title` varchar(128) default null comment '课标小节',
  `clause_no` varchar(32) default null comment '条目',
  `content` text default null comment '课标原文',
  `used_indicators` varchar(255) default null comment '用于指标',
  `doc_page` varchar(32) default null comment '文件页',
  `text_page` varchar(32) default null comment '正文页',
  primary key (`id`),
  key `idx_dict_curr_theme` (`theme_id`)
) engine=innodb default charset=utf8mb4 comment='00_字典：课标原文';

create table if not exists `dict_questions` (
  `material_id` varchar(32) not null comment '材料/题目编号（如 q001）',
  `material_type` varchar(32) default null comment '材料类型',
  `theme_id` varchar(32) default null comment '主题编号',
  `theme_name` varchar(128) default null comment '主题名称',
  `indicator_id` varchar(32) default null comment '指标编号',
  `indicator_name` varchar(255) default null comment '指标名称',
  `question_type` varchar(64) default null comment '题型',
  `full_score` double default null comment '满分',
  `rubric_points` text default null comment '评分点',
  `reference_answer` text default null comment '参考答案',
  `source_file` varchar(128) default null comment '来源文件',
  primary key (`material_id`),
  key `idx_dict_q_theme` (`theme_id`),
  key `idx_dict_q_ind` (`indicator_id`)
) engine=innodb default charset=utf8mb4 comment='00_字典：题目字典';

-- ==================== 01_按学生 ====================
create table if not exists `student_profiles` (
  `student_id` varchar(64) not null comment '学号',
  `class_id` varchar(64) default null comment '班级编号',
  `grade` int default null comment '年级',
  `record_count` int default null comment '记录数',
  `distinct_question_count` int default null comment '做过不同题数',
  `available_question_count` int default null comment '他能考到题数',
  `score_total` double default null comment '总得分',
  `full_score_total` double default null comment '总满分',
  `score_rate` double default null comment '总得分率',
  `attended_exams` varchar(255) default null comment '参加考试列表 json',
  primary key (`student_id`),
  key `idx_sp_class` (`class_id`)
) engine=innodb default charset=utf8mb4 comment='01_按学生：学生学情档案';

create table if not exists `student_overview` (
  `id` int not null auto_increment comment '自增主键',
  `student_id` varchar(64) not null comment '学号',
  `row_type` varchar(32) not null comment '行类型：indicator / theme',
  `theme_id` varchar(32) default null comment '主题编号',
  `theme_name` varchar(128) default null comment '主题名称',
  `indicator_id` varchar(64) default null comment '指标编号',
  `indicator_name` varchar(255) default null comment '指标名称',
  `total_bank_count` int default null comment '全库题数',
  `eligible_count` int default null comment '他能考到',
  `done_count` int default null comment '做过不同题目',
  `threshold` int default null comment '判定线',
  `coverage_rate` double default null comment '覆盖率',
  `score` double default null comment '得分',
  `full_score` double default null comment '满分',
  `score_rate` double default null comment '得分率',
  `tier` varchar(32) default null comment '档位',
  `tier_note` varchar(255) default null comment '档位说明',
  `curriculum_scope` varchar(255) default null comment '课标范围',
  `textbook_scope` varchar(255) default null comment '教材范围',
  `recommended_questions` text default null comment '可补练习题',
  primary key (`id`),
  key `idx_so_student` (`student_id`),
  key `idx_so_theme` (`theme_id`)
) engine=innodb default charset=utf8mb4 comment='01_按学生：学生指标与主题速览';

create table if not exists `student_question_records` (
  `id` int not null auto_increment comment '自增主键',
  `record_id` varchar(64) default null comment '作答记录编号',
  `student_id` varchar(64) not null comment '学号',
  `exam_id` varchar(32) default null comment '考试编号',
  `question_id` varchar(32) default null comment '题号',
  `theme_id` varchar(32) default null comment '主题编号',
  `indicator_id` varchar(32) default null comment '指标编号',
  `full_score` double default null comment '满分',
  `score` double default null comment '得分',
  `score_rate` double default null comment '得分率',
  `rubric_scores` text default null comment '评分点得分详情',
  `counted_in_denominator` tinyint(1) default 1 comment '是否计入分母',
  `grading_flag` varchar(64) default null comment '判分标记',
  primary key (`id`),
  key `idx_sqr_student` (`student_id`),
  key `idx_sqr_question` (`question_id`)
) engine=innodb default charset=utf8mb4 comment='01_按学生：学生逐题作答明细';

-- ==================== 02_按班级 ====================
create table if not exists `class_student_summary` (
  `student_id` varchar(64) not null comment '学号',
  `class_id` varchar(64) default null comment '班级编号',
  `record_count` int default null comment '记录数',
  `distinct_question_count` int default null comment '不同题目数',
  `available_question_count` int default null comment '他能考到题数',
  `score` double default null comment '总得分',
  `full_score` double default null comment '总满分',
  `score_rate` double default null comment '总得分率',
  `theme_rates_json` text default null comment '各主题得分率 json',
  primary key (`student_id`),
  key `idx_css_class` (`class_id`)
) engine=innodb default charset=utf8mb4 comment='02_按班级：班级总表';

create table if not exists `class_theme_summary` (
  `id` int not null auto_increment comment '自增主键',
  `group_name` varchar(64) not null comment '群体（班级编号或全年级）',
  `student_count` int default null comment '人数',
  `theme_id` varchar(32) not null comment '主题编号',
  `theme_name` varchar(128) not null comment '主题名称',
  `done_questions_total` int default null comment '做过题数合计',
  `score` double default null comment '得分合计',
  `full_score` double default null comment '满分合计',
  `score_rate` double default null comment '主题总得分率',
  `recorded_students` int default null comment '有记录人数',
  primary key (`id`),
  key `idx_cts_group_theme` (`group_name`, `theme_id`)
) engine=innodb default charset=utf8mb4 comment='02_按班级：班级主题汇总';

create table if not exists `class_indicator_summary` (
  `id` int not null auto_increment comment '自增主键',
  `group_name` varchar(64) not null comment '群体（班级编号或全年级）',
  `student_count` int default null comment '人数',
  `theme_id` varchar(32) default null comment '主题编号',
  `indicator_id` varchar(32) not null comment '指标编号',
  `indicator_name` varchar(255) default null comment '指标名称',
  `eligible_questions_total` int default null comment '可考题数合计',
  `done_questions_total` int default null comment '做过题数合计',
  `score` double default null comment '得分合计',
  `full_score` double default null comment '满分合计',
  `score_rate` double default null comment '指标得分率',
  `recorded_students` int default null comment '有记录人数',
  primary key (`id`),
  key `idx_cis_group_ind` (`group_name`, `indicator_id`)
) engine=innodb default charset=utf8mb4 comment='02_按班级：班级指标汇总';

-- ==================== 03_按主题 ====================
create table if not exists `theme_student_scores` (
  `id` int not null auto_increment comment '自增主键',
  `theme_id` varchar(32) not null comment '主题编号',
  `theme_name` varchar(128) not null comment '主题名称',
  `student_id` varchar(64) not null comment '学号',
  `class_id` varchar(64) default null comment '班级编号',
  `eligible_count` int default null comment '本主题可考题数',
  `done_count` int default null comment '做过题数',
  `score` double default null comment '本主题得分',
  `full_score` double default null comment '本主题满分',
  `score_rate` double default null comment '本主题得分率',
  `ind1_rate` double default null comment '指标一得分率',
  `ind2_rate` double default null comment '指标二得分率',
  `ind3_rate` double default null comment '指标三得分率',
  primary key (`id`),
  unique key `uk_tss_theme_student` (`theme_id`, `student_id`),
  key `idx_tss_student` (`student_id`),
  key `idx_tss_class` (`class_id`)
) engine=innodb default charset=utf8mb4 comment='03_按主题：学生各主题得分明细';

-- ==================== 04_质量与剔除 ====================
create table if not exists `quality_grading_suspects` (
  `id` int not null auto_increment comment '自增主键',
  `record_id` varchar(64) default null comment '记录编号',
  `student_id` varchar(64) default null comment '学号',
  `question_id` varchar(32) default null comment '题号',
  `grading_flag` varchar(64) default null comment '判分标记',
  `description` text default null comment '说明',
  primary key (`id`)
) engine=innodb default charset=utf8mb4 comment='04_质量与剔除：判分存疑';

create table if not exists `quality_multi_versions` (
  `id` int not null auto_increment comment '自增主键',
  `attempt_event` varchar(128) default null comment '作答事件',
  `student_id` varchar(64) default null comment '学号',
  `question_id` varchar(32) default null comment '题号',
  `revision` int default null comment '修订版本',
  `grading_status` varchar(64) default null comment '评分状态',
  `score` double default null comment '得分',
  `is_adopted` varchar(16) default null comment '是否采用',
  primary key (`id`)
) engine=innodb default charset=utf8mb4 comment='04_质量与剔除：多版本明细';

create table if not exists `quality_excluded_records` (
  `id` int not null auto_increment comment '自增主键',
  `record_id` varchar(64) default null comment '记录编号',
  `student_id` varchar(64) default null comment '学号',
  `question_id` varchar(32) default null comment '题号',
  `exam_id` varchar(32) default null comment '考试编号',
  `revision` int default null comment '修订版本',
  `grading_status` varchar(64) default null comment '评分状态',
  `score` double default null comment '得分',
  `full_score` double default null comment '满分',
  `exclude_reason` varchar(255) default null comment '剔除原因',
  primary key (`id`)
) engine=innodb default charset=utf8mb4 comment='04_质量与剔除：被剔除记录';

create table if not exists `quality_checklist` (
  `id` int not null auto_increment comment '自增主键',
  `issue_code` varchar(64) default null comment '问题代码',
  `severity` varchar(32) default null comment '严重程度',
  `record_count` int default null comment '记录数',
  `sample_records` text default null comment '样例记录',
  `description` text default null comment '说明',
  `handling` text default null comment '处置',
  `affects_denominator` varchar(16) default null comment '影响分母',
  primary key (`id`)
) engine=innodb default charset=utf8mb4 comment='04_质量与剔除：质量检查清单';

create table if not exists `quality_benchmarks` (
  `name` varchar(128) not null comment '基准项名称',
  `expected` varchar(128) default null comment '期望值',
  `actual` varchar(128) default null comment '实际值',
  `unit` varchar(32) default null comment '单位',
  `description` text default null comment '说明',
  `source` varchar(255) default null comment '来源',
  primary key (`name`)
) engine=innodb default charset=utf8mb4 comment='04_质量与剔除：基准数字';
