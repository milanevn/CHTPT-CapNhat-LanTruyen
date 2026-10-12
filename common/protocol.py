"""Định dạng thông điệp, loại thông điệp, thao tác và mã lỗi. Phụ trách: TV1.

Mỗi thông điệp là một đối tượng JSON trên một dòng, UTF-8, kết thúc bằng "\n".
Luôn tạo thông điệp bằng make_message().
"""

import json
import uuid
from datetime import datetime

ENCODING = "utf-8"
DELIMITER = b"\n"
MAX_MESSAGE_BYTES = 1024 * 1024

REQUIRED_FIELDS = ("type", "msg_id", "sender", "seq", "op", "data", "ts")


class MsgType:
    REQUEST = "REQUEST"
    REPLY = "REPLY"
    UPDATE = "UPDATE"
    UPDATE_BATCH = "UPDATE_BATCH"
    ACK = "ACK"
    NACK = "NACK"
    HEARTBEAT = "HEARTBEAT"
    SYNC_REQUEST = "SYNC_REQUEST"
    SYNC_RESPONSE = "SYNC_RESPONSE"
    SNAPSHOT_REQUEST = "SNAPSHOT_REQUEST"
    SNAPSHOT_RESPONSE = "SNAPSHOT_RESPONSE"
    STATUS_REQUEST = "STATUS_REQUEST"
    STATUS_RESPONSE = "STATUS_RESPONSE"
    CONFIG_SET = "CONFIG_SET"
    ADMIN = "ADMIN"


class Op:
    ADD_PRODUCT = "ADD_PRODUCT"
    STOCK_IN = "STOCK_IN"
    STOCK_OUT = "STOCK_OUT"
    GET_STOCK = "GET_STOCK"
    CORRUPT_DATA = "CORRUPT_DATA"
    RECOVER = "RECOVER"


# Thao tác ghi: chỉ S1 nhận, máy khác trả NACK mã NOT_PRIMARY
WRITE_OPS = frozenset({Op.ADD_PRODUCT, Op.STOCK_IN, Op.STOCK_OUT})


class ErrorCode:
    BAD_FORMAT = "BAD_FORMAT"
    UNKNOWN_OP = "UNKNOWN_OP"
    NOT_PRIMARY = "NOT_PRIMARY"
    PRODUCT_EXISTS = "PRODUCT_EXISTS"
    PRODUCT_NOT_FOUND = "PRODUCT_NOT_FOUND"
    INVALID_QUANTITY = "INVALID_QUANTITY"
    INSUFFICIENT_STOCK = "INSUFFICIENT_STOCK"
    SEQ_GAP = "SEQ_GAP"
    LOG_TRUNCATED = "LOG_TRUNCATED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# Câu hiển thị trên giao diện. SEQ_GAP, LOG_TRUNCATED chỉ dùng giữa các máy chủ.
ERROR_MESSAGES_VI = {
    ErrorCode.BAD_FORMAT: "Dữ liệu gửi lên không hợp lệ",
    ErrorCode.UNKNOWN_OP: "Thao tác không được hỗ trợ",
    ErrorCode.NOT_PRIMARY: "Máy này không nhận thao tác ghi",
    ErrorCode.PRODUCT_EXISTS: "Mã hàng đã có",
    ErrorCode.PRODUCT_NOT_FOUND: "Không tìm thấy mã hàng",
    ErrorCode.INVALID_QUANTITY: "Số lượng phải là số nguyên lớn hơn 0",
    ErrorCode.INSUFFICIENT_STOCK: "Không đủ hàng tồn để xuất",
    ErrorCode.INTERNAL_ERROR: "Máy chủ gặp lỗi, vui lòng thử lại",
}


class ProtocolError(Exception):
    """Thông điệp sai định dạng; bên nhận trả NACK mã BAD_FORMAT."""

    code = ErrorCode.BAD_FORMAT


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def new_msg_id():
    return uuid.uuid4().hex


def make_message(type, sender, op=None, data=None, seq=None, msg_id=None):
    """Tạo thông điệp đủ 7 trường bắt buộc.

    msg_id: truyền lại msg_id cũ khi gửi lại; để None thì sinh mới.
    seq:    chỉ có ở thông điệp mang cập nhật dữ liệu.
    """
    return {
        "type": type,
        "msg_id": msg_id or new_msg_id(),
        "sender": sender,
        "seq": seq,
        "op": op,
        "data": data if data is not None else {},
        "ts": now_iso(),
    }


def encode(message):
    """dict -> bytes một dòng kết thúc bằng \\n."""
    raw = json.dumps(message, ensure_ascii=False).encode(ENCODING) + DELIMITER
    if len(raw) > MAX_MESSAGE_BYTES:
        raise ProtocolError(
            f"Thông điệp {len(raw)} byte vượt giới hạn {MAX_MESSAGE_BYTES}; hãy chia lô nhỏ hơn"
        )
    return raw


def decode(line):
    """bytes hoặc str một dòng -> dict. Sai định dạng thì ném ProtocolError."""
    if isinstance(line, bytes):
        try:
            line = line.decode(ENCODING)
        except UnicodeDecodeError as exc:
            raise ProtocolError("Không phải UTF-8") from exc
    try:
        message = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ProtocolError("Không phải JSON hợp lệ") from exc
    if not isinstance(message, dict):
        raise ProtocolError("Thông điệp phải là đối tượng JSON")
    missing = [f for f in REQUIRED_FIELDS if f not in message]
    if missing:
        raise ProtocolError(f"Thiếu trường: {', '.join(missing)}")
    return message


def voucher_no(op, seq):
    """Số phiếu: PN-/PX- + 6 chữ số của seq, ví dụ PN-000012."""
    prefix = {Op.STOCK_IN: "PN-", Op.STOCK_OUT: "PX-"}[op]
    return f"{prefix}{seq:06d}"
