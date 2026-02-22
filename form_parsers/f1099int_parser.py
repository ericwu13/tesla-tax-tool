"""1099-INT (Interest Income) parser for extracted PDF text."""

import re
from collections import Counter
from datetime import datetime


def _find_decimal_amounts(text: str) -> list:
    """Find all dollar amounts in decimal format (requires $ and .dd)."""
    amounts = []
    for m in re.finditer(r'\$\s*([\d,]+\.\d{2})\b', text):
        cleaned = m.group(1).replace(',', '')
        try:
            val = float(cleaned)
            if val > 0:
                amounts.append(val)
        except ValueError:
            continue
    return amounts


def _sum_unique(amounts: list) -> float:
    """Sum unique values (deduplicate repeated appearances of the same amount)."""
    if not amounts:
        return 0.0
    counts = Counter(amounts)
    return sum(counts.keys())


def parse_1099int(text: str, tax_year: int = None) -> dict:
    """
    Parse 1099-INT interest income from extracted text.

    Uses multiple strategies to handle different PDF layouts:
    1. Find $ amount on the same line as "interest income"
    2. Find $ amount within several lines after "interest income" label
    3. Find $ amount immediately before "Form 1099-INT" text
    4. Find the first non-zero $ amount in the Box 1 area of the form
    """
    if tax_year is None:
        tax_year = datetime.now().year

    amounts = []
    lines = text.split('\n')

    # Strategy 1 & 2: Find "interest income" label, then look for nearby $ amount
    for i, line in enumerate(lines):
        # Match "interest income" with or without spaces (pdfplumber merges words)
        if not re.search(r'(?:1\s*)?interest\s*income', line, re.IGNORECASE):
            continue

        # Skip IRS instruction text (very long lines with few spaces)
        if len(line) > 300:
            continue

        # Look for $ amount on this line
        line_amounts = _find_decimal_amounts(line)
        if line_amounts:
            amounts.extend(line_amounts[:1])
            continue

        # Look on the next several lines — the amount can be far from the label
        # when payer address/info is between them (e.g., Mr. Cooper format)
        for offset in range(1, 8):
            if i + offset < len(lines):
                next_line = lines[i + offset]
                # Stop if we hit another box label (Box 2, 3, etc.)
                if re.search(r'^\s*(?:2|3|4)\s+\w', next_line):
                    break
                next_amounts = _find_decimal_amounts(next_line)
                if next_amounts:
                    amounts.extend(next_amounts[:1])
                    break

    # Strategy 3: "$ amount" right before "Form 1099-INT" or "Form1099-INT"
    for m in re.finditer(
        r'\$\s*([\d,]+\.\d{2})\s+\S*\s*Form\s*1099[\-\s]?INT',
        text, re.IGNORECASE
    ):
        cleaned = m.group(1).replace(',', '')
        try:
            val = float(cleaned)
            if val > 0:
                amounts.append(val)
        except ValueError:
            continue

    # Strategy 4: Look for "$ amount" right before year (e.g., "$ 23.57 2025")
    # This appears in forms where the amount and calendar year are on the same line
    for m in re.finditer(
        r'\$\s*([\d,]+\.\d{2})\s+\d{4}\b',
        text
    ):
        cleaned = m.group(1).replace(',', '')
        try:
            val = float(cleaned)
            if val > 0:
                amounts.append(val)
        except ValueError:
            continue

    total_interest = _sum_unique(amounts)

    # Extract payer name — look for lines after "PAYER'S name" label
    # Skip generic form labels and look for an actual company/bank name
    payer = ''
    for i, line in enumerate(lines):
        if re.search(r"payer.?s?\s*name", line, re.IGNORECASE):
            for offset in range(1, 6):
                if i + offset < len(lines):
                    candidate = lines[i + offset].strip()
                    if not candidate or len(candidate) < 3:
                        continue
                    # Skip: numbers-only, form labels, generic address headers
                    if re.match(r'^[\d$,.\s\-]+$', candidate):
                        continue
                    if re.search(r'payer|recipient|tin\b|postal\s*code|telephone|foreign|'
                                 r'form\s*1099|interest\s*income|box\s*\d|OMB\s*No', candidate, re.IGNORECASE):
                        continue
                    # Good sign: contains known institution keywords
                    if re.search(r'(?:bank|credit\s*union|mortgage|financial|securities|LLC|Inc|NA\b|Corp)', candidate, re.IGNORECASE):
                        payer = candidate[:80]
                        break
                    # Accept if it looks like a name (starts with uppercase, has letters)
                    if re.match(r'^[A-Z]', candidate) and len(candidate) > 5:
                        payer = candidate[:80]
                        break
            if payer:
                break

    payers = []
    if total_interest > 0:
        payers.append({
            'payer': payer,
            'interest': total_interest,
            'description': '',
        })

    return {
        'payers': payers,
        'total_interest': round(total_interest, 2),
    }
