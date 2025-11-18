"""
Find abstract tags by checking which tags appear in PRE but not NUM
Abstract tags are section headers - they appear in presentation but have no raw value
"""

import pandas as pd

print("="*80)
print("FINDING ABSTRACT TAGS BY USAGE PATTERN")
print("="*80)

# Load Amazon filing
adsh = '0001018724-24-000130'

pre_df = pd.read_csv('data/sec_data/extracted/2024q3/pre.txt', sep='\t', dtype=str)
num_df = pd.read_csv('data/sec_data/extracted/2024q3/num.txt', sep='\t', dtype=str)

filing_pre = pre_df[pre_df['adsh'] == adsh]
filing_num = num_df[num_df['adsh'] == adsh]

tags_in_pre = set(filing_pre['tag'].unique())
tags_in_num = set(filing_num['tag'].unique())

tags_pre_only = tags_in_pre - tags_in_num

print(f"\nAmazon filing: {adsh}")
print(f"Tags in PRE: {len(tags_in_pre)}")
print(f"Tags in NUM: {len(tags_in_num)}")
print(f"Tags in PRE but NOT in NUM: {len(tags_pre_only)}")

if tags_pre_only:
    print(f"\nThese are likely ABSTRACT tags (section headers with no raw values):")
    print(f"They appear in presentation but have no values in NUM table")
    print()

    # Show them by statement type
    for stmt in ['BS', 'IS', 'CF']:
        stmt_pre = filing_pre[filing_pre['stmt'] == stmt]
        stmt_abstract = stmt_pre[stmt_pre['tag'].isin(tags_pre_only)]

        if len(stmt_abstract) > 0:
            print(f"\n{stmt} Statement - Abstract tags:")
            for idx, row in stmt_abstract.iterrows():
                print(f"  {row['tag']}: {row.get('plabel', 'N/A')}")

# Check if we're handling these in reconstruction
print(f"\n{'='*80}")
print("IMPACT ON RECONSTRUCTION")
print(f"{'='*80}")

print(f"\nOur current code:")
print(f"  - Filters NUM for values (excludes abstract tags)")
print(f"  - These abstract tags have node.value = None")
print(f"  - They should appear in hierarchy as section headers")
print(f"  - Their values should be calculated as sum of children")

print(f"\nQuestion: Are we including abstract tags in output?")
print(f"  Let me check...")

# Simulate what we export
print(f"\nIn flatten_multi_period, we check: 'if node.value is not None'")
print(f"This means abstract tags (value=None) are EXCLUDED from line_items!")
print(f"\n⚠️  PROBLEM: We're excluding section headers from output!")

print(f"\n{'='*80}")
