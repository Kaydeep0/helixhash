"""
helixhash.analysis
==================
Tools for feeding real data into the helix hash and reading the results.

Includes:
- from_csv()       : load any timestamped ratio dataset as crossings
- from_vault()     : load vault giving/taking rows directly
- detect_decay()   : find exactly where E_memory started declining
- find_threshold() : find the crossing where PT first crossed 1/φ
- report()         : print a readable summary of the full path
"""

import csv
import math
import os
from typing import List, Optional, Tuple, Dict

from .core import HelixHash, Crossing, CrossingRecord, INV_PHI, PHI


# ── Loaders ───────────────────────────────────────────────────────────────────

def from_csv(
    path: str,
    delta_I_col: str,
    A_col: str,
    timestamp_col: Optional[str] = None,
    kappa_col: Optional[str] = None,
    C_col: Optional[str] = None,
    label_col: Optional[str] = None,
    default_kappa: float = INV_PHI,
    default_C: float = 1.0,
    fibonacci_weight: float = 0.1,
) -> Tuple[HelixHash, List[CrossingRecord]]:
    """
    Load any CSV with timestamped ratio data as a sequence of crossings.

    Parameters
    ----------
    path : str
        Path to the CSV file.
    delta_I_col : str
        Column name for ΔI (information gained, bits).
    A_col : str
        Column name for A (action cost paid).
    timestamp_col : str, optional
        Column for Unix timestamps. If None, uses row index × 1.0.
    kappa_col : str, optional
        Column for coherence κ. If None, uses default_kappa.
    C_col : str, optional
        Column for credibility C. If None, uses default_C.
    label_col : str, optional
        Column for human-readable crossing label.

    Returns
    -------
    (HelixHash, List[CrossingRecord])
    """
    h = HelixHash(fibonacci_weight=fibonacci_weight)
    records = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            try:
                dI = float(row[delta_I_col])
                A  = float(row[A_col])
                if dI <= 0 or A <= 0:
                    continue
                ts    = float(row[timestamp_col]) if timestamp_col and row.get(timestamp_col) else float(i)
                kappa = float(row[kappa_col]) if kappa_col and row.get(kappa_col) else default_kappa
                C     = float(row[C_col]) if C_col and row.get(C_col) else default_C
                label = str(row[label_col]) if label_col and row.get(label_col) else f"row_{i+1}"
                kappa = max(0.001, min(1.0, kappa))
                C     = max(0.001, min(1.0, C))
                c = Crossing(delta_I=dI, A=A, kappa=kappa, C=C, timestamp=ts, label=label)
                records.append(h.cross(c))
            except (ValueError, KeyError):
                continue
    return h, records


def from_vault(
    path: str,
    giving_label: str = "giving",
    taking_label: str = "taking",
    amount_col: str = "amount",
    timestamp_col: Optional[str] = None,
    label_col: Optional[str] = None,
    fibonacci_weight: float = 0.1,
) -> Tuple[HelixHash, List[CrossingRecord]]:
    """
    Load vault giving/taking rows directly.

    Maps vault row types to (ΔI, A) pairs using fixed heuristics:
    - Giving rows: ΔI = amount, A = amount × 0.1  → E = 10 (outward flow)
    - Taking rows: ΔI = amount × 0.1, A = amount  → E = 0.1 (extraction)
    - Unknown rows: ΔI = A = amount               → E = 1 (neutral)

    HONEST LABEL: the 10x/0.1x factors are DESIGN CHOICES, not derived from
    the axiom. They encode the intuition that giving generates 10× more
    information per unit action than taking extracts. Adjust giving_efficiency
    and taking_efficiency if your system has measured E values.

    Parameters
    ----------
    path : str
        Path to vault CSV.
    giving_label : str
        Value in the type column that marks a giving row.
    taking_label : str
        Value in the type column that marks a taking row.
    amount_col : str
        Column name for the amount / value of the row.
    """
    h = HelixHash(fibonacci_weight=fibonacci_weight)
    records = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        # Auto-detect type column
        type_col = next(
            (c for c in fieldnames if c.lower() in ("type", "kind", "direction", "flow")),
            None
        )
        for i, row in enumerate(reader):
            try:
                amount = float(row[amount_col])
                if amount <= 0:
                    continue
                row_type = row.get(type_col, "").lower() if type_col else ""
                ts    = float(row[timestamp_col]) if timestamp_col and row.get(timestamp_col) else float(i)
                label = str(row[label_col]) if label_col and row.get(label_col) else f"vault_{i+1}"

                if giving_label in row_type:
                    dI, A = amount, max(amount * 0.1, 0.001)
                elif taking_label in row_type:
                    dI, A = max(amount * 0.1, 0.001), amount
                else:
                    # Treat unknown as neutral: E = 1
                    dI, A = amount, amount

                c = Crossing(delta_I=dI, A=A, kappa=INV_PHI, C=0.9, timestamp=ts, label=label)
                records.append(h.cross(c))
            except (ValueError, KeyError):
                continue
    return h, records


def from_dicts(
    rows: List[Dict],
    delta_I_key: str = "delta_I",
    A_key: str = "A",
    kappa_key: str = "kappa",
    C_key: str = "C",
    timestamp_key: str = "timestamp",
    label_key: str = "label",
    default_kappa: float = INV_PHI,
    default_C: float = 1.0,
    fibonacci_weight: float = 0.1,
) -> Tuple[HelixHash, List[CrossingRecord]]:
    """
    Load from a list of dicts (e.g. from a database query or API response).
    """
    h = HelixHash(fibonacci_weight=fibonacci_weight)
    records = []
    for i, row in enumerate(rows):
        try:
            dI    = float(row[delta_I_key])
            A     = float(row[A_key])
            kappa = float(row.get(kappa_key, default_kappa))
            C     = float(row.get(C_key, default_C))
            ts    = float(row.get(timestamp_key, float(i)))
            label = str(row.get(label_key, f"row_{i+1}"))
            kappa = max(0.001, min(1.0, kappa))
            C     = max(0.001, min(1.0, C))
            if dI <= 0 or A <= 0:
                continue
            c = Crossing(delta_I=dI, A=A, kappa=kappa, C=C, timestamp=ts, label=label)
            records.append(h.cross(c))
        except (ValueError, KeyError):
            continue
    return h, records


# ── Analysis ─────────────────────────────────────────────────────────────────

def detect_decay(records: List[CrossingRecord], window: int = 5) -> Optional[int]:
    """
    Find the crossing index where E_memory started its sustained decline.

    Uses a rolling window of E values. Decay is detected when the rolling
    average drops below 1.0 and stays there.

    Returns the 1-based crossing index, or None if no decay detected.
    """
    if len(records) < window + 1:
        return None
    E_vals = [r.E for r in records]
    for i in range(window, len(E_vals)):
        window_mean = sum(E_vals[i-window:i]) / window
        if window_mean < 1.0:
            # Check it stays below
            future = E_vals[i:i+window]
            if future and sum(future) / len(future) < 1.0:
                return i + 1  # 1-based
    return None


def find_threshold_crossing(records: List[CrossingRecord]) -> Optional[CrossingRecord]:
    """
    Return the first crossing where PT reached or exceeded 1/φ.
    Returns None if the threshold has not yet been crossed.
    """
    for r in records:
        if r.threshold_crossed:
            return r
    return None


def G_trajectory(records: List[CrossingRecord]) -> List[Tuple[int, float]]:
    """Return list of (n, G) tuples — the full memory trajectory."""
    return [(r.n, r.G) for r in records]


def PT_trajectory(records: List[CrossingRecord]) -> List[Tuple[int, float]]:
    """Return list of (n, PT) tuples — the full protocol truth trajectory."""
    return [(r.n, r.PT) for r in records]


def regime_changes(records: List[CrossingRecord]) -> List[Tuple[int, str, str]]:
    """
    Return list of (n, from_regime, to_regime) at every regime transition.
    """
    if not records:
        return []
    changes = []
    prev = records[0].regime
    for r in records[1:]:
        if r.regime != prev:
            changes.append((r.n, prev, r.regime))
            prev = r.regime
    return changes


def top_crossings(records: List[CrossingRecord], n: int = 5, by: str = "E") -> List[CrossingRecord]:
    """
    Return the top-n crossings ranked by a metric.

    Parameters
    ----------
    by : str
        One of 'E', 'G', 'PT', 'psi'.
    """
    key_map = {"E": lambda r: r.E, "G": lambda r: r.G,
               "PT": lambda r: r.PT, "psi": lambda r: r.psi}
    key = key_map.get(by, lambda r: r.E)
    return sorted(records, key=key, reverse=True)[:n]


# ── Report ────────────────────────────────────────────────────────────────────

def report(h: HelixHash, records: List[CrossingRecord], title: str = "Helix Hash Report") -> str:
    """
    Generate a readable plain-text report of the full path integral.
    """
    lines = []
    sep  = "─" * 72
    sep2 = "═" * 72

    lines.append(sep2)
    lines.append(f"  {title}")
    lines.append(f"  E = ΔI / A  |  One axiom. Every crossing honestly labeled.")
    lines.append(sep2)
    lines.append("")

    s = h.summary()
    lines.append(f"  Crossings (N)     : {s['N']}")
    lines.append(f"  Accumulated G     : {s['G']:.6f}")
    lines.append(f"  Protocol truth PT : {s['PT']:.6f}  (threshold 1/φ = {INV_PHI:.6f})")
    lines.append(f"  Regime            : {s['regime'].upper()}")
    lines.append(f"  E_memory          : {s['E_memory']:.6f}  ({'healthy' if s['E_memory'] >= 1 else 'DECAYING'})")
    lines.append(f"  Threshold crossed : {'YES' if s['threshold_crossed'] else 'not yet'}")
    lines.append(f"  Distance to 1/φ   : {s['distance_to_threshold']:+.6f}")
    lines.append(f"  Fingerprint       : {s['fingerprint'][:32]}…")
    lines.append(f"  Chain verified    : {h.verify()}")
    lines.append("")

    # Threshold event
    tc = find_threshold_crossing(records)
    if tc:
        lines.append(sep)
        lines.append(f"  THRESHOLD CROSSED at crossing N={tc.n}")
        lines.append(f"  Label     : {tc.crossing.label or '(unlabeled)'}")
        lines.append(f"  E at cross: {tc.E:.4f}  |  G at cross: {tc.G:.4f}")
        lines.append(f"  PT at cross: {tc.PT:.4f}  ≥  1/φ = {INV_PHI:.4f}")
        lines.append(f"  Regime flipped: quantum → classical")
        lines.append("")

    # Decay
    decay_n = detect_decay(records)
    if decay_n:
        dr = records[decay_n - 1]
        lines.append(sep)
        lines.append(f"  MEMORY DECAY detected at crossing N={decay_n}")
        lines.append(f"  Label  : {dr.crossing.label or '(unlabeled)'}")
        lines.append(f"  E_memory dropped below 1.0 and sustained.")
        lines.append(f"  E at crossing: {dr.E:.4f}")
        lines.append("")

    # Top crossings by efficiency
    lines.append(sep)
    lines.append("  Top 5 crossings by efficiency (E = ΔI/A):")
    lines.append(f"  {'N':>4}  {'E':>8}  {'G':>12}  {'PT':>8}  {'regime':<9}  label")
    lines.append(f"  {'─'*4}  {'─'*8}  {'─'*12}  {'─'*8}  {'─'*9}  {'─'*20}")
    for r in top_crossings(records, n=5, by="E"):
        lbl = (r.crossing.label or "")[:20]
        lines.append(
            f"  {r.n:>4}  {r.E:>8.4f}  {r.G:>12.4f}  "
            f"{r.PT:>8.4f}  {r.regime:<9}  {lbl}"
        )
    lines.append("")

    # Full crossing log
    lines.append(sep)
    lines.append("  Full crossing log:")
    lines.append(f"  {'N':>4}  {'E':>8}  {'G':>12}  {'PT':>8}  {'Ψ':>8}  {'regime':<9}  fingerprint")
    lines.append(f"  {'─'*4}  {'─'*8}  {'─'*12}  {'─'*8}  {'─'*8}  {'─'*9}  {'─'*16}")
    for r in records:
        marker = " ◀ THRESHOLD" if r.threshold_crossed else ""
        lines.append(
            f"  {r.n:>4}  {r.E:>8.4f}  {r.G:>12.4f}  "
            f"{r.PT:>8.4f}  {r.psi:>8.4f}  {r.regime:<9}  "
            f"{r.fingerprint[:16]}…{marker}"
        )

    lines.append("")
    lines.append(sep2)
    lines.append("  Kirandeep Kaur | 2026  |  helixhash")
    lines.append(sep2)

    return "\n".join(lines)
