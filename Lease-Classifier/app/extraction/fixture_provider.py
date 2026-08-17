"""
Fixture extraction provider — returns pre-extracted terms from a JSON file.

Used for offline demos, deterministic tests, and CI where no API key is present.
Point it at any ClassifyRequest-shaped JSON via EFG_FIXTURE_PATH; it defaults to
the bundled Davalor Mold worked example.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from app.extraction.base import ExtractionProvider
from app.models import ExtractedTerms

_DEFAULT_FIXTURE = Path(__file__).resolve().parent.parent.parent / "examples" / "davalor_2025699.json"


class FixtureProvider(ExtractionProvider):
    name = "fixture"

    def __init__(self, path: str | os.PathLike | None = None):
        self.path = Path(path or os.getenv("EFG_FIXTURE_PATH", _DEFAULT_FIXTURE))

    def extract(self, *, pdf_bytes=None, text=None, document_name=None) -> ExtractedTerms:
        with open(self.path, encoding="utf-8") as fh:
            data = json.load(fh)
        terms = data.get("terms", data)
        return ExtractedTerms.model_validate(terms)
