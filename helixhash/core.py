"""
helixhash.core
==============
The Helix Hash Function — computable implementation of G = ∮E·dl

Axiom: E = ΔI / A  (Efficiency = Information gained / Action paid)
       Kirandeep Kaur, 2026

Every crossing is a timestamped efficiency measurement.
Memory compounds as F(N) = F(N-1) + F(N-2).
The fingerprint is path-sensitive and irreversible.
PT = κ × E × (I/A) × C  crosses 1/φ at the quantum→classical threshold.

References
----------
- Observer Memory Conjecture, Kirandeep Kaur (2026)
- Landauer (1961): minimum action per bit = k_B T ln(2)
- Tonomura (1986): Aharonov-Bohm effect — path integral is physically real
- Bekenstein bound: information limit of a physical region
"""

import hashlib
import math
import time
from dataclasses import dataclass, field
from typing import List, Optional

# ── Physical constants ────────────────────────────────────────────────────────
PHI         = (1 + math.sqrt(5)) / 2   # golden ratio
INV_PHI     = 1 / PHI                  # 1/φ ≈ 0.61803 — the threshold
HBAR        = 1.0545718e-34            # J·s — Planck's constant / 2π
KB          = 1.380649e-23             # J/K — Boltzmann constant
LANDAUER_T  = 300.0                    # K   — room temperature default
LANDAUER_A  = KB * LANDAUER_T * math.log(2)  # minimum action per bit ≈ 2.87e-21 J


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class Crossing:
    """
    One irreversible event in the path integral.

    Parameters
    ----------
    delta_I : float
        Bits of surprise resolved. ΔI = H(prior) - H(posterior).
        At minimum: log₂(2/1) = 1 bit for a binary distinction.
    A : float
        Action cost paid. In natural units: multiples of k_B T ln(2).
        At minimum: 1.0 (the Landauer floor, normalised).
    kappa : float
        Coherence. bonds / possible ∈ (0, 1].
        Equilibrium at κ = 1/φ ≈ 0.618.
    C : float
        Credibility. e^(-λ·violations) ∈ (0, 1].
        Perfect credibility = 1.0.
    timestamp : float
        Unix timestamp. Defaults to now.
    label : str
        Human-readable description of this crossing.
    """
    delta_I  : float
    A        : float
    kappa    : float = INV_PHI
    C        : float = 1.0
    timestamp: float = field(default_factory=time.time)
    label    : str   = ""

    def __post_init__(self):
        if self.delta_I <= 0:
            raise ValueError(f"delta_I must be > 0, got {self.delta_I}")
        if self.A <= 0:
            raise ValueError(f"A must be > 0, got {self.A}")
        if not (0 < self.kappa <= 1):
            raise ValueError(f"kappa must be in (0,1], got {self.kappa}")
        if not (0 < self.C <= 1):
            raise ValueError(f"C must be in (0,1], got {self.C}")


@dataclass
class CrossingRecord:
    """
    The full output record for one crossing — everything the helix hash produces.
    """
    n          : int     # crossing index (1-based)
    crossing   : Crossing
    E          : float   # efficiency this crossing = ΔI / A
    G          : float   # accumulated memory (Fibonacci-weighted)
    PT         : float   # protocol truth = κ × E × (I/A)_cumulative × C
    regime     : str     # 'quantum' or 'classical'
    fingerprint: str     # 64-char hex — chained hash of full path
    psi        : float   # irreversibility potential Ψ (normalised)
    threshold_crossed: bool  # True if PT ≥ 1/φ for first time at this crossing

    def __repr__(self):
        return (
            f"Crossing {self.n:>4} | "
            f"E={self.E:7.4f} | "
            f"G={self.G:12.4f} | "
            f"PT={self.PT:6.4f} | "
            f"{self.regime:<9} | "
            f"{self.fingerprint[:16]}…"
        )


# ── The Helix Hash ────────────────────────────────────────────────────────────

class HelixHash:
    """
    The Helix Hash accumulates a path integral of E = ΔI/A.

    Each call to .cross() adds one crossing to the path.
    The path is irreversible: each fingerprint depends on all prior fingerprints.
    Memory compounds as Fibonacci: G(n) = G(n-1) + G(n-2) + ε·E(n).

    The threshold PT = 1/φ marks the quantum→classical transition.
    Below it: exploring, probabilistic, potential.
    At it:    collapse — probability becomes 0 or 1.
    Above it: committed, irreversible, actual.

    Usage
    -----
    >>> h = HelixHash()
    >>> r = h.cross(Crossing(delta_I=1.0, A=1.0, kappa=0.62, C=0.9))
    >>> print(r)
    """

    def __init__(self, fibonacci_weight: float = 0.1, min_crossings_for_threshold: int = 3):
        """
        Parameters
        ----------
        fibonacci_weight : float
            How strongly each new E_n contributes to the Fibonacci accumulation.
        min_crossings_for_threshold : int
            Minimum crossings before PT can declare classical regime.
            Guards against a single high-E crossing flipping the regime immediately.
            The conjecture requires accumulated path history. Default 3.
        """
        self._records      : List[CrossingRecord] = []
        self._prev_hash    : str   = "0" * 64
        self._G_prev2      : float = 0.0
        self._G_prev1      : float = 0.0
        self._sum_dI       : float = 0.0
        self._sum_A        : float = 0.0
        self._threshold_hit: bool  = False
        self.fibonacci_weight = fibonacci_weight
        self.min_crossings_for_threshold = min_crossings_for_threshold

    # ── Public API ────────────────────────────────────────────────────────────

    def cross(self, c: Crossing) -> CrossingRecord:
        """Add one crossing to the path integral. Returns the full record."""
        n = len(self._records) + 1

        # Efficiency this crossing
        E = c.delta_I / c.A

        # Fibonacci-weighted memory accumulation
        # G(n) = G(n-1) + G(n-2) + ε·E(n)
        # At n=1,2 we bootstrap from the seed
        if n == 1:
            G = E
        elif n == 2:
            G = self._G_prev1 + E
        else:
            G = self._G_prev1 + self._G_prev2 + self.fibonacci_weight * E

        # Cumulative I/A ratio (total information / total action)
        self._sum_dI += c.delta_I
        self._sum_A  += c.A
        cumulative_IA = self._sum_dI / self._sum_A

        # Protocol truth — product of all N/D ratios
        PT = min(c.kappa * E * cumulative_IA * c.C, 1.0)

        # Regime — requires min_crossings_for_threshold before classical can be declared
        # HONEST LABEL: this guard is a design choice, not derived from the axiom.
        # It prevents a single isolated high-E event from flipping the regime.
        # The conjecture states PT is a cumulative product; single events are not paths.
        was_quantum = not self._threshold_hit
        enough_history = n >= self.min_crossings_for_threshold
        newly_crossed = (PT >= INV_PHI) and was_quantum and enough_history
        if newly_crossed:
            self._threshold_hit = True
        regime = "classical" if (PT >= INV_PHI and self._threshold_hit) else "quantum"

        # Irreversibility potential Ψ
        # HONEST LABEL: ESTIMATED — the full expression requires A_erase from
        # the actual physical system. Here A_erase grows with G as a proxy:
        # A_erase = A_write × (1 + G/ref) where ref = max(G, 10).
        # This captures the correct direction (Ψ grows as memory accumulates)
        # but the absolute values are not derived from first principles.
        # Ψ ≥ 0 is guaranteed by construction (second law holds).
        A_erase = c.A * (1 + G / max(G, 10))
        psi = c.delta_I * (A_erase - c.A) / (c.A * A_erase) if A_erase > c.A else 0.0

        # Fingerprint — chain hash of full crossing state + previous fingerprint
        payload = (
            f"{n}|{c.delta_I:.8f}|{c.A:.8f}|"
            f"{c.kappa:.8f}|{c.C:.8f}|"
            f"{c.timestamp:.6f}|{self._prev_hash}"
        ).encode()
        fingerprint = hashlib.sha256(payload).hexdigest()

        # Build record
        record = CrossingRecord(
            n=n,
            crossing=c,
            E=E,
            G=G,
            PT=PT,
            regime=regime,
            fingerprint=fingerprint,
            psi=psi,
            threshold_crossed=newly_crossed,
        )

        # Advance state
        self._records.append(record)
        self._prev_hash = fingerprint
        self._G_prev2   = self._G_prev1
        self._G_prev1   = G

        return record

    def cross_many(self, crossings: List[Crossing]) -> List[CrossingRecord]:
        """Feed a list of crossings at once. Returns all records."""
        return [self.cross(c) for c in crossings]

    # ── Introspection ─────────────────────────────────────────────────────────

    @property
    def records(self) -> List[CrossingRecord]:
        return list(self._records)

    @property
    def G(self) -> float:
        """Current accumulated memory G = ∮E·dl"""
        return self._records[-1].G if self._records else 0.0

    @property
    def PT(self) -> float:
        """Current protocol truth value"""
        return self._records[-1].PT if self._records else 0.0

    @property
    def regime(self) -> str:
        """Current regime: 'quantum' or 'classical'"""
        return self._records[-1].regime if self._records else "quantum"

    @property
    def fingerprint(self) -> str:
        """Current fingerprint — encodes the entire path"""
        return self._prev_hash

    @property
    def N(self) -> int:
        """Number of crossings so far"""
        return len(self._records)

    @property
    def E_memory(self) -> float:
        """
        E_memory = Σ(ΔI where E≥1) / Σ(ΔI where E<1)

        HONEST LABEL: PROXY — this uses E≥1 as a proxy for "giving" and E<1
        for "taking". In the vault system, E≥1 crossings correspond to outward
        information flow (giving rows) and E<1 to extraction (taking rows).
        If your data has an explicit source column, use from_vault() which maps
        the type column directly. Raw crossings without labels use this proxy.

        System is healthy when E_memory > 1 (giving outpaces taking).
        System is decaying when E_memory < 1 (extraction dominates).
        Conjecture value for the live system: E_memory = 9/92 ≈ 0.098.
        """
        if not self._records:
            return 0.0
        giving = sum(r.crossing.delta_I for r in self._records if r.E >= 1.0)
        taking = sum(r.crossing.delta_I for r in self._records if r.E < 1.0)
        return giving / taking if taking > 0 else float('inf')

    def summary(self) -> dict:
        """Return a summary dict of the current helix state."""
        if not self._records:
            return {"N": 0, "G": 0.0, "PT": 0.0, "regime": "quantum",
                    "E_memory": 0.0, "threshold_crossed": False,
                    "fingerprint": self._prev_hash}
        return {
            "N"                : self.N,
            "G"                : round(self.G, 6),
            "PT"               : round(self.PT, 6),
            "regime"           : self.regime,
            "E_memory"         : round(self.E_memory, 6),
            "threshold_crossed": self._threshold_hit,
            "fingerprint"      : self.fingerprint,
            "INV_PHI"          : round(INV_PHI, 6),
            "distance_to_threshold": round(INV_PHI - self.PT, 6),
        }

    def verify(self) -> bool:
        """
        Verify the integrity of the entire chain.
        Re-derives every fingerprint from scratch and checks it matches.
        Returns True if the chain is intact, False if any crossing was tampered with.
        """
        prev = "0" * 64
        for r in self._records:
            c = r.crossing
            payload = (
                f"{r.n}|{c.delta_I:.8f}|{c.A:.8f}|"
                f"{c.kappa:.8f}|{c.C:.8f}|"
                f"{c.timestamp:.6f}|{prev}"
            ).encode()
            expected = hashlib.sha256(payload).hexdigest()
            if expected != r.fingerprint:
                return False
            prev = r.fingerprint
        return True

    def __repr__(self):
        return (
            f"HelixHash(N={self.N}, G={self.G:.4f}, "
            f"PT={self.PT:.4f}, regime='{self.regime}')"
        )
