-- ============================================================
--  Habit Tracker MVP — схема базы данных (SQLite)
--  Хранение дат отметок: локальная календарная дата пользователя.
--  Служебные метки времени: UTC ISO-8601.
-- ============================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS users (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    name                  TEXT    NOT NULL,
    email                 TEXT    NOT NULL COLLATE NOCASE UNIQUE,
    password_hash         TEXT    NOT NULL,
    role                  TEXT    NOT NULL DEFAULT 'user'
                                  CHECK (role IN ('user', 'admin')),
    timezone              TEXT    NOT NULL DEFAULT 'Europe/Moscow',
    goal                  TEXT    NOT NULL DEFAULT '',
    quiet_hours_start     TEXT    NOT NULL DEFAULT '22:00',
    quiet_hours_end       TEXT    NOT NULL DEFAULT '08:00',
    telegram_id           TEXT,
    telegram_link_code    TEXT,
    telegram_connected_at TEXT,
    reminder_channel      TEXT    NOT NULL DEFAULT 'telegram'
                                  CHECK (reminder_channel IN ('telegram', 'none')),
    ai_enabled            INTEGER NOT NULL DEFAULT 1,
    ai_consent            INTEGER NOT NULL DEFAULT 0,
    conditions_enabled    TEXT    NOT NULL DEFAULT
                          '{"streak_badge":true,"missed_reminder":true,"low_week":true}',
    theme                 TEXT    NOT NULL DEFAULT 'light'
                                  CHECK (theme IN ('light', 'dark')),
    onboarded_at          TEXT,
    created_at            TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash  TEXT    NOT NULL UNIQUE,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TEXT    NOT NULL,
    expires_at  TEXT    NOT NULL,
    user_agent  TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

CREATE TABLE IF NOT EXISTS habits (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title            TEXT    NOT NULL,
    description      TEXT    NOT NULL DEFAULT '',
    icon             TEXT    NOT NULL DEFAULT 'spark',
    color            TEXT    NOT NULL DEFAULT '#C9623E',
    type             TEXT    NOT NULL DEFAULT 'boolean'
                             CHECK (type IN ('boolean', 'quantity', 'duration')),
    target_value     REAL    NOT NULL DEFAULT 1,
    unit             TEXT    NOT NULL DEFAULT '',
    schedule         TEXT    NOT NULL DEFAULT 'daily'
                             CHECK (schedule IN ('daily', 'weekdays', 'times_per_week')),
    times_per_week   INTEGER NOT NULL DEFAULT 3
                             CHECK (times_per_week BETWEEN 1 AND 7),
    reminder_time    TEXT    NOT NULL DEFAULT '09:00',
    status           TEXT    NOT NULL DEFAULT 'active'
                             CHECK (status IN ('active', 'paused', 'completed', 'archived')),
    freeze_limit     INTEGER NOT NULL DEFAULT 2
                             CHECK (freeze_limit BETWEEN 0 AND 5),
    start_date       TEXT    NOT NULL,
    sort_order       INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT    NOT NULL,
    updated_at       TEXT    NOT NULL,
    deleted_at       TEXT
);
CREATE INDEX IF NOT EXISTS idx_habits_user ON habits(user_id, status);

CREATE TABLE IF NOT EXISTS habit_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    habit_id    INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date        TEXT    NOT NULL,
    value       REAL    NOT NULL DEFAULT 0,
    status      TEXT    NOT NULL
                        CHECK (status IN ('done', 'partial', 'skipped', 'missed', 'frozen')),
    note        TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL,
    UNIQUE (habit_id, date)
);
CREATE INDEX IF NOT EXISTS idx_logs_user_date ON habit_logs(user_id, date);
CREATE INDEX IF NOT EXISTS idx_logs_habit_date ON habit_logs(habit_id, date);

CREATE TABLE IF NOT EXISTS condition_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    habit_id    INTEGER REFERENCES habits(id) ON DELETE CASCADE,
    type        TEXT    NOT NULL
                        CHECK (type IN ('streak_badge', 'missed_reminder', 'low_week')),
    event_key   TEXT    NOT NULL,
    title       TEXT    NOT NULL,
    message     TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,
    seen_at     TEXT,
    UNIQUE (habit_id, type, event_key)
);
CREATE INDEX IF NOT EXISTS idx_events_user ON condition_events(user_id, seen_at);

CREATE TABLE IF NOT EXISTS reminder_sends (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    habit_id    INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
    date        TEXT    NOT NULL,
    due_at      TEXT    NOT NULL,
    sent_at     TEXT,
    channel     TEXT    NOT NULL DEFAULT 'telegram',
    status      TEXT    NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'sent', 'simulated', 'skipped', 'error')),
    error       TEXT    NOT NULL DEFAULT '',
    UNIQUE (habit_id, date)
);
CREATE INDEX IF NOT EXISTS idx_reminder_due ON reminder_sends(status, due_at);

CREATE TABLE IF NOT EXISTS notifications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    habit_id    INTEGER REFERENCES habits(id) ON DELETE SET NULL,
    channel     TEXT    NOT NULL DEFAULT 'telegram',
    kind        TEXT    NOT NULL DEFAULT 'reminder',
    text        TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'simulated',
    created_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS ai_requests (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type          TEXT    NOT NULL
                          CHECK (type IN ('generate_habits', 'weekly_review')),
    input_text    TEXT    NOT NULL,
    output_json   TEXT    NOT NULL DEFAULT '{}',
    provider      TEXT    NOT NULL DEFAULT 'fallback',
    status        TEXT    NOT NULL DEFAULT 'ok'
                          CHECK (status IN ('ok', 'fallback', 'invalid', 'error', 'rate_limited')),
    created_at    TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ai_user_date ON ai_requests(user_id, created_at);

CREATE TABLE IF NOT EXISTS habit_templates (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    title          TEXT    NOT NULL,
    description    TEXT    NOT NULL DEFAULT '',
    icon           TEXT    NOT NULL DEFAULT 'spark',
    color          TEXT    NOT NULL DEFAULT '#C9623E',
    type           TEXT    NOT NULL DEFAULT 'boolean',
    target_value   REAL    NOT NULL DEFAULT 1,
    unit           TEXT    NOT NULL DEFAULT '',
    schedule       TEXT    NOT NULL DEFAULT 'daily',
    times_per_week INTEGER NOT NULL DEFAULT 3,
    is_active      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS error_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    level       TEXT    NOT NULL DEFAULT 'error',
    message     TEXT    NOT NULL,
    path        TEXT    NOT NULL DEFAULT '',
    method      TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_errors_created ON error_logs(created_at DESC);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
