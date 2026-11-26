from __future__ import annotations

from datetime import datetime
from io import BytesIO

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen.canvas import Canvas

from utils.file_tools import to_float
from utils.student_report import (
    AMBER,
    BLUE,
    BOTTOM_MARGIN,
    FONT_NAME,
    GREEN,
    LINE,
    MARGIN,
    MUTED,
    NAVY,
    PAGE_HEIGHT,
    PAGE_WIDTH,
    PANEL,
    RED_BG,
    RED_BORDER,
    RED_TEXT,
    SUBTLE,
    TRACK_BG,
    WIDTH,
    _draw_single_line,
    _number,
    _rate_bar_color,
    _register_font,
    _wrapped_lines,
)

GREEN_BG = HexColor("#F0FDF4")
GREEN_BORDER = HexColor("#BBF7D0")
GREEN_TEXT = HexColor("#15803D")
BLUE_BG = HexColor("#EFF6FF")
AMBER_BG = HexColor("#FFFBEB")


def _fmt_score(value) -> str:
    num = to_float(value)
    if num is None:
        return "—"
    if float(num).is_integer():
        return str(int(num))
    return f"{num:.2f}".rstrip("0").rstrip(".")


def _fmt_pct(value) -> str:
    rate = to_float(value)
    return "暂未作答" if rate is None else f"{rate * 100:.1f}%"


def build_class_report_summary(report_data: dict) -> str:
    """根据班级真实学情生成结构化总结：包含平均成绩、掌握最好与最差知识点。"""
    cid = str(report_data.get("class_id") or "-").strip()
    overall = report_data.get("overall") or {}
    best_list = report_data.get("best_knowledge_points") or []
    worst_list = report_data.get("worst_knowledge_points") or []
    kps = report_data.get("knowledge_points") or []

    student_count = overall.get("student_count") or 0
    avg_score = _fmt_score(overall.get("avg_score"))
    max_score = _fmt_score(overall.get("max_score"))
    min_score = _fmt_score(overall.get("min_score"))
    overall_pct = _fmt_pct(overall.get("overall_score_rate"))
    total_score = _number(overall.get("total_score"))
    total_full = _number(overall.get("total_full_score"))

    p1 = (
        f"1. 班级平均成绩概况：{cid} 班共有学生 {student_count} 人，班级平均成绩为 {avg_score} 分"
        f"（最高分 {max_score} 分，最低分 {min_score} 分），"
        f"班级整体总得分率为 {overall_pct}（累计得分 {total_score}/{total_full} 分）。"
    )

    if best_list:
        best_names = "、".join(f"「{item.get('name')}」" for item in best_list)
        first_best = best_list[0]
        best_pct = _fmt_pct(first_best.get("score_rate"))
        best_detail = f"{_number(first_best.get('score'))}/{_number(first_best.get('full_score'))} 分"
        p2 = (
            f"2. 掌握最好的知识点：本班掌握情况最好的是 {best_names}，"
            f"班级得分率达 {best_pct}（班级累计得分 {best_detail}），整体基础较为扎实。"
        )
    else:
        p2 = "2. 掌握最好的知识点：当前暂无已作答的知识点得分记录。"

    if worst_list:
        first_worst = worst_list[0]
        if best_list and abs(float(best_list[0].get("score_rate") or 0) - float(first_worst.get("score_rate") or 0)) < 1e-6:
            p3 = "3. 掌握最差的知识点：各已测知识点得分率一致，班级整体掌握程度较为均衡，建议结合教材稳步推进综合练习。"
        else:
            worst_names = "、".join(f"「{item.get('name')}」" for item in worst_list)
            worst_pct = _fmt_pct(first_worst.get("score_rate"))
            worst_detail = f"{_number(first_worst.get('score'))}/{_number(first_worst.get('full_score'))} 分"
            scope = first_worst.get("textbook_scope")
            scope_hint = f"，对应教材范围为 {scope}" if scope else ""
            unans_cnt = sum(1 for k in kps if k.get("score_rate") is None)
            unans_hint = f"；另有 {unans_cnt} 个知识点暂未开展作答" if unans_cnt > 0 else ""
            p3 = (
                f"3. 掌握最差的知识点：本班掌握情况最差的是 {worst_names}，"
                f"班级得分率为 {worst_pct}（班级累计得分 {worst_detail}{scope_hint}）{unans_hint}，"
                "建议优先围绕该知识点梳理共性易错步骤并安排针对性讲评巩固。"
            )
    else:
        p3 = "3. 掌握最差的知识点：当前暂无可对比的薄弱知识点数据。"

    return "\n".join([p1, p2, p3])


def _draw_pill(
    pdf: Canvas,
    text: str,
    x: float,
    y: float,
    w: float,
    h: float,
    bg_color,
    text_color,
    border_color=None,
) -> None:
    pdf.setFillColor(bg_color)
    if border_color is not None:
        pdf.setStrokeColor(border_color)
        pdf.roundRect(x, y, w, h, 4, stroke=1, fill=1)
    else:
        pdf.roundRect(x, y, w, h, 4, stroke=0, fill=1)
    pdf.setFont(FONT_NAME, 8.2)
    pdf.setFillColor(text_color)
    tw = pdfmetrics.stringWidth(text, FONT_NAME, 8.2)
    pdf.drawString(x + max(2.0, (w - tw) / 2), y + 3.6, text)


def _draw_class_report_to_canvas(pdf: Canvas, report_data: dict) -> None:
    _register_font()
    cid = str(report_data.get("class_id") or "-").strip()
    overall = report_data.get("overall") or {}
    knowledge_points = report_data.get("knowledge_points") or []
    best_kps = report_data.get("best_knowledge_points") or []
    worst_kps = report_data.get("worst_knowledge_points") or []
    summary_text = report_data.get("summary") or build_class_report_summary(report_data)

    student_count = overall.get("student_count") or 0
    scored_kp_count = overall.get("scored_knowledge_point_count") or 0
    excellent_cnt = overall.get("excellent_count") or 0
    good_cnt = overall.get("good_count") or 0
    weak_cnt = overall.get("weak_count") or 0

    pdf.setTitle(f"班级学情报告_{cid}")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    page_no = 1
    y = PAGE_HEIGHT - MARGIN

    def draw_footer(pno: int) -> None:
        pdf.setFont(FONT_NAME, 8.5)
        pdf.setFillColor(MUTED)
        pdf.drawString(MARGIN, 22, "班级学情数据来自已同步作答记录 · 智教慧学教学分析报告")
        pdf.drawRightString(PAGE_WIDTH - MARGIN, 22, f"第 {pno} 页")

    def start_new_page() -> None:
        nonlocal page_no, y
        draw_footer(page_no)
        pdf.showPage()
        page_no += 1
        y = PAGE_HEIGHT - MARGIN
        _draw_single_line(pdf, f"班级学情报告 · {cid} 班", MARGIN, y - 12, 10, MUTED, WIDTH - 120)
        pdf.setFont(FONT_NAME, 9.5)
        pdf.setFillColor(MUTED)
        pdf.drawRightString(PAGE_WIDTH - MARGIN, y - 12, now_str)
        pdf.setStrokeColor(LINE)
        pdf.line(MARGIN, y - 20, PAGE_WIDTH - MARGIN, y - 20)
        y -= 38

    def ensure_space(needed: float) -> None:
        if y - needed < BOTTOM_MARGIN:
            start_new_page()

    # 1. 顶部标题栏
    _draw_single_line(pdf, "班级学情报告", MARGIN, y - 22, 23, NAVY)
    y -= 42
    _draw_single_line(
        pdf,
        f"班级：{cid} · 班级人数：{student_count} 人",
        MARGIN,
        y,
        10.5,
        SUBTLE,
        WIDTH - 130,
    )
    pdf.setFont(FONT_NAME, 10)
    pdf.setFillColor(SUBTLE)
    pdf.drawRightString(PAGE_WIDTH - MARGIN, y, now_str)
    y -= 11
    pdf.setStrokeColor(LINE)
    pdf.line(MARGIN, y, PAGE_WIDTH - MARGIN, y)
    y -= 15

    # 2. 顶部核心指标卡片（重点突出班级平均成绩、整体得分率与掌握概况）
    avg_score_str = f"{_fmt_score(overall.get('avg_score'))} 分"
    score_range_str = f"最高 {_fmt_score(overall.get('max_score'))} 分 · 最低 {_fmt_score(overall.get('min_score'))} 分"

    overall_rate_val = to_float(overall.get("overall_score_rate"))
    overall_rate_str = "—" if overall_rate_val is None else f"{overall_rate_val * 100:.1f}%"
    total_pair_str = f"总得分 {_number(overall.get('total_score'))} / {_number(overall.get('total_full_score'))} 分"

    kp_overview_main = f"已测 {scored_kp_count} / {len(knowledge_points)} 个"
    kp_overview_sub = f"优秀 {excellent_cnt} · 良好 {good_cnt} · 待加强 {weak_cnt}"

    card_gap = 8
    card_width = (WIDTH - 2 * card_gap) / 3
    card_height = 56
    cards = (
        ("班级平均成绩", avg_score_str, score_range_str, 15.5),
        ("班级整体得分率", overall_rate_str, total_pair_str, 15.5),
        ("知识点掌握分布", kp_overview_main, kp_overview_sub, 13.0),
    )
    for idx, (label, main_val, sub_val, main_size) in enumerate(cards):
        cx = MARGIN + idx * (card_width + card_gap)
        pdf.setFillColor(PANEL)
        pdf.roundRect(cx, y - card_height, card_width, card_height, 6, stroke=0, fill=1)
        _draw_single_line(pdf, label, cx + 11, y - 15, 9.2, SUBTLE, card_width - 22)
        _draw_single_line(pdf, main_val, cx + 11, y - 34, main_size, NAVY, card_width - 22)
        _draw_single_line(pdf, sub_val, cx + 11, y - 48, 8.3, MUTED, card_width - 22)
    y -= card_height + 20

    # 3. 一、最值知识点对比与班级学情总结
    ensure_space(130)
    _draw_single_line(pdf, "一、班级学情总结（最好与最差知识点及平均成绩）", MARGIN, y, 13.5, NAVY)
    y -= 13

    half_gap = 10
    half_w = (WIDTH - half_gap) / 2
    hl_h = 62

    # 左卡：掌握情况最好的知识点
    lx = MARGIN
    pdf.setFillColor(GREEN_BG)
    pdf.setStrokeColor(GREEN_BORDER)
    pdf.roundRect(lx, y - hl_h, half_w, hl_h, 6, stroke=1, fill=1)
    _draw_single_line(pdf, "掌握情况最好的知识点", lx + 11, y - 16, 9.2, GREEN_TEXT, half_w - 80)
    if best_kps:
        b0 = best_kps[0]
        b_rate_str = _fmt_pct(b0.get("score_rate"))
        pdf.setFont(FONT_NAME, 11.5)
        pdf.setFillColor(GREEN_TEXT)
        pdf.drawRightString(lx + half_w - 11, y - 16, b_rate_str)
        b_names = "、".join(item.get("name") or "-" for item in best_kps)
        _draw_single_line(pdf, b_names, lx + 11, y - 35, 10.5, NAVY, half_w - 22)
        b_meta = (
            f"主题：{b0.get('theme_name') or '—'} · "
            f"得分 {_number(b0.get('score'))}/{_number(b0.get('full_score'))} 分 · "
            f"作答 {b0.get('recorded_students') or 0}/{b0.get('student_count') or student_count} 人"
        )
        _draw_single_line(pdf, b_meta, lx + 11, y - 51, 8.5, SUBTLE, half_w - 22)
    else:
        _draw_single_line(pdf, "暂无作答记录", lx + 11, y - 38, 10, MUTED, half_w - 22)

    # 右卡：掌握情况最差的知识点
    rx = MARGIN + half_w + half_gap
    pdf.setFillColor(RED_BG)
    pdf.setStrokeColor(RED_BORDER)
    pdf.roundRect(rx, y - hl_h, half_w, hl_h, 6, stroke=1, fill=1)
    _draw_single_line(pdf, "掌握情况最差的知识点", rx + 11, y - 16, 9.2, RED_TEXT, half_w - 80)
    if worst_kps:
        w0 = worst_kps[0]
        w_rate_str = _fmt_pct(w0.get("score_rate"))
        pdf.setFont(FONT_NAME, 11.5)
        pdf.setFillColor(RED_TEXT)
        pdf.drawRightString(rx + half_w - 11, y - 16, w_rate_str)
        w_names = "、".join(item.get("name") or "-" for item in worst_kps)
        _draw_single_line(pdf, w_names, rx + 11, y - 35, 10.5, NAVY, half_w - 22)
        w_meta = (
            f"主题：{w0.get('theme_name') or '—'} · "
            f"得分 {_number(w0.get('score'))}/{_number(w0.get('full_score'))} 分 · "
            f"作答 {w0.get('recorded_students') or 0}/{w0.get('student_count') or student_count} 人"
        )
        _draw_single_line(pdf, w_meta, rx + 11, y - 51, 8.5, SUBTLE, half_w - 22)
    else:
        _draw_single_line(pdf, "暂无作答记录", rx + 11, y - 38, 10, MUTED, half_w - 22)

    y -= hl_h + 10

    # 总结文字面板（支持自动跨页换行）
    padding = 11
    line_h = 15.5
    summary_lines = _wrapped_lines(summary_text, WIDTH - 2 * padding, 9.8, limit=None)
    idx = 0
    while idx < len(summary_lines):
        avail_h = y - BOTTOM_MARGIN
        max_fit = int((avail_h - 2 * padding) // line_h)
        if max_fit < 2:
            start_new_page()
            avail_h = y - BOTTOM_MARGIN
            max_fit = max(1, int((avail_h - 2 * padding) // line_h))

        chunk = summary_lines[idx : idx + max_fit]
        box_h = 2 * padding + len(chunk) * line_h
        box_bottom = y - box_h
        pdf.setFillColor(PANEL)
        pdf.roundRect(MARGIN, box_bottom, WIDTH, box_h, 6, stroke=0, fill=1)
        pdf.setFont(FONT_NAME, 9.8)
        pdf.setFillColor(NAVY)
        for line_i, line_str in enumerate(chunk):
            pdf.drawString(MARGIN + padding, y - padding - 10.5 - line_i * line_h, line_str)
        y = box_bottom - 18
        idx += len(chunk)

    # 4. 二、各知识点掌握情况明细（支持动态数量与自动跨页）
    ensure_space(48)
    _draw_single_line(
        pdf,
        f"二、各知识点掌握情况明细（共 {len(knowledge_points)} 个知识点）",
        MARGIN,
        y,
        13.5,
        NAVY,
    )
    y -= 15

    if not knowledge_points:
        ensure_space(28)
        _draw_single_line(pdf, "暂无班级知识点记录", MARGIN, y - 12, 10.5, SUBTLE)
    else:
        row_h = 24
        bar_x = MARGIN + 284
        bar_w = 60
        bar_h = 6
        pill_x = MARGIN + 350
        pill_w = 42
        pill_h = 14

        for kp in knowledge_points:
            ensure_space(row_h + 4)
            row_mid_y = y - 14
            name_text = kp.get("name") or "未命名知识点"
            theme_text = kp.get("theme_name") or ""
            label_full = f"{name_text}（{theme_text}）" if theme_text else name_text
            _draw_single_line(pdf, label_full, MARGIN + 2, row_mid_y, 9.5, NAVY, 276)

            r_val = to_float(kp.get("score_rate"))
            bar_y = row_mid_y + 1.5
            pdf.setFillColor(TRACK_BG)
            pdf.roundRect(bar_x, bar_y, bar_w, bar_h, 3, stroke=0, fill=1)
            if r_val is not None and r_val > 0:
                fill_w = max(3.0, min(1.0, r_val) * bar_w)
                pdf.setFillColor(_rate_bar_color(r_val))
                pdf.roundRect(bar_x, bar_y, fill_w, bar_h, 3, stroke=0, fill=1)

            if kp.get("is_best"):
                _draw_pill(pdf, "最好", pill_x, row_mid_y - 2.5, pill_w, pill_h, GREEN_BG, GREEN_TEXT, GREEN_BORDER)
            elif kp.get("is_worst"):
                _draw_pill(pdf, "最差", pill_x, row_mid_y - 2.5, pill_w, pill_h, RED_BG, RED_TEXT, RED_BORDER)
            elif r_val is None:
                _draw_pill(pdf, "未作答", pill_x, row_mid_y - 2.5, pill_w, pill_h, PANEL, MUTED)
            elif r_val >= 0.8:
                _draw_pill(pdf, "优秀", pill_x, row_mid_y - 2.5, pill_w, pill_h, GREEN_BG, GREEN_TEXT)
            elif r_val >= 0.6:
                _draw_pill(pdf, "良好", pill_x, row_mid_y - 2.5, pill_w, pill_h, BLUE_BG, BLUE)
            else:
                _draw_pill(pdf, "待加强", pill_x, row_mid_y - 2.5, pill_w, pill_h, AMBER_BG, AMBER)

            score_detail = (
                f"{_number(kp.get('score'))}/{_number(kp.get('full_score'))}分"
                if kp.get("score") is not None and kp.get("full_score")
                else "未作答"
            )
            pdf.setFont(FONT_NAME, 9.0)
            pdf.setFillColor(SUBTLE)
            pdf.drawRightString(PAGE_WIDTH - MARGIN - 48, row_mid_y, score_detail)

            rate_label = "—" if r_val is None else f"{r_val * 100:.1f}%"
            pdf.setFont(FONT_NAME, 9.8)
            pdf.setFillColor(NAVY if r_val is not None else MUTED)
            pdf.drawRightString(PAGE_WIDTH - MARGIN, row_mid_y, rate_label)

            pdf.setStrokeColor(LINE)
            pdf.line(MARGIN, y - row_h + 3, PAGE_WIDTH - MARGIN, y - row_h + 3)
            y -= row_h

    draw_footer(page_no)
    pdf.showPage()
    pdf.save()


def render_class_report_bytes(report_data: dict) -> bytes:
    """将班级学情报告渲染为内存 PDF 字节流，供教师端成绩单页面一键下载。"""
    buffer = BytesIO()
    pdf = Canvas(buffer, pagesize=A4)
    _draw_class_report_to_canvas(pdf, report_data)
    return buffer.getvalue()
