"""
Check Amazon's Balance Sheet hierarchy structure
See if there are section headers vs line items
"""

import pandas as pd

print("="*80)
print("AMAZON BALANCE SHEET STRUCTURE")
print("="*80)

adsh = '0001018724-24-000130'
pre_df = pd.read_csv('data/sec_data/extracted/2024q3/pre.txt', sep='\t', dtype=str)
num_df = pd.read_csv('data/sec_data/extracted/2024q3/num.txt', sep='\t', dtype=str)

filing_pre = pre_df[pre_df['adsh'] == adsh]
filing_num = num_df[num_df['adsh'] == adsh]

# Get Balance Sheet
bs = filing_pre[filing_pre['stmt'] == 'BS'].sort_values('line')

print(f"\nBalance Sheet PRE entries: {len(bs)}")
print(f"\nStructure (showing indentation levels):\n")

for idx, row in bs.iterrows():
    tag = row['tag']
    plabel = row.get('plabel', tag)
    level = int(row.get('inpth', 0))
    line = row['line']

    # Check if has value in NUM
    has_value = len(filing_num[filing_num['tag'] == tag]) > 0

    indent = "  " * level
    value_indicator = "✓" if has_value else "✗"

    print(f"{line:3} {indent}{plabel} [{tag}] {value_indicator}")

print("\n" + "="*80)
print("Legend: ✓ = has value in NUM, ✗ = no value in NUM")
print("="*80)
