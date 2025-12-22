"""
Extract Amazon Balance Sheet Assets for Mapping Experiment
===========================================================
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from statement_reconstructor import StatementReconstructor

# Amazon 2024Q2
adsh = '0001018724-24-000083'
cik = '1018724'
year, quarter = 2024, 2

print("\n" + "="*70)
print("AMAZON BALANCE SHEET ASSETS - 2024Q2")
print("="*70)

# Reconstruct balance sheet
reconstructor = StatementReconstructor(year=year, quarter=quarter)

result = reconstructor.reconstruct_statement_multi_period(
    cik=cik,
    adsh=adsh,
    stmt_type='BS'
)

if not result or not result.get('line_items'):
    print("❌ Failed to reconstruct balance sheet")
    sys.exit(1)

line_items = result['line_items']
periods = result.get('periods', [])

print(f"\n✅ Reconstructed Balance Sheet")
print(f"   Line items: {len(line_items)}")
print(f"   Periods: {len(periods)}")

# Extract only ASSET items
print(f"\n" + "="*70)
print("ASSET LINE ITEMS (for mapping)")
print("="*70)

assets = []
in_assets = True  # Amazon typically starts with assets

for item in line_items:
    plabel = item['plabel']
    tag = item.get('tag', '')

    # Stop when we hit liabilities section
    if 'liabilities' in plabel.lower() and 'total' not in plabel.lower():
        in_assets = False
        break

    if in_assets:
        # Get value for first period (values is a dict keyed by (ddate, qtrs))
        values = item.get('values', {})
        if isinstance(values, dict) and len(values) > 0:
            # Get first value from dict
            value = list(values.values())[0]
        elif isinstance(values, list) and len(values) > 0:
            value = values[0]
        else:
            value = None

        assets.append({
            'plabel': plabel,
            'tag': tag,
            'value': value
        })

print(f"\nFound {len(assets)} asset line items:\n")

for i, asset in enumerate(assets, 1):
    value_str = f"${asset['value']:,.0f}" if asset['value'] else "N/A"
    print(f"{i:2d}. {asset['plabel'][:60]:<60s} | {value_str:>20s}")
    print(f"    Tag: {asset['tag']}")

# Export for mapping
print(f"\n" + "="*70)
print("ASSET ITEMS FOR MAPPING (plabel only)")
print("="*70)
print()

for asset in assets:
    print(f'"{asset["plabel"]}"')
