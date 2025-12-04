"""
Read tag.txt and export to Excel.

Usage:
    python export_tag.py <input_file>

Example:
    python export_tag.py data/sec_datasets/extracted/2024q2/tag.txt
"""

import argparse
import pandas as pd
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Read tag.txt and export to Excel")
    parser.add_argument("input_file", help="Path to tag.txt file")

    args = parser.parse_args()

    input_path = Path(args.input_file)

    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        return 1

    print(f"Reading {input_path}...")
    df = pd.read_csv(input_path, sep="\t", dtype=str)

    print(f"Total rows: {len(df)}")

    # Truncate long text in 'doc' column to avoid Excel cell limit (32767 chars)
    if "doc" in df.columns:
        df["doc"] = df["doc"].apply(lambda x: x[:32000] if isinstance(x, str) and len(x) > 32000 else x)

    output_path = input_path.parent / "tag.xlsx"

    # Use xlsxwriter engine for better handling of large files
    df.to_excel(output_path, index=False, engine="xlsxwriter")
    print(f"Exported to: {output_path}")

    return 0


if __name__ == "__main__":
    exit(main())
