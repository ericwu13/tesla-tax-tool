#!/usr/bin/env python3
"""
Calculate annual federal + California state tax liability
using W-2, 1099-B, 1098, 1099-INT, and optional rental property data.

Accepts command-line arguments for year and file paths.
"""

from tax_calculator import TaxCalculator
from datetime import datetime
import os
import argparse


def main():
    parser = argparse.ArgumentParser(
        description='Calculate federal and California state tax liability',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage with default file paths (data/w2_2025.csv, etc.)
  python run_annual_taxes.py --year 2025

  # Custom file paths
  python run_annual_taxes.py --year 2025 --w2 mydata/w2.csv --1099b mydata/stocks.csv

  # With rental property (20% rental usage, started March)
  python run_annual_taxes.py --year 2025 --rental-pct 0.20 --rental-income 16000 --rental-start-month 3

  # With estimated payments
  python run_annual_taxes.py --year 2025 --estimated-payments 5000
        """
    )

    # Required arguments
    parser.add_argument('--year', type=int, required=True,
                        help='Tax year (e.g., 2025)')

    # Optional file paths (defaults to data/{form}_{year}.csv)
    parser.add_argument('--w2', type=str,
                        help='Path to W-2 CSV file (default: data/w2_{year}.csv)')
    parser.add_argument('--1099b', type=str,
                        help='Path to 1099-B CSV file (default: data/1099b_{year}.csv)')
    parser.add_argument('--1098', type=str,
                        help='Path to 1098 mortgage CSV file (default: data/1098_{year}.csv)')
    parser.add_argument('--1099int', type=str,
                        help='Path to 1099-INT CSV file (default: data/1099int_{year}.csv)')

    # Optional tax parameters
    parser.add_argument('--estimated-payments', type=float, default=0.0,
                        help='Estimated tax payments made during the year (default: 0)')
    parser.add_argument('--stock-tax-withheld', type=float, default=0.0,
                        help='Federal tax withheld on stock sales (default: 0)')
    parser.add_argument('--st-gains', type=float, default=None,
                        help='Override short-term capital gains directly (skips 1099-B CSV)')
    parser.add_argument('--lt-gains', type=float, default=None,
                        help='Override long-term capital gains directly (skips 1099-B CSV)')

    # Rental property parameters
    parser.add_argument('--rental-pct', type=float, default=0.0,
                        help='Rental usage percentage 0-1 (e.g., 0.20 for 20%%, default: 0)')
    parser.add_argument('--rental-income', type=float, default=0.0,
                        help='Annual rental income received (default: 0)')
    parser.add_argument('--other-rental-income', type=float, default=0.0,
                        help='Other rental income (security deposit interest, etc., default: 0)')
    parser.add_argument('--rental-start-month', type=int, default=1,
                        help='Month rental started 1-12 (default: 1)')
    parser.add_argument('--rental-hoa', type=float, default=0.0,
                        help='Annual HOA fees (default: 0)')
    parser.add_argument('--rental-insurance', type=float, default=0.0,
                        help='Annual homeowner insurance (default: 0)')
    parser.add_argument('--rental-supplies', type=float, default=0.0,
                        help='Rental supplies expense (default: 0)')
    parser.add_argument('--rental-electricity', type=float, default=0.0,
                        help='Annual electricity expense (default: 0)')
    parser.add_argument('--rental-telephone', type=float, default=0.0,
                        help='Annual telephone/internet expense (default: 0)')

    # Output options
    parser.add_argument('--no-print', action='store_true',
                        help='Skip printing data summary (only show final report)')
    parser.add_argument('--output', type=str,
                        help='Save report to specific file (default: outputs/tax_liability_{year}_{timestamp}.txt)')

    args = parser.parse_args()

    # Set default file paths if not provided
    year = args.year
    w2_file = args.w2 or f"data/w2_{year}.csv"
    b1099_file = getattr(args, '1099b') or f"data/1099b_{year}.csv"
    f1098_file = getattr(args, '1098') or f"data/1098_{year}.csv"
    int1099_file = getattr(args, '1099int') or f"data/1099int_{year}.csv"

    # Initialize calculator
    calc = TaxCalculator(tax_year=year)

    # --- Load all tax documents ---
    print(f"Loading tax data for year {year}...")

    try:
        w2 = calc.load_w2_data(w2_file)
    except FileNotFoundError:
        print(f"Error: W-2 file not found: {w2_file}")
        print("Please create the file or specify --w2 path")
        return

    try:
        stock_results = calc.load_1099b_data(b1099_file)
        summary = calc.get_1099b_summary(stock_results)
    except FileNotFoundError:
        print(f"Warning: 1099-B file not found: {b1099_file}")
        print("Continuing without stock sales data...")
        stock_results = []
        summary = {
            'short_term': {'taxable_gain': 0, 'count': 0, 'proceeds': 0, 'cost_basis': 0, 'wash_sale': 0, 'shares': 0},
            'long_term': {'taxable_gain': 0, 'count': 0, 'proceeds': 0, 'cost_basis': 0, 'wash_sale': 0, 'shares': 0},
            'total_count': 0, 'total_proceeds': 0, 'total_cost_basis': 0, 'total_wash_sale': 0, 'total_taxable_gain': 0, 'total_shares': 0
        }

    # Override gains from command line if provided (overrides CSV values)
    if args.st_gains is not None:
        summary['short_term']['taxable_gain'] = args.st_gains
        print(f"  Using --st-gains override: ${args.st_gains:,.2f}")
    if args.lt_gains is not None:
        summary['long_term']['taxable_gain'] = args.lt_gains
        print(f"  Using --lt-gains override: ${args.lt_gains:,.2f}")

    try:
        mortgage = calc.load_1098_data(f1098_file)
    except FileNotFoundError:
        print(f"Warning: 1098 file not found: {f1098_file}")
        print("Continuing without mortgage data...")
        mortgage = {
            'mortgage_interest': 0, 'property_taxes': 0, 'mortgage_insurance': 0, 'purchase_price': 0
        }

    try:
        interest = calc.load_1099int_data(int1099_file)
    except FileNotFoundError:
        print(f"Warning: 1099-INT file not found: {int1099_file}")
        print("Continuing without interest income data...")
        interest = {'payers': [], 'total_interest': 0}

    # --- Print loaded data (unless --no-print) ---
    if not args.no_print:
        print("=" * 80)
        print(f"  {year} FEDERAL + CA TAX LIABILITY")
        print("=" * 80)
        print()
        print("  W-2 DATA:")
        print(f"    Box 1  (Wages):               ${w2['wages']:>14,.2f}")
        print(f"    Box 2  (Fed Tax Withheld):    ${w2['federal_tax_withheld']:>14,.2f}")
        if w2.get('box12d_401k', 0) > 0:
            print(f"    Box 12D (401k):               ${w2['box12d_401k']:>14,.2f}")
        if w2.get('box12w_hsa', 0) > 0:
            print(f"    Box 12W (HSA):                ${w2['box12w_hsa']:>14,.2f}")
        print(f"    State: {w2.get('state', 'N/A')}, Wages: ${w2.get('state_wages', 0):,.2f}, Tax: ${w2.get('state_tax_withheld', 0):,.2f}")
        print()

        if summary['total_count'] > 0:
            print("  1099-B DATA:")
            print(f"    Total Lots:                    {summary['total_count']:>14}")
            print(f"    ST Taxable Gain:              ${summary['short_term']['taxable_gain']:>14,.2f}")
            print(f"    LT Taxable Gain:              ${summary['long_term']['taxable_gain']:>14,.2f}")
            if summary['total_wash_sale'] > 0:
                print(f"    Wash Sale Adjustments:        ${summary['total_wash_sale']:>14,.2f}")
            print()

        if mortgage['mortgage_interest'] > 0 or mortgage['property_taxes'] > 0:
            print("  MORTGAGE / PROPERTY DATA:")
            if mortgage['mortgage_interest'] > 0:
                print(f"    Mortgage Interest (full year): ${mortgage['mortgage_interest']:>14,.2f}")
            if mortgage['property_taxes'] > 0:
                print(f"    Property Taxes (full year):    ${mortgage['property_taxes']:>14,.2f}")
            if mortgage.get('mortgage_insurance', 0) > 0:
                print(f"    Mortgage Insurance:           ${mortgage['mortgage_insurance']:>14,.2f}")
            if mortgage.get('purchase_price', 0) > 0:
                print(f"    Purchase Price:               ${mortgage['purchase_price']:>14,.2f}")
            print()

        if interest['total_interest'] > 0:
            print("  1099-INT DATA:")
            for p in interest['payers']:
                print(f"    {p['payer']:<30}  ${p['interest']:>14,.2f}")
            print(f"    {'Total Interest Income':<30}  ${interest['total_interest']:>14,.2f}")
            print()

        if args.rental_pct > 0:
            print(f"  RENTAL PROPERTY ({args.rental_pct*100:.0f}% of home):")
            print(f"    Rental Income:                ${args.rental_income:>14,.2f}")
            if args.other_rental_income > 0:
                print(f"    Other Income:                 ${args.other_rental_income:>14,.2f}")
            if args.rental_insurance > 0:
                print(f"    Insurance:                    ${args.rental_insurance:>14,.2f}")
            if args.rental_hoa > 0:
                print(f"    HOA:                          ${args.rental_hoa:>14,.2f}")
            if args.rental_supplies > 0:
                print(f"    Supplies:                     ${args.rental_supplies:>14,.2f}")
            if args.rental_electricity > 0:
                print(f"    Electricity:                  ${args.rental_electricity:>14,.2f}")
            if args.rental_telephone > 0:
                print(f"    Telephone:                    ${args.rental_telephone:>14,.2f}")
            print()

    # --- Calculate rental income (Schedule E) ---
    if args.rental_pct > 0:
        rental_result = calc.calculate_rental_income(
            rental_pct=args.rental_pct,
            mortgage_interest=mortgage['mortgage_interest'],
            property_taxes=mortgage['property_taxes'],
            rental_income=args.rental_income,
            other_rental_income=args.other_rental_income,
            mortgage_insurance=mortgage.get('mortgage_insurance', 0),
            hoa=args.rental_hoa,
            insurance=args.rental_insurance,
            supplies=args.rental_supplies,
            electricity=args.rental_electricity,
            telephone=args.rental_telephone,
            home_purchase_price=mortgage.get('purchase_price', 0),
            rental_start_month=args.rental_start_month,
        )
    else:
        rental_result = {'net_rental_income': 0, 'depreciation': 0}

    # --- Classify stock gains ---
    st_gains = summary['short_term']['taxable_gain']
    lt_gains = summary['long_term']['taxable_gain']

    # Rough AGI for mortgage insurance phaseout check
    approx_agi = (w2['wages'] + interest['total_interest'] + st_gains + lt_gains +
                  rental_result['net_rental_income'])

    # --- Calculate itemized deductions (Schedule A) ---
    # CA SDI (Box 14) is deductible as a state/local tax on Schedule A
    state_income_tax_for_salt = w2.get('state_tax_withheld', 0) + w2.get('box14_casdi', 0)
    itemized = calc.calculate_itemized_deductions(
        mortgage_interest=mortgage['mortgage_interest'],
        property_taxes=mortgage['property_taxes'],
        state_income_tax=state_income_tax_for_salt,
        mortgage_insurance=mortgage.get('mortgage_insurance', 0),
        rental_pct=args.rental_pct,
        agi=approx_agi,
    )

    # --- Federal Tax Calculation ---
    liability = calc.calculate_total_tax_liability(
        w2_wages=w2['wages'],
        federal_tax_withheld=w2['federal_tax_withheld'],
        stock_results=stock_results,
        estimated_payments=args.estimated_payments,
        stock_tax_withheld=args.stock_tax_withheld,
        interest_income=interest['total_interest'],
        rental_result=rental_result,
        itemized_result=itemized,
    )

    # --- California State Tax Calculation ---
    ca_personal_mortgage_interest = mortgage['mortgage_interest'] * (1 - args.rental_pct)
    ca_personal_property_taxes = mortgage['property_taxes'] * (1 - args.rental_pct)
    ca_itemized = ca_personal_mortgage_interest + ca_personal_property_taxes

    ca_result = calc.calculate_ca_state_tax(
        w2_state_wages=w2.get('state_wages', w2['wages']),
        interest_income=interest['total_interest'],
        stock_short_term_gains=st_gains,
        stock_long_term_gains=lt_gains,
        net_rental_income=rental_result['net_rental_income'],
        ca_itemized_deductions=ca_itemized,
        state_tax_withheld=w2.get('state_tax_withheld', 0),
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

    if args.output:
        filepath = args.output
    else:
        filename = f"tax_liability_{year}_actual_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        filepath = os.path.join(output_dir, filename)

    with open(filepath, 'w') as f:
        f.write(full_report)
    print(f"\nReport saved to: {filepath}")


if __name__ == '__main__':
    main()
