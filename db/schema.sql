-- Остатки Сладки MVP — SQLite schema (многоканальный вариант)

CREATE TABLE IF NOT EXISTS profiles (
    user_key TEXT PRIMARY KEY,
    channel TEXT,
    demo_used INTEGER DEFAULT 0,
    first_ingredient TEXT,
    last_seen_at TEXT,
    is_admin INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    user_key TEXT,
    state_json TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS recipes (
    id TEXT PRIMARY KEY,
    title_de TEXT,
    title_ru TEXT,
    is_classic INTEGER,
    category TEXT,
    time_min INTEGER,
    difficulty TEXT,
    format_type TEXT,
    short_desc TEXT,
    ingredients_json TEXT,
    steps_json TEXT,
    notes TEXT,
    storage_tip TEXT,
    must_have_json TEXT,
    all_ingredients_json TEXT,
    photo_url TEXT NULL,
    photo_file_id_tg TEXT NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS franz_phrases (
    id TEXT PRIMARY KEY,
    stage TEXT,
    subtype TEXT,
    text TEXT
);

CREATE TABLE IF NOT EXISTS franz_usage (
    user_key TEXT,
    phrase_id TEXT,
    used_at TEXT,
    PRIMARY KEY (user_key, phrase_id, used_at)
);
