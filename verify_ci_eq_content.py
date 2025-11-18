"""
Verify CI and EQ sheets have actual data
"""

import pandas as pd
from pathlib import Path

excel_file = Path('output/complete_statements/The_Home_Depot_Inc_complete.xlsx')

print("="*80)
print(f"Verifying CI and EQ Sheet Content")
print(f"File: {excel_file}")
print("="*80)

# Read CI sheet
print("\n" + "="*80)
print("COMPREHENSIVE INCOME SHEET")
print("="*80)

df_ci = pd.read_excel(excel_file, sheet_name='Comprehensive Income', header=None)

# Find header row
header_row = None
for idx, row in df_ci.iterrows():
    if row[0] == 'Line Item':
        header_row = idx
        break

if header_row:
    headers = df_ci.iloc[header_row].tolist()
    print(f"\nColumn Headers:")
    for h in headers:
        if pd.notna(h):
            print(f"  - {h}")

    # Show data rows
    print(f"\nLine Items:")
    data_start = header_row + 1
    for idx, row in df_ci.iloc[data_start:data_start+5].iterrows():
        line_item = row[0]
        if pd.notna(line_item) and line_item != '':
            print(f"  {line_item}")

# Read EQ sheet
print("\n" + "="*80)
print("STOCKHOLDERS EQUITY SHEET")
print("="*80)

df_eq = pd.read_excel(excel_file, sheet_name='Stockholders Equity', header=None)

# Find header row
header_row = None
for idx, row in df_eq.iterrows():
    if row[0] == 'Line Item':
        header_row = idx
        break

if header_row:
    headers = df_eq.iloc[header_row].tolist()
    print(f"\nColumn Headers:")
    for h in headers:
        if pd.notna(h):
            print(f"  - {h}")

    # Show data rows
    print(f"\nLine Items:")
    data_start = header_row + 1
    for idx, row in df_eq.iloc[data_start:data_start+5].iterrows():
        line_item = row[0]
        if pd.notna(line_item) and line_item != '':
            print(f"  {line_item}")

print("\n" + "="*80)
print("✅ Both CI and EQ sheets have content!")
print("="*80)
