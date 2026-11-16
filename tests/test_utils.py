"""Серверные тексты: единицы измерения и напоминания звучат по-русски."""
from __future__ import annotations

import unittest

from tracker.api_helpers import target_label
from tracker.notifications import build_reminder_text
from tracker.utils import format_amount, plural_unit


class UnitFormattingTests(unittest.TestCase):
    def test_canonical_units_are_pluralized(self):
        cases = [
            (1, "минута", "1 минута"),
            (2, "минута", "2 минуты"),
            (5, "минута", "5 минут"),
            (11, "минута", "11 минут"),
            (21, "минута", "21 минута"),
            (0, "минута", "0 минут"),
            (6, "стакан", "6 стаканов"),
            (2, "стакан", "2 стакана"),
            (1, "стакан", "1 стакан"),
            (3, "раз", "3 раза"),
            (0.5, "минута", "0.5 минуты"),
        ]
        for value, unit, expected in cases:
            with self.subTest(value=value, unit=unit):
                self.assertEqual(format_amount(value, unit), expected)

    def test_plural_units_are_normalized(self):
        self.assertEqual(format_amount(20, "минуты"), "20 минут")
        self.assertEqual(format_amount(6, "стаканы"), "6 стаканов")
        self.assertEqual(format_amount(10, "страницы"), "10 страниц")

    def test_unknown_unit_is_kept(self):
        self.assertEqual(plural_unit(3, "кг"), "кг")
        self.assertEqual(format_amount(3, ""), "3")

    def test_api_target_label(self):
        self.assertEqual(
            target_label({"type": "duration", "target_value": 20, "unit": "минута"}),
            "20 минут",
        )
        self.assertEqual(
            target_label({"type": "boolean", "target_value": 1, "unit": ""}),
            "Да / нет",
        )

    def test_reminder_uses_correct_case(self):
        user = {"name": "Саша"}
        habit = {"title": "Прогулка", "type": "duration", "target_value": 20, "unit": "минута"}
        self.assertIn("Цель — 20 минут", build_reminder_text(user, habit))
        water = {"title": "Вода", "type": "quantity", "target_value": 6, "unit": "стакан"}
        self.assertIn("Цель — 6 стаканов", build_reminder_text(user, water))


if __name__ == "__main__":
    unittest.main()
