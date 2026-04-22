"""
helixhash.core
==============
A tamper-evident append-only log.

HelixHash proves a sequence of bytestrings existed in this order at
these times and has not been altered. It makes no claim about whether
the bytestrings are true, meaningful, or correct. Evaluating the
content is the job of a witness layer — see witnessfield.

Hash formula
------------
SHA-256(
    index            (8 bytes, big-endian)
  | payload_length   (8 bytes, big-endian)
  | payload          (variable)
  | timestamp        (8 bytes, big-endian double)
  | pubkey_length    (2 bytes, big-endian; 0 or 32)
  | signer_pubkey    (0 or 32 bytes)
  | prev_hash        (64 ASCII bytes)
)

signer_pubkey is length-prefixed and included in the hash so that
swapping a pubkey on a signed entry breaks the chain immediately.
"""

from __future__ import annotations

import hashlib
import struct
import time
from base64 import b64decode, b64encode
from dataclasses import dataclass
from typing import Any, Optional

GENESIS_HASH: str = "0" * 64  # fixed sentinel for the first entry's prev_hash


# ---------------------------------------------------------------------------
# Internal: canonical hash computation
# ---------------------------------------------------------------------------

def _compute_hash(
    index: int,
    payload: bytes,
    timestamp: float,
    signer_pubkey: Optional[bytes],
    prev_hash: str,
) -> str:
    """
    Compute the canonical SHA-256 hash for an entry.

    All variable-length fields are length-prefixed to prevent extension
    attacks and ensure the encoding is unambiguous.
    """
    h = hashlib.sha256()
    h.update(index.to_bytes(8, "big"))
    h.update(len(payload).to_bytes(8, "big"))
    h.update(payload)
    h.update(struct.pack(">d", timestamp))
    pk = signer_pubkey if signer_pubkey is not None else b""
    h.update(len(pk).to_bytes(2, "big"))
    h.update(pk)
    h.update(prev_hash.encode("ascii"))
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Entry:
    """
    A single record in the append-only chain.

    All fields are immutable. ``hash`` covers all fields except
    ``signature`` (which is computed over the hash). ``signer_pubkey``
    is covered by the hash, so swapping it breaks the chain.
    """

    index:         int
    payload:       bytes
    timestamp:     float           # unix seconds (monotonically increasing)
    prev_hash:     str             # GENESIS_HASH for index 0
    hash:          str             # SHA-256 of canonical fields (see module docstring)
    signature:     Optional[bytes] # Ed25519 signature over hash.encode("ascii"), or None
    signer_pubkey: Optional[bytes] # raw 32-byte Ed25519 verify key, or None


# ---------------------------------------------------------------------------
# HelixHash
# ---------------------------------------------------------------------------

class HelixHash:
    """
    Tamper-evident append-only log.

    - ``append`` adds an entry and returns it.
    - ``verify`` replays the full chain; returns False on any tampering.
    - ``export`` / ``from_export`` enable JSON round-trips.
    - ``head`` is the hash of the most recent entry (or GENESIS_HASH if empty).
    - ``length`` is the number of entries.

    Signing (optional)
    ------------------
    Pass an ``Ed25519PrivateKey`` from the ``cryptography`` library as
    ``signer``. The public key is embedded in the entry and in the hash.
    Install with: pip install cryptography
    """

    def __init__(self) -> None:
        self._entries: list[Entry] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append(
        self,
        payload: bytes,
        signer: Optional[Any] = None,  # Ed25519PrivateKey (cryptography lib)
    ) -> Entry:
        """
        Append a new entry and return it.

        ``payload`` must be bytes. If ``signer`` is provided it must be
        an ``Ed25519PrivateKey``; the entry will include a signature and
        the signer's public key.

        Timestamps are generated internally from ``time.time()``. If the
        system clock moves backwards, the new timestamp is bumped to
        ``previous + 1 microsecond`` to preserve strict monotonicity.
        """
        if not isinstance(payload, bytes):
            raise TypeError("payload must be bytes")

        now = time.time()
        if self._entries and now <= self._entries[-1].timestamp:
            now = self._entries[-1].timestamp + 1e-6

        prev_hash = self._entries[-1].hash if self._entries else GENESIS_HASH
        index = len(self._entries)

        signer_pubkey: Optional[bytes] = None
        if signer is not None:
            signer_pubkey = _extract_pubkey(signer)

        entry_hash = _compute_hash(index, payload, now, signer_pubkey, prev_hash)

        signature: Optional[bytes] = None
        if signer is not None:
            signature = _sign(signer, entry_hash.encode("ascii"))

        entry = Entry(
            index=index,
            payload=payload,
            timestamp=now,
            prev_hash=prev_hash,
            hash=entry_hash,
            signature=signature,
            signer_pubkey=signer_pubkey,
        )
        self._entries.append(entry)
        return entry

    def verify(self) -> bool:
        """
        Replay the full chain and return True if it is intact.

        Checks, in order, for each entry:
        1. index == position in list
        2. prev_hash == previous entry's hash (or GENESIS_HASH for first)
        3. hash == recomputed canonical hash (catches payload/timestamp tampering)
        4. if signature is present: signature verifies against signer_pubkey
        """
        prev_hash = GENESIS_HASH
        for i, entry in enumerate(self._entries):
            if entry.index != i:
                return False
            if entry.prev_hash != prev_hash:
                return False
            expected = _compute_hash(
                entry.index,
                entry.payload,
                entry.timestamp,
                entry.signer_pubkey,
                entry.prev_hash,
            )
            if entry.hash != expected:
                return False
            if entry.signature is not None:
                if not _verify_sig(entry.signer_pubkey, entry.signature,
                                   entry.hash.encode("ascii")):
                    return False
            prev_hash = entry.hash
        return True

    def export(self) -> list[dict]:
        """
        Return a JSON-serialisable list of all entries.

        ``payload``, ``signature``, and ``signer_pubkey`` are base64-encoded.
        """
        out = []
        for e in self._entries:
            out.append({
                "index":         e.index,
                "payload":       b64encode(e.payload).decode("ascii"),
                "timestamp":     e.timestamp,
                "prev_hash":     e.prev_hash,
                "hash":          e.hash,
                "signature":     b64encode(e.signature).decode("ascii") if e.signature else None,
                "signer_pubkey": b64encode(e.signer_pubkey).decode("ascii") if e.signer_pubkey else None,
            })
        return out

    @classmethod
    def from_export(cls, entries: list[dict]) -> "HelixHash":
        """
        Reconstruct a HelixHash from a previously exported list.

        Validates structural integrity before loading:
        - Indices must be 0, 1, 2, ... in order.
        - Timestamps must be monotonically non-decreasing.
        - Each ``prev_hash`` must match the previous entry's ``hash``.

        Raises ``ValueError`` on any structural violation. Call
        ``verify()`` on the result to additionally confirm hash integrity.
        """
        h = cls()
        prev_hash = GENESIS_HASH
        prev_ts: Optional[float] = None

        for raw in entries:
            idx = raw["index"]
            if idx != len(h._entries):
                raise ValueError(
                    f"Entry index {idx} out of order; expected {len(h._entries)}"
                )

            ts = float(raw["timestamp"])
            if prev_ts is not None and ts < prev_ts:
                raise ValueError(
                    f"Timestamp {ts} at index {idx} is before previous "
                    f"timestamp {prev_ts}"
                )

            if raw["prev_hash"] != prev_hash:
                raise ValueError(
                    f"prev_hash mismatch at index {idx}: "
                    f"stored={raw['prev_hash']!r}, expected={prev_hash!r}"
                )

            entry = Entry(
                index=idx,
                payload=b64decode(raw["payload"]),
                timestamp=ts,
                prev_hash=raw["prev_hash"],
                hash=raw["hash"],
                signature=b64decode(raw["signature"]) if raw.get("signature") else None,
                signer_pubkey=b64decode(raw["signer_pubkey"]) if raw.get("signer_pubkey") else None,
            )
            h._entries.append(entry)
            prev_hash = entry.hash
            prev_ts = ts

        return h

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def head(self) -> str:
        """Hash of the most recent entry, or GENESIS_HASH if the log is empty."""
        return self._entries[-1].hash if self._entries else GENESIS_HASH

    @property
    def length(self) -> int:
        """Number of entries in the log."""
        return len(self._entries)


# ---------------------------------------------------------------------------
# Signing helpers (lazy import of cryptography)
# ---------------------------------------------------------------------------

def _extract_pubkey(signer: Any) -> bytes:
    try:
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        return signer.public_key().public_bytes(
            encoding=Encoding.Raw,
            format=PublicFormat.Raw,
        )
    except ImportError as exc:
        raise ImportError(
            "Install 'cryptography' to use signing: pip install cryptography"
        ) from exc
    except Exception as exc:
        raise TypeError(
            f"signer must be an Ed25519PrivateKey from the cryptography library: {exc}"
        ) from exc


def _sign(signer: Any, data: bytes) -> bytes:
    try:
        return signer.sign(data)
    except Exception as exc:
        raise TypeError(f"Failed to sign entry: {exc}") from exc


def _verify_sig(
    pubkey_bytes: Optional[bytes],
    signature: bytes,
    data: bytes,
) -> bool:
    if pubkey_bytes is None:
        return False
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        pk = Ed25519PublicKey.from_public_bytes(pubkey_bytes)
        pk.verify(signature, data)
        return True
    except ImportError:
        return False
    except Exception:
        return False
