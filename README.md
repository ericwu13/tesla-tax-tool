# Tesla Stock Tax Calculator

A comprehensive Python tool for calculating taxes on Tesla stock grants including RSUs (Restricted Stock Units) and ESPP (Employee Stock Purchase Plan) transactions, plus a bonus allocation calculator for investment planning.

## Features

### Tax Calculation Features
- **Dynamic Tax Brackets**: Automatically fetches current year tax brackets with fallback to 2025 federal rates
- **Stock Type Classification**: Automatically identifies RSUs vs ESPP from CSV data
- **Long-term vs Short-term**: Determines capital gains treatment based on holding periods
- **ESPP Tax Rules**: Implements qualifying vs disqualifying disposition rules per IRS guidelines
- **Tesla ESPP Dates**: Includes Tesla's specific ESPP offer period schedule
- **Real-time Pricing**: Fetches Tesla stock prices for accurate proceeds calculation
- **Comprehensive Reports**: Generates detailed tax reports with breakdowns by transaction type

### Bonus Allocation Calculator (NEW!)
- **Mixed Investment Planning**: Calculate proceeds from bonuses split between RSUs and ISOs
- **ISO Multiplier Effect**: Automatically applies 3x multiplier to ISO shares as specified
- **Historical Price Integration**: Uses actual Tesla stock prices on purchase dates
- **Flexible Allocation**: Support any percentage split (must total 100%)
- **Target Price Modeling**: Calculate potential proceeds at different target sale prices
- **Comprehensive Analysis**: Shows gains, returns, and investment performance metrics

## Requirements

- Python 3.7+
- pandas
- yfinance
- requests
- beautifulsoup4

## Installation

1. Clone or download this repository
2. Install required packages:
   ```bash
   pip install pandas yfinance requests beautifulsoup4
   ```

## Usage

### Tax Calculator

#### Interactive Mode (Recommended)

Run the interactive script:
```bash
python run_tax_calculator.py
```

The script will prompt you for:
- Path to your CSV file (defaults to `./data/my-tesla-stocks.csv`)
- Your ordinary income for 2025
- Sale date (defaults to today)

#### Command Line Mode

You can also use the calculator with command line arguments:
```bash
python tax_calculator.py --csv your-stock-file.csv --income 150000 --sold-date 2025-10-23 --export-csv results.csv
```

Arguments:
- `--csv`: Path to your stock CSV file
- `--income`: Your ordinary income
- `--sold-date`: Sale date (optional, defaults to today)
- `--output`: Save text report to file (optional)
- `--export-csv`: Export results to CSV file (optional)

### Bonus Allocation Calculator

#### Interactive Mode

Run the interactive bonus allocation calculator:
```bash
python bonus_allocation_calculator.py
```

The script will prompt you for:
- Bonus amount (e.g., $100,000)
- Purchase/grant date (YYYY-MM-DD format)
- RSU percentage (0-100)
- Target sale price

#### Programmatic Usage

You can also use the bonus allocation feature programmatically:
```python
from datetime import datetime
from tax_calculator import TaxCalculator

calc = TaxCalculator()
results = calc.calculate_bonus_allocation_proceeds(
    bonus_amount=100000,        # $100k bonus
    purchase_date=datetime(2024, 6, 15),
    rsu_percentage=70,          # 70% RSU
    iso_percentage=30,          # 30% ISO (will be multiplied by 3)
    target_price=500            # Target sale price
)

# Generate report
report = calc.print_bonus_allocation_report(results)
print(report)
```

#### Algorithm Details
1. **Allocation**: Splits bonus amount based on RSU/ISO percentages
2. **Share Calculation**: 
   - RSU shares = RSU allocation ÷ historical stock price on purchase date
   - ISO shares = (ISO allocation ÷ historical stock price) × 3
3. **Proceeds**: Calculates potential proceeds at target price
4. **Analysis**: Shows gains, returns, and performance metrics

### CSV File Format

Your CSV file should contain the following columns:
- `Test`: Transaction type (Grant/Purchase)
- `Symbol`: Stock symbol (TSLA)
- `Plan Type`: "Rest. Stock" for RSUs or "ESPP" for ESPP
- `Date Acquired`: Acquisition/vesting date (DD-Mon-YY format)
- `Sellable Qty.`: Number of shares
- `Expected Gain/Loss`: Expected gain or loss amount
- `Est. Market Value`: Estimated market value
- `Grant Number`: Grant identifier

## Tax Calculation Logic

### RSUs (Restricted Stock Units)
- **Basis**: Fair market value at vesting date
- **Long-term**: Holdings > 1 year from vesting qualify for capital gains rates
- **Short-term**: Holdings ≤ 1 year taxed as ordinary income

### ESPP (Employee Stock Purchase Plan)
- **Qualifying Disposition**: 
  - ≥2 years from offer date AND ≥1 year from purchase date
  - Discount treated as ordinary income (capped at actual gain)
  - Remaining gain taxed as long-term capital gains
- **Disqualifying Disposition**:
  - Does not meet qualifying requirements
  - Discount treated as ordinary income
  - Remaining gain taxed based on holding period from purchase

### Tesla ESPP Schedule
The calculator includes Tesla's ESPP offer periods:
- February 1st and August 1st start dates
- 6-month purchase periods

## Output

The calculator generates both text and CSV reports:

### Text Report
A comprehensive report including:
- Summary statistics (total shares, proceeds, gains, taxes)
- Individual transaction breakdowns
- Tax classification for each transaction
- Effective tax rates
- Tax planning notes

### CSV Export
Structured data export with columns:
- Stock_Type (RSU/ESPP)
- Grant_Number
- Acquired_Date
- Offer_Date (ESPP only)
- Shares
- Acquisition_Price
- Sold_Price
- Proceeds
- Total_Gain
- Holding_Period (Long Term/Short Term)
- Disposition_Type (Qualifying/Disqualifying for ESPP)
- Tax_Type
- Tax_Rate
- Tax_Amount
- Ordinary_Income_Portion

The CSV format is ideal for:
- Import into spreadsheet applications
- Further analysis and calculations
- Integration with accounting software
- Record keeping and audit trails

## Important Notes

⚠️ **This tool is for educational and estimation purposes only**

- Calculations are based on 2025 federal tax brackets
- State taxes are not included
- Consult a qualified tax professional for actual tax filing
- IRS rules and rates may change
- Individual tax situations may have additional complexities

## Example Output

```
TESLA STOCK TAX CALCULATION REPORT
================================================================================
Report Date: 2025-10-23 01:28:12
Ordinary Income: $150,000.00
Sale Date: 2025-10-23
Marginal Tax Rate: 24.0%
Capital Gains Rate: 15.0%

SUMMARY
----------------------------------------
Total Shares: 546.00
Total Proceeds: $239,677.62
Total Gains: $38,711.53
Total Ordinary Income: $10,443.31
Total Tax Due: $7,518.16
Effective Tax Rate: 19.42%
```

## Files

- `tax_calculator.py`: Main calculation engine and command-line interface
- `run_tax_calculator.py`: Interactive user interface
- `test_calculator.py`: Test script for validation
- `data/my-tesla-stocks.csv`: Sample CSV data
- `outputs/`: Directory containing generated reports and CSV exports

## Output Files

All generated reports and CSV files are automatically saved to the `outputs/` directory to keep the project root clean:

- **Text Reports**: `tesla_tax_report_YYYYMMDD.txt`
- **CSV Exports**: `tesla_tax_results_YYYYMMDD.csv`
- **Test Files**: `test_report_YYYYMMDD.txt`, `test_results_YYYYMMDD.csv`

## Testing

Run the test script to validate functionality:
```bash
python test_calculator.py
```

## License

This project is provided as-is for educational purposes. Use at your own risk and always consult tax professionals for actual tax preparation.