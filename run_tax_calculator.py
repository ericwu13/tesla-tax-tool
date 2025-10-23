#!/usr/bin/env python3
"""
Simple interactive script to run the Tesla Stock Tax Calculator
"""

from tax_calculator import TaxCalculator
from datetime import datetime
import os

def main():
    print("=" * 60)
    print("TESLA STOCK TAX CALCULATOR")
    print("=" * 60)
    print()
    
    # Get inputs from user
    try:
        # CSV file path
        csv_file = input("Enter the path to your stock CSV file (or press Enter for 'my-tesla-stocks.csv'): ").strip()
        if not csv_file:
            csv_file = "my-tesla-stocks.csv"
        
        if not os.path.exists(csv_file):
            print(f"Error: File '{csv_file}' not found.")
            return
        
        # Ordinary income
        ordinary_income = float(input("Enter your ordinary income for 2025: $").replace(",", "").replace("$", ""))
        
        # Sold date
        sold_date_str = input("Enter the sale date (YYYY-MM-DD) or press Enter for today: ").strip()
        if sold_date_str:
            sold_date = datetime.strptime(sold_date_str, '%Y-%m-%d')
        else:
            sold_date = datetime.now()
        
        print(f"\nProcessing stock data from: {csv_file}")
        print(f"Ordinary income: ${ordinary_income:,.2f}")
        print(f"Sale date: {sold_date.strftime('%Y-%m-%d')}")
        print("\nFetching Tesla stock price and calculating taxes...")
        print("-" * 60)
        
        # Create calculator and run calculations
        calculator = TaxCalculator()
        results = calculator.calculate_all_taxes(csv_file, ordinary_income, sold_date)
        
        if not results:
            print("No valid stock transactions found in the CSV file.")
            return
        
        # Generate and display report
        report = calculator.generate_report(results, ordinary_income, sold_date)
        print(report)
        
        # Ask if user wants to save the report
        save_report = input("\nWould you like to save this report to a file? (y/n): ").lower().strip()
        if save_report in ['y', 'yes']:
            filename = f"tesla_tax_report_{sold_date.strftime('%Y%m%d')}.txt"
            with open(filename, 'w') as f:
                f.write(report)
            print(f"Report saved to: {filename}")
        
        # Ask if user wants to export to CSV
        export_csv = input("Would you like to export the results to CSV? (y/n): ").lower().strip()
        if export_csv in ['y', 'yes']:
            csv_filename = f"tesla_tax_results_{sold_date.strftime('%Y%m%d')}.csv"
            calculator.export_to_csv(results, csv_filename)
        
    except ValueError as e:
        print(f"Error: Invalid input - {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()