"""
E*TRADE Vesting Schedule Parser.

Parses the "ByStatus" XLSX export from E*TRADE's stock plan portal.
Reads both sheets:
  - "Sellable" sheet: past vests with cost basis (FMV at vest)
  - "Unvested" sheet: complete vest schedule with exact future dates and share counts

The Unvested sheet is the authoritative source for future vests — it has every
grant's full schedule including grants that don't appear in the Sellable sheet
(e.g., monthly-vesting grants).
"""

import math
from datetime import datetime, date
from collections import defaultdict

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


def parse_vesting_xlsx(file_path, as_of_date=None):
    """
    Parse E*TRADE ByStatus XLSX and return all vest events (past + future).

    Reads the Unvested sheet for the complete vest schedule (exact dates and
    share counts for every grant), and the Sellable sheet for cost basis data
    on past vests.

    Args:
        file_path: path to the .xlsx file
        as_of_date: date for past/future cutoff (default: today)

    Returns:
        list of dicts, each with:
            - date (str): "YYYY-MM-DD"
            - shares (float): shares vesting (pre-withholding)
            - plan_type (str): "Rest. Stock", "ESPP", etc.
            - grant_number (str)
            - grant_reason (str)
            - cost_basis_per_share (float): FMV at vest (0 for future)
            - is_future (bool)
            - record_type (str): "Grant", "Purchase", "Vest Schedule", etc.
    """
    if not HAS_PANDAS:
        raise ImportError('pandas and openpyxl are required for XLSX parsing')

    if as_of_date is None:
        as_of_date = date.today()
    elif isinstance(as_of_date, str):
        as_of_date = datetime.strptime(as_of_date, '%Y-%m-%d').date()
    elif isinstance(as_of_date, datetime):
        as_of_date = as_of_date.date()

    # Detect available sheets
    xls = pd.ExcelFile(file_path, engine='openpyxl')
    sheet_names = [s.lower() for s in xls.sheet_names]

    events = []

    # --- Read Unvested sheet (authoritative for full vest schedule) ---
    if 'unvested' in sheet_names:
        unvested_idx = sheet_names.index('unvested')
        events = _parse_unvested_sheet(xls, xls.sheet_names[unvested_idx], as_of_date)
    else:
        # Fallback: read the first sheet as Sellable + infer future vests
        events = _parse_sellable_sheet(xls, xls.sheet_names[0], as_of_date)

    # --- Enrich past events with cost basis from Sellable sheet ---
    if 'sellable' in sheet_names:
        sellable_idx = sheet_names.index('sellable')
        _enrich_with_cost_basis(events, xls, xls.sheet_names[sellable_idx])

    events.sort(key=lambda e: e['date'])
    return events


def _parse_unvested_sheet(xls, sheet_name, as_of_date):
    """
    Parse the Unvested sheet which has the complete vest schedule.

    Structure:
      - "Grant" rows: header for each grant (has Grant Number, Grant Date, etc.)
      - "Vest Schedule" rows: one per vest period (has Vest Date, Vested/Unvested Qty)
      - "Tax Withholding" rows: tax detail (skipped)
    """
    df = pd.read_excel(xls, sheet_name=sheet_name, engine='openpyxl')
    df.columns = [str(c).strip() for c in df.columns]

    events = []
    current_grant = {}  # tracks the current grant header info

    for _, row in df.iterrows():
        record_type = str(row.get('Record Type', '')).strip()

        if record_type == 'Grant':
            # Grant header row — extract grant-level info
            grant_number = _clean_grant_number(row.get('Grant Number', ''))
            grant_date = _parse_date(row.get('Grant Date', ''))
            plan_type = str(row.get('Plan Type', '')).strip()
            grant_reason = str(row.get('Grant Reason', '')).strip()
            if grant_reason == 'nan':
                grant_reason = ''

            current_grant = {
                'grant_number': grant_number,
                'grant_date': grant_date,
                'plan_type': plan_type,
                'grant_reason': grant_reason,
            }

        elif record_type == 'Vest Schedule' and current_grant:
            # Vest schedule row — extract vest date and share count
            vest_date = _parse_date(row.get('Vest Date', ''))
            if vest_date is None:
                continue

            # Determine shares: use Vested Qty for past, Unvested Qty for future
            vested_qty = _parse_float(row.get('Vested Qty.', 0))
            # The second Unvested Qty column (Unvested Qty..1) has per-vest unvested
            unvested_qty = _parse_float(row.get('Unvested Qty..1', 0))
            if unvested_qty <= 0:
                unvested_qty = _parse_float(row.get('Unvested Qty.', 0))

            shares = vested_qty if vested_qty > 0 else unvested_qty
            if shares <= 0:
                continue

            is_future = vest_date > as_of_date

            events.append({
                'date': vest_date.strftime('%Y-%m-%d'),
                'shares': shares,
                'plan_type': current_grant.get('plan_type', ''),
                'grant_number': current_grant.get('grant_number', ''),
                'grant_reason': current_grant.get('grant_reason', ''),
                'cost_basis_per_share': 0,
                'price': 0,
                'is_future': is_future,
                'record_type': record_type,
            })

        elif record_type == 'Overall Total':
            break

    return events


def _parse_sellable_sheet(xls, sheet_name, as_of_date):
    """
    Fallback: parse the Sellable sheet (only past vests) + infer future vests.
    Used when the XLSX doesn't have an Unvested sheet.
    """
    df = pd.read_excel(xls, sheet_name=sheet_name, engine='openpyxl')
    df.columns = [str(c).strip() for c in df.columns]
    col_map = _map_columns(df.columns)

    events = []

    for _, row in df.iterrows():
        record_type = str(row.get(col_map.get('record_type', ''), '')).strip()
        if record_type.lower() in ('overall total', 'total', ''):
            continue

        plan_type = str(row.get(col_map.get('plan_type', ''), '')).strip()
        date_str = row.get(col_map.get('date_acquired', ''), '')
        vest_date = _parse_date(date_str)
        if vest_date is None:
            continue

        shares = _parse_float(row.get(col_map.get('net_shares', ''), 0))
        if shares <= 0:
            shares = _parse_float(row.get(col_map.get('purchased_qty', ''), 0))
        if shares <= 0:
            shares = _parse_float(row.get(col_map.get('shares', ''), 0))

        grant_number = _clean_grant_number(row.get(col_map.get('grant_number', ''), ''))
        grant_reason = str(row.get(col_map.get('grant_reason', ''), '')).strip()
        cost_basis = _parse_float(row.get(col_map.get('cost_basis', ''), 0))

        is_future = vest_date > as_of_date

        events.append({
            'date': vest_date.strftime('%Y-%m-%d'),
            'shares': shares,
            'plan_type': plan_type,
            'grant_number': grant_number,
            'grant_reason': grant_reason if grant_reason != 'nan' else '',
            'cost_basis_per_share': cost_basis,
            'price': cost_basis if not is_future else 0,
            'is_future': is_future,
            'record_type': record_type,
        })

    return events


def _enrich_with_cost_basis(events, xls, sheet_name):
    """
    Enrich events with cost basis data from the Sellable sheet.
    Matches by grant_number + date to find FMV at vest.
    """
    df = pd.read_excel(xls, sheet_name=sheet_name, engine='openpyxl')
    df.columns = [str(c).strip() for c in df.columns]
    col_map = _map_columns(df.columns)

    # Build lookup: (grant_number, date_str) -> cost_basis
    cost_lookup = {}
    for _, row in df.iterrows():
        record_type = str(row.get(col_map.get('record_type', ''), '')).strip()
        if record_type.lower() in ('overall total', 'total', ''):
            continue

        grant_number = _clean_grant_number(row.get(col_map.get('grant_number', ''), ''))
        vest_date = _parse_date(row.get(col_map.get('date_acquired', ''), ''))
        cost_basis = _parse_float(row.get(col_map.get('cost_basis', ''), 0))

        if vest_date and cost_basis > 0:
            key = (grant_number, vest_date.strftime('%Y-%m-%d'))
            cost_lookup[key] = cost_basis

    # Apply to events
    for event in events:
        if event['cost_basis_per_share'] <= 0:
            key = (event['grant_number'], event['date'])
            cb = cost_lookup.get(key, 0)
            if cb > 0:
                event['cost_basis_per_share'] = cb
                if not event['is_future']:
                    event['price'] = cb


def _clean_grant_number(val):
    """Clean grant number: handle pandas float-to-string artifacts."""
    s = str(val).strip()
    if s.endswith('.0'):
        s = s[:-2]
    if s == 'nan':
        s = ''
    return s


def _map_columns(columns):
    """Map expected column purposes to actual column names in the DataFrame."""
    col_map = {}
    for col in columns:
        cl = col.lower()
        if 'record' in cl and 'type' in cl:
            col_map['record_type'] = col
        elif 'plan' in cl and 'type' in cl:
            col_map['plan_type'] = col
        elif 'date' in cl and 'acq' in cl:
            col_map['date_acquired'] = col
        elif cl == 'net shares' or ('net' in cl and 'share' in cl):
            col_map['net_shares'] = col
        elif 'purchased' in cl and 'qty' in cl:
            col_map['purchased_qty'] = col
        elif 'sellable' in cl and 'qty' in cl:
            col_map['shares'] = col
        elif 'grant' in cl and 'number' in cl:
            col_map['grant_number'] = col
        elif 'grant' in cl and 'date' in cl and 'fmv' not in cl:
            col_map['grant_date'] = col
        elif 'grant' in cl and 'reason' in cl:
            col_map['grant_reason'] = col
        elif 'vest' in cl and 'period' in cl:
            col_map['vest_period'] = col
        elif 'cost' in cl and 'basis' in cl and 'per' in cl:
            col_map['cost_basis'] = col
    return col_map


def _parse_date(date_str):
    """Parse date from various formats."""
    if date_str is None:
        return None
    if hasattr(date_str, 'date'):
        return date_str.date()
    s = str(date_str).strip()
    if not s or s == 'nan' or s == 'NaT':
        return None
    for fmt in ('%d-%b-%Y', '%m/%d/%Y', '%Y-%m-%d', '%b %d, %Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def _parse_float(val):
    """Safely parse a float from potentially messy cell data."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return 0.0 if math.isnan(val) else float(val)
    s = str(val).replace('$', '').replace(',', '').strip()
    if s == '--' or s == 'nan' or not s:
        return 0.0
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0
