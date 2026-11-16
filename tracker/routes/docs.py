"""Публичная документация: ТЗ в Markdown и PDF, OpenAPI."""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, abort, current_app, jsonify, request
from flask import Response, send_file

from ..markdown_pdf import markdown_to_pdf
from ..security import get_current_user

bp = Blueprint("docs", __name__)
BASE = Path(__file__).resolve().parent.parent.parent
TZ_MD = BASE / "docs" / "TZ_habit_tracker_MVP.md"
OPENAPI = BASE / "openapi.yaml"

# Документы, которые можно скачать через /docs/file/<name>.
DOWNLOADABLE = {
    "schema.sql": ("text/plain; charset=utf-8", "schema.sql"),
    "seed.json": ("application/json; charset=utf-8", "seed.json"),
    "README.md": ("text/markdown; charset=utf-8", "README.md"),
}

_cache: dict[str, tuple[float, bytes]] = {}


def _allowed() -> bool:
    if current_app.config.get("DOCS_PUBLIC", True):
        return True
    user = get_current_user()
    return bool(user and user.get("role") == "admin")


def _tz_pdf() -> bytes:
    if not TZ_MD.exists():
        abort(404)
    mtime = TZ_MD.stat().st_mtime
    cached = _cache.get("tz")
    if cached and cached[0] == mtime:
        return cached[1]
    content = markdown_to_pdf(TZ_MD.read_text(encoding="utf-8"))
    _cache["tz"] = (mtime, content)
    return content


@bp.get("/docs/tz.md")
def tz_markdown():
    if not _allowed():
        return jsonify({"error": "Документация доступна только администратору",
                        "code": "forbidden"}), 403
    if not TZ_MD.exists():
        abort(404)
    data = TZ_MD.read_bytes()
    disposition = "inline" if request.args.get("inline") == "1" else "attachment"
    return Response(
        data,
        content_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'{disposition}; filename="TZ_habit_tracker_MVP.md"',
            "Cache-Control": "no-store",
        },
    )


@bp.get("/docs/tz.pdf")
def tz_pdf():
    if not _allowed():
        return jsonify({"error": "Документация доступна только администратору",
                        "code": "forbidden"}), 403
    content = _tz_pdf()
    disposition = "inline" if request.args.get("inline") == "1" else "attachment"
    return Response(
        content,
        content_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="TZ_habit_tracker_MVP.pdf"',
            "Cache-Control": "no-store",
        },
    )


@bp.get("/openapi.yaml")
def openapi():
    if not OPENAPI.exists():
        abort(404)
    return send_file(OPENAPI, mimetype="application/yaml", as_attachment=False,
                     download_name="openapi.yaml")


@bp.get("/docs/file/<name>")
def doc_file(name: str):
    """Скачивание обязательных артефактов проекта по белому списку."""
    if name not in DOWNLOADABLE:
        abort(404)
    mimetype, download_name = DOWNLOADABLE[name]
    path = BASE / name
    if not path.exists():
        abort(404)
    data = path.read_bytes()
    if name == "README.md":
        disposition = "inline" if request.args.get("inline") == "1" else "attachment"
        return Response(
            data,
            content_type=mimetype,
            headers={
                "Content-Disposition": f'{disposition}; filename="{download_name}"',
                "Cache-Control": "no-store",
            },
        )
    return send_file(
        path,
        mimetype=mimetype.split(";")[0],
        as_attachment=request.args.get("inline") != "1",
        download_name=download_name,
    )
