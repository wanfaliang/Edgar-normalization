"""
Load EDGAR pre.txt, num.txt, tag.txt files into PostgreSQL tables
=================================================================

Uses chunked reading for memory efficiency on large files.

Usage:
    python scripts/load_edgar_data.py --year 2024 --quarter 2
    python scripts/load_edgar_data.py --year 2024 --quarter 2 --tables pre,num
    python scripts/load_edgar_data.py --all  # Load all available quarters

Author: Generated with Claude Code
Date: 2025-12
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import argparse
import pandas as pd
from sqlalchemy import create_engine, text
from config import config
import time

# Chunk size for reading files and inserting (memory efficient)
CHUNK_SIZE = 50000


def get_engine():
    """Create SQLAlchemy engine"""
    return create_engine(config.get_db_connection())


def estimate_rows(file_path: Path) -> int:
    """Estimate rows from file size (instant, no file read)"""
    # Rough estimate: ~200 bytes per row for pre/num, ~500 for tag
    size_bytes = file_path.stat().st_size
    return size_bytes // 200


def load_pre_data(engine, year: int, quarter: int, clear_existing: bool = True):
    """Load pre.txt into edgar_pre table using chunked reading"""
    file_path = config.storage.extracted_dir / f'{year}q{quarter}' / 'pre.txt'

    if not file_path.exists():
        print(f"  File not found: {file_path}")
        return 0

    print(f"  Loading {file_path}...")
    est_rows = estimate_rows(file_path)
    print(f"    Estimated rows: ~{est_rows:,}")

    with engine.connect() as conn:
        if clear_existing:
            conn.execute(text(
                "DELETE FROM edgar_pre WHERE source_year = :year AND source_quarter = :quarter"
            ), {'year': year, 'quarter': quarter})
            conn.commit()
            print(f"    Cleared existing data for {year}Q{quarter}")

        # Read and insert in chunks
        total_inserted = 0
        chunks = pd.read_csv(file_path, sep='\t', dtype=str, chunksize=CHUNK_SIZE)

        for chunk in chunks:
            # Add source tracking columns
            chunk['source_year'] = year
            chunk['source_quarter'] = quarter

            # Select columns that exist
            columns = ['adsh', 'report', 'line', 'stmt', 'inpth', 'rfile',
                       'tag', 'version', 'plabel', 'negating', 'source_year', 'source_quarter']
            existing_cols = [c for c in columns if c in chunk.columns]
            chunk = chunk[existing_cols]

            # Convert numeric columns
            for col in ['report', 'line', 'inpth']:
                if col in chunk.columns:
                    chunk[col] = pd.to_numeric(chunk[col], errors='coerce').astype('Int64')

            # Filter out rows with NULL tag
            if 'tag' in chunk.columns:
                chunk = chunk.dropna(subset=['tag'])

            # Insert chunk
            chunk.to_sql('edgar_pre', conn, if_exists='append', index=False, method='multi')
            total_inserted += len(chunk)
            print(f"    Inserted {total_inserted:,} rows...", end='\r')

        conn.commit()

    print(f"    Inserted {total_inserted:,} rows total        ")
    return total_inserted


def load_num_data(engine, year: int, quarter: int, clear_existing: bool = True):
    """Load num.txt into edgar_num table using chunked reading"""
    file_path = config.storage.extracted_dir / f'{year}q{quarter}' / 'num.txt'

    if not file_path.exists():
        print(f"  File not found: {file_path}")
        return 0

    print(f"  Loading {file_path}...")
    est_rows = estimate_rows(file_path)
    print(f"    Estimated rows: ~{est_rows:,}")

    with engine.connect() as conn:
        if clear_existing:
            conn.execute(text(
                "DELETE FROM edgar_num WHERE source_year = :year AND source_quarter = :quarter"
            ), {'year': year, 'quarter': quarter})
            conn.commit()
            print(f"    Cleared existing data for {year}Q{quarter}")

        # Read and insert in chunks
        total_inserted = 0
        chunks = pd.read_csv(file_path, sep='\t', dtype=str, chunksize=CHUNK_SIZE)

        for chunk in chunks:
            # Add source tracking columns
            chunk['source_year'] = year
            chunk['source_quarter'] = quarter

            # Columns to keep
            columns = ['adsh', 'tag', 'version', 'ddate', 'qtrs', 'uom',
                       'coreg', 'value', 'footnote', 'source_year', 'source_quarter']

            # Handle segments column
            if 'segments' in chunk.columns:
                columns.insert(columns.index('coreg'), 'segments')
            elif 'segment' in chunk.columns:
                chunk['segments'] = chunk['segment']
                columns.insert(columns.index('coreg'), 'segments')

            # Select columns that exist
            existing_cols = [c for c in columns if c in chunk.columns]
            chunk = chunk[existing_cols]

            # Convert value to numeric
            if 'value' in chunk.columns:
                chunk['value'] = pd.to_numeric(chunk['value'], errors='coerce')

            # Filter out rows with NULL tag
            if 'tag' in chunk.columns:
                chunk = chunk.dropna(subset=['tag'])

            # Insert chunk
            chunk.to_sql('edgar_num', conn, if_exists='append', index=False, method='multi')
            total_inserted += len(chunk)
            print(f"    Inserted {total_inserted:,} rows...", end='\r')

        conn.commit()

    print(f"    Inserted {total_inserted:,} rows total        ")
    return total_inserted


def load_tag_data(engine, year: int, quarter: int, clear_existing: bool = True):
    """Load tag.txt into edgar_tag table using chunked reading"""
    file_path = config.storage.extracted_dir / f'{year}q{quarter}' / 'tag.txt'

    if not file_path.exists():
        print(f"  File not found: {file_path}")
        return 0

    print(f"  Loading {file_path}...")
    est_rows = estimate_rows(file_path)
    print(f"    Estimated rows: ~{est_rows:,}")

    with engine.connect() as conn:
        if clear_existing:
            conn.execute(text(
                "DELETE FROM edgar_tag WHERE source_year = :year AND source_quarter = :quarter"
            ), {'year': year, 'quarter': quarter})
            conn.commit()
            print(f"    Cleared existing data for {year}Q{quarter}")

        # Read and insert in chunks
        total_inserted = 0
        chunks = pd.read_csv(file_path, sep='\t', dtype=str, chunksize=CHUNK_SIZE)

        for chunk in chunks:
            # Add source tracking columns
            chunk['source_year'] = year
            chunk['source_quarter'] = quarter

            # Columns to keep
            columns = ['tag', 'version', 'custom', 'abstract', 'datatype',
                       'iord', 'crdr', 'tlabel', 'doc', 'source_year', 'source_quarter']

            # Select columns that exist
            existing_cols = [c for c in columns if c in chunk.columns]
            chunk = chunk[existing_cols]

            # Filter out rows with NULL required fields
            if 'tag' in chunk.columns and 'version' in chunk.columns:
                chunk = chunk.dropna(subset=['tag', 'version'])

            # Insert chunk
            chunk.to_sql('edgar_tag', conn, if_exists='append', index=False, method='multi')
            total_inserted += len(chunk)
            print(f"    Inserted {total_inserted:,} rows...", end='\r')

        conn.commit()

    print(f"    Inserted {total_inserted:,} rows total        ")
    return total_inserted


def load_quarter(engine, year: int, quarter: int, tables: list = None):
    """Load all data for a specific quarter"""
    if tables is None:
        tables = ['pre', 'num', 'tag']

    print(f"\n{'='*60}")
    print(f"Loading {year}Q{quarter} data")
    print(f"{'='*60}")

    start_time = time.time()
    results = {}

    if 'pre' in tables:
        results['pre'] = load_pre_data(engine, year, quarter)

    if 'num' in tables:
        results['num'] = load_num_data(engine, year, quarter)

    if 'tag' in tables:
        results['tag'] = load_tag_data(engine, year, quarter)

    elapsed = time.time() - start_time
    print(f"\nCompleted {year}Q{quarter} in {elapsed:.1f}s")
    print(f"  PRE: {results.get('pre', 'skipped'):,} rows" if 'pre' in results else "")
    print(f"  NUM: {results.get('num', 'skipped'):,} rows" if 'num' in results else "")
    print(f"  TAG: {results.get('tag', 'skipped'):,} rows" if 'tag' in results else "")

    return results


def find_available_quarters():
    """Find all quarters with extracted data"""
    extracted_dir = config.storage.extracted_dir
    quarters = []

    for folder in sorted(extracted_dir.iterdir()):
        if folder.is_dir() and folder.name[0:4].isdigit():
            try:
                year = int(folder.name[:4])
                quarter = int(folder.name[5])
                if (folder / 'pre.txt').exists():
                    quarters.append((year, quarter))
            except (ValueError, IndexError):
                continue

    return quarters


def main():
    parser = argparse.ArgumentParser(description='Load EDGAR data into PostgreSQL')
    parser.add_argument('--year', type=int, help='Year (e.g., 2024)')
    parser.add_argument('--quarter', type=int, help='Quarter (1-4)')
    parser.add_argument('--tables', type=str, default='pre,num,tag',
                       help='Comma-separated list of tables to load (pre,num,tag)')
    parser.add_argument('--all', action='store_true', help='Load all available quarters')
    parser.add_argument('--list', action='store_true', help='List available quarters')

    args = parser.parse_args()

    engine = get_engine()

    if args.list:
        quarters = find_available_quarters()
        print(f"Found {len(quarters)} quarters with data:")
        for y, q in quarters:
            print(f"  {y}Q{q}")
        return

    tables = args.tables.split(',')

    if args.all:
        quarters = find_available_quarters()
        print(f"Loading {len(quarters)} quarters...")

        total_start = time.time()
        for year, quarter in quarters:
            load_quarter(engine, year, quarter, tables)

        total_elapsed = time.time() - total_start
        print(f"\n{'='*60}")
        print(f"All done! Total time: {total_elapsed:.1f}s")

    elif args.year and args.quarter:
        load_quarter(engine, args.year, args.quarter, tables)
    else:
        parser.print_help()
        print("\nExamples:")
        print("  python scripts/load_edgar_data.py --year 2024 --quarter 2")
        print("  python scripts/load_edgar_data.py --all")
        print("  python scripts/load_edgar_data.py --list")


if __name__ == '__main__':
    main()
