"""
helixhash
=========
The Helix Hash Function — path integral of E = ΔI/A made computable.

Axiom: E = ΔI / A
       Kirandeep Kaur, 2026

Quick start
-----------
>>> from helixhash import HelixHash, Crossing
>>> h = HelixHash()
>>> h.cross(Crossing(delta_I=2.0, A=1.0, kappa=0.62, C=0.9))
>>> h.cross(Crossing(delta_I=1.5, A=0.8, kappa=0.63, C=0.9))
>>> print(h.summary())
"""

from .core import (
    HelixHash,
    Crossing,
    CrossingRecord,
    PHI,
    INV_PHI,
    HBAR,
    KB,
    LANDAUER_A,
)

from .analysis import (
    from_csv,
    from_vault,
    from_dicts,
    detect_decay,
    find_threshold_crossing,
    G_trajectory,
    PT_trajectory,
    regime_changes,
    top_crossings,
    report,
)

__version__ = "0.2.0"
__author__  = "Kirandeep Kaur"
__all__ = [
    "HelixHash", "Crossing", "CrossingRecord",
    "PHI", "INV_PHI", "HBAR", "KB", "LANDAUER_A",
    "from_csv", "from_vault", "from_dicts",
    "detect_decay", "find_threshold_crossing",
    "G_trajectory", "PT_trajectory", "regime_changes",
    "top_crossings", "report",
]
