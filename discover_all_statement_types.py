"""
Discover all statement types available in PRE.txt for a filing
"""
import pandas as pd
from pathlib import Path

# Amazon filing from test script
cik = 1018724
adsh = '0001018724-24-000130'
year = 2024
quarter = 3

base_dir = Path(f'data/sec_data/extracted/{year}q{quarter}')
pre_file = base_dir / 'pre.txt'

print("="*80)
print(f"DISCOVERING ALL STATEMENT TYPES")
print("="*80)
print(f"Company CIK: {cik}")
print(f"ADSH: {adsh}")
print(f"Data: {year}q{quarter}")
print()

# Load PRE file
print("Loading PRE.txt...")
pre_df = pd.read_csv(pre_file, sep='\t', dtype=str, low_memory=False)
print(f"Total rows in PRE.txt: {len(pre_df):,}")

# Filter to this filing
filing_pre = pre_df[pre_df['adsh'] == adsh].copy()
print(f"Rows for this filing: {len(filing_pre):,}")
print()

# Find all unique statement types
print("="*80)
print("ALL STATEMENT TYPES IN THIS FILING:")
print("="*80)

stmt_counts = filing_pre.groupby('stmt').size().reset_index(name='count')
stmt_counts = stmt_counts.sort_values('stmt')

for _, row in stmt_counts.iterrows():
    stmt = row['stmt']
    count = row['count']
    print(f"  {stmt}: {count} rows")

print()
print("="*80)
print("CHECKING FOR PARENTHETICAL STATEMENTS:")
print("="*80)

# Look for parenthetical statements
parenthetical_stmts = stmt_counts[stmt_counts['stmt'].str.contains('Parenthetical', case=False, na=False)]

if len(parenthetical_stmts) > 0:
    print("\n✅ Found parenthetical statements:")
    for _, row in parenthetical_stmts.iterrows():
        stmt = row['stmt']
        count = row['count']
        print(f"\n  Statement: {stmt}")
        print(f"  Rows: {count}")

        # Show sample tags
        stmt_rows = filing_pre[filing_pre['stmt'] == stmt].head(10)
        print(f"  Sample tags:")
        for _, tag_row in stmt_rows.iterrows():
            print(f"    Line {tag_row['line']}: {tag_row['tag']} - '{tag_row['plabel']}'")
else:
    print("\n❌ No parenthetical statements found")

print()
print("="*80)
print("TRYING TO RECONSTRUCT EACH STATEMENT TYPE:")
print("="*80)

from src.statement_reconstructor import StatementReconstructor

reconstructor = StatementReconstructor(year, quarter)

for _, row in stmt_counts.iterrows():
    stmt = row['stmt']
    print(f"\nTrying to reconstruct: {stmt}")

    try:
        result = reconstructor.reconstruct_statement_multi_period(
            cik=cik,
            adsh=adsh,
            stmt_type=stmt
        )

        if 'error' in result:
            print(f"  ❌ Error: {result['error']}")
        else:
            periods = len(result.get('periods', []))
            items = len(result.get('line_items', []))
            print(f"  ✅ Success: {periods} periods, {items} line items")
    except Exception as e:
        print(f"  ❌ Exception: {str(e)}")
