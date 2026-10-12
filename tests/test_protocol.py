"""Test protocol và config. Phụ trách: TV1."""

import unittest

from common import config, protocol
from common.protocol import ErrorCode, MsgType, Op, ProtocolError


class ProtocolTest(unittest.TestCase):
    def test_make_message_has_all_required_fields(self):
        msg = protocol.make_message(MsgType.REQUEST, "client", op=Op.GET_STOCK)
        for field in protocol.REQUIRED_FIELDS:
            self.assertIn(field, msg)

    def test_encode_decode_roundtrip_keeps_vietnamese(self):
        msg = protocol.make_message(
            MsgType.REQUEST,
            "client",
            op=Op.ADD_PRODUCT,
            data={"product_name": "Bút bi"},
        )
        raw = protocol.encode(msg)
        self.assertTrue(raw.endswith(b"\n"))
        self.assertEqual(raw.count(b"\n"), 1)
        self.assertEqual(protocol.decode(raw), msg)

    def test_resend_keeps_msg_id(self):
        first = protocol.make_message(MsgType.UPDATE, "S1", seq=1)
        again = protocol.make_message(
            MsgType.UPDATE, "S1", seq=1, msg_id=first["msg_id"]
        )
        self.assertEqual(first["msg_id"], again["msg_id"])

    def test_decode_rejects_bad_input(self):
        for bad in (b"not json\n", b"[1, 2]\n", b'{"type": "ACK"}\n'):
            with self.subTest(bad=bad):
                with self.assertRaises(ProtocolError):
                    protocol.decode(bad)

    def test_encode_rejects_oversized_message(self):
        msg = protocol.make_message(
            MsgType.UPDATE_BATCH, "S1", data={"blob": "x" * protocol.MAX_MESSAGE_BYTES}
        )
        with self.assertRaises(ProtocolError):
            protocol.encode(msg)

    def test_voucher_no(self):
        self.assertEqual(protocol.voucher_no(Op.STOCK_IN, 12), "PN-000012")
        self.assertEqual(protocol.voucher_no(Op.STOCK_OUT, 7), "PX-000007")

    def test_every_user_error_has_vietnamese_text(self):
        server_only = {ErrorCode.SEQ_GAP, ErrorCode.LOG_TRUNCATED}
        codes = {v for k, v in vars(ErrorCode).items() if not k.startswith("_")}
        self.assertEqual(set(protocol.ERROR_MESSAGES_VI), codes - server_only)


class ConfigTest(unittest.TestCase):
    def setUp(self):
        # Luôn test file chung trong repo, không bị config.local.json của từng máy ảnh hưởng
        self.cfg = config.load(config.CONFIG_PATH)

    def test_four_nodes_on_distinct_ports(self):
        ports = [config.address(self.cfg, n)[1] for n in config.NODE_IDS]
        self.assertEqual(len(set(ports)), 4)

    def test_topology_matches_assignment(self):
        self.assertIsNone(config.upstream(self.cfg, "S1"))
        self.assertEqual(config.upstream(self.cfg, "S2"), "S1")
        self.assertEqual(config.upstream(self.cfg, "S3"), "S1")
        self.assertEqual(config.upstream(self.cfg, "S4"), "S2")
        self.assertEqual(
            sorted(config.downstreams(self.cfg, "S1")),
            [("S2", "immediate"), ("S3", "periodic")],
        )
        self.assertEqual(config.downstreams(self.cfg, "S2"), [("S4", "batch")])

    def test_bad_config_raises_value_error(self):
        import copy

        bad_cases = [
            lambda c: c["nodes"]["S2"].update(port="5002"),
            lambda c: c["nodes"]["S3"].update(port=5001),
            lambda c: c["replication"][0].pop("mode"),
            lambda c: c.update(primary="S9"),
            lambda c: c.update(batch_n=0),
        ]
        for i, mutate in enumerate(bad_cases):
            with self.subTest(case=i):
                cfg = copy.deepcopy(self.cfg)
                mutate(cfg)
                with self.assertRaises(ValueError):
                    config._validate(cfg)


if __name__ == "__main__":
    unittest.main()
