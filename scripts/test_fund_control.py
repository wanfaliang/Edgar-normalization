"""Test fund balance sheet control item detection"""
import sys
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from statement_reconstructor import StatementReconstructor
from map_financial_statements import find_bs_control_items

def main():
    parser = argparse.ArgumentParser(description='Test fund BS control items')
    parser.add_argument('--adsh', type=str, required=True, help='Filing ADSH')
    parser.add_argument('--cik', type=int, default=None, help='Company CIK (optional)')
    parser.add_argument('--year', type=int, default=2024, help='Fiscal year (default: 2024)')
    parser.add_argument('--quarter', type=int, default=2, help='Quarter 1-4 (default: 2)')
    args = parser.parse_args()

    print(f'ADSH={args.adsh}, CIK={args.cik}, Year={args.year}, Q={args.quarter}')

    reconstructor = StatementReconstructor(year=args.year, quarter=args.quarter, verbose=False)
    result = reconstructor.reconstruct_statement_multi_period(cik=args.cik, adsh=args.adsh, stmt_type='BS')

    if not result or not result.get('line_items'):
        print('No BS data found')
        return

    line_items = result['line_items']
    print(f'\nLine items ({len(line_items)}):')
    for item in line_items:
        ln = item.get('stmt_order', 0)
        print(f'  {ln}: {item.get("plabel", "")[:55]}')

    print()
    control_lines = find_bs_control_items(line_items)
    print('Control lines:')
    for k, v in sorted(control_lines.items()):
        print(f'  {k}: {v}')

if __name__ == '__main__':
    main()
