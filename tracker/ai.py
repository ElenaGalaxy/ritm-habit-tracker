"""AI-ассистент: генерация привычек и недельный обзор.

Провайдер — любой OpenAI-совместимый endpoint (AI_API_KEY / AI_BASE_URL / AI_MODEL).
Если ключа нет или провайдер недоступен, возвращается валидный шаблонный план:
пользователь никогда не видит ошибку вместо результата.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from flask import current_app

from .utils import ValidationError, clamp_text

RATE_LIMIT_PER_DAY = 10

PLAN_SCHEMA = {
    "habits": [
        {
            "title": "Stories до 12:00",
            "description": "Короткая публикация, чтобы блог жил",
            "type": "boolean",
            "target_value": 1,
            "unit": "",
            "schedule": "daily",
            "times_per_week": 3,
            "micro_step": "Открыть камеру и снять один кадр",
            "trigger": "После утреннего кофе я сделаю Stories",
            "icon": "camera",
            "color": "#C9623E",
        }
    ],
    "summary": "Короткое объяснение, почему эти привычки подходят",
}

REVIEW_SCHEMA = {
    "wins": ["Что получается"],
    "gaps": ["Где просадка"],
    "recommendations": [
        {
            "text": "Конкретная рекомендация",
            "habit_title": "Название привычки или null",
            "suggested_target": 10,
        }
    ],
    "summary": "Одна мягкая итоговая фраза",
}


class RateLimited(Exception):
    pass


class AIConfig:
    def __init__(self, app):
        self.api_key = app.config.get("AI_API_KEY", "")
        self.base_url = (app.config.get("AI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.model = app.config.get("AI_MODEL") or "gpt-4o-mini"
        self.timeout = int(app.config.get("AI_TIMEOUT", 40))

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S | re.I)
    if fenced:
        text = fenced.group(1).strip()
    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ValidationError("AI не вернул JSON")
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError("AI вернул некорректный JSON") from exc


def _chat(config: AIConfig, messages: list[dict], max_tokens: int = 1400) -> dict:
    payload = {
        "model": config.model,
        "messages": messages,
        "temperature": 0.6,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        f"{config.base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=config.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"AI provider error: {type(exc).__name__}") from exc
    try:
        return _extract_json(body["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise ValidationError("Неожиданный формат ответа AI") from exc


SYSTEM_PROMPT = """Ты — бережный ассистент по привычкам внутри приложения-трекера.
Правила:
- Только бытовые и рабочие привычки. Никаких медицинских, психологических или лечебных советов, диагнозов.
- Без токсичной мотивации, стыда и давления. Тон спокойный и поддерживающий.
- Привычки маленькие и конкретные, выполнимые за один шаг.
- Отвечай строго ОДНИМ JSON-объектом без markdown и пояснений.
- Формат триггера: «После [действие] я сделаю [привычку]».
- 3–5 привычек, у каждой заполнены все поля схемы."""


def _fallback_plan(goal: str) -> dict:
    text = (goal or "").lower()
    is_blog = any(word in text for word in ("блог", "контент", "reels", "сторис", "stories", "пост", "снять"))
    if is_blog:
        habits = [
            {
                "title": "Stories до 12:00", "description": "Один короткий кадр, чтобы блог оставался живым",
                "type": "boolean", "target_value": 1, "unit": "", "schedule": "daily",
                "times_per_week": 7, "micro_step": "Снять один кадр без монтажа",
                "trigger": "После утреннего кофе я сделаю Stories",
                "icon": "camera", "color": "#C9623E",
            },
            {
                "title": "Сценарий Reels 20 минут", "description": "Спокойная работа над следующим роликом",
                "type": "duration", "target_value": 20, "unit": "минута", "schedule": "times_per_week",
                "times_per_week": 5, "micro_step": "Открыть заметки и написать одну мысль",
                "trigger": "После обеда я 20 минут пишу сценарий Reels",
                "icon": "pen", "color": "#5C7A5A",
            },
            {
                "title": "Прогулка 30 минут", "description": "Пауза от экрана и свежая голова",
                "type": "duration", "target_value": 30, "unit": "минута", "schedule": "daily",
                "times_per_week": 7, "micro_step": "Выйти на улицу хотя бы на 5 минут",
                "trigger": "После обеда я выхожу на прогулку",
                "icon": "walk", "color": "#A8763E",
            },
            {
                "title": "Вода 6 стаканов", "description": "Базовая забота о себе в течение дня",
                "type": "quantity", "target_value": 6, "unit": "стакан", "schedule": "daily",
                "times_per_week": 7, "micro_step": "Поставить стакан рядом с рабочим местом",
                "trigger": "После пробуждения я наливаю первый стакан воды",
                "icon": "water", "color": "#4F7C8A",
            },
            {
                "title": "Без телефона после 23:00", "description": "Спокойное завершение дня без ленты",
                "type": "boolean", "target_value": 1, "unit": "", "schedule": "daily",
                "times_per_week": 7, "micro_step": "Убрать телефон на зарядку вне спальни",
                "trigger": "После вечерних дел я убираю телефон на зарядку",
                "icon": "moon", "color": "#6B5B8E",
            },
        ]
    elif any(word in text for word in ("спорт", "бег", "трениров", "форме", "движ")):
        habits = [
            {"title": "Зарядка 10 минут", "description": "Мягкое начало дня",
             "type": "duration", "target_value": 10, "unit": "минута", "schedule": "daily",
             "times_per_week": 7, "micro_step": "Сделать одну минуту растяжки",
             "trigger": "После пробуждения я делаю зарядку", "icon": "sun", "color": "#C9623E"},
            {"title": "Шаги 6000", "description": "Движение в течение дня",
             "type": "quantity", "target_value": 6000, "unit": "шаг", "schedule": "daily",
             "times_per_week": 7, "micro_step": "Пройти одну остановку пешком",
             "trigger": "После работы я иду пешком", "icon": "run", "color": "#5C7A5A"},
            {"title": "Вода 6 стаканов", "description": "Базовая гидратация",
             "type": "quantity", "target_value": 6, "unit": "стакан", "schedule": "daily",
             "times_per_week": 7, "micro_step": "Налить первый стакан утром",
             "trigger": "После пробуждения я наливаю стакан воды", "icon": "water", "color": "#4F7C8A"},
        ]
    elif any(word in text for word in ("учёб", "учеб", "курс", "книг", "учить", "язык")):
        habits = [
            {"title": "Учёба 25 минут", "description": "Один короткий блок без отвлечений",
             "type": "duration", "target_value": 25, "unit": "минута", "schedule": "weekdays",
             "times_per_week": 5, "micro_step": "Открыть материалы и повторить вчерашнее",
             "trigger": "После завтрака я сажусь за учёбу", "icon": "book", "color": "#C9623E"},
            {"title": "Страницы 10", "description": "Чтение без спешки",
             "type": "quantity", "target_value": 10, "unit": "страница", "schedule": "daily",
             "times_per_week": 7, "micro_step": "Прочитать одну страницу",
             "trigger": "После ужина я читаю книгу", "icon": "book", "color": "#5C7A5A"},
            {"title": "Конспект дня", "description": "Одна мысль, которая осталась",
             "type": "boolean", "target_value": 1, "unit": "", "schedule": "weekdays",
             "times_per_week": 5, "micro_step": "Записать одну фразу",
             "trigger": "После учёбы я записываю одну мысль", "icon": "pen", "color": "#A8763E"},
        ]
    else:
        habits = [
            {"title": "Маленький шаг к цели", "description": "Одно конкретное действие в день",
             "type": "boolean", "target_value": 1, "unit": "", "schedule": "daily",
             "times_per_week": 7, "micro_step": "Выбрать самый маленький шаг",
             "trigger": "После завтрака я делаю маленький шаг к цели", "icon": "target", "color": "#C9623E"},
            {"title": "Прогулка 20 минут", "description": "Пауза и свежий воздух",
             "type": "duration", "target_value": 20, "unit": "минута", "schedule": "daily",
             "times_per_week": 7, "micro_step": "Выйти на улицу на 5 минут",
             "trigger": "После обеда я выхожу на прогулку", "icon": "walk", "color": "#5C7A5A"},
            {"title": "Вода 6 стаканов", "description": "Базовая забота о себе",
             "type": "quantity", "target_value": 6, "unit": "стакан", "schedule": "daily",
             "times_per_week": 7, "micro_step": "Поставить стакан рядом",
             "trigger": "После пробуждения я наливаю стакан воды", "icon": "water", "color": "#4F7C8A"},
            {"title": "Без телефона после 23:00", "description": "Спокойный вечер",
             "type": "boolean", "target_value": 1, "unit": "", "schedule": "daily",
             "times_per_week": 7, "micro_step": "Убрать телефон на зарядку",
             "trigger": "После вечерних дел я убираю телефон", "icon": "moon", "color": "#6B5B8E"},
        ]
    return {
        "habits": habits,
        "summary": "Небольшие ежедневные шаги под вашу цель. Начните с одного — остальное подтянется.",
        "fallback": True,
    }


def _fallback_review(data: dict) -> dict:
    habits = data.get("habits", [])
    wins, gaps, recs = [], [], []
    for item in habits:
        pct = item.get("completion_percent", 0)
        title = item.get("title", "Привычка")
        target = item.get("target_value") or 1
        if pct >= 70:
            wins.append(f"«{title}»: {round(pct)}% недельного плана — хороший ритм.")
        elif pct < 50:
            gaps.append(f"«{title}»: за неделю выполнено около {round(pct)}% запланированного.")
            if item.get("type") in ("quantity", "duration") and target > 5:
                suggested = max(1, round(target / 2))
                recs.append({
                    "text": f"Уменьшите цель «{title}» с {target:g} до {suggested:g} — маленький шаг легче повторить.",
                    "habit_title": title,
                    "suggested_target": suggested,
                })
            else:
                recs.append({
                    "text": f"Попробуйте один микро-шаг по «{title}» в удобное время и не требуйте большего на этой неделе.",
                    "habit_title": title,
                    "suggested_target": None,
                })
        else:
            wins.append(f"«{title}» держится на уровне {round(pct)}% — уже устойчивый ритм.")
    if not habits:
        wins = ["Вы открыли трекер и посмотрели на свою неделю — это уже шаг."]
        gaps = ["Пока нет данных для анализа."]
    if not recs:
        recs = [
            {"text": "Оставьте одну привычку как опору и отметьте её в ближайшие 10 минут.",
             "habit_title": None, "suggested_target": None},
            {"text": "Поставьте напоминание на время, когда вам реально удобно, а не «идеально».",
             "habit_title": None, "suggested_target": None},
        ]
    if len(recs) == 1:
        recs.append({"text": "Разрешите себе частичное выполнение: оно сохраняет ритм.",
                     "habit_title": None, "suggested_target": None})
    return {
        "wins": wins[:3],
        "gaps": gaps[:3],
        "recommendations": recs[:3],
        "summary": "Главное — вернуться, а не пройти идеально. Один небольшой шаг на этой неделе уже достаточен.",
        "fallback": True,
    }


def generate_plan(goal: str, app=None) -> tuple[dict, str, str]:
    """Возвращает (план, provider, status). status: ok | fallback."""
    app = app or current_app
    goal = clamp_text(goal, "цель", 500, required=True)
    config = AIConfig(app)
    if not config.enabled:
        return _fallback_plan(goal), "fallback", "fallback"
    try:
        payload = _chat(config, [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": (
                "Цель пользователя: «" + goal + "».\n"
                "Верни JSON строго такой структуры:\n" + json.dumps(PLAN_SCHEMA, ensure_ascii=False)
            )},
        ])
        return payload, config.model, "ok"
    except Exception:
        if app.config.get("TESTING"):
            raise
        return _fallback_plan(goal), "fallback", "fallback"


def generate_review(review_data: dict, goal: str, app=None) -> tuple[dict, str, str]:
    app = app or current_app
    config = AIConfig(app)
    if not config.enabled:
        return _fallback_review(review_data), "fallback", "fallback"
    try:
        payload = _chat(config, [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": (
                "Данные за последние 7 дней (JSON):\n"
                + json.dumps(review_data, ensure_ascii=False)
                + "\nЦель пользователя: «" + (goal or "вести регулярную жизнь без выгорания") + "».\n"
                "Сделай недельный обзор: что получается, где просадка, 2–3 конкретные рекомендации. "
                "Не давай медицинских советов. Верни JSON строго такой структуры:\n"
                + json.dumps(REVIEW_SCHEMA, ensure_ascii=False)
            )},
        ], max_tokens=900)
        return payload, config.model, "ok"
    except Exception:
        if app.config.get("TESTING"):
            raise
        return _fallback_review(review_data), "fallback", "fallback"
