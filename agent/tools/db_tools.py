"""供 LangChain Agent 调用的 MySQL 学情与课标查询工具。

MySQL 未启动时，各函数会自动改读 数据层/dataset 下的 CSV / JSON 文件，保证对话与建议不中断。
"""
import csv
import json
from pathlib import Path

import pymysql
from langchain_core.tools import tool

from agent.config.settings import AGENT_ROOT, MYSQL_CONFIG

DATASET_DIR = AGENT_ROOT.parent / "数据层" / "dataset"


# ==================== 1. 基础辅助函数 ====================
def query_mysql(sql: str, params=()) -> list[dict]:
    """执行 SELECT 并返回字典列表，数据库错误由调用方处理。"""
    with pymysql.connect(
        **MYSQL_CONFIG,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=1,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())


def _read_csv(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _read_json(path: Path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _to_float(val):
    if val is None:
        return None
    text = str(val).strip()
    if text in ("", "None", "null", "nan"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def format_num(val) -> str:
    """把 18.0 格式化成 18，保留小数时最多 1 位"""
    num = _to_float(val)
    if num is None:
        return "—"
    return str(int(num)) if num.is_integer() else f"{num:.1f}"


def _pct(rate) -> str:
    num = _to_float(rate)
    return "—" if num is None else f"{round(num * 100, 1)}%"


# ==================== 2. 学生学情查询函数（供个性化建议 + Agent 工具共用） ====================
def _student_summary_from_files(sid: str) -> str:
    profile_json = _read_json(DATASET_DIR / "01_按学生" / sid / f"{sid}.json")
    overview_rows = _read_csv(DATASET_DIR / "01_按学生" / sid / f"{sid}_速览.csv")
    if not profile_json and not overview_rows:
        return f"未查到学号为 {sid} 的学情记录。"

    lines = [f"学号：{sid}"]
    p = (profile_json or {}).get("student") or {}
    if p:
        lines.append(
            f"所属班级：{p.get('class_id', '未知')}；总成绩：{format_num(p.get('score_total'))}/{format_num(p.get('full_score_total'))} 分"
            f"（总得分率 {_pct(p.get('score_rate'))}）；做过不同题目：{p.get('distinct_question_count')}/{p.get('available_question_count')} 题。"
        )

    lines.append("\n各知识点作答明细：")
    for row in overview_rows:
        if (row.get("行类型") or "").strip() == "theme":
            continue
        theme = row.get("主题名称", "")
        name = row.get("指标名称", "")
        textbook = row.get("教材范围") or "对应章节"
        rec = row.get("可补练习题") or "无"
        score, full = _to_float(row.get("得分")), _to_float(row.get("满分"))
        if score is not None and full:
            lines.append(
                f"- 【{theme}】{name}：得分 {format_num(score)}/{format_num(full)}（得分率 {round(score / full * 100, 1)}%），"
                f"已做 {row.get('做过不同题目')}/{row.get('他能考到')} 题，教材范围：{textbook}，可补练习题：{rec}"
            )
        else:
            lines.append(
                f"- 【{theme}】{name}：暂未作答（已做 0/{row.get('他能考到')} 题），教材范围：{textbook}，可补练习题：{rec}"
            )
    return "\n".join(lines)


def get_student_summary_text(student_id: str) -> str:
    """
    查询某名学生的整体成绩、各主题/知识点得分率、未作答项与推荐练习题，
    拼成一段清晰的中文报告（MySQL 不可用时改读本地数据层文件）。
    """
    sid = student_id.strip().upper()
    try:
        profiles = query_mysql(
            "SELECT student_id, class_id, score_total, full_score_total, score_rate, "
            "distinct_question_count, available_question_count "
            "FROM student_profiles WHERE student_id = %s",
            (sid,),
        )
        overview_rows = query_mysql(
            "SELECT row_type, theme_name, indicator_name, done_count, eligible_count, "
            "score, full_score, score_rate, textbook_scope, recommended_questions "
            "FROM student_overview WHERE student_id = %s ORDER BY id",
            (sid,),
        )
    except Exception:
        return _student_summary_from_files(sid)

    if not profiles and not overview_rows:
        return _student_summary_from_files(sid)

    lines = [f"学号：{sid}"]
    if profiles:
        p = profiles[0]
        lines.append(
            f"所属班级：{p.get('class_id', '未知')}；总成绩：{format_num(p.get('score_total'))}/{format_num(p.get('full_score_total'))} 分"
            f"（总得分率 {_pct(p.get('score_rate'))}）；做过不同题目：{p.get('distinct_question_count')}/{p.get('available_question_count')} 题。"
        )

    lines.append("\n各知识点作答明细：")
    for row in overview_rows:
        if row["row_type"] == "theme":
            continue
        theme = row["theme_name"] or ""
        name = row["indicator_name"] or ""
        textbook = row["textbook_scope"] or "对应章节"
        rec = row["recommended_questions"] or "无"

        if row["score"] is not None and row["full_score"]:
            pct = round((float(row["score"]) / float(row["full_score"])) * 100, 1)
            lines.append(
                f"- 【{theme}】{name}：得分 {format_num(row['score'])}/{format_num(row['full_score'])}（得分率 {pct}%），"
                f"已做 {row['done_count']}/{row['eligible_count']} 题，教材范围：{textbook}，可补练习题：{rec}"
            )
        else:
            lines.append(
                f"- 【{theme}】{name}：暂未作答（已做 0/{row['eligible_count']} 题），"
                f"教材范围：{textbook}，可补练习题：{rec}"
            )

    return "\n".join(lines)


# ==================== 3. 暴露给 LangChain Agent 的 @tool 工具 ====================
@tool(description="查询指定学号学生的总成绩、各主题和知识点得分率、教材范围及可补练习题。参数 student_id 为学号，如 D01。")
def query_student_scores(student_id: str) -> str:
    return get_student_summary_text(student_id)


def _wrong_questions_from_files(sid: str) -> list[dict]:
    data = _read_json(DATASET_DIR / "01_按学生" / sid / f"{sid}.json") or {}
    indicator_map = {
        r.get("指标编号", ""): (r.get("主题名称", ""), r.get("指标名称", ""))
        for r in _read_csv(DATASET_DIR / "00_字典" / "指标字典.csv")
    }
    rows = []
    for rec in data.get("question_records") or []:
        score, full = _to_float(rec.get("score")), _to_float(rec.get("full_score"))
        if score is None or full is None or score >= full:
            continue
        theme_name, ind_name = indicator_map.get(rec.get("indicator_id", ""), ("", ""))
        rows.append(
            {
                "exam_id": rec.get("exam_id"),
                "question_id": rec.get("question_id"),
                "score": score,
                "full_score": full,
                "rubric_scores": rec.get("rubric_scores"),
                "theme_name": theme_name,
                "indicator_name": ind_name,
                "question_type": None,
            }
        )
    rows.sort(key=lambda r: (-(r["full_score"] - r["score"]), r["question_id"] or ""))
    return rows[:12]


@tool(description="查询指定学号学生的失分题目与错题明细（包含题号、知识点、得分/满分、评分点扣分情况）。参数 student_id 为学号，如 D01。")
def query_student_wrong_questions(student_id: str) -> str:
    sid = student_id.strip().upper()
    try:
        rows = query_mysql(
            """
            SELECT r.exam_id, r.question_id, r.score, r.full_score, r.rubric_scores,
                   q.theme_name, q.indicator_name, q.question_type
            FROM student_question_records r
            LEFT JOIN dict_questions q ON r.question_id = q.material_id
            WHERE r.student_id = %s AND r.score < r.full_score
            ORDER BY (r.full_score - r.score) DESC, r.question_id ASC
            LIMIT 12
            """,
            (sid,),
        )
    except Exception:
        rows = _wrong_questions_from_files(sid)

    if not rows:
        return f"学号 {sid} 暂无失分错题记录。"

    lines = [f"学号 {sid} 的失分/错题记录（按失分从高到低，最多展示 12 题）："]
    for row in rows:
        lost = float(row["full_score"]) - float(row["score"])
        lines.append(
            f"- 题号 {row['question_id']}（{row['exam_id']}，{row['question_type'] or '题目'}）"
            f"| 知识点：【{row['theme_name'] or ''}】{row['indicator_name'] or ''}"
            f" | 得分 {format_num(row['score'])}/{format_num(row['full_score'])}（失 {format_num(lost)} 分）"
            f" | 评分点：{row['rubric_scores'] or '无'}"
        )
    return "\n".join(lines)


def _class_rows_from_files(cid: str, is_all: bool, group_name: str):
    stu_rows = [
        {
            "student_id": r.get("学生"),
            "class_id": r.get("班级"),
            "score": _to_float(r.get("得分")),
            "full_score": _to_float(r.get("满分")),
            "score_rate": _to_float(r.get("得分率")),
        }
        for r in _read_csv(DATASET_DIR / "02_按班级" / "班级总表.csv")
        if is_all or (r.get("班级") or "").strip() == cid
    ]
    stu_rows.sort(key=lambda r: (r["score_rate"] is None, r["score_rate"] or 0))

    theme_rows = [
        {
            "theme_name": r.get("主题名称"),
            "score": _to_float(r.get("得分")),
            "full_score": _to_float(r.get("满分")),
            "score_rate": _to_float(r.get("得分率")),
        }
        for r in _read_csv(DATASET_DIR / "02_按班级" / "班级_主题汇总.csv")
        if (r.get("群体") or "").strip() == group_name
    ]
    theme_rows.sort(key=lambda r: r["score_rate"] or 0)

    ind_rows = [
        {
            "indicator_name": r.get("指标名称"),
            "score": _to_float(r.get("得分")),
            "full_score": _to_float(r.get("满分")),
            "score_rate": _to_float(r.get("得分率")),
        }
        for r in _read_csv(DATASET_DIR / "02_按班级" / "班级_指标汇总.csv")
        if (r.get("群体") or "").strip() == group_name
    ]
    ind_rows.sort(key=lambda r: r["score_rate"] or 0)
    return stu_rows, theme_rows, ind_rows[:3]


@tool(description="查询某个班级（如 DC01、DC02）或全年级（传 '全年级'）的整体学情：班级人数、平均分、各主题得分率、最薄弱主题、薄弱知识点和重点关注学生。")
def query_class_analysis(class_id: str) -> str:
    cid = class_id.strip().upper()
    is_all = class_id.strip() in ("全年级", "全部", "all", "ALL")
    group_name = "全年级" if is_all else cid

    try:
        if is_all:
            stu_rows = query_mysql(
                "SELECT student_id, class_id, score, full_score, score_rate "
                "FROM class_student_summary ORDER BY score_rate ASC"
            )
        else:
            stu_rows = query_mysql(
                "SELECT student_id, class_id, score, full_score, score_rate "
                "FROM class_student_summary WHERE class_id = %s ORDER BY score_rate ASC",
                (cid,),
            )
        theme_rows = query_mysql(
            "SELECT theme_name, score, full_score, score_rate "
            "FROM class_theme_summary WHERE group_name = %s ORDER BY score_rate ASC",
            (group_name,),
        )
        ind_rows = query_mysql(
            "SELECT indicator_name, score, full_score, score_rate "
            "FROM class_indicator_summary WHERE group_name = %s ORDER BY score_rate ASC LIMIT 3",
            (group_name,),
        )
    except Exception:
        stu_rows, theme_rows, ind_rows = _class_rows_from_files(cid, is_all, group_name)

    if not stu_rows:
        return f"未找到班级「{cid}」的记录，可尝试传 DC01、DC02 或 全年级。"

    scores = [r["score"] for r in stu_rows if r["score"] is not None]
    avg_score = round(sum(scores) / len(scores), 2) if scores else 0
    lines = [
        f"【{group_name} 整体学情分析】",
        f"学生人数：{len(stu_rows)} 人；平均总分：{avg_score} 分。",
    ]

    if theme_rows:
        lowest = theme_rows[0]
        lines.append(
            f"最薄弱主题：{lowest['theme_name']}（得分率 {_pct(lowest['score_rate'])}，"
            f"{format_num(lowest['score'])}/{format_num(lowest['full_score'])} 分）。"
        )
        lines.append("各主题得分率排行（从低到高）：")
        for t in theme_rows:
            lines.append(
                f"  - {t['theme_name']}：{_pct(t['score_rate'])}（{format_num(t['score'])}/{format_num(t['full_score'])} 分）"
            )

    if ind_rows:
        lines.append("最薄弱的 3 个知识点：")
        for ind in ind_rows:
            lines.append(
                f"  - {ind['indicator_name']}：得分率 {_pct(ind['score_rate'])}（{format_num(ind['score'])}/{format_num(ind['full_score'])} 分）"
            )

    focus_students = [r for r in stu_rows if r["score_rate"] is not None][:5]
    if focus_students:
        lines.append("需重点关注学生（得分率最低前 5 名）：")
        for s in focus_students:
            lines.append(
                f"  - {s['student_id']}（{s['class_id']}）：{format_num(s['score'])}/{format_num(s['full_score'])} 分（{_pct(s['score_rate'])}）"
            )

    return "\n".join(lines)


def query_curriculum_table(keyword: str) -> str:
    """从 MySQL 的 dict_curriculum 表查询课标原文（数据库不可用时返回空串，由 PDF 检索兜底）。"""
    kw = keyword.strip()
    try:
        if not kw:
            rows = query_mysql(
                "SELECT section_title, clause_no, content, doc_page FROM dict_curriculum LIMIT 8"
            )
        else:
            like_kw = f"%{kw}%"
            rows = query_mysql(
                "SELECT section_title, clause_no, content, doc_page FROM dict_curriculum "
                "WHERE section_title LIKE %s OR content LIKE %s LIMIT 8",
                (like_kw, like_kw),
            )
            if not rows:
                rows = query_mysql(
                    "SELECT section_title, clause_no, content, doc_page FROM dict_curriculum LIMIT 12"
                )
    except Exception:
        return ""

    if not rows:
        return ""

    lines = ["【数据库课标原文表】"]
    for r in rows:
        lines.append(f"- {r['section_title']} {r['clause_no']}：{r['content']}（课标第{r['doc_page']}页）")
    return "\n".join(lines)
