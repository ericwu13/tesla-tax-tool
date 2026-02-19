# Tesla Tax Calculator

A comprehensive tax calculator for computing complete federal and California state income tax liability. Supports W-2 income, stock sales (RSUs), rental property income, mortgage deductions, and itemized deductions.

## Features

### Complete Tax Return Calculation
- **Federal Income Tax**: Progressive bracket calculation with 2025+ tax brackets
- **California State Tax**: Progressive bracket calculation with CA-specific rules (all gains taxed as ordinary income)
- **Stock Sales (1099-B)**: Short-term and long-term capital gains, wash sale adjustments, RSU sales
- **Rental Property (Schedule E)**: Rental income, expenses, depreciation (27.5-year, mid-month convention)
- **Itemized Deductions (Schedule A)**: Mortgage interest, property taxes, SALT cap, mortgage insurance phaseout
- **Net Investment Income Tax (NIIT)**: 3.8% surtax on investment income when AGI > $200,000
- **Multiple Income Sources**: W-2 wages, interest income (1099-INT), capital gains (1099-B)

## Quick Start - Annual Tax Calculation

### 1. Prepare Your Data Files

Create CSV files in the `data/` directory following the naming convention `data/{form}_{year}.csv`:

#### W-2 Data (`data/w2_YYYY.csv`)
```csv
Field,Value,Description
employer,Employer Name,Employer name
tax_year,2025,Tax year
box1_wages,150000.00,Box 1: Wages tips other compensation (includes RSU vest income)
box2_federal_tax_withheld,30000.00,Box 2: Federal income tax withheld
box12d_401k,23000.00,Box 12d: 401(k) contributions
box12w_hsa,4300.00,Box 12w: HSA contributions
state,CA,State abbreviation
box16_state_wages,154300.00,Box 16: State wages
box17_state_tax_withheld,13000.00,Box 17: State income tax withheld
box14_casdi,1800.00,Box 14: CA SDI withheld
```

**Where to find this**: Your W-2 form from your employer

#### 1099-B Stock Sales (`data/1099b_YYYY.csv`)
```csv
Term,Date Sold,Date Acquired,Proceeds,Cost Basis,Wash Sale Disallowed,Gain Loss,Grant Number,Shares,Form 8949 Box
Short Term,03/06/25,03/05/25,5000.00,5200.00,200.00,-200.00,100001,10.000,B
Short Term,06/06/25,06/05/25,5500.00,5100.00,0.00,400.00,100001,10.000,B
Long Term,10/27/25,12/05/23,12000.00,8000.00,0.00,4000.00,200001,20.000,E
Long Term,10/28/25,06/05/24,8000.00,5000.00,0.00,3000.00,200002,15.000,E
```

**Important**:
- Use actual sale data from your 1099-B form
- "Short Term" = held ≤ 1 year, "Long Term" = held > 1 year
- Include wash sale disallowed amounts if applicable (reported on your 1099-B)
- **RSU sales**: Cost basis already includes ordinary income reported on W-2 (FMV at vest)
- **ESPP sales**: If you sold ESPP, the 15% discount is ordinary income (usually added to W-2, check your supplement)

**Where to find this**: Your 1099-B form from your brokerage

#### Mortgage Data (`data/1098_YYYY.csv`)
```csv
Field,Value,Description
lender,Mortgage Servicer,Mortgage servicer
tax_year,2025,Form 1098 Tax Year
box1_mortgage_interest,20000.00,Box 1: Mortgage interest paid
box2_outstanding_principal,600000.00,Box 2: Outstanding mortgage principal
box5_mortgage_insurance,500.00,Box 5: Mortgage insurance premiums
box10_property_taxes,8000.00,Box 10: Property taxes paid
purchase_price,750000.00,Property purchase price (for depreciation calc)
rental_start_date,03/01/2025,Date rental activity began (if applicable)
```

**Where to find this**: Your Form 1098 from your mortgage lender

#### Interest Income (`data/1099int_YYYY.csv`)
```csv
Payer,Box 1 Interest,Description
Brokerage Account,50.00,Interest income from brokerage account
Savings Bank,800.00,Interest income from savings account
Mortgage Escrow,75.00,Interest income from mortgage escrow
```

**Where to find this**: Your 1099-INT form(s) from banks and financial institutions

### 2. Run the Tax Calculator

The calculator automatically finds your CSV files based on the year. Use command-line arguments for flexibility:

#### Basic Usage (No Rental Property)
```bash
# Uses default file paths: data/w2_2025.csv, data/1099b_2025.csv, etc.
python run_annual_taxes.py --year 2025
```

#### With Rental Property
```bash
# Example: 20% rental usage, $12,000 rental income, started January
python run_annual_taxes.py --year 2025 \
  --rental-pct 0.20 \
  --rental-income 12000 \
  --other-rental-income 200 \
  --rental-start-month 1 \
  --rental-hoa 4000 \
  --rental-insurance 1200 \
  --rental-supplies 400 \
  --rental-electricity 1000 \
  --rental-telephone 600
```

#### With Estimated Payments
```bash
python run_annual_taxes.py --year 2025 --estimated-payments 5000
```

#### Override Capital Gains Directly
```bash
# Skip the 1099-B CSV and pass gains manually
python run_annual_taxes.py --year 2025 --st-gains 500 --lt-gains 7000
```

#### Custom File Paths
```bash
# If your files are in a different location or use different names
python run_annual_taxes.py --year 2025 \
  --w2 mydata/my_w2.csv \
  --1099b mydata/my_stocks.csv \
  --1098 mydata/my_mortgage.csv \
  --1099int mydata/my_interest.csv
```

#### All Options
```bash
python run_annual_taxes.py --help
```

### 3. Review the Output

The tool generates a comprehensive report showing:

```
================================================================================
  2025 FEDERAL INCOME TAX LIABILITY ESTIMATE
================================================================================

  INCOME
    W-2 Wages (Box 1):                          $    150,000.00
    Interest Income (1099-INT):                  $        925.00
    Short-Term Capital Gains:                    $        200.00
    Long-Term Capital Gains:                     $      7,000.00
    Net Rental Income (Schedule E):              $        500.00
                                                    --------------
    Adjusted Gross Income (AGI):                 $    158,625.00

  DEDUCTIONS
    Itemized Deductions (Schedule A):
      Mortgage Interest (personal 80%):          $     16,000.00
      SALT (State tax + property tax):            $     17,400.00
    Total Itemized:                             ($     33,400.00)
    -> Using Itemized

    Taxable Ordinary Income:                     $    125,125.00
    Taxable Long-Term Capital Gains:             $      7,000.00

  FEDERAL TAX CALCULATION
    Tax on Ordinary Income (Progressive):        $     22,500.00
    Long-Term Capital Gains Tax (15%):           $      1,050.00
    Net Investment Income Tax (3.8%):            $        266.00
                                                    ==============
    TOTAL FEDERAL TAX LIABILITY:                 $     23,816.00

  PAYMENTS & WITHHOLDINGS
    W-2 Federal Tax Withheld:                   ($     30,000.00)
                                                    ==============
    REFUND:                                      $      6,184.00

  Effective Tax Rate: 15.0%
================================================================================
```

## Understanding the Results

### Income Types
- **W-2 Wages**: Ordinary income from employment (includes RSU vest income — FMV on vest date)
- **Interest Income**: Taxed as ordinary income
- **Short-Term Capital Gains**: Stock sold ≤ 1 year after acquisition, taxed as ordinary income
- **Long-Term Capital Gains**: Stock sold > 1 year after acquisition, taxed at preferential rates (0%, 15%, 20%)
  - **California Exception**: CA taxes ALL capital gains as ordinary income (no preferential rate)
- **Rental Income**: Net income from Schedule E (gross rents minus expenses and depreciation)

### Tax Calculations

#### Federal Tax
- **Progressive Brackets (2025)**: 10%, 12%, 22%, 24%, 32%, 35%, 37%
- **LTCG Rates**: 0% (income < $48,350), 15% (< $533,400), 20% (≥ $533,400)
- **NIIT**: 3.8% surtax on investment income when AGI > $200,000
- **Standard Deduction (2025)**: $15,000 single, $30,000 married filing jointly

#### California Tax
- **Progressive Brackets**: 1%, 2%, 4%, 6%, 8%, 9.3%, 10.3%, 11.3%, 12.3%
- **Mental Health Tax**: Additional 1% over $1,000,000
- **ALL gains taxed as ordinary income** (no preferential LTCG rate)
- **No SALT cap** (unlike federal), but state income tax NOT deductible on CA return

### Deductions

#### Federal Itemized Deductions (Schedule A)
- Mortgage interest (personal portion)
- Property taxes (personal portion)
- State income tax + CA SDI
- **SALT Cap**: $40,000 limit on state/local taxes for 2025 ($10,000 for prior years)
- **Mortgage Insurance**: Phased out for AGI > $109,000 (eliminated at high income)

#### California Itemized Deductions
- Mortgage interest (personal portion)
- Property taxes (personal portion)
- **No SALT cap**, but state income tax NOT deductible

### Rental Property (Schedule E)
- Rental income minus proportional expenses (based on % of home used for rental)
- **Depreciation**: 27.5 years for residential property
  - Method: Straight-line, mid-month convention
  - Calculation: (Purchase price × rental %) ÷ 27.5 years ÷ 12 months × months rented
- **Passive Activity Loss Rules**: If AGI > $150,000, rental losses are suspended and carry forward to future years (released when property is sold)

## Important Tax Concepts

### RSU Sales
RSUs are taxed on two separate events:

1. **At vest**: Fair market value is ordinary income → already in W-2 Box 1
2. **At sale**: Capital gain/loss on the difference between sale price and vest FMV

**Example**:
- 10 shares vest on Jan 1, 2024 @ $200/share = $2,000 ordinary income (in W-2)
- You sell on Oct 1, 2025 @ $350/share = $3,500 proceeds
- 1099-B shows: Cost basis $2,000, Proceeds $3,500, Gain $1,500 (long-term)

### ESPP Sales
- ESPP 15% discount is taxed as **ordinary income** when you sell
- **Qualifying Disposition**: Held ≥2 years from offer date AND ≥1 year from purchase
  - Discount (limited to actual gain) = ordinary income; remaining = long-term gains
- **Disqualifying Disposition**: Full discount = ordinary income; remaining based on holding period

### Wash Sales
- Loss disallowed if you buy same/similar stock within 30 days before or after the sale
- Disallowed loss is added to cost basis of replacement shares
- Handled automatically from 1099-B "Wash Sale Disallowed" column

### Mortgage Insurance Deduction
Mortgage insurance premiums are **phased out** for AGI > $109,000:
- AGI $100,000–$109,000: Partial deduction (prorated)
- AGI > $109,000: No deduction

### 2025 SALT Cap
The 2025 Schedule A raised the SALT cap from $10,000 to **$40,000** for single filers ($20,000 married filing separately). This significantly increases the deduction for high state-tax states like California.

## Frequently Asked Questions

**Q: How much tax did I pay on my stock sales?**

Look for the stock tax breakdown in the output, or calculate manually:
- Short-term gains × your marginal tax rate (ordinary income rate)
- Long-term gains × 15% (or 20% if very high income)
- Add NIIT (3.8%) if AGI > $200,000
- For California: all gains × your CA marginal rate (no preferential rate)

**Q: Why does California tax my long-term gains higher than federal?**

California does NOT have preferential capital gains rates. All gains are taxed as ordinary income using CA's progressive brackets (up to 12.3%, plus 1% mental health tax over $1M).

**Q: What if I made estimated tax payments?**

```bash
python run_annual_taxes.py --year 2025 --estimated-payments 5000
```

**Q: Can I use this for other states?**

The tool currently only supports California state tax. For other states, you'd need to add state-specific tax calculation methods to `tax_calculator.py`.

**Q: What about AMT (Alternative Minimum Tax)?**

This tool does not currently calculate AMT. If you have significant AMT triggers (like ISOs), consult a tax professional.

**Q: How do I calculate taxes for a different year?**

Prepare your CSV files with the year in the filename, then run:
```bash
python run_annual_taxes.py --year 2026
```

The tool automatically looks for `data/w2_2026.csv`, `data/1099b_2026.csv`, etc. and applies inflation-adjusted tax brackets.

**Q: What are rental passive activity loss rules?**

If your AGI exceeds $150,000, rental losses cannot offset W-2 income. They are "suspended" and carry forward to future years. They are fully released when you sell the property, or can offset rental profits in future profitable years.

## File Structure

```
tesla-tax-tool/
├── README.md                          # This file
├── tax_calculator.py                  # Core tax calculation engine
├── run_annual_taxes.py               # Annual tax calculator (command-line)
├── bonus_allocation_calculator.py    # Bonus allocation tool
├── data/                             # Your tax data CSVs (git-ignored)
│   ├── w2_YYYY.csv
│   ├── 1099b_YYYY.csv
│   ├── 1098_YYYY.csv
│   └── 1099int_YYYY.csv
└── outputs/                          # Generated reports (git-ignored)
    └── tax_liability_YYYY_*.txt
```

## Requirements

- Python 3.7+
- pandas
- yfinance
- requests
- beautifulsoup4

## Installation

```bash
pip install pandas yfinance requests beautifulsoup4
```

## Disclaimer

**This tool is for educational and estimation purposes only.** It does not constitute professional tax advice. Tax laws are complex and change frequently. Individual circumstances vary significantly.

**Always consult with a qualified CPA or tax professional** for:
- Actual tax preparation and filing
- Tax planning decisions
- Complex situations (AMT, ISOs, multiple states, etc.)
- IRS audits or disputes

Use at your own risk.

## License

MIT License - Use at your own risk
