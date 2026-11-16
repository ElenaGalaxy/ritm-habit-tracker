"""Юнит-тесты бизнес-правил: серии, заморозки, partial, times_per_week."""
from __future__ import annotations

import unittest
from datetime import date

from tracker.stats import (
    aggregate_day_status,
    best_streak,
    completion,
    current_streak,
    freezes_left,
    freezes_used,
    habit_summary,
    status_for_value,
)


def habit(**overrides) -> dict:
    base = {
        "id": 1,
        "title": "Тест",
        "type": "boolean",
        "target_value": 1,
        "schedule": "daily",
        "times_per_week": 7,
        "freeze_limit": 2,
        "start_date": "2026-05-01",
        "created_at": "2026-05-01T00:00:00+00:00",
    }
    base.update(overrides)
    return base


def logs(**entries) -> dict:
    """logs(2026_05_18="done", ...) -> словарь отметок по датам."""
    result = {}
    for key, status in entries.items():
        iso = key.replace("_", "-")
        result[iso] = {"date": iso, "status": status, "value": 1}
    return result


TODAY = date(2026, 5, 20)  # среда


class DailyStreakTests(unittest.TestCase):
    def test_unmarked_today_does_not_break_streak(self):
        habit_row = habit(start_date="2026-05-01")
        data = logs(**{"2026_05_18": "done", "2026_05_19": "done"})
        self.assertEqual(current_streak(habit_row, data, TODAY), 2)

    def test_done_days_are_counted(self):
        habit_row = habit(start_date="2026-05-01")
        data = logs(**{"2026_05_17": "done", "2026_05_18": "done", "2026_05_19": "done"})
        self.assertEqual(current_streak(habit_row, data, TODAY), 3)

    def test_partial_keeps_streak_but_does_not_grow_it(self):
        habit_row = habit(start_date="2026-05-01")
        data = logs(**{"2026_05_18": "done", "2026_05_19": "partial"})
        self.assertEqual(current_streak(habit_row, data, TODAY), 1)

    def test_frozen_keeps_streak(self):
        habit_row = habit(start_date="2026-05-01")
        data = logs(**{"2026_05_17": "done", "2026_05_18": "frozen", "2026_05_19": "done"})
        self.assertEqual(current_streak(habit_row, data, TODAY), 2)

    def test_skipped_resets_streak(self):
        habit_row = habit(start_date="2026-05-01")
        data = logs(**{
            "2026_05_17": "done", "2026_05_18": "done",
            "2026_05_19": "skipped", "2026_05_20": "done",
        })
        self.assertEqual(current_streak(habit_row, data, TODAY), 1)

    def test_best_streak_remembers_past_runs(self):
        habit_row = habit(start_date="2026-05-01")
        data = logs(**{
            "2026_05_04": "done", "2026_05_05": "done", "2026_05_06": "done",
            "2026_05_07": "missed",
            "2026_05_18": "done", "2026_05_19": "done",
        })
        self.assertEqual(best_streak(habit_row, data, TODAY), 3)

    def test_weekdays_schedule_ignores_weekend(self):
        # 2026-05-16/17 — суббота и воскресенье.
        habit_row = habit(start_date="2026-05-01", schedule="weekdays")
        data = logs(**{
            "2026_05_14": "done", "2026_05_15": "done",
            "2026_05_18": "done", "2026_05_19": "done",
        })
        self.assertEqual(current_streak(habit_row, data, TODAY), 4)

    def test_habit_before_start_is_not_counted(self):
        habit_row = habit(start_date="2026-05-18")
        data = logs(**{"2026_05_16": "done", "2026_05_18": "done", "2026_05_19": "done"})
        self.assertEqual(current_streak(habit_row, data, TODAY), 2)


class TimesPerWeekTests(unittest.TestCase):
    """Неделя успешна, если выполнено не меньше N отметок (пауза засчитывается)."""

    def setUp(self):
        self.habit = habit(
            schedule="times_per_week", times_per_week=3, start_date="2026-05-04",
        )

    def test_current_streak_counts_successful_weeks(self):
        data = logs(**{
            # неделя 4–10 мая: 3 выполнения
            "2026_05_04": "done", "2026_05_06": "done", "2026_05_08": "done",
            # неделя 11–17 мая: 2 выполнения + пауза = 3
            "2026_05_11": "done", "2026_05_12": "done", "2026_05_13": "frozen",
            # текущая неделя ещё идёт
            "2026_05_18": "done",
        })
        self.assertEqual(current_streak(self.habit, data, TODAY), 2)

    def test_incomplete_week_breaks_streak(self):
        data = logs(**{
            "2026_05_04": "done", "2026_05_06": "done", "2026_05_08": "done",
            "2026_05_11": "done", "2026_05_12": "done",  # только 2 из 3
            "2026_05_18": "done", "2026_05_19": "done",
        })
        self.assertEqual(current_streak(self.habit, data, TODAY), 0)

    def test_partial_does_not_fill_weekly_quota(self):
        data = logs(**{
            # успешная неделя
            "2026_05_04": "done", "2026_05_05": "done", "2026_05_06": "done",
            # 2 выполнения + partial = квота всё ещё не набрана
            "2026_05_11": "done", "2026_05_12": "done", "2026_05_13": "partial",
            # текущая неделя ещё идёт
            "2026_05_18": "done", "2026_05_19": "done",
        })
        self.assertEqual(current_streak(self.habit, data, TODAY), 0)

    def test_completion_uses_weekly_target(self):
        data = logs(**{
            "2026_05_14": "done", "2026_05_15": "done", "2026_05_16": "partial",
            "2026_05_18": "done", "2026_05_19": "done", "2026_05_20": "done",
        })
        result = completion(self.habit, data, date(2026, 5, 14), date(2026, 5, 20), TODAY)
        self.assertEqual(result["days"], 7)
        self.assertEqual(result["expected"], 3.0)
        self.assertEqual(result["done"], 5)
        self.assertEqual(result["percent"], 100.0)

    def test_best_streak_for_weeks(self):
        data = logs(**{
            "2026_05_04": "done", "2026_05_05": "done", "2026_05_06": "done",
            "2026_05_11": "done", "2026_05_12": "done", "2026_05_13": "done",
            "2026_05_18": "done", "2026_05_19": "done",
        })
        self.assertGreaterEqual(best_streak(self.habit, data, TODAY), 2)


class FreezeTests(unittest.TestCase):
    def test_freeze_usage_is_limited_per_calendar_month(self):
        habit_row = habit(freeze_limit=2)
        data = logs(**{
            "2026_05_04": "frozen", "2026_05_12": "frozen",
            "2026_04_10": "frozen",
        })
        self.assertEqual(freezes_used(habit_row, data, 2026, 5), 2)
        self.assertEqual(freezes_left(habit_row, data, TODAY), 0)

    def test_freezes_reset_next_month(self):
        habit_row = habit(freeze_limit=2)
        data = logs(**{"2026_04_04": "frozen", "2026_04_12": "frozen"})
        self.assertEqual(freezes_left(habit_row, data, TODAY), 2)

    def test_zero_freeze_limit_is_respected(self):
        habit_row = habit(freeze_limit=0)
        data = logs(**{"2026_05_12": "frozen"})
        self.assertEqual(freezes_left(habit_row, data, TODAY), 0)


class StatusTests(unittest.TestCase):
    def test_status_for_value(self):
        self.assertEqual(status_for_value({"target_value": 6}, 6), "done")
        self.assertEqual(status_for_value({"target_value": 6}, 5), "partial")
        self.assertEqual(status_for_value({"target_value": 0}, 0.1), "partial")

    def test_aggregate_day_status(self):
        self.assertEqual(aggregate_day_status(["empty", "empty"]), "empty")
        self.assertEqual(aggregate_day_status(["done", "done"]), "done")
        self.assertEqual(aggregate_day_status(["done", "partial"]), "partial")
        self.assertEqual(aggregate_day_status(["skipped", "skipped"]), "skipped")
        self.assertEqual(aggregate_day_status(["frozen", "empty"]), "frozen")
        self.assertEqual(aggregate_day_status(["missed", "missed"]), "missed")

    def test_habit_summary_shape(self):
        habit_row = habit(start_date="2026-05-01")
        data = logs(**{"2026_05_19": "done"})
        summary = habit_summary(habit_row, data, TODAY)
        for key in ("current_streak", "best_streak", "streak_unit", "week",
                    "month", "freezes_used", "freezes_left", "best_weekday"):
            self.assertIn(key, summary)
        self.assertEqual(summary["streak_unit"], "days")
        self.assertEqual(summary["freezes_used"], 0)


if __name__ == "__main__":
    unittest.main()
