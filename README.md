# Tesla Stock Tax Calculator

A comprehensive Python tool for calculating taxes on Tesla stock grants including RSUs (Restricted Stock Units) and ESPP (Employee Stock Purchase Plan) transactions.

## Features

- **Tax Bracket Calculation**: Uses 2025 federal tax brackets to determine marginal and capital gains tax rates
- **Stock Type Classification**: Automatically identifies RSUs vs ESPP from CSV data
- **Long-term vs Short-term**: Determines capital gains treatment based on holding periods
- **ESPP Tax Rules**: Implements qualifying vs disqualifying disposition rules per IRS guidelines
- **Tesla ESPP Dates**: Includes Tesla's specific ESPP offer period schedule
- **Real-time Pricing**: Fetches Tesla stock prices for accurate proceeds calculation
- **Comprehensive Reports**: Generates detailed tax reports with breakdowns by transaction type

## Requirements

- Python 3.7+
- pandas
- yfinance
- requests

## Installation

1. Clone or download this repository
2. Install required packages:
   ```bash
   pip install pandas yfinance requests
   ```

## Usage

### Interactive Mode (Recommended)

Run the interactive script:
```bash
python run_tax_calculator.py
```

The script will prompt you for:
- Path to your CSV file (defaults to `my-tesla-stocks.csv`)
- Your ordinary income for 2025
- Sale date (defaults to today)

### Command Line Mode

You can also use the calculator with command line arguments:
```bash
python tax_calculator.py --csv your-stock-file.csv --income 150000 --sold-date 2025-10-23
```

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

The calculator generates a comprehensive report including:
- Summary statistics (total shares, proceeds, gains, taxes)
- Individual transaction breakdowns
- Tax classification for each transaction
- Effective tax rates
- Tax planning notes

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
- `my-tesla-stocks.csv`: Sample CSV data
- `data/my-tesla-stocks.csv`: Alternative location for CSV data

## Testing

Run the test script to validate functionality:
```bash
python test_calculator.py
```

## License

This project is provided as-is for educational purposes. Use at your own risk and always consult tax professionals for actual tax preparation.