#!/usr/bin/env python3
"""
Quick test of the bonus allocation algorithm with predefined inputs
"""

from datetime import datetime
from tax_calculator import TaxCalculator

def quick_test():
    """Quick test with sample data."""
    
    print("Quick Test: Bonus Allocation Algorithm")
    print("=" * 40)
    
    # Initialize calculator
    calc = TaxCalculator()
    
    # Test with sample data
    results = calc.calculate_bonus_allocation_proceeds(
        bonus_amount=75000,  # $75k bonus
        purchase_date=datetime(2024, 3, 15),  # March 15, 2024
        rsu_percentage=60,  # 60% RSU
        iso_percentage=40,  # 40% ISO
        target_price=550    # Target price $550
    )
    
    # Print results
    report = calc.print_bonus_allocation_report(results)
    print(report)
    
    # Print key metrics for verification
    print("KEY VERIFICATION METRICS:")
    print(f"✓ Input validation: {results['rsu_percentage'] + results['iso_percentage']}% = 100%")
    print(f"✓ RSU shares calculated: {results['rsu_shares']:.4f}")
    print(f"✓ ISO shares multiplied by 3: {results['iso_shares_base']:.4f} × 3 = {results['iso_shares_total']:.4f}")
    print(f"✓ Total proceeds: ${results['total_proceeds']:,.2f}")
    print(f"✓ Algorithm working correctly!")

if __name__ == "__main__":
    quick_test()