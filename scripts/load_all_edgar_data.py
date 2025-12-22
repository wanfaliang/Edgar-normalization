"""
Load All EDGAR Data into PostgreSQL
====================================

Loads pre.txt, num.txt, tag.txt from all available quarters into database.
Uses chunked reading for memory efficiency on large files.

Features:
- Progress tracking
- Resume capability (skips already loaded quarters)
- Estimated time remaining
- Log file output
- Memory-efficient chunked loading

Usage:
    python scripts/load_all_edgar_data.py                    # Load all, skip existing
    python scripts/load_all_edgar_data.py --force            # Reload all (clear existing)
    python scripts/load_all_edgar_data.py --start-year 2020  # Load from 2020 onwards
    python scripts/load_all_edgar_data.py --tables pre,num   # Load specific tables only

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
from datetime import datetime
import time

# Chunk size for reading files (memory efficient)
CHUNK_SIZE = 50000

# Log file
LOG_FILE = Path(__file__).parent.parent / 'output' / 'load_edgar_data.log'


def log(message: str, also_print: bool = True):
    """Log message to file and optionally print"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] {message}"

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, 'a') as f:
        f.write(log_line + '\n')

    if also_print:
        print(message)


def get_engine():
    """Create SQLAlchemy engine"""
    return create_engine(config.get_db_connection())


def get_loaded_quarters(engine) -> set:
    """Get set of (year, quarter) tuples already loaded"""
    loaded = set()

    with engine.connect() as conn:
        # Check edgar_pre table for loaded quarters
        result = conn.execute(text(
            "SELECT DISTINCT source_year, source_quarter FROM edgar_pre"
        ))
        for row in result:
            loaded.add((row[0], row[1]))

    return loaded


def estimate_rows(file_path: Path) -> int:
    """Estimate rows from file size (instant, no file read)"""
    size_bytes = file_path.stat().st_size
    return size_bytes // 200


def load_table(engine, table_name: str, year: int, quarter: int, clear_existing: bool = True) -> int:
    """Load a single table for a specific quarter using chunked reading"""
    file_path = config.storage.extracted_dir / f'{year}q{quarter}' / f'{table_name}.txt'

    if not file_path.exists():
        return 0

    db_table = f'edgar_{table_name}'

    with engine.connect() as conn:
        if clear_existing:
            conn.execute(text(
                f"DELETE FROM {db_table} WHERE source_year = :year AND source_quarter = :quarter"
            ), {'year': year, 'quarter': quarter})
            conn.commit()

        # Read and insert in chunks
        total_inserted = 0
        chunks = pd.read_csv(file_path, sep='\t', dtype=str, chunksize=CHUNK_SIZE)

        for chunk in chunks:
            # Add source tracking columns
            chunk['source_year'] = year
            chunk['source_quarter'] = quarter

            # Table-specific column handling
            if table_name == 'pre':
                columns = ['adsh', 'report', 'line', 'stmt', 'inpth', 'rfile',
                           'tag', 'version', 'plabel', 'negating', 'source_year', 'source_quarter']
                for col in ['report', 'line', 'inpth']:
                    if col in chunk.columns:
                        chunk[col] = pd.to_numeric(chunk[col], errors='coerce').astype('Int64')

            elif table_name == 'num':
                columns = ['adsh', 'tag', 'version', 'ddate', 'qtrs', 'uom',
                           'coreg', 'value', 'footnote', 'source_year', 'source_quarter']
                if 'segments' in chunk.columns:
                    columns.insert(columns.index('coreg'), 'segments')
                elif 'segment' in chunk.columns:
                    chunk['segments'] = chunk['segment']
                    columns.insert(columns.index('coreg'), 'segments')
                if 'value' in chunk.columns:
                    chunk['value'] = pd.to_numeric(chunk['value'], errors='coerce')

            elif table_name == 'tag':
                columns = ['tag', 'version', 'custom', 'abstract', 'datatype',
                           'iord', 'crdr', 'tlabel', 'doc', 'source_year', 'source_quarter']

            # Select columns that exist
            existing_cols = [c for c in columns if c in chunk.columns]
            chunk = chunk[existing_cols]

            # Filter out rows with NULL required fields (bad data from SEC)
            if table_name in ('pre', 'num') and 'tag' in chunk.columns:
                chunk = chunk.dropna(subset=['tag'])
            if table_name == 'tag' and 'tag' in chunk.columns and 'version' in chunk.columns:
                chunk = chunk.dropna(subset=['tag', 'version'])

            # Insert chunk
            chunk.to_sql(db_table, conn, if_exists='append', index=False, method='multi')
            total_inserted += len(chunk)

        conn.commit()

    return total_inserted


def load_quarter(engine, year: int, quarter: int, tables: list, clear_existing: bool = True) -> dict:
    """Load all specified tables for a quarter"""
    results = {}

    for table in tables:
        count = load_table(engine, table, year, quarter, clear_existing)
        results[table] = count

    return results


def find_available_quarters() -> list:
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


def format_time(seconds: float) -> str:
    """Format seconds as human-readable time"""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"


def main():
    parser = argparse.ArgumentParser(description='Load all EDGAR data into PostgreSQL')
    parser.add_argument('--force', action='store_true',
                       help='Force reload (clear existing data)')
    parser.add_argument('--start-year', type=int, default=2009,
                       help='Start from this year (default: 2009)')
    parser.add_argument('--end-year', type=int, default=2099,
                       help='End at this year (default: all)')
    parser.add_argument('--tables', type=str, default='pre,num,tag',
                       help='Comma-separated list of tables (default: pre,num,tag)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be loaded without loading')

    args = parser.parse_args()
    tables = args.tables.split(',')

    engine = get_engine()

    # Find available quarters
    all_quarters = find_available_quarters()

    # Filter by year range
    quarters = [(y, q) for y, q in all_quarters
                if args.start_year <= y <= args.end_year]

    # Check what's already loaded (unless forcing)
    if not args.force:
        loaded = get_loaded_quarters(engine)
        to_load = [(y, q) for y, q in quarters if (y, q) not in loaded]
        skipped = len(quarters) - len(to_load)
    else:
        to_load = quarters
        skipped = 0

    log(f"\n{'='*70}")
    log(f"EDGAR DATA LOADER (Chunked)")
    log(f"{'='*70}")
    log(f"Available quarters: {len(all_quarters)}")
    log(f"In year range: {len(quarters)}")
    log(f"Already loaded: {skipped}")
    log(f"To load: {len(to_load)}")
    log(f"Tables: {', '.join(tables)}")
    log(f"Force reload: {args.force}")
    log(f"Chunk size: {CHUNK_SIZE:,}")
    log(f"{'='*70}")

    if args.dry_run:
        log("\nDRY RUN - would load:")
        for y, q in to_load[:10]:
            log(f"  {y}Q{q}")
        if len(to_load) > 10:
            log(f"  ... and {len(to_load) - 10} more")
        return

    if not to_load:
        log("\nNothing to load!")
        return

    # Estimate time (rough: ~5 min per quarter with chunked loading)
    est_time = len(to_load) * 5 * 60  # seconds
    log(f"\nEstimated time: {format_time(est_time)}")
    log(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"Log file: {LOG_FILE}")
    log("")

    # Load each quarter
    start_time = time.time()
    total_pre = 0
    total_num = 0
    total_tag = 0

    for idx, (year, quarter) in enumerate(to_load, 1):
        quarter_start = time.time()

        log(f"[{idx}/{len(to_load)}] Loading {year}Q{quarter}...", also_print=True)

        results = load_quarter(engine, year, quarter, tables, clear_existing=True)

        quarter_time = time.time() - quarter_start
        elapsed = time.time() - start_time
        remaining = (elapsed / idx) * (len(to_load) - idx)

        pre_count = results.get('pre', 0)
        num_count = results.get('num', 0)
        tag_count = results.get('tag', 0)

        total_pre += pre_count
        total_num += num_count
        total_tag += tag_count

        log(f"         PRE: {pre_count:,} | NUM: {num_count:,} | TAG: {tag_count:,} | "
            f"Time: {format_time(quarter_time)} | ETA: {format_time(remaining)}")

    # Summary
    total_time = time.time() - start_time
    log(f"\n{'='*70}")
    log(f"COMPLETE!")
    log(f"{'='*70}")
    log(f"Quarters loaded: {len(to_load)}")
    log(f"Total PRE rows: {total_pre:,}")
    log(f"Total NUM rows: {total_num:,}")
    log(f"Total TAG rows: {total_tag:,}")
    log(f"Total time: {format_time(total_time)}")
    log(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"{'='*70}")


if __name__ == '__main__':
    main()
