"""Фабрика приложения «Трекер привычек»."""
from __future__ import annotations

import os
import secrets
import sqlite3
from pathlib import Path

from flask import Flask, Response, g, jsonify, render_template, request

from .db import close_db, get_db, init_db, log_error
from .security import get_current_user, origin_ok
from .utils import NotFound, ValidationError, iso_now


def _load_dotenv(base: Path) -> None:
    """Простой парсер .env без внешних зависимостей."""
    env_path = base / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def create_app(test_config: dict | None = None) -> Flask:
    base = Path(__file__).resolve().parent.parent
    _load_dotenv(base)

    app = Flask(
        __name__,
        static_folder=str(base / "static"),
        template_folder=str(base / "templates"),
        static_url_path="/static",
    )
    app.config.update({
        "SECRET_KEY": os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        "DATABASE": os.environ.get("DATABASE_PATH") or str(base / "instance" / "tracker.db"),
        "MAX_CONTENT_LENGTH": 1024 * 1024,
        "SESSION_COOKIE_SECURE": _env_bool("SESSION_COOKIE_SECURE", False),
        "ALLOW_DEMO_LOGIN": _env_bool("ALLOW_DEMO_LOGIN", True),
        "SEED_DEMO": _env_bool("SEED_DEMO", True),
        "DOCS_PUBLIC": _env_bool("DOCS_PUBLIC", True),
        "SCHEDULER_ENABLED": _env_bool("SCHEDULER_ENABLED", True),
        "TELEGRAM_BOT_TOKEN": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "TELEGRAM_BOT_USERNAME": os.environ.get("TELEGRAM_BOT_USERNAME", ""),
        "TELEGRAM_WEBHOOK_SECRET": os.environ.get("TELEGRAM_WEBHOOK_SECRET", ""),
        "AI_API_KEY": os.environ.get("AI_API_KEY", ""),
        "AI_BASE_URL": os.environ.get("AI_BASE_URL", "https://api.openai.com/v1"),
        "AI_MODEL": os.environ.get("AI_MODEL", "gpt-4o-mini"),
        "AI_TIMEOUT": int(os.environ.get("AI_TIMEOUT", "40")),
        "JSON_AS_ASCII": False,
    })
    if test_config:
        app.config.update(test_config)
    app.json.ensure_ascii = False
    app.json.sort_keys = False

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    init_db(app)
    app.teardown_appcontext(close_db)

    from .routes import admin, ai, auth, docs, export, habits, logs, settings, stats

    for blueprint in (auth.bp, habits.bp, logs.bp, stats.bp, ai.bp,
                      settings.bp, export.bp, docs.bp, admin.bp):
        app.register_blueprint(blueprint)

    # Демо-данные — только при первом запуске пустой базы.
    if app.config.get("SEED_DEMO"):
        from .seed import seed_demo, ensure_templates

        with app.app_context():
            db = get_db()
            ensure_templates(db)
            seed_demo(db)
    else:
        from .seed import ensure_templates

        with app.app_context():
            ensure_templates(get_db())

    # ------------------------------------------------------------ безопасность
    @app.before_request
    def csrf_guard():
        if not origin_ok():
            return jsonify({"error": "Запрос отклонён (origin)", "code": "csrf"}), 403
        return None

    @app.after_request
    def security_headers(response: Response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
            "base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
        )
        if request.path.startswith(("/auth", "/habits", "/logs", "/stats", "/ai",
                                    "/export", "/settings", "/telegram", "/reminders",
                                    "/events", "/conditions", "/admin", "/account")):
            response.headers["Cache-Control"] = "no-store"
        return response

    # ------------------------------------------------------------ ошибки
    @app.errorhandler(ValidationError)
    def handle_validation(exc: ValidationError):
        return jsonify({
            "error": exc.message,
            "code": "validation_error",
            "details": exc.details,
        }), 400

    @app.errorhandler(NotFound)
    def handle_not_found(exc: NotFound):
        return jsonify({"error": exc.message, "code": "not_found"}), 404

    @app.errorhandler(413)
    def handle_too_large(_exc):
        return jsonify({"error": "Слишком большой запрос", "code": "too_large"}), 413

    @app.errorhandler(sqlite3.IntegrityError)
    def handle_integrity(exc):
        app.logger.warning("Integrity error: %s", exc)
        return jsonify({"error": "Конфликт данных. Обновите страницу.",
                        "code": "conflict"}), 409

    @app.errorhandler(404)
    def handle_404(exc):
        if request.path == "/":
            return render_template("index.html")
        if request.path.startswith(("/auth", "/habits", "/logs", "/stats", "/ai",
                                    "/export", "/settings", "/telegram", "/reminders",
                                    "/events", "/conditions", "/admin", "/account",
                                    "/docs", "/openapi")):
            return jsonify({"error": "Не найдено", "code": "not_found"}), 404
        return exc

    @app.errorhandler(405)
    def handle_405(_exc):
        return jsonify({"error": "Метод не поддерживается", "code": "method"}), 405

    @app.errorhandler(Exception)
    def handle_error(exc):
        app.logger.exception("Unhandled error: %s", exc)
        try:
            user = get_current_user()
            db = get_db()
            log_error(db, f"{type(exc).__name__}: {exc}", request.path, request.method,
                      user["id"] if user else None)
        except Exception:
            pass
        return jsonify({
            "error": "Что-то пошло не так. Мы записали ошибку и попробуем ещё раз.",
            "code": "internal",
        }), 500

    # ------------------------------------------------------------ страницы
    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/health")
    def health():
        db = get_db()
        db.execute("SELECT 1").fetchone()
        return jsonify({"ok": True, "time": iso_now()})

    @app.get("/favicon.ico")
    def favicon():
        return Response(status=204)

    @app.get("/manifest.webmanifest")
    def manifest():
        return jsonify({
            "name": "Ритм — трекер привычек",
            "short_name": "Ритм",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#F7F4ED",
            "theme_color": "#C9623E",
            "icons": [],
        })

    # ------------------------------------------------------------ CLI
    @app.cli.command("reminders-tick")
    def reminders_tick_command():
        from .notifications import tick

        result = tick(app)
        print(result)

    @app.cli.command("seed-demo")
    def seed_demo_command():
        from .seed import ensure_templates, seed_demo

        db = get_db()
        ensure_templates(db)
        created = seed_demo(db)
        print("Демо-данные созданы" if created else "Пользователи уже есть — пропущено")

    @app.cli.command("purge-expired-sessions")
    def purge_sessions():
        db = get_db()
        cur = db.execute("DELETE FROM sessions WHERE expires_at < ?", (iso_now(),))
        db.commit()
        print(f"Удалено сессий: {cur.rowcount}")

    return app
