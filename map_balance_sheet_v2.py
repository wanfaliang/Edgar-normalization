"""
Balance Sheet Mapper v2
=======================
Maps company balance sheets to standardized schema using patterns from CSV v4.

Features:
- Pattern matching with position_before/position_after operators
- 6 control items for section classification
- Aggregation rules: multiple plabels → one target
- First-match rule: one plabel → multiple targets
- Hierarchical YAML output (detailed_mappings + standardized_schema)
- Excel export with reconstructed + standardized sheets

Usage:
    python map_balance_sheet_v2.py --cik 789019 --adsh 0000950170-24-118967
"""

import sys
import argparse
from pathlib import Path
import yaml
import pandas as pd
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from statement_reconstructor import StatementReconstructor
from pattern_parser import parse_pattern
import psycopg2
from psycopg2.extras import RealDictCursor
from config import config


def load_balance_sheet_schema_from_csv():
    """Load balance sheet schema from CSV v4"""
    csv_path = Path('docs/Plabel_Investigation_v4.csv')
    df = pd.read_csv(csv_path)

    # Filter to balance sheet items
    bs_df = df[df['Statements'] == 'balance sheet'].copy()

    # Build schema dictionary
    schema = {}
    for _, row in bs_df.iterrows():
        target = row['Target']
        pattern = row['Common Variations']

        if pd.notna(target) and pd.notna(pattern):
            schema[target] = pattern

    return schema


def find_control_items(line_items, schema):
    """
    Find the 6 control items that divide balance sheet sections.

    Returns:
        dict with keys for each control item and their line numbers
    """
    control_targets = [
        'total current assets',
        'total assets',
        'total current liabilities',
        'total liabilities',
        'total stockholders equity',
        'total liabilities and total equity'
    ]

    control_lines = {}

    for item in line_items:
        plabel = item['plabel']
        line_num = item.get('stmt_order', 0)

        # Check each control target
        for target in control_targets:
            if target in control_lines:
                continue  # Already found

            # Get pattern for this target
            pattern = schema.get(target)
            if pattern and parse_pattern(pattern, plabel):
                control_lines[target] = line_num
                break

    return control_lines


def build_target_line_numbers(line_items):
    """
    Build a mapping of target names to their line numbers.

    This is used for position_before/position_after operators.
    Uses hardcoded logic to identify specific anchor items.

    Returns:
        dict mapping target field names to line numbers
    """
    target_lines = {}

    for item in line_items:
        plabel = item['plabel'].lower()
        line_num = item.get('stmt_order', 0)

        # Hardcoded logic to identify anchor items for balance sheet
        if target_lines.get('accounts_receivables') is None:
            if ('account' in plabel or 'accounts' in plabel) and ('receivable' in plabel or 'receivables' in plabel):
                target_lines['accounts_receivables'] = line_num

        if target_lines.get('inventory') is None:
            if 'inventor' in plabel:  # matches inventory/inventories
                target_lines['inventory'] = line_num

        if target_lines.get('accounts_payables') is None:
            if ('account' in plabel or 'accounts' in plabel) and ('payable' in plabel or 'payables' in plabel):
                target_lines['accounts_payables'] = line_num

        if target_lines.get('total_current_assets') is None:
            if 'total' in plabel and 'current' in plabel and 'asset' in plabel:
                target_lines['total_current_assets'] = line_num

    return target_lines


def classify_item_section(line_num, control_lines):
    """
    Classify item into section based on position relative to control items.

    Sections:
    - current_assets: before total_current_assets
    - non_current_assets: after total_current_assets, before total_assets
    - current_liabilities: after total_assets, before total_current_liabilities
    - non_current_liabilities: after total_current_liabilities, before total_liabilities
    - stockholders_equity: after total_liabilities, before total_stockholders_equity
    - equity_total: after total_stockholders_equity
    """
    if not control_lines:
        return 'unknown'

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


def map_balance_sheet(cik, adsh, year, quarter, company_name, ticker):
    """Map a company's balance sheet to standardized schema"""

    print(f"\n{'='*80}")
    print(f"MAPPING BALANCE SHEET TO STANDARDIZED SCHEMA (v2)")
    print(f"{'='*80}")
    print(f"\nCompany: {company_name} (Ticker: {ticker}, CIK: {cik})")
    print(f"Filing: {adsh}")
    print(f"Dataset: {year}Q{quarter}")

    # Load schema from CSV v4
    print(f"\n📋 Loading patterns from CSV v4...")
    schema = load_balance_sheet_schema_from_csv()
    print(f"   Loaded {len(schema)} patterns")

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

    # Step 1: Find control items
    print(f"\n📍 Finding control items...")
    control_lines = find_control_items(line_items, schema)

    print(f"   Control Items Found:")
    for target, line_num in sorted(control_lines.items(), key=lambda x: x[1]):
        print(f"      {target}: line {line_num}")

    # Step 2: Build target line numbers for position operators
    print(f"\n📍 Building target line numbers...")
    target_line_numbers = build_target_line_numbers(line_items)
    print(f"   Mapped {len(target_line_numbers)} targets to line numbers")
    for target, line_num in sorted(target_line_numbers.items(), key=lambda x: x[1]):
        print(f"      {target}: line {line_num}")

    # Step 3: Map each line item
    print(f"\n🔍 Mapping line items to targets...")

    # Track which plabels have been matched to which targets
    plabel_to_targets = defaultdict(list)  # plabel -> [list of matching targets]
    target_to_plabels = defaultdict(list)  # target -> [list of matching plabels]

    mappings = []
    unmapped_by_section = defaultdict(list)

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
        section = classify_item_section(line_num, control_lines)

        # Build context for pattern matching
        context = {
            'line_num': line_num,
            'target_line_numbers': target_line_numbers
        }

        # Try to match against all schema patterns
        matched_targets = []
        for target, pattern in schema.items():
            if parse_pattern(pattern, plabel, context):
                matched_targets.append(target)

        if matched_targets:
            # Store all matches for aggregation rules
            plabel_to_targets[plabel] = matched_targets
            for target in matched_targets:
                target_to_plabels[target].append(plabel)

            # Apply balance sheet rules:
            # If one plabel matches multiple targets → take first match only
            selected_target = matched_targets[0]

            mappings.append({
                'plabel': plabel,
                'target': selected_target,
                'value': value,
                'section': section,
                'confidence': 0.9,
                'all_matches': matched_targets  # Track all matches for diagnostics
            })
        else:
            # Unmapped item
            unmapped_by_section[section].append({
                'plabel': plabel,
                'value': value
            })

    # Step 4: Aggregate by target (Option C - Hierarchical Structure)
    # Balance sheet rule: If multiple plabels match one target → aggregate values
    print(f"\n📊 Aggregating by target...")
    standardized_schema = {}

    for target in schema.keys():
        if target not in target_to_plabels:
            continue  # No mappings for this target

        # Get all plabels that mapped to this target
        source_plabels = target_to_plabels[target]

        # Get section from first mapping
        section = next(
            (m['section'] for m in mappings if m['target'] == target),
            'unknown'
        )

        # Aggregate values across all source plabels and all periods
        total_value = 0
        for plabel in source_plabels:
            # Find the item with this plabel
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
            'confidence': 0.9
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
                if len(m['all_matches']) > 1:
                    print(f"    ⚠️  Multiple matches: {m['all_matches']} (using first)")
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

    # Display standardized schema
    print(f"\n{'='*80}")
    print("STANDARDIZED SCHEMA (AGGREGATED)")
    print(f"{'='*80}")

    for section in sections_order:
        section_targets = {k: v for k, v in standardized_schema.items() if v['section'] == section}

        if section_targets:
            print(f"\n{section.upper().replace('_', ' ')} ({len(section_targets)} unique targets):")
            for target, data in section_targets.items():
                value_str = f"${data['total_value']:>18,.0f}" if data['total_value'] else "N/A"
                print(f"  • {target}")
                print(f"    Total: {value_str}")
                if data['count'] > 1:
                    print(f"    ⚠️  Aggregated from {data['count']} items:")
                    for source in data['source_items']:
                        print(f"      - {source[:60]}")

    # Summary
    total = len(mappings) + total_unmapped
    coverage = len(mappings) / total * 100 if total > 0 else 0
    unique_targets = len(standardized_schema)

    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"\nTotal items: {total}")
    print(f"Mapped: {len(mappings)} ({coverage:.1f}%)")
    print(f"Unmapped: {total_unmapped}")
    print(f"Unique standardized targets: {unique_targets}")
    print(f"Average confidence: {sum(m['confidence'] for m in mappings) / len(mappings):.2f}" if mappings else "N/A")

    # Save to YAML
    output_dir = Path('mappings')
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / f"{ticker}_{cik}_balance_sheet_v2.yaml"

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
    parser = argparse.ArgumentParser(description='Map balance sheet to standardized schema (v2)')
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
