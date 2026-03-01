import json
import pandas as pd
from .models import VisitInput, BillBreakdown

WHITELISTED_PRICE_CAP = 0.40

def money(x: float) -> float:
    return round(float(x) + 1e-9, 2)

def load_subsidies(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_drugs(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["is_whitelisted"] = df["is_whitelisted"].astype(int)
    return df.set_index("drug_id")

def _compute_meds_total(drugs_df, lines):
    wl = 0.0
    nwl = 0.0

    for line in lines:
        row = drugs_df.loc[line.drug_id]
        is_wl = int(row["is_whitelisted"]) == 1

        if is_wl:
            unit_price = WHITELISTED_PRICE_CAP
            wl += unit_price * line.qty
        else:
            unit_price = float(row["unit_price"])
            nwl += unit_price * line.qty

    return wl, nwl, wl + nwl

def _apply_capped_subsidy(eligible_amount, per_visit_cap, remaining_annual):
    return max(0.0, min(eligible_amount, per_visit_cap, remaining_annual))

def _validate_input(inp: VisitInput):
    if len(inp.drugs) > 10:
        raise ValueError("Max 10 drugs per visit.")

    for d in inp.drugs:
        if d.qty <= 0:
            raise ValueError("Drug quantity must be positive.")
        
def calc_chas(inp: VisitInput, subsidies, drugs_df) -> BillBreakdown:
    _validate_input(inp)

    gst_rate = float(subsidies["gst_rate"])
    consult_fee = float(subsidies["consult_fees"][inp.visit_type])

    wl, nwl, meds_total = _compute_meds_total(drugs_df, inp.drugs)

    eligible_pre_gst = consult_fee + wl
    ineligible_pre_gst = nwl

    gst = money((eligible_pre_gst + ineligible_pre_gst) * gst_rate)
    gross = money(eligible_pre_gst + ineligible_pre_gst + gst)

    card = subsidies["chas"][inp.chas_card]
    if inp.visit_type == "acute":
        per_visit_cap = float(card["acute_per_visit"])
    elif inp.visit_type == "simple_chronic":
        per_visit_cap = float(card["simple"]["per_visit"])
    else:
        per_visit_cap = float(card["complex"]["per_visit"])

    eligible_with_gst = eligible_pre_gst + (eligible_pre_gst * gst_rate)

    services_subsidy = money(_apply_capped_subsidy(
        eligible_amount=eligible_with_gst,
        per_visit_cap=per_visit_cap,
        remaining_annual=inp.chas_remaining_annual
    ))

    remaining_after = money(max(0.0, inp.chas_remaining_annual - services_subsidy))

    patient = money(max(0.0, gross - services_subsidy))

    return BillBreakdown(
        scheme="CHAS",
        consult_before_gst=consult_fee,
        whitelisted_meds_before_gst=wl,
        non_whitelisted_meds_before_gst=nwl,
        gst=gst,
        gross_total=gross,
        services_subsidy=services_subsidy,
        sdl_subsidy=0.0,
        total_subsidy=services_subsidy,
        patient_payable=patient,
        remaining_annual_after=remaining_after
    )

def calc_hsg(inp: VisitInput, subsidies, drugs_df) -> BillBreakdown:
    _validate_input(inp)
    
    # If not enrolled, treat as not eligible => return CHAS (simple fallback)
    if not inp.hsg_enrolled:
        return calc_chas(inp, subsidies, drugs_df)

    gst_rate = float(subsidies["gst_rate"])
    consult_fee = float(subsidies["consult_fees"][inp.visit_type])

    wl, nwl, meds_total = _compute_meds_total(drugs_df, inp.drugs)
    card = subsidies["hsg"][inp.chas_card]

    services_base = consult_fee + nwl
    wl_base = wl

    # GST: assume whitelisted (selected chronic meds) are GST-exempt under HSG
    gst = money(services_base * gst_rate)
    gross = money(services_base + wl_base + gst)

    if inp.visit_type == "simple_chronic":
        per_visit = float(card["services"]["simple"]["per_visit"])
    elif inp.visit_type == "complex_chronic":
        per_visit = float(card["services"]["complex"]["per_visit"])
    else:
        per_visit = 0.0

    # capped subsidy on services component (no GST included in cap for simplicity)
    services_subsidy = money(_apply_capped_subsidy(
        eligible_amount=services_base,
        per_visit_cap=per_visit,
        remaining_annual=inp.hsg_remaining_annual_services
    ))

    remaining_after = money(max(0.0, inp.hsg_remaining_annual_services - services_subsidy))

    sdl_percent = float(card["sdl_percent"])
    sdl_subsidy = wl_base * sdl_percent  # no cap

    total_subsidy = services_subsidy + sdl_subsidy
    patient = money(max(0.0, gross - total_subsidy))

    return BillBreakdown(
        scheme="HSG",
        consult_before_gst=consult_fee,
        whitelisted_meds_before_gst=wl,
        non_whitelisted_meds_before_gst=nwl,
        gst=gst,
        gross_total=gross,
        services_subsidy=services_subsidy,
        sdl_subsidy=sdl_subsidy,
        total_subsidy=total_subsidy,
        patient_payable=patient,
        remaining_annual_after=remaining_after
    )

def compare(chas_bill: BillBreakdown, hsg_bill: BillBreakdown) -> str:
    return "HSG" if hsg_bill.patient_payable < chas_bill.patient_payable else "CHAS"
