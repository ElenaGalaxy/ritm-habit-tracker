"""Общие помощники API: владение объектами, сериализация, события."""
from __future__ import annotations

from datetime import date, timedelta

from flask import current_app, request

from . import conditions
from .db import get_db, rows_to_dicts
from .notifications import condition_notifier
from .stats import (
    best_streak, current_streak, freezes_left, freezes_used, habit_start,
    habit_summary, is_scheduled, normalize_logs, streak_unit, requirement_per_week,
)
from .utils import NotFound, format_amount, plural_ru, today_local


def json_body() -> dict:
    from .utils import ValidationError

    data = request.get_json(silent=True)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValidationError("Ожидается JSON-объект")
    return data


def get_habit(db, user_id: int, habit_id: int, *, include_deleted: bool = False) -> dict:
    sql = "SELECT * FROM habits WHERE id = ? AND user_id = ?"
    if not include_deleted:
        sql += " AND deleted_at IS NULL"
    row = db.execute(sql, (habit_id, user_id)).fetchone()
    if not row:
        raise NotFound("Привычка не найдена")
    return dict(row)


def get_active_habits(db, user_id: int) -> list[dict]:
    return rows_to_dicts(db.execute(
        "SELECT * FROM habits WHERE user_id = ? AND deleted_at IS NULL AND status = 'active'"
        " ORDER BY sort_order, id",
        (user_id,),
    ))


def load_logs(db, user_id: int, since: date | None = None,
              until: date | None = None) -> dict[int, list[dict]]:
    sql = "SELECT * FROM habit_logs WHERE user_id = ?"
    params: list = [user_id]
    if since:
        sql += " AND date >= ?"
        params.append(since.isoformat())
    if until:
        sql += " AND date <= ?"
        params.append(until.isoformat())
    sql += " ORDER BY date ASC"
    result: dict[int, list[dict]] = {}
    for row in db.execute(sql, params):
        result.setdefault(row["habit_id"], []).append(dict(row))
    return result


def logs_map(logs: list[dict]) -> dict[str, dict]:
    return normalize_logs(logs)


def schedule_label(habit: dict) -> str:
    if habit.get("schedule") == "weekdays":
        return "По будням"
    if habit.get("schedule") == "times_per_week":
        n = requirement_per_week(habit)
        return f"{n} {plural_ru(n, 'раз', 'раза', 'раз')} в неделю"
    return "Каждый день"


def target_label(habit: dict) -> str:
    if habit.get("type") == "boolean":
        return "Да / нет"
    value = habit.get("target_value") or 0
    return format_amount(value, habit.get("unit") or "")


def today_status(habit: dict, log: dict | None, today: date) -> str:
    if log:
        return log.get("status", "done")
    if habit.get("status") != "active":
        return "empty"
    if not is_scheduled(habit, today):
        return "rest"
    if habit.get("schedule") == "times_per_week":
        return "empty"
    return "empty"


def serialize_habit(habit: dict, logs: list[dict], today: date, *,
                    with_summary: bool = True) -> dict:
    normalized = logs_map(logs)
    log = normalized.get(today.isoformat())
    summary = habit_summary(habit, normalized, today) if with_summary else {}
    data = {
        "id": habit["id"],
        "title": habit["title"],
        "description": habit.get("description", ""),
        "icon": habit.get("icon", "spark"),
        "color": habit.get("color", "#C9623E"),
        "type": habit["type"],
        "target_value": habit.get("target_value", 1),
        "unit": habit.get("unit", ""),
        "schedule": habit.get("schedule", "daily"),
        "times_per_week": habit.get("times_per_week", 3),
        "reminder_time": habit.get("reminder_time", "09:00"),
        "status": habit.get("status", "active"),
        "freeze_limit": habit.get("freeze_limit", 2),
        "start_date": habit.get("start_date"),
        "created_at": habit.get("created_at"),
        "schedule_label": schedule_label(habit),
        "target_label": target_label(habit),
        "today": log,
        "today_status": today_status(habit, log, today),
        "freezes_used": freezes_used(habit, normalized, today.year, today.month),
        "freezes_left": freezes_left(habit, normalized, today),
        "current_streak": summary.get("current_streak", current_streak(habit, normalized, today)),
        "best_streak": summary.get("best_streak", best_streak(habit, normalized, today)),
        "streak_unit": summary.get("streak_unit", streak_unit(habit)),
        "week_percent": summary.get("week", {}).get("percent", 0),
        "month_percent": summary.get("month", {}).get("percent", 0),
    }
    if "deleted_at" in habit:
        data["deleted_at"] = habit.get("deleted_at")
    return data


def serialize_log(log: dict, habit: dict | None = None) -> dict:
    data = {
        "id": log.get("id"),
        "habit_id": log["habit_id"],
        "date": log["date"],
        "value": log.get("value", 0),
        "status": log.get("status"),
        "note": log.get("note", ""),
        "created_at": log.get("created_at"),
        "updated_at": log.get("updated_at"),
    }
    if habit:
        data["habit_title"] = habit.get("title")
        data["type"] = habit.get("type")
        data["target_value"] = habit.get("target_value")
        data["unit"] = habit.get("unit")
    return data


def evaluate_conditions(app, db, user: dict, today: date) -> list[dict]:
    habits = get_active_habits(db, user["id"])
    logs = load_logs(db, user["id"], since=today - timedelta(days=400))
    return conditions.evaluate(
        db, user, habits, logs, today,
        send_notification=lambda u, h, text, kind, key: condition_notifier(
            app, db, u, h, text, kind, key
        ),
    )


def user_today(user: dict) -> date:
    return today_local(user.get("timezone"))


def month_key(value: str | None, today: date) -> tuple[int, int]:
    from .utils import ValidationError

    if not value:
        return today.year, today.month
    try:
        year_str, month_str = value.split("-")
        year, month = int(year_str), int(month_str)
    except (ValueError, AttributeError) as exc:
        raise ValidationError("Месяц должен быть в формате YYYY-MM") from exc
    if not (1 <= month <= 12 and 2000 <= year <= 2100):
        raise ValidationError("Некорректный месяц")
    return year, month


def current_app_ref():
    return current_app._get_current_object()
