"""Экспорт: CSV, JSON, месячный PDF-отчёт."""
from __future__ import annotations

import calendar
from datetime import date, timedelta

from flask import Blueprint, current_app, g, jsonify, request, Response

from ..api_helpers import load_logs, user_today
from ..db import get_db, rows_to_dicts, log_error
from ..exports import download_name, export_csv, export_json
from ..pdf import build_month_report
from ..security import login_required
from ..utils import ValidationError, month_bounds, parse_date, to_int

bp = Blueprint("export", __name__)


def _attachment(content: bytes | str, filename: str, mimetype: str):
    if isinstance(content, str):
        content = content.encode("utf-8")
    return Response(
        content,
        content_type=mimetype,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@bp.get("/export.csv")
@login_required
def download_csv():
    db = get_db()
    content = export_csv(db, g.user["id"])
    return _attachment(content, download_name("habits", "csv", g.user.get("timezone")),
                       "text/csv; charset=utf-8")


@bp.get("/export.json")
@login_required
def download_json():
    db = get_db()
    content = export_json(db, g.user)
    return _attachment(content, download_name("habits", "json", g.user.get("timezone")),
                       "application/json; charset=utf-8")


@bp.get("/export/report.pdf")
@login_required
def download_report():
    db = get_db()
    today = user_today(g.user)
    month_param = request.args.get("month")
    if month_param:
        try:
            year_str, month_str = month_param.split("-")
            year, month = int(year_str), int(month_str)
        except (ValueError, AttributeError) as exc:
            raise ValidationError("Месяц должен быть в формате YYYY-MM") from exc
        if not 1 <= month <= 12 or not 2000 <= year <= 2100:
            raise ValidationError("Некорректный месяц")
    else:
        year, month = today.year, today.month
    first, last = month_bounds(year, month)
    habits = rows_to_dicts(db.execute(
        "SELECT * FROM habits WHERE user_id = ? AND deleted_at IS NULL"
        " AND start_date <= ? ORDER BY sort_order, id",
        (g.user["id"], last.isoformat()),
    ))
    logs = load_logs(db, g.user["id"], since=first - timedelta(days=31),
                     until=last + timedelta(days=1))
    try:
        content = build_month_report(g.user, habits, logs, year, month, today)
    except Exception as exc:  # noqa: BLE001
        log_error(db, f"PDF report error: {type(exc).__name__}: {exc}",
                  request.path, request.method, g.user["id"])
        raise
    return _attachment(content, f"report-{year}-{month:02d}.pdf", "application/pdf")
