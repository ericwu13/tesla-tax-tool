#!/usr/bin/env python3
"""
Test script for the Tesla Stock Tax Calculator
"""

from tax_calculator import TaxCalculator
from datetime import datetime
import os

def test_calculator():
    print("Testing Tesla Stock Tax Calculator...")
    print("=" * 50)
    
    # Test parameters
    csv_file = "data/my-tesla-stocks.csv"
    ordinary_income = 300000 # Example income
    sold_date = datetime(2025, 10, 23)  # Today's date
    
    print(f"CSV file: {csv_file}")
    print(f"Ordinary income: ${ordinary_income:,.2f}")
    print(f"Sale date: {sold_date.strftime('%Y-%m-%d')}")
    print()
    
    if not os.path.exists(csv_file):
        print(f"Error: File '{csv_file}' not found.")
        return
    
    try:
        # Create calculator
        calculator = TaxCalculator()
        
        # Test individual components first
        print("Testing tax rate calculations...")
        marginal_rate = calculator.calculate_marginal_tax_rate(ordinary_income)
        capital_gains_rate = calculator.calculate_capital_gains_rate(ordinary_income)
        print(f"Marginal tax rate: {marginal_rate:.1%}")
        print(f"Capital gains rate: {capital_gains_rate:.1%}")
        print()
        
        print("Loading and processing stock data...")
        df = calculator.load_stock_data(csv_file)
        print(f"Loaded {len(df)} transactions")
        print("Stock types found:", df['Stock_Type'].value_counts().to_dict())
        print()
        
        print("Fetching Tesla stock price...")
        stock_price = calculator.get_stock_price('TSLA', sold_date)
        print(f"Tesla stock price on {sold_date.strftime('%Y-%m-%d')}: ${stock_price:.2f}")
        print()
        
        print("Calculating taxes for all transactions...")
        results = calculator.calculate_all_taxes(csv_file, ordinary_income, sold_date)
        
        if results:
            print(f"Successfully processed {len(results)} transactions")
            
            # Generate report
            report = calculator.generate_report(results, ordinary_income, sold_date)
            print("\n" + "=" * 80)
            print("GENERATED REPORT:")
            print("=" * 80)
            print(report)
            
            # Save report
            output_dir = "outputs"
            os.makedirs(output_dir, exist_ok=True)
            
            report_file = f"test_report_{sold_date.strftime('%Y%m%d')}.txt"
            report_path = os.path.join(output_dir, report_file)
            with open(report_path, 'w') as f:
                f.write(report)
            print(f"\nReport saved to: {report_path}")
            
            # Test CSV export
            csv_file = f"test_results_{sold_date.strftime('%Y%m%d')}.csv"
            calculator.export_to_csv(results, csv_file)
            print(f"CSV results exported to: outputs/{csv_file}")
            
        else:
            print("No transactions were processed successfully.")
    
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_calculator()