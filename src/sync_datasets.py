"""
Dataset Synchronization Tool
============================
Automatically check for and download new SEC quarterly datasets

This script:
1. Determines the latest available quarter based on current date
2. Checks which datasets are already downloaded/indexed
3. Downloads any missing quarters
4. Indexes new data into PostgreSQL
5. Optionally updates ticker symbols

The SEC typically releases quarterly data 6-8 weeks after quarter end.
This script uses conservative estimates to avoid attempting downloads
of datasets that don't exist yet.

Usage:
    # Sync all missing datasets (recommended)
    python sync_datasets.py

    # Sync and update tickers
    python sync_datasets.py --update-tickers

    # Dry run (show what would be downloaded)
    python sync_datasets.py --dry-run

    # Force check for latest quarter (even if estimate says not ready)
    python sync_datasets.py --force-latest

Author: Finexus Team
Date: November 2025
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Tuple, Dict
import psycopg2
from psycopg2.extras import RealDictCursor

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import config
from bulk_downloader import BulkDatasetDownloader
from filing_index import FilingIndexer
from update_tickers import TickerUpdater


class DatasetSynchronizer:
    """
    Synchronize local datasets with SEC EDGAR releases

    The SEC releases quarterly financial statement datasets approximately
    6-8 weeks after quarter end. This class intelligently determines what
    datasets should be available and downloads/indexes any missing data.
    """

    # Conservative estimate: SEC releases data 8 weeks after quarter end
    RELEASE_DELAY_WEEKS = 8

    def __init__(self):
        """Initialize the synchronizer"""
        self.downloader = BulkDatasetDownloader()
        self.indexer = FilingIndexer()
        self.conn = psycopg2.connect(config.get_db_connection())
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)

    def __del__(self):
        """Cleanup database connection"""
        if hasattr(self, 'cur'):
            self.cur.close()
        if hasattr(self, 'conn'):
            self.conn.close()

    def get_quarter_end_date(self, year: int, quarter: int) -> datetime:
        """
        Get the last day of a fiscal quarter

        Args:
            year: Year
            quarter: Quarter (1-4)

        Returns:
            datetime of quarter end
        """
        quarter_ends = {
            1: (year, 3, 31),
            2: (year, 6, 30),
            3: (year, 9, 30),
            4: (year, 12, 31)
        }

        year_end, month, day = quarter_ends[quarter]
        return datetime(year_end, month, day)

    def estimate_latest_available_quarter(self, conservative: bool = True) -> Tuple[int, int]:
        """
        Estimate the latest quarter that should be available from SEC

        The SEC releases quarterly data approximately 6-8 weeks after quarter end.
        This uses a conservative 8-week estimate by default.

        Args:
            conservative: If True, use 8-week delay; if False, use 6-week delay

        Returns:
            Tuple of (year, quarter)
        """
        today = datetime.now()

        # Use conservative (8 weeks) or aggressive (6 weeks) estimate
        delay_weeks = self.RELEASE_DELAY_WEEKS if conservative else 6

        # Estimate release date by subtracting delay from today
        estimated_latest = today - timedelta(weeks=delay_weeks)

        # Determine which quarter this falls into
        year = estimated_latest.year
        month = estimated_latest.month

        if month <= 3:
            quarter = 1
        elif month <= 6:
            quarter = 2
        elif month <= 9:
            quarter = 3
        else:
            quarter = 4

        return year, quarter

    def get_downloaded_datasets(self) -> List[Tuple[int, int]]:
        """
        Get list of datasets already downloaded

        Returns:
            List of (year, quarter) tuples
        """
        self.cur.execute("""
            SELECT DISTINCT source_year, source_quarter
            FROM filings
            ORDER BY source_year, source_quarter
        """)

        return [(row['source_year'], row['source_quarter']) for row in self.cur.fetchall()]

    def get_indexed_datasets(self) -> Dict[Tuple[int, int], Dict]:
        """
        Get statistics about indexed datasets

        Returns:
            Dict: {(year, quarter): {'companies': count, 'filings': count}}
        """
        self.cur.execute("""
            SELECT
                source_year,
                source_quarter,
                COUNT(DISTINCT cik) as companies,
                COUNT(*) as filings
            FROM filings
            GROUP BY source_year, source_quarter
            ORDER BY source_year, source_quarter
        """)

        stats = {}
        for row in self.cur.fetchall():
            key = (row['source_year'], row['source_quarter'])
            stats[key] = {
                'companies': row['companies'],
                'filings': row['filings']
            }

        return stats

    def get_missing_datasets(self, start_year: int = 2009, start_quarter: int = 1,
                            force_latest: bool = False) -> List[Tuple[int, int]]:
        """
        Determine which datasets are missing

        Args:
            start_year: Earliest year to check (default: 2009)
            start_quarter: Earliest quarter to check (default: 1)
            force_latest: If True, include latest quarter even if estimate says not ready

        Returns:
            List of (year, quarter) tuples for missing datasets
        """
        # Get latest expected quarter
        latest_year, latest_quarter = self.estimate_latest_available_quarter(
            conservative=not force_latest
        )

        # Get what we already have
        downloaded = set(self.get_downloaded_datasets())

        # Generate all quarters from start to latest
        all_quarters = []
        year, quarter = start_year, start_quarter

        while (year, quarter) <= (latest_year, latest_quarter):
            all_quarters.append((year, quarter))

            # Increment quarter
            quarter += 1
            if quarter > 4:
                quarter = 1
                year += 1

        # Find missing quarters
        missing = [q for q in all_quarters if q not in downloaded]

        return missing

    def sync(self, dry_run: bool = False, force_latest: bool = False,
            update_tickers: bool = False) -> Dict:
        """
        Synchronize datasets - download and index missing quarters

        Args:
            dry_run: If True, show what would be done without doing it
            force_latest: If True, attempt to download latest quarter even if estimate says not ready
            update_tickers: If True, update ticker symbols after sync

        Returns:
            Dict with sync results
        """
        print(f"\n{'='*70}")
        print("SEC DATASET SYNCHRONIZATION")
        print(f"{'='*70}\n")

        # Determine latest expected quarter
        latest_year, latest_quarter = self.estimate_latest_available_quarter(
            conservative=not force_latest
        )

        print(f"Today's date: {datetime.now().strftime('%Y-%m-%d')}")
        print(f"Latest expected quarter: {latest_year}Q{latest_quarter}")

        if force_latest:
            print("  ⚠️  Force mode: Will attempt latest quarter even if estimate says not ready")

        # Get current state
        print(f"\n{'='*70}")
        print("CURRENT STATE")
        print(f"{'='*70}\n")

        downloaded = self.get_downloaded_datasets()
        indexed_stats = self.get_indexed_datasets()

        print(f"Downloaded datasets: {len(downloaded)}")
        if downloaded:
            print(f"  Range: {downloaded[0][0]}Q{downloaded[0][1]} - {downloaded[-1][0]}Q{downloaded[-1][1]}")

        total_companies = len(set(cik for stats in indexed_stats.values() for cik in [None]))
        total_filings = sum(stats['filings'] for stats in indexed_stats.values())

        self.cur.execute("SELECT COUNT(DISTINCT cik) FROM filings")
        actual_companies = self.cur.fetchone()['count']

        self.cur.execute("SELECT COUNT(*) FROM filings")
        actual_filings = self.cur.fetchone()['count']

        print(f"Indexed companies: {actual_companies:,}")
        print(f"Indexed filings: {actual_filings:,}")

        # Find missing datasets
        print(f"\n{'='*70}")
        print("CHECKING FOR MISSING DATASETS")
        print(f"{'='*70}\n")

        missing = self.get_missing_datasets(force_latest=force_latest)

        if not missing:
            print("✅ All datasets up to date! No sync needed.")
            return {
                'success': True,
                'downloaded': 0,
                'indexed': 0,
                'message': 'Already up to date'
            }

        print(f"Missing datasets: {len(missing)}")
        for year, quarter in missing[:10]:  # Show first 10
            print(f"  - {year}Q{quarter}")
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more")

        if dry_run:
            print(f"\n{'='*70}")
            print("DRY RUN - No changes will be made")
            print(f"{'='*70}\n")
            print(f"Would download and index {len(missing)} datasets")
            return {
                'success': True,
                'dry_run': True,
                'missing': len(missing)
            }

        # Download and index missing datasets
        print(f"\n{'='*70}")
        print(f"DOWNLOADING & INDEXING {len(missing)} DATASETS")
        print(f"{'='*70}\n")

        results = {
            'downloaded': 0,
            'indexed': 0,
            'failed': [],
            'success': True
        }

        for i, (year, quarter) in enumerate(missing, 1):
            print(f"\n[{i}/{len(missing)}] Processing {year}Q{quarter}...")

            # Download
            try:
                print(f"  Downloading...")
                download_result = self.downloader.download_quarter(year, quarter, force=False)

                if download_result.success:
                    print(f"  ✅ Downloaded ({download_result.zip_size_mb:.1f} MB)")
                    results['downloaded'] += 1
                else:
                    error_msg = download_result.error or "Unknown error"
                    print(f"  ⚠️  Download skipped or failed: {error_msg}")
                    if "not found" in error_msg.lower() or "404" in error_msg:
                        print(f"      This quarter may not be released yet")
                        continue
                    else:
                        results['failed'].append((year, quarter, 'download', error_msg))
                        continue

            except Exception as e:
                print(f"  ❌ Download error: {e}")
                results['failed'].append((year, quarter, 'download', str(e)))
                continue

            # Index
            try:
                print(f"  Indexing...")
                index_result = self.indexer.index_quarter(year, quarter, force=False)

                if index_result and isinstance(index_result, dict):
                    companies = index_result.get('companies', {}).get('upserted', 0)
                    filings = index_result.get('filings', {}).get('inserted', 0)
                    print(f"  ✅ Indexed ({companies:,} companies, {filings:,} filings)")
                    results['indexed'] += 1
                else:
                    # Already indexed or no data
                    print(f"  ⚠️  Already indexed or no data")
                    # Don't count as failure if it's already indexed

            except Exception as e:
                print(f"  ❌ Indexing error: {e}")
                results['failed'].append((year, quarter, 'index', str(e)))

        # Update tickers if requested
        if update_tickers and results['indexed'] > 0:
            print(f"\n{'='*70}")
            print("UPDATING TICKER SYMBOLS")
            print(f"{'='*70}\n")

            try:
                ticker_updater = TickerUpdater()
                ticker_updater.run(include_exchange=True)
                print("✅ Tickers updated")
            except Exception as e:
                print(f"❌ Ticker update failed: {e}")

        # Summary
        print(f"\n{'='*70}")
        print("SYNCHRONIZATION COMPLETE")
        print(f"{'='*70}\n")

        print(f"Downloaded: {results['downloaded']}")
        print(f"Indexed: {results['indexed']}")

        if results['failed']:
            print(f"\n⚠️  Failed: {len(results['failed'])}")
            for year, quarter, stage, error in results['failed'][:5]:
                print(f"  - {year}Q{quarter} ({stage}): {error[:50]}")

        results['success'] = results['indexed'] > 0 or len(results['failed']) == 0

        return results


def main():
    """Command-line interface"""
    parser = argparse.ArgumentParser(
        description='Synchronize SEC datasets - download and index missing quarters',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Sync all missing datasets (recommended)
  python sync_datasets.py

  # Dry run to see what would be downloaded
  python sync_datasets.py --dry-run

  # Force check for latest quarter
  python sync_datasets.py --force-latest

  # Sync and update tickers
  python sync_datasets.py --update-tickers

  # Show current state only
  python sync_datasets.py --status

Notes:
  - The SEC releases quarterly data 6-8 weeks after quarter end
  - This script uses a conservative 8-week estimate
  - Use --force-latest to attempt download of the current quarter
        """
    )

    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without doing it')
    parser.add_argument('--force-latest', action='store_true',
                       help='Attempt to download latest quarter even if estimate says not ready')
    parser.add_argument('--update-tickers', action='store_true',
                       help='Update ticker symbols after sync')
    parser.add_argument('--status', action='store_true',
                       help='Show current state and exit (no sync)')

    args = parser.parse_args()

    syncer = DatasetSynchronizer()

    if args.status:
        # Just show status
        print(f"\n{'='*70}")
        print("DATASET STATUS")
        print(f"{'='*70}\n")

        downloaded = syncer.get_downloaded_datasets()
        indexed_stats = syncer.get_indexed_datasets()
        latest_year, latest_quarter = syncer.estimate_latest_available_quarter()
        missing = syncer.get_missing_datasets()

        print(f"Latest expected: {latest_year}Q{latest_quarter}")
        print(f"Downloaded: {len(downloaded)} datasets")
        if downloaded:
            print(f"  Range: {downloaded[0][0]}Q{downloaded[0][1]} - {downloaded[-1][0]}Q{downloaded[-1][1]}")

        syncer.cur.execute("SELECT COUNT(DISTINCT cik) FROM filings")
        companies = syncer.cur.fetchone()['count']
        syncer.cur.execute("SELECT COUNT(*) FROM filings")
        filings = syncer.cur.fetchone()['count']

        print(f"Indexed: {companies:,} companies, {filings:,} filings")
        print(f"Missing: {len(missing)} datasets")

        sys.exit(0)

    # Run sync
    results = syncer.sync(
        dry_run=args.dry_run,
        force_latest=args.force_latest,
        update_tickers=args.update_tickers
    )

    sys.exit(0 if results['success'] else 1)


if __name__ == '__main__':
    main()
