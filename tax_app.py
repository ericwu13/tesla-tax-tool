"""
Tax App — Main CLI entry point.

Scan PDF/image tax forms (W-2, 1099-B, 1099-INT, 1098), calculate federal + CA
taxes for any filing status, and generate a comprehensive report.

Usage:
    python tax_app.py w2.pdf 1099b.pdf 1098.pdf --status mfj
    python tax_app.py --forms-dir ./my-forms/ --status single --interactive
    python tax_app.py w2.pdf --estimated-payments 5000 --output report.txt
"""

import argparse
import os
import sys
from datetime import datetime

from form_scanner import scan_form_multi
from tax_calculator import TaxCalculator


def discover_files(paths: list, forms_dir: str = None) -> list:
    """Collect PDF/image file paths from arguments and optional directory."""
    files = []
    supported_ext = {'.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp'}

    # Files passed as positional arguments
    for p in (paths or []):
        if os.path.isfile(p):
            files.append(p)
        else:
            print(f"Warning: File not found, skipping: {p}")

    # Files from --forms-dir
    if forms_dir and os.path.isdir(forms_dir):
        for name in sorted(os.listdir(forms_dir)):
            ext = os.path.splitext(name)[1].lower()
            if ext in supported_ext:
                files.append(os.path.join(forms_dir, name))

    return files


def display_extracted_data(form_type: str, data, source: str):
    """Pretty-print extracted data for review."""
    print(f"\n{'─' * 60}")
    print(f"  Form: {form_type}  |  Source: {os.path.basename(source)}")
    print(f"{'─' * 60}")

    if form_type == 'W-2':
        print(f"  Employer:             {data.get('employer', 'N/A')}")
        print(f"  Wages (Box 1):        ${data.get('wages', 0):>12,.2f}")
        print(f"  Fed Withheld (Box 2): ${data.get('federal_tax_withheld', 0):>12,.2f}")
        print(f"  SS Wages (Box 3):     ${data.get('ss_wages', 0):>12,.2f}")
        print(f"  Medicare Wages (5):   ${data.get('medicare_wages', 0):>12,.2f}")
        if data.get('box12d_401k', 0) > 0:
            print(f"  401(k) (12-D):        ${data['box12d_401k']:>12,.2f}")
        if data.get('box12w_hsa', 0) > 0:
            print(f"  HSA (12-W):           ${data['box12w_hsa']:>12,.2f}")
        print(f"  State:                {data.get('state', 'N/A')}")
        print(f"  State Wages (Box 16): ${data.get('state_wages', 0):>12,.2f}")
        print(f"  State Tax (Box 17):   ${data.get('state_tax_withheld', 0):>12,.2f}")

    elif form_type == '1099-B':
        if isinstance(data, list):
            print(f"  Transactions: {len(data)}")
            st = [t for t in data if not t.get('is_long_term')]
            lt = [t for t in data if t.get('is_long_term')]
            st_gain = sum(t.get('total_gain', 0) for t in st)
            lt_gain = sum(t.get('total_gain', 0) for t in lt)
            print(f"  Short-term ({len(st)} lots):  ${st_gain:>12,.2f}")
            print(f"  Long-term  ({len(lt)} lots):  ${lt_gain:>12,.2f}")
            print(f"  Total gain/loss:      ${st_gain + lt_gain:>12,.2f}")
        else:
            print(f"  Data: {data}")

    elif form_type == '1099-INT':
        print(f"  Total Interest:       ${data.get('total_interest', 0):>12,.2f}")
        for p in data.get('payers', []):
            print(f"    {p.get('payer', 'Unknown')}: ${p.get('interest', 0):>10,.2f}")

    elif form_type == '1098':
        print(f"  Lender:               {data.get('lender', 'N/A')}")
        print(f"  Mortgage Interest:    ${data.get('mortgage_interest', 0):>12,.2f}")
        print(f"  Outstanding Balance:  ${data.get('outstanding_principal', 0):>12,.2f}")
        print(f"  Mortgage Insurance:   ${data.get('mortgage_insurance', 0):>12,.2f}")
        print(f"  Property Taxes:       ${data.get('property_taxes', 0):>12,.2f}")

    else:
        print(f"  (Unrecognized form type)")


def prompt_correction(field: str, current_value, expected_type=float):
    """Prompt user to confirm or correct a value in interactive mode."""
    user_input = input(f"  {field} [{current_value}]: ").strip()
    if not user_input:
        return current_value
    try:
        return expected_type(user_input.replace('$', '').replace(',', ''))
    except (ValueError, TypeError):
        print(f"  Invalid input, keeping: {current_value}")
        return current_value


def interactive_review(form_type: str, data):
    """Let user review and correct extracted values."""
    print(f"\n  Review extracted values (press Enter to keep, or type new value):")
    if form_type == 'W-2':
        data['wages'] = prompt_correction('Wages (Box 1)', data.get('wages', 0))
        data['federal_tax_withheld'] = prompt_correction('Fed Withheld (Box 2)', data.get('federal_tax_withheld', 0))
        data['state_wages'] = prompt_correction('State Wages (Box 16)', data.get('state_wages', 0))
        data['state_tax_withheld'] = prompt_correction('State Tax (Box 17)', data.get('state_tax_withheld', 0))
    elif form_type == '1099-INT':
        data['total_interest'] = prompt_correction('Total Interest', data.get('total_interest', 0))
    elif form_type == '1098':
        data['mortgage_interest'] = prompt_correction('Mortgage Interest', data.get('mortgage_interest', 0))
        data['property_taxes'] = prompt_correction('Property Taxes', data.get('property_taxes', 0))
        data['mortgage_insurance'] = prompt_correction('Mortgage Insurance', data.get('mortgage_insurance', 0))
    return data


def build_tax_inputs(scanned_forms: list) -> dict:
    """Aggregate scanned form data into inputs for TaxCalculator."""
    w2_wages = 0.0
    fed_withheld = 0.0
    state_wages = 0.0
    state_tax_withheld = 0.0
    interest_income = 0.0
    mortgage_interest = 0.0
    property_taxes = 0.0
    mortgage_insurance = 0.0
    stock_results = []

    for form in scanned_forms:
        ft = form['form_type']
        data = form['data']

        if ft == 'W-2':
            w2_wages += data.get('wages', 0)
            fed_withheld += data.get('federal_tax_withheld', 0)
            state_wages += data.get('state_wages', 0)
            state_tax_withheld += data.get('state_tax_withheld', 0)

        elif ft == '1099-B':
            if isinstance(data, list):
                stock_results.extend(data)

        elif ft == '1099-INT':
            interest_income += data.get('total_interest', 0)

        elif ft == '1098':
            mortgage_interest += data.get('mortgage_interest', 0)
            property_taxes += data.get('property_taxes', 0)
            mortgage_insurance += data.get('mortgage_insurance', 0)

    return {
        'w2_wages': w2_wages,
        'fed_withheld': fed_withheld,
        'state_wages': state_wages,
        'state_tax_withheld': state_tax_withheld,
        'interest_income': interest_income,
        'mortgage_interest': mortgage_interest,
        'property_taxes': property_taxes,
        'mortgage_insurance': mortgage_insurance,
        'stock_results': stock_results,
    }


def main():
    parser = argparse.ArgumentParser(
        description='Tax App — Scan tax forms and calculate federal + CA taxes',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tax_app.py w2.pdf 1099b.pdf 1098.pdf --status mfj
  python tax_app.py --forms-dir ./my-forms/ --status single --interactive
  python tax_app.py w2.pdf --estimated-payments 5000 --output report.txt
        """,
    )
    parser.add_argument('files', nargs='*', help='PDF or image files to scan')
    parser.add_argument('--status', default='single',
                        choices=['single', 'mfj', 'mfs', 'hoh'],
                        help='Filing status (default: single)')
    parser.add_argument('--year', type=int, default=None,
                        help='Tax year (default: current year)')
    parser.add_argument('--forms-dir', help='Directory of PDF forms to scan')
    parser.add_argument('--output', help='Save report to file')
    parser.add_argument('--estimated-payments', type=float, default=0,
                        help='Quarterly estimated payments made')
    parser.add_argument('--interactive', action='store_true',
                        help='Review/correct extracted values before calculating')

    args = parser.parse_args()

    # Discover files
    files = discover_files(args.files, args.forms_dir)
    if not files:
        print("No files provided. Use positional args or --forms-dir.")
        print("Run with --help for usage.")
        sys.exit(1)

    tax_year = args.year or datetime.now().year

    # Step 1: Scan all forms
    print(f"\n{'=' * 60}")
    print(f"  TAX APP — Scanning {len(files)} file(s) for tax year {tax_year}")
    print(f"  Filing Status: {args.status.upper()}")
    print(f"{'=' * 60}")

    scanned = []
    for f in files:
        print(f"\nScanning: {f}")
        try:
            results = scan_form_multi(f, tax_year=tax_year)
            for result in results:
                display_extracted_data(result['form_type'], result['data'], f)

                if args.interactive and result['form_type'] != 'unknown':
                    result['data'] = interactive_review(result['form_type'], result['data'])

                scanned.append(result)
        except Exception as e:
            print(f"  Error scanning {f}: {e}")

    if not scanned:
        print("\nNo forms could be scanned. Check file paths and formats.")
        sys.exit(1)

    # Step 2: Aggregate inputs
    inputs = build_tax_inputs(scanned)

    print(f"\n{'=' * 60}")
    print(f"  AGGREGATED TAX DATA")
    print(f"{'=' * 60}")
    print(f"  W-2 Wages:            ${inputs['w2_wages']:>12,.2f}")
    print(f"  Federal Withheld:     ${inputs['fed_withheld']:>12,.2f}")
    print(f"  Interest Income:      ${inputs['interest_income']:>12,.2f}")
    print(f"  Stock Transactions:   {len(inputs['stock_results'])}")
    print(f"  Mortgage Interest:    ${inputs['mortgage_interest']:>12,.2f}")
    print(f"  Property Taxes:       ${inputs['property_taxes']:>12,.2f}")

    # Step 3: Calculate taxes
    calc = TaxCalculator(tax_year=tax_year, filing_status=args.status)

    # Build itemized deductions if we have 1098 data
    stock_gains = sum(r.get('total_gain', 0) for r in inputs['stock_results'])
    estimated_agi = inputs['w2_wages'] + inputs['interest_income'] + stock_gains

    itemized_result = None
    if (inputs['mortgage_interest'] > 0 or inputs['property_taxes'] > 0
            or inputs['state_tax_withheld'] > 0):
        itemized_result = calc.calculate_itemized_deductions(
            mortgage_interest=inputs['mortgage_interest'],
            property_taxes=inputs['property_taxes'],
            state_income_tax=inputs['state_tax_withheld'],
            mortgage_insurance=inputs['mortgage_insurance'],
            agi=estimated_agi,
        )

    # Federal tax liability
    liability = calc.calculate_total_tax_liability(
        w2_wages=inputs['w2_wages'],
        federal_tax_withheld=inputs['fed_withheld'],
        stock_results=inputs['stock_results'],
        estimated_payments=args.estimated_payments,
        interest_income=inputs['interest_income'],
        itemized_result=itemized_result,
    )

    # Step 4: Generate report
    report = calc.generate_tax_liability_report(liability, inputs['stock_results'])

    # CA state tax (if state wages exist)
    ca_report = ''
    if inputs['state_wages'] > 0:
        st_gains = sum(
            r.get('total_gain', 0) for r in inputs['stock_results']
            if not r.get('is_long_term', False)
        )
        lt_gains = sum(
            r.get('total_gain', 0) for r in inputs['stock_results']
            if r.get('is_long_term', False)
        )
        ca_itemized = None
        if inputs['mortgage_interest'] > 0 or inputs['property_taxes'] > 0:
            # CA doesn't allow SALT; just mortgage interest + property taxes
            ca_itemized = inputs['mortgage_interest'] + inputs['property_taxes']

        ca_result = calc.calculate_ca_state_tax(
            w2_state_wages=inputs['state_wages'],
            interest_income=inputs['interest_income'],
            stock_short_term_gains=st_gains,
            stock_long_term_gains=lt_gains,
            ca_itemized_deductions=ca_itemized,
            state_tax_withheld=inputs['state_tax_withheld'],
        )
        ca_report = calc.generate_ca_tax_report_section(ca_result)

    full_report = report + ca_report

    # Output
    if args.output:
        os.makedirs('outputs', exist_ok=True)
        output_path = os.path.join('outputs', args.output)
        with open(output_path, 'w') as f:
            f.write(full_report)
        print(f"\nReport saved to: {output_path}")
    else:
        print(full_report)

    # Summary line
    if liability['net_tax_due'] > 0:
        print(f"\n  >>> FEDERAL TAX DUE: ${liability['net_tax_due']:,.2f}")
    else:
        print(f"\n  >>> FEDERAL REFUND: ${liability['refund']:,.2f}")


if __name__ == '__main__':
    main()
