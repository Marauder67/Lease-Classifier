"""
Render a ClassificationReport as Markdown in the exact governed format from the
EFG Lease Classifier prompt (Step 4). The API returns both this Markdown and the
structured JSON; the Markdown is what a human reads, the JSON is what the CRM
consumes.
"""

from __future__ import annotations

from app.models import ClassificationReport


def render_markdown(r: ClassificationReport) -> str:
    L: list[str] = []
    add = L.append

    add("# EFG Lease Classifier Report")
    add(f"**Document:** {r.document or '—'}")
    add(f"**Lessee / Lessor:** {r.lessee or '—'} / {r.lessor or '—'}")
    add(f"**Lease date / term / cost:** {r.lease_date_term_cost or '—'}")
    add(f"**Governing law:** {r.governing_law or '—'}")
    add(f"**Date of analysis:** {r.date_of_analysis or '—'}")
    add(f"**Analyst:** {r.analyst}")
    add("")

    add("## Executive summary")
    add("| Regime | Verdict | Confidence |")
    add("|---|---|---|")
    for row in r.executive_summary:
        add(f"| {row.regime} | {row.verdict} | {row.confidence} |")
    add(f"| Cross-regime alignment | {r.cross_regime_alignment} | — |")
    add("")

    add("## Solved economics")
    se = r.solved_economics
    if se.stated_index_rate is not None:
        add(f"- Stated index rate in lease: {se.stated_index_rate:.2%}")
    add(f"- Solved implicit yield to lessor: {se.solved_implicit_yield:.2%}")
    add(f"- Undiscounted total payments: ${se.undiscounted_total_payments:,.2f}")
    for label, pct in se.pv_percent_at_rate.items():
        add(f"- PV @ {label}: {pct:.1f}% of cost")
    for n in se.notes:
        add(f"- {n}")
    add("")

    if r.traceability_matrix:
        add("## Traceability matrix — which facts trigger which verdicts")
        add("| Fact / Term | GAAP | Tax | UCC | Dispositive? |")
        add("|---|---|---|---|---|")
        for row in r.traceability_matrix:
            add(f"| {row.fact} | {row.gaap_triggered} | {row.tax_triggered} "
                f"| {row.ucc_triggered} | {row.dispositive} |")
        add("")

    for track, title in ((r.gaap, "Track A — GAAP (ASC 842)"),
                         (r.tax, "Track B — Federal tax"),
                         (r.ucc, "Track C — UCC §1-203")):
        add(f"## {title}")
        add(f"**Verdict:** {track.verdict} · Confidence: {track.confidence}")
        add("")
        add("| # | Criterion | Input | Threshold | Result | Conf. |")
        add("|---|---|---|---|---|---|")
        for c in track.criteria:
            add(f"| {c.number} | {c.name} | {c.input_value} | {c.threshold} "
                f"| {c.result} | {c.confidence} |")
        add("")
        for n in track.notes:
            add(f"> {n}")
        if track.citations:
            add("")
            add("_Authorities:_")
            for c in track.citations:
                cite = c.get("authority") or c.get("citation")
                weight = f" ({c['weight']})" if c.get("weight") else ""
                url = f" — {c['url']}" if c.get("url") else ""
                add(f"- {cite}{weight}{url}")
        add("")

    if r.flagged_ambiguities:
        add("## Flagged ambiguities & close calls")
        for f in r.flagged_ambiguities:
            add(f"- {f}")
        add("")

    add("## Authorities cited")
    for a in r.authorities_cited:
        add(f"- {a}")
    add("")

    add("## Governance notes")
    for n in r.governance_notes:
        add(f"- {n}")
    add("")

    return "\n".join(L)
