"""
tests/test_core.py — Each test maps to a claim in the conjecture.

Set HELIXHASH_TEST_INSTALLED=1 to run against the installed package only
(no repo root on sys.path). Use after: pip install .
"""
import math, sys, os

if os.environ.get("HELIXHASH_TEST_INSTALLED") != "1":
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from helixhash import (
    HelixHash, Crossing, CrossingRecord,
    PHI, INV_PHI,
    detect_decay, find_threshold_crossing,
    G_trajectory, PT_trajectory, regime_changes, report, from_dicts, top_crossings,
)

def test_axiom_one_bit():
    h = HelixHash()
    r = h.cross(Crossing(delta_I=1.0, A=1.0, kappa=0.5, C=0.9))
    assert abs(r.E - 1.0) < 1e-10, f"E={r.E}"
    assert r.n == 1
    assert r.regime == "quantum", f"kappa=0.5 should stay quantum, PT={r.PT}"
    print("  PASS: axiom — first +1 produces E=1.0, low kappa keeps quantum regime")

def test_fibonacci_memory():
    h = HelixHash(fibonacci_weight=1.0)
    G_vals = [h.cross(Crossing(delta_I=1.0, A=1.0, kappa=0.62, C=0.9)).G for _ in range(10)]
    for i in range(1, len(G_vals)):
        assert G_vals[i] >= G_vals[i-1], f"G decreased at {i+1}"
    print(f"  PASS: fibonacci memory — G grew {G_vals[0]:.3f} → {G_vals[-1]:.3f}")

def test_threshold_crossing():
    h = HelixHash()
    tc = None
    for _ in range(50):
        r = h.cross(Crossing(delta_I=3.0, A=1.0, kappa=0.65, C=0.95))
        if r.threshold_crossed:
            tc = r; break
    assert tc is not None, "Threshold never crossed"
    assert tc.PT >= INV_PHI
    assert tc.regime == "classical"
    print(f"  PASS: threshold — PT={tc.PT:.4f} ≥ 1/φ={INV_PHI:.4f} at N={tc.n}")

def test_quantum_regime_low_efficiency():
    h = HelixHash()
    for _ in range(20):
        r = h.cross(Crossing(delta_I=0.1, A=2.0, kappa=0.3, C=0.5))
    assert r.regime == "quantum", f"Expected quantum, got {r.regime}"
    print(f"  PASS: quantum regime — low E keeps PT={r.PT:.4f} < 1/φ")

def test_chain_integrity():
    h = HelixHash()
    for i in range(10):
        h.cross(Crossing(delta_I=float(i+1), A=1.0, kappa=0.62, C=0.9))
    assert h.verify() is True
    print("  PASS: chain integrity — 10 fingerprints verified")

def test_path_dependence():
    t0 = 1000000.0
    h1, h2 = HelixHash(), HelixHash()
    h1.cross(Crossing(delta_I=2.0, A=1.0, timestamp=t0))
    h1.cross(Crossing(delta_I=1.0, A=1.0, timestamp=t0+1))
    h2.cross(Crossing(delta_I=1.0, A=1.0, timestamp=t0))
    h2.cross(Crossing(delta_I=2.0, A=1.0, timestamp=t0+1))
    assert h1.fingerprint != h2.fingerprint, "Path-dependence violated"
    print("  PASS: path dependence — order matters")

def test_e_memory_decay():
    # E_memory counts giving (E>=1) vs taking (E<1) by delta_I sums
    h = HelixHash()
    h.cross(Crossing(delta_I=4.0, A=1.0, kappa=0.62, C=0.9))  # E=4, giving
    h.cross(Crossing(delta_I=4.0, A=1.0, kappa=0.62, C=0.9))  # E=4, giving
    for _ in range(10):
        h.cross(Crossing(delta_I=0.1, A=5.0, kappa=0.4, C=0.7))  # E=0.02, taking
    # giving sum=8, taking sum=1 => ratio=8 but by delta_I: giving_dI=8, taking_dI=1
    # need taking to dominate in delta_I sum
    # Re-check: giving_dI=8, taking_dI=10×0.1=1.0 → ratio=8 still > 1
    # Fix: need taking rows with large delta_I but low E (large A)
    h2 = HelixHash()
    h2.cross(Crossing(delta_I=1.0, A=0.1, kappa=0.62, C=0.9))  # giving, dI=1
    for _ in range(20):
        h2.cross(Crossing(delta_I=5.0, A=100.0, kappa=0.4, C=0.7))  # taking, E=0.05, dI=5 each
    assert h2.E_memory < 1.0, f"Expected E_memory<1, got {h2.E_memory:.4f}"
    print(f"  PASS: memory decay — E_memory={h2.E_memory:.4f} < 1.0 (taking dominates)")

def test_psi_positive():
    h = HelixHash(fibonacci_weight=1.0)
    for i in range(20):
        r = h.cross(Crossing(delta_I=float(i+1)*0.5, A=1.0, kappa=0.62, C=0.9))
        assert r.psi >= 0, f"Ψ<0 at N={r.n}: {r.psi}"
    print("  PASS: irreversibility — Ψ≥0 for all 20 crossings")

def test_inv_phi_is_golden_ratio():
    assert abs(INV_PHI - (PHI - 1)) < 1e-12
    assert abs(PHI * INV_PHI - 1.0) < 1e-12
    print(f"  PASS: golden ratio — 1/φ={INV_PHI:.10f}")

def test_detect_decay():
    rows = [{"delta_I": 3.0, "A": 1.0} for _ in range(5)]
    rows += [{"delta_I": 5.0, "A": 100.0} for _ in range(15)]
    h, records = from_dicts(rows)
    decay_n = detect_decay(records)
    assert decay_n is not None, "Decay not detected"
    assert decay_n > 5, f"Decay too early: N={decay_n}"
    print(f"  PASS: decay detection — decline at N={decay_n}")

def test_regime_changes():
    h = HelixHash()
    records = []
    for _ in range(5):
        records.append(h.cross(Crossing(delta_I=0.1, A=2.0, kappa=0.3, C=0.5)))
    for _ in range(50):
        r = h.cross(Crossing(delta_I=5.0, A=1.0, kappa=0.70, C=0.98))
        records.append(r)
        if h.PT >= 0.618:
            break
    changes = regime_changes(records)
    assert len(changes) >= 1, "No regime change detected"
    assert changes[0][1] == "quantum" and changes[0][2] == "classical"
    print(f"  PASS: regime change — quantum→classical at N={changes[0][0]}")

def test_report_generates():
    h = HelixHash()
    records = [h.cross(Crossing(delta_I=float(i+1), A=1.0, kappa=0.62, C=0.9, label=f"t{i}")) for i in range(5)]
    r = report(h, records, title="Test")
    assert "E = ΔI / A" in r and "Kirandeep Kaur" in r
    print("  PASS: report generation")

def run_all():
    tests = [test_axiom_one_bit, test_fibonacci_memory, test_threshold_crossing,
             test_quantum_regime_low_efficiency, test_chain_integrity, test_path_dependence,
             test_e_memory_decay, test_psi_positive, test_inv_phi_is_golden_ratio,
             test_detect_decay, test_regime_changes, test_report_generates]
    passed = failed = 0
    print("\n" + "═"*60)
    print("  HELIX HASH — TEST SUITE")
    print("  Each test maps to a claim in the conjecture.")
    print("═"*60)
    for t in tests:
        try:
            t(); passed += 1
        except Exception as e:
            print(f"  FAIL: {t.__name__} — {e}"); failed += 1
    print("─"*60)
    print(f"  {passed}/{passed+failed} tests passed")
    if failed == 0:
        print("  All claims computably verified.")
    print("═"*60 + "\n")
    return failed == 0

if __name__ == "__main__":
    import sys; sys.exit(0 if run_all() else 1)
