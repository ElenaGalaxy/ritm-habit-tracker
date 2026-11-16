"""Экран «Сегодня», отметки, заморозки, календарь, события условий."""
from __future__ import annotations

from datetime import date, timedelta

from flask import Blueprint, current_app, g, jsonify, request

from .. import conditions
from ..api_helpers import (
    evaluate_conditions, get_habit, json_body, load_logs, logs_map,
    schedule_label, serialize_habit, serialize_log, target_label, user_today,
)
from ..db import get_db, rows_to_dicts
from ..security import login_required
from ..stats import (
    aggregate_day_status, best_weekday, completion, day_status, freezes_left,
    freezes_used, habit_start, heatmap_year, is_scheduled, normalize_logs,
    overall_summary, status_for_value,
)
from ..utils import (
    NotFound, ValidationError, date_range, iso_now, month_bounds, parse_date,
    plural_ru, to_float, to_int,
)
from ..validation import validate_log_payload

bp = Blueprint("logs", __name__)


class FreezeLimit(Exception):
    pass


def _own_habits(db, user_id: int, *, include_archived: bool = True) -> list[dict]:
    sql = "SELECT * FROM habits WHERE user_id = ? AND deleted_at IS NULL"
    if not include_archived:
        sql += " AND status IN ('active', 'paused')"
    sql += " ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, sort_order, id"
    return rows_to_dicts(db.execute(sql, (user_id,)))


def _freeze(db, user: dict, habit: dict, d: date, note: str = "") -> dict:
    today = user_today(user)
    if d > today:
        raise ValidationError("Нельзя поставить заморозку на будущий день")
    if d < habit_start(habit):
        raise ValidationError("Дата раньше начала привычки")
    existing = db.execute(
        "SELECT * FROM habit_logs WHERE habit_id = ? AND date = ?",
        (habit["id"], d.isoformat()),
    ).fetchone()
    already = existing and existing["status"] == "frozen"
    if not already:
        used = db.execute(
            "SELECT COUNT(*) AS c FROM habit_logs WHERE habit_id = ? AND status = 'frozen'"
            " AND date LIKE ?",
            (habit["id"], f"{d.year:04d}-{d.month:02d}-%"),
        ).fetchone()["c"]
        if used >= int(habit.get("freeze_limit", 2)):
            raise FreezeLimit()
    now = iso_now()
    db.execute(
        "INSERT INTO habit_logs(habit_id, user_id, date, value, status, note, created_at, updated_at)"
        " VALUES (?, ?, ?, 0, 'frozen', ?, ?, ?)"
        " ON CONFLICT(habit_id, date) DO UPDATE SET value = 0, status = 'frozen',"
        " note = excluded.note, updated_at = excluded.updated_at",
        (habit["id"], user["id"], d.isoformat(), note[:500], now, now),
    )
    db.commit()
    return db.execute(
        "SELECT * FROM habit_logs WHERE habit_id = ? AND date = ?",
        (habit["id"], d.isoformat()),
    ).fetchone()


def _day_entries(habits: list[dict], logs_by_habit: dict[int, list[dict]], d: date,
                 today: date) -> list[dict]:
    entries = []
    for habit in habits:
        if d < habit_start(habit):
            continue
        normalized = normalize_logs(logs_by_habit.get(habit["id"], []))
        log = normalized.get(d.isoformat())
        status = day_status(habit, log, d, today)
        entries.append({
            "habit_id": habit["id"],
            "title": habit["title"],
            "color": habit["color"],
            "icon": habit["icon"],
            "type": habit["type"],
            "target_value": habit["target_value"],
            "unit": habit.get("unit", ""),
            "schedule_label": schedule_label(habit),
            "status": status,
            "value": log["value"] if log else 0,
            "note": log.get("note", "") if log else "",
            "log_id": log["id"] if log else None,
        })
    return entries


@bp.get("/today")
@login_required
def today_view():
    db = get_db()
    today = user_today(g.user)
    habits = _own_habits(db, g.user["id"], include_archived=False)
    active = [habit for habit in habits if habit["status"] == "active"]
    logs = load_logs(db, g.user["id"], since=today - timedelta(days=400))
    items = []
    for habit in active:
        habit_logs = logs.get(habit["id"], [])
        normalized = normalize_logs(habit_logs)
        has_log = today.isoformat() in normalized
        if not is_scheduled(habit, today) and not has_log:
            continue
        items.append(serialize_habit(habit, habit_logs, today))

    done = sum(1 for item in items if item["today_status"] == "done")
    partial = sum(1 for item in items if item["today_status"] == "partial")
    total = len(items)
    percent = round(done / total * 100) if total else 0
    current_best = max((item["current_streak"] for item in items), default=0)
    freezes_total = sum(item["freezes_left"] for item in items)
    unseen = conditions.list_events(db, g.user["id"], unseen_only=True, limit=5)

    tip = "Один маленький шаг сегодня — уже достаточно."
    if total and done == total:
        tip = "Всё отмечено. Можно спокойно выдохнуть — ритм важнее идеальности."
    elif percent >= 50:
        tip = "Хороший ритм. Осталось немного — без спешки."
    elif done > 0:
        tip = "Начало положено. Следующий шаг может быть совсем маленьким."
    if unseen:
        tip = unseen[0]["message"]

    reminder_candidates = [
        item["reminder_time"] for item in items
        if item["today_status"] not in ("done", "frozen", "skipped")
    ]
    return jsonify({
        "date": today.isoformat(),
        "weekday": today.weekday(),
        "name": g.user["name"],
        "goal": g.user.get("goal", ""),
        "habits": items,
        "summary": {
            "total": total,
            "done": done,
            "partial": partial,
            "remaining": max(0, total - done),
            "percent": percent,
            "freezes_left": freezes_total,
            "best_current_streak": current_best,
        },
        "tip": tip,
        "unseen_events": unseen,
        "next_reminder": min(reminder_candidates) if reminder_candidates else None,
        "telegram_connected": bool(g.user.get("telegram_id")),
    })


@bp.get("/logs")
@login_required
def list_logs():
    db = get_db()
    today = user_today(g.user)
    from_raw = request.args.get("from")
    to_raw = request.args.get("to")
    start = parse_date(from_raw) if from_raw else today - timedelta(days=30)
    end = parse_date(to_raw) if to_raw else today
    if start > end:
        raise ValidationError("Дата начала позже даты конца")
    if (end - start).days > 800:
        raise ValidationError("Слишком большой период")
    sql = ("SELECT l.*, h.title, h.type, h.target_value, h.unit FROM habit_logs l"
           " JOIN habits h ON h.id = l.habit_id"
           " WHERE l.user_id = ? AND l.date BETWEEN ? AND ?")
    params: list = [g.user["id"], start.isoformat(), end.isoformat()]
    habit_id = request.args.get("habit_id")
    if habit_id:
        params.append(to_int(habit_id, "habit_id"))
        sql += " AND l.habit_id = ?"
    sql += " ORDER BY l.date ASC, h.sort_order ASC"
    logs = []
    for row in db.execute(sql, params):
        item = dict(row)
        logs.append({
            "id": item["id"], "habit_id": item["habit_id"], "habit_title": item["title"],
            "date": item["date"], "value": item["value"], "status": item["status"],
            "note": item["note"], "type": item["type"],
            "target_value": item["target_value"], "unit": item["unit"],
            "updated_at": item["updated_at"],
        })
    return jsonify({"logs": logs, "from": start.isoformat(), "to": end.isoformat()})


@bp.post("/logs")
@login_required
def save_log():
    data = json_body()
    habit_id = to_int(data.get("habit_id"), "habit_id")
    db = get_db()
    habit = get_habit(db, g.user["id"], habit_id)
    payload = validate_log_payload(data, habit)
    today = user_today(g.user)
    d = payload["date"]
    if d > today:
        raise ValidationError("Нельзя отмечать будущий день")
    if d < habit_start(habit):
        raise ValidationError("Дата раньше начала привычки")
    status = payload["status"]
    value = payload["value"]

    if status == "frozen":
        try:
            log = _freeze(db, g.user, habit, d, payload["note"])
        except FreezeLimit:
            return jsonify({
                "error": f"Заморозки на этот месяц закончились "
                         f"({habit['freeze_limit']} из {habit['freeze_limit']}).",
                "code": "freeze_limit",
            }), 409
        events = evaluate_conditions(current_app._get_current_object(), db, g.user, today)
        habit_logs = load_logs(db, g.user["id"]).get(habit_id, [])
        return jsonify({
            "log": serialize_log(dict(log), habit),
            "habit": serialize_habit(habit, habit_logs, today),
            "events": events,
            "freezes_left": freezes_left(habit, habit_logs, d),
        })

    if status == "skipped":
        value = 0
    elif value <= 0 and status not in ("done", "frozen"):
        db.execute("DELETE FROM habit_logs WHERE habit_id = ? AND date = ?",
                   (habit_id, d.isoformat()))
        db.commit()
        habit_logs = load_logs(db, g.user["id"]).get(habit_id, [])
        return jsonify({
            "removed": True,
            "habit": serialize_habit(habit, habit_logs, today),
            "freezes_left": freezes_left(habit, habit_logs, today),
        })
    elif habit["type"] == "boolean":
        value = 1

    if status is None:
        status = status_for_value(habit, value)
    if status == "done" and value < float(habit["target_value"]):
        raise ValidationError("Отметка «выполнено» требует достижения цели. "
                              "Сохраните частичное выполнение.")

    now = iso_now()
    db.execute(
        "INSERT INTO habit_logs(habit_id, user_id, date, value, status, note, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        " ON CONFLICT(habit_id, date) DO UPDATE SET value = excluded.value,"
        " status = excluded.status, note = excluded.note, updated_at = excluded.updated_at",
        (habit_id, g.user["id"], d.isoformat(), value, status, payload["note"], now, now),
    )
    db.commit()
    log = db.execute(
        "SELECT * FROM habit_logs WHERE habit_id = ? AND date = ?", (habit_id, d.isoformat())
    ).fetchone()
    events = evaluate_conditions(current_app._get_current_object(), db, g.user, today)
    habit_logs = load_logs(db, g.user["id"]).get(habit_id, [])
    return jsonify({
        "log": serialize_log(dict(log), habit),
        "habit": serialize_habit(habit, habit_logs, today),
        "events": events,
        "freezes_left": freezes_left(habit, habit_logs, d),
    })


@bp.delete("/logs")
@login_required
def delete_log():
    db = get_db()
    habit_id = to_int(request.args.get("habit_id"), "habit_id")
    habit = get_habit(db, g.user["id"], habit_id)
    d = parse_date(request.args.get("date") or user_today(g.user).isoformat())
    db.execute("DELETE FROM habit_logs WHERE habit_id = ? AND date = ? AND user_id = ?",
               (habit_id, d.isoformat(), g.user["id"]))
    db.commit()
    habit_logs = load_logs(db, g.user["id"]).get(habit_id, [])
    events = evaluate_conditions(current_app._get_current_object(), db, g.user, user_today(g.user))
    return jsonify({
        "removed": True,
        "habit": serialize_habit(habit, habit_logs, user_today(g.user)),
        "events": events,
        "freezes_left": freezes_left(habit, habit_logs, d),
    })


@bp.post("/logs/freeze")
@login_required
def freeze_day():
    data = json_body()
    habit_id = to_int(data.get("habit_id"), "habit_id")
    d = parse_date(data.get("date") or user_today(g.user).isoformat())
    note = (data.get("note") or "").strip()[:500]
    db = get_db()
    habit = get_habit(db, g.user["id"], habit_id)
    try:
        log = _freeze(db, g.user, habit, d, note)
    except FreezeLimit:
        used = freezes_used(habit, load_logs(db, g.user["id"]).get(habit_id, []), d.year, d.month)
        return jsonify({
            "error": f"Заморозки на этот месяц закончились ({used} из {habit['freeze_limit']}).",
            "code": "freeze_limit",
            "freezes_left": 0,
        }), 409
    events = evaluate_conditions(current_app._get_current_object(), db, g.user, user_today(g.user))
    habit_logs = load_logs(db, g.user["id"]).get(habit_id, [])
    return jsonify({
        "log": serialize_log(dict(log), habit),
        "habit": serialize_habit(habit, habit_logs, user_today(g.user)),
        "events": events,
        "freezes_left": freezes_left(habit, habit_logs, d),
    })


@bp.delete("/logs/freeze")
@login_required
def unfreeze_day():
    db = get_db()
    habit_id = to_int(request.args.get("habit_id"), "habit_id")
    d = parse_date(request.args.get("date") or user_today(g.user).isoformat())
    habit = get_habit(db, g.user["id"], habit_id)
    db.execute(
        "DELETE FROM habit_logs WHERE habit_id = ? AND date = ? AND user_id = ? AND status = 'frozen'",
        (habit_id, d.isoformat(), g.user["id"]),
    )
    db.commit()
    habit_logs = load_logs(db, g.user["id"]).get(habit_id, [])
    return jsonify({
        "ok": True,
        "habit": serialize_habit(habit, habit_logs, user_today(g.user)),
        "freezes_left": freezes_left(habit, habit_logs, d),
    })


@bp.get("/calendar")
@login_required
def calendar():
    db = get_db()
    today = user_today(g.user)
    year_param = request.args.get("year")
    if year_param:
        year = to_int(year_param, "year")
        if not 2000 <= year <= 2100:
            raise ValidationError("Некорректный год")
        habits = _own_habits(db, g.user["id"])
        logs = load_logs(db, g.user["id"], since=date(year, 1, 1))
        days = heatmap_year(habits, logs, year, today)
        done_total = sum(day["done"] for day in days)
        active_days = sum(1 for day in days if day["done"] > 0)
        return jsonify({
            "mode": "year", "year": year, "days": days,
            "habits": [serialize_habit(habit, logs.get(habit["id"], []), today)
                       for habit in habits],
            "summary": {"done": done_total, "active_days": active_days,
                        "days": len(days)},
        })

    today_year, today_month = today.year, today.month
    year, month = today_year, today_month
    month_param = request.args.get("month")
    if month_param:
        try:
            year_str, month_str = month_param.split("-")
            year, month = int(year_str), int(month_str)
        except (ValueError, AttributeError) as exc:
            raise ValidationError("Месяц должен быть в формате YYYY-MM") from exc
    first, last = month_bounds(year, month)
    habits = _own_habits(db, g.user["id"])
    logs = load_logs(db, g.user["id"],
                     since=first - timedelta(days=7), until=last + timedelta(days=7))
    included = []
    for habit in habits:
        if habit_start(habit) > last:
            continue
        if habit["status"] != "active" and not logs.get(habit["id"]):
            continue
        included.append(habit)

    days = []
    for d in date_range(first, last):
        entries = _day_entries(included, logs, d, today)
        statuses = [entry["status"] for entry in entries if entry["status"] != "empty"]
        done_count = sum(1 for status in statuses if status == "done")
        days.append({
            "date": d.isoformat(),
            "day": d.day,
            "weekday": d.weekday(),
            "status": aggregate_day_status(statuses),
            "done": done_count,
            "total": len(statuses),
            "entries": entries,
            "future": d > today,
        })

    freezes = {}
    for habit in included:
        habit_logs = normalize_logs(logs.get(habit["id"], []))
        used = freezes_used(habit, habit_logs, year, month)
        freezes[habit["id"]] = {
            "used": used, "limit": habit["freeze_limit"],
            "left": max(0, habit["freeze_limit"] - used),
        }
    month_summary = {
        "done": sum(day["done"] for day in days),
        "planned": sum(day["total"] for day in days),
    }
    return jsonify({
        "mode": "month", "year": year, "month": month,
        "first_weekday": first.weekday(), "today": today.isoformat(),
        "days": days,
        "habits": [serialize_habit(habit, logs.get(habit["id"], []), today)
                   for habit in included],
        "freezes": freezes,
        "summary": month_summary,
    })


@bp.get("/calendar/day")
@login_required
def calendar_day():
    db = get_db()
    today = user_today(g.user)
    d = parse_date(request.args.get("date") or today.isoformat())
    habits = _own_habits(db, g.user["id"])
    logs = load_logs(db, g.user["id"], since=d - timedelta(days=60), until=d + timedelta(days=1))
    entries = _day_entries(habits, logs, d, today)
    freezes = {}
    for habit in habits:
        habit_logs = normalize_logs(logs.get(habit["id"], []))
        used = freezes_used(habit, habit_logs, d.year, d.month)
        freezes[habit["id"]] = {
            "used": used, "limit": habit["freeze_limit"],
            "left": max(0, habit["freeze_limit"] - used),
        }
    if d > today:
        return jsonify({"date": d.isoformat(), "future": True, "entries": [],
                        "freezes": freezes, "editable": False})
    return jsonify({
        "date": d.isoformat(),
        "weekday": d.weekday(),
        "future": False,
        "editable": d <= today,
        "entries": entries,
        "freezes": freezes,
    })


@bp.get("/events")
@login_required
def events():
    db = get_db()
    unseen = request.args.get("unseen") == "1"
    items = conditions.list_events(db, g.user["id"], unseen_only=unseen)
    return jsonify({"events": items, "unseen_count": sum(1 for e in items if not e["seen_at"])})


@bp.post("/events/seen")
@login_required
def see_events():
    data = json_body()
    event_id = data.get("id")
    db = get_db()
    conditions.mark_seen(db, g.user["id"], to_int(event_id, "id") if event_id else None)
    return jsonify({"ok": True})


@bp.get("/conditions")
@login_required
def get_conditions():
    db = get_db()
    items = conditions.list_events(db, g.user["id"], limit=20)
    return jsonify({
        "settings": conditions.enabled_settings(g.user),
        "events": items,
        "unseen_count": sum(1 for e in items if not e["seen_at"]),
    })


@bp.patch("/conditions")
@login_required
def update_conditions():
    data = json_body()
    current = conditions.enabled_settings(g.user)
    for key in ("streak_badge", "missed_reminder", "low_week"):
        if key in data:
            if not isinstance(data[key], bool):
                raise ValidationError("Значения условий должны быть true/false")
            current[key] = data[key]
    db = get_db()
    import json

    db.execute("UPDATE users SET conditions_enabled = ? WHERE id = ?",
               (json.dumps(current, ensure_ascii=False), g.user["id"]))
    db.commit()
    return jsonify({"settings": current})
