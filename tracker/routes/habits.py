"""CRUD привычек, лимит активных, архив, удаление с восстановлением."""
from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from ..api_helpers import (
    get_habit, json_body, load_logs, serialize_habit, user_today,
)
from ..db import get_db, rows_to_dicts
from ..security import login_required
from ..utils import NotFound, ValidationError, iso_now
from ..validation import MAX_ACTIVE_HABITS, validate_habit_payload

bp = Blueprint("habits", __name__)


def _active_count(db, user_id: int, exclude_id: int | None = None) -> int:
    if exclude_id:
        row = db.execute(
            "SELECT COUNT(*) AS c FROM habits WHERE user_id = ? AND status = 'active'"
            " AND deleted_at IS NULL AND id != ?",
            (user_id, exclude_id),
        ).fetchone()
    else:
        row = db.execute(
            "SELECT COUNT(*) AS c FROM habits WHERE user_id = ? AND status = 'active'"
            " AND deleted_at IS NULL",
            (user_id,),
        ).fetchone()
    return row["c"]


def _insert_habit(db, user_id: int, payload: dict, start_date: str, sort_order: int) -> int:
    if payload.get("type") != "boolean" and not payload.get("unit"):
        payload["unit"] = "раз"
    now = iso_now()
    cur = db.execute(
        "INSERT INTO habits(user_id, title, description, icon, color, type, target_value,"
        " unit, schedule, times_per_week, reminder_time, status, freeze_limit,"
        " start_date, sort_order, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, payload["title"], payload.get("description", ""), payload.get("icon", "spark"),
         payload.get("color", "#C9623E"), payload["type"], payload["target_value"],
         payload.get("unit", ""), payload["schedule"], payload.get("times_per_week", 3),
         payload.get("reminder_time", "09:00"), payload.get("status", "active"),
         payload.get("freeze_limit", 2), start_date, sort_order, now, now),
    )
    return cur.lastrowid


@bp.get("/habits")
@login_required
def list_habits():
    status = request.args.get("status", "active")
    include_deleted = request.args.get("include_deleted") == "1"
    db = get_db()
    sql = "SELECT * FROM habits WHERE user_id = ?"
    params: list = [g.user["id"]]
    if status != "all":
        if status not in ("active", "paused", "completed", "archived"):
            raise ValidationError("Недопустимый фильтр статуса")
        sql += " AND status = ?"
        params.append(status)
    if not include_deleted:
        sql += " AND deleted_at IS NULL"
    sql += " ORDER BY sort_order, id"
    habits = rows_to_dicts(db.execute(sql, params))
    logs = load_logs(db, g.user["id"])
    today = user_today(g.user)
    return jsonify({
        "habits": [serialize_habit(habit, logs.get(habit["id"], []), today) for habit in habits],
        "active_count": _active_count(db, g.user["id"]),
        "active_limit": MAX_ACTIVE_HABITS,
    })


@bp.get("/habits/<int:habit_id>")
@login_required
def get_one(habit_id: int):
    db = get_db()
    habit = get_habit(db, g.user["id"], habit_id)
    logs = load_logs(db, g.user["id"])
    return jsonify({"habit": serialize_habit(habit, logs.get(habit_id, []), user_today(g.user))})


@bp.post("/habits")
@login_required
def create_habit():
    data = json_body()
    payload = validate_habit_payload(data)
    db = get_db()
    if payload.get("status", "active") == "active" and \
            _active_count(db, g.user["id"]) >= MAX_ACTIVE_HABITS:
        return jsonify({
            "error": f"В MVP можно вести не более {MAX_ACTIVE_HABITS} активных привычек. "
                     "Поставьте одну на паузу или завершите её.",
            "code": "active_limit",
        }), 409
    max_order = db.execute(
        "SELECT COALESCE(MAX(sort_order), -10) AS m FROM habits WHERE user_id = ?",
        (g.user["id"],),
    ).fetchone()["m"]
    habit_id = _insert_habit(db, g.user["id"], payload, user_today(g.user).isoformat(),
                             max_order + 10)
    db.commit()
    habit = get_habit(db, g.user["id"], habit_id)
    logs = load_logs(db, g.user["id"])
    return jsonify({"habit": serialize_habit(habit, logs.get(habit_id, []), user_today(g.user))}), 201


@bp.post("/habits/batch")
@login_required
def create_batch():
    data = json_body()
    items = data.get("habits")
    if not isinstance(items, list) or not 1 <= len(items) <= 6:
        raise ValidationError("Передайте от 1 до 6 привычек")
    payloads = [validate_habit_payload(item) for item in items]
    active_new = sum(1 for payload in payloads if payload.get("status", "active") == "active")
    db = get_db()
    if _active_count(db, g.user["id"]) + active_new > MAX_ACTIVE_HABITS:
        return jsonify({
            "error": f"Лимит активных привычек — {MAX_ACTIVE_HABITS}. Уменьшите список.",
            "code": "active_limit",
        }), 409
    max_order = db.execute(
        "SELECT COALESCE(MAX(sort_order), -10) AS m FROM habits WHERE user_id = ?",
        (g.user["id"],),
    ).fetchone()["m"]
    ids = []
    for index, payload in enumerate(payloads):
        ids.append(_insert_habit(db, g.user["id"], payload, user_today(g.user).isoformat(),
                                 max_order + 10 + index * 10))
    db.commit()
    logs = load_logs(db, g.user["id"])
    habits = rows_to_dicts(db.execute(
        f"SELECT * FROM habits WHERE user_id = ? AND id IN ({','.join('?' * len(ids))})"
        " ORDER BY sort_order, id", (g.user["id"], *ids),
    ))
    return jsonify({
        "habits": [serialize_habit(h, logs.get(h["id"], []), user_today(g.user)) for h in habits],
        "created": len(ids),
    }), 201


@bp.patch("/habits/<int:habit_id>")
@login_required
def update_habit(habit_id: int):
    db = get_db()
    habit = get_habit(db, g.user["id"], habit_id)
    data = json_body()
    payload = validate_habit_payload(data, partial=True, existing=habit)
    if payload.get("status") == "active" and habit["status"] != "active":
        if _active_count(db, g.user["id"], exclude_id=habit_id) >= MAX_ACTIVE_HABITS:
            return jsonify({"error": "Лимит активных привычек достигнут",
                            "code": "active_limit"}), 409
    if payload.get("type") == "boolean":
        payload["unit"] = ""
    fields = {**payload, "updated_at": iso_now()}
    assignments = ", ".join(f"{key} = ?" for key in fields)
    db.execute(f"UPDATE habits SET {assignments} WHERE id = ? AND user_id = ?",
               (*fields.values(), habit_id, g.user["id"]))
    db.commit()
    updated = get_habit(db, g.user["id"], habit_id)
    logs = load_logs(db, g.user["id"])
    return jsonify({"habit": serialize_habit(updated, logs.get(habit_id, []), user_today(g.user))})


@bp.delete("/habits/<int:habit_id>")
@login_required
def delete_habit(habit_id: int):
    db = get_db()
    get_habit(db, g.user["id"], habit_id, include_deleted=True)
    permanent = request.args.get("permanent") in ("1", "true")
    mode = request.args.get("mode", "")
    if permanent:
        db.execute("DELETE FROM habits WHERE id = ? AND user_id = ?", (habit_id, g.user["id"]))
        db.commit()
        return jsonify({"ok": True, "permanent": True, "habit_id": habit_id})
    if mode == "archive":
        db.execute("UPDATE habits SET status = 'archived', updated_at = ? WHERE id = ? AND user_id = ?",
                   (iso_now(), habit_id, g.user["id"]))
        db.commit()
        return jsonify({"ok": True, "archived": True, "habit_id": habit_id})
    db.execute(
        "UPDATE habits SET deleted_at = ?, status = 'archived', updated_at = ?"
        " WHERE id = ? AND user_id = ?",
        (iso_now(), iso_now(), habit_id, g.user["id"]),
    )
    db.commit()
    return jsonify({
        "ok": True, "deleted": True, "habit_id": habit_id,
        "undo_seconds": 10,
        "message": "Привычка удалена. Вернуть можно в течение 10 секунд.",
    })


@bp.post("/habits/<int:habit_id>/restore")
@login_required
def restore_habit(habit_id: int):
    db = get_db()
    habit = get_habit(db, g.user["id"], habit_id, include_deleted=True)
    if not habit.get("deleted_at") and habit["status"] != "archived":
        return jsonify({"error": "Привычка не удалена", "code": "not_deleted"}), 409
    if _active_count(db, g.user["id"], exclude_id=habit_id) >= MAX_ACTIVE_HABITS:
        return jsonify({"error": "Лимит активных привычек достигнут", "code": "active_limit"}), 409
    db.execute(
        "UPDATE habits SET deleted_at = NULL, status = 'active', updated_at = ?"
        " WHERE id = ? AND user_id = ?",
        (iso_now(), habit_id, g.user["id"]),
    )
    db.commit()
    updated = get_habit(db, g.user["id"], habit_id)
    logs = load_logs(db, g.user["id"])
    return jsonify({"habit": serialize_habit(updated, logs.get(habit_id, []), user_today(g.user))})


@bp.get("/templates")
@login_required
def templates():
    db = get_db()
    rows = rows_to_dicts(db.execute(
        "SELECT * FROM habit_templates WHERE is_active = 1 ORDER BY id"
    ))
    return jsonify({"templates": rows})
