"""Интеграционные тесты HTTP-API на временной базе SQLite."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tracker import create_app
from tracker.seed import ADMIN_EMAIL, ADMIN_PASSWORD, DEMO_EMAIL, DEMO_PASSWORD


class ApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        db_path = str(Path(cls.tmp.name) / "test.db")
        cls.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "DATABASE": db_path,
            "SCHEDULER_ENABLED": False,
            "SEED_DEMO": True,
            "DOCS_PUBLIC": True,
        })

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.client = self.app.test_client()

    # ------------------------------------------------------------ helpers
    def login_demo(self):
        response = self.client.post("/auth/demo")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()

    def login_admin(self):
        response = self.client.post("/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD,
        })
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()

    @staticmethod
    def habit_payload(**overrides):
        payload = {
            "title": "Тестовая привычка",
            "description": "Проверка API",
            "type": "boolean",
            "target_value": 1,
            "unit": "",
            "schedule": "daily",
            "times_per_week": 7,
            "reminder_time": "09:00",
            "color": "#C9623E",
            "icon": "spark",
            "freeze_limit": 2,
        }
        payload.update(overrides)
        return payload

    def create_habit(self, **overrides):
        response = self.client.post("/habits", json=self.habit_payload(**overrides))
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()["habit"]

    # ------------------------------------------------------------ auth
    def test_health_is_public(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])

    def test_unauthorized_access_is_rejected(self):
        response = self.client.get("/habits")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["code"], "unauthorized")

    def test_demo_login_and_profile(self):
        data = self.login_demo()
        self.assertTrue(data["user"]["email"] == DEMO_EMAIL)
        self.assertNotIn("password_hash", data["user"])

        me = self.client.get("/auth/me").get_json()
        self.assertEqual(me["user"]["email"], DEMO_EMAIL)
        self.assertFalse(me["onboarding_needed"])

        self.client.post("/auth/logout")
        self.assertIsNone(self.client.get("/auth/me").get_json()["user"])

    def test_login_with_wrong_password_fails(self):
        response = self.client.post("/auth/login", json={
            "email": DEMO_EMAIL, "password": "wrong-password",
        })
        self.assertIn(response.status_code, (401, 429))

    def test_csrf_origin_rejected(self):
        response = self.client.post(
            "/auth/login",
            json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
            headers={"Origin": "https://evil.example"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["code"], "csrf")

    # ------------------------------------------------------------ habits and logs
    def test_habit_crud_and_validation(self):
        self.login_demo()
        habit = self.create_habit(title="Проверка CRUD")
        self.assertEqual(habit["title"], "Проверка CRUD")
        self.assertEqual(habit["current_streak"], 0)

        listed = self.client.get("/habits").get_json()
        self.assertTrue(any(item["id"] == habit["id"] for item in listed["habits"]))

        updated = self.client.patch(
            f"/habits/{habit['id']}", json={"title": "Новое имя"},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["habit"]["title"], "Новое имя")

        invalid = self.client.post("/habits", json=self.habit_payload(title=""))
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.get_json()["code"], "validation_error")

        invalid_type = self.client.post("/habits", json=self.habit_payload(type="magic"))
        self.assertEqual(invalid_type.status_code, 400)

        deleted = self.client.delete(f"/habits/{habit['id']}")
        self.assertEqual(deleted.status_code, 200)
        self.assertTrue(deleted.get_json()["deleted"])

        restored = self.client.post(f"/habits/{habit['id']}/restore")
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(restored.get_json()["habit"]["title"], "Новое имя")

        permanent = self.client.delete(f"/habits/{habit['id']}?permanent=1")
        self.assertEqual(permanent.status_code, 200)

    def test_active_habit_limit(self):
        self.login_demo()
        current = self.client.get("/habits").get_json()
        free_slots = current["active_limit"] - current["active_count"]
        created = []
        for index in range(free_slots):
            created.append(self.create_habit(title=f"Лимит {index}"))
        overflow = self.client.post("/habits", json=self.habit_payload(title="Лишняя"))
        self.assertEqual(overflow.status_code, 409)
        self.assertEqual(overflow.get_json()["code"], "active_limit")
        for item in created:
            self.client.delete(f"/habits/{item['id']}?permanent=1")

    def test_log_flow_today_calendar_and_export(self):
        self.login_demo()
        habit = self.create_habit(title="Отметка в один тап", type="boolean")

        today = self.client.get("/today").get_json()
        self.assertTrue(any(item["id"] == habit["id"] for item in today["habits"]))
        date = today["date"]

        saved = self.client.post("/logs", json={
            "habit_id": habit["id"], "date": date, "value": 1, "status": "done",
        })
        self.assertEqual(saved.status_code, 200, saved.get_data(as_text=True))
        self.assertEqual(saved.get_json()["log"]["status"], "done")

        again = self.client.get("/today").get_json()
        entry = next(item for item in again["habits"] if item["id"] == habit["id"])
        self.assertEqual(entry["today_status"], "done")

        calendar = self.client.get(f"/calendar?month={date[:7]}").get_json()
        day = next(item for item in calendar["days"] if item["date"] == date)
        self.assertIn(day["status"], ("done", "partial"))
        self.assertGreaterEqual(day["done"], 1)

        day_view = self.client.get(f"/calendar/day?date={date}").get_json()
        self.assertTrue(day_view["editable"])
        self.assertTrue(any(item["habit_id"] == habit["id"] for item in day_view["entries"]))

        removed = self.client.delete(f"/logs?habit_id={habit['id']}&date={date}")
        self.assertEqual(removed.status_code, 200)
        self.assertTrue(removed.get_json()["removed"])

        self.client.delete(f"/habits/{habit['id']}?permanent=1")

    def test_freeze_limit_returns_conflict(self):
        self.login_demo()
        habit = self.create_habit(title="Заморозки", freeze_limit=1, type="boolean")
        today = self.client.get("/today").get_json()["date"]

        first = self.client.post("/logs", json={
            "habit_id": habit["id"], "date": today, "value": 0, "status": "frozen",
        })
        self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
        self.assertEqual(first.get_json()["freezes_left"], 0)

        second = self.client.post("/logs", json={
            "habit_id": habit["id"], "date": today, "value": 0, "status": "frozen",
        })
        # повторная заморозка того же дня не расходует лимит
        self.assertEqual(second.status_code, 200)

        self.client.delete(f"/habits/{habit['id']}?permanent=1")

    def test_stats_and_heatmap(self):
        self.login_demo()
        stats = self.client.get("/stats?days=30")
        self.assertEqual(stats.status_code, 200)
        data = stats.get_json()
        for key in ("today", "period", "overview", "habits", "series"):
            self.assertIn(key, data)
        self.assertGreaterEqual(len(data["habits"]), 1)

        heatmap = self.client.get("/stats/heatmap?year=2026")
        self.assertEqual(heatmap.status_code, 200)
        self.assertIn("days", heatmap.get_json())

    # ------------------------------------------------------------ AI
    def test_ai_requires_consent_then_falls_back(self):
        self.login_demo()
        self.client.patch("/settings", json={"ai_consent": False})
        status = self.client.get("/ai/status").get_json()
        self.assertTrue(status["enabled"])
        self.assertFalse(status["consent"])

        blocked = self.client.post("/ai/generate", json={"goal": "Больше движения"})
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.get_json()["code"], "consent_required")

        consent = self.client.patch("/settings", json={"ai_consent": True})
        self.assertEqual(consent.status_code, 200)

        plan = self.client.post("/ai/generate", json={"goal": "Больше движения каждый день"})
        self.assertEqual(plan.status_code, 200, plan.get_data(as_text=True))
        body = plan.get_json()
        self.assertTrue(body["fallback"])
        self.assertGreaterEqual(len(body["plan"]["habits"]), 3)
        self.assertLessEqual(len(body["plan"]["habits"]), 5)
        self.assertLess(body["remaining"], 10)

        review = self.client.post("/ai/review", json={})
        self.assertEqual(review.status_code, 200, review.get_data(as_text=True))
        review_body = review.get_json()
        self.assertIn("wins", review_body["review"])
        self.assertIn("recommendations", review_body["review"])

        history = self.client.get("/ai/history").get_json()
        self.assertGreaterEqual(len(history["requests"]), 2)

    def test_ai_consent_can_be_revoked(self):
        self.login_demo()
        self.client.patch("/settings", json={"ai_consent": False})
        blocked = self.client.post("/ai/generate", json={"goal": "Проверка согласия"})
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.get_json()["code"], "consent_required")

    # ------------------------------------------------------------ documents and exports
    def test_exports(self):
        self.login_demo()
        csv_response = self.client.get("/export.csv")
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("text/csv", csv_response.headers["Content-Type"])
        self.assertIn("attachment", csv_response.headers["Content-Disposition"])

        json_response = self.client.get("/export.json")
        self.assertEqual(json_response.status_code, 200)
        payload = json.loads(json_response.get_data(as_text=True))
        self.assertIn("habits", payload)

        pdf_response = self.client.get("/export/report.pdf")
        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response.headers["Content-Type"], "application/pdf")
        self.assertTrue(pdf_response.get_data().startswith(b"%PDF"))

    def test_documents(self):
        tz_md = self.client.get("/docs/tz.md")
        self.assertEqual(tz_md.status_code, 200)
        self.assertIn("text/markdown", tz_md.headers["Content-Type"])

        tz_pdf = self.client.get("/docs/tz.pdf")
        self.assertEqual(tz_pdf.status_code, 200)
        self.assertTrue(tz_pdf.get_data().startswith(b"%PDF"))

        for name, content_type in (
            ("schema.sql", "text/plain"),
            ("seed.json", "application/json"),
            ("README.md", "text/markdown"),
        ):
            response = self.client.get(f"/docs/file/{name}")
            self.assertEqual(response.status_code, 200, name)
            self.assertIn(content_type, response.headers["Content-Type"])
            self.assertGreater(len(response.get_data()), 10)
            response.close()

        missing = self.client.get("/docs/file/secret.txt")
        self.assertEqual(missing.status_code, 404)

    def test_openapi_document(self):
        response = self.client.get("/openapi.yaml")
        self.assertEqual(response.status_code, 200)
        self.assertIn("openapi", response.get_data(as_text=True))
        response.close()

    # ------------------------------------------------------------ admin
    def test_admin_section_requires_admin_role(self):
        self.login_demo()
        forbidden = self.client.get("/admin/overview")
        self.assertEqual(forbidden.status_code, 403)

        self.client.post("/auth/logout")
        self.login_admin()
        overview = self.client.get("/admin/overview")
        self.assertEqual(overview.status_code, 200)
        body = overview.get_json()
        for key in ("counts", "users", "templates", "errors"):
            self.assertIn(key, body)

    def test_delete_account_requires_confirmation_word(self):
        self.login_demo()
        wrong = self.client.delete("/account", json={"confirm": "нет"})
        self.assertEqual(wrong.status_code, 400)

    def test_admin_can_run_reminder_tick(self):
        self.login_admin()
        response = self.client.post("/reminders/tick")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        body = response.get_json()
        for key in ("checked", "sent", "skipped", "simulated", "errors"):
            self.assertIn(key, body)


if __name__ == "__main__":
    unittest.main()
