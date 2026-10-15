"""Test lược đồ CSDL common/schema.sql. Phụ trách: TV1.

Chạy trên CSDL trong bộ nhớ (:memory:), không tạo file, không cần máy chủ.
"""

import os
import sqlite3
import unittest

from common import protocol
from common.protocol import Op

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(REPO_ROOT, "common", "schema.sql")

TABLES = {
    "products",
    "stock_in",
    "stock_out",
    "inventory",
    "update_log",
    "node_state",
    "replication_progress",
    "processed_requests",
}
TS = "2026-10-13T22:00:00"


def read_schema():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return f.read()


def open_db():
    """Mở CSDL giống cách server/db.py phải làm: bật khóa ngoại rồi chạy schema."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(read_schema())
    return conn


class SchemaTestBase(unittest.TestCase):
    def setUp(self):
        self.db = open_db()
        self.addCleanup(self.db.close)

    def assertRejected(self, sql, params=()):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(sql, params)

    def add_product(self, code="SP01", seq=1, name="Bút bi Thiên Long"):
        self.db.execute(
            "INSERT INTO products VALUES (?, ?, 'cái', ?, ?)", (code, name, TS, seq)
        )
        self.db.execute(
            "INSERT INTO inventory (product_code, seq) VALUES (?, ?)", (code, seq)
        )

    def add_voucher(self, table, op, seq, quantity, code="SP01", unit_price=None):
        self.db.execute(
            f"INSERT INTO {table} VALUES (?, ?, ?, ?, NULL, ?, ?)",
            (protocol.voucher_no(op, seq), code, quantity, unit_price, TS, seq),
        )


class CreateSchemaTest(SchemaTestBase):
    def test_creates_all_eight_tables(self):
        names = {
            r[0]
            for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        self.assertEqual(names, TABLES)

    def test_running_twice_is_safe(self):
        # Máy chủ chạy schema mỗi lần khởi động: không lỗi, không nhân đôi dữ liệu
        self.db.executescript(read_schema())
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM node_state").fetchone()[0], 1
        )

    def test_vietnamese_text_round_trip(self):
        self.add_product(name="Sữa tươi Vinamilk ít đường")
        name = self.db.execute("SELECT product_name FROM products").fetchone()[0]
        self.assertEqual(name, "Sữa tươi Vinamilk ít đường")


class NodeStateTest(SchemaTestBase):
    def test_starts_with_one_default_row(self):
        row = self.db.execute(
            "SELECT id, last_seq, checkpoint_seq, batch_n, period_t_seconds FROM node_state"
        ).fetchall()
        # N, T để trống: dùng giá trị trong config.json
        self.assertEqual(row, [(1, 0, 0, None, None)])

    def test_only_one_row_allowed(self):
        self.assertRejected("INSERT INTO node_state (id) VALUES (2)")

    def test_rejects_invalid_n_and_t(self):
        self.assertRejected("UPDATE node_state SET batch_n = 0")
        self.assertRejected("UPDATE node_state SET period_t_seconds = 0")

    def test_last_seq_compares_as_number(self):
        self.db.execute("UPDATE node_state SET last_seq = 10")
        self.assertEqual(
            self.db.execute("SELECT last_seq > 9 FROM node_state").fetchone()[0], 1
        )


class BusinessTablesTest(SchemaTestBase):
    def test_inventory_starts_at_zero(self):
        self.add_product()
        qty = self.db.execute("SELECT quantity FROM inventory").fetchone()[0]
        self.assertEqual(qty, 0)

    def test_inventory_never_negative(self):
        self.add_product()
        self.assertRejected("UPDATE inventory SET quantity = -1")

    def test_foreign_keys_block_unknown_product(self):
        self.assertRejected("INSERT INTO inventory (product_code, seq) VALUES ('X', 1)")
        with self.assertRaises(sqlite3.IntegrityError):
            self.add_voucher("stock_in", Op.STOCK_IN, 1, 5, code="X")

    def test_duplicate_product_code_rejected(self):
        self.add_product()
        self.assertRejected(
            "INSERT INTO products VALUES ('SP01', 'Khác', 'cái', ?, 2)", (TS,)
        )

    def test_voucher_quantity_must_be_positive(self):
        self.add_product()
        for table, op in (("stock_in", Op.STOCK_IN), ("stock_out", Op.STOCK_OUT)):
            for seq, qty in ((2, 0), (3, -5)):
                with self.subTest(table=table, quantity=qty):
                    with self.assertRaises(sqlite3.IntegrityError):
                        self.add_voucher(table, op, seq, qty)

    def test_voucher_no_and_seq_are_unique(self):
        self.add_product()
        self.add_voucher("stock_in", Op.STOCK_IN, 2, 10)
        with self.assertRaises(sqlite3.IntegrityError):
            self.add_voucher("stock_in", Op.STOCK_IN, 2, 10)
        self.assertRejected(
            "INSERT INTO stock_in VALUES ('PN-999999', 'SP01', 1, NULL, NULL, ?, 2)",
            (TS,),
        )

    def test_unit_price_optional_but_not_negative(self):
        self.add_product()
        self.add_voucher("stock_in", Op.STOCK_IN, 2, 10, unit_price=None)
        self.add_voucher("stock_in", Op.STOCK_IN, 3, 10, unit_price=5000)
        with self.assertRaises(sqlite3.IntegrityError):
            self.add_voucher("stock_in", Op.STOCK_IN, 4, 10, unit_price=-1)


class TechnicalTablesTest(SchemaTestBase):
    def test_update_log_seq_unique(self):
        sql = "INSERT INTO update_log VALUES (1, 'STOCK_IN', '{}', ?, ?)"
        self.db.execute(sql, (TS, TS))
        self.assertRejected(sql, (TS, TS))

    def test_replication_target_must_be_known_node(self):
        self.db.execute("INSERT INTO replication_progress (target) VALUES ('S2')")
        row = self.db.execute("SELECT last_acked_seq FROM replication_progress").fetchone()
        self.assertEqual(row[0], 0)
        self.assertRejected("INSERT INTO replication_progress (target) VALUES ('S9')")

    def test_processed_request_msg_id_unique(self):
        sql = "INSERT INTO processed_requests VALUES ('abc', '{}', ?)"
        self.db.execute(sql, (TS,))
        self.assertRejected(sql, (TS,))


class ApplyUpdateScenarioTest(SchemaTestBase):
    """Mô phỏng tay một chuỗi cập nhật như Hợp đồng chung mục 6, quy tắc 3."""

    def apply(self, seq, op, quantity=None):
        """Một cập nhật = một giao tác: phiếu, tồn, nhật ký, last_seq."""
        with self.db:  # lỗi ở bất kỳ bước nào thì rollback cả giao tác
            if op == Op.ADD_PRODUCT:
                self.add_product(seq=seq)
            else:
                table, sign = (
                    ("stock_in", 1) if op == Op.STOCK_IN else ("stock_out", -1)
                )
                self.add_voucher(table, op, seq, quantity)
                self.db.execute(
                    "UPDATE inventory SET quantity = quantity + ?, seq = ? "
                    "WHERE product_code = 'SP01'",
                    (sign * quantity, seq),
                )
            self.db.execute(
                "INSERT INTO update_log VALUES (?, ?, '{}', ?, ?)", (seq, op, TS, TS)
            )
            self.db.execute("UPDATE node_state SET last_seq = ?", (seq,))

    def state(self):
        return (
            self.db.execute("SELECT quantity, seq FROM inventory").fetchone(),
            self.db.execute("SELECT last_seq FROM node_state").fetchone()[0],
            self.db.execute("SELECT COUNT(*) FROM update_log").fetchone()[0],
            self.db.execute("SELECT COUNT(*) FROM stock_out").fetchone()[0],
        )

    def test_add_in_out_updates_stock(self):
        self.apply(1, Op.ADD_PRODUCT)
        self.apply(2, Op.STOCK_IN, 10)
        self.apply(3, Op.STOCK_OUT, 4)
        self.assertEqual(self.state(), ((6, 3), 3, 3, 1))

    def test_overdraw_rolls_back_everything(self):
        self.apply(1, Op.ADD_PRODUCT)
        self.apply(2, Op.STOCK_IN, 10)
        before = self.state()
        with self.assertRaises(sqlite3.IntegrityError):
            self.apply(3, Op.STOCK_OUT, 11)
        # Không còn phiếu xuất, nhật ký hay last_seq nào của seq 3
        self.assertEqual(self.state(), before)


if __name__ == "__main__":
    unittest.main()