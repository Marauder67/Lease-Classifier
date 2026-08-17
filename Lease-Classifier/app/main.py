"""
EFG Lease Classifier — HTTP API (FastAPI).

Endpoints
---------
GET  /health                     liveness + versions
POST /classify                   classify from structured terms + user inputs
POST /classify/document          upload a lease PDF; extract then classify
GET  /report/{id}                fetch a stored report
GET  /reports                    list recent classifications (audit log)
POST /webhooks/register          register a CRM callback URL (in-memory demo)

The deterministic engine is CRM-agnostic. `/classify` is the integration point:
your CRM POSTs terms (or uploads the PDF to `/classify/document`) and stores the
returned structured report against the deal record. See docs/API.md.
"""

from __future__ import annotations

import json
import os
from datetime import date

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse

from app import __version__
from app.db import get_classification, init_db, list_classifications, record_classification
from app.engine import case_law
from app.engine.classifier import classify
from app.engine.report import render_markdown
from app.engine.report_html import render_html
from app.models import ClassificationReport, ClassifyRequest, ExtractedTerms, UserInputs

app = FastAPI(
    title="EFG Lease Classifier",
    version=__version__,
    description="Diagnostic three-regime lease classification (GAAP / Tax / UCC). "
                "Classification only — no legal or tax advice, no restructuring output.",
)

# Allow the browser-based intake page (web/new_lease.html) to call the API.
# For an internal tool this is open; tighten allow_origins for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory webhook registry (demo). Replace with the CRM's real callback config.
_WEBHOOKS: list[str] = []


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "EFG Lease Classifier",
        "version": __version__,
        "case_law_library_version": case_law.library_version(),
        "extraction_provider": os.getenv("EFG_EXTRACTION_PROVIDER", "anthropic"),
    }


@app.post("/classify", response_model=ClassificationReport)
def classify_endpoint(
    req: ClassifyRequest,
    format: str = "json",
    persist: bool = True,
):
    """Classify from already-extracted terms + user inputs.

    `format`: json (default) · markdown · html (branded EFG report).
    """
    report = _run(req.terms, req.user_inputs, persist=persist)
    if format == "markdown":
        return PlainTextResponse(render_markdown(report))
    if format == "html":
        return HTMLResponse(render_html(report))
    return report


@app.post("/classify/document")
async def classify_document(
    file: UploadFile = File(...),
    user_inputs: str = Form("{}"),
    provider: str | None = Form(None),
    persist: bool = Form(True),
    format: str = Form("json"),
):
    """Upload a lease PDF; run extraction then classification.

    `user_inputs` is a JSON string carrying the missing-input interview answers.
    `format`: json (default) or html (branded EFG report).
    """
    from app.extraction.base import get_provider

    try:
        ui = UserInputs.model_validate(json.loads(user_inputs or "{}"))
    except Exception as exc:
        raise HTTPException(422, f"Invalid user_inputs JSON: {exc}")

    pdf_bytes = await file.read()
    try:
        extractor = get_provider(provider)
        terms = extractor.extract(pdf_bytes=pdf_bytes, document_name=file.filename)
    except Exception as exc:
        raise HTTPException(502, f"Extraction failed: {exc}")

    report = _run(terms, ui, persist=persist)
    if format == "html":
        return HTMLResponse(render_html(report))
    return report


@app.get("/report/{record_id}")
def get_report(record_id: str) -> dict:
    report = get_classification(record_id)
    if report is None:
        raise HTTPException(404, "Report not found")
    return report


@app.get("/reports")
def get_reports(limit: int = 50) -> list[dict]:
    return list_classifications(limit)


@app.post("/webhooks/register")
def register_webhook(url: str = Body(..., embed=True)) -> dict:
    if url not in _WEBHOOKS:
        _WEBHOOKS.append(url)
    return {"registered": url, "total": len(_WEBHOOKS)}


def _run(terms: ExtractedTerms, inputs: UserInputs, *, persist: bool) -> ClassificationReport:
    try:
        report = classify(terms, inputs, date_of_analysis=date.today().isoformat())
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if persist:
        record_id = record_classification(report.model_dump())
        report.governance_notes = report.governance_notes + [f"Audit record id: {record_id}"]
    return report
