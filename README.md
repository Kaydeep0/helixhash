# helixhash

A tamper-evident append-only log. Proves a sequence of bytestrings existed in this order at these times and has not been altered.

v1.0 is a clean rewrite. In v0.x, scoring and priors were baked
into the protocol, which created circular dependencies between the
two libraries (HelixHash was a high-trust witness class inside
witnessfield, and witnessfield-style credibility values leaked into
HelixHash entries). v1.0 separates the protocol (what the library
guarantees) from policy (opinions about how to weight things).
HelixHash now only guarantees order and non-tampering. witnessfield
now only describes witness structure. Scoring is a separate,
swappable policy layer.

## Install

```bash
pip install helixhash

# Optional: Ed25519 signing support
pip install helixhash cryptography
```

## What it guarantees

**HelixHash proves a sequence of bytestrings existed in this order at
these times and has not been altered. It makes no claim about whether
the bytestrings are true, meaningful, or correct. Evaluating the
content is the job of a witness layer — see witnessfield.**

## Quickstart

```python
from helixhash import HelixHash

h = HelixHash()
h.append(b"first event")
h.append(b"second event")
h.append(b"third event")

print(h.length)   # 3
print(h.head)     # SHA-256 of the last entry (64-char hex)
print(h.verify()) # True — chain is intact
```

## Hash formula

Each entry's hash commits to: its index, its payload, its timestamp,
its signer's public key (if signed), and the previous entry's hash.

```
SHA-256(
    index            (8 bytes, big-endian)
  | payload_length   (8 bytes, big-endian)
  | payload          (variable)
  | timestamp        (8 bytes, big-endian double)
  | pubkey_length    (2 bytes, big-endian; 0 if unsigned)
  | signer_pubkey    (0 or 32 bytes)
  | prev_hash        (64 ASCII bytes)
)
```

`signer_pubkey` is in the hash so that swapping an entry's public key
breaks the chain immediately. `verify()` catches it.

## Tamper detection

`verify()` replays the full chain in O(n). It catches:

- Any change to a payload
- Any change to a timestamp
- Any change to a signer pubkey
- Any reordering of entries
- Any inserted or deleted entry

```python
# Mutate a payload — verify() returns False
h._entries[1] = Entry(
    index=1, payload=b"tampered", timestamp=h._entries[1].timestamp,
    prev_hash=h._entries[1].prev_hash, hash=h._entries[1].hash,
    signature=None, signer_pubkey=None,
)
print(h.verify())  # False
```

## Optional signing

Pass an `Ed25519PrivateKey` from the `cryptography` library to sign entries.
The signature covers the entry hash. The signer's public key is stored in
the entry and included in the hash.

```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

key = Ed25519PrivateKey.generate()

h = HelixHash()
h.append(b"signed payload", signer=key)
print(h.verify())  # True — signature checks out

# Forge the signer key: replace pubkey in export
exported = h.export()
from base64 import b64encode
other_key = Ed25519PrivateKey.generate()
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
exported[0]["signer_pubkey"] = b64encode(
    other_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
).decode()
h2 = HelixHash.from_export(exported)
print(h2.verify())  # False — pubkey swap breaks the hash
```

## Export and import

```python
import json

# Export to JSON-serialisable list
data = h.export()
json_str = json.dumps(data)

# Reconstruct from export
h2 = HelixHash.from_export(json.loads(json_str))
print(h2.head == h.head)   # True
print(h2.verify())         # True
```

`from_export` validates structural integrity (index order, timestamp
monotonicity, prev_hash chain) before loading. Call `verify()` to
additionally confirm hash integrity.

## API reference

```python
class HelixHash:
    def append(self, payload: bytes, signer=None) -> Entry
    def verify(self) -> bool
    def export(self) -> list[dict]

    @classmethod
    def from_export(cls, entries: list[dict]) -> "HelixHash"

    @property
    def head(self) -> str     # tip hash, or GENESIS_HASH if empty
    @property
    def length(self) -> int

@dataclass(frozen=True)
class Entry:
    index:         int
    payload:       bytes
    timestamp:     float          # unix seconds, monotonically increasing
    prev_hash:     str
    hash:          str
    signature:     Optional[bytes]
    signer_pubkey: Optional[bytes]

GENESIS_HASH: str = "0" * 64    # sentinel for first entry's prev_hash
```

## Tests

```bash
pytest tests/test_helixhash.py -v
```

## Honest limitations

- `time.time()` is used for timestamps. If two appends happen within 1 microsecond,
  the second timestamp is bumped to `previous + 1µs`. Sub-microsecond ordering
  is not guaranteed.
- Signing requires the `cryptography` package. Without it, `signer=None` works
  but signed entries cannot be verified.
- `from_export` does not recompute hashes on load; call `verify()` to do the
  full integrity check.

## License

MIT — Kirandeep Kaur, 2026
