"""
Analyze unmapped items across multiple companies to identify mapping gaps.

This script:
1. Processes N companies from the filing index
2. Identifies line items that were NOT mapped to any standardized field
3. Collects metadata for each unmapped item
4. Generates frequency statistics for (plabel, tag) pairs
5. Exports detailed results to Excel

Usage:
    python analyze_unmapped_items.py --num 50 --year 2024 --quarter 2
    python analyze_unmapped_items.py --num 500 --year 2024 --quarter 2
"""

import sys
sys.path.insert(0, '../src')

import argparse
import psycopg2
from psycopg2.extras import RealDictCursor
from pathlib import Path
from collections import defaultdict
import pandas as pd
from datetime import datetime

from map_financial_statements import map_financial_statements
from config import config


def get_companies_from_db(num_companies, year, quarter):
    """Get list of companies from PostgreSQL database"""
    conn = psycopg2.connect(config.get_db_connection())
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Get companies with filings in specified quarter
    query = """
    SELECT c.cik, c.company_name, c.ticker, f.adsh, f.form_type
    FROM companies c
    JOIN filings f ON c.cik = f.cik
    WHERE f.source_year = %s AND f.source_quarter = %s
    AND f.form_type IN ('10-K', '10-Q')
    ORDER BY c.cik
    LIMIT %s
    """

    cur.execute(query, (year, quarter, num_companies))
    companies = cur.fetchall()
    cur.close()
    conn.close()

    return [dict(c) for c in companies]


def analyze_company(cik, adsh, year, quarter, company_name, ticker):
    """Analyze a single company's filing and return unmapped items"""
    unmapped_items = []

    try:
        results = map_financial_statements(cik, adsh, year, quarter, company_name, ticker)

        # Analyze each statement type
        for stmt_type in ['balance_sheet', 'income_statement', 'cash_flow']:
            if stmt_type not in results:
                continue

            stmt_result = results[stmt_type]
            line_items = stmt_result.get('line_items', [])
            mappings = stmt_result.get('mappings', [])

            # Create set of mapped plabels
            mapped_plabels = {m.get('plabel', '') for m in mappings}

            # Find unmapped items
            for item in line_items:
                plabel = item.get('plabel', '')
                line_num = item.get('stmt_order', 0)

                if plabel not in mapped_plabels:
                    # This item was not mapped
                    unmapped_items.append({
                        'cik': cik,
                        'adsh': adsh,
                        'stmt_type': stmt_type,
                        'plabel': plabel,
                        'tag': item.get('tag', ''),
                        'line_num': line_num,
                        'datatype': item.get('datatype', ''),
                        'custom': item.get('custom', ''),
                        'negating': item.get('negating', ''),
                        'value': item.get('value') or list(item.get('values', {}).values())[0] if item.get('values') else None
                    })

        return unmapped_items, None

    except Exception as e:
        return [], str(e)


def main():
    parser = argparse.ArgumentParser(description="Analyze unmapped items across companies")
    parser.add_argument('--num', type=int, default=50, help='Number of companies to analyze')
    parser.add_argument('--year', type=int, default=2024, help='Year')
    parser.add_argument('--quarter', type=int, default=2, help='Quarter')

    args = parser.parse_args()

    print(f"\n{'='*80}")
    print(f"UNMAPPED ITEMS ANALYSIS")
    print(f"{'='*80}")
    print(f"Target: {args.num} companies from {args.year}Q{args.quarter}")
    print(f"{'='*80}\n")

    # Get companies
    print("Loading companies from database...")
    companies = get_companies_from_db(args.num, args.year, args.quarter)
    print(f"Found {len(companies)} companies\n")

    # Analyze each company
    all_unmapped = []
    company_metadata = []
    errors = []

    for idx, company in enumerate(companies, 1):
        cik = company['cik']
        company_name = company['company_name']
        ticker = company['ticker']
        adsh = company['adsh']
        form_type = company['form_type']

        ticker_display = ticker if ticker else "N/A"
        print(f"[{idx}/{len(companies)}] Processing {company_name} ({ticker_display}, CIK: {cik})...", end=' ')

        unmapped_items, error = analyze_company(cik, adsh, args.year, args.quarter, company_name, ticker)

        if error:
            print(f"❌ Error: {error}")
            errors.append({
                'cik': cik,
                'company_name': company_name,
                'ticker': ticker,
                'adsh': adsh,
                'error': error
            })
        else:
            print(f"✅ Found {len(unmapped_items)} unmapped items")
            all_unmapped.extend(unmapped_items)
            company_metadata.append({
                'cik': cik,
                'company_name': company_name,
                'ticker': ticker,
                'adsh': adsh,
                'unmapped_count': len(unmapped_items)
            })

    print(f"\n{'='*80}")
    print(f"Analysis complete!")
    print(f"  Total unmapped items: {len(all_unmapped)}")
    print(f"  Successful companies: {len(company_metadata)}")
    print(f"  Errors: {len(errors)}")
    print(f"{'='*80}\n")

    if len(all_unmapped) == 0:
        print("No unmapped items found!")
        return 0

    # Generate statistics
    print("Generating statistics...")

    # Frequency by (plabel, tag) pair
    pair_frequency = defaultdict(lambda: {
        'count': 0,
        'stmt_types': set(),
        'companies': set(),
        'datatypes': set(),
        'sample_values': []
    })

    for item in all_unmapped:
        key = (item['plabel'], item['tag'])
        pair_frequency[key]['count'] += 1
        pair_frequency[key]['stmt_types'].add(item['stmt_type'])
        pair_frequency[key]['companies'].add(item['cik'])
        pair_frequency[key]['datatypes'].add(item['datatype'])
        if item['value'] and len(pair_frequency[key]['sample_values']) < 3:
            pair_frequency[key]['sample_values'].append(item['value'])

    # Convert to DataFrame
    frequency_data = []
    for (plabel, tag), stats in pair_frequency.items():
        frequency_data.append({
            'plabel': plabel,
            'tag': tag,
            'frequency': stats['count'],
            'num_companies': len(stats['companies']),
            'stmt_types': ', '.join(sorted(stats['stmt_types'])),
            'datatypes': ', '.join(sorted(stats['datatypes'])),
            'sample_value': stats['sample_values'][0] if stats['sample_values'] else None
        })

    frequency_df = pd.DataFrame(frequency_data).sort_values('frequency', ascending=False)

    # Detailed unmapped items
    detailed_df = pd.DataFrame(all_unmapped)

    # Add company names
    company_map = {c['cik']: c['company_name'] for c in company_metadata}
    detailed_df['company_name'] = detailed_df['cik'].map(company_map)

    # Company summary
    company_summary_df = pd.DataFrame(company_metadata).sort_values('unmapped_count', ascending=False)

    # Statement type breakdown
    stmt_breakdown = detailed_df.groupby('stmt_type').size().reset_index(name='unmapped_count')

    # Export to Excel
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = Path(f'../output/unmapped_analysis_{args.num}companies_{timestamp}.xlsx')
    output_path.parent.mkdir(exist_ok=True)

    print(f"Exporting to {output_path}...")

    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        # Summary sheet
        summary_data = {
            'Metric': [
                'Total Companies Analyzed',
                'Companies with Errors',
                'Total Unmapped Items',
                'Unique (plabel, tag) Pairs',
                'Average Unmapped per Company'
            ],
            'Value': [
                len(company_metadata),
                len(errors),
                len(all_unmapped),
                len(frequency_df),
                len(all_unmapped) / len(company_metadata) if company_metadata else 0
            ]
        }
        pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)

        # Frequency table (most important)
        frequency_df.to_excel(writer, sheet_name='Frequency_by_Plabel_Tag', index=False)

        # Statement type breakdown
        stmt_breakdown.to_excel(writer, sheet_name='By_Statement_Type', index=False)

        # Company summary
        company_summary_df.to_excel(writer, sheet_name='By_Company', index=False)

        # Detailed items (may be large)
        if len(detailed_df) < 50000:  # Excel row limit consideration
            detailed_df.to_excel(writer, sheet_name='Detailed_Items', index=False)
        else:
            detailed_df.head(50000).to_excel(writer, sheet_name='Detailed_Items_Sample', index=False)

        # Errors (if any)
        if errors:
            pd.DataFrame(errors).to_excel(writer, sheet_name='Errors', index=False)

    print(f"\n✅ Results exported to: {output_path}")
    print(f"\n{'='*80}")
    print("TOP 20 MOST FREQUENTLY UNMAPPED ITEMS:")
    print(f"{'='*80}")
    print(frequency_df.head(20).to_string(index=False))
    print(f"{'='*80}\n")

    return 0


if __name__ == '__main__':
    exit(main())
