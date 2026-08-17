"""
Standalone verification harness (no pytest required).

Runs the golden Davalor classification end-to-end and checks the key assertions
from tests/, then prints the rendered Markdown report. Use this for a quick,
dependency-light confidence check:

    python3 scripts/verify.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.engine import case_law                       # noqa: E402
from app.engine.classifier import classify            # noqa: E402
from app.engine.economics import compute_economics    # noqa: E402
from app.engine.report import render_markdown         # noqa: E402
from app.models import ClassifyRequest, ExtractedTerms, UserInputs  # noqa: E402

checks = []


def check(label, cond):
    checks.append((label, bool(cond)))
    print(("  PASS  " if cond else "  FAIL  ") + label)


print("=== Economics ===")
econ = compute_economics(586760.0, 11863.13, 60, timing="advance", buyout=1.0,
                         stated_index_rate=0.0397, extra_rates={"ibr": 0.08})
check(f"solved implicit yield 8.17% (got {econ.solved_implicit_yield:.4%})",
      abs(econ.solved_implicit_yield - 0.0817) < 0.0005)
check(f"PV @ solved = 100.0% (got {econ.pv_percent_at_rate['solved_implicit']:.1f}%)",
      abs(econ.pv_percent_at_rate['solved_implicit'] - 100.0) < 0.1)
check(f"PV @ IBR 8% = 100.4% (got {econ.pv_percent_at_rate['ibr']:.1f}%)",
      abs(econ.pv_percent_at_rate['ibr'] - 100.4) < 0.2)
check(f"PV @ SOFR 3.97% = 110.2% (got {econ.pv_percent_at_rate['stated_index']:.1f}%)",
      abs(econ.pv_percent_at_rate['stated_index'] - 110.2) < 0.2)

print("\n=== Case law library ===")
oh = case_law.citations_for_state("Ohio")
check("Ohio -> Sixth Circuit", oh["circuit"] == "Sixth Circuit")
check("Ohio controlling cites QDS Components",
      any("QDS" in c["citation"] for c in oh["controlling"]))
de = case_law.citations_for_state("DE")
check("Delaware -> Third Circuit / Pillowtex",
      de["circuit"] == "Third Circuit" and any("Pillowtex" in c["citation"] for c in de["controlling"]))
gap = case_law.citations_for_state("Atlantis")
check("Unknown state flags gap, invents nothing", gap["gap"] and gap["controlling"] == [])

print("\n=== Golden Davalor classification ===")
data = json.loads((ROOT / "examples" / "davalor_2025699.json").read_text())
req = ClassifyRequest.model_validate(data)
report = classify(req.terms, req.user_inputs, date_of_analysis="2026-08-13")
verdicts = {r.regime: r.verdict for r in report.executive_summary}
check(f"GAAP = Finance Lease (got {verdicts['GAAP (ASC 842)']})",
      verdicts["GAAP (ASC 842)"] == "Finance Lease")
check(f"Tax = Conditional Sale (got {verdicts['Tax (IRC)']})",
      verdicts["Tax (IRC)"] == "Conditional Sale")
check(f"UCC = Article 9 Security Interest (got {verdicts['UCC (§1-203)']})",
      verdicts["UCC (§1-203)"] == "UCC Article 9 Disguised Security Interest")
check("Cross-regime fully aligned (financing)",
      "Fully aligned" in report.cross_regime_alignment and "financing" in report.cross_regime_alignment)

gaap_by_num = {c.number: c.result for c in report.gaap.criteria}
check("GAAP criteria 1,2,4 PASS; 3 FAIL",
      gaap_by_num[1] == "Pass" and gaap_by_num[2] == "Pass" and gaap_by_num[4] == "Pass" and gaap_by_num[3] == "Fail")
tax5 = next(c for c in report.tax.criteria if c.number == 5)
check("Tax factor 5 (bargain) FAIL & dispositive", tax5.result == "Fail")
ucc4 = next(c for c in report.ucc.criteria if c.number == 4)
check("UCC per se condition 4 MET", ucc4.result == "Pass")
check("UCC cites controlling Ohio QDS authority",
      any("QDS" in c.get("citation", "") for c in report.ucc.citations))

blob = json.dumps(report.model_dump()).lower()
check("No restructuring language present",
      all(b not in blob for b in ["restructure the lease", "you should restructure", "to convert this to an operating lease"]))

print("\n=== Rendered Markdown report (first 60 lines) ===")
md = render_markdown(report)
print("\n".join(md.splitlines()[:60]))

passed = sum(1 for _, ok in checks if ok)
print(f"\n=========== {passed}/{len(checks)} checks passed ===========")
sys.exit(0 if passed == len(checks) else 1)
