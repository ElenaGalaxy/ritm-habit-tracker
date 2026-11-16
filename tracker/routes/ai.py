"""AI-ассистент: генерация привычек и недельный обзор с fallback."""
from __future__ import annotations

import json
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from flask import Blueprint, current_app, g, jsonify, request

from .. import ai
from ..api_helpers import json_body, load_logs, serialize_habit, user_today
from ..db import get_db, rows_to_dicts
from ..security import login_required
from ..stats import normalize_logs, weekly_review_data
from ..utils import ValidationError, clamp_text, get_zone, iso_now, json_dumps, to_int
from ..validation import validate_ai_plan, validate_ai_review

bp = Blueprint("ai", __name__)


def _requests_today(db, user: dict) -> int:
    today = user_today(user)
    zone = get_zone(user.get("timezone"))
    start = datetime.combine(today, time.min, tzinfo=zone).astimezone(ZoneInfo("UTC"))
    row = db.execute(
        "SELECT COUNT(*) AS c FROM ai_requests WHERE user_id = ? AND created_at >= ?",
        (user["id"], start.replace(microsecond=0).isoformat()),
    ).fetchone()
    return row["c"]


def _check_access(db) -> None:
    if not g.user.get("ai_enabled"):
        raise AIForbidden("AI-рекомендации отключены в настройках", "ai_disabled")
    if not g.user.get("ai_consent"):
        raise AIForbidden(
            "Нужно согласие на отправку обезличенных данных AI. Включите его в настройках.",
            "consent_required",
        )
    used = _requests_today(db, g.user)
    if used >= ai.RATE_LIMIT_PER_DAY:
        raise AIRateLimited()


class AIForbidden(Exception):
    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.message = message
        self.code = code


class AIRateLimited(Exception):
    pass


@bp.errorhandler(AIForbidden)
def handle_forbidden(exc: AIForbidden):
    return jsonify({"error": exc.message, "code": exc.code}), 409


@bp.errorhandler(AIRateLimited)
def handle_rate(exc: AIRateLimited):
    return jsonify({
        "error": f"Лимит {ai.RATE_LIMIT_PER_DAY} AI-запросов в день исчерпан. "
                 "Шаблонный план доступен и без AI.",
        "code": "ai_rate_limit",
    }), 429


@bp.get("/ai/status")
@login_required
def status():
    db = get_db()
    used = _requests_today(db, g.user)
    config = ai.AIConfig(current_app)
    return jsonify({
        "enabled": bool(g.user.get("ai_enabled")),
        "consent": bool(g.user.get("ai_consent")),
        "provider_ready": config.enabled,
        "requests_today": used,
        "limit": ai.RATE_LIMIT_PER_DAY,
        "remaining": max(0, ai.RATE_LIMIT_PER_DAY - used),
        "model": config.model if config.enabled else None,
    })


@bp.post("/ai/generate")
@login_required
def generate():
    db = get_db()
    _check_access(db)
    data = json_body()
    goal = clamp_text(data.get("goal") or g.user.get("goal"), "цель", 500, required=True)
    if len(goal) < 3:
        raise ValidationError("Опишите цель чуть подробнее")
    app = current_app._get_current_object()
    raw_plan, provider, provider_status = ai.generate_plan(goal, app)
    status = provider_status
    try:
        plan = validate_ai_plan(raw_plan)
        if raw_plan.get("fallback"):
            plan["fallback"] = True
    except ValidationError:
        plan = ai._fallback_plan(goal)
        plan["fallback"] = True
        status = "invalid"
        provider = "fallback"
    db.execute(
        "INSERT INTO ai_requests(user_id, type, input_text, output_json, provider, status, created_at)"
        " VALUES (?, 'generate_habits', ?, ?, ?, ?, ?)",
        (g.user["id"], goal, json_dumps(plan), provider, status, iso_now()),
    )
    db.commit()
    used = _requests_today(db, g.user)
    return jsonify({
        "plan": plan,
        "goal": goal,
        "provider": provider,
        "fallback": bool(plan.get("fallback")),
        "status": status,
        "requests_today": used,
        "remaining": max(0, ai.RATE_LIMIT_PER_DAY - used),
    })


@bp.post("/ai/review")
@login_required
def review():
    db = get_db()
    _check_access(db)
    today = user_today(g.user)
    habits = rows_to_dicts(db.execute(
        "SELECT * FROM habits WHERE user_id = ? AND deleted_at IS NULL AND status = 'active'"
        " ORDER BY sort_order, id",
        (g.user["id"],),
    ))
    logs = load_logs(db, g.user["id"], since=today - timedelta(days=7))
    data = weekly_review_data(habits, logs, today)
    app = current_app._get_current_object()
    raw_review, provider, provider_status = ai.generate_review(
        data, g.user.get("goal", ""), app,
    )
    status = provider_status
    try:
        validated = validate_ai_review(raw_review)
        if raw_review.get("fallback"):
            validated["fallback"] = True
    except ValidationError:
        validated = ai._fallback_review(data)
        validated["fallback"] = True
        status = "invalid"
        provider = "fallback"
    db.execute(
        "INSERT INTO ai_requests(user_id, type, input_text, output_json, provider, status, created_at)"
        " VALUES (?, 'weekly_review', ?, ?, ?, ?, ?)",
        (g.user["id"], g.user.get("goal", ""), json_dumps(validated), provider, status, iso_now()),
    )
    db.commit()
    used = _requests_today(db, g.user)
    return jsonify({
        "review": validated,
        "period": data["period"],
        "habits": data["habits"],
        "provider": provider,
        "fallback": bool(validated.get("fallback")),
        "status": status,
        "requests_today": used,
        "remaining": max(0, ai.RATE_LIMIT_PER_DAY - used),
    })


@bp.get("/ai/history")
@login_required
def history():
    db = get_db()
    limit = min(50, max(1, to_int(request.args.get("limit", 20), "limit")))
    items = []
    for row in db.execute(
        "SELECT * FROM ai_requests WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (g.user["id"], limit),
    ):
        item = dict(row)
        try:
            item["output"] = json.loads(item.pop("output_json"))
        except (TypeError, ValueError):
            item["output"] = None
            item.pop("output_json", None)
        items.append(item)
    return jsonify({"requests": items})
