"""
Pydantic data models — the typed contract for the whole service.

Three families:
  1. ExtractedTerms  — what the extraction layer pulls from the lease document.
  2. UserInputs      — the facts the missing-input interview must collect.
  3. Result models   — the structured classification report the API returns.

Field names are deliberately explicit so a non-programmer can read the JSON and
understand what each value means.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Enumerations (closed vocabularies keep extraction honest)
# --------------------------------------------------------------------------- #

class PaymentTiming(str, Enum):
    ADVANCE = "advance"
    ARREARS = "arrears"


class EndOfTermOption(str, Enum):
    DOLLAR_BUYOUT = "dollar_buyout"        # $1 or other nominal fixed price
    FIXED_PRICE = "fixed_price"            # stated non-nominal fixed price
    FMV = "fmv"                            # fair market value purchase
    PUT = "put"                            # lessee obligated to buy
    RENEWAL_ONLY = "renewal_only"
    RETURN_ONLY = "return_only"            # no purchase option; return the asset
    NONE = "none"


class ReportingFramework(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"


# --------------------------------------------------------------------------- #
# 1. Extracted terms
# --------------------------------------------------------------------------- #

class EquipmentItem(BaseModel):
    quantity: Optional[float] = None
    year: Optional[int] = None
    supplier: Optional[str] = None
    description: Optional[str] = None
    serial_number: Optional[str] = None
    cost: Optional[float] = None
    likely_macrs_class: Optional[str] = None


class ExtractedTerms(BaseModel):
    """Classification-relevant terms read from the lease document (Step 1)."""

    document_name: Optional[str] = None
    lessee: Optional[str] = None
    lessor: Optional[str] = None
    lessee_state_of_organization: Optional[str] = None
    equipment_location: Optional[str] = None
    equipment_description: Optional[str] = None

    total_equipment_cost: Optional[float] = None
    down_payment: Optional[float] = None
    finance_amount: Optional[float] = None
    security_deposit: Optional[float] = None

    lease_term_months: Optional[int] = None
    commencement_date: Optional[str] = None
    expiration_date: Optional[str] = None
    payment_amount: Optional[float] = None
    payment_frequency: Optional[str] = "monthly"
    payment_timing: Optional[PaymentTiming] = None

    end_of_term_option: Optional[EndOfTermOption] = None
    purchase_option_price: Optional[float] = None
    automatic_ownership_transfer: Optional[bool] = None
    renewal_terms: Optional[str] = None
    early_termination_rights: Optional[str] = None

    non_cancellable: Optional[bool] = None
    hell_or_high_water: Optional[bool] = None
    risk_of_loss: Optional[str] = None
    insurance_responsibility: Optional[str] = None
    property_tax_responsibility: Optional[str] = None
    maintenance_responsibility: Optional[str] = None
    assignment_terms: Optional[str] = None
    residual_guarantee: Optional[str] = None
    stipulated_loss_value: Optional[str] = None
    default_remedy: Optional[str] = None

    governing_law_state: Optional[str] = None
    stated_index_rate: Optional[float] = Field(
        None, description="Stated pricing index in the doc as a decimal, e.g. 0.0397"
    )

    equipment_schedule: list[EquipmentItem] = Field(default_factory=list)

    # Free-form provenance: field name -> section/page it came from
    source_sections: dict[str, str] = Field(default_factory=dict)
    # Fields the extractor could not determine from the document
    undetermined_fields: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# 2. User-supplied inputs (Step 2 missing-input interview)
# --------------------------------------------------------------------------- #

class UserInputs(BaseModel):
    """Facts required by the three tracks that a lease document rarely states."""

    fair_market_value_at_inception: Optional[float] = Field(
        None, description="Defaults to total equipment cost if not provided."
    )
    economic_useful_life_years: Optional[float] = None
    lessor_cost_basis: Optional[float] = None
    estimated_end_of_term_fmv: Optional[float] = None
    discount_rate_for_pv_test: Optional[float] = Field(
        None, description="Decimal. Defaults to the solved implicit yield."
    )
    macrs_class_life_years: Optional[float] = None
    lessor_has_residual_value_insurance: Optional[bool] = None
    reporting_framework: Optional[ReportingFramework] = None


# --------------------------------------------------------------------------- #
# 3. Classification request / response
# --------------------------------------------------------------------------- #

class ClassifyRequest(BaseModel):
    """Classify from already-extracted terms plus user inputs.

    Use this when the CRM already holds the structured terms, or when you want
    to run the deterministic engine without the extraction/LLM step.
    """

    terms: ExtractedTerms
    user_inputs: UserInputs = Field(default_factory=UserInputs)


class CriterionOut(BaseModel):
    number: int
    name: str
    input_value: str
    threshold: str
    result: str
    confidence: str
    analysis: str = ""


class TrackOut(BaseModel):
    regime: str
    verdict: str
    confidence: str
    criteria: list[CriterionOut] = Field(default_factory=list)
    citations: list[dict] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class TraceabilityRow(BaseModel):
    fact: str
    gaap_triggered: str = ""
    tax_triggered: str = ""
    ucc_triggered: str = ""
    dispositive: str = ""


class SolvedEconomicsOut(BaseModel):
    stated_index_rate: Optional[float] = None
    solved_implicit_yield: float
    undiscounted_total_payments: float
    pv_percent_at_rate: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ExecutiveSummaryRow(BaseModel):
    regime: str
    verdict: str
    confidence: str


class ClassificationReport(BaseModel):
    """The full structured report — the primary API output."""

    document: Optional[str] = None
    lessee: Optional[str] = None
    lessor: Optional[str] = None
    lease_date_term_cost: Optional[str] = None
    governing_law: Optional[str] = None
    date_of_analysis: Optional[str] = None
    analyst: str = "EFG Lease Classifier v1.1"

    executive_summary: list[ExecutiveSummaryRow] = Field(default_factory=list)
    cross_regime_alignment: str = ""

    extracted_terms: ExtractedTerms
    user_inputs: UserInputs
    solved_economics: SolvedEconomicsOut
    traceability_matrix: list[TraceabilityRow] = Field(default_factory=list)

    gaap: TrackOut
    tax: TrackOut
    ucc: TrackOut

    flagged_ambiguities: list[str] = Field(default_factory=list)
    authorities_cited: list[str] = Field(default_factory=list)
    governance_notes: list[str] = Field(default_factory=list)
