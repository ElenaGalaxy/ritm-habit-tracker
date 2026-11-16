"""Условия: настройки приходят и словарём, и JSON-строкой из SQLite."""
from __future__ import annotations

import unittest

from tracker.conditions import DEFAULT_SETTINGS, enabled_settings


class ConditionsSettingsTests(unittest.TestCase):
    def test_missing_value_uses_defaults(self):
        self.assertEqual(enabled_settings({}), DEFAULT_SETTINGS)

    def test_dict_overrides_defaults(self):
        result = enabled_settings({"conditions_enabled": {"low_week": False}})
        self.assertFalse(result["low_week"])
        self.assertTrue(result["streak_badge"])

    def test_json_string_is_parsed(self):
        result = enabled_settings({
            "conditions_enabled": '{"streak_badge": false, "missed_reminder": false}',
        })
        self.assertFalse(result["streak_badge"])
        self.assertFalse(result["missed_reminder"])
        self.assertTrue(result["low_week"])

    def test_broken_json_falls_back_to_defaults(self):
        self.assertEqual(enabled_settings({"conditions_enabled": "не json"}), DEFAULT_SETTINGS)


if __name__ == "__main__":
    unittest.main()
