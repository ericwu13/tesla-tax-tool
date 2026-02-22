"""
Tesla Stock Tax Calculator
A comprehensive tool for calculating taxes on Tesla stock grants (RSUs and ESPP).
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import yfinance as yf
import re
import os


class TaxCalculator:
    """Class to handle tax calculations for Tesla stock grants."""

    VALID_FILING_STATUSES = ('single', 'mfj', 'mfs', 'hoh')

    def __init__(self, tax_year: int = None, filing_status: str = 'single'):
        # Tax year defaults to current year, but can be overridden (e.g., filing 2025 in 2026)
        self.current_year = tax_year if tax_year else datetime.now().year

        # Filing status
        filing_status = filing_status.lower()
        if filing_status not in self.VALID_FILING_STATUSES:
            raise ValueError(f"Invalid filing status '{filing_status}'. Must be one of: {self.VALID_FILING_STATUSES}")
        self.filing_status = filing_status

        # Active brackets (set by _load_tax_brackets based on filing status)
        self.tax_brackets = []
        self.capital_gains_brackets = []
        self.standard_deduction = 15000
        self.niit_threshold = 200000

        # Legacy aliases for backward compatibility
        self.tax_brackets_single = []
        self.capital_gains_brackets_single = []
        self.standard_deduction_single = 15000
        self.niit_threshold_single = 200000

        self.niit_rate = 0.038

        # CA state brackets and deductions (set by _load_tax_brackets)
        self.ca_tax_brackets = []
        self.ca_standard_deduction = 5540
        # Legacy alias
        self.ca_tax_brackets_single = []
        self.ca_standard_deduction_single = 5540

        # CA Mental Health Services Tax: additional 1% on taxable income over $1,000,000
        self.ca_mental_health_threshold = 1000000
        self.ca_mental_health_rate = 0.01

        # CA SDI rate (informational - already withheld via W-2 box 14)
        self.ca_sdi_rate = 0.012

        # Load tax brackets for the target year
        self._load_tax_brackets()
        
    def _load_tax_brackets(self):
        """Load tax brackets for the configured tax year."""
        if self.current_year == 2025:
            self._use_2025_tax_brackets()
        else:
            # Apply inflation adjustment from 2025 base for other years
            years_diff = self.current_year - 2025
            inflation_factor = (1.025) ** years_diff
            self._use_2025_tax_brackets()
            if years_diff != 0:
                self._apply_inflation_adjustment(inflation_factor)

    def _apply_inflation_adjustment(self, inflation_factor):
        """Apply inflation adjustment to tax brackets from 2025 base values."""
        self.tax_brackets = [
            (int(t * inflation_factor) if t > 0 else 0, r)
            for t, r in self.tax_brackets
        ]
        self.capital_gains_brackets = [
            (int(t * inflation_factor) if t > 0 else 0, r)
            for t, r in self.capital_gains_brackets
        ]
        self.standard_deduction = int(self.standard_deduction * inflation_factor)
        # Keep legacy aliases in sync
        self.tax_brackets_single = self.tax_brackets
        self.capital_gains_brackets_single = self.capital_gains_brackets
        self.standard_deduction_single = self.standard_deduction

    def _use_2025_tax_brackets(self):
        """Hardcoded 2025 tax brackets - IRS Rev. Proc. 2024-40."""
        # Federal Ordinary Income Brackets by filing status
        brackets_by_status = {
            'single': [
                (0, 0.10), (11925, 0.12), (48475, 0.22), (103350, 0.24),
                (197300, 0.32), (250525, 0.35), (626350, 0.37),
            ],
            'mfj': [
                (0, 0.10), (23850, 0.12), (96950, 0.22), (206700, 0.24),
                (394600, 0.32), (501050, 0.35), (751600, 0.37),
            ],
            'mfs': [
                (0, 0.10), (11925, 0.12), (48475, 0.22), (103350, 0.24),
                (197300, 0.32), (250525, 0.35), (375800, 0.37),
            ],
            'hoh': [
                (0, 0.10), (17000, 0.12), (64850, 0.22), (103350, 0.24),
                (197300, 0.32), (250500, 0.35), (626350, 0.37),
            ],
        }

        # LTCG Brackets by filing status
        ltcg_by_status = {
            'single': [(0, 0.0), (48350, 0.15), (533400, 0.20)],
            'mfj':    [(0, 0.0), (96700, 0.15), (600050, 0.20)],
            'mfs':    [(0, 0.0), (48350, 0.15), (300000, 0.20)],
            'hoh':    [(0, 0.0), (64750, 0.15), (566700, 0.20)],
        }

        # Standard Deductions
        std_deduction_by_status = {
            'single': 15000, 'mfj': 30000, 'mfs': 15000, 'hoh': 22500,
        }

        # NIIT Thresholds (statutory, does not adjust for inflation)
        niit_by_status = {
            'single': 200000, 'mfj': 250000, 'mfs': 125000, 'hoh': 200000,
        }

        # Set active brackets based on filing status
        self.tax_brackets = brackets_by_status[self.filing_status]
        self.capital_gains_brackets = ltcg_by_status[self.filing_status]
        self.standard_deduction = std_deduction_by_status[self.filing_status]
        self.niit_threshold = niit_by_status[self.filing_status]

        # Keep legacy aliases in sync for backward compatibility
        self.tax_brackets_single = self.tax_brackets
        self.capital_gains_brackets_single = self.capital_gains_brackets
        self.standard_deduction_single = self.standard_deduction
        self.niit_threshold_single = self.niit_threshold

        # CA State Brackets by filing status
        ca_brackets_by_status = {
            'single': [
                (0, 0.01), (10756, 0.02), (25499, 0.04), (40245, 0.06),
                (55866, 0.08), (70606, 0.093), (360659, 0.103),
                (432787, 0.113), (721314, 0.123),
            ],
            'mfj': [
                (0, 0.01), (21512, 0.02), (50998, 0.04), (80490, 0.06),
                (111732, 0.08), (141212, 0.093), (721318, 0.103),
                (865574, 0.113), (1442628, 0.123),
            ],
            'mfs': [
                (0, 0.01), (10756, 0.02), (25499, 0.04), (40245, 0.06),
                (55866, 0.08), (70606, 0.093), (360659, 0.103),
                (432787, 0.113), (721314, 0.123),
            ],
            'hoh': [
                (0, 0.01), (21527, 0.02), (51000, 0.04), (65744, 0.06),
                (81364, 0.08), (96104, 0.093), (490493, 0.103),
                (588617, 0.113), (980987, 0.123),
            ],
        }

        ca_std_deduction_by_status = {
            'single': 5540, 'mfj': 11080, 'mfs': 5540, 'hoh': 11080,
        }

        self.ca_tax_brackets = ca_brackets_by_status[self.filing_status]
        self.ca_standard_deduction = ca_std_deduction_by_status[self.filing_status]

        # Keep legacy aliases in sync
        self.ca_tax_brackets_single = self.ca_tax_brackets
        self.ca_standard_deduction_single = self.ca_standard_deduction
        
    def calculate_marginal_tax_rate(self, ordinary_income: float) -> float:
        """Calculate the marginal tax rate based on ordinary income."""
        for threshold, rate in reversed(self.tax_brackets):
            if ordinary_income > threshold:
                return rate
        return self.tax_brackets[0][1]

    def calculate_capital_gains_rate(self, ordinary_income: float) -> float:
        """Calculate the capital gains tax rate based on ordinary income."""
        for threshold, rate in reversed(self.capital_gains_brackets):
            if ordinary_income > threshold:
                return rate
        return self.capital_gains_brackets[0][1]
    
    def calculate_progressive_ordinary_tax(self, taxable_ordinary_income: float) -> Tuple[float, List[Dict]]:
        """
        Calculate federal income tax using progressive bracket application.

        Returns:
            Tuple of (total_tax, bracket_details) where bracket_details shows
            how much income fell in each bracket and the tax on that portion.
        """
        if taxable_ordinary_income <= 0:
            return 0.0, []

        total_tax = 0.0
        bracket_details = []
        remaining_income = taxable_ordinary_income

        for i, (threshold, rate) in enumerate(self.tax_brackets):
            if remaining_income <= 0:
                break

            if i + 1 < len(self.tax_brackets):
                next_threshold = self.tax_brackets[i + 1][0]
                bracket_width = next_threshold - threshold
            else:
                bracket_width = remaining_income

            taxable_in_bracket = min(remaining_income, bracket_width)
            tax_in_bracket = taxable_in_bracket * rate
            total_tax += tax_in_bracket

            bracket_details.append({
                'bracket_floor': threshold,
                'rate': rate,
                'income_in_bracket': taxable_in_bracket,
                'tax_in_bracket': tax_in_bracket
            })

            remaining_income -= taxable_in_bracket

        return total_tax, bracket_details

    def calculate_progressive_ltcg_tax(self, taxable_ordinary_income: float,
                                        long_term_gains: float) -> Tuple[float, List[Dict]]:
        """
        Calculate long-term capital gains tax progressively.
        LTCG brackets are based on total taxable income. Ordinary income fills
        the brackets first, then LTCG stacks on top.
        """
        if long_term_gains <= 0:
            return 0.0, []

        total_tax = 0.0
        bracket_details = []
        remaining_gains = long_term_gains
        income_already_used = taxable_ordinary_income

        for i, (threshold, rate) in enumerate(self.capital_gains_brackets):
            if remaining_gains <= 0:
                break

            if i + 1 < len(self.capital_gains_brackets):
                next_threshold = self.capital_gains_brackets[i + 1][0]
            else:
                next_threshold = float('inf')

            if income_already_used >= next_threshold:
                continue

            bracket_start = max(threshold, income_already_used)
            bracket_room = next_threshold - bracket_start
            taxable_in_bracket = min(remaining_gains, bracket_room)

            tax_in_bracket = taxable_in_bracket * rate
            total_tax += tax_in_bracket

            bracket_details.append({
                'bracket_floor': threshold,
                'rate': rate,
                'gains_in_bracket': taxable_in_bracket,
                'tax_in_bracket': tax_in_bracket
            })

            remaining_gains -= taxable_in_bracket
            income_already_used += taxable_in_bracket

        return total_tax, bracket_details

    def calculate_niit(self, agi: float, net_investment_income: float) -> float:
        """
        Calculate Net Investment Income Tax (3.8% surtax).
        Applies to single filers with MAGI > $200,000.
        """
        excess_agi = max(0, agi - self.niit_threshold)
        niit_base = min(excess_agi, net_investment_income)
        return niit_base * self.niit_rate

    def calculate_ca_progressive_tax(self, taxable_income: float) -> Tuple[float, List[Dict]]:
        """
        Calculate California state income tax using progressive brackets.
        CA taxes all income the same (no special LTCG rate).
        """
        if taxable_income <= 0:
            return 0.0, []

        total_tax = 0.0
        bracket_details = []
        remaining = taxable_income

        for i, (threshold, rate) in enumerate(self.ca_tax_brackets):
            if remaining <= 0:
                break

            if i + 1 < len(self.ca_tax_brackets):
                next_threshold = self.ca_tax_brackets[i + 1][0]
                bracket_width = next_threshold - threshold
            else:
                bracket_width = remaining

            taxable_in_bracket = min(remaining, bracket_width)
            tax_in_bracket = taxable_in_bracket * rate
            total_tax += tax_in_bracket

            bracket_details.append({
                'bracket_floor': threshold,
                'rate': rate,
                'income_in_bracket': taxable_in_bracket,
                'tax_in_bracket': tax_in_bracket,
            })

            remaining -= taxable_in_bracket

        # Mental Health Services Tax: 1% on income over $1M
        mental_health_tax = 0.0
        if taxable_income > self.ca_mental_health_threshold:
            mental_health_tax = (taxable_income - self.ca_mental_health_threshold) * self.ca_mental_health_rate
            total_tax += mental_health_tax

        return total_tax, bracket_details

    def calculate_ca_state_tax(self, w2_state_wages: float,
                                interest_income: float = 0,
                                stock_short_term_gains: float = 0,
                                stock_long_term_gains: float = 0,
                                net_rental_income: float = 0,
                                ca_itemized_deductions: Optional[float] = None,
                                state_tax_withheld: float = 0,
                                ca_sdi_withheld: float = 0) -> Dict:
        """
        Calculate California state income tax liability.

        CA taxes all capital gains as ordinary income (no preferential rate).
        CA does not allow SALT deduction. Mortgage interest is deductible.

        Args:
            w2_state_wages: W-2 Box 16 state wages
            interest_income: 1099-INT interest income
            stock_short_term_gains: Short-term capital gains
            stock_long_term_gains: Long-term capital gains
            net_rental_income: Net rental income from Schedule E
            ca_itemized_deductions: CA itemized deductions (mortgage interest + property tax)
            state_tax_withheld: W-2 Box 17 state tax withheld
            ca_sdi_withheld: CA SDI from Box 14
        """
        # CA AGI = state wages + investment income + rental income
        # Note: W-2 Box 16 already includes the state wage amount
        ca_total_income = (w2_state_wages + interest_income +
                           stock_short_term_gains + stock_long_term_gains +
                           net_rental_income)

        # CA deduction
        if ca_itemized_deductions is not None and ca_itemized_deductions > self.ca_standard_deduction:
            ca_deduction = ca_itemized_deductions
            ca_deduction_type = 'Itemized'
        else:
            ca_deduction = self.ca_standard_deduction
            ca_deduction_type = 'Standard'

        ca_taxable_income = max(0, ca_total_income - ca_deduction)

        # Progressive CA tax
        ca_tax, ca_brackets = self.calculate_ca_progressive_tax(ca_taxable_income)

        # Mental health surtax info
        mental_health_tax = 0.0
        if ca_taxable_income > self.ca_mental_health_threshold:
            mental_health_tax = (ca_taxable_income - self.ca_mental_health_threshold) * self.ca_mental_health_rate

        # Net due
        ca_net_due = ca_tax - state_tax_withheld

        return {
            'ca_total_income': ca_total_income,
            'ca_deduction_type': ca_deduction_type,
            'ca_deduction': ca_deduction,
            'ca_taxable_income': ca_taxable_income,
            'ca_tax': ca_tax,
            'ca_brackets': ca_brackets,
            'ca_mental_health_tax': mental_health_tax,
            'ca_state_tax_withheld': state_tax_withheld,
            'ca_sdi_withheld': ca_sdi_withheld,
            'ca_net_tax_due': max(0, ca_net_due),
            'ca_refund': max(0, -ca_net_due),
            'ca_effective_rate': (ca_tax / ca_total_income * 100) if ca_total_income > 0 else 0,
        }

    def generate_ca_tax_report_section(self, ca_result: Dict) -> str:
        """Generate a California state tax section for the report."""
        lines = []
        lines.append("")
        lines.append("=" * 80)
        lines.append(f"  {self.current_year} CALIFORNIA STATE TAX LIABILITY ESTIMATE")
        lines.append("=" * 80)
        lines.append("")

        lines.append("  CA INCOME")
        lines.append("  " + "-" * 70)
        lines.append(f"    CA Total Income:                             ${ca_result['ca_total_income']:>14,.2f}")
        lines.append(f"    {ca_result['ca_deduction_type']} Deduction:                          (${ca_result['ca_deduction']:>13,.2f})")
        lines.append(f"                                                 {'':>3}{'-' * 14}")
        lines.append(f"    CA Taxable Income:                           ${ca_result['ca_taxable_income']:>14,.2f}")
        lines.append("")

        lines.append("  CA TAX CALCULATION")
        lines.append("  " + "-" * 70)
        lines.append("    Progressive CA Tax:")
        for b in ca_result['ca_brackets']:
            rate_pct = f"{b['rate']*100:.1f}%"
            lines.append(f"      {rate_pct:>6} on ${b['income_in_bracket']:>12,.2f}:                   ${b['tax_in_bracket']:>12,.2f}")
        if ca_result['ca_mental_health_tax'] > 0:
            lines.append(f"    Mental Health Surtax (1% over $1M):          ${ca_result['ca_mental_health_tax']:>14,.2f}")
        lines.append(f"                                                 {'':>3}{'-' * 14}")
        lines.append(f"    Total CA Tax:                                ${ca_result['ca_tax']:>14,.2f}")
        lines.append("")

        lines.append("  CA PAYMENTS & WITHHOLDINGS")
        lines.append("  " + "-" * 70)
        lines.append(f"    CA State Tax Withheld (W-2 Box 17):         (${ca_result['ca_state_tax_withheld']:>13,.2f})")
        lines.append(f"                                                 {'':>3}{'-' * 14}")
        if ca_result['ca_net_tax_due'] > 0:
            lines.append(f"    CA NET TAX DUE:                              ${ca_result['ca_net_tax_due']:>14,.2f}")
        else:
            lines.append(f"    CA REFUND:                                   ${ca_result['ca_refund']:>14,.2f}")
        lines.append("")
        lines.append(f"    CA Effective Tax Rate:                        {ca_result['ca_effective_rate']:>13.1f}%")
        if ca_result['ca_sdi_withheld'] > 0:
            lines.append(f"    CA SDI Withheld (Box 14):                    ${ca_result['ca_sdi_withheld']:>14,.2f}  (not income tax)")
        lines.append("")

        return "\n".join(lines)

    def parse_currency(self, value: str) -> float:
        """Parse currency string to float."""
        if pd.isna(value) or value == '':
            return 0.0
        # Remove currency symbols, commas, and spaces
        cleaned = re.sub(r'[\$,\s]', '', str(value))
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
    
    def parse_date(self, date_str: str) -> datetime:
        """Parse date string to datetime object."""
        if pd.isna(date_str) or date_str == '':
            return None
        try:
            return datetime.strptime(str(date_str), '%d-%b-%y')
        except ValueError:
            try:
                return datetime.strptime(str(date_str), '%d-%b-%Y')
            except ValueError:
                try:
                    return datetime.strptime(str(date_str), '%Y-%m-%d')
                except ValueError:
                    raise ValueError(f"Unable to parse date: {date_str}")
    
    def is_long_term(self, acquired_date: datetime, sold_date: datetime) -> bool:
        """Determine if the holding period qualifies for long-term capital gains."""
        return (sold_date - acquired_date).days > 365
    
    def get_tesla_offer_date(self, purchase_date: datetime) -> datetime:
        """Infer the ESPP offer date based on Tesla's ESPP schedule."""
        year = purchase_date.year
        
        # Tesla ESPP periods:
        # - February 1 to July 31 (purchase in July/August)
        # - August 1 to January 31 (purchase in January/February of next year)
        
        if purchase_date.month <= 2:
            # Purchase in Jan/Feb means offer was from previous August
            return datetime(year - 1, 8, 1)
        elif purchase_date.month <= 8:
            # Purchase in Mar-Aug means offer was from February of same year
            return datetime(year, 2, 1)
        else:
            # Purchase in Sep-Dec means offer was from August of same year
            return datetime(year, 8, 1)
    
    def is_qualifying_espp_disposition(self, offer_date: datetime, purchase_date: datetime, 
                                     sold_date: datetime) -> bool:
        """
        Determine if ESPP sale is qualifying disposition.
        Qualifying if:
        1. At least 2 years from offer date
        2. At least 1 year from purchase date
        """
        two_years_from_offer = (sold_date - offer_date).days >= 730
        one_year_from_purchase = (sold_date - purchase_date).days >= 365
        
        return two_years_from_offer and one_year_from_purchase
    
    def get_stock_price(self, symbol: str, date: datetime) -> float:
        """Get stock price for a given date using yfinance."""
        try:
            ticker = yf.Ticker(symbol)
            
            # Get historical data around the date
            start_date = (date - timedelta(days=10)).strftime('%Y-%m-%d')
            end_date = (date + timedelta(days=10)).strftime('%Y-%m-%d')
            
            hist = ticker.history(start=start_date, end=end_date)
            
            if hist.empty:
                print(f"Warning: No data found for {symbol} around {date}")
                return 0.0
            
            # Find the closest trading day
            target_date = date.strftime('%Y-%m-%d')
            
            # Convert index to date strings for comparison
            hist_dates = [idx.strftime('%Y-%m-%d') for idx in hist.index]
            
            if target_date in hist_dates:
                # Exact date match
                return hist.loc[hist.index[hist_dates.index(target_date)]]['Close']
            else:
                # Find the closest trading day (prefer earlier dates for acquisition)
                hist_with_dates = [(idx, abs((idx.date() - date.date()).days)) for idx in hist.index]
                closest_date_idx = min(hist_with_dates, key=lambda x: x[1])[0]
                price = hist.loc[closest_date_idx]['Close']
                print(f"Note: Using {closest_date_idx.strftime('%Y-%m-%d')} price (${price:.2f}) for {symbol} on {date.strftime('%Y-%m-%d')}")
                return price
        
        except Exception as e:
            print(f"Error fetching stock price for {symbol} on {date}: {e}")
            return 0.0
    
    def load_stock_data(self, csv_file: str) -> pd.DataFrame:
        """Load and parse the stock CSV data."""
        df = pd.read_csv(csv_file)

        # Normalize first column name (CSV may use 'Test' or 'Record Type')
        first_col = df.columns[0]
        if first_col != 'Record Type':
            df = df.rename(columns={first_col: 'Record Type'})

        # Clean up the dataframe
        df = df.dropna(how='all')  # Remove empty rows
        df = df[df['Record Type'].notna()]  # Remove rows with no data
        df = df[df['Record Type'] != 'Overall Total']  # Remove summary row

        # Parse dates
        df['Date Acquired'] = df['Date Acquired'].apply(self.parse_date)
        df = df[df['Date Acquired'].notna()]  # Remove rows with invalid dates

        # Parse optional sale columns (backward compatible)
        if 'Date Sold' in df.columns:
            df['Date Sold'] = df['Date Sold'].apply(
                lambda x: self.parse_date(x) if pd.notna(x) and str(x).strip() != '' else None
            )
        else:
            df['Date Sold'] = None

        if 'Sale Price' in df.columns:
            df['Sale Price'] = df['Sale Price'].apply(
                lambda x: self.parse_currency(str(x)) if pd.notna(x) and str(x).strip() != '' else 0.0
            )
        else:
            df['Sale Price'] = 0.0

        # Parse numeric values
        df['Sellable Qty.'] = pd.to_numeric(df['Sellable Qty.'], errors='coerce')
        df['Expected Gain/Loss'] = df['Expected Gain/Loss'].apply(self.parse_currency)
        df['Est. Market Value'] = df['Est. Market Value'].apply(self.parse_currency)

        # Remove rows with invalid quantities
        df = df[df['Sellable Qty.'] > 0]

        # Classify stock type
        df['Stock_Type'] = df['Plan Type'].apply(self.classify_stock_type)

        return df
    
    def classify_stock_type(self, plan_type: str) -> str:
        """Classify whether the stock is RSU or ESPP."""
        if pd.isna(plan_type):
            return 'Unknown'
        
        plan_type_lower = plan_type.lower()
        if 'espp' in plan_type_lower:
            return 'ESPP'
        elif 'rest' in plan_type_lower or 'rsu' in plan_type_lower:
            return 'RSU'
        else:
            return 'Unknown'
    
    def calculate_rsu_taxes(self, row: pd.Series, sold_date: datetime, 
                           sold_price: float, ordinary_income: float) -> Dict:
        """Calculate taxes for RSU transactions."""
        acquired_date = row['Date Acquired']
        shares = row['Sellable Qty.']
        
        # For RSUs, get the actual stock price at the acquisition/vesting date
        # This is the fair market value that becomes the tax basis
        print(f"Fetching historical price for RSU acquired on {acquired_date.strftime('%Y-%m-%d')}...")
        acquisition_price = self.get_stock_price('TSLA', acquired_date)
        
        if acquisition_price == 0:
            print(f"Warning: Could not get acquisition price for {acquired_date}")
            return None
        
        # Calculate values based on actual stock prices
        acquisition_value = acquisition_price * shares
        proceeds = shares * sold_price
        total_gain = proceeds - acquisition_value
        
        # Determine if long-term or short-term
        is_long_term_holding = self.is_long_term(acquired_date, sold_date)
        
        # Calculate tax
        if is_long_term_holding:
            tax_rate = self.calculate_capital_gains_rate(ordinary_income)
            tax_type = 'Long Term Capital Gains'
        else:
            tax_rate = self.calculate_marginal_tax_rate(ordinary_income)
            tax_type = 'Short Term Capital Gains (Ordinary Income)'
        
        tax_amount = max(0, total_gain * tax_rate)  # No negative taxes
        
        return {
            'stock_type': 'RSU',
            'acquired_date': acquired_date,
            'shares': shares,
            'acquisition_price': acquisition_price,
            'sold_price': sold_price,
            'proceeds': proceeds,
            'total_gain': total_gain,
            'is_long_term': is_long_term_holding,
            'tax_type': tax_type,
            'tax_rate': tax_rate,
            'tax_amount': tax_amount,
            'ordinary_income_portion': 0,  # RSUs don't have ordinary income portion at sale
            'capital_gain_portion': total_gain  # For RSUs, all gain is capital gain
        }
    
    def calculate_espp_taxes(self, row: pd.Series, sold_date: datetime, 
                            sold_price: float, ordinary_income: float) -> Dict:
        """Calculate taxes for ESPP transactions."""
        purchase_date = row['Date Acquired']
        shares = row['Sellable Qty.']
        
        # Infer offer date
        offer_date = self.get_tesla_offer_date(purchase_date)
        
        # Get historical stock prices for ESPP calculation
        print(f"Fetching ESPP prices for offer: {offer_date.strftime('%Y-%m-%d')}, purchase: {purchase_date.strftime('%Y-%m-%d')}...")
        
        offer_price = self.get_stock_price('TSLA', offer_date)
        purchase_date_price = self.get_stock_price('TSLA', purchase_date)
        
        if offer_price == 0 or purchase_date_price == 0:
            print(f"Warning: Could not get historical prices for ESPP calculation")
            return None
        
        # ESPP purchase price is typically 85% of the lower of offer price or purchase date price
        lower_price = min(offer_price, purchase_date_price)
        espp_purchase_price = lower_price * 0.85  # 15% discount
        
        # Calculate values
        purchase_value = espp_purchase_price * shares
        proceeds = shares * sold_price
        total_gain = proceeds - purchase_value
        
        # Determine if qualifying disposition
        is_qualifying = self.is_qualifying_espp_disposition(offer_date, purchase_date, sold_date)
        
        if is_qualifying:
            # Qualifying disposition
            # Ordinary income = min(15% of FMV at offer, actual gain)
            discount_amount = (lower_price - espp_purchase_price) * shares
            ordinary_income_portion = min(discount_amount, total_gain)
            capital_gain_portion = max(0, total_gain - ordinary_income_portion)
            
            # Tax calculation
            ordinary_tax = ordinary_income_portion * self.calculate_marginal_tax_rate(ordinary_income)
            capital_gains_tax = capital_gain_portion * self.calculate_capital_gains_rate(ordinary_income)
            total_tax = ordinary_tax + capital_gains_tax
            tax_type = 'Qualifying ESPP'
            
        else:
            # Disqualifying disposition
            # For disqualifying dispositions, the discount is based on FMV at purchase date
            # NOT the lower of offer/purchase price
            discount_amount = (purchase_date_price - espp_purchase_price) * shares
            ordinary_income_portion = discount_amount
            capital_gain_portion = max(0, total_gain - ordinary_income_portion)
            
            # Tax calculation
            ordinary_tax = ordinary_income_portion * self.calculate_marginal_tax_rate(ordinary_income)
            
            # Capital gains tax (short or long term based on holding period from purchase)
            is_long_term_holding = self.is_long_term(purchase_date, sold_date)
            if is_long_term_holding:
                capital_gains_tax = capital_gain_portion * self.calculate_capital_gains_rate(ordinary_income)
                tax_type = 'Disqualifying ESPP (LT Capital Gains)'
            else:
                capital_gains_tax = capital_gain_portion * self.calculate_marginal_tax_rate(ordinary_income)
                tax_type = 'Disqualifying ESPP (ST Capital Gains)'
            
            total_tax = ordinary_tax + capital_gains_tax
        
        return {
            'stock_type': 'ESPP',
            'acquired_date': purchase_date,
            'offer_date': offer_date,
            'offer_price': offer_price,
            'purchase_date_price': purchase_date_price,
            'shares': shares,
            'acquisition_price': espp_purchase_price,
            'sold_price': sold_price,
            'proceeds': proceeds,
            'total_gain': total_gain,
            'is_qualifying': is_qualifying,
            'is_long_term': is_qualifying or self.is_long_term(purchase_date, sold_date),
            'tax_type': tax_type,
            'tax_amount': total_tax,
            'ordinary_income_portion': ordinary_income_portion,
            'capital_gain_portion': capital_gain_portion
        }
    
    def calculate_all_taxes(self, csv_file: str, ordinary_income: float,
                           sold_date: Optional[datetime] = None,
                           sold_only: bool = False) -> List[Dict]:
        """
        Calculate taxes for all stock transactions.

        Args:
            csv_file: Path to the stock CSV file
            ordinary_income: Ordinary income for tax bracket determination
            sold_date: Default sale date for rows without a specific Date Sold
            sold_only: If True, only process rows that have Date Sold filled in
        """
        if sold_date is None:
            sold_date = datetime.now()

        # Load stock data
        df = self.load_stock_data(csv_file)

        # Get default Tesla stock price for rows without a specific sale price
        default_sold_price = None
        if not sold_only:
            default_sold_price = self.get_stock_price('TSLA', sold_date)
            if default_sold_price == 0:
                print(f"Warning: Could not fetch Tesla stock price for {sold_date}. Using current price.")
                default_sold_price = self.get_stock_price('TSLA', datetime.now())

        results = []

        for index, row in df.iterrows():
            try:
                # Determine sale date and price for this row
                row_has_sale = row.get('Date Sold') is not None and pd.notna(row.get('Date Sold'))

                if sold_only and not row_has_sale:
                    continue  # Skip unsold rows when only processing actual sales

                if row_has_sale:
                    row_sold_date = row['Date Sold']
                    row_sold_price = row.get('Sale Price', 0.0)
                    if row_sold_price == 0.0:
                        row_sold_price = self.get_stock_price('TSLA', row_sold_date)
                else:
                    row_sold_date = sold_date
                    row_sold_price = default_sold_price

                if row['Stock_Type'] == 'RSU':
                    result = self.calculate_rsu_taxes(row, row_sold_date, row_sold_price, ordinary_income)
                elif row['Stock_Type'] == 'ESPP':
                    result = self.calculate_espp_taxes(row, row_sold_date, row_sold_price, ordinary_income)
                else:
                    continue

                # Skip if calculation failed (couldn't get historical prices)
                if result is None:
                    print(f"Skipping row {index} due to missing price data")
                    continue

                # Add additional info
                result['grant_number'] = row.get('Grant Number', 'N/A')
                result['original_tax_status'] = row.get('Tax Status', 'N/A')
                result['actually_sold'] = row_has_sale

                results.append(result)

            except Exception as e:
                print(f"Error processing row {index}: {e}")
                continue

        return results
    
    def generate_report(self, results: List[Dict], ordinary_income: float, 
                       sold_date: datetime) -> str:
        """Generate a comprehensive tax report."""
        report = []
        report.append("=" * 80)
        report.append("TESLA STOCK TAX CALCULATION REPORT")
        report.append("=" * 80)
        report.append(f"Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Ordinary Income: ${ordinary_income:,.2f}")
        report.append(f"Sale Date: {sold_date.strftime('%Y-%m-%d')}")
        report.append(f"Marginal Tax Rate: {self.calculate_marginal_tax_rate(ordinary_income):.1%}")
        report.append(f"Capital Gains Rate: {self.calculate_capital_gains_rate(ordinary_income):.1%}")
        report.append("")
        
        # Summary statistics
        total_shares = sum(r['shares'] for r in results)
        total_proceeds = sum(r['proceeds'] for r in results)
        total_gains = sum(r['total_gain'] for r in results)
        total_taxes = sum(r['tax_amount'] for r in results)
        total_ordinary_income = sum(r.get('ordinary_income_portion', 0) for r in results)
        
        report.append("SUMMARY")
        report.append("-" * 40)
        report.append(f"Total Shares: {total_shares:.2f}")
        report.append(f"Total Proceeds: ${total_proceeds:,.2f}")
        report.append(f"Total Gains: ${total_gains:,.2f}")
        report.append(f"Total Ordinary Income: ${total_ordinary_income:,.2f}")
        report.append(f"Total Tax Due: ${total_taxes:,.2f}")
        report.append(f"Effective Tax Rate: {total_taxes/total_gains*100:.2f}%" if total_gains > 0 else "N/A")
        report.append("")
        
        # Detailed breakdown
        report.append("DETAILED BREAKDOWN")
        report.append("-" * 80)
        
        # Group by stock type
        rsu_results = [r for r in results if r['stock_type'] == 'RSU']
        espp_results = [r for r in results if r['stock_type'] == 'ESPP']
        
        if rsu_results:
            report.append("\nRSU TRANSACTIONS:")
            report.append("=" * 50)
            for r in rsu_results:
                report.append(f"Grant: {r.get('grant_number', 'N/A')}")
                report.append(f"  Acquired: {r['acquired_date'].strftime('%Y-%m-%d')}")
                report.append(f"  Shares: {r['shares']:.2f}")
                report.append(f"  Acquisition Price: ${r['acquisition_price']:.2f}")
                report.append(f"  Sold Price: ${r['sold_price']:.2f}")
                report.append(f"  Proceeds: ${r['proceeds']:,.2f}")
                report.append(f"  Total Gain: ${r['total_gain']:,.2f}")
                report.append(f"  Holding Period: {'Long Term' if r['is_long_term'] else 'Short Term'}")
                report.append(f"  Tax Type: {r['tax_type']}")
                report.append(f"  Tax Rate: {r['tax_rate']:.1%}")
                report.append(f"  Tax Amount: ${r['tax_amount']:,.2f}")
                report.append("")
        
        if espp_results:
            report.append("\nESPP TRANSACTIONS:")
            report.append("=" * 50)
            for r in espp_results:
                report.append(f"Grant: {r.get('grant_number', 'N/A')}")
                report.append(f"  Offer Date: {r['offer_date'].strftime('%Y-%m-%d')}")
                report.append(f"  Purchase Date: {r['acquired_date'].strftime('%Y-%m-%d')}")
                report.append(f"  Offer Price: ${r.get('offer_price', 0):.2f}")
                report.append(f"  Purchase Date Price: ${r.get('purchase_date_price', 0):.2f}")
                report.append(f"  ESPP Purchase Price (15% discount): ${r['acquisition_price']:.2f}")
                report.append(f"  Shares: {r['shares']:.2f}")
                report.append(f"  Sold Price: ${r['sold_price']:.2f}")
                report.append(f"  Proceeds: ${r['proceeds']:,.2f}")
                report.append(f"  Total Gain: ${r['total_gain']:,.2f}")
                report.append(f"  Disposition: {'Qualifying' if r['is_qualifying'] else 'Disqualifying'}")
                report.append(f"  Ordinary Income: ${r['ordinary_income_portion']:,.2f}")
                report.append(f"  Tax Type: {r['tax_type']}")
                report.append(f"  Tax Amount: ${r['tax_amount']:,.2f}")
                report.append("")
        
        # Tax planning notes
        report.append("\nTAX PLANNING NOTES:")
        report.append("=" * 50)
        report.append("• This calculation is based on 2025 federal tax brackets")
        report.append("• State taxes are not included in this calculation")
        report.append("• For ESPP, qualifying vs disqualifying disposition rules have been applied")
        report.append("• Consult a tax professional for complex situations")
        report.append("• Consider timing of sales to optimize tax efficiency")
        report.append("")
        
        return "\n".join(report)
    
    def export_to_csv(self, results: List[Dict], filename: str) -> None:
        """Export calculation results to CSV format."""
        if not results:
            print("No results to export.")
            return
        
        # Create outputs directory if it doesn't exist
        output_dir = "outputs"
        os.makedirs(output_dir, exist_ok=True)
        
        # Add output directory to filename
        csv_path = os.path.join(output_dir, filename)
        
        # Prepare data for CSV export
        csv_data = []
        for r in results:
            row = {
                'Stock_Type': r['stock_type'],
                'Grant_Number': r.get('grant_number', 'N/A'),
                'Acquired_Date': r['acquired_date'].strftime('%Y-%m-%d'),
                'Shares': r['shares'],
                'Acquisition_Price': r['acquisition_price'],
                'Sold_Price': r['sold_price'],
                'Proceeds': r['proceeds'],
                'Total_Gain': r['total_gain'],
                'Ordinary_Income_Portion': r.get('ordinary_income_portion', 0),
                'Capital_Gain_Portion': r.get('capital_gain_portion', 0),
                'Holding_Period': 'Long Term' if r['is_long_term'] else 'Short Term',
                'Tax_Type': r['tax_type'],
                'Tax_Rate': r.get('tax_rate', 0),
                'Tax_Amount': r['tax_amount']
            }
            
            # Add ESPP-specific fields
            if r['stock_type'] == 'ESPP':
                row['Offer_Date'] = r['offer_date'].strftime('%Y-%m-%d')
                row['Offer_Price'] = r.get('offer_price', 0)
                row['Purchase_Date_Price'] = r.get('purchase_date_price', 0)
                row['Disposition_Type'] = 'Qualifying' if r['is_qualifying'] else 'Disqualifying'
            else:
                row['Offer_Date'] = ''
                row['Offer_Price'] = ''
                row['Purchase_Date_Price'] = ''
                row['Disposition_Type'] = ''
            
            csv_data.append(row)
        
        # Create DataFrame and save to CSV
        df = pd.DataFrame(csv_data)
        
        # Reorder columns for better readability
        column_order = [
            'Stock_Type', 'Grant_Number', 'Acquired_Date', 'Offer_Date', 'Offer_Price', 'Purchase_Date_Price',
            'Shares', 'Acquisition_Price', 'Sold_Price', 'Proceeds',
            'Total_Gain', 'Ordinary_Income_Portion', 'Capital_Gain_Portion', 'Holding_Period', 'Disposition_Type',
            'Tax_Type', 'Tax_Rate', 'Tax_Amount'
        ]
        
        df = df[column_order]
        df.to_csv(csv_path, index=False)
        print(f"Results exported to CSV: {csv_path}")
    
    def calculate_total_tax_liability(self,
                                     w2_wages: float,
                                     federal_tax_withheld: float,
                                     stock_results: List[Dict],
                                     deduction_amount: Optional[float] = None,
                                     estimated_payments: float = 0,
                                     stock_tax_withheld: float = 0,
                                     interest_income: float = 0,
                                     rental_result: Optional[Dict] = None,
                                     itemized_result: Optional[Dict] = None) -> Dict:
        """
        Calculate total federal income tax liability for the tax year.

        Args:
            w2_wages: W-2 Box 1 wages
            federal_tax_withheld: W-2 Box 2 federal tax withheld
            stock_results: List of per-transaction results from calculate_all_taxes()
            deduction_amount: Override deduction amount (ignored if itemized_result provided)
            estimated_payments: Quarterly estimated tax payments made
            stock_tax_withheld: Federal tax withheld on stock sales
            interest_income: Total 1099-INT interest income
            rental_result: Result from calculate_rental_income() (Schedule E)
            itemized_result: Result from calculate_itemized_deductions() (Schedule A)
        """
        # Step 1: Classify stock results into income categories
        stock_short_term_gains = 0.0
        stock_long_term_gains = 0.0
        stock_ordinary_income = 0.0

        for r in stock_results:
            ordinary_portion = r.get('ordinary_income_portion', 0)
            capital_portion = r.get('capital_gain_portion', 0)

            # ESPP ordinary income portion always taxed as ordinary income
            stock_ordinary_income += ordinary_portion

            if r.get('is_long_term', False):
                stock_long_term_gains += capital_portion
            else:
                # Short-term capital gains taxed as ordinary income
                stock_short_term_gains += capital_portion

        # Step 2: Aggregate income
        net_rental_income = rental_result['net_rental_income'] if rental_result else 0
        total_ordinary_income = (w2_wages + stock_ordinary_income +
                                 stock_short_term_gains + interest_income +
                                 net_rental_income)
        total_long_term_gains = stock_long_term_gains

        agi = total_ordinary_income + total_long_term_gains

        # Step 3: Determine deduction (itemized vs standard)
        if itemized_result is not None:
            itemized_total = itemized_result['total_itemized']
            if itemized_total > self.standard_deduction:
                deduction = itemized_total
                deduction_type = 'Itemized'
            else:
                deduction = self.standard_deduction
                deduction_type = 'Standard (exceeds itemized)'
        elif deduction_amount is not None:
            deduction = deduction_amount
            deduction_type = 'Itemized'
        else:
            deduction = self.standard_deduction
            deduction_type = 'Standard'

        # Deduction reduces ordinary income first
        taxable_ordinary_income = max(0, total_ordinary_income - deduction)
        excess_deduction = max(0, deduction - total_ordinary_income)
        taxable_ltcg = max(0, total_long_term_gains - excess_deduction)

        # Step 4: Calculate taxes progressively
        ordinary_tax, ordinary_brackets = self.calculate_progressive_ordinary_tax(taxable_ordinary_income)
        ltcg_tax, ltcg_brackets = self.calculate_progressive_ltcg_tax(taxable_ordinary_income, taxable_ltcg)

        # NIIT: net investment income includes interest, ST gains, LT gains, rental income
        net_investment_income = (total_long_term_gains + stock_short_term_gains +
                                 interest_income + max(0, net_rental_income))
        niit = self.calculate_niit(agi, net_investment_income)

        total_tax = ordinary_tax + ltcg_tax + niit

        # Step 5: Calculate net due/refund
        total_payments = federal_tax_withheld + estimated_payments + stock_tax_withheld
        net_due = total_tax - total_payments

        return {
            # Income
            'w2_wages': w2_wages,
            'stock_ordinary_income': stock_ordinary_income,
            'stock_short_term_gains': stock_short_term_gains,
            'stock_long_term_gains': stock_long_term_gains,
            'interest_income': interest_income,
            'net_rental_income': net_rental_income,
            'total_ordinary_income': total_ordinary_income,
            'total_long_term_gains': total_long_term_gains,
            'agi': agi,

            # Deductions
            'deduction_type': deduction_type,
            'deduction_amount': deduction,
            'itemized_detail': itemized_result,
            'rental_detail': rental_result,

            # Taxable income
            'taxable_ordinary_income': taxable_ordinary_income,
            'taxable_ltcg': taxable_ltcg,
            'total_taxable_income': taxable_ordinary_income + taxable_ltcg,

            # Tax calculation
            'ordinary_tax': ordinary_tax,
            'ordinary_tax_brackets': ordinary_brackets,
            'ltcg_tax': ltcg_tax,
            'ltcg_tax_brackets': ltcg_brackets,
            'niit': niit,
            'net_investment_income': net_investment_income,
            'total_tax_liability': total_tax,

            # Payments and withholdings
            'federal_tax_withheld': federal_tax_withheld,
            'stock_tax_withheld': stock_tax_withheld,
            'estimated_payments': estimated_payments,
            'total_payments': total_payments,

            # Result
            'net_tax_due': max(0, net_due),
            'refund': max(0, -net_due),
            'effective_tax_rate': (total_tax / agi * 100) if agi > 0 else 0,
            'marginal_ordinary_rate': self.calculate_marginal_tax_rate(taxable_ordinary_income),
            'marginal_ltcg_rate': self.calculate_capital_gains_rate(taxable_ordinary_income),
        }

    def generate_tax_liability_report(self, liability: Dict, stock_results: List[Dict]) -> str:
        """Generate a Form 1040-style tax liability report."""
        lines = []
        lines.append("=" * 80)
        status_labels = {
            'single': 'Single', 'mfj': 'Married Filing Jointly',
            'mfs': 'Married Filing Separately', 'hoh': 'Head of Household',
        }
        lines.append(f"  {self.current_year} FEDERAL INCOME TAX LIABILITY ESTIMATE")
        lines.append(f"  {status_labels.get(self.filing_status, self.filing_status)}")
        lines.append("=" * 80)
        lines.append(f"  Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # Income section
        lines.append("  INCOME")
        lines.append("  " + "-" * 70)
        lines.append(f"    W-2 Wages (Box 1):                          ${liability['w2_wages']:>14,.2f}")
        if liability.get('interest_income', 0) > 0:
            lines.append(f"    Interest Income (1099-INT):                  ${liability['interest_income']:>14,.2f}")
        if liability['stock_ordinary_income'] > 0:
            lines.append(f"    Stock Ordinary Income (ESPP discount):      ${liability['stock_ordinary_income']:>14,.2f}")
        if liability['stock_short_term_gains'] > 0:
            lines.append(f"    Short-Term Capital Gains:                    ${liability['stock_short_term_gains']:>14,.2f}")
        if liability.get('net_rental_income', 0) != 0:
            val = liability['net_rental_income']
            if val >= 0:
                lines.append(f"    Net Rental Income (Schedule E):              ${val:>14,.2f}")
            else:
                lines.append(f"    Net Rental Loss (Schedule E):               (${abs(val):>13,.2f})")
        lines.append(f"                                                 {'':>3}{'-' * 14}")
        lines.append(f"    Total Ordinary Income:                       ${liability['total_ordinary_income']:>14,.2f}")
        if liability['total_long_term_gains'] > 0:
            lines.append(f"    Long-Term Capital Gains:                     ${liability['total_long_term_gains']:>14,.2f}")
        lines.append(f"                                                 {'':>3}{'-' * 14}")
        lines.append(f"    Adjusted Gross Income (AGI):                 ${liability['agi']:>14,.2f}")
        lines.append("")

        # Rental detail (if applicable)
        rental_detail = liability.get('rental_detail')
        if rental_detail:
            pct_label = f"{rental_detail['rental_pct']*100:.0f}%"
            lines.append("  SCHEDULE E - RENTAL INCOME")
            lines.append("  " + "-" * 70)
            lines.append(f"    Rental Usage:                                {pct_label:>14}")
            lines.append(f"    Rental Income:                               ${rental_detail['rental_income']:>14,.2f}")
            if rental_detail.get('other_rental_income', 0) > 0:
                lines.append(f"    Other Income:                                ${rental_detail['other_rental_income']:>14,.2f}")
            lines.append(f"    Total Rental Income:                         ${rental_detail['total_income']:>14,.2f}")
            lines.append(f"    Expenses ({pct_label} of property):")
            exp = rental_detail['expenses']
            for key, label in [('mortgage_interest', 'Mortgage Interest'),
                               ('property_taxes', 'Property Taxes'),
                               ('insurance', 'Insurance'),
                               ('hoa', 'HOA'),
                               ('mortgage_insurance', 'Mortgage Insurance'),
                               ('supplies', 'Supplies'),
                               ('electricity', 'Electricity'),
                               ('telephone', 'Telephone'),
                               ('depreciation', 'Depreciation')]:
                val = exp.get(key, 0)
                if val > 0:
                    lines.append(f"      {label:<40}  (${val:>13,.2f})")
            lines.append(f"                                                 {'':>3}{'-' * 14}")
            lines.append(f"    Total Rental Expenses:                      (${rental_detail['total_expenses']:>13,.2f})")
            lines.append(f"    Net Rental Income:                           ${rental_detail['net_rental_income']:>14,.2f}")
            lines.append("")

        # Deductions
        lines.append("  DEDUCTIONS")
        lines.append("  " + "-" * 70)
        itemized_detail = liability.get('itemized_detail')
        if itemized_detail and 'Itemized' in liability['deduction_type']:
            lines.append(f"    Itemized Deductions (Schedule A):")
            if rental_detail:
                lines.append(f"      Mortgage Interest (personal {(1-rental_detail['rental_pct'])*100:.0f}%):          ${itemized_detail['mortgage_interest']:>14,.2f}")
            else:
                lines.append(f"      Mortgage Interest:                         ${itemized_detail['mortgage_interest']:>14,.2f}")
            lines.append(f"      SALT (State tax + property tax):            ${itemized_detail['salt_deduction']:>14,.2f}")
            if itemized_detail['salt_limited']:
                lines.append(f"        (Capped at ${itemized_detail['salt_cap']:,.0f}; uncapped: ${itemized_detail['salt_uncapped']:>11,.2f})")
            if itemized_detail.get('mortgage_insurance', 0) > 0:
                lines.append(f"      Mortgage Insurance Premium:                 ${itemized_detail['mortgage_insurance']:>14,.2f}")
            elif itemized_detail.get('mortgage_insurance_phased_out'):
                lines.append(f"      Mortgage Insurance Premium:                           $0.00")
                lines.append(f"        (Phased out for AGI > $110,000)")
            lines.append(f"                                                 {'':>3}{'-' * 14}")
            lines.append(f"    Total Itemized:                             (${itemized_detail['total_itemized']:>13,.2f})")
            lines.append(f"    Standard Deduction Comparison:               (${self.standard_deduction:>13,.2f})")
            lines.append(f"    -> Using {liability['deduction_type']}")
        else:
            lines.append(f"    {liability['deduction_type']} Deduction ({self.current_year}):              (${liability['deduction_amount']:>13,.2f})")
        lines.append(f"                                                 {'':>3}{'-' * 14}")
        lines.append(f"    Taxable Ordinary Income:                     ${liability['taxable_ordinary_income']:>14,.2f}")
        if liability['taxable_ltcg'] > 0:
            lines.append(f"    Taxable Long-Term Capital Gains:             ${liability['taxable_ltcg']:>14,.2f}")
        lines.append(f"    Total Taxable Income:                        ${liability['total_taxable_income']:>14,.2f}")
        lines.append("")

        # Ordinary income tax brackets
        lines.append("  FEDERAL TAX CALCULATION")
        lines.append("  " + "-" * 70)
        lines.append("    Tax on Ordinary Income (Progressive):")
        for b in liability['ordinary_tax_brackets']:
            rate_pct = f"{b['rate']*100:.0f}%"
            lines.append(f"      {rate_pct:>4} on ${b['income_in_bracket']:>12,.2f}:                    ${b['tax_in_bracket']:>12,.2f}")
        lines.append(f"                                                 {'':>3}{'-' * 14}")
        lines.append(f"    Subtotal - Ordinary Income Tax:               ${liability['ordinary_tax']:>14,.2f}")
        lines.append("")

        # LTCG tax
        if liability['taxable_ltcg'] > 0:
            lines.append("    Tax on Long-Term Capital Gains:")
            for b in liability['ltcg_tax_brackets']:
                rate_pct = f"{b['rate']*100:.0f}%"
                lines.append(f"      {rate_pct:>4} on ${b['gains_in_bracket']:>12,.2f}:                    ${b['tax_in_bracket']:>12,.2f}")
            lines.append(f"                                                 {'':>3}{'-' * 14}")
            lines.append(f"    Subtotal - LTCG Tax:                         ${liability['ltcg_tax']:>14,.2f}")
            lines.append("")

        # NIIT
        if liability['niit'] > 0:
            lines.append(f"    Net Investment Income Tax (3.8%):             ${liability['niit']:>14,.2f}")
            lines.append(f"      (Net investment income: ${liability.get('net_investment_income', 0):>11,.2f})")
            lines.append("")

        lines.append(f"                                                 {'':>3}{'=' * 14}")
        lines.append(f"    TOTAL FEDERAL TAX LIABILITY:                  ${liability['total_tax_liability']:>14,.2f}")
        lines.append("")

        # Payments and withholdings
        lines.append("  PAYMENTS & WITHHOLDINGS")
        lines.append("  " + "-" * 70)
        lines.append(f"    W-2 Federal Tax Withheld (Box 2):           (${liability['federal_tax_withheld']:>13,.2f})")
        if liability['stock_tax_withheld'] > 0:
            lines.append(f"    Stock Sale Withholding:                     (${liability['stock_tax_withheld']:>13,.2f})")
        if liability['estimated_payments'] > 0:
            lines.append(f"    Estimated Tax Payments:                     (${liability['estimated_payments']:>13,.2f})")
        lines.append(f"                                                 {'':>3}{'-' * 14}")
        lines.append(f"    Total Payments:                             (${liability['total_payments']:>13,.2f})")
        lines.append("")

        # Result
        lines.append("  " + "=" * 70)
        if liability['net_tax_due'] > 0:
            lines.append(f"    NET TAX DUE:                                 ${liability['net_tax_due']:>14,.2f}")
        else:
            lines.append(f"    REFUND:                                      ${liability['refund']:>14,.2f}")
        lines.append("")
        lines.append(f"    Effective Tax Rate:                           {liability['effective_tax_rate']:>13.1f}%")
        lines.append(f"    Marginal Ordinary Rate:                       {liability['marginal_ordinary_rate']*100:>13.0f}%")
        lines.append(f"    Marginal LTCG Rate:                           {liability['marginal_ltcg_rate']*100:>13.0f}%")
        lines.append("")

        # Stock transaction detail
        if stock_results:
            is_1099b = any(r.get('source') == '1099-B' for r in stock_results)

            if is_1099b:
                # Show 1099-B summary with wash sale detail
                summary = self.get_1099b_summary(stock_results)
                lines.append("  1099-B SUMMARY")
                lines.append("  " + "-" * 70)
                lines.append(f"    {'':30} {'Short-Term':>16} {'Long-Term':>16} {'Total':>16}")
                lines.append("    " + "-" * 64)
                lines.append(f"    {'Lots':30} {summary['short_term']['count']:>16} {summary['long_term']['count']:>16} {summary['total_count']:>16}")
                lines.append(f"    {'Shares':30} {summary['short_term']['shares']:>16.3f} {summary['long_term']['shares']:>16.3f} {summary['total_shares']:>16.3f}")
                lines.append(f"    {'Proceeds':30} ${summary['short_term']['proceeds']:>14,.2f} ${summary['long_term']['proceeds']:>14,.2f} ${summary['total_proceeds']:>14,.2f}")
                lines.append(f"    {'Cost Basis':30} ${summary['short_term']['cost_basis']:>14,.2f} ${summary['long_term']['cost_basis']:>14,.2f} ${summary['total_cost_basis']:>14,.2f}")
                if summary['total_wash_sale'] > 0:
                    lines.append(f"    {'Wash Sale Disallowed':30} ${summary['short_term']['wash_sale']:>14,.2f} ${summary['long_term']['wash_sale']:>14,.2f} ${summary['total_wash_sale']:>14,.2f}")
                    lines.append(f"    {'Realized Gain/Loss':30} ${summary['short_term']['raw_gain']:>14,.2f} ${summary['long_term']['raw_gain']:>14,.2f} ${summary['short_term']['raw_gain']+summary['long_term']['raw_gain']:>14,.2f}")
                    lines.append(f"    {'Taxable Gain (adjusted)':30} ${summary['short_term']['taxable_gain']:>14,.2f} ${summary['long_term']['taxable_gain']:>14,.2f} ${summary['total_taxable_gain']:>14,.2f}")
                else:
                    lines.append(f"    {'Gain/Loss':30} ${summary['short_term']['taxable_gain']:>14,.2f} ${summary['long_term']['taxable_gain']:>14,.2f} ${summary['total_taxable_gain']:>14,.2f}")
                lines.append("")
            else:
                lines.append("  STOCK TRANSACTION DETAIL")
                lines.append("  " + "-" * 70)
                lines.append(f"    {'Type':<6} {'Acquired':<12} {'Shares':>8} {'Gain/Loss':>14} {'Tax Type':<20}")
                lines.append("    " + "-" * 64)
                for r in stock_results:
                    acq_date = r['acquired_date'].strftime('%Y-%m-%d')
                    gain = r['total_gain']
                    lines.append(f"    {r['stock_type']:<6} {acq_date:<12} {r['shares']:>8.2f} ${gain:>13,.2f} {r['tax_type']:<20}")
                lines.append("")

        # Notes
        lines.append("  NOTES")
        lines.append("  " + "-" * 70)
        lines.append(f"    * This is an estimate based on {self.current_year} federal tax brackets.")
        lines.append("    * Does not account for AMT, tax credits, or other adjustments.")
        lines.append(f"    * NIIT applies when MAGI > ${self.niit_threshold:,}.")
        lines.append("    * Consult a tax professional for your actual filing.")
        lines.append("=" * 80)

        return "\n".join(lines)

    def load_w2_data(self, csv_file: str) -> Dict:
        """
        Load W-2 data from a CSV file.

        Expected CSV columns: Field, Value, Description
        Returns a dict with all W-2 fields parsed as appropriate types.
        """
        df = pd.read_csv(csv_file)
        raw = {}
        for _, row in df.iterrows():
            field = str(row['Field']).strip()
            value = row['Value']
            raw[field] = value

        # Parse into structured dict with numeric conversions
        w2 = {
            'tax_year': int(raw.get('tax_year', self.current_year)),
            'wages': float(raw.get('box1_wages', 0)),
            'federal_tax_withheld': float(raw.get('box2_federal_withheld', 0)),
            'ss_wages': float(raw.get('box3_ss_wages', 0)),
            'ss_tax_withheld': float(raw.get('box4_ss_withheld', 0)),
            'medicare_wages': float(raw.get('box5_medicare_wages', 0)),
            'medicare_tax_withheld': float(raw.get('box6_medicare_withheld', 0)),
            'box12c_life_insurance': float(raw.get('box12c_life_insurance', 0)),
            'box12d_401k': float(raw.get('box12d_401k', 0)),
            'box12w_hsa': float(raw.get('box12w_hsa', 0)),
            'state': str(raw.get('box15_state', '')),
            'state_wages': float(raw.get('box16_state_wages', 0)),
            'state_tax_withheld': float(raw.get('box17_state_tax', 0)),
        }

        # Store any extra fields from box14
        for key, val in raw.items():
            if key.startswith('box14_'):
                w2[key] = float(val) if val else 0

        return w2

    def load_1099b_data(self, csv_file: str) -> List[Dict]:
        """
        Load 1099-B CSV data and return stock results compatible with
        calculate_total_tax_liability().

        The 1099-B data is authoritative for tax filing because it includes
        wash sale adjustments that per-lot recalculation via yfinance cannot
        replicate. This method uses the exact figures from the brokerage's
        1099-B form.

        Expected CSV columns:
            Term, Date Sold, Date Acquired, Proceeds, Cost Basis,
            Wash Sale Disallowed, Gain Loss, Grant Number, Shares, Form 8949 Box
        """
        df = pd.read_csv(csv_file)

        results = []
        for _, row in df.iterrows():
            is_long = str(row['Term']).strip().lower().startswith('long')
            wash_sale = float(row.get('Wash Sale Disallowed', 0) or 0)
            raw_gain = float(row['Gain Loss'])
            # Tax-reportable gain = raw gain + wash sale disallowed
            # (wash sale losses are added back, increasing taxable gain)
            taxable_gain = raw_gain + wash_sale

            # Parse dates
            date_sold = datetime.strptime(str(row['Date Sold']).strip(), '%m/%d/%y')
            date_acquired = datetime.strptime(str(row['Date Acquired']).strip(), '%m/%d/%y')

            shares = float(row['Shares'])
            proceeds = float(row['Proceeds'])
            cost_basis = float(row['Cost Basis'])

            result = {
                'stock_type': 'RSU',
                'acquired_date': date_acquired,
                'sold_date': date_sold,
                'shares': shares,
                'acquisition_price': cost_basis / shares if shares > 0 else 0,
                'sold_price': proceeds / shares if shares > 0 else 0,
                'proceeds': proceeds,
                'cost_basis': cost_basis,
                'total_gain': taxable_gain,
                'raw_gain': raw_gain,
                'wash_sale_disallowed': wash_sale,
                'is_long_term': is_long,
                'tax_type': 'Long Term Capital Gains' if is_long else 'Short Term Capital Gains (Ordinary Income)',
                'tax_rate': 0,  # Will be computed by total liability calculator
                'tax_amount': 0,
                'ordinary_income_portion': 0,
                'capital_gain_portion': taxable_gain,
                'grant_number': str(row.get('Grant Number', 'N/A')),
                'form_8949_box': str(row.get('Form 8949 Box', '')),
                'actually_sold': True,
                'source': '1099-B',
            }

            results.append(result)

        return results

    def get_1099b_summary(self, stock_results: List[Dict]) -> Dict:
        """
        Generate a summary of 1099-B stock results.

        Returns totals for short-term and long-term categories including
        proceeds, cost basis, wash sale adjustments, and gains.
        """
        summary = {
            'short_term': {'proceeds': 0, 'cost_basis': 0, 'wash_sale': 0, 'raw_gain': 0, 'taxable_gain': 0, 'shares': 0, 'count': 0},
            'long_term': {'proceeds': 0, 'cost_basis': 0, 'wash_sale': 0, 'raw_gain': 0, 'taxable_gain': 0, 'shares': 0, 'count': 0},
        }

        for r in stock_results:
            key = 'long_term' if r.get('is_long_term', False) else 'short_term'
            summary[key]['proceeds'] += r.get('proceeds', 0)
            summary[key]['cost_basis'] += r.get('cost_basis', 0)
            summary[key]['wash_sale'] += r.get('wash_sale_disallowed', 0)
            summary[key]['raw_gain'] += r.get('raw_gain', r.get('total_gain', 0))
            summary[key]['taxable_gain'] += r.get('total_gain', 0)
            summary[key]['shares'] += r.get('shares', 0)
            summary[key]['count'] += 1

        summary['total_proceeds'] = summary['short_term']['proceeds'] + summary['long_term']['proceeds']
        summary['total_cost_basis'] = summary['short_term']['cost_basis'] + summary['long_term']['cost_basis']
        summary['total_wash_sale'] = summary['short_term']['wash_sale'] + summary['long_term']['wash_sale']
        summary['total_taxable_gain'] = summary['short_term']['taxable_gain'] + summary['long_term']['taxable_gain']
        summary['total_shares'] = summary['short_term']['shares'] + summary['long_term']['shares']
        summary['total_count'] = summary['short_term']['count'] + summary['long_term']['count']

        return summary

    def load_1098_data(self, csv_file: str) -> Dict:
        """
        Load Form 1098 mortgage data from a CSV file.

        Expected CSV columns: Field, Value, Description
        Returns a dict with mortgage interest, principal, insurance, property taxes,
        and property purchase info for depreciation.
        """
        df = pd.read_csv(csv_file)
        raw = {}
        for _, row in df.iterrows():
            field = str(row['Field']).strip()
            value = row['Value']
            raw[field] = value

        return {
            'lender': str(raw.get('lender', '')),
            'tax_year': int(raw.get('tax_year', self.current_year)),
            'mortgage_interest': float(raw.get('box1_mortgage_interest', 0)),
            'outstanding_principal': float(raw.get('box2_outstanding_principal', 0)),
            'origination_date': str(raw.get('box3_origination_date', '')),
            'mortgage_insurance': float(raw.get('box5_mortgage_insurance', 0)),
            'property_taxes': float(raw.get('box10_property_taxes', 0)),
            'purchase_price': float(raw.get('purchase_price', 0)),
            'purchase_date': str(raw.get('purchase_date', '')),
            'rental_start_date': str(raw.get('rental_start_date', '')),
        }

    def load_1099int_data(self, csv_file: str) -> Dict:
        """
        Load 1099-INT interest income data from a CSV file.

        Expected CSV columns: Payer, Box 1 Interest, Description
        Returns a dict with per-payer details and total interest.
        """
        df = pd.read_csv(csv_file)
        payers = []
        total = 0.0
        for _, row in df.iterrows():
            amount = float(row['Box 1 Interest'])
            payers.append({
                'payer': str(row['Payer']).strip(),
                'interest': amount,
                'description': str(row.get('Description', '')).strip(),
            })
            total += amount

        return {
            'payers': payers,
            'total_interest': round(total, 2),
        }

    def calculate_rental_income(self, rental_pct: float,
                                mortgage_interest: float,
                                property_taxes: float,
                                rental_income: float = 0,
                                other_rental_income: float = 0,
                                mortgage_insurance: float = 0,
                                hoa: float = 0,
                                insurance: float = 0,
                                supplies: float = 0,
                                electricity: float = 0,
                                telephone: float = 0,
                                home_purchase_price: float = 0,
                                rental_start_month: int = 1) -> Dict:
        """
        Calculate Schedule E rental income and expenses.

        All expense amounts should be the FULL annual totals for the property.
        They will be multiplied by rental_pct to get the rental portion.

        Args:
            rental_pct: Rental usage percentage (0-1), e.g. 0.20 for 20%
            mortgage_interest: Full-year mortgage interest (from 1098/spreadsheet)
            property_taxes: Full-year property taxes
            rental_income: Actual rental income received for the year
            other_rental_income: Other income (security deposit interest, etc.)
            mortgage_insurance: Annual mortgage insurance premiums
            hoa: Annual HOA fees
            insurance: Annual homeowner's insurance
            supplies: Supplies expense
            electricity: Electricity expense (rental portion)
            telephone: Telephone/internet expense (rental portion)
            home_purchase_price: Purchase price for depreciation
            rental_start_month: Month rental started (1-12) for partial-year depreciation
        """
        total_income = rental_income + other_rental_income

        # Allocate expenses by rental percentage
        exp = {
            'mortgage_interest': mortgage_interest * rental_pct,
            'property_taxes': property_taxes * rental_pct,
            'mortgage_insurance': mortgage_insurance * rental_pct,
            'hoa': hoa * rental_pct,
            'insurance': insurance * rental_pct,
            'supplies': supplies * rental_pct,
            'electricity': electricity * rental_pct,
            'telephone': telephone * rental_pct,
        }

        # Depreciation: residential rental = 27.5 years, mid-month convention
        depreciation = 0.0
        if home_purchase_price > 0:
            building_value = home_purchase_price * 0.80  # 80% building, 20% land
            rental_building = building_value * rental_pct
            annual_depreciation = rental_building / 27.5
            # Mid-month convention: half month for month placed in service
            months_in_service = 12 - rental_start_month + 0.5
            depreciation = annual_depreciation * (months_in_service / 12)
        exp['depreciation'] = depreciation

        total_expenses = sum(exp.values())
        net_rental_income = total_income - total_expenses

        return {
            'rental_income': rental_income,
            'other_rental_income': other_rental_income,
            'total_income': total_income,
            'rental_pct': rental_pct,
            'expenses': exp,
            'total_expenses': total_expenses,
            'net_rental_income': net_rental_income,
        }

    def calculate_itemized_deductions(self, mortgage_interest: float,
                                       property_taxes: float,
                                       state_income_tax: float,
                                       mortgage_insurance: float,
                                       rental_pct: float = 0,
                                       agi: float = 0) -> Dict:
        """
        Calculate itemized deductions (Schedule A) for the personal-use portion.

        Args:
            mortgage_interest: Total annual mortgage interest from 1098
            property_taxes: Total annual property taxes from 1098
            state_income_tax: State income tax withheld from W-2
            mortgage_insurance: Total annual mortgage insurance from 1098
            rental_pct: Rental usage percentage (0-1), reduces personal portion
            agi: AGI for mortgage insurance phaseout check

        Returns:
            Dict with deduction components and total
        """
        personal_pct = 1.0 - rental_pct

        # Personal-use mortgage interest
        personal_mortgage_interest = mortgage_interest * personal_pct

        # SALT deduction: state/local income tax + personal property taxes
        # 2025+: cap is $40,000 ($20,000 for MFS). Pre-2025: $10,000 under TCJA.
        personal_property_taxes = property_taxes * personal_pct
        salt_uncapped = state_income_tax + personal_property_taxes
        if self.current_year >= 2025:
            salt_cap = 20000 if self.filing_status == 'mfs' else 40000
        else:
            salt_cap = 5000 if self.filing_status == 'mfs' else 10000
        salt_deduction = min(salt_uncapped, salt_cap)

        # Mortgage insurance premium deduction
        # Expired after 2021; reinstated for tax year 2026+ by the One Big Beautiful Bill Act.
        # For 2026+: phases out for AGI > $100,000 (fully phased out at $110,000).
        personal_mortgage_insurance = 0.0
        if self.current_year >= 2026:
            if agi <= 100000:
                personal_mortgage_insurance = mortgage_insurance * personal_pct
            elif agi < 110000:
                phaseout_pct = (110000 - agi) / 10000
                personal_mortgage_insurance = mortgage_insurance * personal_pct * phaseout_pct
            # else: fully phased out

        total_itemized = personal_mortgage_interest + salt_deduction + personal_mortgage_insurance

        return {
            'mortgage_interest': personal_mortgage_interest,
            'salt_state_income_tax': state_income_tax,
            'salt_property_taxes': personal_property_taxes,
            'salt_uncapped': salt_uncapped,
            'salt_deduction': salt_deduction,
            'salt_cap': salt_cap,
            'salt_limited': salt_uncapped > salt_cap,
            'mortgage_insurance': personal_mortgage_insurance,
            'mortgage_insurance_phased_out': self.current_year >= 2026 and agi >= 110000,
            'total_itemized': total_itemized,
        }

    def calculate_bonus_allocation_proceeds_with_taxes(self, bonus_amount: float, purchase_date: datetime,
                                                     rsu_percentage: float, iso_percentage: float,
                                                     target_price: float, ordinary_income: float = 300000) -> Dict[str, float]:
        """
        Calculate proceeds from a bonus distributed between RSUs and ISOs, including tax impacts.
        
        Assumptions:
        - RSUs are held for 1+ year and sold (long-term capital gains)
        - ISOs are exercised via cashless exercise (taxed as ordinary income)
        - Sale occurs 1+ year after grant date
        
        Args:
            bonus_amount: Total bonus amount to be allocated
            purchase_date: Date when stocks were purchased/granted (ISO strike date)
            rsu_percentage: Percentage of bonus allocated to RSUs (0-100)
            iso_percentage: Percentage of bonus allocated to ISOs (0-100)
            target_price: Target sale price for calculating proceeds
            ordinary_income: Current ordinary income for tax bracket calculation (default $300k)
            
        Returns:
            Dictionary containing calculation results including tax implications
        """
        # Get the basic calculation first
        basic_results = self.calculate_bonus_allocation_proceeds(
            bonus_amount, purchase_date, rsu_percentage, iso_percentage, target_price
        )
        
        # Calculate tax implications
        historical_price = basic_results['historical_price']
        rsu_shares = basic_results['rsu_shares']
        iso_shares_total = basic_results['iso_shares_total']
        rsu_proceeds = basic_results['rsu_proceeds']
        iso_proceeds = basic_results['iso_proceeds']
        rsu_allocation = basic_results['rsu_allocation']
        
        # RSU Tax Calculation (Long-term capital gains)
        # RSU gain = proceeds - original allocation (cost basis)
        rsu_gain = rsu_proceeds - rsu_allocation
        ltcg_rate = self.calculate_capital_gains_rate(ordinary_income)
        rsu_taxes = rsu_gain * ltcg_rate
        rsu_after_tax_proceeds = rsu_proceeds - rsu_taxes
        
        # ISO Tax Calculation (Cashless exercise - ordinary income)
        # For cashless exercise, the entire gain is taxed as ordinary income
        marginal_tax_rate = self.calculate_marginal_tax_rate(ordinary_income)
        iso_taxes = iso_proceeds * marginal_tax_rate  # iso_proceeds = gain for cashless
        iso_after_tax_proceeds = iso_proceeds - iso_taxes
        
        # Total after-tax calculations
        total_taxes = rsu_taxes + iso_taxes
        total_after_tax_proceeds = rsu_after_tax_proceeds + iso_after_tax_proceeds
        net_after_tax_gain = total_after_tax_proceeds - bonus_amount
        after_tax_roi = (net_after_tax_gain / bonus_amount) * 100
        
        # Enhanced results including tax impacts
        tax_results = basic_results.copy()
        tax_results.update({
            'ordinary_income': ordinary_income,
            'ltcg_tax_rate': ltcg_rate,
            'marginal_tax_rate': marginal_tax_rate,
            
            # RSU tax details
            'rsu_gain': rsu_gain,
            'rsu_taxes': rsu_taxes,
            'rsu_after_tax_proceeds': rsu_after_tax_proceeds,
            
            # ISO tax details  
            'iso_taxes': iso_taxes,
            'iso_after_tax_proceeds': iso_after_tax_proceeds,
            
            # Total after-tax results
            'total_taxes': total_taxes,
            'total_after_tax_proceeds': total_after_tax_proceeds,
            'net_after_tax_gain': net_after_tax_gain,
            'after_tax_roi': after_tax_roi,
            'effective_tax_rate': (total_taxes / (rsu_gain + iso_proceeds)) * 100 if (rsu_gain + iso_proceeds) > 0 else 0
        })
        
        return tax_results

    def calculate_bonus_allocation_proceeds(self, bonus_amount: float, purchase_date: datetime, 
                                          rsu_percentage: float, iso_percentage: float, 
                                          target_price: float) -> Dict[str, float]:
        """
        Calculate proceeds from a bonus distributed between RSUs and ISOs.
        
        This function assumes ISOs will be exercised using cashless exercise (exercise and sell 
        immediately), which means no upfront cash is needed and proceeds represent pure gain.
        
        Args:
            bonus_amount: Total bonus amount to be allocated
            purchase_date: Date when stocks were purchased/granted (ISO strike date)
            rsu_percentage: Percentage of bonus allocated to RSUs (0-100)
            iso_percentage: Percentage of bonus allocated to ISOs (0-100)
            target_price: Target sale price for calculating proceeds
            
        Returns:
            Dictionary containing calculation results
            
        Note:
            - RSU proceeds = shares × target_price (full sale value)
            - ISO proceeds = shares × (target_price - strike_price) [gain only via cashless exercise]
            - ISO shares are multiplied by 3 as per the algorithm requirement
        """
        # Input validation
        if rsu_percentage + iso_percentage != 100:
            raise ValueError(f"RSU and ISO percentages must sum to 100%. Got: {rsu_percentage}% + {iso_percentage}% = {rsu_percentage + iso_percentage}%")
        
        if bonus_amount <= 0:
            raise ValueError("Bonus amount must be positive")
            
        if target_price <= 0:
            raise ValueError("Target price must be positive")
        
        # Calculate allocation amounts
        rsu_allocation = bonus_amount * (rsu_percentage / 100)
        iso_allocation = bonus_amount * (iso_percentage / 100)
        
        # Get historical stock price at purchase date
        print(f"Fetching Tesla stock price for {purchase_date.strftime('%Y-%m-%d')}...")
        historical_price = self.get_stock_price("TSLA", purchase_date)
        
        if historical_price is None:
            raise ValueError(f"Could not fetch historical price for {purchase_date.strftime('%Y-%m-%d')}")
        
        # Calculate RSU shares
        rsu_shares = rsu_allocation / historical_price
        
        # Calculate ISO shares (multiplied by 3 as per requirement)
        iso_shares_base = iso_allocation / historical_price
        iso_shares_total = iso_shares_base * 3
        
        # Calculate proceeds at target price
        rsu_proceeds = rsu_shares * target_price
        
        # For ISOs with cashless exercise (exercise and sell immediately):
        # - No upfront cash required to exercise
        # - Proceeds = (sale_price - strike_price) × shares
        # - Strike price = historical_price (when ISOs were granted)
        # - This represents pure gain without needing exercise capital
        iso_gain_per_share = target_price - historical_price
        iso_proceeds = iso_shares_total * iso_gain_per_share  # Only the gain portion
        
        total_proceeds = rsu_proceeds + iso_proceeds
        
        # Calculate gains
        rsu_gain = rsu_proceeds - rsu_allocation
        iso_gain = iso_proceeds  # For cashless exercise, proceeds = gain
        total_gain = rsu_gain + iso_gain
        
        # Calculate the actual return on investment (ROI)
        # ROI should be based on total proceeds vs initial bonus investment
        actual_roi = ((total_proceeds - bonus_amount) / bonus_amount) * 100
        
        # Return comprehensive results
        results = {
            'bonus_amount': bonus_amount,
            'purchase_date': purchase_date.strftime('%Y-%m-%d'),
            'historical_price': historical_price,
            'target_price': target_price,
            'rsu_percentage': rsu_percentage,
            'iso_percentage': iso_percentage,
            'rsu_allocation': rsu_allocation,
            'iso_allocation': iso_allocation,
            'rsu_shares': rsu_shares,
            'iso_shares_base': iso_shares_base,
            'iso_shares_total': iso_shares_total,
            'rsu_proceeds': rsu_proceeds,
            'iso_proceeds': iso_proceeds,
            'total_proceeds': total_proceeds,
            'rsu_gain': rsu_gain,
            'iso_gain': iso_gain,
            'total_gain': total_gain,
            'total_return_percentage': actual_roi,  # Fixed ROI calculation
            'net_gain_loss': total_proceeds - bonus_amount  # Net gain or loss
        }
        
        return results
    
    def print_bonus_allocation_report(self, results: Dict[str, float]) -> str:
        """Generate a formatted report for bonus allocation calculation."""
        
        report = f"""
================================================================================
BONUS ALLOCATION PROCEEDS CALCULATION
================================================================================
Bonus Amount: ${results['bonus_amount']:,.2f}
Purchase Date: {results['purchase_date']}
Historical Stock Price: ${results['historical_price']:.2f}
Target Sale Price: ${results['target_price']:.2f}

ALLOCATION BREAKDOWN
----------------------------------------
RSU Allocation: {results['rsu_percentage']:.1f}% = ${results['rsu_allocation']:,.2f}
ISO Allocation: {results['iso_percentage']:.1f}% = ${results['iso_allocation']:,.2f}

SHARES CALCULATION
----------------------------------------
RSU Shares: ${results['rsu_allocation']:,.2f} ÷ ${results['historical_price']:.2f} = {results['rsu_shares']:.4f} shares
ISO Shares (base): ${results['iso_allocation']:,.2f} ÷ ${results['historical_price']:.2f} = {results['iso_shares_base']:.4f} shares
ISO Shares (×3 multiplier): {results['iso_shares_base']:.4f} × 3 = {results['iso_shares_total']:.4f} shares

PROCEEDS AT TARGET PRICE
----------------------------------------
RSU Proceeds: {results['rsu_shares']:.4f} × ${results['target_price']:.2f} = ${results['rsu_proceeds']:,.2f}
ISO Proceeds (Cashless Exercise): {results['iso_shares_total']:.4f} × (${results['target_price']:.2f} - ${results['historical_price']:.2f}) = ${results['iso_proceeds']:,.2f}
  • Strike Price: ${results['historical_price']:.2f}
  • Gain per Share: ${results['target_price']:.2f} - ${results['historical_price']:.2f} = ${results['target_price'] - results['historical_price']:.2f}
  • ISO proceeds are gain-only since this is cashless exercise (no upfront cash needed)
Total Proceeds: ${results['total_proceeds']:,.2f}

GAINS ANALYSIS
----------------------------------------
RSU Gain: ${results['rsu_proceeds']:,.2f} - ${results['rsu_allocation']:,.2f} = ${results['rsu_gain']:,.2f}
ISO Gain: ${results['iso_proceeds']:,.2f} (proceeds = gain for cashless exercise)
Total Investment Gain: ${results['net_gain_loss']:,.2f}
Return on Investment: {results['total_return_percentage']:.2f}%

SUMMARY
----------------------------------------
Initial Investment: ${results['bonus_amount']:,.2f}
Final Proceeds: ${results['total_proceeds']:,.2f}
Net Gain/Loss: ${results['net_gain_loss']:,.2f}
Return on Investment: {results['total_return_percentage']:.2f}%
================================================================================
        """
        
        return report

def main():
    """Main function to run the tax calculator."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Tesla Stock Tax Calculator')
    parser.add_argument('--csv', required=True, help='Path to the stock CSV file')
    parser.add_argument('--income', type=float, required=True, help='Your ordinary income')
    parser.add_argument('--sold-date', help='Sale date (YYYY-MM-DD), defaults to today')
    parser.add_argument('--output', help='Output file for the report')
    parser.add_argument('--export-csv', help='Export results to CSV file')
    
    args = parser.parse_args()
    
    # Parse sold date
    if args.sold_date:
        try:
            sold_date = datetime.strptime(args.sold_date, '%Y-%m-%d')
        except ValueError:
            print("Error: Date must be in YYYY-MM-DD format")
            return
    else:
        sold_date = datetime.now()
    
    # Create calculator and run calculations
    calculator = TaxCalculator()
    
    try:
        results = calculator.calculate_all_taxes(args.csv, args.income, sold_date)
        report = calculator.generate_report(results, args.income, sold_date)
        
        # Create outputs directory if it doesn't exist
        output_dir = "outputs"
        os.makedirs(output_dir, exist_ok=True)
        
        if args.output:
            output_path = os.path.join(output_dir, args.output)
            with open(output_path, 'w') as f:
                f.write(report)
            print(f"Report saved to {output_path}")
        else:
            print(report)
        
        # Export to CSV if requested
        if args.export_csv:
            calculator.export_to_csv(results, args.export_csv)
            
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()