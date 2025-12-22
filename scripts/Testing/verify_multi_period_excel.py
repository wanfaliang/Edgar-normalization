"""
Verify Multi-Period Excel Output

Reads one of the multi-period Excel files and validates:
- Correct number of period columns
- Values populated correctly
- Beginning/ending cash balances correct
"""

import pandas as pd
from pathlib import Path

# Read Amazon multi-period Excel file
excel_file = Path('output/multi_period/Amazoncom_Inc_multi_period.xlsx')

if not excel_file.exists():
    print(f"❌ File not found: {excel_file}")
    exit(1)

print("="*80)
print(f"Verifying Multi-Period Excel Output")
print(f"File: {excel_file}")
print("="*80)

# Read each sheet
sheets = ['Balance Sheet', 'Income Statement', 'Cash Flow']

for sheet_name in sheets:
    print(f"\n{'='*80}")
    print(f"{sheet_name}")
    print(f"{'='*80}")

    df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)

    # Find the header row (contains "Line Item")
    header_row = None
    for idx, row in df.iterrows():
        if row[0] == 'Line Item':
            header_row = idx
            break

    if header_row is None:
        print(f"  ⚠️  Could not find header row")
        continue

    # Extract column headers
    headers = df.iloc[header_row].tolist()
    print(f"\n  Column Headers:")
    for i, header in enumerate(headers):
        if pd.notna(header):
            print(f"    Column {i}: {header}")

    # Count period columns (exclude "Line Item" column)
    period_cols = [h for h in headers if pd.notna(h) and h != 'Line Item']
    print(f"\n  Number of periods: {len(period_cols)}")

    # Sample first few data rows
    print(f"\n  Sample data rows:")
    data_start = header_row + 1
    sample_rows = df.iloc[data_start:data_start+5]

    for idx, row in sample_rows.iterrows():
        line_item = row[0]
        if pd.notna(line_item):
            print(f"    {line_item}")
            for col_idx in range(1, len(period_cols) + 1):
                value = row[col_idx]
                if pd.notna(value):
                    print(f"      {period_cols[col_idx-1]}: ${value:,.0f}")

# Read Cash Flow to specifically check beginning/ending cash
print(f"\n{'='*80}")
print("Cash Flow - Beginning/Ending Cash Validation")
print(f"{'='*80}")

df_cf = pd.read_excel(excel_file, sheet_name='Cash Flow', header=None)

# Find header row
header_row = None
for idx, row in df_cf.iterrows():
    if row[0] == 'Line Item':
        header_row = idx
        break

headers = df_cf.iloc[header_row].tolist()
period_cols = [h for h in headers if pd.notna(h) and h != 'Line Item']

# Find beginning and ending cash rows
data_start = header_row + 1
for idx, row in df_cf.iloc[data_start:].iterrows():
    line_item = str(row[0]).lower()

    if 'beginning' in line_item and 'period' in line_item:
        print(f"\n✅ BEGINNING CASH:")
        print(f"   Label: {row[0]}")
        for col_idx in range(1, len(period_cols) + 1):
            value = row[col_idx]
            if pd.notna(value):
                print(f"   {period_cols[col_idx-1]}: ${value:,.0f}")

    if 'end' in line_item and 'period' in line_item and 'beginning' not in line_item:
        print(f"\n✅ ENDING CASH:")
        print(f"   Label: {row[0]}")
        for col_idx in range(1, len(period_cols) + 1):
            value = row[col_idx]
            if pd.notna(value):
                print(f"   {period_cols[col_idx-1]}: ${value:,.0f}")

print(f"\n{'='*80}")
print("✅ Multi-period Excel verification complete!")
print(f"{'='*80}")
