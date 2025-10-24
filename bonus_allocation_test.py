#!/usr/bin/env python3
"""
Bonus Allocation Test - Compare 5 RSU/ISO allocation scenarios
Usage: python bonus_allocation_test.py [bonus_amount] [purchase_date] [target_price]
"""

import sys
from datetime import datetime
from tax_calculator import TaxCalculator

def test_allocation_scenarios(bonus_amount: float, purchase_date: datetime, target_price: float, 
                            ordinary_income: float = 300000, include_taxes: bool = True):
    """
    Test 5 different RSU/ISO allocation combinations:
    1) 100% RSUs, 0% ISOs
    2) 80% RSUs, 20% ISOs  
    3) 50% RSUs, 50% ISOs
    4) 20% RSUs, 80% ISOs
    5) 0% RSUs, 100% ISOs
    
    Args:
        bonus_amount: Bonus amount to allocate
        purchase_date: Purchase/grant date
        target_price: Target sale price
        ordinary_income: Current ordinary income for tax calculations
        include_taxes: Whether to include tax impact analysis
    """
    
    print("BONUS ALLOCATION SCENARIO COMPARISON")
    print("=" * 60)
    print(f"Bonus Amount: ${bonus_amount:,.2f}")
    print(f"Purchase Date: {purchase_date.strftime('%B %d, %Y')}")
    print(f"Target Sale Price: ${target_price:.2f}")
    if include_taxes:
        print(f"Ordinary Income: ${ordinary_income:,.2f}")
        print("Analysis: Including Tax Impact (RSU = LTCG, ISO = Ordinary Income)")
    else:
        print("Analysis: Pre-Tax Calculations Only")
    print()
    
    # Initialize calculator
    calc = TaxCalculator()
    
    # Define the 5 allocation scenarios
    scenarios = [
        {"name": "100% RSUs", "rsu_pct": 100, "iso_pct": 0},
        {"name": "80% RSUs, 20% ISOs", "rsu_pct": 80, "iso_pct": 20},
        {"name": "50% RSUs, 50% ISOs", "rsu_pct": 50, "iso_pct": 50},
        {"name": "20% RSUs, 80% ISOs", "rsu_pct": 20, "iso_pct": 80},
        {"name": "0% RSUs, 100% ISOs", "rsu_pct": 0, "iso_pct": 100},
    ]
    
    results_list = []
    strike_price = None
    
    # Calculate each scenario
    for i, scenario in enumerate(scenarios, 1):
        print(f"{i}) {scenario['name']}")
        print("-" * 35)
        
        try:
            if include_taxes:
                results = calc.calculate_bonus_allocation_proceeds_with_taxes(
                    bonus_amount=bonus_amount,
                    purchase_date=purchase_date,
                    rsu_percentage=scenario['rsu_pct'],
                    iso_percentage=scenario['iso_pct'],
                    target_price=target_price,
                    ordinary_income=ordinary_income
                )
                
                if strike_price is None:
                    strike_price = results['historical_price']
                
                # Print tax-aware results
                print(f"  Pre-Tax Proceeds: ${results['total_proceeds']:,.0f}")
                print(f"  After-Tax Proceeds: ${results['total_after_tax_proceeds']:,.0f}")
                print(f"  Total Taxes: ${results['total_taxes']:,.0f}")
                print(f"  Pre-Tax ROI: {results['total_return_percentage']:.1f}%")
                print(f"  After-Tax ROI: {results['after_tax_roi']:.1f}%")
                
                # Store after-tax results for comparison
                comparison_proceeds = results['total_after_tax_proceeds']
                comparison_gain = results['net_after_tax_gain']
                comparison_roi = results['after_tax_roi']
                
            else:
                results = calc.calculate_bonus_allocation_proceeds(
                    bonus_amount=bonus_amount,
                    purchase_date=purchase_date,
                    rsu_percentage=scenario['rsu_pct'],
                    iso_percentage=scenario['iso_pct'],
                    target_price=target_price
                )
                
                if strike_price is None:
                    strike_price = results['historical_price']
                
                # Print pre-tax results
                print(f"  Proceeds: ${results['total_proceeds']:,.0f}")
                print(f"  Net Gain/Loss: ${results['net_gain_loss']:,.0f}")
                print(f"  ROI: {results['total_return_percentage']:.1f}%")
                
                # Store pre-tax results for comparison
                comparison_proceeds = results['total_proceeds']
                comparison_gain = results['net_gain_loss']
                comparison_roi = results['total_return_percentage']
            
            if results.get('rsu_shares', 0) > 0:
                print(f"  RSU Shares: {results['rsu_shares']:.1f}")
            if results.get('iso_shares_total', 0) > 0:
                print(f"  ISO Options: {results['iso_shares_total']:.0f}")
            
            results_list.append({
                'scenario': scenario['name'],
                'proceeds': comparison_proceeds,
                'net_gain_loss': comparison_gain,
                'roi': comparison_roi,
                'has_taxes': include_taxes,
                'tax_data': results if include_taxes else None
            })
            
        except Exception as e:
            print(f"  Error: {e}")
            results_list.append({
                'scenario': scenario['name'],
                'error': str(e)
            })
        
        print()
    
    # Summary comparison
    print("=" * 60)
    header = "AFTER-TAX COMPARISON" if include_taxes else "PRE-TAX COMPARISON"
    print(header)
    print("=" * 60)
    
    proceed_label = "After-Tax Proceeds" if include_taxes else "Proceeds"
    gain_label = "After-Tax Gain" if include_taxes else "Net Gain"
    roi_label = "After-Tax ROI" if include_taxes else "ROI"
    
    print(f"{'Scenario':<25} {proceed_label:<15} {gain_label:<12} {roi_label:<8}")
    print("-" * 62)
    
    valid_results = []
    for result in results_list:
        if 'error' not in result:
            print(f"{result['scenario']:<25} "
                  f"${result['proceeds']:>12,.0f}  "
                  f"${result['net_gain_loss']:>9,.0f}  "
                  f"{result['roi']:>6.1f}%")
            valid_results.append(result)
        else:
            print(f"{result['scenario']:<25} ERROR")
    
    if valid_results and strike_price:
        # Analysis
        best = max(valid_results, key=lambda x: x['proceeds'])
        worst = min(valid_results, key=lambda x: x['proceeds'])
        
        print(f"\nBest Strategy: {best['scenario']}")
        print(f"  Proceeds: ${best['proceeds']:,.0f}")
        print(f"  ROI: {best['roi']:.1f}%")
        
        if best['proceeds'] != worst['proceeds']:
            improvement = ((best['proceeds'] - worst['proceeds']) / abs(worst['proceeds'])) * 100
            print(f"\nImprovement over worst: {improvement:.1f}%")
        
        # Key insights
        gain_per_iso = target_price - strike_price
        print(f"\nAnalysis:")
        print(f"• Strike Price: ${strike_price:.2f}")
        print(f"• Target Price: ${target_price:.2f}")
        print(f"• Gain per ISO Share: ${gain_per_iso:.2f}")
        
        if gain_per_iso > 0:
            print(f"• ISOs provide 3x leverage on ${gain_per_iso:.2f} gain per share")
            if gain_per_iso > strike_price * 0.5:
                print(f"• High gain per share strongly favors ISO allocation")
            elif gain_per_iso > strike_price * 0.2:
                print(f"• Moderate gain per share - mixed allocation may be optimal")
            else:
                print(f"• Low gain per share - RSUs may be safer choice")
        else:
            print(f"• Negative gain per share - ISOs will lose money!")
            print(f"• RSUs are clearly better when target < strike price")

def parse_date(date_str):
    """Parse date string in various formats"""
    formats = ['%Y-%m-%d', '%m/%d/%Y', '%m-%d-%Y', '%Y/%m/%d']
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unable to parse date: {date_str}")

def main():
    """Main function - handle command line arguments or prompt for input"""
    
    if len(sys.argv) >= 4:
        # Command line arguments provided
        try:
            bonus_amount = float(sys.argv[1])
            purchase_date = parse_date(sys.argv[2])
            target_price = float(sys.argv[3])
            
            # Optional parameters
            ordinary_income = float(sys.argv[4]) if len(sys.argv) > 4 else 300000
            include_taxes = sys.argv[5].lower() != 'false' if len(sys.argv) > 5 else True
            
        except (ValueError, IndexError) as e:
            print(f"Error parsing arguments: {e}")
            print("Usage: python bonus_allocation_test.py <bonus_amount> <purchase_date> <target_price> [ordinary_income] [include_taxes]")
            print("Example: python bonus_allocation_test.py 100000 2024-03-15 500 300000 true")
            return
    else:
        # Interactive input
        print("BONUS ALLOCATION SCENARIO TESTER")
        print("=" * 40)
        print("Enter the following parameters:")
        
        try:
            bonus_amount = float(input("Bonus Amount ($): "))
            date_str = input("Purchase Date (YYYY-MM-DD): ")
            purchase_date = parse_date(date_str)
            target_price = float(input("Target Sale Price ($): "))
            
            # Optional tax parameters
            income_input = input("Ordinary Income ($ - default 300000): ").strip()
            ordinary_income = float(income_input) if income_input else 300000
            
            tax_input = input("Include tax analysis? (y/n - default y): ").strip().lower()
            include_taxes = tax_input != 'n'
            
        except (ValueError, KeyboardInterrupt) as e:
            print(f"\\nError: {e}")
            return
        
        print()
    
    # Run the test
    test_allocation_scenarios(bonus_amount, purchase_date, target_price, ordinary_income, include_taxes)

if __name__ == "__main__":
    main()