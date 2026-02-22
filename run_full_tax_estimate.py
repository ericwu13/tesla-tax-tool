#!/usr/bin/env python3
"""
Full Federal Income Tax Liability Estimator
Calculates total tax liability including W-2 income and stock sales.
Supports W-2 CSV import, 1099-B CSV import, and stock holdings CSV.
"""

from tax_calculator import TaxCalculator
from datetime import datetime
import os


def get_currency_input(prompt: str, default: float = None) -> float:
    """Get a currency amount from user input."""
    if default is not None:
        prompt = f"{prompt} (default ${default:,.2f}): "
    raw = input(prompt).strip().replace(",", "").replace("$", "")
    if not raw and default is not None:
        return default
    return float(raw)


def main():
    print("=" * 60)
    print(f"  FEDERAL INCOME TAX LIABILITY ESTIMATOR")
    print("=" * 60)
    print()

    try:
        # Determine tax year
        current_year = __import__('datetime').datetime.now().year
        default_year = current_year - 1 if current_year > 2025 else current_year
        year_input = input(
            f"Tax year (default {default_year}): "
        ).strip()
        tax_year = int(year_input) if year_input else default_year

        # Create calculator for the specified tax year
        calculator = TaxCalculator(tax_year=tax_year)
        print()

        # --- W-2 Information ---
        print(f"--- W-2 Information ({tax_year}) ---")
        print("  Input options:")
        print("  [1] Load from W-2 CSV file")
        print("  [2] Enter manually")
        w2_choice = input("  Choose (1/2, default 1): ").strip()
        if not w2_choice:
            w2_choice = '1'

        if w2_choice == '1':
            w2_file = input(
                f"  Path to W-2 CSV (Enter for 'data/w2_{tax_year}.csv'): "
            ).strip()
            if not w2_file:
                w2_file = f"data/w2_{tax_year}.csv"

            if not os.path.exists(w2_file):
                print(f"  Error: File '{w2_file}' not found.")
                return

            w2_data = calculator.load_w2_data(w2_file)
            w2_wages = w2_data['wages']
            federal_withheld = w2_data['federal_tax_withheld']
            print(f"  Loaded W-2 data from: {w2_file}")
            print(f"    Box 1 (Wages):              ${w2_wages:>14,.2f}")
            print(f"    Box 2 (Fed Tax Withheld):   ${federal_withheld:>14,.2f}")
            if w2_data.get('box12d_401k', 0) > 0:
                print(f"    Box 12D (401k):             ${w2_data['box12d_401k']:>14,.2f}")
            if w2_data.get('state'):
                print(f"    State: {w2_data['state']}, Wages: ${w2_data['state_wages']:>,.2f}, Tax: ${w2_data['state_tax_withheld']:>,.2f}")
        else:
            w2_wages = get_currency_input("  W-2 Box 1 (Wages, tips, other compensation): $")
            federal_withheld = get_currency_input("  W-2 Box 2 (Federal income tax withheld): $")
            w2_data = None
        print()

        # --- Stock Sales ---
        print("--- Stock Sales ---")
        print("  Input options:")
        print("  [1] 1099-B CSV (recommended if you have your 1099-B)")
        print("  [2] Stock holdings CSV (calculates gains via yfinance)")
        print("  [3] Skip stock sales (W-2 only)")
        stock_choice = input("  Choose (1/2/3, default 1): ").strip()
        if not stock_choice:
            stock_choice = '1'

        stock_results = []

        if stock_choice == '1':
            # --- 1099-B CSV ---
            csv_file = input(
                f"  Path to 1099-B CSV (Enter for 'data/1099b_{tax_year}.csv'): "
            ).strip()
            if not csv_file:
                csv_file = f"data/1099b_{tax_year}.csv"

            if not os.path.exists(csv_file):
                print(f"  Error: File '{csv_file}' not found.")
                return

            print(f"  Loading 1099-B data from: {csv_file}")
            stock_results = calculator.load_1099b_data(csv_file)
            summary = calculator.get_1099b_summary(stock_results)
            print(f"  Loaded {summary['total_count']} transactions ({summary['short_term']['count']} short-term, {summary['long_term']['count']} long-term)")
            print(f"  Total proceeds: ${summary['total_proceeds']:,.2f}")
            print(f"  Total taxable gain: ${summary['total_taxable_gain']:,.2f}")
            if summary['total_wash_sale'] > 0:
                print(f"  Wash sale adjustments: ${summary['total_wash_sale']:,.2f}")

        elif stock_choice == '2':
            # --- Stock Holdings CSV ---
            csv_file = input(
                "  Path to stock CSV (Enter for 'data/my-tesla-stocks.csv'): "
            ).strip()
            if not csv_file:
                csv_file = "data/my-tesla-stocks.csv"

            if not os.path.exists(csv_file):
                print(f"  Error: File '{csv_file}' not found.")
                return

            # Check if CSV has Date Sold column
            import pandas as pd
            df_check = pd.read_csv(csv_file, nrows=1)
            has_sale_data = 'Date Sold' in df_check.columns

            if has_sale_data:
                print("  CSV has 'Date Sold' column - processing actual sales only.")
                sold_only = True
            else:
                print("  CSV does not have 'Date Sold' column.")
                print("  Tip: Add 'Date Sold' and 'Sale Price' columns for stocks you've sold.")
                mode = input("  Process all rows as hypothetical sales? (y/n): ").lower().strip()
                if mode not in ['y', 'yes']:
                    print("  Skipping stock sales. Only W-2 income will be calculated.")
                    sold_only = None
                else:
                    sold_only = False

            if sold_only is not None:
                print("\n  Fetching stock prices and calculating gains...")
                print("  " + "-" * 56)
                stock_results = calculator.calculate_all_taxes(
                    csv_file,
                    ordinary_income=w2_wages,
                    sold_only=sold_only
                )
                print(f"\n  Processed {len(stock_results)} stock transaction(s).")

        # else stock_choice == '3': skip, stock_results stays empty

        print()

        # --- Stock Withholding ---
        stock_tax_withheld = 0.0
        if stock_results:
            raw = input("Federal tax withheld on stock sales (Enter for $0): $").strip()
            if raw:
                stock_tax_withheld = float(raw.replace(",", "").replace("$", ""))
        print()

        # --- Deduction ---
        print("--- Deduction ---")
        std_ded = calculator.standard_deduction_single
        print(f"  {tax_year} Standard Deduction (Single): ${std_ded:,.2f}")
        ded_choice = input(
            "  Use standard deduction? (y/n, default y): "
        ).lower().strip()
        deduction_amount = None  # None = use standard
        if ded_choice in ['n', 'no']:
            deduction_amount = get_currency_input("  Enter your itemized deduction amount: $")
        print()

        # --- Estimated Payments ---
        estimated_payments = 0.0
        raw = input(
            "Estimated tax payments made this year (Enter for $0): $"
        ).strip()
        if raw:
            estimated_payments = float(raw.replace(",", "").replace("$", ""))
        print()

        # --- Calculate ---
        print("=" * 60)
        print("  Calculating total tax liability...")
        print("=" * 60)
        print()

        liability = calculator.calculate_total_tax_liability(
            w2_wages=w2_wages,
            federal_tax_withheld=federal_withheld,
            stock_results=stock_results,
            deduction_amount=deduction_amount,
            estimated_payments=estimated_payments,
            stock_tax_withheld=stock_tax_withheld
        )

        report = calculator.generate_tax_liability_report(liability, stock_results)
        print(report)

        # --- Save Options ---
        save = input("\nSave this report to a file? (y/n): ").lower().strip()
        if save in ['y', 'yes']:
            output_dir = "outputs"
            os.makedirs(output_dir, exist_ok=True)
            filename = f"tax_liability_{tax_year}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            filepath = os.path.join(output_dir, filename)
            with open(filepath, 'w') as f:
                f.write(report)
            print(f"Report saved to: {filepath}")

    except ValueError as e:
        print(f"Error: Invalid input - {e}")
    except KeyboardInterrupt:
        print("\n\nCancelled.")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
