"""Демо-данные: кабинет блогера, администратор, шаблоны привычек."""
from __future__ import annotations

import random
from datetime import date, timedelta

from .security import hash_password
from .utils import iso_now, json_dumps, today_local

DEMO_EMAIL = "demo@treker.local"
DEMO_PASSWORD = "demo1234"
ADMIN_EMAIL = "admin@treker.local"
ADMIN_PASSWORD = "admin1234"

TZ = "Europe/Moscow"

TEMPLATES = [
    {
        "title": "Stories до 12:00", "description": "Один короткий кадр, чтобы блог оставался живым",
        "icon": "camera", "color": "#2E685F", "type": "boolean", "target_value": 1,
        "unit": "", "schedule": "daily", "times_per_week": 7,
    },
    {
        "title": "Сценарий Reels 20 минут", "description": "Спокойная работа над следующим роликом",
        "icon": "pen", "color": "#4F7D70", "type": "duration", "target_value": 20,
        "unit": "минута", "schedule": "times_per_week", "times_per_week": 5,
    },
    {
        "title": "Прогулка 30 минут", "description": "Пауза от экрана и свежая голова",
        "icon": "walk", "color": "#AD8557", "type": "duration", "target_value": 30,
        "unit": "минута", "schedule": "daily", "times_per_week": 7,
    },
    {
        "title": "Вода 6 стаканов", "description": "Базовая забота о себе в течение дня",
        "icon": "water", "color": "#5E8794", "type": "quantity", "target_value": 6,
        "unit": "стакан", "schedule": "daily", "times_per_week": 7,
    },
    {
        "title": "Без телефона после 23:00", "description": "Спокойное завершение дня без ленты",
        "icon": "moon", "color": "#7D6F7A", "type": "boolean", "target_value": 1,
        "unit": "", "schedule": "daily", "times_per_week": 7,
    },
]

DEMO_HABITS = [
    {**TEMPLATES[0], "reminder_time": "09:30", "freeze_limit": 2},
    {**TEMPLATES[1], "reminder_time": "14:00", "freeze_limit": 2},
    {**TEMPLATES[2], "reminder_time": "18:00", "freeze_limit": 2},
    {**TEMPLATES[3], "reminder_time": "11:00", "freeze_limit": 2},
    {**TEMPLATES[4], "reminder_time": "22:30", "freeze_limit": 2},
]


def ensure_templates(db) -> None:
    count = db.execute("SELECT COUNT(*) AS c FROM habit_templates").fetchone()["c"]
    if count:
        return
    for item in TEMPLATES:
        db.execute(
            "INSERT INTO habit_templates"
            " (title, description, icon, color, type, target_value, unit, schedule, times_per_week)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (item["title"], item["description"], item["icon"], item["color"], item["type"],
             item["target_value"], item["unit"], item["schedule"], item["times_per_week"]),
        )
    db.commit()


def seed_demo(db) -> bool:
    """Создаёт демо-кабинет, если пользователей ещё нет. Возвращает True при создании."""
    existing = db.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    if existing:
        return False

    now = iso_now()
    today = today_local(TZ)
    cur = db.execute(
        "INSERT INTO users(name, email, password_hash, role, timezone, goal, quiet_hours_start,"
        " quiet_hours_end, telegram_id, telegram_connected_at, reminder_channel, ai_enabled,"
        " ai_consent, conditions_enabled, theme, onboarded_at, created_at)"
        " VALUES (?, ?, ?, 'user', ?, ?, '22:00', '08:00', 'demo-chat', ?, 'telegram', 1, 0,"
        " ?, 'light', ?, ?)",
        ("Саша", DEMO_EMAIL, hash_password(DEMO_PASSWORD), TZ,
         "Вести блог 5 раз в неделю и не выгорать", now,
         json_dumps({"streak_badge": True, "missed_reminder": True, "low_week": True}),
         now, now),
    )
    user_id = cur.lastrowid

    db.execute(
        "INSERT INTO users(name, email, password_hash, role, timezone, goal,"
        " reminder_channel, conditions_enabled, theme, onboarded_at, created_at)"
        " VALUES (?, ?, ?, 'admin', ?, 'Поддержка сервиса', 'none', ?, 'light', ?, ?)",
        ("Админ", ADMIN_EMAIL, hash_password(ADMIN_PASSWORD), TZ,
         json_dumps({"streak_badge": False, "missed_reminder": False, "low_week": False}),
         now, now),
    )

    start = today - timedelta(days=74)
    habit_ids: list[int] = []
    for order, habit in enumerate(DEMO_HABITS):
        cur = db.execute(
            "INSERT INTO habits(user_id, title, description, icon, color, type, target_value,"
            " unit, schedule, times_per_week, reminder_time, status, freeze_limit,"
            " start_date, sort_order, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?)",
            (user_id, habit["title"], habit["description"], habit["icon"], habit["color"],
             habit["type"], habit["target_value"], habit["unit"], habit["schedule"],
             habit["times_per_week"], habit["reminder_time"], habit["freeze_limit"],
             start.isoformat(), order * 10, now, now),
        )
        habit_ids.append(cur.lastrowid)

    rng = random.Random(42)
    freeze_dates = {
        habit_ids[0]: {today - timedelta(days=16)},
        habit_ids[2]: {today - timedelta(days=9)},
    }
    notes = {
        (today - timedelta(days=3)): "Получилось без спешки — записала идею в заметки.",
        (today - timedelta(days=10)): "День был плотный, сделала маленький шаг.",
        (today - timedelta(days=21)): "Вернулась после паузы. Главное — не идеально.",
    }

    for offset in range(74, -1, -1):
        d = today - timedelta(days=offset)
        weekday = d.weekday()

        # Stories: стабильная ежедневная привычка
        if d in freeze_dates[habit_ids[0]]:
            _log(db, habit_ids[0], user_id, d, 0, "frozen", "Заморозка: важная съёмка")
        elif d == today:
            _log(db, habit_ids[0], user_id, d, 1, "done")
        elif rng.random() < 0.84:
            _log(db, habit_ids[0], user_id, d, 1, "done")
        elif rng.random() < 0.5:
            _log(db, habit_ids[0], user_id, d, 0, "missed")

        # Reels: 5 раз в неделю, длительность
        if weekday in (0, 1, 2, 4, 5) and rng.random() < 0.82:
            value = rng.choice([20, 20, 22, 25, 18, 15, 10])
            status = "done" if value >= 20 else "partial"
            _log(db, habit_ids[1], user_id, d, value, status)
        elif weekday in (2, 4) and rng.random() < 0.3:
            _log(db, habit_ids[1], user_id, d, rng.choice([8, 10, 12]), "partial")

        # Прогулка
        if d in freeze_dates[habit_ids[2]]:
            _log(db, habit_ids[2], user_id, d, 0, "frozen", "Заморозка: весь день в разъездах")
        elif rng.random() < 0.72:
            value = rng.choice([30, 30, 35, 40, 25])
            _log(db, habit_ids[2], user_id, d, value, "done" if value >= 30 else "partial")
        elif rng.random() < 0.6:
            _log(db, habit_ids[2], user_id, d, 0, "skipped")

        # Вода
        value = rng.choice([6, 6, 7, 5, 8, 4, 6, 3])
        status = "done" if value >= 6 else "partial"
        if rng.random() < 0.93:
            _log(db, habit_ids[3], user_id, d, value, status)

        # Телефон после 23:00
        if rng.random() < 0.62:
            _log(db, habit_ids[4], user_id, d, 1, "done")
        elif rng.random() < 0.45:
            _log(db, habit_ids[4], user_id, d, 0, "missed")

        note = notes.get(d)
        if note:
            # заметка к ближайшей привычке, отмеченной в этот день
            row = db.execute(
                "SELECT id FROM habit_logs WHERE user_id = ? AND date = ? LIMIT 1",
                (user_id, d.isoformat()),
            ).fetchone()
            if row:
                db.execute("UPDATE habit_logs SET note = ? WHERE id = ?", (note, row["id"]))

    # Сегодня оставляем место для действия: отмечены только Stories.
    db.execute(
        "DELETE FROM habit_logs WHERE user_id = ? AND date = ? AND habit_id != ?",
        (user_id, today.isoformat(), habit_ids[0]),
    )
    db.commit()
    return True


def _log(db, habit_id: int, user_id: int, d: date, value: float, status: str,
         note: str = "") -> None:
    db.execute(
        "INSERT OR REPLACE INTO habit_logs(habit_id, user_id, date, value, status, note,"
        " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (habit_id, user_id, d.isoformat(), value, status, note, iso_now(), iso_now()),
    )
