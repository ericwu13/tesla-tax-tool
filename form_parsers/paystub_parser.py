"""
Paystub PDF Parser (Workday format — Tesla, Inc.)

Extracts YTD totals from a Workday paystub PDF for mid-year tax projection.
Designed for Tesla's format but uses flexible patterns that should handle
variations in Workday layouts.

Key fields extracted:
  - pay_date: date the paycheck was issued
  - ytd_gross_wages: YTD gross from Pay Summary
  - ytd_rsu_income: YTD RSU/equity income from Earnings section (0 if none)
  - ytd_fed_withheld: YTD Federal Income Tax from Taxes section
  - ytd_state_withheld: YTD state income tax from Taxes section
  - pay_frequency: Biweekly, Semi-Monthly, Monthly, Weekly
  - ytd_401k: YTD 401k contributions (pre-tax)
  - ytd_espp: YTD ESPP contributions
"""

import re

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False


# Earnings line items that represent RSU/equity income
_RSU_KEYWORDS = re.compile(
    r'(?:RSU|Restricted\s*Stock|Stock\s*Award|Equity|RSA|Vest)',
    re.IGNORECASE
)


def parse_paystub(file_path):
    """
    Parse a Workday paystub PDF and return extracted YTD data.

    Args:
        file_path: path to the PDF file

    Returns:
        dict with keys:
            - pay_date (str): "YYYY-MM-DD"
            - period_end (str): "YYYY-MM-DD"
            - pay_frequency (str): e.g. "Biweekly"
            - ytd_gross_wages (float)
            - ytd_fit_taxable_wages (float)
            - ytd_rsu_income (float)
            - ytd_base_salary (float)
            - ytd_fed_withheld (float)
            - ytd_state_withheld (float)
            - ytd_medicare (float)
            - ytd_social_security (float)
            - ytd_401k (float)
            - ytd_espp (float)
            - employer (str)
            - state (str): two-letter state code
    """
    if not HAS_PDFPLUMBER:
        raise ImportError('pdfplumber is required for paystub PDF parsing')

    with pdfplumber.open(file_path) as pdf:
        text = '\n'.join(page.extract_text() or '' for page in pdf.pages)

    result = {
        'pay_date': '',
        'period_end': '',
        'pay_frequency': '',
        'ytd_gross_wages': 0.0,
        'ytd_fit_taxable_wages': 0.0,
        'ytd_rsu_income': 0.0,
        'ytd_base_salary': 0.0,
        'ytd_fed_withheld': 0.0,
        'ytd_state_withheld': 0.0,
        'ytd_medicare': 0.0,
        'ytd_social_security': 0.0,
        'ytd_401k': 0.0,
        'ytd_espp': 0.0,
        'employer': '',
        'state': '',
    }

    # --- Header fields ---
    result['pay_date'] = _extract_date(text, r'Pay\s*Date\s+(\d{2}/\d{2}/\d{4})')
    result['period_end'] = _extract_date(text, r'Period\s*End\s*Date\s+(\d{2}/\d{2}/\d{4})')

    freq_match = re.search(r'Pay\s*Frequency\s+(\w+)', text)
    if freq_match:
        result['pay_frequency'] = freq_match.group(1)

    # Employer: first line that looks like a company name (before address)
    employer_match = re.search(r'^([\w][\w\s,\.]+(?:Inc|Corp|LLC|Ltd|Co)[\.]?)', text, re.MULTILINE)
    if employer_match:
        result['employer'] = employer_match.group(1).strip()

    # State: detect from state income tax line or location
    state_match = re.search(r'(\w{2})\s+State\s+Income\s+Tax', text)
    if state_match:
        result['state'] = state_match.group(1).upper()
    else:
        loc_match = re.search(r'Location\s+\S+-(\w{2})-', text)
        if loc_match:
            result['state'] = loc_match.group(1).upper()

    # --- Pay Summary section (YTD Gross) ---
    # Look for "YTD" row in Pay Summary: YTD $29,844.89 $26,273.00 ...
    ytd_summary = re.search(
        r'YTD\s+\$?([\d,]+\.\d{2})\s+\$?([\d,]+\.\d{2})',
        text
    )
    if ytd_summary:
        result['ytd_gross_wages'] = _parse_dollar(ytd_summary.group(1))
        result['ytd_fit_taxable_wages'] = _parse_dollar(ytd_summary.group(2))

    # --- Taxes section ---
    result['ytd_fed_withheld'] = _extract_ytd_tax(text, r'Federal\s*Income\s*Tax')
    result['ytd_medicare'] = _extract_ytd_tax(text, r'(?:Employee\s*)?Medicare')
    result['ytd_social_security'] = _extract_ytd_tax(text, r'Social\s*Security\s*Employee\s*Tax?')

    # State income tax — try state-specific first, then generic
    state_tax = _extract_ytd_tax(text, r'\w{2}\s+State\s+Income\s+Tax')
    if state_tax == 0:
        state_tax = _extract_ytd_tax(text, r'State\s+Income\s+Tax')
    result['ytd_state_withheld'] = state_tax

    # --- Earnings section (RSU + base salary) ---
    _parse_earnings(text, result)

    # --- Deductions section (401k, ESPP) ---
    result['ytd_401k'] = _extract_ytd_deduction(text, r'401[kK](?!\s*/)')
    result['ytd_espp'] = _extract_ytd_deduction(text, r'ESPP')

    return result


def _extract_date(text, pattern):
    """Extract a date matching pattern and convert to YYYY-MM-DD."""
    m = re.search(pattern, text)
    if m:
        parts = m.group(1).split('/')
        if len(parts) == 3:
            return f'{parts[2]}-{parts[0]}-{parts[1]}'
    return ''


def _parse_dollar(s):
    """Parse a dollar string like '29,844.89' to float."""
    return float(s.replace(',', '').replace('$', ''))


def _extract_ytd_tax(text, tax_pattern):
    """
    Extract YTD amount for a tax line item.
    Tax lines look like: Federal Income Tax $1,249.37 $5,157.83
    The second dollar amount is YTD.
    """
    pattern = tax_pattern + r'\s+\$?([\d,]+\.\d{2})\s+\$?([\d,]+\.\d{2})'
    m = re.search(pattern, text)
    if m:
        return _parse_dollar(m.group(2))  # YTD is the second value
    return 0.0


def _extract_ytd_deduction(text, deduction_pattern):
    """
    Extract YTD employee amount for a deduction line item.
    Deduction lines: 401k  Yes  $890.77  $2,895.01  $0.00  $0.00
    May have extra words: ESPP Overlap  No  $1,113.46  $4,453.84 ...
    Employee YTD is the second dollar amount.
    """
    pattern = deduction_pattern + r'[\w\s]*?(?:Yes|No)\s+\$?([\d,]+\.\d{2})\s+\$?([\d,]+\.\d{2})'
    m = re.search(pattern, text)
    if m:
        return _parse_dollar(m.group(2))  # Employee YTD
    return 0.0


def _parse_earnings(text, result):
    """
    Parse the Earnings section to find base salary and RSU income YTD.

    Earnings lines look like:
        Salary 80.000000 $92.7885 $7,423.08 $25,980.78
        RSU Income                           $50,000.00 $50,000.00
    """
    # Find all lines with dollar amounts in the Earnings section
    # The section is between "Earnings" and "Deductions" (or "Total Hours")
    earnings_match = re.search(
        r'Earnings\s*\n(.*?)(?:Total\s*Hours|Deductions)',
        text,
        re.DOTALL
    )
    if not earnings_match:
        return

    earnings_text = earnings_match.group(1)

    for line in earnings_text.split('\n'):
        line = line.strip()
        if not line:
            continue

        # Extract all dollar amounts from the line
        amounts = re.findall(r'\$([\d,]+\.\d{2})', line)
        if not amounts:
            continue

        # The last dollar amount on an earnings line is YTD
        ytd_amount = _parse_dollar(amounts[-1])

        # Check if this is an RSU/equity line
        if _RSU_KEYWORDS.search(line):
            result['ytd_rsu_income'] += ytd_amount
        # Check if this is base salary
        elif re.match(r'Salary\b', line, re.IGNORECASE):
            result['ytd_base_salary'] = ytd_amount
