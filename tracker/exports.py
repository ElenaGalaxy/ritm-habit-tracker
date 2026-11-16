"""Экспорт данных пользователя: CSV, JSON."""
from __future__ import annotations

import csv
import json
from datetime import datetime
from io import StringIO
from zoneinfo import ZoneInfo

from .stats import habit_summary, normalize_logs
from .utils import iso_now, today_local

CSV_HEADER = ["date", "habit_title", "type", "value", "target", "status", "note"]


def _num(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return str(int(number)) if number.is_integer() else f"{number:g}"


def export_csv(db, user_id: int) -> str:
    rows = db.execute(
        "SELECT l.date, h.title, h.type, l.value, h.target_value, l.status, l.note"
        " FROM habit_logs l JOIN habits h ON h.id = l.habit_id"
        " WHERE l.user_id = ? ORDER BY l.date ASC, h.sort_order ASC, h.id ASC",
        (user_id,),
    ).fetchall()
    out = StringIO()
    out.write("\ufeff")  # BOM помогает Excel открыть UTF-8 корректно
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(CSV_HEADER)
    for row in rows:
        writer.writerow([
            row["date"], row["title"], row["type"], _num(row["value"]),
            _num(row["target_value"]), row["status"], row["note"] or "",
        ])
    return out.getvalue()


def export_json(db, user: dict) -> str:
    today = today_local(user.get("timezone"))
    habits = [dict(row) for row in db.execute(
        "SELECT * FROM habits WHERE user_id = ? AND deleted_at IS NULL ORDER BY sort_order, id",
        (user["id"],),
    )]
    log_rows = [dict(row) for row in db.execute(
        "SELECT * FROM habit_logs WHERE user_id = ? ORDER BY date ASC, id ASC",
        (user["id"],),
    )]
    by_habit: dict[int, list[dict]] = {}
    titles = {habit["id"]: habit["title"] for habit in habits}
    for log in log_rows:
        by_habit.setdefault(log["habit_id"], []).append(log)

    logs_out = []
    for log in log_rows:
        logs_out.append({
            "habit_id": log["habit_id"],
            "habit_title": titles.get(log["habit_id"], "—"),
            "date": log["date"],
            "value": log["value"],
            "status": log["status"],
            "note": log["note"],
            "created_at": log["created_at"],
            "updated_at": log["updated_at"],
        })

    events = [dict(row) for row in db.execute(
        "SELECT id, habit_id, type, event_key, title, message, created_at, seen_at"
        " FROM condition_events WHERE user_id = ? ORDER BY id",
        (user["id"],),
    )]
    ai_requests = []
    for row in db.execute(
        "SELECT id, type, input_text, output_json, provider, status, created_at"
        " FROM ai_requests WHERE user_id = ? ORDER BY id",
        (user["id"],),
    ):
        item = dict(row)
        try:
            item["output"] = json.loads(item.pop("output_json"))
        except (TypeError, ValueError):
            item.pop("output_json", None)
        ai_requests.append(item)

    stats = []
    for habit in habits:
        summary = habit_summary(habit, normalize_logs(by_habit.get(habit["id"], [])), today)
        summary.pop("best_weekday", None)
        stats.append({"habit_id": habit["id"], "title": habit["title"], **summary})

    payload = {
        "format": "habit-tracker-export",
        "schema_version": 1,
        "exported_at": iso_now(),
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "timezone": user["timezone"],
            "goal": user.get("goal", ""),
            "created_at": user["created_at"],
        },
        "habits": [
            {key: habit[key] for key in (
                "id", "title", "description", "icon", "color", "type", "target_value",
                "unit", "schedule", "times_per_week", "reminder_time", "status",
                "freeze_limit", "start_date", "created_at", "updated_at",
            )}
            for habit in habits
        ],
        "logs": logs_out,
        "conditions": events,
        "ai_requests": ai_requests,
        "stats": stats,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def download_name(prefix: str, extension: str, tz: str | None = None) -> str:
    try:
        zone = ZoneInfo(tz or "Europe/Moscow")
    except Exception:
        zone = ZoneInfo("Europe/Moscow")
    stamp = datetime.now(zone).strftime("%Y-%m-%d")
    return f"{prefix}-{stamp}.{extension}"
