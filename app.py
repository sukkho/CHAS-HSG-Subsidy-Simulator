import pandas as pd
import streamlit as st

from logic.models import VisitInput, DrugLine
from logic.engine import load_subsidies, load_drugs, calc_chas, calc_hsg, compare

st.set_page_config(page_title="CHAS vs HSG Bill Calculator", layout="wide")

# ---------- Load data (cached) ----------
@st.cache_data
def get_subsidies():
    return load_subsidies("data/subsidies.json")

@st.cache_data
def get_drugs_df():
    return load_drugs("data/drugs.csv")

subs = get_subsidies()
drugs_df = get_drugs_df()

# ---------- UI ----------
st.title("CHAS vs Healthier SG Bill Calculator")
st.markdown(
    "This application simulates patient out-of-pocket costs under CHAS Classic and "
    "Healthier SG Chronic Tier based on configurable subsidy tables."
)

left, right = st.columns(2)

with left:
    st.subheader("Visit Inputs")

    chas_card = st.selectbox(
        "CHAS Card Type",
        ["GREEN", "ORANGE", "BLUE", "MG", "PG"],
        index=2
    )

    hsg_enrolled = st.checkbox("Healthier SG enrolled at clinic?", value=True)

    visit_type = st.selectbox(
        "Visit Type",
        ["acute", "simple_chronic", "complex_chronic"],
        index=1
    )

    st.markdown("### Remaining subsidy balances (simulation)")
    chas_remaining = st.number_input("CHAS remaining annual balance ($)", min_value=0.0, value=320.0, step=10.0)
    hsg_remaining = st.number_input("HSG remaining annual services balance ($)", min_value=0.0, value=210.0, step=10.0)

    st.markdown("### Drugs (up to 10)")
    st.write("Select drugs and quantities. Whitelisted drugs are capped at $0.40 each (before GST/subsidy).")

    # Build an editable table for up to 10 drug lines
    drug_options = drugs_df.reset_index()[["drug_id", "drug_name", "is_whitelisted", "unit_price"]]

    # Pre-fill with 2 lines to help users
    default_rows = pd.DataFrame([
        {"drug_id": "D001", "qty": 30},
        {"drug_id": "D003", "qty": 10},
    ])

    edited = st.data_editor(
        default_rows,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "drug_id": st.column_config.SelectboxColumn(
                "Drug",
                help="Choose a drug",
                options=drug_options["drug_id"].tolist(),
                format_func=lambda x: f"{x} - {drug_options.set_index('drug_id').loc[x]['drug_name']}",
                required=True,
            ),
            "qty": st.column_config.NumberColumn(
                "qty",
                min_value=1,
                step=1,
                required=True,
            ),
        },
        key="drug_editor"
    )

    # Guardrail: limit to 10 rows in UI too
    if len(edited) > 10:
        st.error("Max 10 drugs. Please remove extra rows.")
        st.stop()

    # Convert edited rows -> DrugLine list
    drug_lines = []
    for _, row in edited.dropna().iterrows():
        drug_id = str(row["drug_id"]).strip()
        qty = int(row["qty"])
        drug_lines.append(DrugLine(drug_id=drug_id, qty=qty))

    # Show chosen drug details (optional but helpful)
    if drug_lines:
        chosen_ids = [d.drug_id for d in drug_lines]
        st.markdown("#### Selected drug details")
        st.write(", ".join(
            f"{drug_options.set_index('drug_id').loc[d.drug_id]['drug_name']} (x{d.qty})"
            for d in drug_lines
        ))

with right:
    st.subheader("Results")

    try:
        inp = VisitInput(
            chas_card=chas_card,
            hsg_enrolled=hsg_enrolled,
            visit_type=visit_type,
            chas_remaining_annual=float(chas_remaining),
            hsg_remaining_annual_services=float(hsg_remaining),
            drugs=drug_lines
        )

        chas_bill = calc_chas(inp, subs, drugs_df)
        hsg_bill = calc_hsg(inp, subs, drugs_df)
        winner = compare(chas_bill, hsg_bill)

        # Headline
        difference = abs(chas_bill.patient_payable - hsg_bill.patient_payable)

        if winner == "CHAS":
            st.metric(
                "Better option",
                "CHAS",
                f"${difference:.2f} cheaper"
            )
        else:
            st.metric(
                "Better option",
                "HSG",
                f"${difference:.2f} cheaper"
            )

        # Side-by-side breakdown
        c1, c2 = st.columns(2)

        def breakdown_to_df(b):
            def fmt(x):
                return f"${x:,.2f}"
    
            return pd.DataFrame({
                "Item": [
                    "Consult (pre-GST)",
                    "Whitelisted meds (pre-GST)",
                    "Non-whitelisted meds (pre-GST)",
                    "GST",
                    "Gross total",
                    "Services subsidy",
                    "SDL subsidy",
                    "Total subsidy",
                    "Patient payable",
                    "Remaining annual after",
                ],
                "Amount ($)": [
                    b.consult_before_gst,
                    b.whitelisted_meds_before_gst,
                    b.non_whitelisted_meds_before_gst,
                    b.gst,
                    b.gross_total,
                    b.services_subsidy,
                    b.sdl_subsidy,
                    b.total_subsidy,
                    b.patient_payable,
                    b.remaining_annual_after,
                ]
            })

        with c1:
            st.markdown("### CHAS")
            st.dataframe(
                breakdown_to_df(chas_bill).set_index("Item"),
                use_container_width=True
            )

        with c2:
            st.markdown("### HSG")
            st.dataframe(
                breakdown_to_df(hsg_bill).set_index("Item"),
                use_container_width=True
            )

        st.divider()

        c3, c4 = st.columns(2)

        with c3:
            st.metric("CHAS Patient Payable", f"${chas_bill.patient_payable:.2f}")

        with c4:
            st.metric("HSG Patient Payable", f"${hsg_bill.patient_payable:.2f}")

    except Exception as e:
        st.error(f"Error: {e}")
        st.stop()

        

st.divider()
st.caption("Note: This is a simulation based on subsidy parameters in data/subsidies.json and drug table data/drugs.csv."
           " Calculations include GST and subsidy caps for simulation purposes only.")
