from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock
from uuid import UUID

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from agent.core.student_agent import generate_student_report_advice
from models.dataset import StudentProfile


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "printfiles"
PRINT_SCRIPT = REPO_ROOT / "打印模块" / "print_pdf" / "print_pdf_file.py"
FONT_NAME = "StudentReportChinese"
_FONT_LOCK = Lock()
logger = logging.getLogger(__name__)

PAGE_WIDTH, _ = A4
MARGIN = 38
WIDTH = PAGE_WIDTH - 2 * MARGIN
NAVY = HexColor("#16345A")
SUBTLE = HexColor("#42566D")
LINE = HexColor("#D7E0EA")
PANEL = HexColor("#F0F5FA")


def _register_font() -> None:
    with _FONT_LOCK:
        if FONT_NAME in pdfmetrics.getRegisteredFontNames():
            return
        configured_font = os.environ.get("REPORT_FONT_PATH")
        windows_fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        font_paths = [Path(configured_font)] if configured_font else [windows_fonts / "msyh.ttc", windows_fonts / "simhei.ttf"]
        for font_path in font_paths:
            if font_path.is_file():
                pdfmetrics.registerFont(TTFont(FONT_NAME, str(font_path)))
                return
        raise FileNotFoundError("未找到中文 TrueType 字体，可通过 REPORT_FONT_PATH 指定字体文件")


def _number(value) -> str:
    return "-" if value is None else f"{value:g}"


def _rate(value) -> str:
    return "-" if value is None else f"{value:.1%}"


def _wrapped_lines(text: str, width: float, size: int, limit: int) -> list[str]:
    """逐字符测量中文行宽，内容超过指定行数时在最后一行加省略号。"""
    lines = []
    line = ""
    paragraphs = (" ".join(paragraph.split()) for paragraph in text.splitlines() if paragraph.strip())
    for char in "\n".join(paragraphs):
        if char != "\n" and pdfmetrics.stringWidth(line + char, FONT_NAME, size) <= width:
            line += char
            continue
        if len(lines) == limit - 1:
            while pdfmetrics.stringWidth(line + "…", FONT_NAME, size) > width:
                line = line[:-1]
            return [*lines, line.rstrip() + "…"]
        lines.append(line)
        line = char.lstrip()
    if line:
        lines.append(line)
    return lines


def _draw_text(pdf: Canvas, text: str, x: float, y: float, size: int, color=NAVY, width: float = WIDTH) -> None:
    lines = _wrapped_lines(text, width, size, 1)
    if lines:
        pdf.setFont(FONT_NAME, size)
        pdf.setFillColor(color)
        pdf.drawString(x, y, lines[0])


def render_student_report(
    path: Path, student_id: str, profile: StudentProfile | None, rows: list[dict], advice: str,
) -> None:
    _register_font()
    pdf = Canvas(str(path), pagesize=A4)
    pdf.setTitle("学生学情报告")

    _draw_text(pdf, "学生学情报告", MARGIN, 784, 26)
    class_name = profile.class_id if profile and profile.class_id else "-"
    _draw_text(pdf, f"学号 {student_id}    班级 {class_name}", MARGIN, 761, 11, SUBTLE, WIDTH - 125)
    pdf.setFont(FONT_NAME, 10)
    pdf.setFillColor(SUBTLE)
    pdf.drawRightString(PAGE_WIDTH - MARGIN, 761, datetime.now().strftime("%Y-%m-%d %H:%M"))
    pdf.setStrokeColor(LINE)
    pdf.line(MARGIN, 748, PAGE_WIDTH - MARGIN, 748)

    score = f"{_number(profile.score_total)} / {_number(profile.full_score_total)}" if profile else "-"
    rate = _rate(profile.score_rate) if profile else "-"
    completed = f"{_number(profile.distinct_question_count)} / {_number(profile.available_question_count)}" if profile else "-"
    card_width = (WIDTH - 16) / 3
    for index, (label, value) in enumerate((("总得分", score), ("总得分率", rate), ("已作答题数", completed))):
        x = MARGIN + index * (card_width + 8)
        pdf.setFillColor(PANEL)
        pdf.roundRect(x, 691, card_width, 45, 6, stroke=0, fill=1)
        _draw_text(pdf, label, x + 10, 720, 10, SUBTLE, card_width - 20)
        _draw_text(pdf, value, x + 10, 701, 15, NAVY, card_width - 20)

    _draw_text(pdf, "主题表现", MARGIN, 667, 15)
    themes = [row for row in rows if row.get("行类型") == "theme"][:4]
    y = 646
    if not themes:
        _draw_text(pdf, "暂无主题汇总记录", MARGIN, y, 11, SUBTLE)
        y -= 24
    for row in themes:
        _draw_text(pdf, row.get("主题名称") or "未命名主题", MARGIN, y, 11, NAVY, WIDTH - 168)
        metric = f"{_number(row.get('得分'))} / {_number(row.get('满分'))} 分    {_rate(row.get('得分率'))}"
        pdf.setFont(FONT_NAME, 11)
        pdf.setFillColor(SUBTLE)
        pdf.drawRightString(PAGE_WIDTH - MARGIN, y, metric)
        pdf.setStrokeColor(LINE)
        pdf.line(MARGIN, y - 8, PAGE_WIDTH - MARGIN, y - 8)
        y -= 24

    _draw_text(pdf, "个性化建议", MARGIN, y - 5, 15)
    panel_top = y - 15
    padding = 12
    line_height = 16
    max_lines = int((panel_top - 58 - 2 * padding) / line_height)
    advice_lines = _wrapped_lines(advice, WIDTH - 2 * padding, 11, max_lines)
    panel_height = 2 * padding + len(advice_lines) * line_height
    panel_bottom = panel_top - panel_height
    pdf.setFillColor(PANEL)
    pdf.roundRect(MARGIN, panel_bottom, WIDTH, panel_height, 6, stroke=0, fill=1)
    pdf.setFont(FONT_NAME, 11)
    pdf.setFillColor(NAVY)
    for index, line in enumerate(advice_lines):
        pdf.drawString(MARGIN + padding, panel_top - padding - 11 - index * line_height, line)

    _draw_text(pdf, "学情数据来自已同步记录。学习建议由 Agent 生成。", MARGIN, panel_bottom - 19, 9, SUBTLE)
    pdf.showPage()
    pdf.save()


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


def generate_and_print_report(student_id: str, visit_id: UUID, profile: StudentProfile | None, rows: list[dict]) -> dict:
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
        try:
            advice = generate_student_report_advice(student_id)
        except Exception:
            logger.exception("学生 Agent 未能生成打印建议。")
            return {"status": "advice_failed"}
        if not advice:
            return {"status": "advice_failed"}

        with NamedTemporaryFile(dir=REPORT_DIR, suffix=".tmp", delete=False) as temporary_file:
            temporary_path = Path(temporary_file.name)
        render_student_report(temporary_path, student_id, profile, rows, advice)
        temporary_path.replace(pdf_path)

        try:
            _submit_to_printer(pdf_path)
        except (OSError, subprocess.SubprocessError) as exc:
            logger.error("学情报告已保存，打印脚本提交失败。%s %s", pdf_path.name, getattr(exc, "stdout", None) or exc)
            return {"status": "print_failed", "filename": pdf_path.name}
        return {"status": "submitted", "filename": pdf_path.name}
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        claim_path.unlink(missing_ok=True)
