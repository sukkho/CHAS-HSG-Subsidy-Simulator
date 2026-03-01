from logic.models import VisitInput, DrugLine
from logic.engine import load_subsidies, load_drugs, calc_chas, calc_hsg, compare

subs = load_subsidies("data/subsidies.json")
drugs = load_drugs("data/drugs.csv")

inp = VisitInput(
    chas_card="BLUE",
    hsg_enrolled=True,
    visit_type="simple_chronic",
    chas_remaining_annual=320,
    hsg_remaining_annual_services=210,
    drugs=[
        DrugLine("D001", 30),
        DrugLine("D003", 10),
    ],
)

chas = calc_chas(inp, subs, drugs)
hsg = calc_hsg(inp, subs, drugs)

print("\n--- CHAS ---")
print(chas)
print("\n--- HSG ---")
print(hsg)
print("\nBetter:", compare(chas, hsg))
