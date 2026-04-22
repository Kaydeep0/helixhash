"""
helixhash
=========
A tamper-evident append-only log.

HelixHash proves a sequence of bytestrings existed in this order at
these times and has not been altered. It makes no claim about whether
the bytestrings are true, meaningful, or correct.

Quick start
-----------
>>> from helixhash import HelixHash
>>> h = HelixHash()
>>> h.append(b"first event")
>>> h.append(b"second event")
>>> h.verify()
True
>>> h.head   # SHA-256 of the latest entry
'...'
"""

from .core import (
    HelixHash,
    Entry,
    GENESIS_HASH,
)

__version__ = "1.0.0"
__author__  = "Kirandeep Kaur"
__all__ = ["HelixHash", "Entry", "GENESIS_HASH"]
