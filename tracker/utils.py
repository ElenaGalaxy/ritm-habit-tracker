"""Служебные утилиты: даты, время, валидация, JSON-ответы."""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UTC = timezone.utc
DEFAULT_TZ = "Europe/Moscow"
TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(Exception):
    """Ошибка валидации входных данных (400)."""

    def __init__(self, message: str, details: dict[str, str] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFound(Exception):
    def __init__(self, message: str = "Не найдено"):
        super().__init__(message)
        self.message = message


def utcnow() -> datetime:
    return datetime.now(UTC)


def iso_now() -> str:
    return utcnow().replace(microsecond=0).isoformat()


def parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def get_zone(tz_name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or DEFAULT_TZ)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TZ)


def today_local(tz_name: str | None) -> date:
    return datetime.now(get_zone(tz_name)).date()


def local_date_of(iso_ts: str, tz_name: str | None) -> date:
    return parse_iso(iso_ts).astimezone(get_zone(tz_name)).date()


def parse_date(value: str) -> date:
    if not isinstance(value, str) or not DATE_RE.match(value):
        raise ValidationError("Дата должна быть в формате YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError("Некорректная дата") from exc


def format_date(d: date) -> str:
    return d.isoformat()


def month_bounds(year: int, month: int, tz_name: str | None = None) -> tuple[date, date]:
    if not 1 <= month <= 12:
        raise ValidationError("Месяц должен быть от 1 до 12")
    first = date(year, month, 1)
    if month == 12:
        last = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    return first, last


def week_start(d: date) -> date:
    """Понедельник недели, содержащей дату."""
    return d - timedelta(days=d.weekday())


def week_end(d: date) -> date:
    return week_start(d) + timedelta(days=6)


def date_range(start: date, end: date):
    cursor = start
    while cursor <= end:
        yield cursor
        cursor += timedelta(days=1)


def valid_time(value: Any) -> str:
    if not isinstance(value, str) or not TIME_RE.match(value):
        raise ValidationError("Время должно быть в формате HH:MM")
    return value


def valid_timezone(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Укажите часовой пояс")
    value = value.strip()
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValidationError("Неизвестный часовой пояс") from exc
    return value


def clamp_text(value: Any, field: str, max_len: int, required: bool = False) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValidationError(f"Поле «{field}» должно быть строкой")
    value = value.strip()
    if required and not value:
        raise ValidationError(f"Заполните поле «{field}»", {field: "required"})
    if len(value) > max_len:
        raise ValidationError(f"Поле «{field}» длиннее {max_len} символов", {field: "too_long"})
    return value


def to_float(value: Any, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Поле «{field}» должно быть числом") from exc
    if result != result or result in (float("inf"), float("-inf")):
        raise ValidationError(f"Некорректное число в поле «{field}»")
    return result


def to_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"Поле «{field}» должно быть числом")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Поле «{field}» должно быть целым числом") from exc
    return result


def json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def plural_ru(n: int, one: str, few: str, many: str) -> str:
    n = abs(n) % 100
    if 11 <= n <= 14:
        return many
    n %= 10
    if n == 1:
        return one
    if 2 <= n <= 4:
        return few
    return many


# Канонические единицы хранятся в единственном числе («минута», «стакан»),
# но старые записи и AI-планы могут приходить во множественном. Формы нужны,
# чтобы и серверные тексты звучали по-русски: «20 минут», а не «20 минута».
_UNIT_FORMS = {
    "раз": ("раз", "раза", "раз"),
    "раза": ("раз", "раза", "раз"),
    "минута": ("минута", "минуты", "минут"),
    "минуты": ("минута", "минуты", "минут"),
    "минут": ("минута", "минуты", "минут"),
    "стакан": ("стакан", "стакана", "стаканов"),
    "стаканы": ("стакан", "стакана", "стаканов"),
    "стаканов": ("стакан", "стакана", "стаканов"),
    "страница": ("страница", "страницы", "страниц"),
    "страницы": ("страница", "страницы", "страниц"),
    "страниц": ("страница", "страницы", "страниц"),
    "шаг": ("шаг", "шага", "шагов"),
    "шаги": ("шаг", "шага", "шагов"),
    "шагов": ("шаг", "шага", "шагов"),
}


def plural_unit(value: float, unit: str) -> str:
    if not unit:
        return ""
    forms = _UNIT_FORMS.get(str(unit).strip().lower())
    if not forms:
        return str(unit)
    number = abs(float(value or 0))
    if not number.is_integer():
        return forms[1]
    return plural_ru(int(number), *forms)


def format_amount(value: float, unit: str) -> str:
    number = float(value or 0)
    text = str(int(number)) if number.is_integer() else f"{number:g}"
    return f"{text} {plural_unit(number, unit)}".strip()



def human_minutes(minutes: int) -> str:
    hours, mins = divmod(int(minutes), 60)
    if hours and mins:
        return f"{hours} ч {mins} мин"
    if hours:
        return f"{hours} ч"
    return f"{mins} мин"
