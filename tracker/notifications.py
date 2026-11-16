"""Telegram-напоминания, тихие часы, snooze и фоновый планировщик."""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from . import conditions
from .db import connect
from .stats import is_scheduled, normalize_logs
from .utils import format_amount, get_zone, iso_now, parse_date, today_local

QUIET_DEFAULT = ("22:00", "08:00")


def _hm(value: str) -> int:
    try:
        hours, minutes = value.split(":")
        return int(hours) * 60 + int(minutes)
    except (ValueError, AttributeError):
        return 0


def quiet_now(now_local: datetime, start: str, end: str) -> bool:
    if not start or not end:
        return False
    s, e = _hm(start), _hm(end)
    if s == e:
        return False
    minutes = now_local.hour * 60 + now_local.minute
    if s < e:
        return s <= minutes < e
    return minutes >= s or minutes < e


def build_reminder_text(user: dict, habit: dict) -> str:
    name = (user.get("name") or "").split(" ")[0]
    greeting = f"{name}, " if name else ""
    if habit.get("type") in ("quantity", "duration") and habit.get("target_value"):
        goal = f"Цель — {format_amount(habit['target_value'], habit.get('unit') or '')}".strip()
        return (f"{greeting}небольшое напоминание: «{habit['title']}». {goal}. "
                f"Даже частичный шаг сегодня считается.")
    return (f"{greeting}небольшое напоминание: «{habit['title']}». "
            f"Один маленький шаг — уже достаточно.")


def _telegram_config(app):
    return (app.config.get("TELEGRAM_BOT_TOKEN") or "",
            app.config.get("TELEGRAM_BOT_USERNAME") or "")


def send_telegram(app, chat_id: str, text: str, reply_markup: dict | None = None) -> tuple[str, str]:
    token, _ = _telegram_config(app)
    if not token:
        return "simulated", ""
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
        return "sent", ""
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        return "error", f"{type(exc).__name__}: {getattr(exc, 'code', '')}"


def notify_user(app, db, user: dict, text: str, habit_id: int | None = None,
                kind: str = "reminder", reply_markup: dict | None = None) -> dict:
    chat_id = user.get("telegram_id")
    status = "skipped"
    error = ""
    if chat_id:
        status, error = send_telegram(app, str(chat_id), text, reply_markup)
    db.execute(
        "INSERT INTO notifications(user_id, habit_id, channel, kind, text, status, created_at)"
        " VALUES (?, ?, 'telegram', ?, ?, ?, ?)",
        (user["id"], habit_id, kind, text[:1000], status, iso_now()),
    )
    db.commit()
    return {"status": status, "error": error}


def condition_notifier(app, db, user: dict, habit: dict | None, text: str,
                       kind: str, _dedup_key: str = "") -> None:
    """Callback для conditions.evaluate()."""
    if not user.get("telegram_id"):
        return
    notify_user(app, db, user, text, habit["id"] if habit else None,
                kind="condition", reply_markup=_snooze_markup(habit, user))


def _snooze_markup(habit: dict | None, user: dict) -> dict | None:
    if not habit:
        return None
    today = today_local(user.get("timezone")).isoformat()
    return {
        "inline_keyboard": [[
            {"text": "Отложить на 1 час", "callback_data": f"snooze:{habit['id']}:{today}"}
        ]]
    }


def _user_habits(db, user_id: int) -> list[dict]:
    rows = db.execute(
        "SELECT * FROM habits WHERE user_id = ? AND deleted_at IS NULL AND status = 'active'"
        " ORDER BY sort_order, id",
        (user_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _logs_for(db, user_id: int, date_str: str) -> dict[int, list[dict]]:
    rows = db.execute(
        "SELECT * FROM habit_logs WHERE user_id = ? AND date = ?", (user_id, date_str)
    ).fetchall()
    result: dict[int, list[dict]] = {}
    for row in rows:
        result.setdefault(row["habit_id"], []).append(dict(row))
    return result


def tick_db(db, app, now_utc: datetime | None = None) -> dict:
    now_utc = now_utc or datetime.now(timezone.utc)
    stats = {"checked": 0, "sent": 0, "skipped": 0, "simulated": 0, "errors": 0}
    users = db.execute("SELECT * FROM users").fetchall()
    for user_row in users:
        user = dict(user_row)
        user["conditions_enabled"] = conditions.enabled_settings(user)
        tz = get_zone(user.get("timezone"))
        now_local = now_utc.astimezone(tz)
        today = now_local.date()
        date_str = today.isoformat()
        habits = _user_habits(db, user["id"])
        if not habits:
            continue
        logs = _logs_for(db, user["id"], date_str)
        by_id = {habit["id"]: habit for habit in habits}

        # 1. Отложенные напоминания (snooze).
        pending = db.execute(
            "SELECT * FROM reminder_sends WHERE user_id = ? AND date = ?"
            " AND status = 'pending' AND due_at <= ?",
            (user["id"], date_str, now_utc.replace(microsecond=0).isoformat()),
        ).fetchall()
        for row in pending:
            habit = by_id.get(row["habit_id"])
            stats["checked"] += 1
            if not habit or habit.get("status") != "active":
                _finish_reminder(db, row["id"], "skipped", "привычка недоступна")
                stats["skipped"] += 1
                continue
            if logs.get(habit["id"]):
                _finish_reminder(db, row["id"], "skipped", "уже отмечено")
                stats["skipped"] += 1
                continue
            if quiet_now(now_local, user.get("quiet_hours_start"), user.get("quiet_hours_end")):
                continue
            result = notify_user(
                app, db, user, build_reminder_text(user, habit), habit["id"], "snooze",
                _snooze_markup(habit, user),
            )
            _finish_reminder(db, row["id"], result["status"], result["error"])
            stats["sent" if result["status"] == "sent" else result["status"]] = \
                stats.get(result["status"], 0) + 1

        # 2. Плановые напоминания на сегодня.
        if user.get("reminder_channel") != "none" and user.get("telegram_id"):
            if not quiet_now(now_local, user.get("quiet_hours_start"), user.get("quiet_hours_end")):
                current = now_local.hour * 60 + now_local.minute
                for habit in habits:
                    if not is_scheduled(habit, today):
                        continue
                    if logs.get(habit["id"]):
                        continue
                    if _hm(habit["reminder_time"]) > current:
                        continue
                    existing = db.execute(
                        "SELECT id FROM reminder_sends WHERE habit_id = ? AND date = ?",
                        (habit["id"], date_str),
                    ).fetchone()
                    if existing:
                        continue
                    stats["checked"] += 1
                    cursor = db.execute(
                        "INSERT INTO reminder_sends(user_id, habit_id, date, due_at, channel, status)"
                        " VALUES (?, ?, ?, ?, 'telegram', 'pending')",
                        (user["id"], habit["id"], date_str,
                         now_utc.replace(microsecond=0).isoformat()),
                    )
                    result = notify_user(
                        app, db, user, build_reminder_text(user, habit), habit["id"],
                        "reminder", _snooze_markup(habit, user),
                    )
                    _finish_reminder(db, cursor.lastrowid, result["status"], result["error"])
                    if result["status"] == "sent":
                        stats["sent"] += 1
                    elif result["status"] == "simulated":
                        stats["simulated"] += 1
                    elif result["status"] == "error":
                        stats["errors"] += 1
                    else:
                        stats["skipped"] += 1

        # 3. Условия: бейджи, мягкие напоминания, недельные рекомендации.
        all_logs: dict[int, list[dict]] = {}
        rows = db.execute(
            "SELECT * FROM habit_logs WHERE user_id = ? AND date >= ?",
            (user["id"], (today - timedelta(days=90)).isoformat()),
        ).fetchall()
        for row in rows:
            all_logs.setdefault(row["habit_id"], []).append(dict(row))
        conditions.evaluate(
            db, user, habits, all_logs, today,
            send_notification=lambda u, h, text, kind, key: condition_notifier(
                app, db, u, h, text, kind, key
            ),
        )
    return stats


def _finish_reminder(db, reminder_id: int, status: str, error: str = "") -> None:
    if status not in ("sent", "simulated", "skipped", "error"):
        status = "error" if status else "skipped"
    db.execute(
        "UPDATE reminder_sends SET status = ?, sent_at = ?, error = ? WHERE id = ?",
        (status, iso_now(), (error or "")[:300], reminder_id),
    )
    db.commit()


def tick(app, now_utc: datetime | None = None) -> dict:
    db = connect(app.config["DATABASE"])
    try:
        return tick_db(db, app, now_utc)
    finally:
        db.close()


def start_scheduler(app, interval: int = 25) -> threading.Event:
    """Фоновый цикл напоминаний. Запускается из app.py, не из WSGI-фабрики."""
    stop = threading.Event()
    if app.config.get("TESTING") or not app.config.get("SCHEDULER_ENABLED", True):
        return stop

    def loop():
        # Небольшая пауза, чтобы сервер успел подняться.
        if stop.wait(5):
            return
        while not stop.is_set():
            try:
                tick(app)
            except Exception:  # noqa: BLE001
                app.logger.exception("Reminder tick failed")
            if stop.wait(interval):
                return

    thread = threading.Thread(target=loop, name="habit-reminders", daemon=True)
    thread.start()
    return stop
