"""
Case-law library service (governance-critical).

The UCC track cites the leading authority for the governing-law state. Citations
come ONLY from the controlled library file — the classifier can never invent a
citation. If the governing-law state is not covered, the service returns the
cross-cutting statutory authority and raises a `gap` flag for library expansion.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_LIBRARY_PATH = Path(__file__).resolve().parent.parent / "data" / "case_law_library.json"

# Full state name -> USPS abbreviation (governing-law fields vary in format)
_STATE_NAMES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI",
    "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
    "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}


@lru_cache(maxsize=1)
def _load_library() -> dict:
    with open(_LIBRARY_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def normalize_state(raw: str | None) -> str | None:
    if not raw:
        return None
    s = raw.strip()
    if len(s) == 2 and s.upper() in _STATE_NAMES.values():
        return s.upper()
    return _STATE_NAMES.get(s.lower())


def library_version() -> str:
    return _load_library().get("version", "unknown")


def citations_for_state(raw_state: str | None) -> dict:
    """Return controlled citations for a governing-law state.

    Result shape:
        {
          "state": "OH", "circuit": "Sixth Circuit",
          "controlling": [...], "persuasive": [...], "cross_cutting": [...],
          "gap": False, "gap_note": ""
        }
    Every citation is a dict {citation, holding, url} copied from the library.
    """
    lib = _load_library()
    abbr = normalize_state(raw_state)
    out = {
        "state": abbr or raw_state,
        "circuit": None,
        "controlling": [],
        "persuasive": [],
        "cross_cutting": list(lib["cross_cutting"]),
        "gap": False,
        "gap_note": "",
    }

    if abbr is None:
        out["gap"] = True
        out["gap_note"] = (
            f"Governing-law state '{raw_state}' could not be identified. "
            "Cite UCC §1-203 as adopted by that state and the most authoritative "
            "available decision; flag for library expansion.")
        return out

    # State-specific override (e.g. Ohio's ordered citation list).
    state_specific = lib.get("state_specific", {}).get(abbr)
    if state_specific:
        out["controlling"] = list(state_specific["ordered_citations"])
        for name, circ in lib["circuits"].items():
            if abbr in circ["states"]:
                out["circuit"] = name
        return out

    # Otherwise match the circuit and use its leading case(s).
    for name, circ in lib["circuits"].items():
        if abbr in circ["states"]:
            out["circuit"] = name
            out["controlling"] = list(circ["cases"])
            return out

    out["gap"] = True
    out["gap_note"] = (
        f"No circuit or state entry for {abbr}. Cite UCC §1-203 as adopted by "
        f"{abbr} and the most authoritative available circuit/state decision; "
        "flag for library expansion.")
    return out


def nominal_consideration_table() -> list[dict]:
    return list(_load_library()["nominal_consideration"])
