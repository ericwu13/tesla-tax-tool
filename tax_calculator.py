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


class TaxCalculator:
    """Class to handle tax calculations for Tesla stock grants."""
    
    def __init__(self):
        # 2025 Federal Tax Brackets (Single filer)
        self.tax_brackets_single = [
            (0, 0.10),          # 10% on income up to $10,275
            (10275, 0.12),      # 12% on income from $10,275 to $41,775
            (41775, 0.22),      # 22% on income from $41,775 to $89,450
            (89450, 0.24),      # 24% on income from $89,450 to $190,750
            (190750, 0.32),     # 32% on income from $190,750 to $243,725
            (243725, 0.35),     # 35% on income from $243,725 to $609,350
            (609350, 0.37)      # 37% on income over $609,350
        ]
        
        # 2025 Capital Gains Tax Brackets (Single filer)
        self.capital_gains_brackets_single = [
            (0, 0.0),           # 0% on capital gains up to $47,025
            (47025, 0.15),      # 15% on capital gains from $47,025 to $518,900
            (518900, 0.20)      # 20% on capital gains over $518,900
        ]
        
        # Tesla ESPP plan dates (offer periods typically start in February and August)
        # Each offer period lasts 6 months
        self.tesla_espp_periods = {
            2019: [datetime(2019, 2, 1), datetime(2019, 8, 1)],
            2020: [datetime(2020, 2, 1), datetime(2020, 8, 1)],
            2021: [datetime(2021, 2, 1), datetime(2021, 8, 1)],
            2022: [datetime(2022, 2, 1), datetime(2022, 8, 1)],
            2023: [datetime(2023, 2, 1), datetime(2023, 8, 1)],
            2024: [datetime(2024, 2, 1), datetime(2024, 8, 1)],
            2025: [datetime(2025, 2, 1), datetime(2025, 8, 1)],
        }
    
    def calculate_marginal_tax_rate(self, ordinary_income: float) -> float:
        """Calculate the marginal tax rate based on ordinary income."""
        for threshold, rate in reversed(self.tax_brackets_single):
            if ordinary_income > threshold:
                return rate
        return self.tax_brackets_single[0][1]
    
    def calculate_capital_gains_rate(self, ordinary_income: float) -> float:
        """Calculate the capital gains tax rate based on ordinary income."""
        for threshold, rate in reversed(self.capital_gains_brackets_single):
            if ordinary_income > threshold:
                return rate
        return self.capital_gains_brackets_single[0][1]
    
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
            start_date = (date - timedelta(days=5)).strftime('%Y-%m-%d')
            end_date = (date + timedelta(days=5)).strftime('%Y-%m-%d')
            
            hist = ticker.history(start=start_date, end=end_date)
            
            if hist.empty:
                raise ValueError(f"No data found for {symbol} around {date}")
            
            # Find the closest trading day
            target_date = date.strftime('%Y-%m-%d')
            if target_date in hist.index:
                return hist.loc[target_date]['Close']
            else:
                # Get the closest date
                closest_date = min(hist.index, key=lambda x: abs((x.date() - date.date()).days))
                return hist.loc[closest_date]['Close']
        
        except Exception as e:
            print(f"Error fetching stock price for {symbol} on {date}: {e}")
            return 0.0
    
    def load_stock_data(self, csv_file: str) -> pd.DataFrame:
        """Load and parse the stock CSV data."""
        df = pd.read_csv(csv_file)
        
        # Clean up the dataframe
        df = df.dropna(how='all')  # Remove empty rows
        df = df[df['Test'].notna()]  # Remove rows with no data
        df = df[df['Test'] != 'Overall Total']  # Remove summary row
        
        # Parse dates
        df['Date Acquired'] = df['Date Acquired'].apply(self.parse_date)
        df = df[df['Date Acquired'].notna()]  # Remove rows with invalid dates
        
        # Parse numeric values
        df['Sellable Qty.'] = pd.to_numeric(df['Sellable Qty.'], errors='coerce')
        df['Expected Gain/Loss'] = df['Expected Gain/Loss'].apply(self.parse_currency)
        df['Est. Market Value'] = df['Est. Market Value'].apply(self.parse_currency)
        df['Tax'] = df['Tax'].apply(self.parse_currency)
        
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
        
        # For RSUs, the basis is the FMV at vesting (when acquired)
        # The Expected Gain/Loss shows gain based on current market value
        # We need to back-calculate the acquisition price from this
        expected_gain = row['Expected Gain/Loss']
        current_market_value = row['Est. Market Value']
        
        # acquisition_value = current_market_value - expected_gain
        acquisition_value = current_market_value - expected_gain
        acquisition_price = acquisition_value / shares if shares > 0 else 0
        
        # Calculate proceeds and gains based on actual sold price
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
            'ordinary_income_portion': 0  # RSUs don't have ordinary income portion at sale
        }
    
    def calculate_espp_taxes(self, row: pd.Series, sold_date: datetime, 
                            sold_price: float, ordinary_income: float) -> Dict:
        """Calculate taxes for ESPP transactions."""
        purchase_date = row['Date Acquired']
        shares = row['Sellable Qty.']
        
        # Infer offer date
        offer_date = self.get_tesla_offer_date(purchase_date)
        
        # Determine if qualifying disposition
        is_qualifying = self.is_qualifying_espp_disposition(offer_date, purchase_date, sold_date)
        
        # Calculate the purchase price from the data
        # Expected gain is the difference between current market value and what was paid
        expected_gain = row['Expected Gain/Loss']
        market_value = row['Est. Market Value']
        purchase_value = market_value - expected_gain
        purchase_price_per_share = purchase_value / shares if shares > 0 else 0
        
        # Calculate proceeds and total gain
        proceeds = shares * sold_price
        total_gain = proceeds - purchase_value
        
        if is_qualifying:
            # Qualifying disposition
            # For qualifying disposition, the ordinary income portion is the lesser of:
            # 1. The discount at grant (typically 15% of FMV at offer date)
            # 2. The actual gain on sale
            
            # Estimate FMV at offer date (reverse engineer from 15% discount)
            # Tesla ESPP typically offers 15% discount off the lower of offer/purchase price
            estimated_offer_fmv = purchase_price_per_share / 0.85
            discount_per_share = estimated_offer_fmv * 0.15
            total_discount = discount_per_share * shares
            
            ordinary_income_portion = min(total_discount, total_gain)
            capital_gain_portion = max(0, total_gain - ordinary_income_portion)
            
            # Tax calculation
            ordinary_tax = ordinary_income_portion * self.calculate_marginal_tax_rate(ordinary_income)
            capital_gains_tax = capital_gain_portion * self.calculate_capital_gains_rate(ordinary_income)
            total_tax = ordinary_tax + capital_gains_tax
            tax_type = 'Qualifying ESPP'
            
        else:
            # Disqualifying disposition
            # The discount amount is treated as ordinary income
            # The remaining gain is capital gains
            
            # Estimate the FMV at purchase date for discount calculation
            # We'll use a simplified approach where the discount is ~15%
            estimated_fmv_at_purchase = purchase_price_per_share / 0.85
            discount_per_share = estimated_fmv_at_purchase - purchase_price_per_share
            discount_amount = discount_per_share * shares
            
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
            'shares': shares,
            'acquisition_price': purchase_price_per_share,
            'sold_price': sold_price,
            'proceeds': proceeds,
            'total_gain': total_gain,
            'is_qualifying': is_qualifying,
            'is_long_term': is_qualifying or self.is_long_term(purchase_date, sold_date),
            'tax_type': tax_type,
            'tax_amount': total_tax,
            'ordinary_income_portion': ordinary_income_portion
        }
    
    def calculate_all_taxes(self, csv_file: str, ordinary_income: float, 
                           sold_date: Optional[datetime] = None) -> List[Dict]:
        """Calculate taxes for all stock transactions."""
        if sold_date is None:
            sold_date = datetime.now()
        
        # Load stock data
        df = self.load_stock_data(csv_file)
        
        # Get Tesla stock price for the sold date
        sold_price = self.get_stock_price('TSLA', sold_date)
        
        if sold_price == 0:
            print(f"Warning: Could not fetch Tesla stock price for {sold_date}. Using current price.")
            sold_price = self.get_stock_price('TSLA', datetime.now())
        
        results = []
        
        for index, row in df.iterrows():
            try:
                if row['Stock_Type'] == 'RSU':
                    result = self.calculate_rsu_taxes(row, sold_date, sold_price, ordinary_income)
                elif row['Stock_Type'] == 'ESPP':
                    result = self.calculate_espp_taxes(row, sold_date, sold_price, ordinary_income)
                else:
                    continue
                
                # Add additional info
                result['grant_number'] = row.get('Grant Number', 'N/A')
                result['original_tax_status'] = row.get('Tax Status', 'N/A')
                
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
                report.append(f"  Shares: {r['shares']:.2f}")
                report.append(f"  Purchase Price: ${r['acquisition_price']:.2f}")
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
                'Holding_Period': 'Long Term' if r['is_long_term'] else 'Short Term',
                'Tax_Type': r['tax_type'],
                'Tax_Rate': r.get('tax_rate', 0),
                'Tax_Amount': r['tax_amount'],
                'Ordinary_Income_Portion': r.get('ordinary_income_portion', 0)
            }
            
            # Add ESPP-specific fields
            if r['stock_type'] == 'ESPP':
                row['Offer_Date'] = r['offer_date'].strftime('%Y-%m-%d')
                row['Disposition_Type'] = 'Qualifying' if r['is_qualifying'] else 'Disqualifying'
            else:
                row['Offer_Date'] = ''
                row['Disposition_Type'] = ''
            
            csv_data.append(row)
        
        # Create DataFrame and save to CSV
        df = pd.DataFrame(csv_data)
        
        # Reorder columns for better readability
        column_order = [
            'Stock_Type', 'Grant_Number', 'Acquired_Date', 'Offer_Date',
            'Shares', 'Acquisition_Price', 'Sold_Price', 'Proceeds',
            'Total_Gain', 'Holding_Period', 'Disposition_Type',
            'Tax_Type', 'Tax_Rate', 'Tax_Amount', 'Ordinary_Income_Portion'
        ]
        
        df = df[column_order]
        df.to_csv(filename, index=False)
        print(f"Results exported to CSV: {filename}")


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
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(report)
            print(f"Report saved to {args.output}")
        else:
            print(report)
        
        # Export to CSV if requested
        if args.export_csv:
            calculator.export_to_csv(results, args.export_csv)
            
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()