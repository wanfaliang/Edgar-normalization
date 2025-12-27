"""Check IS structure for multiple companies - output to file

Usage:
    python scripts/check_is_roots.py                     # All 75 companies
    python scripts/check_is_roots.py --group general     # 50 general companies
    python scripts/check_is_roots.py --group financial   # 25 financial companies
    python scripts/check_is_roots.py --ticker AAPL MSFT  # Specific tickers
    python scripts/check_is_roots.py --year 2024 --quarter 3  # Different period
"""
import sys
import argparse
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import psycopg2
from config import config
from statement_reconstructor import StatementReconstructor

# 50 General Companies
GENERAL_COMPANIES = [
    789019, 320193, 1652044, 1018724, 1326801, 1045810, 50863, 1341439, 1108524, 796343,
    104169, 27419, 909832, 354950, 60667, 109198, 29534, 764478,
    66740, 18230, 12927, 936468, 315189, 40545, 773840,
    19617, 70858, 72971, 886982, 895421, 4962, 1403161, 1141391,
    200406, 78003, 731766, 1800, 310158, 64803,
    34088, 93410, 1163165, 87347,
    21344, 77476, 80424, 320187, 63908, 829224, 21665
]

# 25 Financial Companies
FINANCIAL_COMPANIES = [
    1000209, 1000275, 1001171, 1001290, 1004434, 1004702, 1004724, 1005101,
    1005817, 1006830, 1010470, 101199, 1013272, 101382, 1015328, 1018979,
    1020569, 1021917, 102212, 1022837, 1025378, 1025835, 1025996, 1026214, 1029199
]

# Parse arguments
parser = argparse.ArgumentParser(description='Check IS structure for companies')
parser.add_argument('--ticker', nargs='+', help='Specific tickers (e.g., AAPL MSFT)')
parser.add_argument('--group', choices=['general', 'financial', 'all'], default='all',
                    help='Predefined company group')
parser.add_argument('--year', type=int, default=2024, help='Fiscal year (default: 2024)')
parser.add_argument('--quarter', type=int, default=2, help='Quarter 1-4 (default: 2)')
args = parser.parse_args()

# Get adsh for each company
conn = psycopg2.connect(config.get_db_connection())
cursor = conn.cursor()

companies = []

if args.ticker:
    # Lookup by ticker
    for ticker in args.ticker:
        cursor.execute('''
            SELECT c.cik, f.adsh, f.company_name
            FROM companies c
            JOIN filings f ON c.cik = f.cik
            WHERE c.ticker = %s
              AND EXISTS (
                  SELECT 1 FROM edgar_pre ep
                  WHERE ep.adsh = f.adsh
                    AND ep.source_year = %s
                    AND ep.source_quarter = %s
                    AND ep.stmt = 'IS'
              )
            LIMIT 1
        ''', (ticker.upper(), args.year, args.quarter))
        row = cursor.fetchone()
        if row:
            companies.append((row[1], row[0], row[2]))
        else:
            print(f'Warning: No IS data for {ticker}')
else:
    # Use predefined groups
    if args.group == 'general':
        cik_list = GENERAL_COMPANIES
    elif args.group == 'financial':
        cik_list = FINANCIAL_COMPANIES
    else:
        cik_list = GENERAL_COMPANIES + FINANCIAL_COMPANIES

    for cik in cik_list:
        cursor.execute('''
            SELECT f.adsh, f.company_name
            FROM filings f
            WHERE f.cik = %s
              AND EXISTS (
                  SELECT 1 FROM edgar_pre ep
                  WHERE ep.adsh = f.adsh
                    AND ep.source_year = %s
                    AND ep.source_quarter = %s
                    AND ep.stmt = 'IS'
              )
            LIMIT 1
        ''', (str(cik), args.year, args.quarter))
        row = cursor.fetchone()
        if row:
            companies.append((row[0], cik, row[1]))

conn.close()
print(f'Found {len(companies)} companies with IS data')

reconstructor = StatementReconstructor(year=args.year, quarter=args.quarter, verbose=False)

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
output_file = config.storage.reports_dir / f'is_structure_analysis_{timestamp}.txt'
with open(output_file, 'w', encoding='utf-8') as f:
    f.write("INCOME STATEMENT STRUCTURE ANALYSIS\n")
    f.write("="*80 + "\n\n")

    for adsh, cik, name in companies:
        f.write(f'\n{"="*80}\n')
        f.write(f'{name}\n')
        f.write(f'CIK: {cik}, ADSH: {adsh}\n')
        f.write("="*80 + "\n")

        try:
            result = reconstructor.reconstruct_statement_multi_period(cik=cik, adsh=adsh, stmt_type='IS')
        except Exception as e:
            f.write(f'  Error: {e}\n')
            continue

        if not result or not result.get('line_items'):
            f.write('  No IS data\n')
            continue

        f.write(f'\nALL LINE ITEMS ({len(result["line_items"])} items):\n')
        f.write("-"*100 + "\n")
        f.write(f'{"Ln":>3} {"Label":<50} {"CRDR":>4} {"is_sum":>6} {"parent":>6} {"#child":>6}\n')
        f.write("-"*100 + "\n")

        root_items = []
        for item in result['line_items']:
            ln = item.get('stmt_order', 0)
            is_sum = item.get('is_sum', False)
            parent = item.get('parent_line')
            children = len(item.get('calc_children', []))
            plabel = (item.get('plabel', '') or '')[:50]
            crdr = item.get('crdr') or '-'

            parent_str = str(parent) if parent else 'ROOT'
            f.write(f'{ln:3} {plabel:<50} {crdr:>4} {str(is_sum):>6} {parent_str:>6} {children:>6}\n')

            if parent is None:
                root_items.append((ln, plabel, is_sum))

        f.write("\nROOT ITEMS (no parent):\n")
        for ln, plabel, is_sum in root_items:
            f.write(f'  {ln:3}: {plabel} (is_sum={is_sum})\n')

print(f'Output written to: {output_file}')
