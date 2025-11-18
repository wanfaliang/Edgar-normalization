"""
Find prior period dates for beginning cash balance
"""
import pandas as pd

adsh = '0001018724-24-000130'
num_df = pd.read_csv('data/sec_data/extracted/2024q3/num.txt', sep='\t', dtype=str)
sub_df = pd.read_csv('data/sec_data/extracted/2024q3/sub.txt', sep='\t', dtype=str)

# Get filing metadata
sub = sub_df[sub_df['adsh'] == adsh].iloc[0]
current_period = sub['period']  # 20240630

print(f"Current period: {current_period}")
print(f"Fiscal period: {sub['fp']}")
print(f"Fiscal year: {sub['fy']}")

# Filter to Amazon
num = num_df[num_df['adsh'] == adsh].copy()

# Look at cash balance tag
cash_tag = 'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents'
cash_values = num[num['tag'] == cash_tag]

print(f"\nCash balance values (qtrs=0, instant):")
instant_cash = cash_values[cash_values['qtrs'] == '0'].copy()
instant_cash = instant_cash[instant_cash['segments'].isna() & instant_cash['coreg'].isna()]

for _, row in instant_cash.sort_values('ddate').iterrows():
    print(f"  ddate={row['ddate']}: ${float(row['value']):,.0f}")

print("\nFor Q2 2024 CF statement:")
print(f"  Current period end: {current_period} (Jun 30, 2024)")
print(f"  Prior period end should be: 20231231 (Dec 31, 2023)")
print(f"  Beginning cash: Look for ddate=20231231, qtrs=0")
print(f"  Ending cash: Look for ddate={current_period}, qtrs=0")
