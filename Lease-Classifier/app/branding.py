"""
EFG brand constants — the single source of truth for palette and type in code.

Values are from the official Brand Assets kit (06 Brand Assets):
  - Navy / Red come from the registered trademark (USPTO Reg. No. 5359034).
  - Red is an ACCENT only — never body text or large fills.
  - Charcoal is the standard body/heading text colour.
  - Poppins (OFL, embeddable) is the display font for web/PDF headlines.
"""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

# --- Palette (authoritative hex values) ------------------------------------
NAVY = "#0C2240"        # primary brand colour
RED = "#C02B2C"         # accent only
CHARCOAL = "#313540"    # body/heading text
WHITE = "#FFFFFF"
LIGHT = "#F4F6F8"       # light neutral background
BORDER = "#D9DEE4"

# Semantic result colours (UI convention; green/red for pass/fail)
PASS_GREEN = "#1E7A46"
FAIL_RED = RED
INSUFFICIENT_GRAY = "#6B7280"

# --- Type ------------------------------------------------------------------
DISPLAY_FONT = "Poppins"                       # headlines (web/PDF)
BODY_FONT_STACK = "'Calibri', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif"

_LOGO_PATH = Path(__file__).resolve().parent / "assets" / "efg_logo.png"


@lru_cache(maxsize=1)
def logo_data_uri() -> str:
    """Return the EFG combined-colour logo as a base64 data URI for self-contained HTML."""
    if not _LOGO_PATH.exists():
        return ""
    data = base64.b64encode(_LOGO_PATH.read_bytes()).decode()
    return f"data:image/png;base64,{data}"
