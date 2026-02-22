#!/usr/bin/env python3
"""Quick test for the new tax liability features."""

from tax_calculator import TaxCalculator

calc = TaxCalculator(tax_year=2025)

# Test 1: Progressive ordinary tax on $100,000
# Expected: $11,925 x 10% + ($48,475-$11,925) x 12% + ($100,000-$48,475) x 22%
# = $1,192.50 + $4,386.00 + $11,335.50 = $16,914.00
tax, brackets = calc.calculate_progressive_ordinary_tax(100000)
print(f"Test 1 - Progressive tax on $100k: ${tax:,.2f} (expected $16,914.00)")
for b in brackets:
    print(f"  {b['rate']*100:.0f}%: ${b['income_in_bracket']:,.2f} -> ${b['tax_in_bracket']:,.2f}")
assert abs(tax - 16914.00) < 0.01, f"FAIL: expected $16,914.00 got ${tax:,.2f}"
print("  PASS")
print()

# Test 2: LTCG stacking - $100k ordinary fills past the $48,350 0% bracket
# So all $50k LTCG should be at 15%
ltcg_tax, ltcg_brackets = calc.calculate_progressive_ltcg_tax(100000, 50000)
print(f"Test 2 - LTCG tax on $50k (with $100k ordinary): ${ltcg_tax:,.2f} (expected $7,500.00)")
for b in ltcg_brackets:
    print(f"  {b['rate']*100:.0f}%: ${b['gains_in_bracket']:,.2f} -> ${b['tax_in_bracket']:,.2f}")
assert abs(ltcg_tax - 7500.00) < 0.01, f"FAIL: expected $7,500.00 got ${ltcg_tax:,.2f}"
print("  PASS")
print()

# Test 3: NIIT - AGI $300k, investment income $50k
# excess AGI = $300k - $200k = $100k, min($100k, $50k) = $50k * 3.8% = $1,900
niit = calc.calculate_niit(300000, 50000)
print(f"Test 3 - NIIT: ${niit:,.2f} (expected $1,900.00)")
assert abs(niit - 1900.00) < 0.01, f"FAIL: expected $1,900.00 got ${niit:,.2f}"
print("  PASS")
print()

# Test 4: Full tax liability, W-2 only
liability = calc.calculate_total_tax_liability(
    w2_wages=150000,
    federal_tax_withheld=30000,
    stock_results=[],
)
# Taxable = $150,000 - $15,000 = $135,000
# Tax = $11,925*10% + $36,550*12% + $54,875*22% + $31,650*24%
#      = $1,192.50 + $4,386.00 + $12,072.50 + $7,596.00 = $25,247.00
print(f"Test 4 - W2-only $150k:")
print(f"  Taxable: ${liability['taxable_ordinary_income']:,.2f} (expected $135,000.00)")
print(f"  Total tax: ${liability['total_tax_liability']:,.2f} (expected $25,247.00)")
print(f"  Net due: ${liability['net_tax_due']:,.2f}")
print(f"  Refund: ${liability['refund']:,.2f}")
assert abs(liability['taxable_ordinary_income'] - 135000) < 0.01
assert abs(liability['total_tax_liability'] - 25247.00) < 0.01
print("  PASS")
print()

# Test 5: Full report generation
print("Test 5 - Report generation:")
report = calc.generate_tax_liability_report(liability, [])
print(report)

# Test 6: Full liability with mock stock results
mock_stock = [
    {
        'stock_type': 'RSU',
        'acquired_date': __import__('datetime').datetime(2024, 3, 5),
        'shares': 24.25,
        'acquisition_price': 200.0,
        'sold_price': 400.0,
        'proceeds': 9700.0,
        'total_gain': 4850.0,
        'is_long_term': True,
        'tax_type': 'Long Term Capital Gains',
        'tax_rate': 0.15,
        'tax_amount': 727.50,
        'ordinary_income_portion': 0,
        'capital_gain_portion': 4850.0,
        'grant_number': '632058',
    }
]
liability2 = calc.calculate_total_tax_liability(
    w2_wages=150000,
    federal_tax_withheld=30000,
    stock_results=mock_stock,
)
print(f"\nTest 6 - W2 $150k + LTCG $4,850:")
print(f"  AGI: ${liability2['agi']:,.2f}")
print(f"  LTCG: ${liability2['total_long_term_gains']:,.2f}")
print(f"  LTCG tax: ${liability2['ltcg_tax']:,.2f}")
print(f"  NIIT: ${liability2['niit']:,.2f}")
print(f"  Total tax: ${liability2['total_tax_liability']:,.2f}")
report2 = calc.generate_tax_liability_report(liability2, mock_stock)
print(report2)

# Test 7: Load 1099-B CSV and verify totals
print("Test 7 - 1099-B CSV loading:")
results_1099b = calc.load_1099b_data("data/1099b_2025.csv")
summary = calc.get_1099b_summary(results_1099b)
print(f"  Total lots: {summary['total_count']} (expected 27)")
print(f"  ST lots: {summary['short_term']['count']} (expected 20)")
print(f"  LT lots: {summary['long_term']['count']} (expected 7)")
print(f"  ST proceeds: ${summary['short_term']['proceeds']:,.2f} (expected $52,431.25)")
print(f"  LT proceeds: ${summary['long_term']['proceeds']:,.2f} (expected $24,338.78)")
print(f"  ST cost basis: ${summary['short_term']['cost_basis']:,.2f} (expected $52,670.44)")
print(f"  LT cost basis: ${summary['long_term']['cost_basis']:,.2f} (expected $11,906.73)")
print(f"  Wash sale disallowed: ${summary['total_wash_sale']:,.2f} (expected $852.24)")
print(f"  ST taxable gain: ${summary['short_term']['taxable_gain']:,.2f} (expected $613.05)")
print(f"  LT taxable gain: ${summary['long_term']['taxable_gain']:,.2f} (expected $12,432.05)")

assert summary['total_count'] == 27
assert summary['short_term']['count'] == 20
assert summary['long_term']['count'] == 7
assert abs(summary['short_term']['proceeds'] - 52431.25) < 0.01
assert abs(summary['long_term']['proceeds'] - 24338.78) < 0.01
assert abs(summary['short_term']['cost_basis'] - 52670.44) < 0.01
assert abs(summary['long_term']['cost_basis'] - 11906.73) < 0.01
assert abs(summary['total_wash_sale'] - 852.24) < 0.01
assert abs(summary['short_term']['taxable_gain'] - 613.05) < 0.01
assert abs(summary['long_term']['taxable_gain'] - 12432.05) < 0.01
print("  PASS")
print()

# Test 8: Full tax liability with 1099-B data + W-2
print("Test 8 - Full liability with 1099-B + W-2 $150k:")
liability3 = calc.calculate_total_tax_liability(
    w2_wages=150000,
    federal_tax_withheld=30000,
    stock_results=results_1099b,
)
# ST gains ($613.05) taxed as ordinary income: total ordinary = $150,613.05
# LT gains ($12,432.05) taxed at LTCG rate
# AGI = $150,613.05 + $12,432.05 = $163,045.10
# Taxable ordinary = $150,613.05 - $15,000 = $135,613.05
print(f"  AGI: ${liability3['agi']:,.2f}")
print(f"  ST gains (ordinary): ${liability3['stock_short_term_gains']:,.2f}")
print(f"  LT gains: ${liability3['total_long_term_gains']:,.2f}")
print(f"  Taxable ordinary: ${liability3['taxable_ordinary_income']:,.2f}")
print(f"  Ordinary tax: ${liability3['ordinary_tax']:,.2f}")
print(f"  LTCG tax: ${liability3['ltcg_tax']:,.2f}")
print(f"  NIIT: ${liability3['niit']:,.2f}")
print(f"  Total tax: ${liability3['total_tax_liability']:,.2f}")
print(f"  Net due: ${liability3['net_tax_due']:,.2f}")
print(f"  Refund: ${liability3['refund']:,.2f}")

assert abs(liability3['stock_short_term_gains'] - 613.05) < 0.01
assert abs(liability3['total_long_term_gains'] - 12432.05) < 0.01
assert abs(liability3['agi'] - 163045.10) < 0.01
print("  PASS")
print()

# Test 9: Report with 1099-B data (verify 1099-B summary section appears)
print("Test 9 - Report with 1099-B summary:")
report3 = calc.generate_tax_liability_report(liability3, results_1099b)
assert "1099-B SUMMARY" in report3
assert "Wash Sale Disallowed" in report3
print(report3)
print("  PASS")

print("\nAll tests passed!")
