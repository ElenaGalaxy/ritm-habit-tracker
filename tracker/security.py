"""Аутентификация: пароли, сессии, проверка прав, простой rate-limit."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import timedelta
from functools import wraps
from urllib.parse import urlsplit

from flask import current_app, g, jsonify, request

from .db import get_db, rows_to_dicts
from .utils import ValidationError, iso_now, json_loads, parse_iso

SESSION_COOKIE = "ht_session"
SESSION_DAYS = 30
PBKDF2_ROUNDS = 260_000


# ---------------------------------------------------------------- пароли

def hash_password(password: str) -> str:
    if not isinstance(password, str) or len(password) < 8:
        raise ValidationError("Пароль должен содержать не менее 8 символов")
    if len(password) > 200:
        raise ValidationError("Пароль слишком длинный")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return f"pbkdf2${PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, rounds, salt_hex, digest_hex = stored.split("$")
        if algorithm != "pbkdf2":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, AttributeError, TypeError):
        return False


# ---------------------------------------------------------------- сессии

def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db, user_id: int, user_agent: str = "") -> str:
    token = secrets.token_urlsafe(32)
    now = iso_now()
    expires = (parse_iso(now) + timedelta(days=SESSION_DAYS)).isoformat()
    db.execute(
        "INSERT INTO sessions(token_hash, user_id, created_at, expires_at, user_agent)"
        " VALUES (?, ?, ?, ?, ?)",
        (_token_hash(token), user_id, now, expires, (user_agent or "")[:300]),
    )
    db.commit()
    return token


def set_session_cookie(response, token: str):
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 24 * 3600,
        httponly=True,
        samesite="Lax",
        secure=bool(current_app.config.get("SESSION_COOKIE_SECURE")),
        path="/",
    )
    return response


def clear_session_cookie(response):
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


def get_current_user() -> dict | None:
    if "current_user" in g:
        return g.current_user
    token = request.cookies.get(SESSION_COOKIE)
    user = None
    if token:
        db = get_db()
        row = db.execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id"
            " WHERE s.token_hash = ? AND s.expires_at > ?",
            (_token_hash(token), iso_now()),
        ).fetchone()
        if row:
            user = dict(row)
            user["conditions_enabled"] = json_loads(
                user.get("conditions_enabled"),
                {"streak_badge": True, "missed_reminder": True, "low_week": True},
            )
            user.pop("password_hash", None)
    g.current_user = user
    return user


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"error": "Требуется вход", "code": "unauthorized"}), 401
        g.user = user
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        if g.user.get("role") != "admin":
            return jsonify({"error": "Недостаточно прав", "code": "forbidden"}), 403
        return fn(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------------- CSRF / origin

def origin_ok() -> bool:
    """SameSite=Lax + проверка Origin для изменяющих запросов."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return True
    origin = request.headers.get("Origin")
    if not origin:
        referer = request.headers.get("Referer")
        if not referer:
            return True  # не браузерный клиент (curl, тесты)
        origin = referer
    try:
        host = urlsplit(origin).netloc.lower()
    except ValueError:
        return False
    if not host:
        return False
    allowed = {request.host.lower()}
    return host in allowed or host.split(":")[0] == request.host.split(":")[0]


# ---------------------------------------------------------------- rate limit

class SlidingWindow:
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and q[0] <= now - self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)


login_limiter = SlidingWindow(limit=12, window_seconds=300)
register_limiter = SlidingWindow(limit=8, window_seconds=3600)


# ---------------------------------------------------------------- сериализация

def public_user(user: dict) -> dict:
    """Профиль без чувствительных полей."""
    keys = (
        "id", "name", "email", "role", "timezone", "goal", "quiet_hours_start",
        "quiet_hours_end", "reminder_channel", "ai_enabled", "ai_consent",
        "theme", "onboarded_at", "created_at",
    )
    out = {key: user.get(key) for key in keys}
    out["conditions_enabled"] = user.get("conditions_enabled") or {}
    out["telegram_connected"] = bool(user.get("telegram_id"))
    out["telegram_id"] = user.get("telegram_id")
    out["telegram_connected_at"] = user.get("telegram_connected_at")
    return out


def admin_user(user: dict) -> dict:
    out = public_user(user)
    out.pop("telegram_id", None)
    return out


def list_sessions(db, user_id: int) -> list[dict]:
    return rows_to_dicts(
        db.execute(
            "SELECT id, created_at, expires_at, user_agent FROM sessions"
            " WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        )
    )
