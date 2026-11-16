"""WSGI-точка входа для Gunicorn на Render.

Запускает Flask-приложение и фоновый планировщик напоминаний.
Важно: запускайте Gunicorn с одним worker, иначе напоминания
могут отправляться несколько раз.
"""
from app import app
from tracker.notifications import start_scheduler

start_scheduler(app)
