"""把任意 PDF 静默打印到指定打印机（Windows / GDI）。

路径：PDF 文件 → PDFium 渲染成位图 → GDI 画到打印机画布 → 驱动转成打印机指令。

不依赖 .pdf 的文件关联，不调用 WPS / Edge / Acrobat，不弹任何窗口。

用法：
    python print_pdf_file.py --list-printers
    python print_pdf_file.py test.pdf --dry
    python print_pdf_file.py test.pdf
    python print_pdf_file.py test.pdf --printer "HP LaserJet Professional M1218nfs MFP" --dpi 600

依赖：
    pip install -r requirements.txt      # pywin32 + pypdfium2（+ Pillow）
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

try:
    import win32con
    import win32print
    import win32ui
    from PIL import Image, ImageWin
except ImportError as exc:  # 依赖没装
    print(f"[失败] 缺少依赖：{exc}")
    print("       请先执行：pip install -r requirements.txt")
    sys.exit(3)

# 默认打印机：优先读环境变量 PRINTER_NAME，其次用下面这个名字
DEFAULT_PRINTER = os.environ.get("PRINTER_NAME", "HP LaserJet Professional M1218nfs MFP")

# 打印机常见状态位（不同驱动未必都支持，取不到的按 0 处理）
STATUS_TEXT = {
    0x00000001: "暂停",
    0x00000002: "错误",
    0x00000008: "卡纸",
    0x00000010: "缺纸",
    0x00000020: "手动进纸",
    0x00000080: "离线",
    0x00040000: "门未关",
    0x000400: "缺墨粉",
}


def list_printers() -> list[str]:
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    try:
        return [d["pPrinterName"] for d in win32print.EnumPrinters(flags, None, 2)]
    except (KeyError, TypeError):
        return [p[2] for p in win32print.EnumPrinters(flags, None, 1)]


def describe_status(name: str) -> list[str]:
    try:
        h = win32print.OpenPrinter(name)
        try:
            info = win32print.GetPrinter(h, 2)
        finally:
            win32print.ClosePrinter(h)
    except Exception:
        return []
    status = info.get("Status", 0)
    return [text for bit, text in STATUS_TEXT.items() if status & bit]


def check_pdf(path: Path) -> int:
    """返回页数。文件不对就抛 SystemExit。"""
    if not path.exists():
        raise SystemExit(f"[失败] 找不到文件：{path}")
    with path.open("rb") as fh:
        if fh.read(5) != b"%PDF-":
            raise SystemExit(f"[失败] 这不是 PDF 文件：{path}")
    import pypdfium2 as pdfium

    return len(pdfium.PdfDocument(str(path)))


def render_pages(path: Path, dpi: int, pages: list[int] | None):
    """逐页渲染，一页一张 PIL 图像。"""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(path))
    total = len(doc)
    wanted = pages if pages else list(range(total))
    for i in wanted:
        if not 0 <= i < total:
            print(f"[跳过] 没有第 {i + 1} 页（共 {total} 页）")
            continue
        img = doc[i].render(scale=dpi / 72).to_pil()
        if img.mode != "RGB":
            img = img.convert("RGB")
        yield i, img


def fit_box(img_w: int, img_h: int, box_w: int, box_h: int) -> tuple[int, int, int, int]:
    """等比缩放并居中，返回 (x, y, w, h)。"""
    scale = min(box_w / img_w, box_h / img_h)
    w, h = int(img_w * scale), int(img_h * scale)
    return (box_w - w) // 2, (box_h - h) // 2, w, h


def main() -> int:
    ap = argparse.ArgumentParser(description="把 PDF 静默打印到打印机")
    ap.add_argument("pdf", nargs="?", help="PDF 文件路径")
    ap.add_argument("--printer", default=DEFAULT_PRINTER, help="打印机名字（默认取环境变量 PRINTER_NAME）")
    ap.add_argument("--dpi", type=int, default=300, help="渲染精度：300 够看，600 更细更慢")
    ap.add_argument("--pages", default="", help="只打某几页，例如 1 或 1,3")
    ap.add_argument("--copies", type=int, default=1, help="打印份数")
    ap.add_argument("--margin", type=float, default=0.0, help="四周再留白多少毫米")
    ap.add_argument("--dry", action="store_true", help="只渲染，不出纸")
    ap.add_argument("--list-printers", action="store_true", help="列出系统里的打印机")
    a = ap.parse_args()

    if a.list_printers:
        for n in list_printers():
            print(n)
        return 0

    if not a.pdf:
        print("[失败] 没给 PDF 路径。用 --help 看用法。")
        return 2

    pdf_path = Path(a.pdf)
    total = check_pdf(pdf_path)
    pages = [int(x) - 1 for x in a.pages.split(",") if x.strip()] if a.pages else None

    if a.dry:
        print(f"[信息] 文件 {pdf_path.name}，共 {total} 页，渲染 {a.dpi}dpi")
        for i, img in render_pages(pdf_path, a.dpi, pages):
            print(f"  第 {i + 1} 页 → {img.size[0]}x{img.size[1]} px")
        return 0

    if a.printer not in list_printers():
        print(f"[失败] 系统里没有这台打印机：{a.printer}")
        print("       可用的有：")
        for n in list_printers():
            print("   ", n)
        return 1

    warnings = describe_status(a.printer)
    if warnings:
        print(f"[注意] 打印机当前状态：{'、'.join(warnings)}（仍会尝试提交）")

    try:
        dc = win32ui.CreateDC()
        dc.CreatePrinterDC(a.printer)
    except Exception as exc:
        print(f"[失败] 打开打印机失败：{exc}")
        return 1

    box_w = dc.GetDeviceCaps(win32con.HORZRES)
    box_h = dc.GetDeviceCaps(win32con.VERTRES)
    if a.margin > 0:
        dpi = dc.GetDeviceCaps(win32con.LOGPIXELSX)
        cut = int(a.margin / 25.4 * dpi)
        box_w -= 2 * cut
        box_h -= 2 * cut
        offset = cut
    else:
        offset = 0

    print(f"[信息] 打印机 {a.printer}")
    print(f"[信息] 可打印区域 {box_w}x{box_h} 点，渲染 {a.dpi}dpi，共 {total} 页 x {a.copies} 份")

    started = time.time()
    dc.StartDoc(pdf_path.name)
    drawn = 0
    try:
        for _ in range(max(1, a.copies)):
            for i, img in render_pages(pdf_path, a.dpi, pages):
                dc.StartPage()
                x, y, w, h = fit_box(img.size[0], img.size[1], box_w, box_h)
                ImageWin.Dib(img).draw(dc.GetSafeHdc(), (x + offset, y + offset, w, h))
                dc.EndPage()
                drawn += 1
                print(f"[打印] 第 {i + 1} 页")
    except Exception as exc:
        print(f"[失败] 渲染或送纸出错：{exc}")
        try:
            dc.AbortDoc()
        except Exception:
            pass
        dc.DeleteDC()
        return 1
    finally:
        try:
            dc.EndDoc()
        except Exception:
            pass

    dc.DeleteDC()
    print(f"[完成] 已提交 {drawn} 页，用时 {time.time() - started:.1f} 秒。")
    print("       如果没出纸，看一眼打印机面板和打印队列。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
