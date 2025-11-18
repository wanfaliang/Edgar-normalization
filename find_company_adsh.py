"""
Find correct ADSH for companies in 2024Q3 dataset
"""
import pandas as pd

# Load SUB table
sub_df = pd.read_csv('data/sec_data/extracted/2024q3/sub.txt', sep='\t', dtype=str)
sub_df['cik'] = sub_df['cik'].astype(int)

# Companies to find
companies = [
    {'name': 'P&G', 'cik': 80424},
    {'name': 'M&T Bank', 'cik': 36270}
]

for company in companies:
    print(f"\n{company['name']} (CIK: {company['cik']})")
    print("=" * 60)

    matches = sub_df[sub_df['cik'] == company['cik']]

    if len(matches) == 0:
        print("  ❌ No filings found in 2024Q3 dataset")
    else:
        print(f"  Found {len(matches)} filing(s):")
        for _, row in matches.iterrows():
            print(f"\n  ADSH: {row['adsh']}")
            print(f"  Name: {row['name']}")
            print(f"  Form: {row['form']}")
            print(f"  Period: FY{row['fy']} {row['fp']}")
            print(f"  Filed: {row['filed']}")
