"""Расчёт серий, процента выполнения, заморозок и агрегатов календаря.

Все функции — чистые: получают привычку, словарь отметок и дату отсчёта.
Это позволяет покрыть бизнес-правила тестами без базы данных.

Правила MVP:
  * daily / weekdays: серия считается по запланированным дням;
  * times_per_week: серия считается по неделям (пн–вс), неделя успешна,
    если выполнено не меньше N раз;
  * frozen сохраняет серию и засчитывается в недельную квоту;
  * partial не увеличивает серию, но не обнуляет её (мягкий тон интерфейса);
  * skipped и missed обнуляют серию (для сохранения есть заморозка);
  * сегодняшний ещё не отмеченный день не обнуляет текущую серию.
"""
from __future__ import annotations

from datetime import date, timedelta

from .utils import date_range, parse_date, week_end, week_start

WEEKDAY_NAMES = [
    "Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье",
]
WEEKDAY_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


# ------------------------------------------------------------------ базовое

def normalize_logs(logs) -> dict[str, dict]:
    if isinstance(logs, dict):
        return logs
    return {log["date"]: log for log in logs}


def habit_start(habit: dict) -> date:
    raw = habit.get("start_date") or habit.get("created_at", "")[:10]
    try:
        return parse_date(raw[:10])
    except Exception:
        return date(1970, 1, 1)


def is_scheduled(habit: dict, d: date) -> bool:
    schedule = habit.get("schedule", "daily")
    if schedule == "weekdays":
        return d.weekday() < 5
    return True  # daily и times_per_week: отмечать можно в любой день


def requirement_per_week(habit: dict) -> int:
    if habit.get("schedule") != "times_per_week":
        return 7 if habit.get("schedule", "daily") == "daily" else 5
    return max(1, min(7, int(habit.get("times_per_week", 3))))


def status_for_value(habit: dict, value: float) -> str:
    target = float(habit.get("target_value") or 1)
    if target <= 0:
        target = 1
    return "done" if value >= target else "partial"


def day_status(habit: dict, log: dict | None, d: date, today: date) -> str:
    """Статус привычки в конкретный день для календаря."""
    if log:
        status = log.get("status", "done")
        return status if status in ("done", "partial", "skipped", "missed", "frozen") else "done"
    if d > today:
        return "empty"
    if d < habit_start(habit):
        return "empty"
    if not is_scheduled(habit, d):
        return "empty"
    if habit.get("schedule") == "times_per_week":
        return "empty"  # квота недели, а не конкретного дня
    return "missed" if d < today else "empty"


def _is_active_on(habit: dict, d: date) -> bool:
    return d >= habit_start(habit)


# ------------------------------------------------------------------ серии

def _daily_backwards_run(habit: dict, logs: dict[str, dict], today: date) -> int:
    start = habit_start(habit)
    cursor = today
    run = 0

    # Сегодняшний незаполненный день не должен ломать серию.
    if cursor >= start and is_scheduled(habit, cursor) and cursor.isoformat() not in logs:
        cursor -= timedelta(days=1)

    while cursor >= start:
        if not is_scheduled(habit, cursor):
            cursor -= timedelta(days=1)
            continue
        log = logs.get(cursor.isoformat())
        if log is None:
            break
        status = log.get("status", "done")
        if status == "done":
            run += 1
        elif status in ("frozen", "partial"):
            pass  # серия сохраняется, но не растёт
        else:  # missed / skipped
            break
        cursor -= timedelta(days=1)
    return run


def _daily_best_run(habit: dict, logs: dict[str, dict], today: date) -> int:
    start = habit_start(habit)
    end = min(today, today)
    run = 0
    best = 0
    for d in date_range(start, end):
        if not is_scheduled(habit, d):
            continue
        log = logs.get(d.isoformat())
        if log is None:
            if d == today:
                continue  # сегодня ещё есть время
            run = 0
            continue
        status = log.get("status", "done")
        if status == "done":
            run += 1
            best = max(best, run)
        elif status in ("frozen", "partial"):
            best = max(best, run)
        else:
            run = 0
    return max(best, run)


def _week_weeks(habit: dict, today: date) -> list[date]:
    start = week_start(habit_start(habit))
    current = week_start(today)
    weeks = []
    cursor = start
    while cursor <= current:
        weeks.append(cursor)
        cursor += timedelta(days=7)
    return weeks


def _week_done_count(habit: dict, logs: dict[str, dict], monday: date, today: date) -> int:
    start = habit_start(habit)
    count = 0
    for i in range(7):
        d = monday + timedelta(days=i)
        if d < start or d > today:
            continue
        log = logs.get(d.isoformat())
        if log and log.get("status") in ("done", "frozen"):
            count += 1
    return count


def _week_target(habit: dict, monday: date) -> int:
    """Для первой неполной недели цель пропорционально меньше."""
    start = habit_start(habit)
    target = requirement_per_week(habit)
    if start > monday:
        days_available = (week_end(monday) - start).days + 1
        return max(1, min(target, days_available))
    return target


def _weekly_backwards_run(habit: dict, logs: dict[str, dict], today: date) -> int:
    weeks = _week_weeks(habit, today)
    current = week_start(today)
    run = 0
    for monday in reversed(weeks):
        done = _week_done_count(habit, logs, monday, today)
        target = _week_target(habit, monday)
        if done >= target:
            run += 1
        elif monday == current:
            continue
        else:
            break
    return run


def _weekly_best_run(habit: dict, logs: dict[str, dict], today: date) -> int:
    weeks = _week_weeks(habit, today)
    current = week_start(today)
    run = 0
    best = 0
    for monday in weeks:
        done = _week_done_count(habit, logs, monday, today)
        target = _week_target(habit, monday)
        if done >= target:
            run += 1
            best = max(best, run)
        elif monday == current:
            continue  # неделя ещё идёт
        else:
            run = 0
    return max(best, run)


def current_streak(habit: dict, logs, today: date) -> int:
    logs = normalize_logs(logs)
    if habit.get("schedule") == "times_per_week":
        return _weekly_backwards_run(habit, logs, today)
    return _daily_backwards_run(habit, logs, today)


def best_streak(habit: dict, logs, today: date) -> int:
    logs = normalize_logs(logs)
    if habit.get("schedule") == "times_per_week":
        return max(_weekly_best_run(habit, logs, today), _weekly_backwards_run(habit, logs, today))
    return max(_daily_best_run(habit, logs, today), _daily_backwards_run(habit, logs, today))


def streak_unit(habit: dict) -> str:
    return "weeks" if habit.get("schedule") == "times_per_week" else "days"


# ------------------------------------------------------------------ выполнение

def completion(habit: dict, logs, start: date, end: date, today: date) -> dict:
    """Процент выполнения за период [start, end].

    Для daily/weekdays знаменатель — запланированные дни.
    Для times_per_week — недельная квота, пропорциональная длине периода.
    """
    logs = normalize_logs(logs)
    habit_from = habit_start(habit)
    lo = max(start, habit_from)
    hi = min(end, today)
    if lo > hi:
        return {"expected": 0.0, "done": 0, "frozen": 0, "partial": 0,
                "missed": 0, "percent": 0.0, "days": 0}

    days = list(date_range(lo, hi))
    done = frozen = partial = missed = 0
    for d in days:
        log = logs.get(d.isoformat())
        if log:
            status = log.get("status")
            if status == "done":
                done += 1
            elif status == "frozen":
                frozen += 1
            elif status == "partial":
                partial += 1
            elif status in ("missed", "skipped"):
                missed += 1

    if habit.get("schedule") == "times_per_week":
        expected = requirement_per_week(habit) * (len(days) / 7.0)
        expected = min(expected, float(len(days)))
    else:
        expected = float(sum(1 for d in days if is_scheduled(habit, d)))
        # незаполненные прошедшие дни считаются пропусками
        for d in days:
            if d < today and is_scheduled(habit, d) and d.isoformat() not in logs:
                missed += 1

    expected = round(expected, 2)
    percent = 0.0 if expected <= 0 else min(100.0, round(done / expected * 100, 1))
    return {
        "expected": expected,
        "done": done,
        "frozen": frozen,
        "partial": partial,
        "missed": missed,
        "percent": percent,
        "days": len(days),
    }


def freezes_used(habit: dict, logs, year: int, month: int) -> int:
    logs = normalize_logs(logs)
    prefix = f"{year:04d}-{month:02d}-"
    return sum(
        1 for d, log in logs.items()
        if d.startswith(prefix) and log.get("status") == "frozen"
    )


def freezes_left(habit: dict, logs, today: date) -> int:
    used = freezes_used(habit, logs, today.year, today.month)
    return max(0, int(habit.get("freeze_limit", 2)) - used)


def best_weekday(logs, start: date, end: date) -> dict:
    logs = normalize_logs(logs)
    counts = [0] * 7
    for d in date_range(start, end):
        log = logs.get(d.isoformat())
        if log and log.get("status") == "done":
            counts[d.weekday()] += 1
    if not any(counts):
        return {"weekday": None, "name": "—", "count": 0}
    best_idx = max(range(7), key=lambda i: (counts[i], -i))
    return {
        "weekday": best_idx,
        "name": WEEKDAY_NAMES[best_idx],
        "short": WEEKDAY_SHORT[best_idx],
        "count": counts[best_idx],
        "by_day": counts,
    }


# ------------------------------------------------------------------ агрегаты

def aggregate_day_status(statuses: list[str]) -> str:
    meaningful = [s for s in statuses if s != "empty"]
    if not meaningful:
        return "empty"
    if all(s == "done" for s in meaningful):
        return "done"
    if all(s in ("frozen", "empty") for s in meaningful):
        return "frozen"
    if any(s in ("done", "partial") for s in meaningful):
        if all(s == "missed" for s in meaningful):
            return "missed"
        return "partial"
    if any(s == "frozen" for s in meaningful):
        return "frozen"
    if all(s == "skipped" for s in meaningful):
        return "skipped"
    return "missed"


def day_intensity(done: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(done / total, 3)


def habit_summary(habit: dict, logs, today: date) -> dict:
    logs = normalize_logs(logs)
    week_start_date = today - timedelta(days=6)
    month_start_date = today.replace(day=1)
    week = completion(habit, logs, week_start_date, today, today)
    month = completion(habit, logs, month_start_date, today, today)
    return {
        "current_streak": current_streak(habit, logs, today),
        "best_streak": best_streak(habit, logs, today),
        "streak_unit": streak_unit(habit),
        "week": week,
        "month": month,
        "freezes_used": freezes_used(habit, logs, today.year, today.month),
        "freezes_left": freezes_left(habit, logs, today),
        "best_weekday": best_weekday(logs, max(week_start_date, habit_start(habit)), today),
    }


def overall_summary(habits: list[dict], logs_by_habit: dict[int, list[dict]], today: date) -> dict:
    summaries = []
    for habit in habits:
        logs = normalize_logs(logs_by_habit.get(habit["id"], []))
        summaries.append({"habit": habit, **habit_summary(habit, logs, today)})

    current_best = max((s["current_streak"] for s in summaries), default=0)
    best_ever = max((s["best_streak"] for s in summaries), default=0)
    week_percent = (
        round(sum(s["week"]["percent"] for s in summaries) / len(summaries), 1)
        if summaries else 0.0
    )
    month_percent = (
        round(sum(s["month"]["percent"] for s in summaries) / len(summaries), 1)
        if summaries else 0.0
    )
    freezes_left = sum(s["freezes_left"] for s in summaries)

    combined_logs: dict[str, dict] = {}
    for habit in habits:
        for log in logs_by_habit.get(habit["id"], []):
            current = combined_logs.get(log["date"])
            if current is None or log.get("status") == "done":
                combined_logs[log["date"]] = log
    best_day = best_weekday(combined_logs, today - timedelta(days=90), today)

    return {
        "current_streak": current_best,
        "best_streak": best_ever,
        "week_percent": week_percent,
        "month_percent": month_percent,
        "freezes_left": freezes_left,
        "best_weekday": best_day,
        "habits": summaries,
        "total_habits": len(habits),
    }


def heatmap_year(habits: list[dict], logs_by_habit: dict[int, list[dict]], year: int,
                 today: date) -> list[dict]:
    """Дневная тепловая карта за год (для годового режима календаря)."""
    start = date(year, 1, 1)
    end = min(date(year, 12, 31), today)
    if start > end:
        return []

    logs = {habit["id"]: normalize_logs(logs_by_habit.get(habit["id"], [])) for habit in habits}
    result = []
    for d in date_range(start, end):
        total = done = 0
        statuses = []
        for habit in habits:
            if d < habit_start(habit) or not is_scheduled(habit, d):
                continue
            total += 1
            status = day_status(habit, logs[habit["id"]].get(d.isoformat()), d, today)
            statuses.append(status)
            if status == "done":
                done += 1
        result.append({
            "date": d.isoformat(),
            "done": done,
            "total": total,
            "intensity": day_intensity(done, total),
            "status": aggregate_day_status(statuses),
        })
    return result


def weekly_review_data(habits: list[dict], logs_by_habit: dict[int, list[dict]],
                       today: date) -> dict:
    start = today - timedelta(days=6)
    items = []
    for habit in habits:
        logs = normalize_logs(logs_by_habit.get(habit["id"], []))
        stats = completion(habit, logs, start, today, today)
        items.append({
            "habit_id": habit["id"],
            "title": habit["title"],
            "type": habit.get("type"),
            "target_value": habit.get("target_value"),
            "unit": habit.get("unit"),
            "schedule": habit.get("schedule"),
            "times_per_week": habit.get("times_per_week"),
            "completion_percent": stats["percent"],
            "done": stats["done"],
            "frozen": stats["frozen"],
            "partial": stats["partial"],
            "missed": stats["missed"],
            "current_streak": current_streak(habit, logs, today),
        })
    return {"period": {"from": start.isoformat(), "to": today.isoformat()}, "habits": items}
