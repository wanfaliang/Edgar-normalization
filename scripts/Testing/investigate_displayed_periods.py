"""
Investigate which periods are actually DISPLAYED on the primary financial statements

The NUM table contains all data, but PRE table shows what's actually presented.
"""
import pandas as pd

# Load data
adsh = '0001018724-24-000130'  # Amazon
pre_df = pd.read_csv('data/sec_data/extracted/2024q3/pre.txt', sep='\t', dtype=str)
num_df = pd.read_csv('data/sec_data/extracted/2024q3/num.txt', sep='\t', dtype=str)

# Filter to Amazon
pre = pre_df[pre_df['adsh'] == adsh]
num = num_df[num_df['adsh'] == adsh]

print("=" * 80)
print("INVESTIGATING DISPLAYED PERIODS")
print("Amazon 10-Q Q2 2024")
print("=" * 80)

# Look at Balance Sheet first
bs_pre = pre[pre['stmt'] == 'BS']
print(f"\nBalance Sheet PRE entries: {len(bs_pre)}")

# Get unique reports
reports = bs_pre['report'].unique()
print(f"Reports: {reports}")

# For each report, look at the tags and their corresponding NUM entries
for report in sorted(reports):
    print(f"\n--- Report {report} ---")
    bs_report = bs_pre[bs_pre['report'] == report]
    print(f"  Lines in PRE: {len(bs_report)}")

    # Get a sample tag to see what periods exist in NUM
    sample_tag = bs_report.iloc[0]['tag']
    print(f"  Sample tag: {sample_tag}")

    # Find NUM entries for this tag
    num_entries = num[(num['tag'] == sample_tag) &
                      (num['segments'].isna()) &
                      (num['coreg'].isna()) &
                      (num['qtrs'] == '0')]

    print(f"  NUM entries for this tag:")
    for _, row in num_entries.sort_values('ddate', ascending=False).iterrows():
        print(f"    ddate={row['ddate']}, value=${float(row['value']):,.0f}")

# Now check if there's version or dimension information
print("\n" + "=" * 80)
print("CHECKING PRE TABLE STRUCTURE")
print("=" * 80)

print("\nPRE table columns:")
for col in pre.columns:
    print(f"  - {col}")

# Check if there's version info
if 'version' in pre.columns:
    print(f"\nVersion values: {pre['version'].unique()}")

# Look at first few rows to understand structure
print("\nFirst 5 BS rows:")
bs_sample = bs_pre.head(5)[['report', 'line', 'stmt', 'tag', 'version', 'plabel']]
print(bs_sample.to_string())

# Now look at Income Statement to see if there's a pattern
print("\n" + "=" * 80)
print("INCOME STATEMENT ANALYSIS")
print("=" * 80)

is_pre = pre[pre['stmt'] == 'IS']
print(f"\nIncome Statement PRE entries: {len(is_pre)}")

# Check reports
is_reports = is_pre['report'].unique()
print(f"Reports: {is_reports}")

for report in sorted(is_reports):
    print(f"\n--- Report {report} ---")
    is_report = is_pre[is_pre['report'] == report]
    print(f"  Lines in PRE: {len(is_report)}")

    # Get sample tag
    sample_tag = is_report.iloc[0]['tag']
    print(f"  Sample tag: {sample_tag}")

    # Find NUM entries
    num_entries = num[(num['tag'] == sample_tag) &
                      (num['segments'].isna()) &
                      (num['coreg'].isna())]

    print(f"  NUM entries for this tag:")
    for _, row in num_entries.sort_values(['ddate', 'qtrs'], ascending=[False, True]).iterrows():
        print(f"    ddate={row['ddate']}, qtrs={row['qtrs']}, value=${float(row['value']):,.0f}")

# Check if version field helps identify displayed periods
print("\n" + "=" * 80)
print("VERSION FIELD ANALYSIS")
print("=" * 80)

# Group IS by report and version
is_versions = is_pre.groupby(['report', 'version']).size().reset_index(name='count')
print("\nIncome Statement - Report x Version combinations:")
print(is_versions.to_string())

# Try to understand version meaning by looking at a specific tag across versions
print("\n\nLooking at 'Revenues' tag across versions...")
revenue_tag = is_pre[is_pre['tag'].str.contains('Revenue', case=False, na=False)].iloc[0]['tag']
print(f"Revenue tag: {revenue_tag}")

revenue_pre = is_pre[is_pre['tag'] == revenue_tag][['report', 'line', 'version', 'plabel']]
print("\nPRE entries:")
print(revenue_pre.to_string())

# Find corresponding NUM entries
revenue_num = num[(num['tag'] == revenue_tag) &
                  (num['segments'].isna()) &
                  (num['coreg'].isna())]
print("\nNUM entries:")
for _, row in revenue_num.sort_values(['ddate', 'qtrs'], ascending=[False, True]).iterrows():
    print(f"  ddate={row['ddate']}, qtrs={row['qtrs']}, value=${float(row['value']):,.0f}")
