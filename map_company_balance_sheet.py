"""
Universal Company Balance Sheet Mapper
=======================================
Maps any company's balance sheet to standardized schema using:
- Pattern matching with wildcards
- Text normalization
- Fuzzy matching

Usage:
    python map_company_balance_sheet.py --cik 320193 --adsh 0000320193-24-000123
"""

import sys
import re
import argparse
from pathlib import Path
import yaml

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from statement_reconstructor import StatementReconstructor
import psycopg2
from psycopg2.extras import RealDictCursor
from config import config


def normalize_text(text):
    """Normalize text for matching"""
    if not text:
        return ""

    text = str(text).lower()
    text = text.replace("'", "")  # stockholders' → stockholders
    text = text.replace("'", "")  # Smart quotes
    text = re.sub(r'\([^)]*\)', '', text)  # Remove (Note 4), (in millions), etc.
    text = re.sub(r'\s+', ' ', text).strip()  # Normalize whitespace

    return text


def matches_pattern(plabel, pattern):
    """Check if plabel matches pattern (supports wildcards *)"""
    plabel_norm = normalize_text(plabel)
    pattern_norm = normalize_text(pattern)

    if '*' not in pattern_norm:
        # Exact match
        return plabel_norm == pattern_norm

    # Wildcard matching
    if pattern_norm.startswith('*') and pattern_norm.endswith('*'):
        # *XXX* - contains
        search_term = pattern_norm[1:-1]
        return search_term in plabel_norm
    elif pattern_norm.startswith('*'):
        # *XXX - ends with
        search_term = pattern_norm[1:]
        return plabel_norm.endswith(search_term)
    elif pattern_norm.endswith('*'):
        # XXX* - starts with
        search_term = pattern_norm[:-1]
        return plabel_norm.startswith(search_term)

    return False


def find_best_match(plabel, schema_variations):
    """
    Find best matching schema item for a plabel

    Args:
        plabel: Company's plain label
        schema_variations: Dict of {target: [variations]}

    Returns:
        (target, confidence) or (None, 0)
    """
    best_match = None
    best_confidence = 0

    for target, variations in schema_variations.items():
        for variation in variations:
            if matches_pattern(plabel, variation):
                # Calculate confidence based on match type
                if normalize_text(plabel) == normalize_text(variation):
                    confidence = 1.0  # Exact match
                elif '*' not in variation:
                    confidence = 0.95  # Close match
                else:
                    confidence = 0.9  # Wildcard match

                if confidence > best_confidence:
                    best_match = target
                    best_confidence = confidence

    return best_match, best_confidence


def load_schema_variations():
    """Load standardized schema variations from CSV"""
    # For now, hardcode the schema from Plabel Investigation.csv
    # TODO: Load from actual CSV file

    schema = {
        # Assets - Current
        'cash_and_cash_equivalents': ['cash and cash equivalents', 'cash'],
        'short_term_investments': ['short_term investments', 'short-term investments', 'marketable securities', 'marketable debt securities', 'short-term marketable securities'],
        'cash_and_short_term_investments': ['cash and short term investment', 'total cash and short-term investments', 'total cash, cash equivalents, and short-term investments'],
        'account_receivables_net': ['account receivables, net', 'accounts receivable, net*', 'trade receivables', 'trade accounts receivable', 'accounts and notes receivable', 'receivables'],
        'other_receivables': ['other receivables', 'vendor non-trade receivables', 'vendor receivables'],
        'inventory': ['inventory', 'inventories', 'total inventories', 'merchandise inventory', 'materials and supplies'],
        'prepaids': ['prepaids', 'prepayments', 'prepaid expenses'],
        'other_current_assets': ['other current assets'],
        'total_current_assets': ['total current assets'],

        # Assets - Non-Current
        'long_term_investments': ['long term investments', 'long-term investments', 'investments', 'equity and other investments', 'marketable securities', 'long-term marketable securities'],
        'property_plant_equipment_net': ['property plant equipment net', 'property, plant and equipment, net', 'property and equipment, net*', 'property and equipment', 'premises and equipment', 'property'],
        'finance_lease_right_of_use_assets': ['finance lease right of use assets', 'right of use assets'],
        'operating_lease_right_of_use_assets': ['operating lease right-of-use assets', 'operating leases'],
        'intangible_assets': ['intangible assets', 'intangible assets, net'],
        'goodwill': ['goodwill'],
        'goodwill_and_intangible_assets': ['goodwill and intangible assets'],
        'deferred_tax_assets': ['tax assets', 'deferred income tax assets', 'deferred tax assets', 'deferred taxes on income'],
        'other_non_current_assets': ['other non current assets', 'other non-current assets', 'other long-term assets', 'other assets'],
        'total_non_current_assets': ['total non current assets', 'total non-current assets'],
        'total_assets': ['total assets', 'assets'],

        # Liabilities - Current
        'account_payables': ['account payables', 'accounts payable'],
        'other_payables': ['other payables'],
        'accrued_expenses': ['accrued expenses', 'accrued expenses and other', 'accrued liabilities'],
        'accrued_payroll': ['accrued payroll', 'accrued compensation', 'accrued employment costs', 'salaries, benefits and payroll taxes', 'accrued compensation and related benefits', 'accrued wages and withholdings'],
        'short_term_debt': ['short-term debt', 'short-term borrowings', 'commercial paper', 'loans', 'loans and notes payable', 'current maturities of debt', 'notes payable and other borrowings, current', 'debt due within one year', 'long-term debt due within one year'],
        'current_portion_of_long_term_debt': ['current portion of long-term debt', 'current maturities of long-term debt'],
        'finance_lease_obligations_current': ['capital lease obligations current', 'current portion of finance lease liabilities'],
        'operating_lease_obligations_current': ['operating lease obligations current', 'current portion of operating lease liabilities', 'current maturities of operating leases'],
        'tax_payables': ['tax payables', 'accrued income taxes', 'short-term income taxes', 'income taxes payable'],
        'deferred_revenue': ['deferred revenue', 'unearned revenue', 'short-term unearned revenue', 'unexpired subscriptions revenue', 'unearned premiums', 'unearned fees'],
        'other_current_liabilities': ['other current liabilities'],
        'total_current_liabilities': ['total current liabilities'],

        # Liabilities - Non-Current
        'long_term_debt': ['long term debt', 'long-term debt', 'term debt', 'notes payable and other borrowings, non-current', 'debt due after one year'],
        'pension_and_postretirement_benefits': ['pension and postretirement benefits', 'accrued pension liabilities', 'pension and postretirement benefits obligation'],
        'deferred_revenue_non_current': ['deferred revenue non-current', 'deferred revenue long-term', 'long-term unearned revenue', 'deferred revenue, net of current portion'],
        'deferred_tax_liabilities_non_current': ['deferred tax liabilities non-current', 'deferred income taxes', 'deferred taxes on income', 'long-term income taxes'],
        'finance_lease_obligations_non_current': ['finance lease obligations non-current', 'capital lease obligations non-current'],
        'operating_lease_obligations_non_current': ['operating lease obligations non-current', 'long-term operating lease liabilities', 'long-term lease liabilities'],
        'operating_lease_liabilities': ['operating lease liabilities'],
        'commitments_and_contingencies': ['commitments and contingencies*', 'commitments and contingent liabilities'],
        'other_non_current_liabilities': ['other non-current liabilities', 'other long-term liabilities'],
        'total_non_current_liabilities': ['total non-current liabilities'],
        'total_liabilities': ['total liabilities'],

        # Equity
        'treasury_stock': ['treasury stock', 'treasury stock, at cost'],
        'preferred_stock': ['preferred stock*'],
        'common_stock': ['common stock*'],
        'retained_earnings': ['retained earnings', 'accumulated deficit', 'accumulated earnings', 'retained earnings (accumulated deficit)'],
        'additional_paid_in_capital': ['additional paid in capital', 'additional paid-in capital', 'capital in excess of par value of shares', 'capital in excess of par value'],
        'accumulated_other_comprehensive_income_loss': ['accumulated other comprehensive income loss', 'accumulated other comprehensive loss', 'accumulated other comprehensive income', 'accumulated other comprehensive income (loss)', 'accumulated other comprehensive income/(loss)'],
        'other_total_stockholders_equity': ['other total stockholders equity'],
        'total_stockholders_equity': ['total stockholders equity', 'total stockholders\' equity', '*stockholders equity', '*stockholders\' equity', 'total shareholders equity', 'total shareholders\' equity', '*shareholders equity', '*shareholders\' equity', 'total shareowners equity', 'total shareowners\' equity'],
        'total_equity': ['total equity'],
        'redeemable_non_controlling_interests': ['redeemable non-controlling interests', 'redeemable noncontrolling interests in subsidiaries'],
        'minority_interest': ['minority interest', 'noncontrolling interest', 'noncontrolling interests', 'noncontrolling interests in subsidiaries'],
        'total_liabilities_and_total_equity': ['total liabilities and total equity', 'total liabilities and equity', 'total liabilities and stockholders\' equity', 'total liabilities and stockholders equity', 'total liabilities and shareholders\' equity', 'total liabilities and shareholders equity', 'total liabilities and shareowners\' equity', 'total liabilities and shareowners equity'],
    }

    return schema


def map_balance_sheet(cik, adsh, year, quarter, company_name, ticker):
    """Map a company's balance sheet to standardized schema"""

    print(f"\n{'='*80}")
    print(f"MAPPING BALANCE SHEET TO STANDARDIZED SCHEMA")
    print(f"{'='*80}")
    print(f"\nCompany: {company_name} (Ticker: {ticker}, CIK: {cik})")
    print(f"Filing: {adsh}")
    print(f"Dataset: {year}Q{quarter}")

    # Reconstruct balance sheet
    reconstructor = StatementReconstructor(year=year, quarter=quarter)

    result = reconstructor.reconstruct_statement_multi_period(
        cik=cik,
        adsh=adsh,
        stmt_type='BS'
    )

    if not result or not result.get('line_items'):
        print("❌ Failed to reconstruct balance sheet")
        return None

    line_items = result['line_items']
    periods = result.get('periods', [])

    print(f"\n✅ Reconstructed Balance Sheet")
    print(f"   Line items: {len(line_items)}")
    print(f"   Periods: {len(periods)}")

    # Load schema
    schema_variations = load_schema_variations()

    # Map each line item
    mappings = []
    unmapped = []

    for item in line_items:
        plabel = item['plabel']
        tag = item.get('tag', '')

        # Get value for first period
        values = item.get('values', {})
        if isinstance(values, dict) and len(values) > 0:
            value = list(values.values())[0]
        elif isinstance(values, list) and len(values) > 0:
            value = values[0]
        else:
            value = None

        # Find best match
        target, confidence = find_best_match(plabel, schema_variations)

        if target:
            mappings.append({
                'plabel': plabel,
                'target': target,
                'confidence': confidence,
                'value': value,
                'tag': tag
            })
        else:
            unmapped.append({
                'plabel': plabel,
                'value': value,
                'tag': tag
            })

    # Display results
    print(f"\n{'='*80}")
    print("MAPPING RESULTS")
    print(f"{'='*80}")

    print(f"\n✅ Mapped Items ({len(mappings)}):")
    for m in mappings:
        value_str = f"${m['value']:>18,.0f}" if m['value'] and not pd.isna(m['value']) else "N/A"
        conf_marker = "●" if m['confidence'] == 1.0 else "○"
        print(f"\n{conf_marker} {m['plabel'][:60]}")
        print(f"   → {m['target']}")
        print(f"   Value: {value_str} | Confidence: {m['confidence']:.2f}")

    if unmapped:
        print(f"\n⚠️  Unmapped Items ({len(unmapped)}):")
        for u in unmapped:
            value_str = f"${u['value']:>18,.0f}" if u['value'] and not pd.isna(u['value']) else "N/A"
            print(f"   • {u['plabel'][:60]} | {value_str}")

    # Summary
    total = len(mappings) + len(unmapped)
    coverage = len(mappings) / total * 100 if total > 0 else 0

    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"\nTotal items: {total}")
    print(f"Mapped: {len(mappings)} ({coverage:.1f}%)")
    print(f"Unmapped: {len(unmapped)}")
    print(f"Average confidence: {sum(m['confidence'] for m in mappings) / len(mappings):.2f}" if mappings else "N/A")

    # Save to YAML
    output_dir = Path('mappings')
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / f"{ticker}_{cik}_balance_sheet.yaml"

    yaml_data = {
        'company': {
            'cik': cik,
            'name': company_name,
            'ticker': ticker
        },
        'filing': {
            'adsh': adsh,
            'dataset': f'{year}Q{quarter}'
        },
        'statement': 'balance_sheet',
        'mappings': {}
    }

    for m in mappings:
        yaml_data['mappings'][m['plabel']] = {
            'target': m['target'],
            'confidence': m['confidence']
        }

    with open(output_file, 'w') as f:
        yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)

    print(f"\n✅ Mapping saved to: {output_file}")

    return {
        'mappings': mappings,
        'unmapped': unmapped,
        'coverage': coverage
    }


if __name__ == "__main__":
    import pandas as pd

    parser = argparse.ArgumentParser(description='Map company balance sheet to standardized schema')
    parser.add_argument('--cik', required=True, help='Company CIK')
    parser.add_argument('--adsh', required=True, help='Filing ADSH')

    args = parser.parse_args()

    # Get company info from database
    conn = psycopg2.connect(config.get_db_connection())
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT c.company_name, c.ticker, f.source_year, f.source_quarter
        FROM companies c
        JOIN filings f ON c.cik = f.cik
        WHERE c.cik = %s AND f.adsh = %s
    """, (args.cik, args.adsh))

    info = cur.fetchone()
    cur.close()
    conn.close()

    if not info:
        print(f"❌ Filing not found: CIK {args.cik}, ADSH {args.adsh}")
        sys.exit(1)

    map_balance_sheet(
        cik=args.cik,
        adsh=args.adsh,
        year=info['source_year'],
        quarter=info['source_quarter'],
        company_name=info['company_name'],
        ticker=info['ticker'] or 'N/A'
    )
