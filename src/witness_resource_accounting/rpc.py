"""Minimal Bitcoin Core JSON-RPC transport and transaction acquisition."""

from __future__ import annotations

from base64 import b64encode
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .accounting import TransactionAnalysis, analyze_transaction
from .transaction import Transaction


class BitcoinRPCError(RuntimeError):
    """Raised for transport failures or JSON-RPC error responses."""


class BitcoinCoreParityError(RuntimeError):
    """Raised when local BIP141 measurements disagree with Bitcoin Core."""


Transport = Callable[[str, bytes, dict[str, str], float], bytes]


def _default_transport(
    url: str,
    payload: bytes,
    headers: dict[str, str],
    timeout: float,
) -> bytes:
    request = Request(url, data=payload, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read()
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise BitcoinRPCError(f"Bitcoin Core RPC HTTP {error.code}: {body}") from error
    except URLError as error:
        raise BitcoinRPCError(f"Bitcoin Core RPC connection failed: {error.reason}") from error


@dataclass(slots=True)
class BitcoinRPCClient:
    url: str
    username: str
    password: str
    timeout: float = 30.0
    transport: Transport = _default_transport
    _request_id: int = 0

    @classmethod
    def from_cookie(
        cls,
        *,
        url: str,
        cookie_path: Path,
        timeout: float = 30.0,
        transport: Transport = _default_transport,
    ) -> BitcoinRPCClient:
        try:
            cookie = cookie_path.expanduser().read_text(encoding="utf-8").strip()
        except OSError as error:
            raise BitcoinRPCError(f"cannot read Bitcoin Core cookie file: {cookie_path}") from error
        username, separator, password = cookie.partition(":")
        if separator == "" or username == "" or password == "":
            raise BitcoinRPCError("Bitcoin Core cookie must contain username:password")
        return cls(url, username, password, timeout, transport)

    def call(self, method: str, parameters: list[Any]) -> Any:
        self._request_id += 1
        request_id = self._request_id
        payload = json.dumps(
            {
                "jsonrpc": "1.0",
                "id": request_id,
                "method": method,
                "params": parameters,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        authorization = b64encode(f"{self.username}:{self.password}".encode()).decode("ascii")
        response_bytes = self.transport(
            self.url,
            payload,
            {
                "Authorization": f"Basic {authorization}",
                "Content-Type": "application/json",
            },
            self.timeout,
        )
        try:
            response = json.loads(response_bytes, parse_float=Decimal)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise BitcoinRPCError("Bitcoin Core returned invalid JSON") from error
        if not isinstance(response, dict) or response.get("id") != request_id:
            raise BitcoinRPCError("Bitcoin Core returned an invalid JSON-RPC envelope")
        if response.get("error") is not None:
            error = response["error"]
            if isinstance(error, dict):
                raise BitcoinRPCError(
                    f"Bitcoin Core RPC {method} failed ({error.get('code')}): {error.get('message')}"
                )
            raise BitcoinRPCError(f"Bitcoin Core RPC {method} failed: {error}")
        return response.get("result")

    def get_raw_transaction(
        self,
        txid: str,
        *,
        block_hash: str | None = None,
    ) -> dict[str, Any]:
        parameters: list[Any] = [txid, 2]
        if block_hash is not None:
            parameters.append(block_hash)
        result = self.call("getrawtransaction", parameters)
        if not isinstance(result, dict):
            raise BitcoinRPCError("getrawtransaction did not return an object")
        return result

    def get_block_count(self) -> int:
        result = self.call("getblockcount", [])
        if not isinstance(result, int) or isinstance(result, bool) or result < 0:
            raise BitcoinRPCError("getblockcount did not return a non-negative integer")
        return result

    def get_block_hash(self, height: int) -> str:
        result = self.call("getblockhash", [height])
        if not isinstance(result, str) or len(result) != 64:
            raise BitcoinRPCError("getblockhash did not return a 32-byte hex hash")
        try:
            bytes.fromhex(result)
        except ValueError as error:
            raise BitcoinRPCError("getblockhash returned invalid hex") from error
        return result

    def get_block(self, block_hash: str, *, verbosity: int = 3) -> dict[str, Any]:
        result = self.call("getblock", [block_hash, verbosity])
        if not isinstance(result, dict):
            raise BitcoinRPCError("getblock did not return an object")
        return result

    def get_blockchain_info(self) -> dict[str, Any]:
        result = self.call("getblockchaininfo", [])
        if not isinstance(result, dict):
            raise BitcoinRPCError("getblockchaininfo did not return an object")
        return result


def btc_fee_to_sats(value: Any) -> int | None:
    if value is None:
        return None
    decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    satoshis = decimal_value * Decimal(100_000_000)
    if satoshis != satoshis.to_integral_value():
        raise BitcoinRPCError("Bitcoin Core returned a fee below satoshi precision")
    return int(satoshis)


def analyze_core_transaction(
    rpc_result: dict[str, Any],
    *,
    identifier: str | None = None,
) -> TransactionAnalysis:
    transaction_hex = rpc_result.get("hex")
    if not isinstance(transaction_hex, str):
        raise BitcoinRPCError("getrawtransaction result is missing transaction hex")
    transaction = Transaction.from_hex(transaction_hex)

    parity_fields = {
        "size": transaction.total_size,
        "vsize": (transaction.stripped_size * 3 + transaction.total_size + 3) // 4,
        "weight": transaction.stripped_size * 3 + transaction.total_size,
        "txid": transaction.txid,
        "hash": transaction.wtxid,
    }
    for core_field, local_value in parity_fields.items():
        core_value = rpc_result.get(core_field)
        if core_value != local_value:
            raise BitcoinCoreParityError(
                f"Bitcoin Core parity failure for {core_field}: Core={core_value!r}, local={local_value!r}"
            )

    vin = rpc_result.get("vin")
    if not isinstance(vin, list) or len(vin) != len(transaction.inputs):
        raise BitcoinRPCError("getrawtransaction vin does not align with decoded inputs")

    prevout_scripts: list[bytes | None] = []
    for index, input_result in enumerate(vin):
        if not isinstance(input_result, dict):
            raise BitcoinRPCError(f"getrawtransaction vin {index} is not an object")
        prevout = input_result.get("prevout")
        if prevout is None:
            prevout_scripts.append(None)
            continue
        if not isinstance(prevout, dict):
            raise BitcoinRPCError(f"getrawtransaction vin {index} prevout is not an object")
        script_pubkey = prevout.get("scriptPubKey")
        script_hex = script_pubkey.get("hex") if isinstance(script_pubkey, dict) else None
        if not isinstance(script_hex, str):
            raise BitcoinRPCError(f"getrawtransaction vin {index} prevout lacks scriptPubKey hex")
        try:
            prevout_scripts.append(bytes.fromhex(script_hex))
        except ValueError as error:
            raise BitcoinRPCError(
                f"getrawtransaction vin {index} prevout scriptPubKey is invalid hex"
            ) from error

    return analyze_transaction(
        transaction,
        identifier=identifier or transaction.txid,
        fee_sats=btc_fee_to_sats(rpc_result.get("fee")),
        prevout_script_pubkeys=prevout_scripts,
    )
