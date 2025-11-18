"""
Ticker Updater
==============
Downloads ticker symbols from SEC and updates the companies table

The SEC provides a company tickers JSON file that maps CIK to ticker symbols
and exchange information. This script downloads that data and updates our
local database.

Usage:
    python update_tickers.py              # Update all tickers
    python update_tickers.py --verify     # Verify ticker coverage
    python update_tickers.py --stats      # Show ticker statistics

Data Source:
    https://www.sec.gov/files/company_tickers.json
    https://www.sec.gov/files/company_tickers_exchange.json

Author: Finexus Team
Date: November 2025
"""

import sys
import json
import argparse
import requests
from pathlib import Path
from typing import Dict, List, Optional
import psycopg2
from psycopg2.extras import execute_batch

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import config


class TickerUpdater:
    """
    Download and update ticker symbols from SEC

    The SEC provides two ticker mapping files:
    1. company_tickers.json - Basic CIK to ticker mapping
    2. company_tickers_exchange.json - Includes exchange info (NYSE, NASDAQ, etc.)
    """

    SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
    SEC_TICKERS_EXCHANGE_URL = "https://www.sec.gov/files/company_tickers_exchange.json"

    def __init__(self):
        """Initialize the updater"""
        self.conn = psycopg2.connect(config.get_db_connection())
        self.cur = self.conn.cursor()

        # SEC requires user agent
        self.headers = {
            'User-Agent': config.sec.user_agent
        }

    def __del__(self):
        """Cleanup database connection"""
        if hasattr(self, 'cur'):
            self.cur.close()
        if hasattr(self, 'conn'):
            self.conn.close()

    def download_tickers(self, include_exchange: bool = True) -> Dict:
        """
        Download ticker data from SEC

        Args:
            include_exchange: If True, download exchange info (slower but more complete)

        Returns:
            Dict mapping CIK to ticker/exchange data
        """
        print(f"\n{'='*70}")
        print("DOWNLOADING TICKER DATA FROM SEC")
        print(f"{'='*70}\n")

        if include_exchange:
            print(f"Downloading from: {self.SEC_TICKERS_EXCHANGE_URL}")
            url = self.SEC_TICKERS_EXCHANGE_URL
        else:
            print(f"Downloading from: {self.SEC_TICKERS_URL}")
            url = self.SEC_TICKERS_URL

        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()

            data = response.json()

            print(f"✅ Downloaded successfully")
            print(f"   Records: {len(data.get('data', data)) if isinstance(data, dict) else len(data):,}")

            return data

        except Exception as e:
            print(f"❌ Download failed: {e}")
            raise

    def parse_ticker_data(self, data: Dict, include_exchange: bool = True) -> Dict[str, Dict]:
        """
        Parse SEC ticker data into CIK → {ticker, exchange} mapping

        Args:
            data: Raw JSON data from SEC
            include_exchange: Whether exchange data is included

        Returns:
            Dict: {cik: {'ticker': 'AAPL', 'exchange': 'Nasdaq'}}
        """
        print(f"\n{'='*70}")
        print("PARSING TICKER DATA")
        print(f"{'='*70}\n")

        ticker_map = {}

        if include_exchange:
            # Format: {"data": [[cik, name, ticker, exchange], ...], "fields": [...]}
            if 'data' in data:
                for row in data['data']:
                    # row format: [cik, name, ticker, exchange]
                    if len(row) >= 4:
                        cik = str(row[0])  # Store CIK as-is (no padding)
                        ticker = row[2]
                        exchange = row[3]

                        ticker_map[cik] = {
                            'ticker': ticker,
                            'exchange': exchange
                        }
            else:
                print("⚠️  Warning: Unexpected data format (no 'data' field)")

        else:
            # Format: {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
            for key, item in data.items():
                if isinstance(item, dict) and 'cik_str' in item:
                    cik = str(item['cik_str'])  # Store CIK as-is (no padding)
                    ticker = item['ticker']

                    ticker_map[cik] = {
                        'ticker': ticker,
                        'exchange': None
                    }

        print(f"✅ Parsed {len(ticker_map):,} ticker mappings")

        return ticker_map

    def update_database(self, ticker_map: Dict[str, Dict]) -> Dict:
        """
        Update companies table with ticker information

        Args:
            ticker_map: Dict mapping CIK to {ticker, exchange}

        Returns:
            Dict with update statistics
        """
        print(f"\n{'='*70}")
        print("UPDATING DATABASE")
        print(f"{'='*70}\n")

        # Prepare batch update data
        updates = []
        for cik, info in ticker_map.items():
            updates.append((
                info['ticker'],
                info.get('exchange'),
                cik
            ))

        print(f"Updating {len(updates):,} companies...")

        # Batch update using execute_batch for performance
        update_sql = """
            UPDATE companies
            SET ticker = %s,
                exchange = %s
            WHERE cik = %s
        """

        try:
            execute_batch(self.cur, update_sql, updates, page_size=1000)
            self.conn.commit()

            # Get statistics
            self.cur.execute("SELECT COUNT(*) FROM companies WHERE ticker IS NOT NULL")
            companies_with_tickers = self.cur.fetchone()[0]

            self.cur.execute("SELECT COUNT(*) FROM companies")
            total_companies = self.cur.fetchone()[0]

            print(f"✅ Database updated successfully")
            print(f"   Companies with tickers: {companies_with_tickers:,}")
            print(f"   Total companies: {total_companies:,}")
            print(f"   Coverage: {companies_with_tickers/total_companies*100:.1f}%")

            return {
                'updated': len(updates),
                'companies_with_tickers': companies_with_tickers,
                'total_companies': total_companies,
                'coverage_pct': companies_with_tickers/total_companies*100
            }

        except Exception as e:
            self.conn.rollback()
            print(f"❌ Database update failed: {e}")
            raise

    def get_statistics(self) -> Dict:
        """
        Get ticker coverage statistics

        Returns:
            Dict with statistics
        """
        print(f"\n{'='*70}")
        print("TICKER STATISTICS")
        print(f"{'='*70}\n")

        # Overall coverage
        self.cur.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(ticker) as with_ticker,
                COUNT(exchange) as with_exchange
            FROM companies
        """)
        stats = self.cur.fetchone()
        total, with_ticker, with_exchange = stats

        print(f"Total companies: {total:,}")
        print(f"Companies with ticker: {with_ticker:,} ({with_ticker/total*100:.1f}%)")
        print(f"Companies with exchange: {with_exchange:,} ({with_exchange/total*100:.1f}%)")

        # Top exchanges
        print(f"\nTop Exchanges:")
        self.cur.execute("""
            SELECT exchange, COUNT(*) as count
            FROM companies
            WHERE exchange IS NOT NULL
            GROUP BY exchange
            ORDER BY count DESC
            LIMIT 10
        """)

        for row in self.cur.fetchall():
            exchange, count = row
            print(f"  {exchange:15s}: {count:,}")

        return {
            'total': total,
            'with_ticker': with_ticker,
            'with_exchange': with_exchange,
            'coverage_pct': with_ticker/total*100
        }

    def verify_tickers(self, sample_size: int = 10):
        """
        Verify ticker mappings with sample data

        Args:
            sample_size: Number of random samples to verify
        """
        print(f"\n{'='*70}")
        print(f"VERIFYING TICKER MAPPINGS (sample size: {sample_size})")
        print(f"{'='*70}\n")

        # Get random sample
        self.cur.execute(f"""
            SELECT cik, company_name, ticker, exchange
            FROM companies
            WHERE ticker IS NOT NULL
            ORDER BY RANDOM()
            LIMIT {sample_size}
        """)

        print(f"{'CIK':<12} {'Ticker':<8} {'Exchange':<10} Company")
        print("-" * 70)

        for row in self.cur.fetchall():
            cik, name, ticker, exchange = row
            exchange = exchange or 'N/A'
            print(f"{cik:<12} {ticker:<8} {exchange:<10} {name[:40]}")

    def run(self, include_exchange: bool = True):
        """
        Main execution: Download and update all tickers

        Args:
            include_exchange: Include exchange information
        """
        # Download
        data = self.download_tickers(include_exchange=include_exchange)

        # Parse
        ticker_map = self.parse_ticker_data(data, include_exchange=include_exchange)

        # Update database
        stats = self.update_database(ticker_map)

        print(f"\n{'='*70}")
        print("✅ TICKER UPDATE COMPLETE")
        print(f"{'='*70}\n")

        return stats


def main():
    """Command-line interface"""
    parser = argparse.ArgumentParser(
        description='Update company ticker symbols from SEC',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--no-exchange', action='store_true',
                       help='Skip exchange information (faster)')
    parser.add_argument('--stats', action='store_true',
                       help='Show statistics only (no update)')
    parser.add_argument('--verify', action='store_true',
                       help='Verify ticker mappings with sample data')
    parser.add_argument('--sample-size', type=int, default=10,
                       help='Sample size for verification (default: 10)')

    args = parser.parse_args()

    updater = TickerUpdater()

    if args.stats:
        # Just show statistics
        updater.get_statistics()

    elif args.verify:
        # Verify mappings
        updater.verify_tickers(sample_size=args.sample_size)

    else:
        # Run full update
        include_exchange = not args.no_exchange
        updater.run(include_exchange=include_exchange)

        # Show verification sample
        print()
        updater.verify_tickers(sample_size=5)


if __name__ == '__main__':
    main()
