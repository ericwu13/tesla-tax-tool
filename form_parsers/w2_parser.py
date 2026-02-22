"""W-2 (Wage and Tax Statement) parser for extracted PDF text."""

import re
from datetime import datetime


def _find_decimal_amounts(text, start_pos, max_lines=2):
    """Find all decimal monetary amounts (NNN.NN) in the next few lines."""
    rest = text[start_pos:]
    lines = rest.split('\n', max_lines + 1)
    search_text = '\n'.join(lines[:max_lines])
    return re.findall(r'(\d[\d,]*\.\d{2})\b', search_text)


def _parse_paired_row(text, label_pattern, num_values=2):
    """Extract values from the line following a label pattern.

    W-2 PDFs commonly have labels on one line and values on the next:
        1 Wages, tips, other compensation 2 Federal income tax withheld
        XXX-XX-8849 312916.19 64975.95

    The decimal requirement (NNN.NN) skips box numbers, SSN fragments, etc.
    """
    match = re.search(label_pattern, text, re.IGNORECASE)
    if not match:
        return [0.0] * num_values

    amounts = _find_decimal_amounts(text, match.end(), max_lines=2)
    result = []
    for i in range(num_values):
        if i < len(amounts):
            result.append(float(amounts[i].replace(',', '')))
        else:
            result.append(0.0)
    return result


def _find_amount(text: str, patterns: list) -> float:
    """Find a dollar amount near keyword patterns (fallback for same-line layouts)."""
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            raw = match.group(1)
            cleaned = re.sub(r'[\$,\s]', '', raw)
            try:
                return float(cleaned)
            except ValueError:
                continue
    return 0.0


def parse_w2(text: str, tax_year: int = None) -> dict:
    """
    Parse W-2 fields from extracted text.

    Handles two common PDF layouts:
      1. Paired-row: labels on one line, values on the next (most common)
      2. Same-line: label and value on the same line
    """
    if tax_year is None:
        tax_year = datetime.now().year

    # --- Paired-row extraction (primary) ---

    # Boxes 1 & 2: Wages and federal withholding
    wages, fed_withheld = _parse_paired_row(
        text, r'wages.*?compensation.*?federal\s*income\s*tax\s*withheld')

    # Boxes 3 & 4: Social security wages and tax
    ss_wages, ss_tax = _parse_paired_row(
        text, r'social\s*security\s*wages.*?social\s*security\s*tax\s*withheld')

    # Boxes 5 & 6: Medicare wages and tax
    medicare_wages, medicare_tax = _parse_paired_row(
        text, r'medicare\s*wages.*?medicare\s*tax\s*withheld')

    # Boxes 16 & 17: State wages and state income tax
    state_wages, state_tax = _parse_paired_row(
        text, r'(?:16\s*)?state\s*wages.*?(?:17\s*)?state\s*income\s*tax')

    # --- Fallback: same-line patterns (require decimal amounts) ---

    if wages == 0:
        wages = _find_amount(text, [
            r'(?:wages[,.]?\s*tips[,.]?\s*other\s*compensation)[^$\d]*\$?\s*(\d[\d,]*\.\d{2})',
        ])
    if fed_withheld == 0:
        fed_withheld = _find_amount(text, [
            r'(?:federal\s*income\s*tax\s*withheld)[^$\d]*\$?\s*(\d[\d,]*\.\d{2})',
        ])
    if ss_wages == 0:
        ss_wages = _find_amount(text, [
            r'(?:social\s*security\s*wages)[^$\d]*\$?\s*(\d[\d,]*\.\d{2})',
        ])
    if medicare_wages == 0:
        medicare_wages = _find_amount(text, [
            r'(?:medicare\s*wages)[^$\d]*\$?\s*(\d[\d,]*\.\d{2})',
        ])
    if state_wages == 0:
        state_wages = _find_amount(text, [
            r'(?:state\s*wages)[^$\d]*\$?\s*(\d[\d,]*\.\d{2})',
        ])
    if state_tax == 0:
        state_tax = _find_amount(text, [
            r'(?:state\s*income\s*tax)[^$\d]*\$?\s*(\d[\d,]*\.\d{2})',
        ])

    # --- Box 12 codes: D=401k, W=HSA (code letter followed by amount) ---

    box12d_401k = _find_amount(text, [
        r'\bD\s*\$?\s*(\d[\d,]*\.\d{2})',
    ])
    box12w_hsa = _find_amount(text, [
        r'\bW\s*\$?\s*(\d[\d,]*\.\d{2})',
    ])

    # --- State abbreviation (Box 15) ---
    # Look for 2-letter state code before an EIN-like number on the values line
    state = ''
    state_match = re.search(r'\n\s*([A-Z]{2})\s*\d{2,3}[\-\d]+\s*\d', text)
    if state_match:
        state = state_match.group(1)
    else:
        # Fallback: look after "State" label on the next line
        state_match = re.search(
            r'(?:15\s*[Ss]tate|[Ss]tate\s*[Ee]mployer).*?\n\s*([A-Z]{2})\b', text)
        if state_match:
            state = state_match.group(1)

    # --- Employer name ---
    employer = ''
    emp_match = re.search(r"[Ee]mployer.s?\s*name.*?\n", text)
    if emp_match:
        # Employer name is typically a few lines after the label
        # (the next line is usually box values). Skip numeric-only lines.
        rest = text[emp_match.end():]
        for line in rest.split('\n')[:5]:
            line = line.strip()
            if line and not re.match(r'^[\d,.\s$\-]+$', line) and 'box' not in line.lower():
                employer = line[:80]
                break

    return {
        'tax_year': tax_year,
        'employer': employer,
        'wages': wages,
        'federal_tax_withheld': fed_withheld,
        'ss_wages': ss_wages,
        'ss_tax_withheld': ss_tax,
        'medicare_wages': medicare_wages,
        'medicare_tax_withheld': medicare_tax,
        'box12d_401k': box12d_401k,
        'box12w_hsa': box12w_hsa,
        'state': state,
        'state_wages': state_wages,
        'state_tax_withheld': state_tax,
    }
