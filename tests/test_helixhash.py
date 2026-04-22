"""
tests/test_helixhash.py
=======================
Tests for helixhash v1.0.0.

Run: pytest tests/test_helixhash.py -v
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
import pytest
from base64 import b64encode
from helixhash import HelixHash, Entry, GENESIS_HASH
from helixhash.core import _compute_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_chain(n: int) -> HelixHash:
    h = HelixHash()
    for i in range(n):
        h.append(f"entry {i}".encode())
    return h


# ---------------------------------------------------------------------------
# Basic append and verify
# ---------------------------------------------------------------------------

def test_empty_chain_verifies():
    h = HelixHash()
    assert h.verify() is True


def test_empty_chain_head_is_genesis():
    h = HelixHash()
    assert h.head == GENESIS_HASH


def test_empty_chain_length_zero():
    assert HelixHash().length == 0


def test_append_returns_entry():
    h = HelixHash()
    e = h.append(b"hello")
    assert isinstance(e, Entry)
    assert e.index == 0
    assert e.payload == b"hello"
    assert e.prev_hash == GENESIS_HASH


def test_append_n_entries_verify_true():
    h = build_chain(20)
    assert h.length == 20
    assert h.verify() is True


def test_head_is_last_entry_hash():
    h = build_chain(5)
    assert h.head == h._entries[-1].hash


def test_chain_links_prev_hashes():
    h = build_chain(4)
    prev = GENESIS_HASH
    for e in h._entries:
        assert e.prev_hash == prev
        prev = e.hash


def test_payload_must_be_bytes():
    h = HelixHash()
    with pytest.raises(TypeError):
        h.append("not bytes")  # type: ignore


# ---------------------------------------------------------------------------
# Tamper detection — payload
# ---------------------------------------------------------------------------

def test_mutate_payload_verify_false():
    """Mutating any entry's payload breaks every subsequent hash."""
    h = build_chain(5)
    assert h.verify() is True

    # Replace the frozen Entry at index 2 with tampered payload
    original = h._entries[2]
    tampered = Entry(
        index=original.index,
        payload=b"TAMPERED",
        timestamp=original.timestamp,
        prev_hash=original.prev_hash,
        hash=original.hash,          # hash not updated — should be detected
        signature=original.signature,
        signer_pubkey=original.signer_pubkey,
    )
    h._entries[2] = tampered
    assert h.verify() is False


def test_mutate_first_payload_verify_false():
    h = build_chain(3)
    original = h._entries[0]
    h._entries[0] = Entry(
        index=original.index,
        payload=b"EVIL",
        timestamp=original.timestamp,
        prev_hash=original.prev_hash,
        hash=original.hash,
        signature=original.signature,
        signer_pubkey=original.signer_pubkey,
    )
    assert h.verify() is False


# ---------------------------------------------------------------------------
# Tamper detection — timestamp
# ---------------------------------------------------------------------------

def test_mutate_timestamp_verify_false():
    """Mutating any entry's timestamp breaks its hash."""
    h = build_chain(4)
    original = h._entries[1]
    h._entries[1] = Entry(
        index=original.index,
        payload=original.payload,
        timestamp=original.timestamp + 9999.0,   # tampered
        prev_hash=original.prev_hash,
        hash=original.hash,                       # stale hash — not updated
        signature=original.signature,
        signer_pubkey=original.signer_pubkey,
    )
    assert h.verify() is False


# ---------------------------------------------------------------------------
# Export / import round-trip
# ---------------------------------------------------------------------------

def test_export_is_json_serialisable():
    h = build_chain(3)
    exported = h.export()
    json.dumps(exported)  # should not raise


def test_export_import_roundtrip_preserves_head():
    h = build_chain(8)
    original_head = h.head
    h2 = HelixHash.from_export(h.export())
    assert h2.head == original_head
    assert h2.length == h.length


def test_from_export_then_verify():
    h = build_chain(5)
    h2 = HelixHash.from_export(h.export())
    assert h2.verify() is True


def test_export_payload_is_base64():
    h = HelixHash()
    h.append(b"\x00\x01\x02\xff")
    exported = h.export()
    assert isinstance(exported[0]["payload"], str)
    import base64
    base64.b64decode(exported[0]["payload"])  # must not raise


# ---------------------------------------------------------------------------
# Out-of-order timestamp rejection
# ---------------------------------------------------------------------------

def test_out_of_order_timestamps_rejected():
    """from_export raises ValueError if timestamps are not monotonically increasing."""
    h = build_chain(3)
    exported = h.export()
    # Swap timestamps of entries 0 and 1 (they're already in order, so swapping = reversal)
    exported[0]["timestamp"], exported[1]["timestamp"] = (
        exported[1]["timestamp"],
        exported[0]["timestamp"],
    )
    with pytest.raises(ValueError, match="[Tt]imestamp"):
        HelixHash.from_export(exported)


def test_out_of_order_index_rejected():
    h = build_chain(3)
    exported = h.export()
    exported[0]["index"] = 99  # wrong index
    with pytest.raises(ValueError):
        HelixHash.from_export(exported)


def test_broken_prev_hash_chain_rejected():
    h = build_chain(3)
    exported = h.export()
    exported[1]["prev_hash"] = "a" * 64  # corrupted link
    with pytest.raises(ValueError, match="prev_hash"):
        HelixHash.from_export(exported)


# ---------------------------------------------------------------------------
# Signing — forged signer is caught
# ---------------------------------------------------------------------------

def test_signed_entry_verifies():
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError:
        pytest.skip("cryptography not installed")

    key = Ed25519PrivateKey.generate()
    h = HelixHash()
    h.append(b"signed payload", signer=key)
    assert h.verify() is True


def test_forged_signer_caught():
    """
    Replacing signer_pubkey in an exported entry breaks the hash
    because signer_pubkey is included in the hash formula.
    verify() returns False.
    """
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    except ImportError:
        pytest.skip("cryptography not installed")

    key_a = Ed25519PrivateKey.generate()
    key_b = Ed25519PrivateKey.generate()

    h = HelixHash()
    h.append(b"secret", signer=key_a)

    exported = h.export()

    # Swap in key_b's pubkey — hash was computed with key_a's pubkey
    exported[0]["signer_pubkey"] = b64encode(
        key_b.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    ).decode("ascii")

    h2 = HelixHash.from_export(exported)
    assert h2.verify() is False


def test_signed_entry_pubkey_in_hash():
    """
    Directly verify that signer_pubkey is bound into the hash:
    recomputing with a different pubkey gives a different hash.
    """
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    except ImportError:
        pytest.skip("cryptography not installed")

    key_a = Ed25519PrivateKey.generate()
    key_b = Ed25519PrivateKey.generate()

    pk_a = key_a.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    pk_b = key_b.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

    h_a = _compute_hash(0, b"payload", 1.0, pk_a, GENESIS_HASH)
    h_b = _compute_hash(0, b"payload", 1.0, pk_b, GENESIS_HASH)
    assert h_a != h_b


def test_unsigned_and_signed_hashes_differ():
    """Unsigned entry (pubkey=None) hashes differently from a signed one."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    except ImportError:
        pytest.skip("cryptography not installed")

    key = Ed25519PrivateKey.generate()
    pk = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

    h_unsigned = _compute_hash(0, b"payload", 1.0, None, GENESIS_HASH)
    h_signed   = _compute_hash(0, b"payload", 1.0, pk,   GENESIS_HASH)
    assert h_unsigned != h_signed
