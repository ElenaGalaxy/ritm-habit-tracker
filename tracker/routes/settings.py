"""Настройки, Telegram, напоминания, удаление аккаунта."""
from __future__ import annotations

import json
import secrets
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, g, jsonify, request

from ..api_helpers import get_habit, json_body, user_today
from ..db import get_db, rows_to_dicts
from ..notifications import notify_user, tick
from ..security import (
    admin_required, clear_session_cookie, login_required, public_user,
)
from ..utils import (
    ValidationError, clamp_text, get_zone, iso_now, json_loads, parse_date,
    to_int, today_local, valid_time, valid_timezone,
)

bp = Blueprint("settings", __name__)


@bp.patch("/settings")
@login_required
def update_settings():
    data = json_body()
    db = get_db()
    fields: dict = {}
    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name or len(name) > 80:
            raise ValidationError("Имя должно быть от 1 до 80 символов")
        fields["name"] = name
    if "timezone" in data:
        fields["timezone"] = valid_timezone(data.get("timezone"))
    if "quiet_hours_start" in data:
        fields["quiet_hours_start"] = valid_time(data.get("quiet_hours_start"))
    if "quiet_hours_end" in data:
        fields["quiet_hours_end"] = valid_time(data.get("quiet_hours_end"))
    if "reminder_channel" in data:
        if data["reminder_channel"] not in ("telegram", "none"):
            raise ValidationError("Канал напоминаний: telegram или none")
        fields["reminder_channel"] = data["reminder_channel"]
    if "ai_enabled" in data:
        if not isinstance(data["ai_enabled"], bool):
            raise ValidationError("ai_enabled должен быть true/false")
        fields["ai_enabled"] = 1 if data["ai_enabled"] else 0
    if "ai_consent" in data:
        if not isinstance(data["ai_consent"], bool):
            raise ValidationError("ai_consent должен быть true/false")
        fields["ai_consent"] = 1 if data["ai_consent"] else 0
    if "theme" in data:
        if data["theme"] not in ("light", "dark"):
            raise ValidationError("Тема: light или dark")
        fields["theme"] = data["theme"]
    if "goal" in data:
        fields["goal"] = clamp_text(data.get("goal"), "цель", 500)
    if not fields:
        return jsonify({"user": public_user(g.user)})
    assignments = ", ".join(f"{key} = ?" for key in fields)
    db.execute(f"UPDATE users SET {assignments} WHERE id = ?",
               (*fields.values(), g.user["id"]))
    db.commit()
    row = db.execute("SELECT * FROM users WHERE id = ?", (g.user["id"],)).fetchone()
    user = dict(row)
    user["conditions_enabled"] = json_loads(user["conditions_enabled"], {})
    return jsonify({"user": public_user(user)})


@bp.post("/telegram/connect")
@login_required
def telegram_connect():
    db = get_db()
    code = secrets.token_hex(4).upper()
    db.execute("UPDATE users SET telegram_link_code = ? WHERE id = ?", (code, g.user["id"]))
    db.commit()
    token = current_app.config.get("TELEGRAM_BOT_TOKEN") or ""
    username = (current_app.config.get("TELEGRAM_BOT_USERNAME") or "").lstrip("@")
    if token and username:
        return jsonify({
            "mode": "bot",
            "code": code,
            "bot_username": username,
            "deep_link": f"https://t.me/{username}?start={code}",
            "instruction": "Откройте бота в Telegram и нажмите «Start» — подключение произойдёт автоматически.",
        })
    return jsonify({
        "mode": "demo",
        "code": code,
        "bot_username": username or None,
        "deep_link": None,
        "instruction": "Telegram-бот не настроен на сервере (нет TELEGRAM_BOT_TOKEN). "
                       "Можно подключить демо-режим: напоминания будут сохраняться в журнале.",
    })


@bp.post("/telegram/simulate-connect")
@login_required
def telegram_simulate_connect():
    token = current_app.config.get("TELEGRAM_BOT_TOKEN") or ""
    if token and request.args.get("force") != "1":
        return jsonify({
            "error": "На сервере настроен настоящий бот. Подключите его через Telegram.",
            "code": "real_bot_configured",
        }), 409
    db = get_db()
    db.execute(
        "UPDATE users SET telegram_id = ?, telegram_connected_at = ?,"
        " telegram_link_code = NULL, reminder_channel = 'telegram' WHERE id = ?",
        (f"demo-{g.user['id']}", iso_now(), g.user["id"]),
    )
    db.commit()
    row = db.execute("SELECT * FROM users WHERE id = ?", (g.user["id"],)).fetchone()
    user = dict(row)
    user["conditions_enabled"] = json_loads(user["conditions_enabled"], {})
    notify_user(
        current_app._get_current_object(), db, user,
        f"Telegram подключён в демо-режиме. Напоминания будут появляться в журнале "
        f"и отправляться сюда, когда бот будет настроен.",
        kind="system",
    )
    return jsonify({"user": public_user(user), "connected": True, "mode": "demo"})


@bp.post("/telegram/disconnect")
@login_required
def telegram_disconnect():
    db = get_db()
    db.execute(
        "UPDATE users SET telegram_id = NULL, telegram_connected_at = NULL,"
        " telegram_link_code = NULL WHERE id = ?",
        (g.user["id"],),
    )
    db.commit()
    row = db.execute("SELECT * FROM users WHERE id = ?", (g.user["id"],)).fetchone()
    user = dict(row)
    user["conditions_enabled"] = json_loads(user["conditions_enabled"], {})
    return jsonify({"user": public_user(user), "connected": False})


def _tg_api(app, method: str, payload: dict) -> dict:
    token = app.config.get("TELEGRAM_BOT_TOKEN") or ""
    if not token:
        return {"ok": False, "description": "no token"}
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {"ok": False}


@bp.post("/telegram/webhook/<secret>")
def telegram_webhook(secret: str):
    expected = current_app.config.get("TELEGRAM_WEBHOOK_SECRET") or ""
    if expected and secret != expected:
        return jsonify({"error": "forbidden"}), 403
    app = current_app._get_current_object()
    db = get_db()
    update = request.get_json(silent=True) or {}
    message = update.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    text = (message.get("text") or "").strip()

    if chat_id and text.startswith("/start"):
        parts = text.split(maxsplit=1)
        code = parts[1].strip() if len(parts) > 1 else ""
        if code:
            row = db.execute("SELECT * FROM users WHERE telegram_link_code = ?", (code,)).fetchone()
            if row:
                db.execute(
                    "UPDATE users SET telegram_id = ?, telegram_connected_at = ?,"
                    " telegram_link_code = NULL, reminder_channel = 'telegram' WHERE id = ?",
                    (str(chat_id), iso_now(), row["id"]),
                )
                db.commit()
                from ..notifications import send_telegram

                send_telegram(
                    app, str(chat_id),
                    "Готово. Теперь я буду мягко напоминать о привычках — без давления. "
                    "Тихие часы и время напоминания можно настроить в приложении.",
                )
            else:
                from ..notifications import send_telegram

                send_telegram(app, str(chat_id),
                              "Код подключения не найден. Откройте настройки трекера "
                              "и нажмите «Подключить Telegram» ещё раз.")
        else:
            from ..notifications import send_telegram

            send_telegram(app, str(chat_id),
                          "Привет! Чтобы подключить напоминания, откройте настройки "
                          "трекера и нажмите «Подключить Telegram».")
        return jsonify({"ok": True})

    callback = update.get("callback_query") or {}
    callback_data = callback.get("data") or ""
    callback_id = callback.get("id")
    callback_chat = ((callback.get("message") or {}).get("chat") or {}).get("id")
    if callback_data.startswith("snooze:") and callback_chat:
        try:
            _, habit_id_str, date_str = callback_data.split(":", 2)
            habit_id = int(habit_id_str)
            parse_date(date_str)
        except (ValueError, ValidationError):
            return jsonify({"ok": True})
        user_row = db.execute("SELECT * FROM users WHERE telegram_id = ?",
                              (str(callback_chat),)).fetchone()
        if not user_row:
            return jsonify({"ok": True})
        habit_row = db.execute(
            "SELECT * FROM habits WHERE id = ? AND user_id = ? AND deleted_at IS NULL",
            (habit_id, user_row["id"]),
        ).fetchone()
        if not habit_row:
            return jsonify({"ok": True})
        user = dict(user_row)
        local_today = today_local(user.get("timezone")).isoformat()
        already = db.execute(
            "SELECT id FROM habit_logs WHERE habit_id = ? AND date = ?",
            (habit_id, local_today),
        ).fetchone()
        if already or date_str != local_today:
            if callback_id:
                _tg_api(app, "answerCallbackQuery", {
                    "callback_query_id": callback_id,
                    "text": "Уже отмечено или напоминание неактуально.",
                })
            return jsonify({"ok": True})
        due = datetime.now(timezone.utc) + timedelta(hours=1)
        due_raw = due.replace(microsecond=0).isoformat()
        db.execute(
            "INSERT INTO reminder_sends(user_id, habit_id, date, due_at, channel, status)"
            " VALUES (?, ?, ?, ?, 'telegram', 'pending')"
            " ON CONFLICT(habit_id, date) DO UPDATE SET due_at = excluded.due_at,"
            " status = 'pending', sent_at = NULL, error = ''",
            (user["id"], habit_id, local_today, due_raw),
        )
        db.commit()
        if callback_id:
            _tg_api(app, "answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "Напомним через час. Хорошо, что вы честны с собой.",
            })
        return jsonify({"ok": True})

    return jsonify({"ok": True})


@bp.get("/reminders")
@login_required
def reminders():
    db = get_db()
    today = user_today(g.user).isoformat()
    rows = rows_to_dicts(db.execute(
        "SELECT r.*, h.title AS habit_title FROM reminder_sends r"
        " JOIN habits h ON h.id = r.habit_id"
        " WHERE r.user_id = ? ORDER BY r.due_at DESC LIMIT 30",
        (g.user["id"],),
    ))
    notifications = rows_to_dicts(db.execute(
        "SELECT n.*, h.title AS habit_title FROM notifications n"
        " LEFT JOIN habits h ON h.id = n.habit_id"
        " WHERE n.user_id = ? ORDER BY n.id DESC LIMIT 30",
        (g.user["id"],),
    ))
    return jsonify({
        "today": today,
        "channel": g.user.get("reminder_channel"),
        "telegram_connected": bool(g.user.get("telegram_id")),
        "quiet_hours": [g.user.get("quiet_hours_start"), g.user.get("quiet_hours_end")],
        "sends": rows,
        "notifications": notifications,
    })


@bp.post("/reminders/snooze")
@login_required
def snooze():
    data = json_body()
    habit_id = to_int(data.get("habit_id"), "habit_id")
    db = get_db()
    habit = get_habit(db, g.user["id"], habit_id)
    if habit.get("status") != "active":
        return jsonify({"error": "Привычка не активна", "code": "inactive"}), 409
    today = user_today(g.user)
    existing_log = db.execute(
        "SELECT id FROM habit_logs WHERE habit_id = ? AND date = ?",
        (habit_id, today.isoformat()),
    ).fetchone()
    if existing_log:
        return jsonify({"error": "Привычка уже отмечена сегодня", "code": "already_done"}), 409
    due = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(microsecond=0).isoformat()
    db.execute(
        "INSERT INTO reminder_sends(user_id, habit_id, date, due_at, channel, status)"
        " VALUES (?, ?, ?, ?, 'telegram', 'pending')"
        " ON CONFLICT(habit_id, date) DO UPDATE SET due_at = excluded.due_at,"
        " status = 'pending', sent_at = NULL, error = ''",
        (g.user["id"], habit_id, today.isoformat(), due),
    )
    db.commit()
    return jsonify({
        "ok": True, "due_at": due, "habit_title": habit["title"],
        "message": "Напомним через час. Можно сделать маленький шаг и раньше.",
    })


@bp.post("/reminders/tick")
@admin_required
def run_tick():
    result = tick(current_app._get_current_object())
    return jsonify({"ok": True, **result})


@bp.delete("/account")
@login_required
def delete_account():
    data = json_body()
    confirm = (data.get("confirm") or "").strip().lower()
    if confirm not in ("удалить", "delete"):
        raise ValidationError("Введите слово «УДАЛИТЬ», чтобы подтвердить удаление")
    db = get_db()
    db.execute("DELETE FROM users WHERE id = ?", (g.user["id"],))
    db.commit()
    return clear_session_cookie(jsonify({
        "ok": True,
        "message": "Аккаунт и все данные удалены без возможности восстановления.",
    }))
