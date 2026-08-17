# API Reference

Base URL (local): `http://127.0.0.1:8000`
Interactive docs: `http://127.0.0.1:8000/docs` (try every endpoint in the browser)

All responses are JSON unless noted.

---

## `GET /health`
Liveness check + versions. Returns the service version, the case-law library
version, and the active extraction provider.

---

## `POST /classify`
Classify from **already-extracted terms** plus user inputs. Use this when your CRM
already holds the structured lease terms, or to run the deterministic engine with
no AI step at all.

**Query params**
- `format` — `json` (default) or `markdown` (returns the human-readable report).
- `persist` — `true` (default) writes the result to the audit log.

**Body** (`ClassifyRequest`)
```json
{
  "terms": { ...ExtractedTerms... },
  "user_inputs": { ...UserInputs... }
}
```
See `examples/davalor_2025699.json` for a complete, working body.

**Returns** a `ClassificationReport` (executive summary, solved economics,
traceability matrix, three tracks, flagged ambiguities, authorities, governance
notes).

---

## `POST /classify/document`
Upload a lease **PDF**; the service runs extraction (Claude) then classification.

**Multipart form fields**
- `file` — the lease PDF (required).
- `user_inputs` — a JSON **string** with the missing-input interview answers
  (e.g. `{"economic_useful_life_years": 7, "estimated_end_of_term_fmv": 117352}`).
- `provider` — optional override: `anthropic` or `fixture`.
- `persist` — optional, default `true`.

**Requires** `ANTHROPIC_API_KEY` in the environment.

---

## `GET /report/{id}`
Fetch a previously stored report by its audit-record id (returned in the report's
governance notes when `persist=true`).

## `GET /reports?limit=50`
List recent classifications from the audit log (id, timestamp, document, the three
verdicts, alignment).

## `POST /webhooks/register`
Register a CRM callback URL. Body: `{"url": "https://your-crm/callback"}`. (This
demo keeps them in memory; wire it to your CRM's real callback config.)

---

## How your CRM plugs in

The engine is intentionally **CRM-agnostic**. Two common patterns:

1. **CRM pushes the PDF.** When a deal reaches the "lease received" stage, the CRM
   POSTs the PDF to `/classify/document`, then stores the returned three verdicts
   and the audit-record id on the deal. The full JSON report can be attached as a
   note or file.

2. **CRM pushes structured terms.** If your intake form already captures the lease
   terms, POST them to `/classify` (no AI, instant, free). Map the three verdicts
   to custom fields on the deal record.

Suggested fields to store on the CRM record:
`gaap_verdict`, `tax_verdict`, `ucc_verdict`, `cross_regime_alignment`,
`solved_implicit_yield`, `audit_record_id`, `date_of_analysis`.

Because every call is also written to the audit log, you always have a
server-side record independent of the CRM.

---

## Data shapes (summary)

- **ExtractedTerms** — everything read from the lease (parties, cost, term,
  payment, buyout, governing law, equipment schedule, source sections…). Full
  field list in `app/models.py`.
- **UserInputs** — the interview answers: `fair_market_value_at_inception`,
  `economic_useful_life_years`, `estimated_end_of_term_fmv`,
  `discount_rate_for_pv_test`, `macrs_class_life_years`,
  `lessor_has_residual_value_insurance`, `reporting_framework`.
- **ClassificationReport** — the structured output. See `app/models.py`.
