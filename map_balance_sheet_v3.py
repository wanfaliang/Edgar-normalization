"""
Balance Sheet Mapper v3
=======================
Maps company balance sheets to standardized schema using direct Python logic.

Features:
- Direct Python code instead of pattern parsing
- Fast string matching and position checks
- 6 control items for section classification
- Hierarchical YAML output (detailed_mappings + standardized_schema)

Usage:
    python map_balance_sheet_v3.py --cik 789019 --adsh 0000950170-24-118967
"""

import sys
import argparse
from pathlib import Path
import yaml
import pandas as pd
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from statement_reconstructor import StatementReconstructor
import psycopg2
from psycopg2.extras import RealDictCursor
from config import config


def normalize(text):
    """Normalize text for matching"""
    if not text:
        return ""
    return text.lower().replace('-', ' ').replace(',', '')


def find_control_items(line_items):
    """Find the 6 control items that divide balance sheet sections"""
    control_lines = {}

    for item in line_items:
        plabel = normalize(item['plabel'])
        line_num = item.get('stmt_order', 0)

        if 'total current assets' not in control_lines:
            if 'total' in plabel and 'current' in plabel and 'asset' in plabel:
                control_lines['total current assets'] = line_num

        if 'total assets' not in control_lines:
            if plabel in ['total assets', 'assets total'] or (
                'total' in plabel and 'asset' in plabel and 'current' not in plabel
            ):
                control_lines['total assets'] = line_num

        if 'total current liabilities' not in control_lines:
            if 'total' in plabel and 'current' in plabel and 'liabilit' in plabel:
                control_lines['total current liabilities'] = line_num

        if 'total liabilities' not in control_lines:
            if plabel in ['total liabilities', 'liabilities total'] or (
                'total' in plabel and 'liabilit' in plabel and 'current' not in plabel and 'stockholder' not in plabel
            ):
                control_lines['total liabilities'] = line_num

        if 'total stockholders equity' not in control_lines:
            if ('total' in plabel and ('stockholder' in plabel or 'shareholder' in plabel) and 'equity' in plabel):
                control_lines['total stockholders equity'] = line_num

        if 'total liabilities and total equity' not in control_lines:
            if ('total' in plabel and 'liabilit' in plabel and 'equity' in plabel):
                control_lines['total liabilities and total equity'] = line_num

    return control_lines


def classify_section(line_num, control_lines):
    """Classify item into section based on position"""
    total_current_assets = control_lines.get('total current assets', float('inf'))
    total_assets = control_lines.get('total assets', float('inf'))
    total_current_liabilities = control_lines.get('total current liabilities', float('inf'))
    total_liabilities = control_lines.get('total liabilities', float('inf'))
    total_stockholders_equity = control_lines.get('total stockholders equity', float('inf'))

    if line_num <= total_current_assets:
        return 'current_assets'
    elif line_num <= total_assets:
        return 'non_current_assets'
    elif line_num <= total_current_liabilities:
        return 'current_liabilities'
    elif line_num <= total_liabilities:
        return 'non_current_liabilities'
    elif line_num <= total_stockholders_equity:
        return 'stockholders_equity'
    else:
        return 'equity_total'


def map_line_item(plabel, line_num, control_lines):
    """
    Map a line item to standardized target using direct Python logic.

    Returns target name or None if no match.
    """
    p = normalize(plabel)

    # Get control line numbers for position checks
    total_current_assets = control_lines.get('total current assets', float('inf'))
    total_assets = control_lines.get('total assets', float('inf'))
    total_current_liabilities = control_lines.get('total current liabilities', float('inf'))
    total_liabilities = control_lines.get('total liabilities', float('inf'))

    # CURRENT ASSETS
    if line_num <= total_current_assets:

        # cash_and_cash_equivalents
        if 'cash' in p and ('equivalent' in p or 'equivalents' in p):
            return 'cash_and_cash_equivalents'

        # short_term_investments
        if ('short term' in p or 'short-term' in p) and ('investment' in p or 'marketable securities' in p):
            return 'short_term_investments'

        # accounts_receivables
        if ('account' in p or 'accounts' in p) and ('receivable' in p or 'receivables' in p):
            return 'accounts_receivables'
        if 'trade' in p and ('receivable' in p or 'receivables' in p):
            return 'accounts_receivables'

        # inventory
        if 'inventor' in p:  # matches inventory/inventories
            return 'inventory'

        # prepaid_expenses
        if 'prepaid' in p and ('expense' in p or 'expenses' in p):
            return 'prepaid_expenses'

        # other_current_assets
        if 'other' in p and 'current' in p and 'asset' in p:
            return 'other_current_assets'

        # total_current_assets (control item)
        if 'total' in p and 'current' in p and 'asset' in p:
            return 'total_current_assets'

    # NON-CURRENT ASSETS
    elif line_num <= total_assets:

        # property_plant_equipment_net
        if ('property' in p or 'plant' in p or 'equipment' in p or 'ppe' in p):
            if 'net' in p or 'property plant and equipment' in p:
                return 'property_plant_equipment_net'

        # long_term_investments
        if ('investment' in p or 'marketable securities' in p) and line_num > total_current_assets:
            return 'long_term_investments'

        # goodwill
        if 'goodwill' in p:
            return 'goodwill'

        # intangible_assets_net
        if 'intangible' in p and 'asset' in p:
            return 'intangible_assets_net'

        # finance_lease_right_of_use_assets
        if (('finance' in p or 'capital' in p or 'financial' in p) and
            ('lease' in p or 'leases' in p or 'right of use' in p or 'rou' in p) and
            line_num < total_assets):
            return 'finance_lease_right_of_use_assets'

        # operating_lease_right_of_use_assets
        if (('operating' in p or 'operation' in p) and
            ('lease' in p or 'leases' in p or 'right of use' in p or 'rou' in p) and
            line_num < total_assets):
            return 'operating_lease_right_of_use_assets'

        # deferred_tax_assets
        if 'deferred' in p and ('tax' in p or 'taxes' in p) and 'asset' in p and line_num < total_assets:
            return 'deferred_tax_assets'

        # other_non_current_assets
        if 'other' in p and ('non current' in p or 'noncurrent' in p or 'long term' in p) and 'asset' in p:
            return 'other_non_current_assets'

        # total_assets (control item)
        if p in ['total assets', 'assets total'] or ('total' in p and 'asset' in p and 'current' not in p):
            return 'total_assets'

    # CURRENT LIABILITIES
    elif line_num <= total_current_liabilities:

        # accounts_payables
        if ('account' in p or 'accounts' in p) and ('payable' in p or 'payables' in p):
            return 'accounts_payables'

        # accrued_liabilities
        if 'accrued' in p and ('liabilit' in p or 'expense' in p):
            return 'accrued_liabilities'

        # short_term_debt
        if ('short term' in p or 'current portion' in p) and ('debt' in p or 'borrowing' in p or 'note' in p):
            return 'short_term_debt'

        # deferred_revenue_current
        if ('deferred revenue' in p or 'unearned' in p) and ('current' in p or 'short term' in p):
            return 'deferred_revenue_current'

        # income_taxes_payable
        if ('income tax' in p or 'tax' in p) and ('payable' in p or 'liability' in p) and 'current' in p:
            return 'income_taxes_payable'

        # finance_lease_obligations_current
        if (('current' in p or 'short term' in p) and
            (('finance' in p or 'capital' in p) and ('lease' in p or 'leases' in p or 'right of use' in p or 'rou' in p)) and
            line_num > total_assets):
            return 'finance_lease_obligations_current'

        # operating_lease_obligations_current
        if (('current' in p or 'short term' in p) and
            (('operating' in p or 'operation' in p) and ('lease' in p or 'leases' in p or 'right of use' in p or 'rou' in p)) and
            line_num > total_assets):
            return 'operating_lease_obligations_current'

        # other_current_liabilities
        if 'other' in p and 'current' in p and 'liabilit' in p:
            return 'other_current_liabilities'

        # total_current_liabilities (control item)
        if 'total' in p and 'current' in p and 'liabilit' in p:
            return 'total_current_liabilities'

    # NON-CURRENT LIABILITIES
    elif line_num <= total_liabilities:

        # long_term_debt
        if ('note' in p or 'notes' in p or 'borrowing' in p or 'debt' in p) and ('long term' in p or 'non current' in p or 'after one year' in p or 'after 12 months' in p):
            return 'long_term_debt'

        # pension_and_postretirement_benefits
        if ('pension' in p or 'postretirement' in p or 'retirement' in p) and ('liabilit' in p or 'obligation' in p):
            return 'pension_and_postretirement_benefits'

        # deferred_revenue_non_current
        if ('deferred revenue' in p or 'unearned' in p) and ('long term' in p or 'non current' in p or 'net of current portion' in p):
            return 'deferred_revenue_non_current'

        # deferred_tax_liabilities_non_current
        if ('deferred' in p and ('tax' in p or 'taxes' in p) and line_num > total_current_liabilities):
            return 'deferred_tax_liabilities_non_current'

        # finance_lease_obligations_non_current
        if ((('finance' in p or 'capital' in p) and ('lease' in p or 'leases' in p or 'right of use' in p or 'rou' in p)) and
            line_num > total_current_liabilities):
            return 'finance_lease_obligations_non_current'

        # operating_lease_obligations_non_current
        if ((('operating' in p or 'operation' in p) and ('lease' in p or 'leases' in p or 'right of use' in p or 'rou' in p)) and
            line_num > total_current_liabilities):
            return 'operating_lease_obligations_non_current'

        # commitments_and_contingencies
        if 'commitment' in p or 'contingenc' in p:
            return 'commitments_and_contingencies'

        # other_non_current_liabilities
        if 'other' in p and ('non current' in p or 'noncurrent' in p) and 'liabilit' in p:
            return 'other_non_current_liabilities'

        # total_liabilities (control item)
        if p in ['total liabilities', 'liabilities total'] or ('total' in p and 'liabilit' in p and 'current' not in p and 'stockholder' not in p):
            return 'total_liabilities'

    # STOCKHOLDERS EQUITY
    else:

        # common_stock
        if 'common stock' in p or 'common shares' in p:
            return 'common_stock'

        # preferred_stock
        if 'preferred stock' in p or 'preferred shares' in p:
            return 'preferred_stock'

        # additional_paid_in_capital
        if 'additional paid in capital' in p or 'paid in capital' in p or 'apic' in p:
            return 'additional_paid_in_capital'

        # retained_earnings
        if 'retained earning' in p or 'accumulated earning' in p:
            return 'retained_earnings'

        # accumulated_other_comprehensive_income
        if 'accumulated other comprehensive' in p or 'aoci' in p:
            return 'accumulated_other_comprehensive_income'

        # treasury_stock
        if 'treasury stock' in p or 'treasury shares' in p:
            return 'treasury_stock'

        # noncontrolling_interest
        if 'noncontrolling' in p or 'non controlling' in p or 'minority interest' in p:
            return 'noncontrolling_interest'

        # total_stockholders_equity (control item)
        if ('total' in p and ('stockholder' in p or 'shareholder' in p) and 'equity' in p):
            return 'total_stockholders_equity'

        # total_liabilities_and_total_equity (control item)
        if 'total' in p and 'liabilit' in p and 'equity' in p:
            return 'total_liabilities_and_total_equity'

    return None


def map_balance_sheet(cik, adsh, year, quarter, company_name, ticker):
    """Map a company's balance sheet to standardized schema"""

    print(f"\n{'='*80}")
    print(f"MAPPING BALANCE SHEET TO STANDARDIZED SCHEMA (v3)")
    print(f"{'='*80}")
    print(f"\nCompany: {company_name} (Ticker: {ticker}, CIK: {cik})")
    print(f"Filing: {adsh}")
    print(f"Dataset: {year}Q{quarter}")

    # Reconstruct balance sheet
    print(f"\n📋 Reconstructing balance sheet...")
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

    print(f"✅ Reconstructed Balance Sheet")
    print(f"   Line items: {len(line_items)}")
    print(f"   Periods: {len(periods)}")

    # Find control items
    print(f"\n📍 Finding control items...")
    control_lines = find_control_items(line_items)

    print(f"   Control Items Found:")
    for target, line_num in sorted(control_lines.items(), key=lambda x: x[1]):
        print(f"      {target}: line {line_num}")

    # Map each line item
    print(f"\n🔍 Mapping line items to targets...")

    mappings = []
    unmapped_by_section = defaultdict(list)
    target_to_plabels = defaultdict(list)

    for item in line_items:
        plabel = item['plabel']
        line_num = item.get('stmt_order', 0)

        # Get value for first period
        values = item.get('values', {})
        if isinstance(values, dict) and len(values) > 0:
            value = list(values.values())[0]
        elif isinstance(values, list) and len(values) > 0:
            value = values[0]
        else:
            value = None

        # Classify section
        section = classify_section(line_num, control_lines)

        # Map to target
        target = map_line_item(plabel, line_num, control_lines)

        if target:
            mappings.append({
                'plabel': plabel,
                'target': target,
                'value': value,
                'section': section,
                'confidence': 0.95
            })
            target_to_plabels[target].append(plabel)
        else:
            unmapped_by_section[section].append({
                'plabel': plabel,
                'value': value
            })

    # Aggregate by target
    print(f"\n📊 Aggregating by target...")
    standardized_schema = {}

    for target, source_plabels in target_to_plabels.items():
        # Get section from first mapping
        section = next(
            (m['section'] for m in mappings if m['target'] == target),
            'unknown'
        )

        # Aggregate values across all source plabels
        total_value = 0
        for plabel in source_plabels:
            for item in line_items:
                if item['plabel'] == plabel:
                    values = item.get('values', {})
                    if isinstance(values, dict) and len(values) > 0:
                        first_value = list(values.values())[0]
                        if first_value and not pd.isna(first_value):
                            total_value += first_value
                    break

        standardized_schema[target] = {
            'total_value': total_value if total_value != 0 else None,
            'count': len(source_plabels),
            'section': section,
            'source_items': source_plabels,
            'confidence': 0.95
        }

    # Display results
    print(f"\n{'='*80}")
    print("MAPPING RESULTS")
    print(f"{'='*80}")

    sections_order = ['current_assets', 'non_current_assets', 'current_liabilities',
                      'non_current_liabilities', 'stockholders_equity', 'equity_total']

    for section in sections_order:
        section_mappings = [m for m in mappings if m['section'] == section]

        if section_mappings:
            print(f"\n{section.upper().replace('_', ' ')} ({len(section_mappings)} mapped):")
            for m in section_mappings:
                value_str = f"${m['value']:>18,.0f}" if m['value'] and not pd.isna(m['value']) else "N/A"
                print(f"  • {m['plabel'][:50]}")
                print(f"    → {m['target']}")
                print(f"    Value: {value_str}")

    # Display unmapped items
    total_unmapped = sum(len(items) for items in unmapped_by_section.values())
    if total_unmapped > 0:
        print(f"\n⚠️  UNMAPPED ITEMS ({total_unmapped}):\n")
        for section in sections_order:
            items = unmapped_by_section[section]
            if items:
                print(f"  {section.replace('_', ' ').title()} ({len(items)}):")
                for item in items:
                    value_str = f"${item['value']:>18,.0f}" if item['value'] and not pd.isna(item['value']) else "N/A"
                    print(f"    • {item['plabel'][:50]} | {value_str}")

    # Summary
    total = len(mappings) + total_unmapped
    coverage = len(mappings) / total * 100 if total > 0 else 0

    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"\nTotal items: {total}")
    print(f"Mapped: {len(mappings)} ({coverage:.1f}%)")
    print(f"Unmapped: {total_unmapped}")
    print(f"Unique standardized targets: {len(standardized_schema)}")

    # Save to YAML
    output_dir = Path('mappings')
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / f"{ticker}_{cik}_balance_sheet_v3.yaml"

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
        'control_items': control_lines,
        'detailed_mappings': [],
        'standardized_schema': {}
    }

    # Add detailed mappings
    for m in mappings:
        yaml_data['detailed_mappings'].append({
            'plabel': m['plabel'],
            'target': m['target'],
            'value': float(m['value']) if m['value'] and not pd.isna(m['value']) else None,
            'section': m['section'],
            'confidence': m['confidence']
        })

    # Add standardized schema
    for target, data in standardized_schema.items():
        yaml_data['standardized_schema'][target] = {
            'total_value': float(data['total_value']) if data['total_value'] else None,
            'count': data['count'],
            'section': data['section'],
            'source_items': data['source_items'],
            'confidence': data['confidence']
        }

    with open(output_file, 'w') as f:
        yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)

    print(f"\n✅ Mapping saved to: {output_file}")

    return {
        'detailed_mappings': mappings,
        'standardized_schema': standardized_schema,
        'unmapped': unmapped_by_section,
        'coverage': coverage,
        'line_items': line_items,
        'periods': periods
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Map balance sheet to standardized schema (v3)')
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
