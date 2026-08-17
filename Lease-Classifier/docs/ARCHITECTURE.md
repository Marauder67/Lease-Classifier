# Architecture & Build Plan

## Design in one picture

```
                 ┌─────────────────────────────────────────────┐
   Lease PDF ──▶ │  EXTRACTION LAYER  (the only AI in the system)│
                 │  app/extraction/  →  ExtractedTerms (JSON)     │
                 └───────────────────────┬─────────────────────┘
                                         │  structured facts only
        User inputs (interview) ─────────┤
                                         ▼
                 ┌─────────────────────────────────────────────┐
                 │  DETERMINISTIC ENGINE  (plain Python, audited) │
                 │  economics → GAAP → Tax → UCC → traceability   │
                 │  case-law lookup (controlled library)          │
                 └───────────────────────┬─────────────────────┘
                                         ▼
                 ClassificationReport (JSON + Markdown) ─▶ API ─▶ CRM
                                         │
                                         ▼
                              Audit log (SQLite → Postgres)
```

The hard boundary between the AI (extraction) and the deterministic engine
(classification) is the central design decision. An LLM is good at reading messy
documents and bad at being reproducible; math and legal thresholds are the
opposite. So the LLM only ever produces *facts*, and every *verdict* comes from
code you can read, test, and defend.

## Why these technology choices

- **FastAPI + Pydantic** — Pydantic gives you typed, self-validating data shapes
  (a bad payload is rejected with a clear error, not a crash). FastAPI turns those
  same types into an interactive `/docs` page for free, which is ideal while you're
  learning and while your CRM team integrates.
- **Deterministic solver (bisection)** — the implicit-rate solver uses bisection
  rather than Newton-Raphson: it always converges and needs no good starting guess,
  so it can't silently return a wrong rate.
- **SQLite now, Postgres later** — SQLite needs zero setup and is perfect for an
  internal tool. `app/db.py` isolates all storage behind a few functions, so moving
  to Postgres is a localized change.
- **Anthropic Claude for extraction, behind an interface** — strong at structured
  extraction and following the governed prompt. The `ExtractionProvider` interface
  means you can swap providers (or add a local model) without touching the engine.

## What was validated

`scripts/verify.py` and `tests/` run the real Davalor pilot case through the whole
engine and assert it reproduces the reference report: solved implicit yield 8.17%,
PV percentages (110.2% / 100.4% / 100.0%), the 71.43% life ratio, and all three
verdicts (Finance Lease / Conditional Sale / Article 9), plus the controlling Ohio
citation. This is the regression guarantee — if a future change breaks any of it,
the tests fail.

## Roadmap to production

**Phase 1 — internal pilot (this repo).** Docker Compose on an internal host.
SQLite. Manual `user_inputs`. Anthropic extraction. Good enough to classify real
leases and integrate with the CRM.

**Phase 2 — hardening.**
- Swap SQLite → managed Postgres (RDS / Azure Database). Only `app/db.py` changes.
- Add authentication (API keys or OAuth) in front of the API.
- Add the implicit-rate and equipment-schedule parsers as pre-checks on extraction
  output (sanity-bound the LLM's numbers against the document totals).
- Add a small review UI so an analyst can confirm/adjust extracted terms before the
  engine runs (human-in-the-loop on the AI step, never on the math).

**Phase 3 — cloud deploy.**
- Package: the included `Dockerfile` runs anywhere.
- AWS: ECS/Fargate behind an Application Load Balancer, or Lambda + API Gateway for
  spiky usage. Secrets in AWS Secrets Manager (never in the image).
- Azure: Container Apps or App Service; secrets in Key Vault.
- Put the CRM callback on a queue (SQS / Service Bus) if you expect bursts.

## Extending the classifier

- **New governing-law state:** edit `app/data/case_law_library.json`, bump its
  `version`, re-run tests. No code change.
- **Tune a threshold:** all numeric thresholds live in `app/engine/thresholds.py`.
- **New regime or criterion:** add a module under `app/engine/` following the
  `TrackResult` shape and call it from `classifier.py`.

## Known simplifications (honest limitations)

- Criterion 5 of ASC 842 (specialized-asset / no alternative use) requires human
  judgment and is reported as "Insufficient data" unless supplied — it is not
  outcome-determinative when Criteria 1/2/4 already trigger a finance lease.
- The economic-realities (second-step) UCC analysis uses residual-interest and
  PV-coverage heuristics; genuinely close calls should still get analyst review.
- Extraction quality depends on document quality; always keep the human-in-the-loop
  confirmation step for production use.
