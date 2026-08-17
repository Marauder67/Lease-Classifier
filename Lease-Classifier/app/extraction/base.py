"""
Extraction layer — the ONLY place a language model touches this system.

The model's job is narrow: read a lease document and return structured terms.
It never computes rates, applies thresholds, or renders verdicts — that is all
deterministic Python downstream. Keeping the LLM boxed into extraction is the
core trust design of the tool.

Providers implement `ExtractionProvider.extract()` and are selected at runtime
by the EFG_EXTRACTION_PROVIDER environment variable:

    anthropic  -> Claude (default)
    fixture    -> load a pre-extracted ExtractedTerms JSON (offline / testing)
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod

from app.models import ExtractedTerms


class ExtractionProvider(ABC):
    name: str = "base"

    @abstractmethod
    def extract(self, *, pdf_bytes: bytes | None = None, text: str | None = None,
                document_name: str | None = None) -> ExtractedTerms:
        """Return structured terms from a lease document.

        Supply either the raw PDF bytes (preferred — models read PDFs natively)
        or already-extracted plain text.
        """
        raise NotImplementedError


def get_provider(name: str | None = None) -> ExtractionProvider:
    name = (name or os.getenv("EFG_EXTRACTION_PROVIDER", "anthropic")).lower()
    if name == "anthropic":
        from app.extraction.anthropic_provider import AnthropicProvider
        return AnthropicProvider()
    if name == "fixture":
        from app.extraction.fixture_provider import FixtureProvider
        return FixtureProvider()
    raise ValueError(f"Unknown extraction provider: {name!r}")
