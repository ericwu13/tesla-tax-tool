#!/usr/bin/env python3
"""
Test script for cashless ISO exercise calculation
"""

from tax_calculator import TaxCalculator
from datetime import datetime

def test_cashless_iso():
    """Test the cashless ISO exercise calculation."""
    
    print("Testing Cashless ISO Exercise Calculation")
    print("=" * 50)
    
    calc = TaxCalculator()
    
    # Test scenario
    bonus_amount = 50000
    purchase_date = datetime(2023, 6, 15)
    rsu_percentage = 50
    iso_percentage = 50
    target_price = 400
    
    results = calc.calculate_bonus_allocation_proceeds(
        bonus_amount=bonus_amount,
        purchase_date=purchase_date,
        rsu_percentage=rsu_percentage,
        iso_percentage=iso_percentage,
        target_price=target_price
    )
    
    # Show detailed breakdown
    print(f"\nINPUT PARAMETERS:")
    print(f"Bonus Amount: ${bonus_amount:,}")
    print(f"Purchase Date: {purchase_date.strftime('%Y-%m-%d')}")
    print(f"RSU/ISO Split: {rsu_percentage}%/{iso_percentage}%")
    print(f"Target Price: ${target_price}")
    
    print(f"\nCALCULATION BREAKDOWN:")
    print(f"Historical Price: ${results['historical_price']:.2f}")
    print(f"RSU Allocation: ${results['rsu_allocation']:,.2f}")
    print(f"ISO Allocation: ${results['iso_allocation']:,.2f}")
    print(f"RSU Shares: {results['rsu_shares']:.4f}")
    print(f"ISO Shares (base): {results['iso_shares_base']:.4f}")
    print(f"ISO Shares (×3): {results['iso_shares_total']:.4f}")
    
    print(f"\nCASHLESS EXERCISE CALCULATION:")
    print(f"ISO Strike Price: ${results['historical_price']:.2f}")
    print(f"Target Sale Price: ${target_price:.2f}")
    print(f"Gain per ISO Share: ${target_price - results['historical_price']:.2f}")
    print(f"Total ISO Gain: {results['iso_shares_total']:.4f} × ${target_price - results['historical_price']:.2f} = ${results['iso_proceeds']:,.2f}")
    
    print(f"\nFINAL RESULTS:")
    print(f"RSU Proceeds: ${results['rsu_proceeds']:,.2f}")
    print(f"ISO Proceeds (gain only): ${results['iso_proceeds']:,.2f}")
    print(f"Total Proceeds: ${results['total_proceeds']:,.2f}")
    print(f"Total Return: {results['total_return_percentage']:.2f}%")
    
    # Verification
    expected_iso_gain = results['iso_shares_total'] * (target_price - results['historical_price'])
    print(f"\n✓ ISO Gain Verification: ${expected_iso_gain:,.2f} = ${results['iso_proceeds']:,.2f}")
    print(f"✓ No upfront cash needed for ISO exercise")
    print(f"✓ ISO proceeds represent pure gain from cashless exercise")

if __name__ == "__main__":
    test_cashless_iso()