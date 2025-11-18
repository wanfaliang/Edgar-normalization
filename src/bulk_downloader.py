"""
SEC Financial Statement Data Sets - Bulk Downloader
====================================================
Downloads all historical SEC quarterly datasets with:
- Concurrent downloads with rate limiting
- Progress tracking and resumption
- PostgreSQL database tracking
- Comprehensive error handling

Author: Finexus Team
Date: November 2025
"""

import os
import sys
import time
import zipfile
import requests
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import psycopg2
from psycopg2.extras import RealDictCursor

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))
from config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class DownloadResult:
    """Result of a quarter download operation"""
    year: int
    quarter: int
    success: bool
    error: Optional[str] = None
    zip_size_mb: float = 0.0
    download_time_seconds: float = 0.0
    extracted_files: int = 0


class BulkDatasetDownloader:
    """
    Download and manage SEC quarterly financial statement datasets

    Features:
    - Download single quarters or ranges
    - Concurrent downloads with SEC rate limiting
    - Database tracking (datasets table)
    - Skip already downloaded datasets
    - Resume interrupted downloads
    - Comprehensive error handling
    """

    def __init__(self):
        self.config = config
        self.sec_config = config.sec
        self.storage = config.storage
        self.processing = config.processing

        # Ensure directories exist
        self.storage.create_directories()

        # Database connection
        self.db_conn_string = config.get_db_connection()

        # SEC compliance
        self.headers = {
            'User-Agent': self.sec_config.user_agent,
            'Accept-Encoding': 'gzip, deflate',
            'Host': 'www.sec.gov'
        }

        # Rate limiting
        self.rate_limit_delay = self.sec_config.rate_limit_delay
        self.last_request_time = 0

    def _get_db_connection(self):
        """Get database connection"""
        return psycopg2.connect(self.db_conn_string)

    def _rate_limit_wait(self):
        """Enforce SEC rate limiting"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

    def _get_quarter_url(self, year: int, quarter: int) -> str:
        """Construct download URL for a quarter"""
        filename = f"{year}q{quarter}.zip"
        return f"{self.sec_config.financial_statements_url}{filename}"

    def _get_quarter_paths(self, year: int, quarter: int) -> Tuple[Path, Path]:
        """Get file paths for a quarter dataset"""
        filename = f"{year}q{quarter}.zip"
        zip_path = self.storage.download_dir / filename
        extract_path = self.storage.extracted_dir / f"{year}q{quarter}"
        return zip_path, extract_path

    def _check_dataset_exists(self, year: int, quarter: int) -> bool:
        """Check if dataset is already downloaded and extracted"""
        zip_path, extract_path = self._get_quarter_paths(year, quarter)

        # Check if extracted files exist
        if extract_path.exists():
            required_files = ['sub.txt', 'num.txt', 'tag.txt', 'pre.txt']
            existing_files = [f for f in required_files if (extract_path / f).exists()]
            if len(existing_files) == len(required_files):
                logger.info(f"✓ Dataset {year}q{quarter} already exists and is complete")
                return True

        return False

    def _get_dataset_status(self, year: int, quarter: int) -> Optional[dict]:
        """Get dataset status from database"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute("""
                SELECT * FROM datasets
                WHERE year = %s AND quarter = %s
            """, (year, quarter))

            result = cursor.fetchone()
            cursor.close()
            conn.close()

            return dict(result) if result else None

        except Exception as e:
            logger.error(f"Error getting dataset status: {e}")
            return None

    def _update_dataset_status(self, year: int, quarter: int, status_updates: dict):
        """Update dataset status in database"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            # Check if record exists
            cursor.execute("""
                SELECT id FROM datasets
                WHERE year = %s AND quarter = %s
            """, (year, quarter))

            exists = cursor.fetchone()

            if exists:
                # Update existing record
                set_clause = ', '.join([f"{k} = %s" for k in status_updates.keys()])
                values = list(status_updates.values()) + [year, quarter]

                cursor.execute(f"""
                    UPDATE datasets
                    SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                    WHERE year = %s AND quarter = %s
                """, values)
            else:
                # Insert new record
                columns = ['year', 'quarter'] + list(status_updates.keys())
                placeholders = ', '.join(['%s'] * len(columns))
                values = [year, quarter] + list(status_updates.values())

                cursor.execute(f"""
                    INSERT INTO datasets ({', '.join(columns)})
                    VALUES ({placeholders})
                """, values)

            conn.commit()
            cursor.close()
            conn.close()

        except Exception as e:
            logger.error(f"Error updating dataset status: {e}")

    def download_quarter(self, year: int, quarter: int, force: bool = False) -> DownloadResult:
        """
        Download and extract a single quarter dataset

        Args:
            year: Year (e.g., 2024)
            quarter: Quarter (1-4)
            force: Force redownload even if exists

        Returns:
            DownloadResult with status and metrics
        """
        start_time = time.time()
        result = DownloadResult(year=year, quarter=quarter, success=False)

        logger.info(f"{'='*60}")
        logger.info(f"Downloading {year}Q{quarter}")
        logger.info(f"{'='*60}")

        # Check if already exists
        if not force and self._check_dataset_exists(year, quarter):
            if self.processing.skip_existing:
                result.success = True
                return result

        # Update database - download starting
        self._update_dataset_status(year, quarter, {
            'download_status': 'downloading',
            'download_started_at': datetime.utcnow()
        })

        try:
            zip_path, extract_path = self._get_quarter_paths(year, quarter)
            url = self._get_quarter_url(year, quarter)

            # Create directories
            zip_path.parent.mkdir(parents=True, exist_ok=True)
            extract_path.mkdir(parents=True, exist_ok=True)

            # Download ZIP file
            logger.info(f"Downloading from: {url}")

            self._rate_limit_wait()
            response = requests.get(url, headers=self.headers, stream=True, timeout=300)
            response.raise_for_status()

            # Get file size
            total_size = int(response.headers.get('content-length', 0))
            total_size_mb = total_size / (1024 * 1024)

            logger.info(f"File size: {total_size_mb:.2f} MB")

            # Download with progress
            downloaded = 0
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        # Progress logging (every 10MB)
                        if downloaded % (10 * 1024 * 1024) < 8192:
                            progress = (downloaded / total_size) * 100 if total_size else 0
                            logger.info(f"Progress: {progress:.1f}% ({downloaded/(1024*1024):.1f} MB)")

            result.zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
            logger.info(f"✓ Download complete: {result.zip_size_mb:.2f} MB")

            # Extract ZIP file
            logger.info("Extracting files...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
                result.extracted_files = len(zip_ref.namelist())

            logger.info(f"✓ Extracted {result.extracted_files} files to: {extract_path}")

            # Verify required files
            required_files = ['sub.txt', 'num.txt', 'tag.txt', 'pre.txt']
            missing_files = [f for f in required_files if not (extract_path / f).exists()]

            if missing_files:
                raise Exception(f"Missing required files: {missing_files}")

            logger.info("✓ All required files present")

            # Success
            result.success = True
            result.download_time_seconds = time.time() - start_time

            # Update database - download complete
            self._update_dataset_status(year, quarter, {
                'download_status': 'completed',
                'download_completed_at': datetime.utcnow(),
                'zip_file_path': str(zip_path),
                'zip_file_size_mb': result.zip_size_mb,
                'extracted_path': str(extract_path),
                'download_error': None
            })

            logger.info(f"✅ {year}Q{quarter} downloaded successfully in {result.download_time_seconds:.1f}s")

        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP error {e.response.status_code}: {e}"
            logger.error(f"❌ Download failed: {error_msg}")
            result.error = error_msg

            # Update database - download failed
            self._update_dataset_status(year, quarter, {
                'download_status': 'failed',
                'download_error': error_msg
            })

        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Download failed: {error_msg}")
            result.error = error_msg

            # Update database - download failed
            self._update_dataset_status(year, quarter, {
                'download_status': 'failed',
                'download_error': error_msg
            })

        return result

    def download_range(self, start_year: int, start_quarter: int,
                      end_year: int, end_quarter: int,
                      concurrent: bool = True) -> List[DownloadResult]:
        """
        Download a range of quarters

        Args:
            start_year: Starting year
            start_quarter: Starting quarter (1-4)
            end_year: Ending year
            end_quarter: Ending quarter (1-4)
            concurrent: Use concurrent downloads

        Returns:
            List of DownloadResults
        """
        # Generate list of quarters
        quarters = []
        year, quarter = start_year, start_quarter

        while (year < end_year) or (year == end_year and quarter <= end_quarter):
            quarters.append((year, quarter))
            quarter += 1
            if quarter > 4:
                quarter = 1
                year += 1

        logger.info(f"\n{'='*60}")
        logger.info(f"BULK DOWNLOAD: {len(quarters)} quarters")
        logger.info(f"From {start_year}Q{start_quarter} to {end_year}Q{end_quarter}")
        logger.info(f"Concurrent downloads: {concurrent}")
        logger.info(f"{'='*60}\n")

        results = []

        if concurrent:
            # Concurrent downloads
            max_workers = min(self.processing.concurrent_downloads, len(quarters))

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_quarter = {
                    executor.submit(self.download_quarter, year, quarter): (year, quarter)
                    for year, quarter in quarters
                }

                for future in as_completed(future_to_quarter):
                    year, quarter = future_to_quarter[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Error downloading {year}Q{quarter}: {e}")
                        results.append(DownloadResult(
                            year=year, quarter=quarter,
                            success=False, error=str(e)
                        ))
        else:
            # Sequential downloads
            for year, quarter in quarters:
                result = self.download_quarter(year, quarter)
                results.append(result)

        return results

    def download_all_historical(self, concurrent: bool = True) -> List[DownloadResult]:
        """
        Download all available historical datasets
        Uses START_YEAR and END_YEAR from config

        Returns:
            List of DownloadResults
        """
        start_year = self.processing.start_year
        end_year = self.processing.end_year
        current_quarter = datetime.now().month // 3  # Approximate current quarter

        logger.info(f"\n{'#'*60}")
        logger.info(f"DOWNLOADING ALL HISTORICAL SEC DATASETS")
        logger.info(f"Year range: {start_year} - {end_year}")
        logger.info(f"{'#'*60}\n")

        return self.download_range(
            start_year, 1,
            end_year, 4,  # Download all 4 quarters (will skip if doesn't exist)
            concurrent=concurrent
        )

    def print_summary(self, results: List[DownloadResult]):
        """Print summary of download results"""
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        total_size_mb = sum(r.zip_size_mb for r in successful)
        total_time = sum(r.download_time_seconds for r in successful)

        print("\n" + "="*60)
        print("DOWNLOAD SUMMARY")
        print("="*60)
        print(f"Total datasets: {len(results)}")
        print(f"✅ Successful: {len(successful)}")
        print(f"❌ Failed: {len(failed)}")
        print(f"Total downloaded: {total_size_mb:.2f} MB")
        print(f"Total time: {total_time:.1f} seconds")

        if failed:
            print("\nFailed downloads:")
            for r in failed:
                print(f"  - {r.year}Q{r.quarter}: {r.error}")

        print("="*60 + "\n")


def main():
    """Main execution with CLI"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Download SEC financial statement datasets in bulk'
    )

    parser.add_argument(
        '--year', type=int,
        help='Download specific year (all 4 quarters)'
    )
    parser.add_argument(
        '--quarter', type=int, choices=[1, 2, 3, 4],
        help='Download specific quarter (requires --year)'
    )
    parser.add_argument(
        '--range', nargs=4, type=int, metavar=('START_YEAR', 'START_Q', 'END_YEAR', 'END_Q'),
        help='Download range: START_YEAR START_Q END_YEAR END_Q'
    )
    parser.add_argument(
        '--all', action='store_true',
        help='Download all historical datasets (2009-2024)'
    )
    parser.add_argument(
        '--sequential', action='store_true',
        help='Download sequentially instead of concurrently'
    )
    parser.add_argument(
        '--force', action='store_true',
        help='Force redownload even if exists'
    )

    args = parser.parse_args()

    downloader = BulkDatasetDownloader()
    results = []

    if args.year and args.quarter:
        # Single quarter
        result = downloader.download_quarter(args.year, args.quarter, force=args.force)
        results = [result]

    elif args.year:
        # Whole year
        results = downloader.download_range(
            args.year, 1, args.year, 4,
            concurrent=not args.sequential
        )

    elif args.range:
        # Range
        start_year, start_q, end_year, end_q = args.range
        results = downloader.download_range(
            start_year, start_q, end_year, end_q,
            concurrent=not args.sequential
        )

    elif args.all:
        # All historical
        results = downloader.download_all_historical(
            concurrent=not args.sequential
        )

    else:
        parser.print_help()
        return

    # Print summary
    downloader.print_summary(results)


if __name__ == "__main__":
    main()
