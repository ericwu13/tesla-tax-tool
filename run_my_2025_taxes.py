#!/usr/bin/env python3
"""
Calculate actual 2025 federal + California state tax liability
using real W-2, 1099-B, 1098, 1099-INT, and rental property data.
"""

from tax_calculator import TaxCalculator
from datetime import datetime
import os

calc = TaxCalculator(tax_year=2025)

# --- Load all tax documents ---
w2 = calc.load_w2_data("data/w2_2025.csv")
stock_results = calc.load_1099b_data("data/1099b_2025.csv")
summary = calc.get_1099b_summary(stock_results)
mortgage = calc.load_1098_data("data/1098_2025.csv")
interest = calc.load_1099int_data("data/1099int_2025.csv")

# --- Rental property data (from rental spreadsheet) ---
RENTAL_PCT = 0.20  # 20% rental usage
RENTAL_INCOME = 16000.00       # $1,600/mo x 10 months (Mar-Dec)
OTHER_RENTAL_INCOME = 263.85   # Security deposit interest, etc.
# Full-year expenses (from spreadsheet - will be multiplied by rental_pct)
INSURANCE = 1088.00
SUPPLIES = 463.17
ELECTRICITY = 946.93
TELEPHONE = 630.00

# --- Print loaded data ---
print("=" * 80)
print("  2025 FEDERAL + CA TAX LIABILITY - ACTUAL DATA")
print("=" * 80)
print()
print("  W-2 DATA (Tesla):")
print(f"    Box 1  (Wages):               ${w2['wages']:>14,.2f}")
print(f"    Box 2  (Fed Tax Withheld):    ${w2['federal_tax_withheld']:>14,.2f}")
print(f"    Box 12D (401k):               ${w2['box12d_401k']:>14,.2f}")
print(f"    Box 12W (HSA):                ${w2['box12w_hsa']:>14,.2f}")
print(f"    State: {w2['state']}, Wages: ${w2['state_wages']:,.2f}, Tax: ${w2['state_tax_withheld']:,.2f}")
print()
print("  1099-B DATA (E*Trade):")
print(f"    Total Lots:                    {summary['total_count']:>14}")
print(f"    ST Taxable Gain:              ${summary['short_term']['taxable_gain']:>14,.2f}")
print(f"    LT Taxable Gain:              ${summary['long_term']['taxable_gain']:>14,.2f}")
if summary['total_wash_sale'] > 0:
    print(f"    Wash Sale Adjustments:        ${summary['total_wash_sale']:>14,.2f}")
print()
print("  MORTGAGE / PROPERTY DATA:")
print(f"    Mortgage Interest (full year): ${mortgage['mortgage_interest']:>14,.2f}")
print(f"    Property Taxes (full year):    ${mortgage['property_taxes']:>14,.2f}")
print(f"    Mortgage Insurance:           ${mortgage['mortgage_insurance']:>14,.2f}")
print(f"    Purchase Price:               ${mortgage['purchase_price']:>14,.2f}")
print()
print("  1099-INT DATA:")
for p in interest['payers']:
    print(f"    {p['payer']:<30}  ${p['interest']:>14,.2f}")
print(f"    {'Total Interest Income':<30}  ${interest['total_interest']:>14,.2f}")
print()
print(f"  RENTAL PROPERTY (20% of home):")
print(f"    Rental Income (10 months):    ${RENTAL_INCOME:>14,.2f}")
print(f"    Other Income:                 ${OTHER_RENTAL_INCOME:>14,.2f}")
print(f"    Insurance:                    ${INSURANCE:>14,.2f}")
print(f"    HOA:                          ${4778.96:>14,.2f}")
print(f"    Supplies:                     ${SUPPLIES:>14,.2f}")
print(f"    Electricity:                  ${ELECTRICITY:>14,.2f}")
print(f"    Telephone:                    ${TELEPHONE:>14,.2f}")
print()

# --- Calculate rental income (Schedule E) ---
rental_result = calc.calculate_rental_income(
    rental_pct=RENTAL_PCT,
    mortgage_interest=mortgage['mortgage_interest'],
    property_taxes=mortgage['property_taxes'],
    rental_income=RENTAL_INCOME,
    other_rental_income=OTHER_RENTAL_INCOME,
    mortgage_insurance=mortgage['mortgage_insurance'],
    hoa=4778.96,             # Annual HOA from spreadsheet
    insurance=INSURANCE,
    supplies=SUPPLIES,
    electricity=ELECTRICITY,
    telephone=TELEPHONE,
    home_purchase_price=mortgage['purchase_price'],
    rental_start_month=3,    # Rental started March 2025
)

# --- Classify stock gains ---
st_gains = summary['short_term']['taxable_gain']
lt_gains = summary['long_term']['taxable_gain']

# Rough AGI for mortgage insurance phaseout check
approx_agi = (w2['wages'] + interest['total_interest'] + st_gains + lt_gains +
              rental_result['net_rental_income'])

# --- Calculate itemized deductions (Schedule A) ---
# CA SDI (Box 14) is deductible as a state/local tax on Schedule A
state_income_tax_for_salt = w2['state_tax_withheld'] + w2.get('box14_casdi', 0)
itemized = calc.calculate_itemized_deductions(
    mortgage_interest=mortgage['mortgage_interest'],
    property_taxes=mortgage['property_taxes'],
    state_income_tax=state_income_tax_for_salt,
    mortgage_insurance=mortgage['mortgage_insurance'],
    rental_pct=RENTAL_PCT,
    agi=approx_agi,
)

# --- Federal Tax Calculation ---
liability = calc.calculate_total_tax_liability(
    w2_wages=w2['wages'],
    federal_tax_withheld=w2['federal_tax_withheld'],
    stock_results=stock_results,
    estimated_payments=0.0,
    stock_tax_withheld=0.0,
    interest_income=interest['total_interest'],
    rental_result=rental_result,
    itemized_result=itemized,
)

# --- California State Tax Calculation ---
# CA itemized: mortgage interest (personal portion) + property taxes (personal portion)
# CA does NOT cap SALT, but state income tax is NOT deductible on CA return
ca_personal_mortgage_interest = mortgage['mortgage_interest'] * (1 - RENTAL_PCT)
ca_personal_property_taxes = mortgage['property_taxes'] * (1 - RENTAL_PCT)
ca_itemized = ca_personal_mortgage_interest + ca_personal_property_taxes

ca_result = calc.calculate_ca_state_tax(
    w2_state_wages=w2['state_wages'],
    interest_income=interest['total_interest'],
    stock_short_term_gains=st_gains,
    stock_long_term_gains=lt_gains,
    net_rental_income=rental_result['net_rental_income'],
    ca_itemized_deductions=ca_itemized,
    state_tax_withheld=w2['state_tax_withheld'],
    ca_sdi_withheld=w2.get('box14_casdi', 0),
)

# --- Generate and print reports ---
federal_report = calc.generate_tax_liability_report(liability, stock_results)
ca_report = calc.generate_ca_tax_report_section(ca_result)

# Combined summary
combined_lines = []
combined_lines.append(federal_report)
combined_lines.append(ca_report)

# Grand total
combined_lines.append("=" * 80)
combined_lines.append("  COMBINED FEDERAL + CALIFORNIA SUMMARY")
combined_lines.append("=" * 80)
combined_lines.append("")
combined_lines.append(f"    Federal Tax Liability:                       ${liability['total_tax_liability']:>14,.2f}")
combined_lines.append(f"    California Tax Liability:                     ${ca_result['ca_tax']:>14,.2f}")
combined_lines.append(f"                                                 {'':>3}{'-' * 14}")
total_tax = liability['total_tax_liability'] + ca_result['ca_tax']
combined_lines.append(f"    TOTAL TAX LIABILITY (Fed + CA):               ${total_tax:>14,.2f}")
combined_lines.append("")
total_withheld = liability['federal_tax_withheld'] + ca_result['ca_state_tax_withheld']
combined_lines.append(f"    Total Federal Withheld:                     (${liability['federal_tax_withheld']:>13,.2f})")
combined_lines.append(f"    Total CA State Withheld:                    (${ca_result['ca_state_tax_withheld']:>13,.2f})")
combined_lines.append(f"                                                 {'':>3}{'-' * 14}")
combined_lines.append(f"    Total Withheld:                             (${total_withheld:>13,.2f})")
combined_lines.append("")
net_owed = (liability['net_tax_due'] - liability['refund']) + (ca_result['ca_net_tax_due'] - ca_result['ca_refund'])
if net_owed > 0:
    combined_lines.append(f"    Federal Net Due:                              ${liability['net_tax_due']:>14,.2f}")
    if ca_result['ca_net_tax_due'] > 0:
        combined_lines.append(f"    CA Net Due:                                   ${ca_result['ca_net_tax_due']:>14,.2f}")
    else:
        combined_lines.append(f"    CA Refund:                                   (${ca_result['ca_refund']:>13,.2f})")
    combined_lines.append(f"                                                 {'':>3}{'=' * 14}")
    combined_lines.append(f"    TOTAL NET OWED:                              ${net_owed:>14,.2f}")
elif net_owed < 0:
    if liability['refund'] > 0:
        combined_lines.append(f"    Federal Refund:                              (${liability['refund']:>13,.2f})")
    else:
        combined_lines.append(f"    Federal Net Due:                              ${liability['net_tax_due']:>14,.2f}")
    if ca_result['ca_refund'] > 0:
        combined_lines.append(f"    CA Refund:                                   (${ca_result['ca_refund']:>13,.2f})")
    else:
        combined_lines.append(f"    CA Net Due:                                   ${ca_result['ca_net_tax_due']:>14,.2f}")
    combined_lines.append(f"                                                 {'':>3}{'=' * 14}")
    combined_lines.append(f"    TOTAL NET REFUND:                            ${abs(net_owed):>14,.2f}")
else:
    combined_lines.append(f"    EXACTLY EVEN - No tax due and no refund.")
combined_lines.append("")
agi = liability['agi']
combined_lines.append(f"    Combined Effective Rate (Fed + CA):           {(total_tax / agi * 100):>13.1f}%")
combined_lines.append("=" * 80)

full_report = "\n".join(combined_lines)
print(full_report)

# --- Save report ---
output_dir = "outputs"
os.makedirs(output_dir, exist_ok=True)
filename = f"tax_liability_2025_actual_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
filepath = os.path.join(output_dir, filename)
with open(filepath, 'w') as f:
    f.write(full_report)
print(f"\nReport saved to: {filepath}")
