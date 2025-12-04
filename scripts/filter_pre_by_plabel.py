"""
Filter pre.txt by plabel substrings and join with company names from sub.txt.

Usage:
    python filter_pre_by_plabel.py <input_file> --plabel <substring1> [<substring2> ...]

Example:
    python filter_pre_by_plabel.py data/sec_datasets/extracted/2024q2/pre.txt --plabel "revenue"
    python filter_pre_by_plabel.py data/sec_datasets/extracted/2024q2/pre.txt --plabel "revenue" "income" "sales"
"""

import argparse
import pandas as pd
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Filter pre.txt by plabel substrings")
    parser.add_argument("input_file", help="Path to pre.txt file")
    parser.add_argument("--plabel", nargs="+", required=True, help="One or more substrings to search in plabel (case-insensitive, OR logic)")

    args = parser.parse_args()

    input_path = Path(args.input_file)

    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        return 1

    # Read pre.txt
    print(f"Reading {input_path}...")
    pre_df = pd.read_csv(input_path, sep="\t", dtype=str)
    print(f"Total rows: {len(pre_df)}")

    # Filter by plabel (case-insensitive contains, OR logic for multiple substrings)
    print(f"Filtering by plabel containing any of: {args.plabel}")
    plabel_upper = pre_df["plabel"].str.upper()
    mask = pd.Series([False] * len(pre_df))
    for substr in args.plabel:
        mask = mask | plabel_upper.str.contains(substr.upper(), na=False)
    filtered_df = pre_df[mask]
    print(f"Filtered rows: {len(filtered_df)}")

    if len(filtered_df) == 0:
        print("No matching rows found.")
        return 0

    # Join with sub.txt to get company names
    sub_path = input_path.parent / "sub.txt"
    if sub_path.exists():
        print(f"\nReading {sub_path}...")
        sub_df = pd.read_csv(sub_path, sep="\t", dtype=str)

        # Select only adsh and name from sub.txt
        sub_for_merge = sub_df[["adsh", "name"]].copy()

        print("Joining with sub.txt on adsh...")
        filtered_df = filtered_df.merge(
            sub_for_merge,
            on="adsh",
            how="left"
        )
        print(f"Rows after join: {len(filtered_df)}")
    else:
        print(f"\nWarning: sub.txt not found at {sub_path}, skipping name join")

    # Output to same folder as input file
    safe_plabel = "_".join("".join(c if c.isalnum() or c in " _-" else "_" for c in p) for p in args.plabel)
    output_path = input_path.parent / f"pre_plabel_{safe_plabel}.xlsx"

    # Truncate long text to avoid Excel cell limit
    for col in filtered_df.columns:
        filtered_df[col] = filtered_df[col].apply(
            lambda x: x[:32000] if isinstance(x, str) and len(x) > 32000 else x
        )

    filtered_df.to_excel(output_path, index=False, engine="xlsxwriter")
    print(f"Exported to: {output_path}")

    return 0


if __name__ == "__main__":
    exit(main())
