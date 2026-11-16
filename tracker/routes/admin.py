"""Минимальный админ-раздел: ошибки, шаблоны, сводка. Без личных заметок."""
from __future__ import annotations

from flask import Blueprint, current_app, g, jsonify, request

from ..api_helpers import json_body
from ..db import get_db, rows_to_dicts
from ..security import admin_required
from ..utils import ValidationError, to_int

bp = Blueprint("admin", __name__)


@bp.get("/admin/overview")
@admin_required
def overview():
    db = get_db()
    counts = {
        "users": db.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"],
        "habits": db.execute("SELECT COUNT(*) AS c FROM habits WHERE deleted_at IS NULL").fetchone()["c"],
        "logs": db.execute("SELECT COUNT(*) AS c FROM habit_logs").fetchone()["c"],
        "ai_requests": db.execute("SELECT COUNT(*) AS c FROM ai_requests").fetchone()["c"],
        "errors": db.execute("SELECT COUNT(*) AS c FROM error_logs").fetchone()["c"],
        "reminders": db.execute(
            "SELECT COUNT(*) AS c FROM notifications WHERE status IN ('sent','simulated')"
        ).fetchone()["c"],
    }
    users = rows_to_dicts(db.execute(
        "SELECT id, name, email, role, timezone, created_at FROM users ORDER BY id"
    ))
    templates = rows_to_dicts(db.execute(
        "SELECT * FROM habit_templates ORDER BY id"
    ))
    errors = rows_to_dicts(db.execute(
        "SELECT id, level, message, path, method, created_at FROM error_logs"
        " ORDER BY id DESC LIMIT 20"
    ))
    return jsonify({
        "counts": counts, "users": users, "templates": templates,
        "errors": errors,
        "bot_configured": bool(current_app.config.get("TELEGRAM_BOT_TOKEN")),
        "ai_configured": bool(current_app.config.get("AI_API_KEY")),
        "docs_public": bool(current_app.config.get("DOCS_PUBLIC", True)),
    })


@bp.patch("/admin/templates/<int:template_id>")
@admin_required
def update_template(template_id: int):
    data = json_body()
    db = get_db()
    row = db.execute("SELECT * FROM habit_templates WHERE id = ?", (template_id,)).fetchone()
    if not row:
        return jsonify({"error": "Шаблон не найден", "code": "not_found"}), 404
    if "is_active" in data:
        if not isinstance(data["is_active"], bool):
            raise ValidationError("is_active должен быть true/false")
        db.execute("UPDATE habit_templates SET is_active = ? WHERE id = ?",
                   (1 if data["is_active"] else 0, template_id))
    if "title" in data:
        title = (data.get("title") or "").strip()
        if not title or len(title) > 80:
            raise ValidationError("Название шаблона — от 1 до 80 символов")
        db.execute("UPDATE habit_templates SET title = ? WHERE id = ?", (title, template_id))
    db.commit()
    updated = db.execute("SELECT * FROM habit_templates WHERE id = ?", (template_id,)).fetchone()
    return jsonify({"template": dict(updated)})


@bp.get("/admin/errors")
@admin_required
def errors():
    db = get_db()
    limit = min(200, max(1, to_int(request.args.get("limit", 50), "limit")))
    rows = rows_to_dicts(db.execute(
        "SELECT * FROM error_logs ORDER BY id DESC LIMIT ?", (limit,)
    ))
    return jsonify({"errors": rows})
