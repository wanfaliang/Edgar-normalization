"""
Investigate why cash beginning/ending balances are missing from CF
"""
import pandas as pd

# Load Amazon data
adsh = '0001018724-24-000130'
pre_df = pd.read_csv('data/sec_data/extracted/2024q3/pre.txt', sep='\t', dtype=str)
num_df = pd.read_csv('data/sec_data/extracted/2024q3/num.txt', sep='\t', dtype=str)
tag_df = pd.read_csv('data/sec_data/extracted/2024q3/tag.txt', sep='\t', dtype=str)

# Filter to Amazon
pre = pre_df[pre_df['adsh'] == adsh].copy()
num = num_df[num_df['adsh'] == adsh].copy()

print("=" * 80)
print("INVESTIGATING MISSING CASH BALANCES IN CASH FLOW STATEMENT")
print("=" * 80)

# Check CF statement in PRE table
cf = pre[pre['stmt'] == 'CF'].copy()
print(f"\nCash Flow statement has {len(cf)} rows in PRE table")

# Look for cash-related tags
print("\nSearching for 'Cash' in tag names...")
cash_tags = cf[cf['tag'].str.contains('Cash', case=False, na=False)].copy()
print(f"Found {len(cash_tags)} lines with 'Cash' in tag name:\n")
for _, row in cash_tags.iterrows():
    print(f"  Line {row['line']}: {row['tag']}")
    print(f"    Label: {row.get('plabel', 'N/A')}")
    print(f"    Report: {row.get('report', 'N/A')}")
    print()

# Check NUM table for these tags
print("\n" + "=" * 80)
print("CHECKING NUM TABLE")
print("=" * 80)

target_ddate = '20240630'
target_qtrs = '2'  # YTD for Q2

for tag in cash_tags['tag'].unique():
    print(f"\nTag: {tag}")
    tag_num = num[num['tag'] == tag]

    if len(tag_num) == 0:
        print("  ❌ NOT FOUND in NUM table")
        continue

    print(f"  Found {len(tag_num)} rows in NUM table:")
    for _, row in tag_num.iterrows():
        print(f"    ddate={row['ddate']}, qtrs={row['qtrs']}, segments={row.get('segments', 'NaN')}, coreg={row.get('coreg', 'NaN')}, value={row['value']}")

# Check what reports exist for CF
print("\n" + "=" * 80)
print("CASH FLOW REPORTS")
print("=" * 80)

if 'report' in cf.columns:
    reports = cf['report'].unique()
    print(f"Found {len(reports)} reports for CF: {reports}")

    for report in reports:
        cf_report = cf[cf['report'] == report]
        print(f"\nReport {report}: {len(cf_report)} lines")
        cash_in_report = cf_report[cf_report['tag'].str.contains('Cash', case=False, na=False)]
        if len(cash_in_report) > 0:
            print("  Cash-related items:")
            for _, row in cash_in_report.iterrows():
                print(f"    Line {row['line']}: {row.get('plabel', row['tag'])}")
