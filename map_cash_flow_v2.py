"""
Cash Flow Statement Mapper v2
=============================
Maps company cash flow statements to standardized schema using patterns from CSV.

Uses the pattern parser to evaluate complex natural language patterns.

Usage:
    python map_cash_flow_v2.py --cik 789019 --adsh 0000950170-24-118967
"""

import sys
import argparse
from pathlib import Path
import yaml
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from statement_reconstructor import StatementReconstructor
from pattern_parser import parse_pattern
import psycopg2
from psycopg2.extras import RealDictCursor
from config import config


def load_cash_flow_schema_from_csv():
    """Load cash flow schema from CSV v3"""
    csv_path = Path('docs/Plabel Investigation v3.csv')

    df = pd.read_csv(csv_path)

    # Filter to cash flow statement items
    cf_df = df[df['Statements'] == 'cash flow statement'].copy()

    # Build schema dictionary
    schema = {}
    for _, row in cf_df.iterrows():
        target = row['Target']
        pattern = row['Common Variations']

        if pd.notna(target) and pd.notna(pattern):
            schema[target] = pattern

    return schema


def find_control_items(line_items, schema):
    """
    Find the 3 control items that divide cash flow sections.

    Returns:
        dict with keys 'operating', 'investing', 'financing'
        Each value is the line_num (stmt_order) of that control item
    """
    control_targets = {
        'net cash provided by operating activities': 'operating',
        'net cash provided by investing activities': 'investing',
        'net cash provided by financing activities': 'financing'
    }

    control_lines = {}

    for item in line_items:
        plabel = item['plabel']
        line_num = item.get('stmt_order', 0)

        # Check each control target
        for target, section in control_targets.items():
            if section in control_lines:
                continue  # Already found

            # Get pattern for this target
            pattern = schema.get(target)
            if pattern and parse_pattern(pattern, plabel):
                control_lines[section] = line_num
                break

    return control_lines


def classify_item_section(line_num, control_lines):
    """
    Classify item into operating/investing/financing based on line position

    The control items mark the END of their respective sections.
    Items up to and including each control item belong to that section.
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


def map_cash_flow_statement(cik, adsh, year, quarter, company_name, ticker):
    """Map a company's cash flow statement to standardized schema"""

    print(f"\n{'='*80}")
    print(f"MAPPING CASH FLOW STATEMENT TO STANDARDIZED SCHEMA (v2)")
    print(f"{'='*80}")
    print(f"\nCompany: {company_name} (Ticker: {ticker}, CIK: {cik})")
    print(f"Filing: {adsh}")
    print(f"Dataset: {year}Q{quarter}")

    # Load schema from CSV
    print(f"\n📋 Loading patterns from CSV...")
    schema = load_cash_flow_schema_from_csv()
    print(f"   Loaded {len(schema)} patterns")

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
    control_lines = find_control_items(line_items, schema)

    print(f"\n📍 Control Items Found:")
    for section, line_num in sorted(control_lines.items(), key=lambda x: x[1]):
        print(f"   {section.capitalize()}: line {line_num}")

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

        # Try to match against schema patterns
        matched_target = None
        for target, pattern in schema.items():
            if parse_pattern(pattern, plabel):
                matched_target = target
                break

        if matched_target:
            mappings.append({
                'plabel': plabel,
                'target': matched_target,
                'value': value,
                'section': section,
                'confidence': 0.9
            })
        else:
            if section in unmapped_by_section:
                unmapped_by_section[section].append({
                    'plabel': plabel,
                    'value': value
                })

    # Step 3: Aggregate mappings by target (Option C - Hierarchical Structure)
    standardized_schema = {}
    for m in mappings:
        target = m['target']

        if target not in standardized_schema:
            standardized_schema[target] = {
                'total_value': 0,
                'count': 0,
                'section': m['section'],
                'source_items': [],
                'confidence': m['confidence']
            }

        # Aggregate values
        if m['value'] and not pd.isna(m['value']):
            standardized_schema[target]['total_value'] += m['value']

        standardized_schema[target]['count'] += 1
        standardized_schema[target]['source_items'].append(m['plabel'])

    # Display results by section
    print(f"\n{'='*80}")
    print("DETAILED MAPPING RESULTS")
    print(f"{'='*80}")

    sections_order = ['operating', 'financing', 'investing', 'supplemental']
    for section in sections_order:
        section_mappings = [m for m in mappings if m['section'] == section]

        if section_mappings:
            print(f"\n{section.upper()} ACTIVITIES ({len(section_mappings)} mapped):")
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
                print(f"  {section.capitalize()} ({len(items)}):")
                for item in items:
                    value_str = f"${item['value']:>18,.0f}" if item['value'] and not pd.isna(item['value']) else "N/A"
                    print(f"    • {item['plabel'][:50]} | {value_str}")

    # Display standardized schema (aggregated by target)
    print(f"\n{'='*80}")
    print("STANDARDIZED SCHEMA (AGGREGATED)")
    print(f"{'='*80}")

    for section in sections_order:
        section_targets = {k: v for k, v in standardized_schema.items() if v['section'] == section}

        if section_targets:
            print(f"\n{section.upper()} ACTIVITIES ({len(section_targets)} unique targets):")
            for target, data in section_targets.items():
                value_str = f"${data['total_value']:>18,.0f}" if data['total_value'] != 0 else "N/A"
                print(f"  • {target}")
                print(f"    Total: {value_str}")
                if data['count'] > 1:
                    print(f"    Aggregated from {data['count']} items:")
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

    output_file = output_dir / f"{ticker}_{cik}_cash_flow_v2.yaml"

    # Build hierarchical YAML structure (Option C)
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

    # Add standardized schema (aggregated)
    for target, data in standardized_schema.items():
        yaml_data['standardized_schema'][target] = {
            'total_value': float(data['total_value']) if data['total_value'] != 0 else None,
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
        'coverage': coverage
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Map company cash flow statement to standardized schema (v2)')
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
