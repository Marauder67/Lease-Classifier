"""
Anthropic (Claude) extraction provider — the default.

Sends the lease PDF (or text) to Claude with the governed extraction prompt and
parses the returned JSON into an ExtractedTerms object. Requires:

    pip install anthropic
    export ANTHROPIC_API_KEY=sk-ant-...
    export EFG_EXTRACTION_MODEL=claude-...   (optional; sensible default below)

The model reads PDFs natively, so pdf_bytes is preferred over pre-extracted text.
"""

from __future__ import annotations

import base64
import json
import os

from app.extraction.base import ExtractionProvider
from app.extraction.prompt import EXTRACTION_SYSTEM, EXTRACTION_USER
from app.models import ExtractedTerms

DEFAULT_MODEL = os.getenv("EFG_EXTRACTION_MODEL", "claude-sonnet-4-5")


class AnthropicProvider(ExtractionProvider):
    name = "anthropic"

    def __init__(self, model: str | None = None):
        self.model = model or DEFAULT_MODEL

    def extract(self, *, pdf_bytes=None, text=None, document_name=None) -> ExtractedTerms:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "The 'anthropic' package is required for the Anthropic provider. "
                "Run: pip install anthropic") from exc

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Set it, or use the 'fixture' provider "
                "for offline runs (EFG_EXTRACTION_PROVIDER=fixture).")

        client = anthropic.Anthropic(api_key=api_key)
        content: list[dict] = []
        if pdf_bytes is not None:
            content.append({
                "type": "document",
                "source": {
                    "type": "base64", "media_type": "application/pdf",
                    "data": base64.standard_b64encode(pdf_bytes).decode(),
                },
            })
        elif text is not None:
            content.append({"type": "text", "text": f"LEASE DOCUMENT:\n{text}"})
        else:
            raise ValueError("Provide pdf_bytes or text.")
        content.append({"type": "text", "text": EXTRACTION_USER})

        message = client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=EXTRACTION_SYSTEM,
            messages=[{"role": "user", "content": content}],
        )
        raw = "".join(block.text for block in message.content if block.type == "text")
        data = _parse_json(raw)
        if document_name and not data.get("document_name"):
            data["document_name"] = document_name
        return ExtractedTerms.model_validate(data)


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    # Strip accidental markdown fences if the model added them.
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"Extraction did not return JSON. Got: {raw[:200]}")
    return json.loads(raw[start:end + 1])
