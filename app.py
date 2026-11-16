"""Точка входа: python app.py (сервер + фоновые напоминания)."""
from __future__ import annotations

import os

from tracker import create_app
from tracker.notifications import start_scheduler

app = create_app()

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "0") in ("1", "true", "True")
    if os.environ.get("DISABLE_SCHEDULER") not in ("1", "true"):
        start_scheduler(app)
    app.run(host=host, port=port, debug=debug, use_reloader=False)
