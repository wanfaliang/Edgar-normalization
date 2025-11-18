"""
Investigate abstract tags
Check why TAG table shows abstract=0 for all tags
"""

import pandas as pd

print("="*80)
print("INVESTIGATING ABSTRACT TAGS")
print("="*80)

# Load TAG table
tag_df = pd.read_csv('data/sec_data/extracted/2024q3/tag.txt', sep='\t', dtype=str, low_memory=False)

print(f"\nTotal tags in TAG table: {len(tag_df)}")

# Check abstract column
print("\n" + "="*80)
print("ABSTRACT COLUMN VALUES")
print("="*80)

abstract_counts = tag_df['abstract'].value_counts()
print("\nAbstract value distribution:")
for value, count in abstract_counts.items():
    print(f"  '{value}': {count} tags")

# Check if column exists
print(f"\nColumn name: 'abstract'")
print(f"Column dtype: {tag_df['abstract'].dtype}")
print(f"\nSample values:")
print(tag_df[['tag', 'abstract']].head(20))

# Look for tags that SHOULD be abstract (section headers, totals)
print("\n" + "="*80)
print("TAGS THAT SHOULD BE ABSTRACT (Section Headers/Totals)")
print("="*80)

abstract_keywords = ['Total', 'Assets', 'Liabilities', 'Current', 'Noncurrent',
                     'Equity', 'Revenue', 'Income', 'Comprehensive']

for keyword in abstract_keywords[:5]:
    matching = tag_df[tag_df['tag'].str.contains(keyword, case=False, na=False)]
    if len(matching) > 0:
        print(f"\nTags containing '{keyword}' ({len(matching)} total):")
        for idx, row in matching.head(3).iterrows():
            print(f"  {row['tag']}: abstract={row['abstract']}, datatype={row.get('datatype', 'N/A')}")

# Check Amazon's PRE table for abstract usage
print("\n" + "="*80)
print("AMAZON PRE TABLE - ABSTRACT TAG USAGE")
print("="*80)

pre_df = pd.read_csv('data/sec_data/extracted/2024q3/pre.txt', sep='\t', dtype=str, low_memory=False)
adsh = '0001018724-24-000130'
filing_pre = pre_df[pre_df['adsh'] == adsh]

# Check if abstract tags appear in PRE
filing_tags = filing_pre['tag'].unique()
filing_tag_info = tag_df[tag_df['tag'].isin(filing_tags)]

print(f"\nTags used in Amazon's PRE table: {len(filing_tags)}")
print(f"Abstract tags in Amazon's filing:")

abstract_in_filing = filing_tag_info[filing_tag_info['abstract'] == '1']
print(f"  Count: {len(abstract_in_filing)}")

if len(abstract_in_filing) > 0:
    print(f"\n  Examples:")
    for tag in abstract_in_filing['tag'].head(10):
        # Check if it appears in PRE
        pre_entries = filing_pre[filing_pre['tag'] == tag]
        if len(pre_entries) > 0:
            stmt = pre_entries.iloc[0]['stmt']
            plabel = pre_entries.iloc[0].get('plabel', 'N/A')
            print(f"    {tag} ({stmt}): {plabel}")

print("\n" + "="*80)
