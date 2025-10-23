from tax_calculator import TaxCalculator
from datetime import datetime
import pandas as pd

def verify_espp_calculation():
    """Verify ESPP tax calculation for the 2/29/2024 transaction."""
    calc = TaxCalculator()
    
    # Test parameters for 2/29/2024 ESPP transaction (qualifying)
    purchase_date = datetime(2024, 2, 29)
    sold_date = datetime(2025, 10, 23)
    ordinary_income = 300000  # Example income for tax calculation
    shares = 63  # From CSV data
    
    print("=" * 60)
    print("ESPP TAX CALCULATION VERIFICATION - 2/29/2024 Transaction")
    print("=" * 60)
    print(f'Transaction: ESPP Purchase on {purchase_date.strftime("%Y-%m-%d")}')
    print(f'Sale Date: {sold_date.strftime("%Y-%m-%d")}')
    print(f'Shares: {shares}')
    print(f'Ordinary Income: ${ordinary_income:,.2f}')
    print()
    
    # Step 1: Determine offer date and qualification
    offer_date = calc.get_tesla_offer_date(purchase_date)
    is_qualifying = calc.is_qualifying_espp_disposition(offer_date, purchase_date, sold_date)
    
    days_from_offer = (sold_date - offer_date).days
    days_from_purchase = (sold_date - purchase_date).days
    
    print("QUALIFICATION CHECK:")
    print(f'Offer Date: {offer_date.strftime("%Y-%m-%d")}')
    print(f'Purchase Date: {purchase_date.strftime("%Y-%m-%d")}')
    print(f'Days from offer: {days_from_offer} (needs >= 730) ✓' if days_from_offer >= 730 else f'Days from offer: {days_from_offer} (needs >= 730) ✗')
    print(f'Days from purchase: {days_from_purchase} (needs >= 365) ✓' if days_from_purchase >= 365 else f'Days from purchase: {days_from_purchase} (needs >= 365) ✗')
    print(f'Is Qualifying Disposition: {is_qualifying}')
    print()
    
    # Step 2: Get historical stock prices
    print("STOCK PRICE LOOKUP:")
    offer_price = calc.get_stock_price('TSLA', offer_date)
    purchase_date_price = calc.get_stock_price('TSLA', purchase_date)
    sold_price = calc.get_stock_price('TSLA', sold_date)
    
    print(f'Tesla price on offer date ({offer_date.strftime("%Y-%m-%d")}): ${offer_price:.2f}')
    print(f'Tesla price on purchase date ({purchase_date.strftime("%Y-%m-%d")}): ${purchase_date_price:.2f}')
    print(f'Tesla price on sale date ({sold_date.strftime("%Y-%m-%d")}): ${sold_price:.2f}')
    print()
    
    # Step 3: Calculate ESPP purchase price
    lower_price = min(offer_price, purchase_date_price)
    espp_purchase_price = lower_price * 0.85  # 15% discount
    
    print("ESPP PRICING CALCULATION:")
    print(f'Lower of offer/purchase price: ${lower_price:.2f}')
    print(f'ESPP purchase price (85% of lower): ${espp_purchase_price:.2f}')
    print(f'Total purchase value: ${espp_purchase_price * shares:.2f}')
    print()
    
    # Step 4: Manual tax calculation
    purchase_value = espp_purchase_price * shares
    proceeds = shares * sold_price
    total_gain = proceeds - purchase_value
    
    print("GAIN CALCULATION:")
    print(f'Proceeds (shares × sale price): ${proceeds:.2f}')
    print(f'Purchase value: ${purchase_value:.2f}')
    print(f'Total gain: ${total_gain:.2f}')
    print()
    
    # Step 5: Tax calculation based on qualification
    if is_qualifying:
        print("QUALIFYING DISPOSITION TAX CALCULATION:")
        discount_amount = (lower_price - espp_purchase_price) * shares
        ordinary_income_portion = min(discount_amount, total_gain)
        capital_gain_portion = max(0, total_gain - ordinary_income_portion)
        
        print(f'Discount amount: ${discount_amount:.2f}')
        print(f'Ordinary income portion: ${ordinary_income_portion:.2f}')
        print(f'Capital gain portion: ${capital_gain_portion:.2f}')
        
        marginal_rate = calc.calculate_marginal_tax_rate(ordinary_income)
        capital_gains_rate = calc.calculate_capital_gains_rate(ordinary_income)
        
        ordinary_tax = ordinary_income_portion * marginal_rate
        capital_gains_tax = capital_gain_portion * capital_gains_rate
        total_tax = ordinary_tax + capital_gains_tax
        
        print(f'Marginal tax rate: {marginal_rate:.1%}')
        print(f'Capital gains rate: {capital_gains_rate:.1%}')
        print(f'Tax on ordinary income: ${ordinary_tax:.2f}')
        print(f'Tax on capital gains: ${capital_gains_tax:.2f}')
        print(f'Total tax: ${total_tax:.2f}')
    else:
        print("DISQUALIFYING DISPOSITION TAX CALCULATION:")
        # For disqualifying dispositions, discount is based on purchase date FMV
        discount_amount = (purchase_date_price - espp_purchase_price) * shares
        ordinary_income_portion = discount_amount
        capital_gain_portion = max(0, total_gain - ordinary_income_portion)
        
        print(f'Discount amount (purchase date FMV - ESPP price): ${discount_amount:.2f}')
        print(f'Ordinary income portion: ${ordinary_income_portion:.2f}')
        print(f'Capital gain portion: ${capital_gain_portion:.2f}')
        
        marginal_rate = calc.calculate_marginal_tax_rate(ordinary_income)
        ordinary_tax = ordinary_income_portion * marginal_rate
        
        # Check if capital gains are long-term
        is_long_term = calc.is_long_term(purchase_date, sold_date)
        if is_long_term:
            capital_gains_rate = calc.calculate_capital_gains_rate(ordinary_income)
            capital_gains_tax = capital_gain_portion * capital_gains_rate
            print(f'Capital gains (long-term) rate: {capital_gains_rate:.1%}')
        else:
            capital_gains_tax = capital_gain_portion * marginal_rate
            print(f'Capital gains (short-term) rate: {marginal_rate:.1%}')
        
        total_tax = ordinary_tax + capital_gains_tax
        
        print(f'Tax on ordinary income: ${ordinary_tax:.2f}')
        print(f'Tax on capital gains: ${capital_gains_tax:.2f}')
        print(f'Total tax: ${total_tax:.2f}')
    
    print()
    print("=" * 60)
    
    # Step 6: Compare with program calculation
    print("COMPARISON WITH PROGRAM CALCULATION:")
    
    # Create a mock row similar to CSV data
    row_data = {
        'Date Acquired': purchase_date,
        'Sellable Qty.': shares,
        'Stock_Type': 'ESPP'
    }
    row = pd.Series(row_data)
    
    # Use the actual calculator
    result = calc.calculate_espp_taxes(row, sold_date, sold_price, ordinary_income)
    
    if result:
        print(f"Program calculated tax: ${result['tax_amount']:.2f}")
        print(f"Manual calculated tax:  ${total_tax:.2f}")
        print(f"Difference: ${abs(result['tax_amount'] - total_tax):.2f}")
        
        if abs(result['tax_amount'] - total_tax) < 0.01:
            print("✓ CALCULATIONS MATCH!")
        else:
            print("✗ CALCULATIONS DIFFER - Need to investigate")
            
        print("\nProgram calculation details:")
        for key, value in result.items():
            if isinstance(value, float):
                print(f"  {key}: ${value:.2f}" if 'price' in key or 'amount' in key or 'gain' in key or 'proceeds' in key else f"  {key}: {value}")
            else:
                print(f"  {key}: {value}")
    else:
        print("Program calculation failed!")
    
    print()
    print("CSV COMPARISON:")
    print("From CSV Expected Gain/Loss: $9,197.37")
    print(f"Our calculated total gain:    ${total_gain:.2f}")
    print("From CSV Est. Market Value:   $27,655.11")
    print(f"Our calculated proceeds:      ${proceeds:.2f}")
    print("From CSV Tax:                 $3,219.08")
    print(f"Our calculated tax:           ${total_tax:.2f}")
    
    # Additional analysis for 2025 transaction
    print()
    print("ANALYSIS:")
    print("This transaction is from 2025, so:")
    print("- It should be a DISQUALIFYING disposition (less than 2 years from offer)")
    print("- It should be SHORT-TERM capital gains (less than 1 year from purchase)")
    print(f"- Time from purchase to sale: {(sold_date - purchase_date).days} days")

if __name__ == "__main__":
    verify_espp_calculation()