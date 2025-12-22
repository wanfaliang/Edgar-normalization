"""Investigate fund balance sheet structures"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from statement_reconstructor import StatementReconstructor

# Specific fund filings to investigate (available in database)
funds = [
    # (cik, adsh, company_name, year, quarter)
    (1771514, '0000950170-24-043546', 'EXCHANGERIGHT INCOME FUND', 2024, 2),
    (1902649, '0000950170-24-052326', 'BLACKROCK PRIVATE CREDIT FUND', 2024, 2),
    (1729997, '0000950170-24-053009', 'GRAYSCALE DIGITAL LARGE CAP FUND LLC', 2024, 2),
]

print(f"Investigating {len(funds)} fund filings")
print("=" * 80)

for cik, adsh, company_name, year, quarter in funds:
    reconstructor = StatementReconstructor(year=year, quarter=quarter, verbose=False)
    print(f"\n{'='*80}")
    print(f"FUND: {company_name}")
    print(f"CIK: {cik}, ADSH: {adsh}, Year: {year}, Quarter: {quarter}")
    print("=" * 80)

    try:
        result = reconstructor.reconstruct_statement_multi_period(cik=cik, adsh=adsh, stmt_type='BS')
        if not result or not result.get('line_items'):
            print("  No BS data")
            continue

        line_items = result['line_items']

        # Find key items
        print("\nKEY ITEMS:")
        print("-" * 60)

        key_patterns = ['asset', 'liabilit', 'net asset', 'equity', 'total']

        for item in line_items:
            tag = item.get('tag', '').lower()
            plabel = (item.get('plabel', '') or '').lower()
            line = item.get('line', 0)
            is_sum = item.get('is_sum', False)
            parent_line = item.get('parent_line')
            calc_children = item.get('calc_children', [])

            # Get first period value
            values = item.get('values', {})
            value = list(values.values())[0] if values else None

            # Check if matches key patterns
            if any(p in plabel or p in tag for p in key_patterns):
                print(f"\nLine {line:3d}: {item.get('plabel', '')[:50]}")
                print(f"         tag: {item.get('tag', '')}")
                print(f"         is_sum: {is_sum}, parent_line: {parent_line}")
                print(f"         value: {value:,.0f}" if value else "         value: None")
                if calc_children:
                    print(f"         calc_children ({len(calc_children)}):")
                    for child in calc_children[:5]:
                        child_tag = child[0] if isinstance(child, (list, tuple)) else child
                        child_plabel = child[2] if isinstance(child, (list, tuple)) and len(child) > 2 else ''
                        print(f"           - {child_tag} ({child_plabel})")
                    if len(calc_children) > 5:
                        print(f"           ... and {len(calc_children) - 5} more")

        # Check for accounting identity
        print("\n" + "-" * 60)
        print("ACCOUNTING IDENTITY CHECK:")

        total_assets = None
        total_liabilities = None
        net_assets = None

        for item in line_items:
            tag = item.get('tag', '').lower()
            plabel = (item.get('plabel', '') or '').lower()
            values = item.get('values', {})
            value = list(values.values())[0] if values else None

            if tag == 'assets' or plabel == 'total assets':
                total_assets = value
            if tag == 'liabilities' or plabel == 'total liabilities':
                total_liabilities = value
            if 'net assets' in plabel or tag == 'netassets':
                net_assets = value

        print(f"  total_assets: {total_assets:,.0f}" if total_assets else "  total_assets: None")
        print(f"  total_liabilities: {total_liabilities:,.0f}" if total_liabilities else "  total_liabilities: None")
        print(f"  net_assets: {net_assets:,.0f}" if net_assets else "  net_assets: None")

        if total_assets and total_liabilities is not None and net_assets:
            calculated = total_assets - total_liabilities
            diff = abs(calculated - net_assets)
            print(f"  total_assets - total_liabilities = {calculated:,.0f}")
            print(f"  Matches net_assets? {diff < 1}")

    except Exception as e:
        print(f"  Error: {e}")

print("\n" + "=" * 80)
print("INVESTIGATION COMPLETE")
