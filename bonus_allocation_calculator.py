#!/usr/bin/env python3
"""
Interactive Tesla Stock Bonus Allocation Calculator
"""

from datetime import datetime
from tax_calculator import TaxCalculator
import os

def get_user_input():
    """Get user input for bonus allocation calculation."""
    
    print("=" * 60)
    print("TESLA STOCK BONUS ALLOCATION CALCULATOR")
    print("=" * 60)
    
    # Get bonus amount
    while True:
        try:
            bonus_amount = float(input("Enter your bonus amount ($): "))
            if bonus_amount <= 0:
                print("Please enter a positive amount.")
                continue
            break
        except ValueError:
            print("Please enter a valid number.")
    
    # Get purchase date
    while True:
        try:
            date_str = input("Enter purchase/grant date (YYYY-MM-DD): ")
            purchase_date = datetime.strptime(date_str, "%Y-%m-%d")
            break
        except ValueError:
            print("Please enter date in YYYY-MM-DD format (e.g., 2024-06-15).")
    
    # Get RSU percentage
    while True:
        try:
            rsu_percentage = float(input("Enter RSU percentage (0-100): "))
            if not (0 <= rsu_percentage <= 100):
                print("Please enter a percentage between 0 and 100.")
                continue
            break
        except ValueError:
            print("Please enter a valid number.")
    
    # Calculate ISO percentage
    iso_percentage = 100 - rsu_percentage
    print(f"ISO percentage will be: {iso_percentage:.1f}%")
    
    # Get target price
    while True:
        try:
            target_price = float(input("Enter target sale price ($): "))
            if target_price <= 0:
                print("Please enter a positive price.")
                continue
            break
        except ValueError:
            print("Please enter a valid number.")
    
    return bonus_amount, purchase_date, rsu_percentage, iso_percentage, target_price

def main():
    """Main function for interactive bonus allocation calculator."""
    
    try:
        # Get user inputs
        bonus_amount, purchase_date, rsu_percentage, iso_percentage, target_price = get_user_input()
        
        # Initialize calculator
        print("\nInitializing calculator...")
        calc = TaxCalculator()
        
        # Calculate proceeds
        print("\nCalculating bonus allocation proceeds...")
        results = calc.calculate_bonus_allocation_proceeds(
            bonus_amount=bonus_amount,
            purchase_date=purchase_date,
            rsu_percentage=rsu_percentage,
            iso_percentage=iso_percentage,
            target_price=target_price
        )
        
        # Generate and display report
        report = calc.print_bonus_allocation_report(results)
        print(report)
        
        # Ask if user wants to save the report
        save_report = input("Save report to file? (y/n): ").lower().strip()
        if save_report in ['y', 'yes']:
            # Create outputs directory if it doesn't exist
            output_dir = "outputs"
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"bonus_allocation_report_{timestamp}.txt"
            filepath = os.path.join(output_dir, filename)
            
            # Save report
            with open(filepath, 'w') as f:
                f.write("TESLA STOCK BONUS ALLOCATION CALCULATOR\n")
                f.write("=" * 60 + "\n")
                f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(report)
            
            print(f"Report saved to: {filepath}")
        
        # Ask if user wants to calculate another scenario
        another = input("\nCalculate another scenario? (y/n): ").lower().strip()
        if another in ['y', 'yes']:
            main()  # Recursive call for another calculation
            
    except KeyboardInterrupt:
        print("\n\nCalculation cancelled by user.")
    except Exception as e:
        print(f"\nError: {e}")
        print("Please try again with valid inputs.")

if __name__ == "__main__":
    main()