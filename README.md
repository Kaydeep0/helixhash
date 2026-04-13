# helixhash

A hash-chained observation log with Fibonacci memory accumulation and a protocol truth score.

## Install

```bash
pip install helixhash
```

## Quickstart

```python
from helixhash import HelixHash, Crossing

h = HelixHash()

h.cross(Crossing(
    delta_I=2.0,   # log-ratio surprise in bits: log2(observed / expected)
    A=1.0,         # observation cost (API calls, processing steps, time elapsed)
    kappa=0.62,    # system coherence (0 to 1)
    C=0.9,         # credibility (0 to 1)
    label="SOFR rate change"
))

h.cross(Crossing(
    delta_I=0.5,
    A=1.0,
    kappa=0.63,
    C=0.9,
    label="BUIDL TVL movement"
))

print(h.verify())     # True — chain is intact
print(h.fingerprint)  # 64-char SHA-256
print(h.PT)           # protocol truth score (0 to 1)
print(h.G)            # accumulated mass
```

## Three properties

**1. Fingerprint chain**

Each crossing produces:

```
SHA256(n | delta_I | A | kappa | C | timestamp | prev_fingerprint)
```

The previous fingerprint is embedded in every new one. Altering any historical record breaks every subsequent fingerprint at that exact point. `h.verify()` checks the full chain in O(n).

**2. Fibonacci memory**

```
G(1) = E(1)
G(2) = G(1) + E(2)
G(n) = G(n-1) + G(n-2) + epsilon * E(n)
```

Older high-efficiency observations retain persistent weight through Fibonacci recurrence. This is a design choice: the unique solution to the unit-coefficient two-state recurrence. Not proven optimal.

**3. Protocol truth score**

```
PT = kappa * E_current * (sum_dI / sum_A) * C
```

| PT | Regime |
|----|--------|
| PT < 0.618 | quantum (accumulating) |
| PT = 0.618 | golden ratio threshold |
| PT > 0.618 | classical (committed) |

The threshold is 1/φ ≈ 0.618 — the fixed point of the Fibonacci recurrence in continuous form.

## Committing on-chain

To create an immutable timestamp for any fingerprint:

1. Run your observation sequence
2. Read `h.fingerprint` (64-char hex string)
3. Submit it as calldata in any EVM transaction
4. The block timestamp is your proof — anyone can verify by recomputing and comparing

## Reference implementation

Eigenstate Research uses HelixHash to watch 197 entities in tokenized settlement infrastructure and commit fingerprints to Base mainnet every 2 hours.

- Research and on-chain proof index: https://kaydeep0.github.io/eigenstate-research/
- Five-minute demo with live data: https://kaydeep0.github.io/eigenstate-research/demo/
- 11 verified commits on Base mainnet: https://kaydeep0.github.io/eigenstate-research/onchain/

## Honest limitations

- `delta_I` is a log-ratio proxy, not exact KL divergence. It approximates entropy reduction but is not identical to it.
- Fibonacci accumulation is a design choice, not a proven optimum.
- The PT threshold at the golden ratio is derived from the Fibonacci fixed point, not from empirical calibration.

## Tests

```bash
python tests/test_core.py
```

## License

MIT — Kirandeep Kaur, 2026
