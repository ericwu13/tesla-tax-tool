"""
Flask Web UI for Tax App.

Provides a browser-based drag-and-drop interface to upload PDF tax forms
and calculate federal + CA taxes. Wraps the existing pipeline:
    scan_form() → build_tax_inputs() → TaxCalculator
"""

import os
import sys
import tempfile
import shutil
from datetime import datetime

from flask import Flask, request, jsonify, render_template

from form_scanner import scan_form_multi
from tax_app import build_tax_inputs
from tax_calculator import TaxCalculator
from projection_engine import project_full_year
from form_parsers.vesting_parser import parse_vesting_xlsx
from form_parsers.paystub_parser import parse_paystub

# When running inside a PyInstaller bundle, templates (and other data files)
# are extracted to a temporary directory pointed to by sys._MEIPASS.
if getattr(sys, 'frozen', False):
    _base = sys._MEIPASS
else:
    _base = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, template_folder=os.path.join(_base, 'templates'))


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    """Accept uploaded files, scan each, return extracted data as JSON."""
    files = request.files.getlist('files')
    if not files:
        return jsonify({'error': 'No files uploaded'}), 400

    tax_year = request.form.get('tax_year', type=int) or datetime.now().year
    tmp_dir = tempfile.mkdtemp(prefix='taxapp_')

    results = []
    try:
        for f in files:
            if not f.filename:
                continue
            tmp_path = os.path.join(tmp_dir, f.filename)
            f.save(tmp_path)
            try:
                scanned_list = scan_form_multi(tmp_path, tax_year=tax_year)
                for scanned in scanned_list:
                    scanned['source_file'] = f.filename
                    results.append(scanned)
            except Exception as e:
                results.append({
                    'form_type': 'error',
                    'data': {'error': str(e)},
                    'source_file': f.filename,
                })
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return jsonify({'forms': results, 'tax_year': tax_year})


@app.route('/calculate', methods=['POST'])
def calculate():
    """Accept form data + settings, run tax calculation, return results."""
    payload = request.get_json()
    if not payload or 'forms' not in payload:
        return jsonify({'error': 'Missing form data'}), 400

    forms = payload['forms']
    filing_status = payload.get('filing_status', 'single')
    tax_year = payload.get('tax_year') or datetime.now().year
    estimated_payments = float(payload.get('estimated_payments', 0))
    manual_property_tax = float(payload.get('property_tax', 0))
    manual_mortgage_interest = float(payload.get('mortgage_interest', 0))
    rental_pct = float(payload.get('rental_pct', 0))

    # Build inputs from the (possibly user-corrected) form data
    inputs = build_tax_inputs(forms)

    # Manual values override 1098-extracted values
    if manual_property_tax > 0:
        inputs['property_taxes'] = manual_property_tax
    if manual_mortgage_interest > 0:
        inputs['mortgage_interest'] = manual_mortgage_interest

    calc = TaxCalculator(tax_year=tax_year, filing_status=filing_status)

    # Estimate AGI for mortgage insurance phaseout calculation
    stock_gains = sum(r.get('total_gain', 0) for r in inputs['stock_results'])
    estimated_agi = inputs['w2_wages'] + inputs['interest_income'] + stock_gains

    # Itemized deductions — consider whenever SALT or mortgage data exists
    itemized_result = None
    if (inputs['mortgage_interest'] > 0 or inputs['property_taxes'] > 0
            or inputs['state_tax_withheld'] > 0):
        itemized_result = calc.calculate_itemized_deductions(
            mortgage_interest=inputs['mortgage_interest'],
            property_taxes=inputs['property_taxes'],
            state_income_tax=inputs['state_tax_withheld'],
            mortgage_insurance=inputs['mortgage_insurance'],
            rental_pct=rental_pct,
            agi=estimated_agi,
        )

    # Federal tax liability
    liability = calc.calculate_total_tax_liability(
        w2_wages=inputs['w2_wages'],
        federal_tax_withheld=inputs['fed_withheld'],
        stock_results=inputs['stock_results'],
        estimated_payments=estimated_payments,
        interest_income=inputs['interest_income'],
        itemized_result=itemized_result,
    )

    report = calc.generate_tax_liability_report(liability, inputs['stock_results'])

    # CA state tax
    ca_report = ''
    if inputs['state_wages'] > 0:
        st_gains = sum(
            r.get('total_gain', 0) for r in inputs['stock_results']
            if not r.get('is_long_term', False)
        )
        lt_gains = sum(
            r.get('total_gain', 0) for r in inputs['stock_results']
            if r.get('is_long_term', False)
        )
        ca_itemized = None
        personal_pct = 1.0 - rental_pct
        if inputs['mortgage_interest'] > 0 or inputs['property_taxes'] > 0:
            ca_itemized = (inputs['mortgage_interest'] * personal_pct
                           + inputs['property_taxes'] * personal_pct)

        ca_result = calc.calculate_ca_state_tax(
            w2_state_wages=inputs['state_wages'],
            interest_income=inputs['interest_income'],
            stock_short_term_gains=st_gains,
            stock_long_term_gains=lt_gains,
            ca_itemized_deductions=ca_itemized,
            state_tax_withheld=inputs['state_tax_withheld'],
        )
        ca_report = calc.generate_ca_tax_report_section(ca_result)

    full_report = report + ca_report

    ca_summary = {}
    if ca_report:
        ca_summary = {
            'total_income': ca_result.get('ca_total_income', 0),
            'taxable_income': ca_result.get('ca_taxable_income', 0),
            'total_tax': ca_result.get('ca_tax', 0),
            'withheld': ca_result.get('ca_state_tax_withheld', 0),
            'net_due': ca_result.get('ca_net_tax_due', 0),
            'refund': ca_result.get('ca_refund', 0),
            'effective_rate': ca_result.get('ca_effective_rate', 0),
        }

    return jsonify({
        'report': full_report,
        'federal': {
            'agi': liability.get('agi', 0),
            'taxable_income': liability.get('total_taxable_income', 0),
            'total_tax': liability.get('total_tax_liability', 0),
            'withheld': liability.get('total_payments', 0),
            'net_due': liability.get('net_tax_due', 0),
            'refund': liability.get('refund', 0),
            'effective_rate': liability.get('effective_tax_rate', 0),
            'deduction_type': liability.get('deduction_type', ''),
            'deduction_amount': liability.get('deduction_amount', 0),
        },
        'california': ca_summary,
        'inputs': inputs,
    })


@app.route('/stock_price/<ticker>', methods=['GET'])
def stock_price(ticker):
    """Fetch current stock price via yfinance."""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        info = t.fast_info
        price = info.get('lastPrice', 0) or info.get('last_price', 0)
        if not price:
            # fallback: get from recent history
            hist = t.history(period='1d')
            if not hist.empty:
                price = float(hist['Close'].iloc[-1])
        return jsonify({'ticker': ticker.upper(), 'price': round(price, 2)})
    except Exception as e:
        return jsonify({'error': str(e), 'ticker': ticker.upper(), 'price': 0}), 200


@app.route('/upload_paystub', methods=['POST'])
def upload_paystub():
    """Accept a paystub PDF and return extracted YTD data as JSON."""
    f = request.files.get('file')
    if not f or not f.filename:
        return jsonify({'error': 'No file uploaded'}), 400

    tmp_dir = tempfile.mkdtemp(prefix='taxapp_stub_')
    try:
        tmp_path = os.path.join(tmp_dir, f.filename)
        f.save(tmp_path)
        data = parse_paystub(tmp_path)
        return jsonify({'paystub': data})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.route('/upload_vesting', methods=['POST'])
def upload_vesting():
    """Accept an E*TRADE XLSX vesting file and return parsed events as JSON."""
    f = request.files.get('file')
    if not f or not f.filename:
        return jsonify({'error': 'No file uploaded'}), 400

    tmp_dir = tempfile.mkdtemp(prefix='taxapp_vest_')
    try:
        tmp_path = os.path.join(tmp_dir, f.filename)
        f.save(tmp_path)
        events = parse_vesting_xlsx(tmp_path)
        return jsonify({'events': events})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.route('/calculate_midyear', methods=['POST'])
def calculate_midyear():
    """Accept mid-year data, project full year, and run tax calculation."""
    payload = request.get_json()
    if not payload:
        return jsonify({'error': 'Missing request data'}), 400

    filing_status = payload.get('filing_status', 'single')
    tax_year = payload.get('tax_year') or datetime.now().year
    estimated_payments = float(payload.get('estimated_payments', 0))
    rental_pct = float(payload.get('rental_pct', 0))

    paystub_data = payload.get('paystub', {})
    vesting_events = payload.get('vesting_events', [])
    user_inputs = {
        'filing_status': filing_status,
        'tax_year': tax_year,
        'estimated_stock_price': float(payload.get('estimated_stock_price', 0)),
        'planned_sales': payload.get('planned_sales', []),
        'estimated_interest': float(payload.get('estimated_interest', 0)),
        'mortgage_interest': float(payload.get('mortgage_interest', 0)),
        'property_taxes': float(payload.get('property_taxes', 0)),
        'rental_pct': rental_pct,
        'estimated_payments': estimated_payments,
    }

    # Project full-year values
    inputs, assumptions = project_full_year(paystub_data, vesting_events, user_inputs)

    # Run through TaxCalculator (same logic as /calculate)
    calc = TaxCalculator(tax_year=tax_year, filing_status=filing_status)

    stock_gains = sum(r.get('total_gain', 0) for r in inputs['stock_results'])
    estimated_agi = inputs['w2_wages'] + inputs['interest_income'] + stock_gains

    itemized_result = None
    if (inputs['mortgage_interest'] > 0 or inputs['property_taxes'] > 0
            or inputs['state_tax_withheld'] > 0):
        itemized_result = calc.calculate_itemized_deductions(
            mortgage_interest=inputs['mortgage_interest'],
            property_taxes=inputs['property_taxes'],
            state_income_tax=inputs['state_tax_withheld'],
            mortgage_insurance=inputs['mortgage_insurance'],
            rental_pct=rental_pct,
            agi=estimated_agi,
        )

    liability = calc.calculate_total_tax_liability(
        w2_wages=inputs['w2_wages'],
        federal_tax_withheld=inputs['fed_withheld'],
        stock_results=inputs['stock_results'],
        estimated_payments=estimated_payments,
        interest_income=inputs['interest_income'],
        itemized_result=itemized_result,
    )

    report = calc.generate_tax_liability_report(liability, inputs['stock_results'])

    # CA state tax
    ca_report = ''
    ca_summary = {}
    if inputs['state_wages'] > 0:
        st_gains = sum(
            r.get('total_gain', 0) for r in inputs['stock_results']
            if not r.get('is_long_term', False)
        )
        lt_gains = sum(
            r.get('total_gain', 0) for r in inputs['stock_results']
            if r.get('is_long_term', False)
        )
        ca_itemized = None
        personal_pct = 1.0 - rental_pct
        if inputs['mortgage_interest'] > 0 or inputs['property_taxes'] > 0:
            ca_itemized = (inputs['mortgage_interest'] * personal_pct
                           + inputs['property_taxes'] * personal_pct)

        ca_result = calc.calculate_ca_state_tax(
            w2_state_wages=inputs['state_wages'],
            interest_income=inputs['interest_income'],
            stock_short_term_gains=st_gains,
            stock_long_term_gains=lt_gains,
            ca_itemized_deductions=ca_itemized,
            state_tax_withheld=inputs['state_tax_withheld'],
        )
        ca_report = calc.generate_ca_tax_report_section(ca_result)
        ca_summary = {
            'total_income': ca_result.get('ca_total_income', 0),
            'taxable_income': ca_result.get('ca_taxable_income', 0),
            'total_tax': ca_result.get('ca_tax', 0),
            'withheld': ca_result.get('ca_state_tax_withheld', 0),
            'net_due': ca_result.get('ca_net_tax_due', 0),
            'refund': ca_result.get('ca_refund', 0),
            'effective_rate': ca_result.get('ca_effective_rate', 0),
        }

    full_report = report + ca_report

    return jsonify({
        'report': full_report,
        'is_projection': True,
        'assumptions': assumptions,
        'federal': {
            'agi': liability.get('agi', 0),
            'taxable_income': liability.get('total_taxable_income', 0),
            'total_tax': liability.get('total_tax_liability', 0),
            'withheld': liability.get('total_payments', 0),
            'net_due': liability.get('net_tax_due', 0),
            'refund': liability.get('refund', 0),
            'effective_rate': liability.get('effective_tax_rate', 0),
            'deduction_type': liability.get('deduction_type', ''),
            'deduction_amount': liability.get('deduction_amount', 0),
        },
        'california': ca_summary,
        'inputs': inputs,
    })


if __name__ == '__main__':
    app.run(debug=True, port=8080)
