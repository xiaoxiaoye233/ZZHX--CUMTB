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
    lines.extend(_prerequisite_lines())
    return "\n".join(lines)


def _prerequisite_lines() -> list[str]:
    """九条前置关系，拼成两行给 Agent（数据表里没有这个字段，按教材章节顺序归纳）。"""
    payload = _read_json(DATASET_DIR / "00_字典" / "必要联系.json") or {}
    edges = payload.get("edges") if isinstance(payload, dict) else payload
    if not isinstance(edges, list) or not edges:
        return []
    out = ["\n指标之间的先后关系（数据表里没有这个字段，按教材章节顺序归纳）："]
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        out.append(
            f"- {edge.get('from_name') or edge.get('from_indicator')} → "
            f"{edge.get('to_name') or edge.get('to_indicator')}（{edge.get('relation_type', '')}）："
            f"{edge.get('rationale_text', '')}"
        )
    return out


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

    lines.extend(_prerequisite_lines())
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
    ind_rows.sort(key=lambda r: (r["score_rate"] is None, r["score_rate"] if r["score_rate"] is not None else 999))
    return stu_rows, theme_rows, ind_rows


def _is_overall_grade_query(raw_class_id: str) -> bool:
    s = str(raw_class_id or "").strip()
    if not s:
        return True
    upper = s.upper()
    overall_aliases = {
        "全年级",
        "全部",
        "全部班级",
        "所有班",
        "所有班级",
        "这两个班",
        "两个班",
        "两班",
        "各班",
        "总体",
        "整体",
        "整体情况",
        "总体情况",
        "全班",
        "ALL",
    }
    if upper in overall_aliases or s in overall_aliases:
        return True
    if any(kw in s for kw in ("两个班", "两班", "所有班", "全部班", "全年级", "整体", "总体")):
        return True
    # 同时包含 DC01 与 DC02（如 "DC01和DC02"、"DC01,DC02"）时同样视为两个班整体情况
    if "DC01" in upper and "DC02" in upper:
        return True
    return False


@tool(
    description=(
        "查询某个班级（如 DC01、DC02）或全部班级整体学情（当教师提到'这两个班'、'两个班'、'全部班级'、"
        "'总体'、'整体'或'全年级'时，参数直接传 '全年级'）：返回人数、平均分、总得分率、最薄弱主题、"
        "全部知识点得分率从低到高排行及重点关注学生。"
    )
)
def query_class_analysis(class_id: str) -> str:
    raw_input = str(class_id or "").strip()
    is_all = _is_overall_grade_query(raw_input)
    cid = raw_input.upper()
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
            "FROM class_indicator_summary WHERE group_name = %s ORDER BY score_rate ASC",
            (group_name,),
        )
    except Exception:
        stu_rows, theme_rows, ind_rows = _class_rows_from_files(cid, is_all, group_name)

    if not stu_rows:
        return f"未找到班级「{raw_input}」的记录，可传 DC01、DC02 或 全年级。"

    scores = [r["score"] for r in stu_rows if r["score"] is not None]
    fulls = [r["full_score"] for r in stu_rows if r["full_score"] is not None]
    avg_score = round(sum(scores) / len(scores), 2) if scores else 0
    overall_rate = (sum(scores) / sum(fulls)) if sum(fulls) > 0 else None
    class_names = sorted({str(r.get("class_id") or "").strip() for r in stu_rows if r.get("class_id")})
    header_label = f"全部班级（{'、'.join(class_names)}）整体" if is_all and class_names else group_name

    lines = [
        f"【{header_label}学情分析】",
        f"学生总数：{len(stu_rows)} 人；平均总分：{avg_score} 分；整体总得分率：{_pct(overall_rate)}（总得分 {format_num(sum(scores))}/{format_num(sum(fulls))} 分）。",
    ]

    if is_all and len(class_names) > 1:
        cls_parts = []
        for cname in class_names:
            c_members = [r for r in stu_rows if r.get("class_id") == cname]
            c_sc = sum(r["score"] for r in c_members if r["score"] is not None)
            c_fl = sum(r["full_score"] for r in c_members if r["full_score"] is not None)
            c_avg = round(c_sc / len(c_members), 2) if c_members else 0
            c_rate = (c_sc / c_fl) if c_fl > 0 else None
            cls_parts.append(f"{cname} 班 {len(c_members)} 人（均分 {c_avg} 分，得分率 {_pct(c_rate)}）")
        lines.append("各班概况：" + "；".join(cls_parts) + "。")

    if theme_rows:
        lowest = theme_rows[0]
        lines.append(
            f"最薄弱主题：{lowest['theme_name']}（得分率 {_pct(lowest['score_rate'])}，"
            f"{format_num(lowest['score'])}/{format_num(lowest['full_score'])} 分）。"
        )
        lines.append("各主题得分率排行（从低到高）：")
        for idx, t in enumerate(theme_rows, start=1):
            lines.append(
                f"  {idx}. {t['theme_name']}：{_pct(t['score_rate'])}（{format_num(t['score'])}/{format_num(t['full_score'])} 分）"
            )

    if ind_rows:
        weakest_ind = ind_rows[0]
        lines.append(
            f"总体最薄弱（做得最差）的知识点：{weakest_ind['indicator_name']}（得分率 {_pct(weakest_ind['score_rate'])}，"
            f"得分 {format_num(weakest_ind['score'])}/{format_num(weakest_ind['full_score'])} 分）。"
        )
        lines.append("各知识点得分率排行（从低到高）：")
        for idx, ind in enumerate(ind_rows, start=1):
            lines.append(
                f"  {idx}. {ind['indicator_name']}：得分率 {_pct(ind['score_rate'])}（{format_num(ind['score'])}/{format_num(ind['full_score'])} 分）"
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
