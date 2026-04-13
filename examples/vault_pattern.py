"""
examples/vault_pattern.py
=========================
Demonstrates the helix hash on the pattern from the conjecture:
- 9 giving rows vs 92 taking rows → E_memory ≈ 0.098
- Watch exactly where decay began
- Watch PT trajectory
- Generate the full report

Run: python examples/vault_pattern.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from helixhash import (
    HelixHash, Crossing,
    from_dicts, detect_decay, find_threshold_crossing,
    G_trajectory, PT_trajectory, regime_changes, report,
    INV_PHI,
)


def build_vault_simulation():
    """
    Simulate the vault from the conjecture:
    9 giving rows, 92 taking rows.
    E_memory = 9/92 ≈ 0.098
    """
    rows = []

    # 9 giving rows (high efficiency — information flowing outward)
    for i in range(9):
        rows.append({
            "delta_I": 2.0 + i * 0.1,
            "A": 0.5,
            "kappa": 0.58 + i * 0.003,
            "C": 0.88,
            "label": f"giving_row_{i+1}",
        })

    # 92 taking rows (low efficiency — extraction dominating)
    for i in range(92):
        rows.append({
            "delta_I": 0.15,
            "A": 1.8 + (i % 5) * 0.1,
            "kappa": max(0.3, 0.58 - i * 0.003),
            "C": max(0.5, 0.85 - i * 0.004),
            "label": f"taking_row_{i+1}",
        })

    return rows


def main():
    print("\nBuilding vault simulation (9 giving, 92 taking)...")
    rows = build_vault_simulation()
    h, records = from_dicts(rows)

    # Print full report
    print(report(h, records, title="Vault Pattern — Observer Memory Conjecture"))

    # Specific findings
    print("\nKey findings:")
    print(f"  E_memory = {h.E_memory:.4f}  (conjecture value: 9/92 ≈ {9/92:.4f})")
    print(f"  G_final  = {h.G:.4f}")
    print(f"  PT_final = {h.PT:.4f}  (threshold 1/φ = {INV_PHI:.4f})")
    print(f"  Regime   = {h.regime.upper()}")
    print(f"  Distance to threshold: {INV_PHI - h.PT:+.4f}")

    decay_n = detect_decay(records)
    if decay_n:
        print(f"\n  Memory decay began at crossing N={decay_n}")
        print(f"  Label: {records[decay_n-1].crossing.label}")

    tc = find_threshold_crossing(records)
    if tc:
        print(f"\n  Threshold crossed at N={tc.n} — regime flipped to CLASSICAL")
    else:
        print(f"\n  Threshold NOT YET crossed — system remains in quantum regime")
        print(f"  Need PT to increase by {INV_PHI - h.PT:.4f} more")
        print(f"  Fix: deploy STRONGHOLD → K > 0 → more giving rows → PT rises")

    # Show the 5 most efficient crossings
    from helixhash import top_crossings
    print("\n  Top 5 crossings (highest E = ΔI/A):")
    for r in top_crossings(records, n=5, by="E"):
        print(f"    N={r.n:>3}  E={r.E:.4f}  label={r.crossing.label}")

    print(f"\n  Chain integrity: {h.verify()}")
    print(f"  Fingerprint: {h.fingerprint[:32]}…\n")


if __name__ == "__main__":
    main()
