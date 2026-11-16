"""Статистика: серии, проценты, тепловая карта, серия последних дней."""
from __future__ import annotations

from datetime import date, timedelta

from flask import Blueprint, g, jsonify, request

from ..api_helpers import load_logs, serialize_habit, user_today
from ..db import get_db, rows_to_dicts
from ..security import login_required
from ..stats import (
    aggregate_day_status, completion, day_status, heatmap_year, is_scheduled,
    overall_summary,
)
from ..utils import ValidationError, date_range, to_int

bp = Blueprint("stats", __name__)


@bp.get("/stats")
@login_required
def stats():
    db = get_db()
    today = user_today(g.user)
    days = to_int(request.args.get("days", 30), "days")
    if not 7 <= days <= 365:
        raise ValidationError("Период статистики — от 7 до 365 дней")
    habits = rows_to_dicts(db.execute(
        "SELECT * FROM habits WHERE user_id = ? AND deleted_at IS NULL"
        " AND status IN ('active', 'paused', 'completed') ORDER BY sort_order, id",
        (g.user["id"],),
    ))
    logs = load_logs(db, g.user["id"], since=today - timedelta(days=400))
    overall = overall_summary(habits, logs, today)

    series = []
    start = today - timedelta(days=days - 1)
    for d in date_range(start, today):
        total = done = 0
        statuses = []
        for habit in habits:
            if d < date.fromisoformat(habit["start_date"]) or not is_scheduled(habit, d):
                continue
            log = next((item for item in logs.get(habit["id"], [])
                        if item["date"] == d.isoformat()), None)
            status = day_status(habit, log, d, today)
            if status == "empty":
                continue
            total += 1
            statuses.append(status)
            if status == "done":
                done += 1
        series.append({
            "date": d.isoformat(),
            "done": done,
            "total": total,
            "percent": round(done / total * 100) if total else 0,
            "status": aggregate_day_status(statuses),
        })

    return jsonify({
        "today": today.isoformat(),
        "period": {"from": start.isoformat(), "to": today.isoformat(), "days": days},
        "overview": {
            "current_streak": overall["current_streak"],
            "best_streak": overall["best_streak"],
            "week_percent": overall["week_percent"],
            "month_percent": overall["month_percent"],
            "freezes_left": overall["freezes_left"],
            "best_weekday": overall["best_weekday"],
            "total_habits": overall["total_habits"],
        },
        "habits": [
            serialize_habit(item["habit"], logs.get(item["habit"]["id"], []), today)
            for item in overall["habits"]
        ],
        "series": series,
    })


@bp.get("/stats/heatmap")
@login_required
def heatmap():
    db = get_db()
    today = user_today(g.user)
    year = to_int(request.args.get("year", today.year), "year")
    if not 2000 <= year <= 2100:
        raise ValidationError("Некорректный год")
    habits = rows_to_dicts(db.execute(
        "SELECT * FROM habits WHERE user_id = ? AND deleted_at IS NULL ORDER BY sort_order, id",
        (g.user["id"],),
    ))
    logs = load_logs(db, g.user["id"], since=date(year, 1, 1))
    days = heatmap_year(habits, logs, year, today)
    return jsonify({
        "year": year,
        "days": days,
        "summary": {
            "done": sum(day["done"] for day in days),
            "active_days": sum(1 for day in days if day["done"] > 0),
        },
    })


@bp.get("/stats/habit/<int:habit_id>")
@login_required
def habit_stats(habit_id: int):
    db = get_db()
    today = user_today(g.user)
    from ..api_helpers import get_habit

    habit = get_habit(db, g.user["id"], habit_id)
    logs = load_logs(db, g.user["id"]).get(habit_id, [])
    month_start = today.replace(day=1)
    week_start = today - timedelta(days=6)
    return jsonify({
        "habit": serialize_habit(habit, logs, today),
        "week": completion(habit, logs, week_start, today, today),
        "month": completion(habit, logs, month_start, today, today),
    })
