CREATE TABLE IF NOT EXISTS products (
    product_code TEXT    PRIMARY KEY,
    product_name TEXT    NOT NULL,
    unit         TEXT    NOT NULL,
    created_at   TEXT    NOT NULL,
    seq          INTEGER NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS stock_in (
    voucher_no   TEXT    PRIMARY KEY,
    product_code TEXT    NOT NULL REFERENCES products (product_code),
    quantity     INTEGER NOT NULL CHECK (quantity > 0),
    unit_price   INTEGER CHECK (unit_price >= 0),
    note         TEXT,
    created_at   TEXT    NOT NULL,
    seq          INTEGER NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS stock_out (
    voucher_no   TEXT    PRIMARY KEY,
    product_code TEXT    NOT NULL REFERENCES products (product_code),
    quantity     INTEGER NOT NULL CHECK (quantity > 0),
    unit_price   INTEGER CHECK (unit_price >= 0),
    note         TEXT,
    created_at   TEXT    NOT NULL,
    seq          INTEGER NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS inventory (
    product_code TEXT    PRIMARY KEY REFERENCES products (product_code),
    quantity     INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    seq          INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS update_log (
    seq        INTEGER PRIMARY KEY,
    op         TEXT    NOT NULL,
    data       TEXT    NOT NULL,
    created_at TEXT    NOT NULL,
    applied_at TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS node_state (
    id               INTEGER PRIMARY KEY CHECK (id = 1),
    last_seq         INTEGER NOT NULL DEFAULT 0,
    checkpoint_seq   INTEGER NOT NULL DEFAULT 0,
    batch_n          INTEGER CHECK (batch_n >= 1),
    period_t_seconds REAL    CHECK (period_t_seconds > 0)
);
INSERT OR IGNORE INTO node_state (id) VALUES (1);

CREATE TABLE IF NOT EXISTS replication_progress (
    target         TEXT    PRIMARY KEY CHECK (target IN ('S1', 'S2', 'S3', 'S4')),
    last_acked_seq INTEGER NOT NULL DEFAULT 0,
    last_sent_at   TEXT
);

CREATE TABLE IF NOT EXISTS processed_requests (
    msg_id     TEXT PRIMARY KEY,
    reply      TEXT NOT NULL,
    created_at TEXT NOT NULL
);

