"""Shared enums and result structures for the three classification tracks."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Confidence(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class Result(str, Enum):
    """Outcome of a single criterion/factor/condition test."""

    PASS = "Pass"
    FAIL = "Fail"
    INSUFFICIENT = "Insufficient data"


# ---- Regime verdicts -------------------------------------------------------

class GaapVerdict(str, Enum):
    FINANCE = "Finance Lease"
    OPERATING = "Operating Lease"
    INSUFFICIENT = "Insufficient data"


class TaxVerdict(str, Enum):
    TRUE_LEASE = "True Lease (Tax Lease)"
    CONDITIONAL_SALE = "Conditional Sale"
    INSUFFICIENT = "Insufficient data"


class UccVerdict(str, Enum):
    TRUE_LEASE = "UCC Article 2A True Lease"
    SECURITY_INTEREST = "UCC Article 9 Disguised Security Interest"
    INSUFFICIENT = "Insufficient data"


@dataclass
class Criterion:
    """One row of a track's analysis: an input measured against a threshold."""

    number: int
    name: str
    input_value: str          # human-readable measured value ("60/84 = 71.43%")
    threshold: str            # human-readable threshold ("75% practical threshold")
    result: Result
    confidence: Confidence
    analysis: str = ""        # short neutral explanation, cites authority only

    def as_dict(self) -> dict:
        return {
            "number": self.number,
            "name": self.name,
            "input_value": self.input_value,
            "threshold": self.threshold,
            "result": self.result.value,
            "confidence": self.confidence.value,
            "analysis": self.analysis,
        }


@dataclass
class TrackResult:
    """Common shape returned by each of the three tracks."""

    regime: str                       # "GAAP (ASC 842)", etc.
    verdict: str                      # one of the *Verdict enum values
    confidence: Confidence
    criteria: list[Criterion] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "regime": self.regime,
            "verdict": self.verdict,
            "confidence": self.confidence.value,
            "criteria": [c.as_dict() for c in self.criteria],
            "citations": self.citations,
            "notes": self.notes,
        }
