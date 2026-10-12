"""Đọc config.json, trả về cấu hình từng máy. Phụ trách: TV1.

from common import config
cfg = config.load()
host, port = config.address(cfg, "S2")
"""

import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
NODE_IDS = ("S1", "S2", "S3", "S4")
MODES = ("immediate", "periodic", "batch")
REQUIRED_KEYS = (
    "primary",
    "nodes",
    "replication",
    "batch_n",
    "period_t_seconds",
    "ack_timeout_seconds",
    "max_retries",
    "heartbeat_interval_seconds",
    "heartbeat_miss_limit",
    "data_dir",
)


def load(path=CONFIG_PATH):
    """Đọc và kiểm tra file cấu hình. Sai cấu trúc thì ném ValueError."""
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    _validate(cfg)
    return cfg


def address(cfg, node_id):
    """(host, port) của một máy."""
    node = cfg["nodes"][node_id]
    return node["host"], node["port"]


def upstream(cfg, node_id):
    """Máy nguồn của node_id; S1 không có nguồn nên trả None."""
    for link in cfg["replication"]:
        if link["to"] == node_id:
            return link["from"]
    return None


def downstreams(cfg, node_id):
    """Các máy node_id phải đẩy cập nhật tới: [(máy đích, mode), ...]."""
    return [
        (link["to"], link["mode"])
        for link in cfg["replication"]
        if link["from"] == node_id
    ]


def data_path(cfg, node_id):
    """Đường dẫn file CSDL của một máy, ví dụ <repo>/data/S1/inventory.db."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, cfg["data_dir"], node_id, "inventory.db")


def _validate(cfg):
    for key in REQUIRED_KEYS:
        if key not in cfg:
            raise ValueError(f"config.json thiếu khóa '{key}'")
    for node_id in NODE_IDS:
        if node_id not in cfg["nodes"]:
            raise ValueError(f"config.json thiếu máy {node_id}")
    for link in cfg["replication"]:
        if link["mode"] not in MODES:
            raise ValueError(
                f"mode '{link['mode']}' không hợp lệ, chọn một trong {MODES}"
            )
