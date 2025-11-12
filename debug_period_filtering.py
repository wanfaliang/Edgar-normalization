"""
Debug: Check what periods/dates are available in NUM table for Amazon Cash Flow
"""
import pandas as pd

adsh = '0001018724-24-000130'

# Load NUM table
num_df = pd.read_csv('data/sec_data/extracted/2024q3/num.txt', sep='\t', dtype=str)
filing_num = num_df[num_df['adsh'] == adsh].copy()

# Look at Beginning Cash
print("=" * 80)
print("CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents - All entries:")
print("=" * 80)
cash_tags = filing_num[filing_num['tag'].str.contains('CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents', na=False)]
print(cash_tags[['tag', 'ddate', 'qtrs', 'uom', 'value']].to_string(index=False))

# Look at Change in Cash
print("\n" + "=" * 80)
print("CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecrease:")
print("=" * 80)
change_tags = filing_num[filing_num['tag'].str.contains('PeriodIncreaseDecrease', na=False)]
print(change_tags[['tag', 'ddate', 'qtrs', 'uom', 'value']].to_string(index=False))

# Look at Operating CF
print("\n" + "=" * 80)
print("NetCashProvidedByUsedInOperatingActivities:")
print("=" * 80)
opcf_tags = filing_num[filing_num['tag'] == 'NetCashProvidedByUsedInOperatingActivities']
print(opcf_tags[['tag', 'ddate', 'qtrs', 'uom', 'value']].to_string(index=False))

# Check submission metadata for period
sub_df = pd.read_csv('data/sec_data/extracted/2024q3/sub.txt', sep='\t', dtype=str)
sub = sub_df[sub_df['adsh'] == adsh].iloc[0]
print("\n" + "=" * 80)
print("Filing Period Information:")
print("=" * 80)
print(f"Period: {sub['period']}")
print(f"FY: {sub['fy']}")
print(f"FP: {sub['fp']}")
print(f"Filed: {sub['filed']}")
