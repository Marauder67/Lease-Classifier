"""
Branded HTML renderer for a ClassificationReport.

Produces a single self-contained HTML document (logo embedded as a data URI,
Poppins loaded from Google Fonts with a system fallback) styled in the EFG
palette. Suitable for viewing in a browser, printing to PDF, or attaching to a
CRM record. All brand values come from app/branding.py.
"""

from __future__ import annotations

import html

from app import branding as B
from app.models import ClassificationReport

_FINANCING_VERDICTS = {
    "Finance Lease", "Conditional Sale", "UCC Article 9 Disguised Security Interest",
}


def _esc(v) -> str:
    return html.escape(str(v)) if v is not None else ""


def _verdict_badge(verdict: str) -> str:
    if verdict == "Insufficient data":
        color = B.INSUFFICIENT_GRAY
    elif verdict in _FINANCING_VERDICTS:
        color = B.RED
    else:
        color = B.PASS_GREEN
    return f'<span class="badge" style="background:{color}">{_esc(verdict)}</span>'


def _result_chip(result: str) -> str:
    color = {"Pass": B.PASS_GREEN, "Fail": B.FAIL_RED}.get(result, B.INSUFFICIENT_GRAY)
    return f'<span class="chip" style="color:{color};border-color:{color}">{_esc(result)}</span>'


def _cite_li(c: dict) -> str:
    name = _esc(c.get("authority") or c.get("citation"))
    weight = f" <em>({_esc(c['weight'])})</em>" if c.get("weight") else ""
    url = c.get("url")
    link = ""
    if url:
        u = _esc(url)
        link = f' &mdash; <a href="{u}">{u}</a>'
    return f"<li>{name}{weight}{link}</li>"


def _track_section(track, title: str) -> str:
    rows = "".join(
        f"<tr><td class='num'>{c.number}</td><td>{_esc(c.name)}</td>"
        f"<td>{_esc(c.input_value)}</td><td>{_esc(c.threshold)}</td>"
        f"<td>{_result_chip(c.result)}</td><td>{_esc(c.confidence)}</td></tr>"
        for c in track.criteria
    )
    notes = "".join(f"<p class='note'>{_esc(n)}</p>" for n in track.notes)
    cites = ""
    if track.citations:
        items = "".join(_cite_li(c) for c in track.citations)
        cites = f"<div class='cites'><strong>Authorities:</strong><ul>{items}</ul></div>"
    return f"""
    <section class="track">
      <h2>{_esc(title)}</h2>
      <p class="verdict-line">Verdict: {_verdict_badge(track.verdict)}
         <span class="conf">Confidence: {_esc(track.confidence)}</span></p>
      <table class="grid">
        <thead><tr><th>#</th><th>Criterion</th><th>Input</th><th>Threshold</th><th>Result</th><th>Conf.</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
      {notes}{cites}
    </section>"""


def render_html(r: ClassificationReport) -> str:
    summary_rows = "".join(
        f"<tr><td>{_esc(row.regime)}</td><td>{_verdict_badge(row.verdict)}</td>"
        f"<td>{_esc(row.confidence)}</td></tr>"
        for row in r.executive_summary
    )
    econ = r.solved_economics
    econ_rows = "".join(
        f"<tr><td>PV @ {_esc(label)}</td><td>{pct:.1f}% of cost</td></tr>"
        for label, pct in econ.pv_percent_at_rate.items()
    )
    trace_rows = "".join(
        f"<tr><td>{_esc(x.fact)}</td><td>{_esc(x.gaap_triggered)}</td>"
        f"<td>{_esc(x.tax_triggered)}</td><td>{_esc(x.ucc_triggered)}</td>"
        f"<td>{_esc(x.dispositive)}</td></tr>"
        for x in r.traceability_matrix
    )
    flags = "".join(f"<li>{_esc(f)}</li>" for f in r.flagged_ambiguities) or "<li>None.</li>"
    auth = "".join(f"<li>{_esc(a)}</li>" for a in r.authorities_cited)
    gov = "".join(f"<li>{_esc(n)}</li>" for n in r.governance_notes)
    logo = B.logo_data_uri()
    logo_img = f'<img src="{logo}" alt="Equipment Finance Group" class="logo"/>' if logo else ""

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>EFG Lease Classifier Report — {_esc(r.document)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700;800&display=swap" rel="stylesheet">
<style>
  :root {{
    --navy:{B.NAVY}; --red:{B.RED}; --charcoal:{B.CHARCOAL};
    --light:{B.LIGHT}; --border:{B.BORDER};
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; color:var(--charcoal); background:#fff;
         font-family:{B.BODY_FONT_STACK}; font-size:14px; line-height:1.5; }}
  h1,h2,h3 {{ font-family:'{B.DISPLAY_FONT}', {B.BODY_FONT_STACK}; color:var(--navy); }}
  .wrap {{ max-width:960px; margin:0 auto; padding:0 28px 48px; }}
  header.band {{ background:var(--navy); color:#fff; padding:22px 28px; }}
  header.band .inner {{ max-width:960px; margin:0 auto; display:flex; align-items:center; gap:20px; }}
  .logo {{ height:46px; background:#fff; padding:6px 10px; border-radius:6px; }}
  header.band h1 {{ color:#fff; margin:0; font-size:22px; font-weight:700;
                   border-left:3px solid var(--red); padding-left:16px; }}
  .meta {{ background:var(--light); border:1px solid var(--border); border-radius:8px;
          padding:16px 20px; margin:24px 0; display:grid;
          grid-template-columns:1fr 1fr; gap:6px 28px; font-size:13px; }}
  .meta b {{ color:var(--navy); }}
  h2 {{ font-size:17px; margin:30px 0 12px; padding-bottom:6px;
       border-bottom:2px solid var(--border); }}
  table {{ width:100%; border-collapse:collapse; margin:8px 0 4px; }}
  th,td {{ text-align:left; padding:8px 10px; border-bottom:1px solid var(--border);
          vertical-align:top; font-size:13px; }}
  thead th {{ background:var(--navy); color:#fff; font-weight:600;
             font-family:'{B.DISPLAY_FONT}', sans-serif; font-size:12px;
             text-transform:uppercase; letter-spacing:.03em; }}
  table.grid td.num {{ width:32px; color:var(--navy); font-weight:700; }}
  .badge {{ display:inline-block; color:#fff; padding:3px 10px; border-radius:12px;
           font-weight:600; font-size:12px; }}
  .chip {{ display:inline-block; border:1px solid; padding:1px 8px; border-radius:10px;
          font-weight:600; font-size:12px; }}
  .verdict-line {{ margin:4px 0 10px; }}
  .conf {{ color:#6B7280; margin-left:12px; font-size:12px; }}
  .note {{ background:var(--light); border-left:3px solid var(--navy);
          padding:8px 12px; margin:8px 0; font-size:13px; }}
  .cites {{ font-size:12px; color:#4b5563; margin-top:6px; }}
  .cites ul, .list ul {{ margin:4px 0 0; padding-left:18px; }}
  a {{ color:var(--navy); }}
  .disclaimer {{ margin-top:34px; padding:16px 20px; border:1px solid var(--border);
                border-radius:8px; background:var(--light); font-size:12px; color:#4b5563; }}
  .disclaimer strong {{ color:var(--red); }}
  footer {{ text-align:center; color:#9aa3ad; font-size:11px; margin-top:26px; }}
  @media print {{ header.band {{ -webkit-print-color-adjust:exact; print-color-adjust:exact; }} }}
</style>
</head><body>
<header class="band"><div class="inner">{logo_img}<h1>Lease Classifier Report</h1></div></header>
<div class="wrap">

  <div class="meta">
    <div><b>Document:</b> {_esc(r.document)}</div>
    <div><b>Governing law:</b> {_esc(r.governing_law)}</div>
    <div><b>Lessee:</b> {_esc(r.lessee)}</div>
    <div><b>Lessor:</b> {_esc(r.lessor)}</div>
    <div><b>Lease:</b> {_esc(r.lease_date_term_cost)}</div>
    <div><b>Date of analysis:</b> {_esc(r.date_of_analysis)}</div>
    <div style="grid-column:1/3"><b>Analyst:</b> {_esc(r.analyst)}</div>
  </div>

  <h2>Executive summary</h2>
  <table>
    <thead><tr><th>Regime</th><th>Verdict</th><th>Confidence</th></tr></thead>
    <tbody>{summary_rows}
      <tr><td><b>Cross-regime alignment</b></td><td colspan="2">{_esc(r.cross_regime_alignment)}</td></tr>
    </tbody>
  </table>

  <h2>Solved economics</h2>
  <table>
    <tbody>
      <tr><td>Stated index rate in lease</td><td>{_fmt_rate(econ.stated_index_rate)}</td></tr>
      <tr><td><b>Solved implicit yield to lessor</b></td><td><b>{econ.solved_implicit_yield:.2%}</b></td></tr>
      <tr><td>Undiscounted total payments</td><td>${econ.undiscounted_total_payments:,.2f}</td></tr>
      {econ_rows}
    </tbody>
  </table>
  {"".join(f'<p class="note">{_esc(n)}</p>' for n in econ.notes)}

  {"".join([f'''
  <h2>Traceability matrix &mdash; which facts trigger which verdicts</h2>
  <table><thead><tr><th>Fact / Term</th><th>GAAP</th><th>Tax</th><th>UCC</th><th>Dispositive?</th></tr></thead>
  <tbody>{trace_rows}</tbody></table>''']) if trace_rows else ""}

  {_track_section(r.gaap, "Track A — GAAP (ASC 842)")}
  {_track_section(r.tax, "Track B — Federal tax")}
  {_track_section(r.ucc, "Track C — UCC §1-203")}

  <h2>Flagged ambiguities &amp; close calls</h2>
  <div class="list"><ul>{flags}</ul></div>

  <h2>Authorities cited</h2>
  <div class="list"><ul>{auth}</ul></div>

  <h2>Governance notes</h2>
  <div class="list"><ul>{gov}</ul></div>

  <div class="disclaimer">
    <strong>Diagnostic classification only.</strong> This report does not constitute
    legal or tax advice and contains no restructuring recommendations. The three
    regimes are analysed independently. Case-law citations are drawn solely from the
    controlled EFG Case Law Library.
  </div>

  <footer>Equipment Finance Group &middot; EFG Lease Classifier v1.1 &middot; Generated for internal use</footer>
</div>
</body></html>"""


def _fmt_rate(v) -> str:
    return f"{v:.2%}" if isinstance(v, (int, float)) else "—"
