"""
Investigate non-monetary tags and values
Check what data types exist beyond monetary values
"""

import pandas as pd

print("="*80)
print("INVESTIGATING NON-MONETARY VALUES AND DATA TYPES")
print("="*80)

# Load NUM and TAG tables
num_df = pd.read_csv('data/sec_data/extracted/2024q3/num.txt', sep='\t', dtype=str, low_memory=False)
tag_df = pd.read_csv('data/sec_data/extracted/2024q3/tag.txt', sep='\t', dtype=str, low_memory=False)

# Check Amazon filing
adsh = '0001018724-24-000130'
filing_num = num_df[num_df['adsh'] == adsh].copy()

print(f"\nAmazon filing: {adsh}")
print(f"Total NUM rows: {len(filing_num)}")

# Try to convert values to numeric
filing_num['value_numeric'] = pd.to_numeric(filing_num['value'], errors='coerce')
non_numeric = filing_num[filing_num['value_numeric'].isna()]

print(f"\nNon-numeric values: {len(non_numeric)}")
if len(non_numeric) > 0:
    print("\nSample non-numeric values:")
    for idx, row in non_numeric.head(10).iterrows():
        print(f"  Tag: {row['tag']}")
        print(f"  Value: {row['value']}")
        print(f"  UOM: {row.get('uom', 'N/A')}")
        print()

# Check UOM (unit of measure) distribution
print("\n" + "="*80)
print("UNIT OF MEASURE (UOM) DISTRIBUTION")
print("="*80)

uom_counts = filing_num['uom'].value_counts()
print("\nTop UOMs in Amazon filing:")
for uom, count in uom_counts.head(20).items():
    print(f"  {uom}: {count} values")

# Check datatype distribution in TAG table
print("\n" + "="*80)
print("TAG TABLE - DATATYPE DISTRIBUTION")
print("="*80)

# Get tags used in Amazon filing
filing_tags = filing_num['tag'].unique()
filing_tag_info = tag_df[tag_df['tag'].isin(filing_tags)]

datatype_counts = filing_tag_info['datatype'].value_counts()
print("\nDatatypes for Amazon's tags:")
for dtype, count in datatype_counts.items():
    print(f"  {dtype}: {count} tags")

# Show examples of non-monetary datatypes
print("\n" + "="*80)
print("EXAMPLES OF NON-MONETARY TAG TYPES")
print("="*80)

for dtype in ['shares', 'perShare', 'pure', 'rate']:
    dtype_tags = filing_tag_info[filing_tag_info['datatype'] == dtype]
    if len(dtype_tags) > 0:
        print(f"\n{dtype} tags ({len(dtype_tags)} total):")
        for tag in dtype_tags['tag'].head(5):
            # Get sample value
            sample = filing_num[filing_num['tag'] == tag].head(1)
            if len(sample) > 0:
                value = sample.iloc[0]['value']
                uom = sample.iloc[0].get('uom', 'N/A')
                print(f"  {tag}: value={value}, uom={uom}")

print("\n" + "="*80)
