"""Регистрация, вход, сессии, онбординг."""
from __future__ import annotations

import re
import sqlite3

from flask import Blueprint, current_app, g, jsonify, request

from ..db import get_db
from ..security import (
    SESSION_COOKIE, clear_session_cookie, create_session, get_current_user,
    hash_password, login_limiter, login_required, public_user, register_limiter,
    set_session_cookie, verify_password,
)
from ..utils import (
    ValidationError, iso_now, json_dumps, json_loads, today_local, valid_timezone,
)
from ..api_helpers import json_body
from ..seed import DEMO_EMAIL

bp = Blueprint("auth", __name__)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_email(value) -> str:
    if not isinstance(value, str):
        raise ValidationError("Укажите email")
    email = value.strip().lower()
    if not EMAIL_RE.match(email) or len(email) > 200:
        raise ValidationError("Некорректный email")
    return email


@bp.post("/auth/register")
def register():
    if not register_limiter.allow(request.remote_addr or "local"):
        return jsonify({"error": "Слишком много попыток. Попробуйте позже.",
                        "code": "rate_limit"}), 429
    data = json_body()
    name = (data.get("name") or "").strip()
    if not name:
        raise ValidationError("Укажите имя")
    if len(name) > 80:
        raise ValidationError("Имя длиннее 80 символов")
    email = _normalize_email(data.get("email"))
    password = data.get("password") or ""
    timezone = valid_timezone(data.get("timezone") or "Europe/Moscow")

    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO users(name, email, password_hash, timezone, conditions_enabled, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (name, email, hash_password(password), timezone,
             json_dumps({"streak_badge": True, "missed_reminder": True, "low_week": True}),
             iso_now()),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Пользователь с таким email уже существует",
                        "code": "email_taken"}), 409

    user_id = cur.lastrowid
    token = create_session(db, user_id, request.headers.get("User-Agent", ""))
    db.execute("DELETE FROM sessions WHERE expires_at < ?", (iso_now(),))
    db.commit()
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    user = dict(row)
    user["conditions_enabled"] = json_loads(user["conditions_enabled"], {})
    resp = jsonify({"user": public_user(user), "onboarding_needed": True})
    resp.status_code = 201
    return set_session_cookie(resp, token)


@bp.post("/auth/login")
def login():
    data = json_body()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    key = f"{request.remote_addr}:{email}"
    if not login_limiter.allow(key):
        return jsonify({"error": "Слишком много попыток входа. Подождите пару минут.",
                        "code": "rate_limit"}), 429
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        return jsonify({"error": "Неверный email или пароль", "code": "invalid_credentials"}), 401
    user = dict(row)
    token = create_session(db, user["id"], request.headers.get("User-Agent", ""))
    login_limiter.reset(key)
    user["conditions_enabled"] = json_loads(user["conditions_enabled"], {})
    return set_session_cookie(jsonify({
        "user": public_user(user),
        "onboarding_needed": not bool(user.get("onboarded_at")),
    }), token)


@bp.post("/auth/demo")
def demo_login():
    if not current_app.config.get("ALLOW_DEMO_LOGIN", True):
        return jsonify({"error": "Демо-вход отключён", "code": "demo_disabled"}), 403
    if not login_limiter.allow(f"demo:{request.remote_addr}"):
        return jsonify({"error": "Слишком много попыток", "code": "rate_limit"}), 429
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE email = ?", (DEMO_EMAIL,)).fetchone()
    if not row:
        return jsonify({"error": "Демо-кабинет не создан", "code": "demo_missing"}), 404
    token = create_session(db, row["id"], request.headers.get("User-Agent", ""))
    user = dict(row)
    user["conditions_enabled"] = json_loads(user["conditions_enabled"], {})
    return set_session_cookie(jsonify({
        "user": public_user(user), "onboarding_needed": False, "demo": True,
    }), token)


@bp.post("/auth/logout")
def logout():
    import hashlib

    token = request.cookies.get(SESSION_COOKIE)
    if token:
        db = get_db()
        db.execute("DELETE FROM sessions WHERE token_hash = ?",
                   (hashlib.sha256(token.encode()).hexdigest(),))
        db.commit()
    return clear_session_cookie(jsonify({"ok": True}))


@bp.get("/auth/me")
def me():
    user = get_current_user()
    if not user:
        return jsonify({"user": None, "onboarding_needed": False}), 200
    return jsonify({
        "user": public_user(user),
        "onboarding_needed": not bool(user.get("onboarded_at")),
    })


@bp.post("/auth/onboarding")
@login_required
def onboarding():
    data = json_body()
    name = (data.get("name") or g.user["name"]).strip()
    if not name:
        raise ValidationError("Укажите имя")
    if len(name) > 80:
        raise ValidationError("Имя длиннее 80 символов")
    timezone = valid_timezone(data.get("timezone") or g.user["timezone"])
    goal = (data.get("goal") or "").strip()
    if len(goal) > 500:
        raise ValidationError("Цель длиннее 500 символов")
    channel = data.get("reminder_channel") or "none"
    if channel not in ("telegram", "none"):
        raise ValidationError("Канал напоминаний: telegram или none")
    db = get_db()
    db.execute(
        "UPDATE users SET name = ?, timezone = ?, goal = ?, reminder_channel = ?,"
        " onboarded_at = COALESCE(onboarded_at, ?) WHERE id = ?",
        (name, timezone, goal, channel, iso_now(), g.user["id"]),
    )
    db.commit()
    row = db.execute("SELECT * FROM users WHERE id = ?", (g.user["id"],)).fetchone()
    user = dict(row)
    user["conditions_enabled"] = json_loads(user["conditions_enabled"], {})
    return jsonify({"user": public_user(user), "onboarding_needed": False})
