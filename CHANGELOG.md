# Changelog

## v1.0.0 — 2026-04-22

### BREAKING CHANGES

v1.0 is a clean rewrite. In v0.x, scoring and priors were baked
into the protocol, which created circular dependencies between the
two libraries (HelixHash was a high-trust witness class inside
witnessfield, and witnessfield-style credibility values leaked into
HelixHash entries). v1.0 separates the protocol (what the library
guarantees) from policy (opinions about how to weight things).
HelixHash now only guarantees order and non-tampering. witnessfield
now only describes witness structure. Scoring is a separate,
swappable policy layer.

### Removed

Everything related to scoring and interpretation has been deleted:

- `PT` (protocol truth score) — removed entirely
- `kappa`, `C`, `delta_I` as `Crossing` fields — removed
- `Crossing` dataclass — removed
- `CrossingRecord` dataclass — removed
- Fibonacci memory accumulation (`G`) — removed
- Golden ratio threshold (`1/φ`) — removed
- Regime classification (`quantum`/`classical`) — removed
- `E_memory` — removed
- `analysis.py` module (`from_csv`, `from_vault`, `from_dicts`, `detect_decay`,
  `find_threshold_crossing`, `G_trajectory`, `PT_trajectory`, `regime_changes`,
  `top_crossings`, `report`) — removed
- All mention of "truth", "credibility", "coherence" in the public API — removed

### Added / Rebuilt

- `Entry` dataclass: `index`, `payload`, `timestamp`, `prev_hash`, `hash`,
  `signature`, `signer_pubkey`
- `HelixHash.append(payload, signer=None)` — returns `Entry`
- `HelixHash.verify()` — O(n) hash + signature replay
- `HelixHash.export()` / `HelixHash.from_export()` — JSON round-trip
- `HelixHash.head` property — current tip hash
- `HelixHash.length` property
- `GENESIS_HASH` constant

### Hash formula change

v0.x did not have a signer identity in the hash. v1.0 includes
`signer_pubkey` in the canonical hash:

```
SHA-256(index | payload_length | payload | timestamp | pubkey_length | signer_pubkey | prev_hash)
```

Swapping a pubkey on a signed entry now immediately breaks `verify()`.

### Migration

There is no migration path from v0.x chain data to v1.0 — the data
structures are incompatible. Archive v0.x exports before upgrading.
The archived tag is `v0.3.0-archive`.

---

## v0.3.0 (archived at `v0.3.0-archive`)

Final v0.x release. HelixHash computed path integrals of E = ΔI/A
with Fibonacci memory accumulation, a protocol truth score PT, and
regime transitions at 1/φ. These features were removed in v1.0.
