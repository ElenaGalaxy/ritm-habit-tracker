"""PDF: шрифты с кириллицей, месячный отчёт пользователя."""
from __future__ import annotations

import calendar
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

from .stats import (
    best_streak, completion, current_streak, day_status, habit_start,
    is_scheduled, normalize_logs, streak_unit,
)

FONT_CANDIDATES = {
    "Body": [
        ("DejaVuSans.ttf", "assets/fonts/DejaVuSans.ttf"),
        ("C:/Windows/Fonts/arial.ttf", None),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", None),
        ("/Library/Fonts/Arial.ttf", None),
    ],
    "Body-Bold": [
        ("DejaVuSans-Bold.ttf", "assets/fonts/DejaVuSans-Bold.ttf"),
        ("C:/Windows/Fonts/arialbd.ttf", None),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", None),
        ("/Library/Fonts/Arial Bold.ttf", None),
    ],
    "Body-Italic": [
        ("DejaVuSans-Oblique.ttf", "assets/fonts/DejaVuSans-Oblique.ttf"),
        ("C:/Windows/Fonts/ariali.ttf", None),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf", None),
    ],
    "Body-BoldItalic": [
        ("DejaVuSans-BoldOblique.ttf", "assets/fonts/DejaVuSans-BoldOblique.ttf"),
        ("C:/Windows/Fonts/arialbi.ttf", None),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf", None),
    ],
    "Mono": [
        ("DejaVuSansMono.ttf", "assets/fonts/DejaVuSansMono.ttf"),
        ("C:/Windows/Fonts/consola.ttf", None),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", None),
    ],
}

BASE_DIR = Path(__file__).resolve().parent.parent
_FONTS_READY: set[str] = set()

INK = colors.HexColor("#25231E")
MUTED = colors.HexColor("#7A7468")
LINE = colors.HexColor("#E2DDD2")
PAPER = colors.HexColor("#F7F4ED")
ACCENT = colors.HexColor("#C9623E")

STATUS_COLORS = {
    "done": colors.HexColor("#DCE7D6"),
    "partial": colors.HexColor("#F6E5C7"),
    "frozen": colors.HexColor("#DCE6EE"),
    "skipped": colors.HexColor("#E9E6E0"),
    "missed": colors.HexColor("#EFECE5"),
    "empty": colors.HexColor("#FBFAF7"),
}
STATUS_LABELS = {
    "done": "Выполнено", "partial": "Частично", "frozen": "Заморозка",
    "skipped": "Пропуск", "missed": "Пропуск", "empty": "—",
}


BUILTIN_FALLBACK = {
    "Body": "Helvetica",
    "Body-Bold": "Helvetica-Bold",
    "Body-Italic": "Helvetica-Oblique",
    "Body-BoldItalic": "Helvetica-BoldOblique",
    "Mono": "Courier",
}


def register_fonts() -> tuple[str, str, str]:
    """Регистрирует TTF-шрифт с кириллицей. Возвращает (body, bold, mono).

    Если TTF не найден, используется встроенный Helvetica (кириллица тогда
    может не отобразиться), но приложение продолжает работать.
    """
    resolved: dict[str, str] = {}
    for name, candidates in FONT_CANDIDATES.items():
        registered = False
        for system_path, project_path in candidates:
            path = Path(project_path) if project_path else Path(system_path)
            if path.exists():
                try:
                    pdfmetrics.registerFont(TTFont(name, str(path)))
                    resolved[name] = name
                    registered = True
                    break
                except Exception:
                    continue
        if not registered:
            resolved[name] = BUILTIN_FALLBACK[name]
    if resolved["Body"] == "Body":
        try:
            pdfmetrics.registerFontFamily(
                "Body", normal="Body", bold=resolved["Body-Bold"],
                italic=resolved["Body-Italic"], boldItalic=resolved["Body-BoldItalic"],
            )
        except Exception:
            pass
    return resolved["Body"], resolved["Body-Bold"], resolved["Mono"]


def _style(name: str, font: str, size: float, leading: float | None = None,
           color=INK, **kwargs) -> ParagraphStyle:
    return ParagraphStyle(
        name, fontName=font, fontSize=size, leading=leading or size * 1.45,
        textColor=color, alignment=TA_LEFT, **kwargs,
    )


class NumberedCanvas:
    """Рисует «Страница X из Y» после сборки документа."""

    @staticmethod
    def paint(canvas, doc, footer_left: str = ""):
        canvas.saveState()
        width, _ = A4
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(20 * mm, 16 * mm, width - 20 * mm, 16 * mm)
        canvas.setFont("Body", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(20 * mm, 11 * mm, footer_left)
        canvas.drawRightString(width - 20 * mm, 11 * mm, f"Страница {doc.page}")
        canvas.restoreState()


def build_month_report(user: dict, habits: list[dict], logs_by_habit: dict[int, list[dict]],
                       year: int, month: int, today: date) -> bytes:
    body, bold, mono = register_fonts()
    buf = BytesIO()
    doc = BaseDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=22 * mm,
        title=f"Отчёт за {calendar.month_name[month]} {year}",
        author="Трекер привычек",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([
        PageTemplate(id="report", frames=[frame],
                     onPage=lambda c, d: NumberedCanvas.paint(c, d, "Трекер привычек · личный отчёт")),
    ])

    title = _style("title", bold, 24, 28)
    h2 = _style("h2", bold, 13, 17, spaceBefore=8, spaceAfter=6)
    small = _style("small", body, 9, 13, color=MUTED)
    cell = _style("cell", body, 8.5, 11)
    cell_bold = _style("cellBold", bold, 8.5, 11)

    month_name = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель", 5: "Май", 6: "Июнь",
        7: "Июль", 8: "Август", 9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
    }[month]
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    effective_end = min(last, today)

    story = [
        Paragraph("Личный отчёт", _style("kicker", bold, 9, 12, color=ACCENT)),
        Paragraph(f"{month_name} {year}", title),
        Spacer(1, 2 * mm),
        Paragraph(f"{user.get('name', 'Пользователь')} · {user.get('email', '')}", small),
        Paragraph(f"Период: {first.strftime('%d.%m.%Y')} — {last.strftime('%d.%m.%Y')}", small),
        Spacer(1, 7 * mm),
    ]

    # --- сводка
    totals = {"done": 0, "partial": 0, "frozen": 0, "skipped": 0, "missed": 0}
    habit_rows = []
    all_days: list[date] = []
    for habit in habits:
        logs = normalize_logs(logs_by_habit.get(habit["id"], []))
        stats = completion(habit, logs, first, effective_end, today)
        unit = streak_unit(habit)
        streak = current_streak(habit, logs, today)
        best = best_streak(habit, logs, today)
        expected = float(stats["expected"])
        expected_text = (
            str(int(expected)) if expected.is_integer()
            else f"{expected:.1f}".rstrip("0").rstrip(".")
        )
        habit_rows.append([
            Paragraph(habit["title"], cell_bold),
            Paragraph(str(stats["percent"]).replace(".0", "") + "%", cell),
            Paragraph(f"{stats['done']} / {expected_text}", cell),
            Paragraph(f"{streak} {('нед.' if unit == 'weeks' else 'дн.')}", cell),
            Paragraph(f"{best}", cell),
            Paragraph(str(stats["frozen"]), cell),
        ])
        for log in logs.values():
            if first.isoformat() <= log["date"] <= last.isoformat():
                status = log.get("status")
                if status in totals:
                    totals[status] += 1

    percent = 0.0
    if habit_rows:
        percent = round(
            sum(completion(habit, normalize_logs(logs_by_habit.get(habit["id"], [])),
                           first, effective_end, today)["percent"] for habit in habits)
            / len(habit_rows), 1
        )

    summary_data = [
        [Paragraph("Выполнено", cell_bold), Paragraph("Частично", cell_bold),
         Paragraph("Заморозки", cell_bold), Paragraph("Пропуски", cell_bold),
         Paragraph("Средний процент", cell_bold)],
        [Paragraph(str(totals["done"]), cell), Paragraph(str(totals["partial"]), cell),
         Paragraph(str(totals["frozen"]), cell),
         Paragraph(str(totals["missed"] + totals["skipped"]), cell),
         Paragraph(f"{percent}%", cell)],
    ]
    summary = Table(summary_data, colWidths=[doc.width / 5] * 5)
    summary.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PAPER),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.6, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
    ]))
    story += [summary, Spacer(1, 8 * mm)]

    # --- по привычкам
    story.append(Paragraph("Привычки", h2))
    if habit_rows:
        header = [Paragraph(x, cell_bold) for x in (
            "Привычка", "Доля", "Отметки", "Серия", "Лучшая", "Заморозки"
        )]
        table = Table([header] + habit_rows,
                      colWidths=[doc.width * x for x in (0.36, 0.13, 0.15, 0.12, 0.1, 0.14)],
                      repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PAPER),
            ("BOX", (0, 0), (-1, -1), 0.6, LINE),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story += [table, Spacer(1, 8 * mm)]
    else:
        story += [Paragraph("В этом месяце ещё не было привычек.", small), Spacer(1, 6 * mm)]

    # --- календарь месяца
    story.append(Paragraph("Календарь", h2))
    weekday_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    grid: list[list] = [[Paragraph(w, cell_bold) for w in weekday_names]]
    row: list = [""] * first.weekday()
    for d in range(1, last.day + 1):
        current = date(year, month, d)
        statuses = []
        for habit in habits:
            if current < habit_start(habit):
                continue
            logs = normalize_logs(logs_by_habit.get(habit["id"], []))
            status = day_status(habit, logs.get(current.isoformat()), current, today)
            if status != "empty":
                statuses.append(status)
        status = "empty"
        if statuses:
            if all(s == "done" for s in statuses):
                status = "done"
            elif any(s in ("done", "partial") for s in statuses):
                status = "partial"
            elif any(s == "frozen" for s in statuses):
                status = "frozen"
            elif any(s == "missed" for s in statuses):
                status = "missed"
            elif any(s == "skipped" for s in statuses):
                status = "skipped"
        done_count = sum(1 for s in statuses if s == "done")
        row.append(Paragraph(
            f"<b>{d}</b>{('<br/>' + str(done_count) + '/' + str(len(statuses))) if statuses else ''}",
            cell,
        ))
        if len(row) == 7:
            grid.append(row)
            row = []
    if row:
        row += [""] * (7 - len(row))
        grid.append(row)
    calendar_table = Table(grid, colWidths=[doc.width / 7] * 7, rowHeights=[9 * mm] * len(grid))
    calendar_styles = [
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
        ("BACKGROUND", (0, 0), (-1, 0), PAPER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    idx = 1
    for d in range(1, last.day + 1):
        current = date(year, month, d)
        cell_index = (first.weekday() + d - 1)
        r, c = divmod(cell_index, 7)
        status = "empty"
        statuses = []
        for habit in habits:
            if current < habit_start(habit):
                continue
            logs = normalize_logs(logs_by_habit.get(habit["id"], []))
            st = day_status(habit, logs.get(current.isoformat()), current, today)
            if st != "empty":
                statuses.append(st)
        if statuses:
            if all(s == "done" for s in statuses):
                status = "done"
            elif any(s in ("done", "partial") for s in statuses):
                status = "partial"
            elif any(s == "frozen" for s in statuses):
                status = "frozen"
            elif any(s == "skipped" for s in statuses):
                status = "skipped"
            else:
                status = "missed"
        calendar_styles.append(("BACKGROUND", (c, r), (c, r), STATUS_COLORS[status]))
    calendar_table.setStyle(TableStyle(calendar_styles))
    story += [calendar_table, Spacer(1, 4 * mm)]
    story.append(Paragraph(
        "Насыщенность отражает отметки: зелёный — выполнено, песочный — частично, "
        "голубой — заморозка, серый — пропуск. Пропуск — это пауза, а не провал.",
        small,
    ))

    # --- заметки
    notes = []
    for habit in habits:
        for log in normalize_logs(logs_by_habit.get(habit["id"], [])).values():
            if log.get("note") and first.isoformat() <= log["date"] <= last.isoformat():
                notes.append((log["date"], habit["title"], log["note"]))
    if notes:
        story += [Spacer(1, 5 * mm), Paragraph("Заметки", h2)]
        for date_str, title, note in sorted(notes):
            story.append(Paragraph(
                f"<b>{date_str}</b> · {title}: {note}", cell,
            ))

    story += [
        Spacer(1, 8 * mm),
        Paragraph(
            f"Отчёт сформирован {datetime.now().strftime('%d.%m.%Y %H:%M')}. "
            "Данные принадлежат пользователю и экспортированы по его запросу.",
            small,
        ),
    ]
    doc.build(story)
    return buf.getvalue()
