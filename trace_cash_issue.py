"""
Trace Cash Balance Issue - Simple Diagnostic
=============================================
"""

import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from config import config

# Apple 10-K details
adsh = '0000320193-24-000123'
year, quarter = 2024, 4

print("\n" + "="*70)
print("TRACING CASH BALANCE ISSUE")
print("="*70)

# Load data files
base_dir = config.storage.extracted_dir / f'{year}q{quarter}'
num_path = base_dir / 'num.txt'
tag_path = base_dir / 'tag.txt'

print(f"\nLoading data from {base_dir}...")
num_df = pd.read_csv(num_path, sep='\t', dtype=str, na_values=[''])
tag_df = pd.read_csv(tag_path, sep='\t', dtype=str, na_values=[''])

# Filter to Apple
apple_num = num_df[num_df['adsh'] == adsh].copy()

print(f"\n✅ Found {len(apple_num)} NUM rows for Apple")

# Find the cash tag
cash_tag = 'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents'

# Check if this tag exists
cash_rows = apple_num[apple_num['tag'] == cash_tag]

print(f"\n{'='*70}")
print(f"CASH TAG: {cash_tag}")
print(f"{'='*70}")
print(f"\nFound {len(cash_rows)} rows with this tag")

if len(cash_rows) > 0:
    print("\nAll cash balance rows (sorted by ddate, qtrs):")
    cash_sorted = cash_rows.sort_values(['ddate', 'qtrs'])

    for _, row in cash_sorted.iterrows():
        ddate = row['ddate']
        qtrs = row['qtrs']
        value = row['value']
        uom = row['uom']
        segments = row.get('segments', 'NaN')
        coreg = row.get('coreg', 'NaN')

        print(f"  ddate={ddate}, qtrs={qtrs}, value={value:>15s}, uom={uom}, segments={segments}, coreg={coreg}")

# Now let's check what the algorithm would do
print(f"\n{'='*70}")
print(f"ALGORITHM SIMULATION")
print(f"{'='*70}")

# For the period ending 20240930, qtrs=4
ending_ddate = '20240930'
target_qtrs = '4'

print(f"\nPeriod: Year Ended Sep 30, 2024")
print(f"  Target ending date: {ending_ddate}")
print(f"  Target qtrs: {target_qtrs}")

# Calculate beginning date
from datetime import datetime, timedelta

end_date = datetime.strptime(ending_ddate, '%Y%m%d')
months = int(target_qtrs) * 3
days = months * 30.5
approx_beginning = end_date - timedelta(days=days)
approx_str = approx_beginning.strftime('%Y%m%d')

# Find all instant dates
all_instant = apple_num[apple_num['qtrs'] == '0']
instant_dates_all = sorted(all_instant['ddate'].unique())

print(f"\n  Calculated beginning date (approx): {approx_str} ({int(days)} days back)")

# Find closest instant date
past_dates = [d for d in instant_dates_all if d < ending_ddate]
if past_dates:
    closest = min(past_dates, key=lambda x: abs(int(x) - int(approx_str)))
    print(f"  Closest instant date: {closest}")
else:
    print(f"  ⚠️  No past instant dates found!")
    closest = ending_ddate

# Now check what values we get for ENDING cash
print(f"\n1. Looking for ENDING cash balance:")
print(f"   Tag: {cash_tag}")
print(f"   ddate: {ending_ddate}")
print(f"   qtrs: 0 (instant)")

ending_cash = cash_rows[(cash_rows['ddate'] == ending_ddate) & (cash_rows['qtrs'] == '0')]
print(f"   Found {len(ending_cash)} matches:")

# Filter to consolidated (no segments, no coreg)
for _, row in ending_cash.iterrows():
    segments = row.get('segments', pd.NA)
    coreg = row.get('coreg', pd.NA)
    is_consolidated = pd.isna(segments) and pd.isna(coreg)
    marker = "✓ CONSOLIDATED" if is_consolidated else "  (has segments/coreg)"
    print(f"   - value={row['value']:>15s}, segments={segments}, coreg={coreg} {marker}")

# Now check what values we get for BEGINNING cash
print(f"\n2. Looking for BEGINNING cash balance:")
print(f"   Tag: {cash_tag}")
print(f"   ddate: {closest}")
print(f"   qtrs: 0 (instant)")

beginning_cash = cash_rows[(cash_rows['ddate'] == closest) & (cash_rows['qtrs'] == '0')]
print(f"   Found {len(beginning_cash)} matches:")

# Filter to consolidated (no segments, no coreg)
for _, row in beginning_cash.iterrows():
    segments = row.get('segments', pd.NA)
    coreg = row.get('coreg', pd.NA)
    is_consolidated = pd.isna(segments) and pd.isna(coreg)
    marker = "✓ CONSOLIDATED" if is_consolidated else "  (has segments/coreg)"
    print(f"   - value={row['value']:>15s}, segments={segments}, coreg={coreg} {marker}")

print(f"\n{'='*70}")
print("CONCLUSION")
print(f"{'='*70}")

# Get consolidated values
ending_consolidated = ending_cash[ending_cash['segments'].isna() & ending_cash['coreg'].isna()]
beginning_consolidated = beginning_cash[beginning_cash['segments'].isna() & beginning_cash['coreg'].isna()]

if len(ending_consolidated) > 0:
    ending_val = ending_consolidated.iloc[0]['value']
    print(f"\n✅ Ending cash (consolidated): {ending_val}")
else:
    print(f"\n⚠️  No consolidated ending cash found")

if len(beginning_consolidated) > 0:
    beginning_val = beginning_consolidated.iloc[0]['value']
    print(f"✅ Beginning cash (consolidated): {beginning_val}")
else:
    print(f"⚠️  No consolidated beginning cash found")

if len(ending_consolidated) > 0 and len(beginning_consolidated) > 0:
    if ending_val == beginning_val:
        print(f"\n⚠️  ⚠️  ⚠️  ISSUE CONFIRMED: Beginning == Ending! ⚠️  ⚠️  ⚠️")
    else:
        print(f"\n✅ Values are different - this is correct!")
