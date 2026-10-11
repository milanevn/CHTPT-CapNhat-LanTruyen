"""Kiểm tra khung: mọi module đều import được.

Quy tắc: import một module KHÔNG được tự chạy gì (không mở socket, không mở cửa sổ).
Code khởi động phải nằm trong  if __name__ == "__main__":
"""
import importlib
import unittest

MODULES = [
    "common.config", "common.protocol", "common.interfaces", "common.fakes",
    "server.transport", "server.db", "server.primary",
    "server.replication_sync", "server.heartbeat",
    "server.replication_lazy", "server.recovery",
    "client.net",
    "client.views.inventory_view", "client.views.status_view",
    "client.views.lag_view", "client.views.recovery_view",
]


class SmokeTest(unittest.TestCase):
    def test_import_all_modules(self):
        for name in MODULES:
            with self.subTest(module=name):
                importlib.import_module(name)


if __name__ == "__main__":
    unittest.main()