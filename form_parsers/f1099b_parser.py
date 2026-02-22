"""1099-B (Proceeds From Broker) parser for extracted PDF text."""

import re
from datetime import datetime
from typing import List, Dict


def _parse_date(date_str: str) -> datetime:
    """Try common date formats."""
    date_str = date_str.strip()
    for fmt in ('%m/%d/%Y', '%m/%d/%y', '%Y-%m-%d', '%m-%d-%Y', '%m-%d-%y'):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _parse_amount(raw: str) -> float:
    """Parse a dollar amount string, handling negatives and parens."""
    raw = raw.strip()
    negative = False
    if raw.startswith('(') and raw.endswith(')'):
        negative = True
        raw = raw[1:-1]
    if raw.startswith('-'):
        negative = True
        raw = raw[1:]
    cleaned = re.sub(r'[\$,\s]', '', raw)
    try:
        val = float(cleaned)
        return -val if negative else val
    except ValueError:
        return 0.0


def _extract_amounts(text: str) -> list:
    """Extract all dollar amounts from a line, preserving negative (parens)."""
    amounts = []
    for m in re.finditer(r'(\(?\$?[\d,]+\.\d{2}\)?)', text):
        amounts.append(_parse_amount(m.group(1)))
    return amounts


def parse_1099b(text: str, tax_year: int = None) -> list:
    """
    Parse 1099-B transaction data from extracted text.

    Returns a list of dicts compatible with TaxCalculator stock results:
        proceeds, cost_basis, total_gain, raw_gain, wash_sale_disallowed,
        is_long_term, tax_type, capital_gain_portion, source
    """
    if tax_year is None:
        tax_year = datetime.now().year

    # Strategy 1: Summary totals (most reliable — broker-calculated totals)
    results = _parse_summary_totals(text, tax_year)
    if results:
        return results

    # Strategy 2: Individual transaction rows
    results = _parse_transaction_rows(text, tax_year)
    if results:
        return results

    # Strategy 3: Summary sections with keyword matching
    results = _parse_summary_sections(text, tax_year)
    if results:
        return results

    # Strategy 4: Transaction blocks (label: value format)
    return _parse_transaction_blocks(text, tax_year)


def _parse_summary_totals(text: str, tax_year: int) -> list:
    """Parse 'Total Short - Term' and 'Total Long - Term' summary lines.

    These appear on the 1099-B Totals Summary page and contain:
        PROCEEDS  COST BASIS  MARKET DISCOUNT  WASH SALE DISALLOWED  REALIZED GAIN/(LOSS)
    Sometimes followed by a 6th column (tax withheld).
    """
    results = []

    for term, is_long in [('Short', False), ('Long', True)]:
        pattern = re.compile(
            rf'Total\s*{term}\s*-?\s*Term\s*(.*)',
            re.IGNORECASE | re.MULTILINE
        )
        match = pattern.search(text)
        if not match:
            continue

        amounts = _extract_amounts(match.group(1))
        if len(amounts) < 5:
            continue

        proceeds = amounts[0]
        cost_basis = amounts[1]
        # amounts[2] = market discount (not used for tax calc)
        wash_sale = amounts[3]
        raw_gain = amounts[4]

        # Taxable gain = realized gain + wash sale losses disallowed
        # (disallowed losses increase taxable amount)
        taxable_gain = raw_gain + wash_sale

        if proceeds == 0 and cost_basis == 0:
            continue

        results.append(_make_result(
            datetime(tax_year, 1, 1), datetime(tax_year, 12, 31),
            proceeds, cost_basis,
            raw_gain, wash_sale, taxable_gain, is_long
        ))

    return results


def _parse_transaction_rows(text: str, tax_year: int) -> list:
    """Parse individual transaction rows from detailed 1099-B pages.

    Handles two common column orders:
      A) date_acquired  date_sold  proceeds  cost_basis  mkt_discount  wash_sale  gain/loss  [tax_wh]
      B) date_sold  date_acquired  proceeds  cost_basis  [wash_sale]  gain/loss
    """
    results = []

    # Detect column order from headers
    acquired_first = bool(re.search(
        r'DATE\s*DATE\s*\n.*?ACQUIRED.*?SOLD',
        text, re.IGNORECASE | re.DOTALL
    ))

    # Match rows: two dates followed by monetary amounts
    row_pattern = re.compile(
        r'(\d{1,2}/\d{1,2}/\d{2,4})\s*'   # date 1
        r'(\d{1,2}/\d{1,2}/\d{2,4})\s*'   # date 2
        r'(.*?)$',                          # rest of line (amounts)
        re.MULTILINE
    )

    for m in row_pattern.finditer(text):
        date1 = _parse_date(m.group(1))
        date2 = _parse_date(m.group(2))
        if date1 is None or date2 is None:
            continue

        if acquired_first:
            date_acquired, date_sold = date1, date2
        else:
            date_sold, date_acquired = date1, date2

        amounts = _extract_amounts(m.group(3))
        if len(amounts) < 2:
            continue

        proceeds = amounts[0]
        cost_basis = amounts[1]

        if acquired_first and len(amounts) >= 5:
            # Format A: proceeds, cost_basis, mkt_discount, wash_sale, gain/loss, [tax_wh]
            wash_sale = amounts[3]
            raw_gain = amounts[4]
        elif len(amounts) >= 3:
            # Format B: proceeds, cost_basis, [wash_sale], gain/loss
            if len(amounts) >= 4:
                wash_sale = amounts[2]
                raw_gain = amounts[3]
            else:
                wash_sale = 0.0
                raw_gain = amounts[2]
        else:
            raw_gain = proceeds - cost_basis
            wash_sale = 0.0

        is_long = (date_sold - date_acquired).days > 365
        taxable_gain = raw_gain + wash_sale

        results.append(_make_result(
            date_acquired, date_sold, proceeds, cost_basis,
            raw_gain, wash_sale, taxable_gain, is_long
        ))

    return results


def _parse_summary_sections(text: str, tax_year: int) -> list:
    """Parse summary-style 1099-B with separate ST/LT sections."""
    results = []

    for term_label, is_long in [('short.?term', False), ('long.?term', True)]:
        section = re.search(
            rf'({term_label}.*?)(?=(?:long|short).?term|$)',
            text, re.IGNORECASE | re.DOTALL
        )
        if not section:
            continue

        section_text = section.group(1)
        proceeds_match = re.search(r'(?:total\s*)?proceeds[^$\d]*\$?\s*([\d,]+\.\d{2})', section_text, re.IGNORECASE)
        basis_match = re.search(r'(?:total\s*)?(?:cost|basis)[^$\d]*\$?\s*([\d,]+\.\d{2})', section_text, re.IGNORECASE)
        gain_match = re.search(r'(?:total\s*)?(?:gain|loss)[^$\d]*(\(?\$?[\d,]+\.\d{2}\)?)', section_text, re.IGNORECASE)
        wash_match = re.search(r'wash\s*sale[^$\d]*\$?\s*([\d,]+\.\d{2})', section_text, re.IGNORECASE)

        if proceeds_match and basis_match:
            proceeds = _parse_amount(proceeds_match.group(1))
            cost_basis = _parse_amount(basis_match.group(1))
            raw_gain = _parse_amount(gain_match.group(1)) if gain_match else (proceeds - cost_basis)
            wash_sale = _parse_amount(wash_match.group(1)) if wash_match else 0.0
            taxable_gain = raw_gain + wash_sale

            results.append(_make_result(
                datetime(tax_year, 1, 1), datetime(tax_year, 12, 31),
                proceeds, cost_basis,
                raw_gain, wash_sale, taxable_gain, is_long
            ))

    return results


def _parse_transaction_blocks(text: str, tax_year: int) -> list:
    """Parse individually listed transactions (block format)."""
    results = []

    block_pattern = re.compile(
        r'date\s*(?:acquired|bought)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}).*?'
        r'date\s*sold[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}).*?'
        r'proceeds[:\s]*\$?\s*([\d,]+\.?\d*).*?'
        r'(?:cost|basis)[:\s]*\$?\s*([\d,]+\.?\d*)',
        re.IGNORECASE | re.DOTALL
    )

    for m in block_pattern.finditer(text):
        date_acquired = _parse_date(m.group(1))
        date_sold = _parse_date(m.group(2))
        proceeds = _parse_amount(m.group(3))
        cost_basis = _parse_amount(m.group(4))

        if date_sold is None or date_acquired is None:
            continue

        raw_gain = proceeds - cost_basis
        is_long = (date_sold - date_acquired).days > 365

        results.append(_make_result(
            date_acquired, date_sold, proceeds, cost_basis,
            raw_gain, 0.0, raw_gain, is_long
        ))

    return results


def _make_result(date_acquired, date_sold, proceeds, cost_basis,
                 raw_gain, wash_sale, taxable_gain, is_long) -> dict:
    """Build a result dict compatible with TaxCalculator stock results."""
    return {
        'stock_type': 'RSU',
        'acquired_date': date_acquired,
        'sold_date': date_sold,
        'shares': 0.0,
        'acquisition_price': 0.0,
        'sold_price': 0.0,
        'proceeds': proceeds,
        'cost_basis': cost_basis,
        'total_gain': taxable_gain,
        'raw_gain': raw_gain,
        'wash_sale_disallowed': wash_sale,
        'is_long_term': is_long,
        'tax_type': 'Long Term Capital Gains' if is_long else 'Short Term Capital Gains (Ordinary Income)',
        'tax_rate': 0,
        'tax_amount': 0,
        'ordinary_income_portion': 0,
        'capital_gain_portion': taxable_gain,
        'grant_number': 'N/A',
        'form_8949_box': '',
        'actually_sold': True,
        'source': '1099-B',
    }
