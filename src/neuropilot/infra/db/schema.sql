-- NeuroPilot unified SQLite schema

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'researcher',
    failed_count  INTEGER NOT NULL DEFAULT 0,
    locked_until  TEXT,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS subjects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    gender      TEXT,
    age         INTEGER,
    diagnosis   TEXT,
    notes       TEXT,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(name)
);

CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id  INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    paradigm    TEXT NOT NULL DEFAULT 'MI',
    status      TEXT NOT NULL DEFAULT 'running',
    transport   TEXT,
    n_channels  INTEGER,
    srate       REAL,
    started_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    stopped_at  TEXT,
    notes       TEXT
);

CREATE TABLE IF NOT EXISTS trials (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    trial_uuid  TEXT NOT NULL UNIQUE,
    label       TEXT NOT NULL,
    onset_time  TEXT NOT NULL,
    offset_time TEXT,
    predicted   TEXT,
    confidence  REAL,
    eeg_file    TEXT,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS models (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id  INTEGER REFERENCES subjects(id) ON DELETE SET NULL,
    name        TEXT NOT NULL,
    algorithm   TEXT NOT NULL,
    file_path   TEXT NOT NULL UNIQUE,
    sha256      TEXT NOT NULL,
    accuracy    REAL,
    is_active   INTEGER NOT NULL DEFAULT 0,
    trained_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_sessions_subject ON sessions(subject_id);
CREATE INDEX IF NOT EXISTS idx_trials_session ON trials(session_id);
CREATE INDEX IF NOT EXISTS idx_models_subject ON models(subject_id);
