from dataclasses import dataclass
from typing import List, Literal

CardType = Literal["GREEN", "ORANGE", "BLUE", "MG", "PG"]
VisitType = Literal["acute", "simple_chronic", "complex_chronic"]

@dataclass(frozen=True)
class DrugLine:
    drug_id: str
    qty: int

@dataclass(frozen=True)
class VisitInput:
    chas_card: CardType
    hsg_enrolled: bool
    visit_type: VisitType
    chas_remaining_annual: float
    hsg_remaining_annual_services: float
    drugs: List[DrugLine]

@dataclass(frozen=True)
class BillBreakdown:
    scheme: Literal["CHAS", "HSG"]

    consult_before_gst: float
    whitelisted_meds_before_gst: float
    non_whitelisted_meds_before_gst: float

    gst: float
    gross_total: float

    services_subsidy: float      # for CHAS: capped subsidy (eligible portion)
    sdl_subsidy: float           # for CHAS: 0; for HSG: % subsidy on whitelisted
    total_subsidy: float

    patient_payable: float

    remaining_annual_after: float