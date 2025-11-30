"""
Cash Flow Statement Mapper
===========================
Map company cash flow statements to standardized schema.

Strategy:
1. Find 3 control items (operating, investing, financing)
2. Classify items by section based on line position
3. Pattern matching from square brackets
4. Aggregate unmapped items into other_*_activities

Usage:
    python map_cash_flow.py --cik 1018724 --adsh 0001018724-24-000083
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


# Items to skip - they're calculated
CALCULATED_ITEMS = {
    'operating_cash_flow',
    'capital_expenditure',
    'free_cash_flow'
}


def normalize_text(text):
    """Normalize text for matching"""
    if not text:
        return ""

    text = str(text).lower()
    text = text.replace("'", "")
    text = text.replace("'", "")
    text = text.replace('-', ' ')
    text = text.replace(',', '')
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def contains_all_terms(text, terms):
    """Check if text contains all terms"""
    text_lower = normalize_text(text)
    return all(term.lower() in text_lower for term in terms)


def contains_any_term(text, terms):
    """Check if text contains any term"""
    text_lower = normalize_text(text)
    return any(term.lower() in text_lower for term in terms)


def find_control_items(line_items):
    """
    Find the 3 control items that divide cash flow sections.

    Returns:
        dict with keys 'operating', 'investing', 'financing'
        Each value is the line_num (stmt_order) of that control item
    """
    control_patterns = {
        'operating': [
            ['cash', 'operating activities'],
            ['cash', 'operations'],  # Microsoft style
            ['cash', 'operating']
        ],
        'investing': [
            ['cash', 'investing activities'],
            ['cash', 'investing'],  # Microsoft style
        ],
        'financing': [
            ['cash', 'financing activities'],
            ['cash', 'financing']  # Microsoft style
        ]
    }

    control_lines = {}

    for item in line_items:
        plabel = item['plabel']
        line_num = item.get('stmt_order', item.get('line_num', 0))

        matched_this_item = False
        for section, pattern_variations in control_patterns.items():
            # Skip if we already found this section's control item
            if section in control_lines:
                continue

            # Try each pattern variation
            for required_terms in pattern_variations:
                # Must contain all required terms
                if contains_all_terms(plabel, required_terms):
                    # Should NOT contain "other"
                    if 'other' not in normalize_text(plabel):
                        control_lines[section] = line_num
                        matched_this_item = True
                        break
            if matched_this_item:
                break  # This item matched a section, move to next item

    return control_lines


def classify_item_section(line_num, control_lines):
    """
    Classify item into operating/investing/financing based on line position

    The control items mark the END of their respective sections.
    Items up to and including each control item belong to that section.

    Args:
        line_num: Line number of the item
        control_lines: Dict with operating/investing/financing line numbers

    Returns:
        'operating' | 'investing' | 'financing' | 'supplemental'
    """
    if not control_lines:
        return 'unknown'

    # Sort control items by line number to handle any order
    sorted_controls = sorted(control_lines.items(), key=lambda x: x[1])

    # Find which section this line belongs to
    for section, control_line in sorted_controls:
        if line_num <= control_line:
            return section

    # If after all control items, it's supplemental (e.g., cash at end)
    return 'supplemental'


def pattern_matches(plabel, pattern):
    """
    Check if plabel matches a pattern.

    Pattern syntax:
        [contains X] - contains term X
        [contains X and contains Y] - contains at least one from X AND at least one from Y
        [contains X or Y] - contains either X or Y
        not [contains X] - does not contain X

    Args:
        plabel: Plain label text
        pattern: Pattern string with square brackets

    Returns:
        bool
    """
    plabel_norm = normalize_text(plabel)

    # Handle "not" patterns
    if ' not [' in pattern:
        parts = pattern.split(' not [')
        positive_pattern = parts[0].strip()
        negative_pattern = '[' + parts[1]

        # Must match positive and NOT match negative
        return (pattern_matches(plabel, positive_pattern) and
                not pattern_matches(plabel, negative_pattern))

    # Remove square brackets
    pattern = pattern.strip('[]')

    # Handle "contains X and contains Y" (multiple AND clauses)
    if ' and contains ' in pattern:
        # Split into parts: ["contains X", "Y", "Z", ...]
        parts = pattern.split(' and contains ')

        # Process each part
        for i, part in enumerate(parts):
            # Remove "contains " prefix from first part
            if i == 0 and part.startswith('contains '):
                part = part[len('contains '):]

            # Check if this part has "or" alternatives
            if ' or ' in part:
                # This part has alternatives - check if ANY match
                alternatives = [alt.strip() for alt in part.split(' or ')]
                if not any(alt.lower() in plabel_norm for alt in alternatives):
                    return False  # This AND clause failed
            else:
                # Single term - check if it's present
                if part.strip().lower() not in plabel_norm:
                    return False  # This AND clause failed

        return True  # All AND clauses passed

    # Handle "contains X or Y" (single OR clause, no AND)
    if ' or ' in pattern:
        # Remove "contains " prefix if present
        if pattern.startswith('contains '):
            pattern = pattern[len('contains '):]

        terms = [t.strip() for t in pattern.split(' or ')]
        return any(term.lower() in plabel_norm for term in terms)

    # Simple "contains X"
    if pattern.startswith('contains '):
        term = pattern[len('contains '):].strip()
        return term.lower() in plabel_norm

    # Equals pattern
    if pattern.startswith('equals to'):
        target = pattern.replace('equals to', '').strip()
        return plabel_norm == normalize_text(target)

    return False


def load_cash_flow_schema():
    """Load cash flow schema with pattern-based variations"""

    schema = {
        # Operating Activities
        'net_income': [
            '[contains net income or net earnings or net income (loss)]'
        ],
        'depreciation_and_amortization': [
            '[contains depreciation and contains amortization]'
        ],
        'depreciation': [
            '[contains depreciation] not [contains amortization]'
        ],
        'amortization': [
            '[contains amortization] not [contains depreciation]'
        ],
        'deferred_income_tax': [
            '[contains deferred and contains tax or taxes]'
        ],
        'impairments': [
            '[contains impairments or impairment]'
        ],
        'pension_and_postretirement': [
            '[contains pension or postretirement]'
        ],
        'stock_based_compensation': [
            '[contains stock based and contains compensation]',
            '[contains stock-based and contains compensation]'
        ],
        'accounts_receivables': [
            '[contains account or accounts and contains receivable or receivables]'
        ],
        'inventory': [
            '[contains inventory or inventories]'
        ],
        'prepaids': [
            '[contains prepaids or prepaid or prepayments or prepayment]'
        ],
        'accounts_payables': [
            '[contains account or accounts and contains payable or payables]'
        ],
        'accrued_expenses': [
            '[contains accrued]'
        ],
        'unearned_revenue': [
            '[contains unearned]'
        ],
        'income_taxes_payable': [
            '[contains income taxes and contains payable or payables]'
        ],
        'other_working_capital': [
            '[contains other working capital]'
        ],
        'other_assets': [
            '[contains other and contains assets]'
        ],
        'other_liabilities': [
            '[contains other and contains liabilities]'
        ],
        'net_cash_provided_by_operating_activities': [
            '[contains cash and contains operating activities] not [contains other or others]',
            '[contains cash and contains operations] not [contains other or others]',  # Microsoft style
            '[contains cash and contains operating] not [contains other or others]'
        ],

        # Investing Activities
        'investments_in_property_plant_and_equipment': [
            '[contains expenditure or expenditures or purchases or purchase or acquisition or acquisitions and contains property or plant or plants or equipment or equipments or ppe]'
        ],
        'proceeds_from_sales_of_ppe': [
            '[contains proceeds or sale or sales or disposition and contains property or plant or equipment or equipments or ppe]'
        ],
        'acquisitions_of_business_net': [
            '[contains business or businesses and contains acquisition or acquisitions]'
        ],
        'proceeds_from_divestiture': [
            '[contains divestiture]',
            '[contains sale or sales or disposition and contains business or businesses]'
        ],
        'purchases_of_investments': [
            '[contains purchases or purchase or acquisition or acquisitions and contains investments or securities]'
        ],
        'sales_maturities_of_investments': [
            '[contains sales or sale or maturity or maturities or proceeds and contains investments or securities]'
        ],
        'net_cash_provided_by_investing_activities': [
            '[contains cash and contains investing activities] not [contains other or others]',
            '[contains cash and contains investing] not [contains other or others]'  # Microsoft style
        ],

        # Financing Activities
        'short_term_debt_issuance': [
            '[contains short term and contains issuance or proceeds]',
            '[contains short-term and contains issuance or proceeds]'
        ],
        'long_term_net_debt_issuance': [
            '[contains long term and contains issuance or proceeds]',
            '[contains long-term and contains issuance or proceeds]'
        ],
        'short_term_debt_repayment': [
            '[contains short term and contains repayment or repayments]',
            '[contains short-term and contains repayment or repayments]'
        ],
        'long_term_net_debt_repayment': [
            '[contains long term and contains repayment or repayments]',
            '[contains long-term and contains repayment or repayments]'
        ],
        'term_debt_issuance': [
            '[contains debt and contains issuance or proceeds] not [contains short term or long term or short-term or long-term]'
        ],
        'term_debt_repayment': [
            '[contains debt and contains repayment or repayments] not [contains short term or long term or short-term or long-term]'
        ],
        'common_stock_issuance': [
            '[contains common stock or common stocks or shares and contains issuance or proceeds] not [contains net]'
        ],
        'common_stock_repurchased': [
            '[contains treasury and contains purchases or purchase]',
            '[contains stocks or stock and contains purchase or purchases]',
            '[contains repurchase or repurchases or repurchased]'
        ],
        'dividends_paid': [
            '[contains dividends] not [contains common or contains preferred]'
        ],
        'common_dividends_paid': [
            '[contains dividends or dividend and contains common] not [contains preferred]'
        ],
        'net_cash_provided_by_financing_activities': [
            '[contains cash and contains financing activities] not [contains other or others]',
            '[contains cash and contains financing] not [contains other or others]'  # Microsoft style
        ],

        # Other Items
        'effect_of_foreign_exchanges_rate_changes_on_cash': [
            '[contains exchange or exchanges or foreign currency or foreign currencies]'
        ],
        'net_change_in_cash': [
            '[contains net change or net increase (decrease) or net increase or net decrease and contains cash]'
        ],
        'cash_at_end_of_period': [
            '[contains cash and contains end]'
        ],
        'cash_at_beginning_of_period': [
            '[contains cash and contains beginning]'
        ],
        'income_taxes_paid': [
            '[contains income taxes and contains paid or payments or payment]'
        ],
        'interest_paid': [
            '[contains interest paid or interests paid]',
            '[contains payments or payment or paid and contains interest or interests]'
        ]
    }

    return schema


def find_best_match(plabel, section, schema_patterns):
    """
    Find best matching schema item using pattern matching

    Args:
        plabel: Plain label
        section: Section this item belongs to (operating/investing/financing)
        schema_patterns: Schema with pattern variations

    Returns:
        (target, confidence, learned_pattern) or (None, 0, None)
    """
    for target, patterns in schema_patterns.items():
        for pattern in patterns:
            if pattern_matches(plabel, pattern):
                return target, 0.9, None

    return None, 0, None


def map_cash_flow_statement(cik, adsh, year, quarter, company_name, ticker):
    """Map a company's cash flow statement to standardized schema"""

    print(f"\n{'='*80}")
    print(f"MAPPING CASH FLOW STATEMENT TO STANDARDIZED SCHEMA")
    print(f"{'='*80}")
    print(f"\nCompany: {company_name} (Ticker: {ticker}, CIK: {cik})")
    print(f"Filing: {adsh}")
    print(f"Dataset: {year}Q{quarter}")

    # Reconstruct cash flow statement
    reconstructor = StatementReconstructor(year=year, quarter=quarter)

    result = reconstructor.reconstruct_statement_multi_period(
        cik=cik,
        adsh=adsh,
        stmt_type='CF'
    )

    if not result or not result.get('line_items'):
        print("❌ Failed to reconstruct cash flow statement")
        return None

    line_items = result['line_items']
    periods = result.get('periods', [])

    print(f"\n✅ Reconstructed Cash Flow Statement")
    print(f"   Line items: {len(line_items)}")
    print(f"   Periods: {len(periods)}")

    # Step 1: Find control items
    control_lines = find_control_items(line_items)

    print(f"\n📍 Control Items Found:")
    for section, line_num in control_lines.items():
        print(f"   {section.capitalize()}: line {line_num}")

    # Load schema
    schema_patterns = load_cash_flow_schema()

    # Step 2: Map each line item
    mappings = []
    unmapped_by_section = {
        'operating': [],
        'investing': [],
        'financing': [],
        'supplemental': []
    }

    for item in line_items:
        plabel = item['plabel']
        tag = item.get('tag', '')
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
        section = classify_item_section(line_num, control_lines)

        # Find best match
        target, confidence, _ = find_best_match(plabel, section, schema_patterns)

        if target:
            # Skip calculated items
            if target in CALCULATED_ITEMS:
                continue

            mappings.append({
                'plabel': plabel,
                'target': target,
                'confidence': confidence,
                'value': value,
                'tag': tag,
                'section': section,
                'line_num': line_num
            })
        else:
            # Track unmapped by section
            if section in unmapped_by_section:
                unmapped_by_section[section].append({
                    'plabel': plabel,
                    'value': value,
                    'tag': tag,
                    'line_num': line_num
                })

    # Display results
    print(f"\n{'='*80}")
    print("MAPPING RESULTS")
    print(f"{'='*80}")

    # Group by section
    for section_name in ['operating', 'investing', 'financing', 'supplemental']:
        section_mappings = [m for m in mappings if m['section'] == section_name]
        if section_mappings:
            print(f"\n{section_name.upper()} ACTIVITIES ({len(section_mappings)} mapped):")
            for m in section_mappings:
                import pandas as pd
                value_str = f"${m['value']:>18,.0f}" if m['value'] and not pd.isna(m['value']) else "N/A"
                print(f"  • {m['plabel'][:50]}")
                print(f"    → {m['target']}")
                print(f"    Value: {value_str}")

    # Show unmapped
    total_unmapped = sum(len(items) for items in unmapped_by_section.values())
    if total_unmapped > 0:
        print(f"\n⚠️  UNMAPPED ITEMS ({total_unmapped}):")
        for section, items in unmapped_by_section.items():
            if items:
                print(f"\n  {section.capitalize()} ({len(items)}):")
                for item in items:
                    import pandas as pd
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
    print(f"Average confidence: {sum(m['confidence'] for m in mappings) / len(mappings):.2f}" if mappings else "N/A")

    # Save to YAML
    output_dir = Path('mappings')
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / f"{ticker}_{cik}_cash_flow.yaml"

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
        'statement': 'cash_flow',
        'control_items': control_lines,
        'mappings': {}
    }

    for m in mappings:
        yaml_data['mappings'][m['plabel']] = {
            'target': m['target'],
            'confidence': m['confidence'],
            'section': m['section']
        }

    with open(output_file, 'w') as f:
        yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)

    print(f"\n✅ Mapping saved to: {output_file}")

    return {
        'mappings': mappings,
        'unmapped': unmapped_by_section,
        'coverage': coverage
    }


if __name__ == "__main__":
    import pandas as pd

    parser = argparse.ArgumentParser(description='Map company cash flow statement to standardized schema')
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

    map_cash_flow_statement(
        cik=args.cik,
        adsh=args.adsh,
        year=info['source_year'],
        quarter=info['source_quarter'],
        company_name=info['company_name'],
        ticker=info['ticker'] or 'N/A'
    )
