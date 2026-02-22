"""
Mid-Year Tax Projection Engine.

Projects full-year income, withholding, and deductions from mid-year data,
then outputs a dict compatible with TaxCalculator (same shape as build_tax_inputs).

Key design decisions:
  - Base salary is extrapolated linearly (reliable)
  - RSU income is event-driven (not extrapolated) because vests are lumpy
  - Withholding uses federal supplemental rate (22%) and CA supplemental rate (10.23%)
  - Capital gains come from user's planned sales (manual entry)
"""

from datetime import datetime, date


# Federal supplemental withholding rate
FED_SUPPLEMENTAL_RATE = 0.22
# California supplemental withholding rate
CA_SUPPLEMENTAL_RATE = 0.1023


def _year_fraction(pay_date, tax_year):
    """Calculate fraction of the tax year elapsed as of pay_date."""
    if isinstance(pay_date, str):
        pay_date = datetime.strptime(pay_date, '%Y-%m-%d').date()
    elif isinstance(pay_date, datetime):
        pay_date = pay_date.date()

    year_start = date(tax_year, 1, 1)
    year_end = date(tax_year, 12, 31)
    total_days = (year_end - year_start).days + 1  # 365 or 366
    elapsed = (pay_date - year_start).days + 1
    elapsed = max(1, min(elapsed, total_days))
    return elapsed / total_days


def _is_in_tax_year(event, tax_year):
    """Check if an event's date falls within the tax year."""
    event_date = event.get('date', '')
    if isinstance(event_date, str) and len(event_date) >= 4:
        return event_date[:4] == str(tax_year)
    return False


def _sum_future_rsu_income(vesting_events, estimated_stock_price, tax_year):
    """Calculate projected income from future RSU vests within the tax year."""
    future_income = 0.0
    for event in vesting_events:
        if (event.get('is_future', False)
                and _is_in_tax_year(event, tax_year)
                and event.get('plan_type', '').lower() in ('rest. stock', 'rsu', 'restricted stock')):
            shares = float(event.get('shares', 0))
            price = float(event.get('price', 0)) or estimated_stock_price
            future_income += shares * price
    return future_income


def _sum_future_espp_discount(vesting_events, estimated_stock_price, tax_year):
    """Estimate ESPP taxable discount from future purchase events within the tax year."""
    discount = 0.0
    for event in vesting_events:
        if (event.get('is_future', False)
                and _is_in_tax_year(event, tax_year)
                and event.get('plan_type', '').lower() in ('espp',)):
            shares = float(event.get('shares', 0))
            cost_basis_per_share = float(event.get('cost_basis_per_share', 0))
            price = float(event.get('price', 0)) or estimated_stock_price
            if cost_basis_per_share > 0:
                discount += shares * (price - cost_basis_per_share)
            else:
                discount += shares * price * 0.15
    return max(0.0, discount)


def project_full_year(paystub_data, vesting_events, user_inputs):
    """
    Project full-year tax values from mid-year data.

    Args:
        paystub_data: dict with keys:
            - ytd_gross_wages (float): total YTD gross wages from paystub
            - ytd_rsu_income (float): YTD RSU income included in gross wages
            - ytd_fed_withheld (float): YTD federal tax withheld
            - ytd_state_withheld (float): YTD state tax withheld
            - pay_date (str): date of the paystub, "YYYY-MM-DD"
        vesting_events: list of dicts with keys:
            - date (str): vest date
            - shares (float): number of shares
            - plan_type (str): "Rest. Stock", "ESPP", etc.
            - is_future (bool): whether this vest hasn't happened yet
            - price (float, optional): FMV at vest for past events
            - cost_basis_per_share (float, optional): for ESPP
        user_inputs: dict with keys:
            - filing_status (str)
            - tax_year (int)
            - estimated_stock_price (float)
            - planned_sales (list of dicts): [{proceeds, cost_basis, is_long_term}]
            - estimated_interest (float)
            - mortgage_interest (float)
            - property_taxes (float)
            - rental_pct (float): 0-1
            - estimated_payments (float)

    Returns:
        (projected_inputs, assumptions) where:
            projected_inputs: dict compatible with TaxCalculator (same shape as build_tax_inputs)
            assumptions: dict describing what was projected and how
    """
    tax_year = int(user_inputs.get('tax_year', datetime.now().year))
    pay_date = paystub_data.get('pay_date', '')
    estimated_stock_price = float(user_inputs.get('estimated_stock_price', 0))

    # Year fraction for linear extrapolation
    frac = _year_fraction(pay_date, tax_year)

    # --- Income projections ---

    ytd_gross = float(paystub_data.get('ytd_gross_wages', 0))
    ytd_rsu = float(paystub_data.get('ytd_rsu_income', 0))
    ytd_base = ytd_gross - ytd_rsu  # base salary + bonuses (non-RSU)

    # Base salary: linear extrapolation
    projected_base = ytd_base / frac

    # RSU income: actual YTD + future vests in this tax year (event-driven)
    future_rsu_income = _sum_future_rsu_income(vesting_events, estimated_stock_price, tax_year)
    projected_rsu = ytd_rsu + future_rsu_income

    # ESPP discount estimate
    future_espp = _sum_future_espp_discount(vesting_events, estimated_stock_price, tax_year)

    # Total projected W-2 wages
    projected_w2_wages = projected_base + projected_rsu + future_espp

    # State wages assumed equal to W-2 wages (CA taxes all W-2 income)
    projected_state_wages = projected_w2_wages

    # --- Withholding projections ---

    ytd_fed = float(paystub_data.get('ytd_fed_withheld', 0))
    ytd_state = float(paystub_data.get('ytd_state_withheld', 0))

    # Split YTD withholding: estimate how much was base vs RSU
    # RSU withholding is typically at supplemental rates
    est_ytd_rsu_fed_withheld = ytd_rsu * FED_SUPPLEMENTAL_RATE
    est_ytd_base_fed_withheld = ytd_fed - est_ytd_rsu_fed_withheld

    est_ytd_rsu_state_withheld = ytd_rsu * CA_SUPPLEMENTAL_RATE
    est_ytd_base_state_withheld = ytd_state - est_ytd_rsu_state_withheld

    # Extrapolate base withholding linearly, add future RSU withholding at supplemental rates
    projected_fed_withheld = (est_ytd_base_fed_withheld / frac
                              + est_ytd_rsu_fed_withheld
                              + future_rsu_income * FED_SUPPLEMENTAL_RATE
                              + future_espp * FED_SUPPLEMENTAL_RATE)

    projected_state_withheld = (est_ytd_base_state_withheld / frac
                                + est_ytd_rsu_state_withheld
                                + future_rsu_income * CA_SUPPLEMENTAL_RATE
                                + future_espp * CA_SUPPLEMENTAL_RATE)

    # --- Capital gains from planned sales ---
    planned_sales = user_inputs.get('planned_sales', [])
    stock_results = []
    for sale in planned_sales:
        proceeds = float(sale.get('proceeds', 0))
        cost_basis = float(sale.get('cost_basis', 0))
        is_long_term = bool(sale.get('is_long_term', False))
        stock_results.append({
            'proceeds': proceeds,
            'cost_basis': cost_basis,
            'total_gain': proceeds - cost_basis,
            'is_long_term': is_long_term,
            'is_projection': True,
            # Fields required by generate_tax_liability_report
            'acquired_date': datetime(tax_year, 1, 1),
            'sold_date': datetime(tax_year, 12, 31),
            'shares': 0,
            'stock_type': 'PROJ',
            'tax_type': 'Long-term' if is_long_term else 'Short-term',
            'wash_sale_adjustment': 0,
        })

    # --- Other income / deductions ---
    interest_income = float(user_inputs.get('estimated_interest', 0))
    mortgage_interest = float(user_inputs.get('mortgage_interest', 0))
    property_taxes = float(user_inputs.get('property_taxes', 0))

    # Build the projected inputs dict (same shape as build_tax_inputs output)
    projected_inputs = {
        'w2_wages': round(projected_w2_wages, 2),
        'fed_withheld': round(projected_fed_withheld, 2),
        'state_wages': round(projected_state_wages, 2),
        'state_tax_withheld': round(projected_state_withheld, 2),
        'interest_income': round(interest_income, 2),
        'mortgage_interest': round(mortgage_interest, 2),
        'property_taxes': round(property_taxes, 2),
        'mortgage_insurance': 0.0,
        'stock_results': stock_results,
    }

    # Build assumptions report
    future_vest_count = sum(1 for e in vesting_events if e.get('is_future', False)
                           and _is_in_tax_year(e, tax_year)
                           and e.get('plan_type', '').lower() in ('rest. stock', 'rsu', 'restricted stock'))
    future_espp_count = sum(1 for e in vesting_events if e.get('is_future', False)
                           and _is_in_tax_year(e, tax_year)
                           and e.get('plan_type', '').lower() == 'espp')

    assumptions = {
        'pay_date': pay_date,
        'year_fraction': round(frac, 4),
        'year_pct': f'{frac * 100:.1f}%',
        'ytd_base_salary': round(ytd_base, 2),
        'projected_base_salary': round(projected_base, 2),
        'ytd_rsu_income': round(ytd_rsu, 2),
        'future_rsu_income': round(future_rsu_income, 2),
        'future_espp_discount': round(future_espp, 2),
        'total_projected_rsu': round(projected_rsu, 2),
        'estimated_stock_price': estimated_stock_price,
        'future_vest_count': future_vest_count,
        'future_espp_count': future_espp_count,
        'projected_w2_wages': round(projected_w2_wages, 2),
        'projected_fed_withheld': round(projected_fed_withheld, 2),
        'projected_state_withheld': round(projected_state_withheld, 2),
        'planned_sales_count': len(planned_sales),
        'total_planned_gains': round(sum(s.get('total_gain', 0) for s in stock_results), 2),
        'method_base': 'Linear extrapolation from YTD',
        'method_rsu': 'Event-driven (YTD actual + future vests x stock price)',
        'method_withholding': f'Base: linear, RSU: {FED_SUPPLEMENTAL_RATE*100:.0f}% fed / {CA_SUPPLEMENTAL_RATE*100:.2f}% CA supplemental',
    }

    return projected_inputs, assumptions
