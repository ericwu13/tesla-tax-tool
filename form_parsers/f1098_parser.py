"""1098 (Mortgage Interest Statement) parser for extracted PDF text."""

import re
from datetime import datetime


def _find_all_amounts(text: str, patterns: list) -> list:
    """Find all dollar amounts matching any of the patterns."""
    amounts = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE | re.DOTALL):
            raw = match.group(1)
            cleaned = re.sub(r'[\$,\s]', '', raw)
            try:
                val = float(cleaned)
                if val > 0:
                    amounts.append(val)
            except ValueError:
                continue
    return amounts


def _sum_amounts(text: str, patterns: list) -> float:
    """Find all matching amounts and return their sum, deduplicating."""
    amounts = _find_all_amounts(text, patterns)
    if not amounts:
        return 0.0
    # Deduplicate: the same value often appears multiple times
    # (Copy B, escrow statement, and Box line all show the same amount).
    # Group by value and count occurrences. If a value appears N times
    # and there are N/copies_per_form copies, it's likely one form.
    # Heuristic: count unique values, each unique value = one form.
    from collections import Counter
    counts = Counter(amounts)
    # Each 1098 form prints the same value ~2-3 times (escrow stmt + Box 1 + Copy B).
    # If a value appears many times, it's still one form.
    # Different values = different servicer periods → sum them.
    return sum(counts.keys())


def parse_1098(text: str, tax_year: int = None) -> dict:
    """
    Parse 1098 mortgage data from extracted text.

    Handles PDFs with multiple 1098 forms (e.g., loan was transferred
    between servicers). Sums values across all forms found.
    """
    if tax_year is None:
        tax_year = datetime.now().year

    # Box 1: Mortgage interest — find all occurrences and sum unique values
    # The "INTEREST PAID:" line from escrow statements is the cleanest source.
    # The "1 Mortgage interest received" Box 1 line is also captured.
    mortgage_interest = _sum_amounts(text, [
        r'INTEREST\s*PAID:\s*\$\s*([\d,]+\.\d{2})',
        r'(?:mortgage\s*interest\s*received|box\s*1)[^$\d]*\$\s*([\d,]+\.\d{2})',
    ])

    # Box 2: Outstanding mortgage principal — use the latest (largest) balance
    principals = _find_all_amounts(text, [
        r'(?:outstanding\s*(?:mortgage\s*)?principal|box\s*2)[^$\d]*\$\s*([\d,]+\.\d{2})',
        r'(?:BEG|ENDING)\s*BAL:\s*\$\s*([\d,]+\.\d{2})',
    ])
    outstanding_principal = max(principals) if principals else 0.0

    # Box 5: Mortgage insurance premiums — sum across servicers
    mortgage_insurance = _sum_amounts(text, [
        r'MORTGAGE\s*INSURANCE:\s*\$\s*([\d,]+\.\d{2})',
        r'(?:mortgage\s*insurance\s*premiums|box\s*5)[^$\d]*\$\s*([\d,]+\.\d{2})',
    ])

    # Property taxes from escrow disbursements — sum across servicers
    property_taxes = _sum_amounts(text, [
        r'PROPERTY\s*TAXES:\s*\$\s*([\d,]+\.\d{2})',
        r'(?:property\s*tax(?:es)?|real\s*estate\s*tax)[^$\d]*\$\s*([\d,]+\.\d{2})',
    ])

    # Lender name(s) — extract company name from escrow statement header
    # Format: "TSANG YUNG WU  Nationstar Mortgage LLC d/b/a Mr. Cooper"
    # The company name typically contains LLC, Inc, Mortgage, Bank, etc.
    lenders = []
    for m in re.finditer(r'ANNUAL\s*ESCROW.*?\n\s*(.+?)(?:\s{2,}|\n)', text, re.IGNORECASE):
        line = m.group(1).strip()
        # Try to extract company name (starts at LLC/Inc/Mortgage/Bank keyword context)
        co_match = re.search(
            r'((?:\S+\s*)?(?:Mortgage|Bank|Lending|Financial|Credit\s*Union)\b.*|'
            r'(?:\S+\s*)?(?:LLC|Inc|Corp)\b.*)',
            line, re.IGNORECASE)
        if co_match:
            name = co_match.group(1).strip()[:80]
        else:
            name = line[:80]
        if name and name not in lenders and not re.match(r'^[\d$,.\s]+$', name):
            lenders.append(name)
    if not lenders:
        m = re.search(r"(?:lender|recipient|servicer).s?\s*(?:name)?\s*[:\-]?\s*(.+)", text, re.IGNORECASE)
        if m:
            lenders.append(m.group(1).strip()[:80])
    lender = ' / '.join(lenders) if lenders else ''

    return {
        'lender': lender,
        'tax_year': tax_year,
        'mortgage_interest': mortgage_interest,
        'outstanding_principal': outstanding_principal,
        'origination_date': '',
        'mortgage_insurance': mortgage_insurance,
        'property_taxes': property_taxes,
        'purchase_price': 0.0,
        'purchase_date': '',
        'rental_start_date': '',
    }
