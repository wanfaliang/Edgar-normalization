"""
Investigate Home Depot's fiscal year structure to understand the beginning cash issue
"""
import pandas as pd

# Load data
adsh = '0000354950-24-000201'
sub_df = pd.read_csv('data/sec_data/extracted/2024q3/sub.txt', sep='\t', dtype=str)
num_df = pd.read_csv('data/sec_data/extracted/2024q3/num.txt', sep='\t', dtype=str)

# Get Home Depot filing metadata
sub = sub_df[sub_df['adsh'] == adsh].iloc[0]

print("=" * 80)
print("HOME DEPOT FISCAL YEAR INVESTIGATION")
print("=" * 80)

print("\nSUB Table Metadata:")
print(f"  Company: {sub['name']}")
print(f"  Form: {sub['form']}")
print(f"  Period: {sub['period']}")
print(f"  Fiscal Period (fp): {sub['fp']}")
print(f"  Fiscal Year (fy): {sub['fy']}")
print(f"  Filed: {sub['filed']}")

# Look at all available instant dates for Home Depot
num_hd = num_df[num_df['adsh'] == adsh].copy()
instant_dates = num_hd[(num_hd['qtrs'] == '0') &
                       (num_hd['segments'].isna()) &
                       (num_hd['coreg'].isna())]['ddate'].unique()
instant_dates_sorted = sorted(instant_dates)

print(f"\nAvailable Instant (qtrs=0) Dates in NUM table:")
for date in instant_dates_sorted:
    # Parse date to make it readable
    year = date[:4]
    month = date[4:6]
    day = date[6:8]
    print(f"  {date} = {year}-{month}-{day}")

# Find cash balance tag
print("\nLooking for cash balance values...")
cash_tags = num_hd[num_hd['tag'].str.contains('Cash', case=False, na=False)]['tag'].unique()

# Filter to likely cash balance tag (instant, no segments)
for tag in cash_tags:
    tag_values = num_hd[(num_hd['tag'] == tag) &
                        (num_hd['qtrs'] == '0') &
                        (num_hd['segments'].isna())]
    if len(tag_values) > 0:
        print(f"\n  Tag: {tag}")
        for _, row in tag_values.sort_values('ddate').iterrows():
            value = float(row['value']) if row['value'] else None
            if value:
                print(f"    {row['ddate']}: ${value:,.0f}")

# Analyze fiscal year pattern
print("\n" + "=" * 80)
print("FISCAL YEAR ANALYSIS")
print("=" * 80)

fy = int(sub['fy'])
current_period = sub['period']

print(f"\nCurrent Filing:")
print(f"  Fiscal Year: {fy} (FY{fy})")
print(f"  Period End: {current_period} (Q2 FY{fy})")
print(f"  This is the second quarter of fiscal year {fy}")

# For Q2 of a fiscal year, beginning cash should be at the START of the fiscal year
# Find fiscal year start by looking at available dates
print(f"\nFor Q2 FY{fy} Cash Flow Statement (YTD, qtrs=2):")
print(f"  Period covers: FY{fy} Start → {current_period}")
print(f"  Ending cash date: {current_period}")

# Look for dates that could be fiscal year start
# Should be around Feb 2024 for FY2024
fy_start_year = current_period[:4]  # Same calendar year for Q2
instant_dates_sorted = sorted(instant_dates)
print(f"\n  Possible beginning cash dates (instant dates before {current_period}):")
for date in instant_dates_sorted:
    if date < current_period:
        year = date[:4]
        month = date[4:6]
        day = date[6:8]
        print(f"    {date} ({year}-{month}-{day})")

# Current logic issue
print("\n" + "=" * 80)
print("CURRENT LOGIC ISSUE")
print("=" * 80)

print(f"\nCurrent code logic:")
print(f"  fy = {fy}")
print(f"  Looks for dates starting with: {fy-1}")
print(f"  Filters to: [d for d in instant_dates if d.startswith('{fy-1}')]")

prior_fy_dates = [d for d in instant_dates_sorted if d.startswith(str(fy-1))]
print(f"  Found dates: {prior_fy_dates}")
if prior_fy_dates:
    print(f"  Selected (latest): {prior_fy_dates[-1]}")

print(f"\n  PROBLEM: This selects the wrong date!")
print(f"  For FY{fy} Q2, beginning cash should be at FY{fy} start (Feb {current_period[:4]})")
print(f"  But it's selecting dates from calendar year {fy-1}")
