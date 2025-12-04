"""
Filter pre.txt (SEC EDGAR presentation data) by adsh or company name and export to Excel.
Also joins with tag.txt to include tag metadata fields.

Usage:
    python filter_pre.py <input_file> --adsh <adsh_value1> [<adsh_value2> ...]
    python filter_pre.py <input_file> --name <company_name>

Example:
    python filter_pre.py data/sec_datasets/extracted/2024q2/pre.txt --adsh 0000002178-24-000054
    python filter_pre.py data/sec_datasets/extracted/2024q2/pre.txt --name "APPLE INC"

Output includes:
    - All pre.txt fields: adsh, report, line, stmt, inpth, rfile, tag, version, plabel, negating
    - Tag metadata from tag.txt: custom, abstract, datatype, iord, crdr, tlabel, doc
"""

import argparse
import pandas as pd
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Filter pre.txt by adsh or company name and export to Excel")
    parser.add_argument("input_file", help="Path to pre.txt file")
    parser.add_argument("--adsh", nargs="+", help="One or more adsh values to filter by")
    parser.add_argument("--name", help="Company name to filter by (searches in sub.txt)")

    args = parser.parse_args()

    if not args.adsh and not args.name:
        print("Error: Must specify either --adsh or --name")
        return 1

    input_path = Path(args.input_file)

    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        return 1

    # Determine adsh values and output filename
    if args.name:
        # Find sub.txt in same folder
        sub_path = input_path.parent / "sub.txt"
        if not sub_path.exists():
            print(f"Error: sub.txt not found at {sub_path}")
            return 1

        print(f"Reading {sub_path}...")
        sub_df = pd.read_csv(sub_path, sep="\t", dtype=str)

        # Filter by name (case-insensitive contains)
        mask = sub_df["name"].str.upper().str.contains(args.name.upper(), na=False)
        matched_sub = sub_df[mask]

        if len(matched_sub) == 0:
            print(f"No company found matching: {args.name}")
            return 0

        adsh_values = matched_sub["adsh"].tolist()
        print(f"Found {len(adsh_values)} filings for companies matching '{args.name}':")
        for _, row in matched_sub.iterrows():
            print(f"  - {row['name']} ({row['adsh']})")

        # Sanitize name for filename
        safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in args.name)
        output_filename = f"pre_{safe_name}.xlsx"
    else:
        adsh_values = args.adsh
        output_filename = "pre_filtered.xlsx"

    print(f"\nReading {input_path}...")
    df = pd.read_csv(input_path, sep="\t", dtype=str)

    print(f"Total rows: {len(df)}")
    print(f"Filtering by adsh: {adsh_values}")

    filtered_df = df[df["adsh"].isin(adsh_values)]

    print(f"Filtered rows: {len(filtered_df)}")

    if len(filtered_df) == 0:
        print("No matching rows found.")
        return 0

    # Join with tag.txt to add tag metadata
    tag_path = input_path.parent / "tag.txt"
    if tag_path.exists():
        print(f"\nReading {tag_path}...")
        tag_df = pd.read_csv(tag_path, sep="\t", dtype=str)

        # Select columns to join from tag.txt
        tag_cols = ["tag", "version", "custom", "abstract", "datatype", "iord", "crdr", "tlabel", "doc"]
        tag_for_merge = tag_df[tag_cols].copy()

        print("Joining with tag.txt on tag and version...")
        filtered_df = filtered_df.merge(
            tag_for_merge,
            on=["tag", "version"],
            how="left"
        )
        print(f"Rows after join: {len(filtered_df)}")
    else:
        print(f"\nWarning: tag.txt not found at {tag_path}, skipping tag metadata join")

    # Output to same folder as input file
    output_path = input_path.parent / output_filename

    filtered_df.to_excel(output_path, index=False)
    print(f"Exported to: {output_path}")

    return 0


if __name__ == "__main__":
    exit(main())
