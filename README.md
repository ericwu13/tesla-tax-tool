# Tesla Tax Calculator

![version](https://img.shields.io/badge/version-2.0.0-blue)
![python](https://img.shields.io/badge/python-3.7%2B-blue)
![build](https://img.shields.io/badge/build-passing-brightgreen)
![tests](https://img.shields.io/badge/tests-passing-brightgreen)
![platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![license](https://img.shields.io/badge/license-MIT-green)

A comprehensive tax calculator for computing federal and California state income tax liability. Two modes: **Year-End Filing** (upload PDF tax forms) and **Mid-Year Estimate** (project full-year taxes from partial-year data). All data stays local.

Includes a **web UI** with drag-and-drop upload, automatic form parsing, and a **standalone Windows .exe** for distribution without Python.

## Features

### Year-End Filing
- **PDF Auto-Detection**: Upload tax form PDFs — forms are identified and parsed automatically
- **Consolidated 1099 Support**: Handles multi-form PDFs (e.g., E*TRADE/Schwab consolidated 1099)
- **Federal Income Tax**: Progressive bracket calculation with 2025+ brackets, MFJ/single/MFS/HoH filing statuses
- **California State Tax**: Progressive brackets, all gains taxed as ordinary income
- **Stock Sales (1099-B)**: Short-term and long-term capital gains, wash sale adjustments, RSU sales
- **Itemized Deductions (Schedule A)**: Mortgage interest, property taxes, SALT cap ($40k for 2025+), mortgage insurance phaseout
- **Net Investment Income Tax (NIIT)**: 3.8% surtax when AGI > $200,000

### Mid-Year Estimate (v2.0)
- **Paystub PDF Parsing**: Upload a Workday paystub to auto-populate YTD income, withholding, and deductions
- **E*TRADE Vesting Schedule**: Upload ByStatus XLSX — reads exact future vest dates and share counts from the Unvested sheet (quarterly, monthly, cliff grants)
- **Projection Engine**: Extrapolates base salary linearly, adds event-driven RSU income from vesting schedule
- **Live Stock Price**: Auto-fetches current TSLA price via yfinance for RSU income projections
- **Live Projected Preview**: Shows extrapolated full-year estimates as you enter data
- **Planned Stock Sales**: Add expected sales with estimated proceeds and cost basis

### General
- **Standalone .exe**: Single-file Windows executable — double-click and go

## Quick Start

### Option A: Web UI

```bash
pip install -r requirements.txt
python web_app.py
```

Open `http://localhost:8080`, drag and drop your PDF tax forms, and click Calculate.

### Option B: Standalone .exe (no Python needed)

Download `tax_app.exe`, double-click it, and a browser opens automatically.

To build the .exe yourself:

```bash
pip install pyinstaller
pyinstaller tax_app.spec
# Output: dist/tax_app.exe
```

## Usage

### Year-End Filing
1. Start the app (web UI or .exe)
2. Drag and drop your PDF tax forms (W-2, 1099-B, 1099-INT, 1098)
3. Review and edit parsed values if needed
4. Set filing status, tax year, and any manual overrides
5. Click **Calculate** to see federal + CA tax results

### Mid-Year Estimate
1. Switch to **Mid-Year Estimate** mode
2. Upload your latest paystub PDF (or enter YTD data manually)
3. Upload your E*TRADE ByStatus XLSX for vesting schedule
4. Add any planned stock sales
5. Click **Calculate** to see projected full-year federal + CA tax results

The app returns:
- Full text report with line-by-line breakdown
- Federal summary (AGI, taxable income, tax, withholdings, refund/amount due)
- California summary (if state wages detected)
- Projection assumptions (mid-year mode)
- Parsed input details for verification

## PDF Parsing

The scanner (`form_scanner.py`) uses pdfplumber for text extraction with an OCR fallback (pytesseract) for scanned documents. It auto-detects form types by keyword signatures and dispatches to the appropriate parser.

Parsers are designed for **scalability** — they handle merged words, varied spacing, multi-line labels, and different institution formats rather than hardcoding to one PDF layout.

| Form | Parser | Key Fields Extracted |
|------|--------|---------------------|
| W-2 | `w2_parser.py` | Wages, federal/state withholding, 401k, HSA |
| 1099-B | `f1099b_parser.py` | Proceeds, cost basis, gain/loss, short/long term |
| 1099-INT | `f1099int_parser.py` | Interest income by payer |
| 1098 | `f1098_parser.py` | Mortgage interest, property tax, insurance premiums |
| Paystub | `paystub_parser.py` | YTD gross wages, withholding, RSU income, 401k, ESPP |
| E*TRADE XLSX | `vesting_parser.py` | Full vest schedule with exact future dates and share counts |

## File Structure

```
tesla-tax-tool/
├── web_app.py                  # Flask web UI entry point
├── projection_engine.py        # Mid-year projection (base salary + RSU extrapolation)
├── build_exe.py                # PyInstaller entry point (auto-opens browser)
├── tax_app.spec                # PyInstaller build config
├── tax_app.py                  # CLI entry point + build_tax_inputs()
├── tax_calculator.py           # Core tax calculation engine
├── form_scanner.py             # PDF text extraction + form type detection
├── form_parsers/               # Per-form-type parsers
│   ├── __init__.py
│   ├── w2_parser.py
│   ├── f1099b_parser.py
│   ├── f1099int_parser.py
│   ├── f1098_parser.py
│   ├── paystub_parser.py       # Workday paystub PDF parser
│   └── vesting_parser.py       # E*TRADE ByStatus XLSX parser
├── templates/
│   └── index.html              # Web UI template (mode toggle + mid-year panel)
├── requirements.txt            # Python dependencies
└── dist/                       # Built .exe output (git-ignored)
```

## Tax Rules Reference

### Federal Tax (2025)
- **Brackets**: 10%, 12%, 22%, 24%, 32%, 35%, 37%
- **Standard Deduction**: $15,000 single / $30,000 MFJ
- **LTCG Rates**: 0%, 15%, 20% (based on income thresholds)
- **NIIT**: 3.8% on investment income when AGI > $200,000
- **SALT Cap**: $40,000 ($20,000 MFS)

### California Tax
- **Brackets**: 1%, 2%, 4%, 6%, 8%, 9.3%, 10.3%, 11.3%, 12.3%
- **Mental Health Tax**: Additional 1% over $1,000,000
- **All capital gains taxed as ordinary income** (no preferential rate)

### Mortgage Insurance Deduction
- Expired after 2021, reinstated 2026+ (One Big Beautiful Bill Act)
- Phaseout: $100k–$110k AGI

## Building the .exe

```bash
pip install pyinstaller
pyinstaller tax_app.spec
```

Output: `dist/tax_app.exe` (~56 MB). Console window stays open for error visibility — change `console=True` to `console=False` in `tax_app.spec` for a windowless build.

## Requirements

- Python 3.7+
- See `requirements.txt`

```bash
pip install -r requirements.txt
```

## Disclaimer

**This tool is for educational and estimation purposes only.** It does not constitute professional tax advice. Always consult a qualified CPA or tax professional for actual tax preparation and filing.

## License

MIT License — Use at your own risk
