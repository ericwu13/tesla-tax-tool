from tax_calculator import TaxCalculator
from datetime import datetime

calc = TaxCalculator()

# Test the 2/29/2024 ESPP purchase
purchase_date = datetime(2024, 2, 29)
offer_date = calc.get_tesla_offer_date(purchase_date)
sold_date = datetime(2025, 10, 23)

print(f'Purchase Date: {purchase_date.strftime("%Y-%m-%d")}')
print(f'Inferred Offer Date: {offer_date.strftime("%Y-%m-%d")}')
print(f'Sale Date: {sold_date.strftime("%Y-%m-%d")}')

# Check qualification
is_qualifying = calc.is_qualifying_espp_disposition(offer_date, purchase_date, sold_date)
print(f'Is Qualifying: {is_qualifying}')

# Check time periods
days_from_offer = (sold_date - offer_date).days
days_from_purchase = (sold_date - purchase_date).days
print(f'Days from offer: {days_from_offer} (needs >= 730)')
print(f'Days from purchase: {days_from_purchase} (needs >= 365)')

print()
print("Expected gain verification:")
print("From CSV: $14,529.09")
print("Est. Market Value: $27,655.11")
print("Purchase value should be: $27,655.11 - $14,529.09 = $13,126.02")
print(f"Purchase price per share: ${13126.02/63:.2f}")