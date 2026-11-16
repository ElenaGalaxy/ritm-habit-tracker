"""Простые условия MVP: бейдж за серию, напоминание после пропусков,
рекомендация при низком недельном выполнении.

Каждое событие логируется и срабатывает один раз (UNIQUE habit+type+event_key).
"""
from __future__ import annotations

import json
from datetime import date, timedelta

from .stats import (
    completion, current_streak, habit_start, is_scheduled, normalize_logs,
)
from .utils import iso_now

DEFAULT_SETTINGS = {"streak_badge": True, "missed_reminder": True, "low_week": True}


def _settings_dict(value) -> dict:
    """Настройки приходят то словарём, то JSON-строкой из SQLite."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def enabled_settings(user: dict) -> dict:
    settings = dict(DEFAULT_SETTINGS)
    settings.update(_settings_dict(user.get("conditions_enabled")))
    return settings


def _insert_event(db, user_id: int, habit_id: int | None, event_type: str,
                  event_key: str, title: str, message: str) -> bool:
    cursor = db.execute(
        "INSERT OR IGNORE INTO condition_events"
        " (user_id, habit_id, type, event_key, title, message, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, habit_id, event_type, event_key, title, message, iso_now()),
    )
    return cursor.rowcount > 0


def _last_scheduled_days(habit: dict, today: date, count: int = 2) -> list[date]:
    days: list[date] = []
    cursor = today - timedelta(days=1)
    start = habit_start(habit)
    guard = 0
    while cursor >= start and len(days) < count and guard < 60:
        if is_scheduled(habit, cursor):
            days.append(cursor)
        cursor -= timedelta(days=1)
        guard += 1
    return days


def evaluate(db, user: dict, habits: list[dict],
             logs_by_habit: dict[int, list[dict]], today: date,
             send_notification=None) -> list[dict]:
    settings = enabled_settings(user)
    new_events: list[dict] = []

    for habit in habits:
        if habit.get("status") not in ("active",):
            continue
        logs = normalize_logs(logs_by_habit.get(habit["id"], []))

        # 1. Серия >= 7 дней — бейдж каждые 7 дней серии.
        if settings.get("streak_badge"):
            streak = current_streak(habit, logs, today)
            milestone = (streak // 7) * 7
            if milestone >= 7:
                key = f"streak-{milestone}"
                if _insert_event(
                    db, user["id"], habit["id"], "streak_badge", key,
                    f"{milestone} дней подряд",
                    f"«{habit['title']}» держится {milestone} дней. Это уже не случайность — "
                    f"можно собой тихо гордиться.",
                ):
                    new_events.append({
                        "type": "streak_badge", "habit_id": habit["id"],
                        "title": f"{milestone} дней подряд", "event_key": key,
                    })

        # 2. Два пропущенных запланированных дня подряд.
        if settings.get("missed_reminder") and habit.get("schedule") != "times_per_week":
            days = _last_scheduled_days(habit, today, 2)
            if len(days) == 2:
                misses = 0
                for d in days:
                    log = logs.get(d.isoformat())
                    if log is None or log.get("status") in ("missed", "skipped"):
                        misses += 1
                if misses == 2:
                    key = days[0].isoformat()
                    message = ("Давно не отмечались. Вернёмся с маленького шага? "
                               "Достаточно одного действия — без давления.")
                    if _insert_event(
                        db, user["id"], habit["id"], "missed_reminder", key,
                        "Мягкое напоминание", message,
                    ):
                        new_events.append({
                            "type": "missed_reminder", "habit_id": habit["id"],
                            "title": "Вернёмся с маленького шага?", "event_key": key,
                        })
                        if send_notification:
                            send_notification(
                                user, habit, message, "condition",
                                f"missed-{habit['id']}-{key}",
                            )

        # 3. Недельное выполнение < 50% — рекомендация раз в неделю.
        if settings.get("low_week"):
            start = max(today - timedelta(days=6), habit_start(habit))
            if (today - start).days >= 2:
                stats = completion(habit, logs, start, today, today)
                if stats["expected"] >= 1 and stats["percent"] < 50:
                    iso = today.isocalendar()
                    key = f"{iso.year}-W{iso.week:02d}"
                    if _insert_event(
                        db, user["id"], habit["id"], "low_week", key,
                        "Можно сделать шаг меньше",
                        f"«{habit['title']}» выполнена примерно на {round(stats['percent'])}% за неделю. "
                        f"Это не провал — возможно, цель пока великовата. Уменьшите её "
                        f"или поставьте привычку на паузу.",
                    ):
                        new_events.append({
                            "type": "low_week", "habit_id": habit["id"],
                            "title": "Можно сделать шаг меньше", "event_key": key,
                        })
    db.commit()
    return new_events


def list_events(db, user_id: int, unseen_only: bool = False, limit: int = 40) -> list[dict]:
    sql = ("SELECT e.*, h.title AS habit_title FROM condition_events e"
           " LEFT JOIN habits h ON h.id = e.habit_id WHERE e.user_id = ?")
    params: list = [user_id]
    if unseen_only:
        sql += " AND e.seen_at IS NULL"
    sql += " ORDER BY e.id DESC LIMIT ?"
    params.append(limit)
    return [dict(row) for row in db.execute(sql, params)]


def mark_seen(db, user_id: int, event_id: int | None = None) -> None:
    if event_id:
        db.execute(
            "UPDATE condition_events SET seen_at = ? WHERE id = ? AND user_id = ?",
            (iso_now(), event_id, user_id),
        )
    else:
        db.execute(
            "UPDATE condition_events SET seen_at = ? WHERE user_id = ? AND seen_at IS NULL",
            (iso_now(), user_id),
        )
    db.commit()
