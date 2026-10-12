"""Đọc cấu hình, trả về cấu hình từng máy. Phụ trách: TV1.

from common import config
cfg = config.load()
host, port = config.address(cfg, "S2")

Thứ tự đọc: biến môi trường CHTPT_CONFIG > common/config.local.json > common/config.json.
"""

import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(_HERE, "config.json")
# Bản riêng của từng máy (đổi IP khi demo nhiều laptop, đổi N/T để thử).
# Đã nằm trong .gitignore nên không bao giờ bị commit nhầm.
LOCAL_CONFIG_PATH = os.path.join(_HERE, "config.local.json")
ENV_VAR = "CHTPT_CONFIG"
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


def resolve_path():
    """File cấu hình sẽ dùng, theo thứ tự ưu tiên:
    biến môi trường CHTPT_CONFIG > common/config.local.json > common/config.json.
    """
    env = os.environ.get(ENV_VAR)
    if env:
        return env
    if os.path.exists(LOCAL_CONFIG_PATH):
        return LOCAL_CONFIG_PATH
    return CONFIG_PATH


def load(path=None):
    """Đọc và kiểm tra file cấu hình. Sai cấu trúc thì ném ValueError."""
    path = path or resolve_path()
    try:
        with open(
            path, encoding="utf-8-sig"
        ) as f:  # -sig: chịu được BOM do Notepad thêm
            cfg = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{os.path.basename(path)} không phải JSON hợp lệ: {exc}"
        ) from exc
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
    if not isinstance(cfg, dict):
        raise ValueError("config.json phải là một đối tượng JSON")
    for key in REQUIRED_KEYS:
        if key not in cfg:
            raise ValueError(f"config.json thiếu khóa '{key}'")
    if not isinstance(cfg["nodes"], dict):
        raise ValueError("'nodes' phải là đối tượng {S1: {...}, ...}")
    endpoints = set()
    for node_id in NODE_IDS:
        node = cfg["nodes"].get(node_id)
        if not isinstance(node, dict):
            raise ValueError(f"config.json thiếu máy {node_id}")
        host, port = node.get("host"), node.get("port")
        if not isinstance(host, str) or not host.strip():
            raise ValueError(f"{node_id}: 'host' phải là chuỗi IP, ví dụ \"127.0.0.1\"")
        if (
            not isinstance(port, int)
            or isinstance(port, bool)
            or not 1024 <= port <= 65535
        ):
            raise ValueError(f"{node_id}: 'port' phải là số nguyên 1024-65535")
        if (host, port) in endpoints:
            raise ValueError(f"{node_id}: trùng host:port {host}:{port} với máy khác")
        endpoints.add((host, port))
    if cfg["primary"] not in NODE_IDS:
        raise ValueError(f"'primary' phải là một trong {NODE_IDS}")
    if not isinstance(cfg["replication"], list):
        raise ValueError("'replication' phải là danh sách")
    for link in cfg["replication"]:
        if not isinstance(link, dict) or not {"from", "to", "mode"} <= set(link):
            raise ValueError("mỗi dòng 'replication' cần đủ from, to, mode")
        if link["from"] not in NODE_IDS or link["to"] not in NODE_IDS:
            raise ValueError(
                f"replication {link['from']}->{link['to']}: tên máy không hợp lệ"
            )
        if link["mode"] not in MODES:
            raise ValueError(
                f"mode '{link['mode']}' không hợp lệ, chọn một trong {MODES}"
            )
    for key in ("batch_n", "max_retries", "heartbeat_miss_limit"):
        if not isinstance(cfg[key], int) or isinstance(cfg[key], bool) or cfg[key] < 1:
            raise ValueError(f"'{key}' phải là số nguyên >= 1")
    for key in (
        "period_t_seconds",
        "ack_timeout_seconds",
        "heartbeat_interval_seconds",
    ):
        if (
            not isinstance(cfg[key], (int, float))
            or isinstance(cfg[key], bool)
            or cfg[key] <= 0
        ):
            raise ValueError(f"'{key}' phải là số > 0")
