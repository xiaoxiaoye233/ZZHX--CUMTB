from __future__ import annotations

from datetime import datetime
from io import BytesIO
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import NamedTemporaryFile
from threading import Lock
from uuid import UUID

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from agent.core.student_agent import generate_student_report_advice, get_student_history
from config.db_conf import students_data_dir
from models.dataset import StudentProfile
from utils.file_tools import read_json_file, to_float, to_int
from utils.knowledge_graph import load_knowledge_graph


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "printfiles"
ADVICE_CACHE_FILE = Path(__file__).resolve().parents[1] / ".report-advice-cache.json"
PRINT_SCRIPT = REPO_ROOT / "打印模块" / "print_pdf" / "print_pdf_file.py"
FONT_NAME = "StudentReportChinese"
_FONT_LOCK = Lock()
_CACHE_LOCK = Lock()
logger = logging.getLogger(__name__)

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 38
BOTTOM_MARGIN = 44
WIDTH = PAGE_WIDTH - 2 * MARGIN

NAVY = HexColor("#16345A")
SUBTLE = HexColor("#4A5D73")
MUTED = HexColor("#7B8B9E")
LINE = HexColor("#D7E0EA")
PANEL = HexColor("#F2F6FA")
TRACK_BG = HexColor("#E2E8F0")
GREEN = HexColor("#16A34A")
BLUE = HexColor("#2563EB")
AMBER = HexColor("#D97706")
RED_BG = HexColor("#FEF2F2")
RED_BORDER = HexColor("#FECACA")
RED_TEXT = HexColor("#B91C1C")


def _register_font() -> None:
    with _FONT_LOCK:
        if FONT_NAME in pdfmetrics.getRegisteredFontNames():
            return
        configured_font = os.environ.get("REPORT_FONT_PATH")
        windows_fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        font_paths = (
            [Path(configured_font)]
            if configured_font
            else [windows_fonts / "msyh.ttc", windows_fonts / "simhei.ttf"]
        )
        for font_path in font_paths:
            if font_path.is_file():
                pdfmetrics.registerFont(TTFont(FONT_NAME, str(font_path)))
                return
        raise FileNotFoundError("未找到中文 TrueType 字体，可通过 REPORT_FONT_PATH 指定字体文件")


def _number(value) -> str:
    number = to_float(value)
    return "-" if number is None else f"{number:g}"


def _rate(value) -> str:
    rate = to_float(value)
    return "暂未作答" if rate is None else f"{rate * 100:.1f}%"


def _clean_markdown_text(raw: str) -> str:
    """清理 Markdown 星号与标题符号，保留自然分段，便于网页与 PDF 统一排版。"""
    text = str(raw or "").strip()
    if not text:
        return ""
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"__(.*?)__", r"\1", text)
    text = text.replace("`", "")
    cleaned_lines = []
    for line in text.splitlines():
        s = re.sub(r"^\s*#{1,6}\s*", "", line).strip()
        if s:
            cleaned_lines.append(s)
    return "\n".join(cleaned_lines)


def build_fallback_report_advice(student_id: str, report_data: dict) -> str:
    """当未配置大模型密钥或网络暂不可用时，基于真实学情动态生成个性化建议（绝不暴露内部编号）。"""
    overall = report_data.get("overall") or {}
    kps = report_data.get("knowledge_points") or []
    wrong_ids = report_data.get("wrong_question_ids") or [
        w.get("question_id") for w in (report_data.get("wrong_questions") or []) if w.get("question_id")
    ]

    scored = [k for k in kps if k.get("score_rate") is not None]
    unanswered = [k for k in kps if k.get("score_rate") is None]
    scored_desc = sorted(scored, key=lambda k: float(k["score_rate"]), reverse=True)
    scored_asc = sorted(scored, key=lambda k: float(k["score_rate"]))

    overall_pct = _rate(overall.get("score_rate"))
    score_str = f"{_number(overall.get('score'))}/{_number(overall.get('full_score'))}"

    if scored_desc and float(scored_desc[0]["score_rate"]) >= 0.6:
        best = scored_desc[0]
        p1 = (
            f"1. {student_id} 同学你好！你目前已累计得分 {score_str} 分（总得分率 {overall_pct}），"
            f"其中在「{best['name']}」（得分率 {_rate(best['score_rate'])}）上展现出了扎实的理解与掌握，值得肯定。"
        )
    else:
        p1 = (
            f"1. {student_id} 同学你好！你目前已累计完成 {overall.get('done_questions') or 0} 道题目，"
            f"总得分 {score_str} 分（总得分率 {overall_pct}），每一次认真作答都在为后续提升积累宝贵经验。"
        )

    weak_items = [k for k in scored_asc if float(k["score_rate"]) < 0.75][:2] or scored_asc[:2]
    if weak_items:
        weak_parts = []
        for item in weak_items:
            scope = f"（参考教材：{item['textbook_scope']}）" if item.get("textbook_scope") else ""
            weak_parts.append(f"「{item['name']}」{scope}")
        unans_hint = (
            f"；此外还有「{unanswered[0]['name']}」等 {len(unanswered)} 个知识点尚待探索练习"
            if unanswered
            else ""
        )
        p2 = (
            f"2. 建议现阶段优先巩固 {'、'.join(weak_parts)}{unans_hint}，"
            "先结合教材例题梳理核心概念与易错步骤，再动手独立推导。"
        )
    else:
        p2 = "2. 各已学知识点整体掌握较为均衡，建议继续结合教材梳理知识脉络，串联前后知识点之间的联系。"

    rec_questions: list[str] = []
    for item in weak_items + unanswered:
        for q in item.get("recommended_questions") or []:
            if q not in rec_questions:
                rec_questions.append(q)
            if len(rec_questions) >= 4:
                break
        if len(rec_questions) >= 4:
            break

    wrong_preview = "、".join(wrong_ids[:6]) + (" 等" if len(wrong_ids) > 6 else "")
    if wrong_ids and rec_questions:
        p3 = (
            f"3. 建议先复盘错题 {wrong_preview}，找准失分原因并订正关键步骤；"
            f"随后可针对性选做 {'、'.join(rec_questions)} 巩固提升。遇到疑问随时在对话框向老师提问！"
        )
    elif wrong_ids:
        p3 = f"3. 建议优先复盘错题 {wrong_preview}，逐题梳理审题与运算细节，遇到卡点随时在对话框提问交流！"
    elif rec_questions:
        p3 = f"3. 下一步可尝试练习 {'、'.join(rec_questions)} 进一步检验学习效果，保持良好学习节奏！"
    else:
        p3 = "3. 继续保持良好的审题和验算习惯，可在任务面板与知识图谱中拓展更多练习！"

    return "\n".join([p1, p2, p3])


def _load_cached_advice(cache_key: str) -> str:
    with _CACHE_LOCK:
        if not ADVICE_CACHE_FILE.is_file():
            return ""
        try:
            data = json.loads(ADVICE_CACHE_FILE.read_text(encoding="utf-8"))
            return str(data.get(cache_key) or "").strip() if isinstance(data, dict) else ""
        except (OSError, ValueError):
            return ""


def _save_cached_advice(cache_key: str, advice: str) -> None:
    with _CACHE_LOCK:
        data = {}
        if ADVICE_CACHE_FILE.is_file():
            try:
                loaded = json.loads(ADVICE_CACHE_FILE.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
            except (OSError, ValueError):
                data = {}
        data[cache_key] = advice
        try:
            ADVICE_CACHE_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass


def resolve_student_report_advice(student_id: str, report_data: dict) -> str:
    """获取学情报告中的个性化建议：优先复用最新已生成建议，其次调用大模型并缓存，最后使用真实学情兜底。"""
    sid = student_id.strip().upper()
    overall = report_data.get("overall") or {}
    cache_key = (
        f"{sid}:{overall.get('score')}:{overall.get('full_score')}:"
        f"{overall.get('done_questions')}:{overall.get('knowledge_point_count')}"
    )

    cached = _load_cached_advice(cache_key)
    if cached:
        return cached

    # 若会话历史中已有个性化建议，直接清理格式后复用，保证秒开
    for msg in reversed(get_student_history(sid)):
        tag = str(msg.get("tag") or "")
        content = _clean_markdown_text(msg.get("content") or "")
        if "个性化建议" in tag and content:
            _save_cached_advice(cache_key, content)
            return content

    if os.environ.get("DASHSCOPE_API_KEY", "").strip():
        try:
            generated = _clean_markdown_text(generate_student_report_advice(sid))
            if generated:
                _save_cached_advice(cache_key, generated)
                return generated
        except Exception:
            logger.warning("调用大模型生成学情报告建议失败，将使用学情规则建议兜底。", exc_info=True)

    return build_fallback_report_advice(sid, report_data)


def _wrapped_lines(text: str, width: float, size: float, limit: int | None = None) -> list[str]:
    """逐字符测量中文行宽；limit=None 时完整换行绝不截断，指定 limit 时超长加省略号。"""
    lines: list[str] = []
    paragraphs = [
        " ".join(paragraph.split())
        for paragraph in str(text or "").splitlines()
        if paragraph.strip()
    ]
    for p_idx, para in enumerate(paragraphs):
        line = ""
        for char in para:
            if pdfmetrics.stringWidth(line + char, FONT_NAME, size) <= width:
                line += char
                continue
            if limit is not None and len(lines) == limit - 1:
                while line and pdfmetrics.stringWidth(line + "…", FONT_NAME, size) > width:
                    line = line[:-1]
                return [*lines, line.rstrip() + "…"]
            lines.append(line)
            line = char.lstrip()
        if line:
            if limit is not None and len(lines) == limit - 1 and p_idx < len(paragraphs) - 1:
                while line and pdfmetrics.stringWidth(line + "…", FONT_NAME, size) > width:
                    line = line[:-1]
                return [*lines, line.rstrip() + "…"]
            lines.append(line)
    return lines


def _draw_single_line(
    pdf: Canvas,
    text: str,
    x: float,
    y: float,
    size: float,
    color=NAVY,
    width: float = WIDTH,
) -> None:
    lines = _wrapped_lines(text, width, size, limit=1)
    if lines:
        pdf.setFont(FONT_NAME, size)
        pdf.setFillColor(color)
        pdf.drawString(x, y, lines[0])


def _rate_bar_color(rate_val: float | None):
    if rate_val is None:
        return MUTED
    if rate_val >= 0.8:
        return GREEN
    if rate_val >= 0.6:
        return BLUE
    return AMBER


def _normalize_report_payload(
    student_id: str,
    profile: StudentProfile | None,
    rows: list[dict],
    advice: str,
    wrong_questions: list[dict] | list[str] | None = None,
    knowledge_points: list[dict] | None = None,
) -> dict:
    sid = student_id.strip().upper()

    if knowledge_points is None:
        graph_data = load_knowledge_graph()
        graph_nodes = graph_data.get("nodes") if isinstance(graph_data, dict) else []
        graph_by_id = {
            str(n.get("id") or "").strip(): n
            for n in (graph_nodes or [])
            if isinstance(n, dict) and str(n.get("id") or "").strip()
        }
        knowledge_points = []
        seen_ids: set[str] = set()
        seen_names: set[str] = set()

        for row in rows or []:
            if str(row.get("行类型") or "").strip().lower() == "theme":
                continue
            ind_id = str(row.get("指标编号") or "").strip()
            raw_name = str(row.get("指标名称") or "").strip()
            g_node = graph_by_id.get(ind_id)
            name = (str(g_node.get("name") or "").strip() if g_node else "") or raw_name or ind_id
            theme_name = (
                (str(g_node.get("theme") or "").strip() if g_node else "")
                or str(row.get("主题名称") or "").strip()
            )
            score = to_float(row.get("得分"))
            full_score = to_float(row.get("满分"))
            has_record = score is not None and full_score is not None and full_score > 0
            score_rate = round(score / full_score, 4) if has_record else to_float(row.get("得分率"))
            knowledge_points.append(
                {
                    "id": ind_id or name,
                    "name": name,
                    "theme_name": theme_name,
                    "score": score,
                    "full_score": full_score,
                    "score_rate": score_rate,
                    "done_count": to_int(row.get("做过不同题目")) or 0,
                    "eligible_count": to_int(row.get("他能考到")) or 0,
                    "has_record": has_record,
                }
            )
            if ind_id:
                seen_ids.add(ind_id)
            if name:
                seen_names.add(name)
            if raw_name:
                seen_names.add(raw_name)

        for n in graph_nodes or []:
            if not isinstance(n, dict):
                continue
            nid = str(n.get("id") or "").strip()
            nname = str(n.get("name") or "").strip()
            if not nname or nid in seen_ids or nname in seen_names:
                continue
            knowledge_points.append(
                {
                    "id": nid or nname,
                    "name": nname,
                    "theme_name": str(n.get("theme") or "").strip(),
                    "score": None,
                    "full_score": None,
                    "score_rate": None,
                    "done_count": 0,
                    "eligible_count": 0,
                    "has_record": False,
                }
            )
            if nid:
                seen_ids.add(nid)
            seen_names.add(nname)

    if wrong_questions is None:
        student_json = read_json_file(students_data_dir / sid / f"{sid}.json") or {}
        wrong_set: set[str] = set()
        for rec in student_json.get("question_records") or []:
            qid = str(rec.get("question_id") or "").strip()
            sc = to_float(rec.get("score"))
            fl = to_float(rec.get("full_score"))
            if qid and sc is not None and fl is not None and fl > 0 and sc < fl:
                wrong_set.add(qid)
        wrong_ids = sorted(
            wrong_set,
            key=lambda q: (int(re.findall(r"\d+", q)[0]) if re.findall(r"\d+", q) else 10**9, q),
        )
    else:
        wrong_ids = [
            (item.get("question_id") if isinstance(item, dict) else str(item)).strip()
            for item in wrong_questions
            if (item.get("question_id") if isinstance(item, dict) else str(item)).strip()
        ]

    scored_kps = [kp for kp in knowledge_points if kp.get("score") is not None and kp.get("full_score")]
    calc_score = round(sum(float(kp["score"]) for kp in scored_kps), 2) if scored_kps else 0.0
    calc_full = round(sum(float(kp["full_score"]) for kp in scored_kps), 2) if scored_kps else 0.0

    score_total = profile.score_total if profile and profile.score_total is not None else calc_score
    full_total = profile.full_score_total if profile and profile.full_score_total is not None else calc_full
    overall_rate = (
        round(float(score_total) / float(full_total), 4)
        if score_total is not None and full_total and float(full_total) > 0
        else (to_float(profile.score_rate) if profile else None)
    )
    done_cnt = (
        profile.distinct_question_count
        if profile and profile.distinct_question_count is not None
        else sum(int(kp.get("done_count") or 0) for kp in knowledge_points)
    )
    avail_cnt = (
        profile.available_question_count
        if profile and profile.available_question_count is not None
        else sum(int(kp.get("eligible_count") or 0) for kp in knowledge_points)
    )

    return {
        "student_id": sid,
        "class_id": (profile.class_id if profile and profile.class_id else ""),
        "overall": {
            "score": score_total,
            "full_score": full_total,
            "score_rate": overall_rate,
            "done_questions": done_cnt,
            "available_questions": avail_cnt,
            "knowledge_point_count": len(knowledge_points),
            "wrong_question_count": len(wrong_ids),
        },
        "knowledge_points": knowledge_points,
        "wrong_question_ids": wrong_ids,
        "advice": _clean_markdown_text(advice),
    }


def _draw_report_to_canvas(pdf: Canvas, report_data: dict) -> None:
    _register_font()
    sid = report_data.get("student_id") or "-"
    class_name = report_data.get("class_id") or "-"
    overall = report_data.get("overall") or {}
    knowledge_points = report_data.get("knowledge_points") or []
    wrong_ids = report_data.get("wrong_question_ids") or [
        w.get("question_id") for w in (report_data.get("wrong_questions") or []) if w.get("question_id")
    ]
    include_advice = bool(report_data.get("include_advice", True))
    advice_text = (
        _clean_markdown_text(report_data.get("advice") or "")
        or build_fallback_report_advice(sid, report_data)
        if include_advice
        else ""
    )

    pdf.setTitle(f"学生学情报告_{sid}")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    page_no = 1
    y = PAGE_HEIGHT - MARGIN

    def draw_footer(pno: int) -> None:
        pdf.setFont(FONT_NAME, 8.5)
        pdf.setFillColor(MUTED)
        footer_note = (
            "学情数据来自已同步作答记录 · 个性化建议由智教慧学 Agent 生成"
            if include_advice
            else "学情数据来自已同步作答记录"
        )
        pdf.drawString(MARGIN, 22, footer_note)
        pdf.drawRightString(PAGE_WIDTH - MARGIN, 22, f"第 {pno} 页")

    def start_new_page() -> None:
        nonlocal page_no, y
        draw_footer(page_no)
        pdf.showPage()
        page_no += 1
        y = PAGE_HEIGHT - MARGIN
        _draw_single_line(pdf, f"学生学情报告 · 学号 {sid}", MARGIN, y - 12, 10, MUTED, WIDTH - 120)
        pdf.setFont(FONT_NAME, 9.5)
        pdf.setFillColor(MUTED)
        pdf.drawRightString(PAGE_WIDTH - MARGIN, y - 12, now_str)
        pdf.setStrokeColor(LINE)
        pdf.line(MARGIN, y - 20, PAGE_WIDTH - MARGIN, y - 20)
        y -= 38

    def ensure_space(needed: float) -> None:
        if y - needed < BOTTOM_MARGIN:
            start_new_page()

    # 1. 顶部标题区
    _draw_single_line(pdf, "学生学情报告", MARGIN, y - 22, 23, NAVY)
    y -= 42
    _draw_single_line(pdf, f"学号：{sid}    班级：{class_name}", MARGIN, y, 10.5, SUBTLE, WIDTH - 130)
    pdf.setFont(FONT_NAME, 10)
    pdf.setFillColor(SUBTLE)
    pdf.drawRightString(PAGE_WIDTH - MARGIN, y, now_str)
    y -= 11
    pdf.setStrokeColor(LINE)
    pdf.line(MARGIN, y, PAGE_WIDTH - MARGIN, y)
    y -= 16

    # 2. 顶部总得分率与核心指标卡片
    overall_rate_val = to_float(overall.get("score_rate"))
    overall_rate_str = "-" if overall_rate_val is None else f"{overall_rate_val * 100:.1f}%"
    score_pair = f"{_number(overall.get('score'))} / {_number(overall.get('full_score'))} 分"
    summary_meta = f"知识点 {len(knowledge_points)} 个 · 错题 {len(wrong_ids)} 题"

    card_gap = 8
    card_width = (WIDTH - 2 * card_gap) / 3
    card_height = 48
    cards = (
        ("总得分率", overall_rate_str),
        ("总得分 / 满分", score_pair),
        ("学习概况", summary_meta),
    )
    for idx, (label, val) in enumerate(cards):
        cx = MARGIN + idx * (card_width + card_gap)
        pdf.setFillColor(PANEL)
        pdf.roundRect(cx, y - card_height, card_width, card_height, 6, stroke=0, fill=1)
        _draw_single_line(pdf, label, cx + 11, y - 17, 9.5, SUBTLE, card_width - 22)
        val_size = 15 if idx < 2 else 11.5
        _draw_single_line(pdf, val, cx + 11, y - 37, val_size, NAVY, card_width - 22)
    y -= card_height + 22

    # 3. 各知识点得分率（动态数量，自动分页）
    ensure_space(48)
    _draw_single_line(
        pdf,
        f"一、各知识点得分率（共 {len(knowledge_points)} 个知识点）",
        MARGIN,
        y,
        13.5,
        NAVY,
    )
    y -= 16

    if not knowledge_points:
        ensure_space(28)
        _draw_single_line(pdf, "暂无知识点记录", MARGIN, y - 12, 10.5, SUBTLE)
        y -= 28
    else:
        row_h = 24
        bar_w = 82
        bar_h = 6
        for kp in knowledge_points:
            ensure_space(row_h + 4)
            row_mid_y = y - 14
            name_text = kp.get("name") or "未命名知识点"
            theme_text = kp.get("theme_name") or ""
            label_full = f"{name_text}（{theme_text}）" if theme_text else name_text
            _draw_single_line(pdf, label_full, MARGIN + 2, row_mid_y, 10, NAVY, WIDTH - 215)

            r_val = to_float(kp.get("score_rate"))
            bar_x = PAGE_WIDTH - MARGIN - 196
            bar_y = row_mid_y + 1.5
            pdf.setFillColor(TRACK_BG)
            pdf.roundRect(bar_x, bar_y, bar_w, bar_h, 3, stroke=0, fill=1)
            if r_val is not None and r_val > 0:
                fill_w = max(3.0, min(1.0, r_val) * bar_w)
                pdf.setFillColor(_rate_bar_color(r_val))
                pdf.roundRect(bar_x, bar_y, fill_w, bar_h, 3, stroke=0, fill=1)

            score_detail = (
                f"{_number(kp.get('score'))}/{_number(kp.get('full_score'))}分"
                if kp.get("score") is not None and kp.get("full_score")
                else "未作答"
            )
            pdf.setFont(FONT_NAME, 9.5)
            pdf.setFillColor(SUBTLE)
            pdf.drawRightString(PAGE_WIDTH - MARGIN - 54, row_mid_y, score_detail)

            rate_label = "—" if r_val is None else f"{r_val * 100:.1f}%"
            pdf.setFont(FONT_NAME, 10)
            pdf.setFillColor(NAVY if r_val is not None else MUTED)
            pdf.drawRightString(PAGE_WIDTH - MARGIN, row_mid_y, rate_label)

            pdf.setStrokeColor(LINE)
            pdf.line(MARGIN, y - row_h + 3, PAGE_WIDTH - MARGIN, y - row_h + 3)
            y -= row_h

    y -= 16

    # 4. 错题列表（陈列全部错题题号，自动换行与分页）
    ensure_space(54)
    _draw_single_line(
        pdf,
        f"二、错题列表（共 {len(wrong_ids)} 题）",
        MARGIN,
        y,
        13.5,
        NAVY,
    )
    y -= 14

    if not wrong_ids:
        ensure_space(34)
        pdf.setFillColor(PANEL)
        pdf.roundRect(MARGIN, y - 28, WIDTH, 28, 6, stroke=0, fill=1)
        _draw_single_line(pdf, "暂无错题记录，表现优秀，请继续保持！", MARGIN + 12, y - 18, 10, SUBTLE)
        y -= 42
    else:
        chip_h = 20
        chip_gap_x = 7
        chip_gap_y = 7
        cur_x = MARGIN
        ensure_space(chip_h + 8)
        y -= chip_h
        for qid in wrong_ids:
            q_text = str(qid)
            chip_w = max(46.0, pdfmetrics.stringWidth(q_text, FONT_NAME, 9.5) + 18)
            if cur_x + chip_w > PAGE_WIDTH - MARGIN:
                cur_x = MARGIN
                if y - (chip_h + chip_gap_y) < BOTTOM_MARGIN:
                    start_new_page()
                    y -= chip_h
                else:
                    y -= chip_h + chip_gap_y

            pdf.setFillColor(RED_BG)
            pdf.setStrokeColor(RED_BORDER)
            pdf.roundRect(cur_x, y, chip_w, chip_h, 5, stroke=1, fill=1)
            pdf.setFont(FONT_NAME, 9.5)
            pdf.setFillColor(RED_TEXT)
            text_w = pdfmetrics.stringWidth(q_text, FONT_NAME, 9.5)
            pdf.drawString(cur_x + (chip_w - text_w) / 2, y + 6, q_text)
            cur_x += chip_w + chip_gap_x
        y -= 18

    # 5. 个性化建议（仅当 include_advice=True 时展示，完整换行跨页不截断）
    if include_advice:
        ensure_space(58)
        _draw_single_line(pdf, "三、个性化建议", MARGIN, y, 13.5, NAVY)
        y -= 12

        padding = 12
        line_h = 16.5
        advice_lines = _wrapped_lines(advice_text, WIDTH - 2 * padding, 10.5, limit=None)
        if not advice_lines:
            advice_lines = ["暂无个性化建议。"]

        idx = 0
        while idx < len(advice_lines):
            avail_h = y - BOTTOM_MARGIN
            max_fit = int((avail_h - 2 * padding) // line_h)
            if max_fit < 2:
                start_new_page()
                avail_h = y - BOTTOM_MARGIN
                max_fit = max(1, int((avail_h - 2 * padding) // line_h))

            chunk = advice_lines[idx : idx + max_fit]
            box_h = 2 * padding + len(chunk) * line_h
            box_bottom = y - box_h
            pdf.setFillColor(PANEL)
            pdf.roundRect(MARGIN, box_bottom, WIDTH, box_h, 6, stroke=0, fill=1)
            pdf.setFont(FONT_NAME, 10.5)
            pdf.setFillColor(NAVY)
            for line_i, line_str in enumerate(chunk):
                pdf.drawString(
                    MARGIN + padding,
                    y - padding - 11 - line_i * line_h,
                    line_str,
                )
            y = box_bottom - 10
            idx += len(chunk)

    draw_footer(page_no)
    pdf.showPage()
    pdf.save()


def render_student_report_bytes(report_data: dict) -> bytes:
    """将学情报告直接渲染为内存 PDF 字节流，供前端右上角一键下载。"""
    buffer = BytesIO()
    pdf = Canvas(buffer, pagesize=A4)
    _draw_report_to_canvas(pdf, report_data)
    return buffer.getvalue()


def render_student_report(
    path: Path,
    student_id: str,
    profile: StudentProfile | None,
    rows: list[dict],
    advice: str,
    wrong_questions: list[dict] | list[str] | None = None,
    knowledge_points: list[dict] | None = None,
) -> None:
    payload = _normalize_report_payload(
        student_id=student_id,
        profile=profile,
        rows=rows,
        advice=advice,
        wrong_questions=wrong_questions,
        knowledge_points=knowledge_points,
    )
    pdf = Canvas(str(path), pagesize=A4)
    _draw_report_to_canvas(pdf, payload)


def _submit_to_printer(pdf_path: Path) -> None:
    subprocess.run(
        [sys.executable, str(PRINT_SCRIPT), str(pdf_path), "--copies", "1"],
        cwd=PRINT_SCRIPT.parent,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        timeout=90,
    )


def generate_and_print_report(
    student_id: str,
    visit_id: UUID,
    profile: StudentProfile | None,
    rows: list[dict],
) -> dict:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    safe_student_id = re.sub(r"[^a-zA-Z0-9_-]", "_", student_id)[:64]
    pdf_path = REPORT_DIR / f"学情报告_{safe_student_id}_{visit_id.hex}.pdf"
    claim_path = pdf_path.with_suffix(".lock")
    try:
        claim_path.touch(exist_ok=False)
    except FileExistsError:
        return {"status": "in_progress", "filename": pdf_path.name}

    temporary_path = None
    try:
        if pdf_path.is_file():
            return {"status": "already_generated", "filename": pdf_path.name}

        base_payload = _normalize_report_payload(student_id, profile, rows, "")
        advice = resolve_student_report_advice(student_id, base_payload)
        base_payload["advice"] = advice

        with NamedTemporaryFile(dir=REPORT_DIR, suffix=".tmp", delete=False) as temporary_file:
            temporary_path = Path(temporary_file.name)
        pdf = Canvas(str(temporary_path), pagesize=A4)
        _draw_report_to_canvas(pdf, base_payload)
        temporary_path.replace(pdf_path)

        try:
            _submit_to_printer(pdf_path)
        except (OSError, subprocess.SubprocessError) as exc:
            logger.error(
                "学情报告已保存，打印脚本提交失败。%s %s",
                pdf_path.name,
                getattr(exc, "stdout", None) or exc,
            )
            return {"status": "print_failed", "filename": pdf_path.name}
        return {"status": "submitted", "filename": pdf_path.name}
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        claim_path.unlink(missing_ok=True)
