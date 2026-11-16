"""Рендер Markdown-документа (ТЗ) в PDF через ReportLab.

Поддерживает заголовки, абзацы, списки, нумерацию, таблицы, цитаты,
код-блоки, горизонтальные линии, bold/italic/inline-code/ссылки.
Этого достаточно, чтобы PDF-версия ТЗ сохраняла структуру документа.
"""
from __future__ import annotations

import html
import re
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (
    BaseDocTemplate, Frame, HRFlowable, PageTemplate, Paragraph, Preformatted,
    Spacer, Table, TableStyle,
)

from .pdf import register_fonts

INK = colors.HexColor("#25231E")
MUTED = colors.HexColor("#777064")
LINE = colors.HexColor("#E1DCD1")
PAPER = colors.HexColor("#F7F4ED")
ACCENT = colors.HexColor("#C9623E")


def _inline(text: str, mono: str) -> str:
    text = html.escape(text.strip(), quote=False)
    codes: list[str] = []

    def stash(match):
        codes.append(match.group(1))
        return f"\x00{len(codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", stash, text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)",
                  lambda m: f'<link href="{m.group(2)}" color="#8A4B32">{m.group(1)}</link>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"~~([^~]+)~~", r"<strike>\1</strike>", text)
    for i, code in enumerate(codes):
        escaped = html.escape(code, quote=False)
        text = text.replace(
            f"\x00{i}\x00",
            f'<font name="{mono}" size="8.7" color="#7A4A33">{escaped}</font>',
        )
    return text


class NumberedCanvas(pdfcanvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            self._footer(total)
            super().showPage()
        super().save()

    def _footer(self, total: int):
        self.saveState()
        width, _ = A4
        self.setStrokeColor(LINE)
        self.setLineWidth(0.5)
        self.line(18 * mm, 15 * mm, width - 18 * mm, 15 * mm)
        self.setFont("Body", 8)
        self.setFillColor(MUTED)
        self.drawString(18 * mm, 10 * mm, "Трекер привычек · техническое задание MVP")
        self.drawRightString(width - 18 * mm, 10 * mm, f"{self._pageNumber} / {total}")
        self.restoreState()


def markdown_to_pdf(markdown_text: str) -> bytes:
    body_font, bold_font, mono = register_fonts()
    buf = BytesIO()
    doc = BaseDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=17 * mm, bottomMargin=21 * mm,
        title="ТЗ: Трекер привычек + AI-ассистент",
        author="Трекер привычек",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="doc", frames=[frame])])

    styles = {
        "kicker": ParagraphStyle(
            "kicker", fontName=bold_font, fontSize=9, leading=12,
            textColor=ACCENT, spaceAfter=3,
        ),
        "h1": ParagraphStyle(
            "h1", fontName=bold_font, fontSize=25, leading=29,
            textColor=INK, spaceBefore=4, spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "h2", fontName=bold_font, fontSize=15.5, leading=19,
            textColor=INK, spaceBefore=13, spaceAfter=5,
        ),
        "h3": ParagraphStyle(
            "h3", fontName=bold_font, fontSize=12, leading=15,
            textColor=INK, spaceBefore=9, spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "body", fontName=body_font, fontSize=10.1, leading=15.2,
            textColor=INK, spaceAfter=4,
        ),
        "lead": ParagraphStyle(
            "lead", fontName=body_font, fontSize=11, leading=16.5,
            textColor=MUTED, spaceAfter=8,
        ),
        "quote": ParagraphStyle(
            "quote", fontName=body_font, fontSize=10, leading=15,
            textColor=MUTED, leftIndent=10, borderPadding=(4, 8, 4, 8),
            backColor=colors.HexColor("#EFEBE2"), spaceBefore=2, spaceAfter=7,
        ),
        "code": ParagraphStyle(
            "code", fontName=mono, fontSize=8, leading=11,
            textColor=colors.HexColor("#3B372F"), backColor=colors.HexColor("#F0ECE3"),
            leftIndent=6, rightIndent=6, spaceBefore=3, spaceAfter=7,
            borderPadding=(5, 6, 5, 6),
        ),
        "cell": ParagraphStyle(
            "cell", fontName=body_font, fontSize=8.1, leading=10.4, textColor=INK,
        ),
        "cell_head": ParagraphStyle(
            "cell_head", fontName=bold_font, fontSize=8.1, leading=10.4, textColor=INK,
        ),
    }

    story: list = []
    lines = markdown_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    i = 0
    paragraph_buffer: list[str] = []
    list_buffer: list[tuple[str, int, str]] = []  # (kind, level, text)
    h1_seen = False

    def flush_paragraph():
        nonlocal paragraph_buffer
        if paragraph_buffer:
            text = " ".join(part.strip() for part in paragraph_buffer if part.strip())
            if text:
                style = styles["lead"] if (not h1_seen and len(story) <= 3) else styles["body"]
                story.append(Paragraph(_inline(text, mono), style))
            paragraph_buffer = []

    def flush_list():
        nonlocal list_buffer
        if not list_buffer:
            return
        for kind, level, text in list_buffer:
            if kind == "bullet":
                bullet = "•"
                left = 12 + level * 12
            else:
                bullet = kind
                left = 12 + level * 12
            style = ParagraphStyle(
                f"li{len(story)}", parent=styles["body"],
                leftIndent=left, bulletIndent=max(2, left - 9),
                spaceAfter=2.5,
            )
            story.append(Paragraph(_inline(text, mono), style, bulletText=bullet))
        list_buffer = []

    def flush_all():
        flush_paragraph()
        flush_list()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_all()
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            story.append(Preformatted("\n".join(code_lines), styles["code"]))
            i += 1
            continue

        # Таблица: строка с |, следующая — разделитель
        if stripped.startswith("|") and i + 1 < len(lines) and re.match(
            r"^\|?[\s:|-]+\|[\s:|-]*$", lines[i + 1].strip()
        ):
            flush_all()
            header_cells = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2
            rows = [header_cells]
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            max_cols = max(len(r) for r in rows)
            for r in rows:
                while len(r) < max_cols:
                    r.append("")
            weights = []
            for col in range(max_cols):
                longest = max((len(r[col]) for r in rows), default=8)
                weights.append(min(42, max(7, longest ** 0.75 * 2.2)))
            total_weight = sum(weights)
            widths = [doc.width * w / total_weight for w in weights]
            data = []
            for row_index, row in enumerate(rows):
                style = styles["cell_head"] if row_index == 0 else styles["cell"]
                data.append([Paragraph(_inline(cell, mono), style) for cell in row])
            table = Table(data, colWidths=widths, repeatRows=1, splitByRow=1)
            style_commands = [
                ("BACKGROUND", (0, 0), (-1, 0), PAPER),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.45, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FBFAF6")]),
            ]
            table.setStyle(TableStyle(style_commands))
            story += [table, Spacer(1, 4)]
            continue

        if not stripped:
            flush_all()
            i += 1
            continue

        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            flush_all()
            story.append(Spacer(1, 3))
            story.append(HRFlowable(width="100%", thickness=0.6, color=LINE,
                                    spaceBefore=3, spaceAfter=7))
            i += 1
            continue

        heading = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if heading:
            flush_all()
            level = len(heading.group(1))
            text = heading.group(2).strip()
            if level == 1 and not h1_seen:
                story.append(Paragraph("ТЕХНИЧЕСКОЕ ЗАДАНИЕ · MVP", styles["kicker"]))
                story.append(Paragraph(_inline(text, mono), styles["h1"]))
                story.append(Paragraph(
                    "Трекер привычек с Telegram-напоминаниями и AI-ассистентом",
                    styles["lead"],
                ))
                story.append(HRFlowable(width="100%", thickness=1, color=ACCENT,
                                        spaceBefore=2, spaceAfter=9))
                h1_seen = True
            elif level == 2:
                story.append(Paragraph(_inline(text, mono), styles["h2"]))
                story.append(HRFlowable(width="100%", thickness=0.5, color=LINE,
                                        spaceBefore=0, spaceAfter=4))
            else:
                story.append(Paragraph(_inline(text, mono),
                                       styles["h3"] if level == 3 else styles["body"]))
            i += 1
            continue

        if stripped.startswith(">"):
            flush_all()
            quote_lines = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote_lines.append(lines[i].strip().lstrip(">").strip())
                i += 1
            story.append(Paragraph(_inline(" ".join(quote_lines), mono), styles["quote"]))
            continue

        bullet = re.match(r"^(\s*)[-*+]\s+(.*)$", line)
        if bullet:
            flush_paragraph()
            level = len(bullet.group(1).replace("\t", "  ")) // 2
            list_buffer.append(("bullet", level, bullet.group(2)))
            i += 1
            continue

        ordered = re.match(r"^(\s*)(\d+)[.)]\s+(.*)$", line)
        if ordered:
            flush_paragraph()
            level = len(ordered.group(1).replace("\t", "  ")) // 2
            list_buffer.append((f"{ordered.group(2)}.", level, ordered.group(3)))
            i += 1
            continue

        paragraph_buffer.append(stripped)
        i += 1

    flush_all()

    if not story:
        story = [Paragraph("Документ пуст", styles["body"])]
    doc.build(story, canvasmaker=NumberedCanvas)
    return buf.getvalue()


def markdown_file_to_pdf(path: str | Path) -> bytes:
    text = Path(path).read_text(encoding="utf-8")
    return markdown_to_pdf(text)
