"""Валидация входных данных привычек и ответов AI."""
from __future__ import annotations

import re
from typing import Any

from .utils import ValidationError, clamp_text, to_float, to_int, valid_time

HABIT_TYPES = ("boolean", "quantity", "duration")
SCHEDULES = ("daily", "weekdays", "times_per_week")
HABIT_STATUSES = ("active", "paused", "completed", "archived")
UNITS = ("", "раз", "минуты", "страницы", "стаканы", "шаги", "кг", "км")
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
MAX_ACTIVE_HABITS = 30


def _color(value: Any, fallback: str = "#C9623E") -> str:
    if value is None or value == "":
        return fallback
    if not isinstance(value, str) or not COLOR_RE.match(value):
        raise ValidationError("Цвет должен быть в формате #RRGGBB")
    return value


def _icon(value: Any) -> str:
    text = clamp_text(value, "иконка", 32)
    return text or "spark"


def validate_habit_payload(data: Any, *, partial: bool = False,
                           existing: dict | None = None) -> dict:
    if not isinstance(data, dict):
        raise ValidationError("Ожидается JSON-объект")
    existing = existing or {}
    out: dict[str, Any] = {}

    if not partial or "title" in data:
        out["title"] = clamp_text(data.get("title"), "название", 80, required=True)
    if "description" in data or not partial:
        out["description"] = clamp_text(data.get("description"), "описание", 300)

    habit_type = data.get("type", existing.get("type", "boolean"))
    if habit_type not in HABIT_TYPES:
        raise ValidationError("Тип привычки: boolean, quantity или duration")
    out["type"] = habit_type

    if "target_value" in data or "type" in data or not partial:
        target = to_float(data.get("target_value", existing.get("target_value", 1)), "цель")
        if target <= 0:
            raise ValidationError("Цель должна быть больше 0")
        if target > 100000:
            raise ValidationError("Слишком большая цель")
        out["target_value"] = target
    if "unit" in data or "type" in data or not partial:
        unit = clamp_text(data.get("unit", existing.get("unit", "")), "единица", 20)
        if habit_type == "boolean":
            unit = ""
        out["unit"] = unit

    schedule = data.get("schedule", existing.get("schedule", "daily"))
    if schedule not in SCHEDULES:
        raise ValidationError("Расписание: daily, weekdays или times_per_week")
    out["schedule"] = schedule
    if schedule == "times_per_week" or not partial:
        times = to_int(data.get("times_per_week", existing.get("times_per_week", 3)), "N раз в неделю")
        if not 1 <= times <= 7:
            raise ValidationError("Для «N раз в неделю» укажите N от 1 до 7")
        out["times_per_week"] = times
    elif "times_per_week" in data:
        times = to_int(data.get("times_per_week"), "N раз в неделю")
        if not 1 <= times <= 7:
            raise ValidationError("Для «N раз в неделю» укажите N от 1 до 7")
        out["times_per_week"] = times

    if "reminder_time" in data or not partial:
        out["reminder_time"] = valid_time(data.get("reminder_time", existing.get("reminder_time", "09:00")))
    if "color" in data or not partial:
        out["color"] = _color(data.get("color", existing.get("color", "#C9623E")))
    if "icon" in data or not partial:
        out["icon"] = _icon(data.get("icon", existing.get("icon", "spark")))
    if "freeze_limit" in data or not partial:
        limit = to_int(data.get("freeze_limit", existing.get("freeze_limit", 2)), "лимит заморозок")
        if not 0 <= limit <= 5:
            raise ValidationError("Лимит заморозок — от 0 до 5")
        out["freeze_limit"] = limit
    if "status" in data:
        status = data.get("status")
        if status not in HABIT_STATUSES:
            raise ValidationError("Недопустимый статус привычки")
        out["status"] = status
    if "sort_order" in data:
        out["sort_order"] = to_int(data.get("sort_order"), "порядок")
    return out


def validate_log_payload(data: Any, habit: dict) -> dict:
    if not isinstance(data, dict):
        raise ValidationError("Ожидается JSON-объект")
    if "habit_id" not in data:
        raise ValidationError("Не указана привычка")
    habit_id = to_int(data.get("habit_id"), "habit_id")
    from .utils import parse_date

    d = parse_date(data.get("date"))
    value = to_float(data.get("value", habit["target_value"] if habit["type"] == "boolean" else 0), "значение")
    if value < 0:
        raise ValidationError("Значение не может быть отрицательным")
    if value > 1_000_000:
        raise ValidationError("Слишком большое значение")
    status = data.get("status")
    allowed = ("done", "partial", "skipped", "frozen")
    if status is not None and status not in allowed:
        raise ValidationError("Статус отметки: done, partial, skipped или frozen")
    note = clamp_text(data.get("note"), "заметка", 500)
    return {"habit_id": habit_id, "date": d, "value": value, "status": status, "note": note}


def validate_ai_habit(item: Any, index: int) -> dict:
    """Строгая валидация одной привычки из ответа AI."""
    if not isinstance(item, dict):
        raise ValidationError(f"Привычка #{index + 1}: ожидается объект")
    title = clamp_text(item.get("title"), f"название привычки #{index + 1}", 80, required=True)
    description = clamp_text(item.get("description", ""), f"описание привычки #{index + 1}", 300)
    habit_type = item.get("type", "boolean")
    if habit_type not in HABIT_TYPES:
        raise ValidationError(f"Привычка #{index + 1}: недопустимый тип")
    try:
        target = to_float(item.get("target_value", 1), "target_value")
    except ValidationError as exc:
        raise ValidationError(f"Привычка #{index + 1}: цель должна быть числом") from exc
    if target <= 0:
        raise ValidationError(f"Привычка #{index + 1}: цель должна быть больше 0")
    schedule = item.get("schedule", "daily")
    if schedule not in SCHEDULES:
        raise ValidationError(f"Привычка #{index + 1}: недопустимое расписание")
    times = 3
    if schedule == "times_per_week":
        times = to_int(item.get("times_per_week", 3), "times_per_week")
        if not 1 <= times <= 7:
            raise ValidationError(f"Привычка #{index + 1}: N от 1 до 7")
    micro_step = clamp_text(item.get("micro_step", ""), f"микро-шаг #{index + 1}", 200, required=True)
    trigger = clamp_text(item.get("trigger", ""), f"триггер #{index + 1}", 200, required=True)
    return {
        "title": title,
        "description": description,
        "type": habit_type,
        "target_value": target,
        "unit": clamp_text(item.get("unit", ""), f"единица #{index + 1}", 20),
        "schedule": schedule,
        "times_per_week": times,
        "micro_step": micro_step,
        "trigger": trigger,
        "icon": _icon(item.get("icon", "spark")),
        "color": _color(item.get("color", "#C9623E")),
    }


def validate_ai_plan(payload: Any) -> dict:
    if not isinstance(payload, dict):
        raise ValidationError("AI вернул не объект")
    habits = payload.get("habits")
    if not isinstance(habits, list) or not 3 <= len(habits) <= 5:
        raise ValidationError("AI должен вернуть от 3 до 5 привычек")
    validated = [validate_ai_habit(item, i) for i, item in enumerate(habits)]
    summary = clamp_text(payload.get("summary", ""), "summary", 500)
    return {"habits": validated, "summary": summary}


def validate_ai_review(payload: Any) -> dict:
    if not isinstance(payload, dict):
        raise ValidationError("AI вернул не объект")
    wins = payload.get("wins")
    gaps = payload.get("gaps")
    recommendations = payload.get("recommendations")
    if not isinstance(wins, list) or not isinstance(gaps, list) or not isinstance(recommendations, list):
        raise ValidationError("AI-обзор должен содержать wins, gaps и recommendations")
    if not 2 <= len(recommendations) <= 3:
        raise ValidationError("AI должен вернуть 2–3 рекомендации")

    def text_list(items, field, limit):
        result = []
        for item in items:
            result.append(clamp_text(item, field, limit, required=True))
        return result

    recs = []
    for item in recommendations:
        if isinstance(item, str):
            recs.append({"text": clamp_text(item, "рекомендация", 400, required=True),
                         "habit_title": None, "suggested_target": None})
        elif isinstance(item, dict):
            recs.append({
                "text": clamp_text(item.get("text"), "рекомендация", 400, required=True),
                "habit_title": clamp_text(item.get("habit_title", ""), "habit_title", 80) or None,
                "suggested_target": (
                    to_float(item["suggested_target"], "suggested_target")
                    if item.get("suggested_target") is not None else None
                ),
            })
        else:
            raise ValidationError("Рекомендация должна быть строкой или объектом")
    return {
        "wins": text_list(wins, "wins", 300),
        "gaps": text_list(gaps, "gaps", 300),
        "recommendations": recs,
        "summary": clamp_text(payload.get("summary", ""), "summary", 500),
    }
