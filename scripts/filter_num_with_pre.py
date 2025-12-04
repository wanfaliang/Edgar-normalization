"""
Filter num.txt and pre.txt by company name, then merge them on tag.

This script:
1. Reads sub.txt to find adsh values by company name
2. Filters both pre.txt and num.txt by those adsh values
3. Extends num.txt with fields from pre.txt (report, line, stmt, inpth, rfile, plabel, negating) based on tag
4. Exports merged result to Excel

Usage:
    python filter_num_with_pre.py <folder_path> --name <company_name>

Example:
    python filter_num_with_pre.py data/sec_datasets/extracted/2024q2 --name "APPLE INC"
"""

import argparse
import pandas as pd
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Filter num.txt and pre.txt by company name, merge on tag")
    parser.add_argument("folder_path", help="Path to folder containing sub.txt, pre.txt, num.txt")
    parser.add_argument("--name", required=True, help="Company name to filter by")

    args = parser.parse_args()

    folder_path = Path(args.folder_path)

    # Check all required files exist
    sub_path = folder_path / "sub.txt"
    pre_path = folder_path / "pre.txt"
    num_path = folder_path / "num.txt"

    for path in [sub_path, pre_path, num_path]:
        if not path.exists():
            print(f"Error: File not found: {path}")
            return 1

    # Step 1: Read sub.txt and find adsh by company name
    print(f"Reading {sub_path}...")
    sub_df = pd.read_csv(sub_path, sep="\t", dtype=str)

    mask = sub_df["name"].str.upper().str.contains(args.name.upper(), na=False)
    matched_sub = sub_df[mask]

    if len(matched_sub) == 0:
        print(f"No company found matching: {args.name}")
        return 0

    adsh_values = matched_sub["adsh"].tolist()
    print(f"Found {len(adsh_values)} filings for companies matching '{args.name}':")
    for _, row in matched_sub.iterrows():
        print(f"  - {row['name']} ({row['adsh']})")

    # Step 2: Read and filter num.txt
    print(f"\nReading {num_path}...")
    num_df = pd.read_csv(num_path, sep="\t", dtype=str)
    print(f"Total num.txt rows: {len(num_df)}")

    num_filtered = num_df[num_df["adsh"].isin(adsh_values)]
    print(f"Filtered num.txt rows: {len(num_filtered)}")

    if len(num_filtered) == 0:
        print("No matching rows in num.txt.")
        return 0

    # Step 3: Read and filter pre.txt
    print(f"\nReading {pre_path}...")
    pre_df = pd.read_csv(pre_path, sep="\t", dtype=str)
    print(f"Total pre.txt rows: {len(pre_df)}")

    pre_filtered = pre_df[pre_df["adsh"].isin(adsh_values)]
    print(f"Filtered pre.txt rows: {len(pre_filtered)}")

    # Step 4: Merge num with pre on adsh and tag
    # Select only the columns we need from pre
    pre_cols = ["adsh", "tag", "report", "line", "stmt", "inpth", "rfile", "plabel", "negating"]
    pre_for_merge = pre_filtered[pre_cols].copy()

    # There may be multiple pre rows for same adsh+tag (different reports/lines)
    # We'll use left join to keep all num rows
    print("\nMerging num.txt with pre.txt on adsh and tag...")
    merged_df = num_filtered.merge(
        pre_for_merge,
        on=["adsh", "tag"],
        how="left"
    )
    print(f"Merged rows: {len(merged_df)}")

    # Step 5: Export to Excel
    safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in args.name)
    output_path = folder_path / f"num_pre_{safe_name}.xlsx"

    merged_df.to_excel(output_path, index=False)
    print(f"\nExported to: {output_path}")

    return 0


if __name__ == "__main__":
    exit(main())
