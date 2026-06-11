-- schema.sql  (SQLite version of luangprabang_heritage.sql)
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS heritage_categories (
    category_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    category_name_lo TEXT,
    category_name_en TEXT
);

CREATE TABLE IF NOT EXISTS heritage_houses (
    house_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    qr_code                TEXT    NOT NULL UNIQUE,
    house_number           TEXT,
    house_name_lo          TEXT,
    house_name_en          TEXT,
    owner_name_lo          TEXT,
    owner_name_en          TEXT,
    construction_year      INTEGER,
    architectural_style_lo TEXT,
    architectural_style_en TEXT,
    historical_significance_lo TEXT,
    historical_significance_en TEXT,
    description_lo         TEXT,
    description_en         TEXT,
    image_main             TEXT,
    status                 TEXT DEFAULT 'active' CHECK(status IN ('active','inactive')),
    house_type             TEXT,
    building_material      TEXT,
    latitude               REAL,
    longitude              REAL,
    created_at             TEXT DEFAULT (datetime('now')),
    updated_at             TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS heritage_images (
    image_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    house_id         INTEGER NOT NULL,
    image_path       TEXT,
    image_caption_lo TEXT,
    image_caption_en TEXT,
    display_order    INTEGER DEFAULT 0,
    created_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (house_id) REFERENCES heritage_houses(house_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS house_categories (
    house_id    INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    PRIMARY KEY (house_id, category_id),
    FOREIGN KEY (house_id)    REFERENCES heritage_houses(house_id)     ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES heritage_categories(category_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT NOT NULL UNIQUE,
    password    TEXT NOT NULL,
    fullname_lo TEXT,
    fullname_en TEXT,
    email       TEXT,
    role        TEXT DEFAULT 'viewer' CHECK(role IN ('admin','staff','viewer')),
    status      TEXT DEFAULT 'active' CHECK(status IN ('active','inactive')),
    last_login  TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS visit_logs (
    log_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    house_id       INTEGER,
    visitor_ip     TEXT,
    visitor_device TEXT,
    visit_date     TEXT,
    visit_time     TEXT,
    FOREIGN KEY (house_id) REFERENCES heritage_houses(house_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_visit_date  ON visit_logs(visit_date);
CREATE INDEX IF NOT EXISTS idx_house_date  ON visit_logs(house_id, visit_date);

-- ── Seed data ────────────────────────────────────────────────
INSERT OR IGNORE INTO heritage_categories (category_id, category_name_lo, category_name_en) VALUES
(1, 'ເຮືອນພື້ນເມືອງ',    'Traditional House'),
(2, 'ວັດວາອາຮາມ',         'Temple'),
(3, 'ອາຄານສະໄໝຝຣັ່ງ',     'French Colonial Building'),
(4, 'ອາຄານສະໄໝລາວ-ຝຣັ່ງ', 'Lao-French Architecture'),
(5, 'ຮ້ານຄ້າພື້ນເມືອງ',    'Traditional Shop House');
