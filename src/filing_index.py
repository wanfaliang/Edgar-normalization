"""
SEC Filing Index - Database Indexer
====================================
Indexes downloaded SEC datasets (sub.txt) into PostgreSQL database.
Populates companies and filings tables for fast search and discovery.

Author: Finexus Team
Date: November 2025
"""

import sys
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))
from config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FilingIndexer:
    """
    Index SEC filings from downloaded datasets into PostgreSQL

    Features:
    - Read sub.txt from extracted datasets
    - Extract company and filing metadata
    - Populate companies and filings tables
    - Incremental updates (skip already indexed)
    - Update dataset processing status
    """

    def __init__(self):
        self.config = config
        self.storage = config.storage
        self.db_conn_string = config.get_db_connection()

    def _get_db_connection(self):
        """Get database connection"""
        return psycopg2.connect(self.db_conn_string)

    def _get_dataset_path(self, year: int, quarter: int) -> Path:
        """Get path to extracted dataset"""
        return self.storage.extracted_dir / f"{year}q{quarter}"

    def _check_dataset_indexed(self, year: int, quarter: int) -> bool:
        """Check if dataset has already been indexed"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT processing_status
                FROM datasets
                WHERE year = %s AND quarter = %s
            """, (year, quarter))

            result = cursor.fetchone()
            cursor.close()
            conn.close()

            if result and result[0] == 'completed':
                logger.info(f"✓ Dataset {year}Q{quarter} already indexed")
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking dataset status: {e}")
            return False

    def _update_dataset_status(self, year: int, quarter: int, status_updates: dict):
        """Update dataset processing status"""
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

    def index_quarter(self, year: int, quarter: int, force: bool = False) -> Dict:
        """
        Index a single quarter's filings into database

        Args:
            year: Year (e.g., 2024)
            quarter: Quarter (1-4)
            force: Force reindex even if already done

        Returns:
            Dict with indexing statistics
        """
        logger.info(f"{'='*60}")
        logger.info(f"Indexing {year}Q{quarter}")
        logger.info(f"{'='*60}")

        result = {
            'success': False,
            'year': year,
            'quarter': quarter,
            'companies_added': 0,
            'companies_updated': 0,
            'filings_added': 0,
            'error': None
        }

        # Check if already indexed
        if not force and self._check_dataset_indexed(year, quarter):
            if self.config.processing.skip_existing:
                result['success'] = True
                return result

        # Update status - processing starting
        self._update_dataset_status(year, quarter, {
            'processing_status': 'processing',
            'processing_started_at': datetime.now()
        })

        try:
            # Get dataset path
            dataset_path = self._get_dataset_path(year, quarter)
            sub_file = dataset_path / 'sub.txt'

            if not sub_file.exists():
                raise FileNotFoundError(f"sub.txt not found at {sub_file}")

            # Load sub.txt
            logger.info(f"Loading sub.txt from {dataset_path}")
            sub_df = pd.read_csv(sub_file, sep='\t', dtype=str, low_memory=False)
            logger.info(f"Loaded {len(sub_df):,} submissions")

            # Index companies
            logger.info("Indexing companies...")
            companies_stats = self._index_companies(sub_df, year, quarter)
            result['companies_added'] = companies_stats['added']
            result['companies_updated'] = companies_stats['updated']

            # Index filings
            logger.info("Indexing filings...")
            filings_stats = self._index_filings(sub_df, year, quarter)
            result['filings_added'] = filings_stats['added']

            # Update dataset status - processing complete
            self._update_dataset_status(year, quarter, {
                'processing_status': 'completed',
                'processing_completed_at': datetime.now(),
                'total_submissions': len(sub_df),
                'total_companies': sub_df['cik'].nunique(),
                'processing_error': None
            })

            result['success'] = True

            logger.info(f"✅ {year}Q{quarter} indexed successfully")
            logger.info(f"   Companies: {result['companies_added']} added, {result['companies_updated']} updated")
            logger.info(f"   Filings: {result['filings_added']} added")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Indexing failed: {error_msg}")
            result['error'] = error_msg

            # Update dataset status - processing failed
            self._update_dataset_status(year, quarter, {
                'processing_status': 'failed',
                'processing_error': error_msg
            })

        return result

    def _index_companies(self, sub_df: pd.DataFrame, year: int, quarter: int) -> Dict:
        """Index companies from sub.txt into companies table"""
        stats = {'added': 0, 'updated': 0}

        # Group by CIK to get company-level aggregates
        company_groups = sub_df.groupby('cik').agg({
            'name': 'first',  # Company name (take first)
            'sic': 'first',   # SIC code
            'filed': ['min', 'max', 'count'],  # First, last, count of filings
            'form': lambda x: list(x.unique())  # Unique form types
        }).reset_index()

        # Flatten column names
        company_groups.columns = ['cik', 'company_name', 'sic', 'first_filing', 'last_filing', 'filing_count', 'forms_filed']

        conn = self._get_db_connection()
        cursor = conn.cursor()

        for _, company in company_groups.iterrows():
            cik = company['cik']
            company_name = company['company_name']
            sic = company['sic']
            first_filing = pd.to_datetime(company['first_filing']).date() if pd.notna(company['first_filing']) else None
            last_filing = pd.to_datetime(company['last_filing']).date() if pd.notna(company['last_filing']) else None
            forms_filed = company['forms_filed'] if isinstance(company['forms_filed'], list) else []

            try:
                # Check if company exists
                cursor.execute("SELECT cik, total_filings FROM companies WHERE cik = %s", (cik,))
                existing = cursor.fetchone()

                if existing:
                    # Update existing company
                    cursor.execute("""
                        UPDATE companies
                        SET company_name = COALESCE(%s, company_name),
                            sic = COALESCE(%s, sic),
                            first_filing_date = LEAST(COALESCE(first_filing_date, %s), %s),
                            last_filing_date = GREATEST(COALESCE(last_filing_date, %s), %s),
                            total_filings = total_filings + %s,
                            forms_filed = ARRAY(SELECT DISTINCT unnest(forms_filed || %s::text[])),
                            updated_at = CURRENT_TIMESTAMP
                        WHERE cik = %s
                    """, (company_name, sic, first_filing, first_filing,
                          last_filing, last_filing, company['filing_count'],
                          forms_filed, cik))
                    stats['updated'] += 1
                else:
                    # Insert new company
                    cursor.execute("""
                        INSERT INTO companies (cik, company_name, sic, first_filing_date,
                                             last_filing_date, total_filings, forms_filed)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (cik, company_name, sic, first_filing, last_filing,
                          company['filing_count'], forms_filed))
                    stats['added'] += 1

            except Exception as e:
                logger.error(f"Error indexing company {cik}: {e}")
                conn.rollback()
                continue

        conn.commit()
        cursor.close()
        conn.close()

        logger.info(f"   Companies: {stats['added']} added, {stats['updated']} updated")
        return stats

    def _index_filings(self, sub_df: pd.DataFrame, year: int, quarter: int) -> Dict:
        """Index filings from sub.txt into filings table"""
        stats = {'added': 0, 'skipped': 0}

        conn = self._get_db_connection()
        cursor = conn.cursor()

        # Prepare filing records
        filing_records = []

        for _, row in sub_df.iterrows():
            # Convert dates
            filed_date = pd.to_datetime(row.get('filed')).date() if pd.notna(row.get('filed')) else None
            period_date = pd.to_datetime(row.get('period')).date() if pd.notna(row.get('period')) else None
            accepted = pd.to_datetime(row.get('accepted')) if pd.notna(row.get('accepted')) else None

            # Extract fiscal info
            fiscal_year = int(row['fy']) if pd.notna(row.get('fy')) else None
            fiscal_period = row.get('fp')

            # Additional co-registrants
            aciks = []
            if pd.notna(row.get('aciks')):
                aciks = [str(cik).strip() for cik in str(row['aciks']).split()]

            filing_record = (
                row['adsh'],           # adsh
                row['cik'],            # cik
                row.get('name'),       # company_name
                row.get('form'),       # form_type
                filed_date,            # filed_date
                period_date,           # period_end_date
                fiscal_year,           # fiscal_year
                fiscal_period,         # fiscal_period
                row.get('sic'),        # sic
                row.get('countryba'),  # countryba
                row.get('stprba'),     # stprba
                row.get('cityba'),     # cityba
                row.get('zipba'),      # zipba
                row.get('bas1'),       # bas1
                accepted,              # accepted_timestamp
                row.get('prevrpt') == '1' if pd.notna(row.get('prevrpt')) else None,  # prevrpt
                row.get('detail') == '1' if pd.notna(row.get('detail')) else None,    # detail
                row.get('instance'),   # instance
                int(row['nciks']) if pd.notna(row.get('nciks')) else None,  # nciks
                aciks if aciks else None,  # aciks
                year,                  # source_year
                quarter,               # source_quarter
                f"{year}q{quarter}"    # source_dataset
            )

            filing_records.append(filing_record)

        # Bulk insert filings
        logger.info(f"   Bulk inserting {len(filing_records):,} filings...")

        try:
            execute_values(cursor, """
                INSERT INTO filings (
                    adsh, cik, company_name, form_type, filed_date, period_end_date,
                    fiscal_year, fiscal_period, sic, countryba, stprba, cityba, zipba, bas1,
                    accepted_timestamp, prevrpt, detail, instance, nciks, aciks,
                    source_year, source_quarter, source_dataset
                )
                VALUES %s
                ON CONFLICT (adsh) DO NOTHING
            """, filing_records)

            stats['added'] = cursor.rowcount
            conn.commit()

        except Exception as e:
            logger.error(f"Error bulk inserting filings: {e}")
            conn.rollback()
            raise

        cursor.close()
        conn.close()

        logger.info(f"   Filings: {stats['added']} added")
        return stats

    def index_range(self, start_year: int, start_quarter: int,
                   end_year: int, end_quarter: int) -> List[Dict]:
        """Index a range of quarters"""
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
        logger.info(f"BULK INDEXING: {len(quarters)} quarters")
        logger.info(f"From {start_year}Q{start_quarter} to {end_year}Q{end_quarter}")
        logger.info(f"{'='*60}\n")

        results = []
        for year, quarter in quarters:
            result = self.index_quarter(year, quarter)
            results.append(result)

        return results

    def index_all_downloaded(self) -> List[Dict]:
        """Index all downloaded datasets"""
        logger.info(f"\n{'#'*60}")
        logger.info(f"INDEXING ALL DOWNLOADED DATASETS")
        logger.info(f"{'#'*60}\n")

        # Get list of downloaded datasets
        extracted_dir = self.storage.extracted_dir
        dataset_dirs = [d for d in extracted_dir.iterdir() if d.is_dir()]

        results = []
        for dataset_dir in sorted(dataset_dirs):
            # Parse year and quarter from directory name (e.g., "2024q2")
            try:
                name_parts = dataset_dir.name.split('q')
                if len(name_parts) == 2:
                    year = int(name_parts[0])
                    quarter = int(name_parts[1])
                    result = self.index_quarter(year, quarter)
                    results.append(result)
            except Exception as e:
                logger.error(f"Error parsing dataset directory {dataset_dir.name}: {e}")
                continue

        return results

    def print_summary(self, results: List[Dict]):
        """Print summary of indexing results"""
        successful = [r for r in results if r.get('success')]
        failed = [r for r in results if not r.get('success')]

        total_companies = sum(r.get('companies_added', 0) + r.get('companies_updated', 0) for r in successful)
        total_filings = sum(r.get('filings_added', 0) for r in successful)

        print("\n" + "="*60)
        print("INDEXING SUMMARY")
        print("="*60)
        print(f"Total datasets: {len(results)}")
        print(f"✅ Successful: {len(successful)}")
        print(f"❌ Failed: {len(failed)}")
        print(f"Companies indexed: {total_companies:,}")
        print(f"Filings indexed: {total_filings:,}")

        if failed:
            print("\nFailed indexing:")
            for r in failed:
                print(f"  - {r['year']}Q{r['quarter']}: {r.get('error')}")

        print("="*60 + "\n")


def main():
    """Main execution with CLI"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Index SEC financial statement datasets into PostgreSQL'
    )

    parser.add_argument(
        '--year', type=int,
        help='Index specific year (all 4 quarters)'
    )
    parser.add_argument(
        '--quarter', type=int, choices=[1, 2, 3, 4],
        help='Index specific quarter (requires --year)'
    )
    parser.add_argument(
        '--range', nargs=4, type=int, metavar=('START_YEAR', 'START_Q', 'END_YEAR', 'END_Q'),
        help='Index range: START_YEAR START_Q END_YEAR END_Q'
    )
    parser.add_argument(
        '--all', action='store_true',
        help='Index all downloaded datasets'
    )
    parser.add_argument(
        '--force', action='store_true',
        help='Force reindex even if already done'
    )

    args = parser.parse_args()

    indexer = FilingIndexer()
    results = []

    if args.year and args.quarter:
        # Single quarter
        result = indexer.index_quarter(args.year, args.quarter, force=args.force)
        results = [result]

    elif args.year:
        # Whole year
        results = indexer.index_range(args.year, 1, args.year, 4)

    elif args.range:
        # Range
        start_year, start_q, end_year, end_q = args.range
        results = indexer.index_range(start_year, start_q, end_year, end_q)

    elif args.all:
        # All downloaded
        results = indexer.index_all_downloaded()

    else:
        parser.print_help()
        return

    # Print summary
    indexer.print_summary(results)


if __name__ == "__main__":
    main()
