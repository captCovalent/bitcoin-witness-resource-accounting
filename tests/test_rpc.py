from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest

from witness_resource_accounting.rpc import (
    BitcoinCoreParityError,
    BitcoinRPCClient,
    BitcoinRPCError,
    analyze_core_transaction,
    btc_fee_to_sats,
)
from witness_resource_accounting.transaction import Transaction

from fixtures import BIP143_SIGNED_NATIVE_P2WPKH, legacy_one_input_one_output


def core_result(raw: bytes) -> dict:
    transaction = Transaction.from_bytes(raw)
    weight = transaction.stripped_size * 3 + transaction.total_size
    return {
        "hex": raw.hex(),
        "size": transaction.total_size,
        "vsize": (weight + 3) // 4,
        "weight": weight,
        "txid": transaction.txid,
        "hash": transaction.wtxid,
        "fee": Decimal("0.00001042"),
        "vin": [
            {
                "prevout": {
                    "scriptPubKey": {
                        "hex": "76a914" + "11" * 20 + "88ac",
                    }
                }
            },
            {
                "prevout": {
                    "scriptPubKey": {
                        "hex": "0014" + "22" * 20,
                    }
                }
            },
        ],
    }


class RPCAnalysisTests(unittest.TestCase):
    def test_core_result_is_parity_checked_and_classified(self) -> None:
        analysis = analyze_core_transaction(core_result(BIP143_SIGNED_NATIVE_P2WPKH)).to_dict()
        self.assertEqual(analysis["fee_sats"], 1_042)
        self.assertEqual(analysis["inputs"][0]["classification"]["spend_type"], "non_witness_or_unknown")
        self.assertEqual(analysis["inputs"][1]["classification"]["spend_type"], "p2wpkh")

    def test_core_weight_disagreement_fails_closed(self) -> None:
        result = core_result(BIP143_SIGNED_NATIVE_P2WPKH)
        result["weight"] += 1
        with self.assertRaisesRegex(BitcoinCoreParityError, "weight"):
            analyze_core_transaction(result)

    def test_fee_conversion_is_exact(self) -> None:
        self.assertEqual(btc_fee_to_sats(Decimal("0.00000001")), 1)
        with self.assertRaisesRegex(BitcoinRPCError, "below satoshi"):
            btc_fee_to_sats(Decimal("0.000000001"))


class RPCClientTests(unittest.TestCase):
    def test_json_rpc_request_uses_basic_auth_and_parameters(self) -> None:
        captured = {}

        def transport(url: str, payload: bytes, headers: dict[str, str], timeout: float) -> bytes:
            captured.update(
                {
                    "url": url,
                    "payload": json.loads(payload),
                    "headers": headers,
                    "timeout": timeout,
                }
            )
            return json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"hex": "00"}}).encode()

        client = BitcoinRPCClient("http://127.0.0.1:8332", "user", "password", transport=transport)
        result = client.get_raw_transaction("ab" * 32, block_hash="cd" * 32)

        self.assertEqual(result, {"hex": "00"})
        self.assertEqual(captured["payload"]["method"], "getrawtransaction")
        self.assertEqual(captured["payload"]["params"], ["ab" * 32, 2, "cd" * 32])
        self.assertTrue(captured["headers"]["Authorization"].startswith("Basic "))
        self.assertNotIn("password", json.dumps(captured["payload"]))

    def test_cookie_authentication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cookie_path = Path(directory) / ".cookie"
            cookie_path.write_text("cookie-user:cookie-password\n", encoding="utf-8")
            client = BitcoinRPCClient.from_cookie(
                url="http://127.0.0.1:8332",
                cookie_path=cookie_path,
                transport=lambda _url, _payload, _headers, _timeout: b"{}",
            )
        self.assertEqual(client.username, "cookie-user")
        self.assertEqual(client.password, "cookie-password")

    def test_block_rpc_helpers_validate_and_return_results(self) -> None:
        calls = []

        def transport(_url: str, payload: bytes, _headers: dict[str, str], _timeout: float) -> bytes:
            request = json.loads(payload)
            calls.append((request["method"], request["params"]))
            results = {
                "getblockcount": 962_135,
                "getblockhash": "ab" * 32,
                "getblock": {"hash": "ab" * 32, "height": 962_135, "tx": []},
                "getblockchaininfo": {"chain": "main", "blocks": 962_135},
            }
            return json.dumps(
                {"jsonrpc": "2.0", "id": request["id"], "result": results[request["method"]]}
            ).encode()

        client = BitcoinRPCClient("http://127.0.0.1:8332", "user", "password", transport=transport)
        self.assertEqual(client.get_block_count(), 962_135)
        self.assertEqual(client.get_block_hash(962_135), "ab" * 32)
        self.assertEqual(client.get_block("ab" * 32, verbosity=3)["height"], 962_135)
        self.assertEqual(client.get_blockchain_info()["chain"], "main")
        self.assertEqual(
            calls,
            [
                ("getblockcount", []),
                ("getblockhash", [962_135]),
                ("getblock", ["ab" * 32, 3]),
                ("getblockchaininfo", []),
            ],
        )

    def test_rpc_error_is_reported_without_credentials(self) -> None:
        def transport(_url: str, _payload: bytes, _headers: dict[str, str], _timeout: float) -> bytes:
            return json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": None,
                    "error": {"code": -5, "message": "No such mempool transaction"},
                }
            ).encode()

        client = BitcoinRPCClient("http://127.0.0.1:8332", "user", "secret", transport=transport)
        with self.assertRaisesRegex(BitcoinRPCError, "No such mempool transaction") as context:
            client.get_raw_transaction("ab" * 32)
        self.assertNotIn("secret", str(context.exception))

    def test_missing_prevout_is_allowed_for_coinbase_shape(self) -> None:
        transaction = Transaction.from_bytes(legacy_one_input_one_output())
        result = {
            "hex": transaction.serialize().hex(),
            "size": 60,
            "vsize": 60,
            "weight": 240,
            "txid": transaction.txid,
            "hash": transaction.wtxid,
            "vin": [{}],
        }
        analysis = analyze_core_transaction(result).to_dict()
        self.assertEqual(analysis["inputs"][0]["classification"]["spend_type"], "unknown")


if __name__ == "__main__":
    unittest.main()
