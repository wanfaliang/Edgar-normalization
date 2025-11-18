"""
Filing Export Tool
==================
Export SEC financial statements to formatted Excel files

This production tool queries the filing database and exports reconstructed
financial statements to Excel with multi-period comparative data.

Usage Examples:
    # Export by ADSH (accession number)
    python export_filing.py --adsh 0001018724-24-000161 --output output/amazon_q3_2024.xlsx

    # Export by company and form type
    python export_filing.py --company "Amazon" --form 10-Q --year 2024 --quarter 3

    # Export by CIK
    python export_filing.py --cik 1018724 --form 10-K --year 2023

    # Batch export all 10-K filings for a company
    python export_filing.py --company "Apple" --form 10-K --all-years

Author: Finexus Team
Date: November 2025
"""

import sys
import argparse
from pathlib import Path
from typing import Optional, Dict, List
import psycopg2
from psycopg2.extras import RealDictCursor

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import config
from statement_reconstructor import StatementReconstructor
from excel_exporter import ExcelExporter


class FilingExporter:
    """
    Export SEC filings to Excel with multi-period financial statements

    This class handles:
    - Database queries to find filings
    - Statement reconstruction for all 5 statement types
    - Excel export with proper formatting
    """

    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize the exporter

        Args:
            output_dir: Directory for Excel output files (default: output/filings)
        """
        # Use project root for default output directory
        project_root = Path(__file__).resolve().parent.parent
        self.output_dir = output_dir or (project_root / 'output' / 'filings')
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Database connection
        self.conn = psycopg2.connect(config.get_db_connection())
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)

    def __del__(self):
        """Cleanup database connection"""
        if hasattr(self, 'cur'):
            self.cur.close()
        if hasattr(self, 'conn'):
            self.conn.close()

    def find_filing_by_adsh(self, adsh: str) -> Optional[Dict]:
        """
        Find filing by accession number

        Args:
            adsh: Accession number (e.g., '0001018724-24-000161')

        Returns:
            Dict with filing info or None if not found
        """
        self.cur.execute("""
            SELECT
                f.adsh, f.cik, f.form_type, f.filed_date, f.period_end_date,
                f.fiscal_year, f.fiscal_period, f.source_year, f.source_quarter,
                c.company_name
            FROM filings f
            JOIN companies c ON f.cik = c.cik
            WHERE f.adsh = %s
        """, (adsh,))

        return self.cur.fetchone()

    def find_filings_by_company(
        self,
        ticker: Optional[str] = None,
        company_search: Optional[str] = None,
        cik: Optional[str] = None,
        form_type: Optional[str] = None,
        year: Optional[int] = None,
        quarter: Optional[int] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Find filings by company and criteria

        Args:
            ticker: Stock ticker symbol (e.g., AMZN, AAPL)
            company_search: Company name search string
            cik: Company CIK
            form_type: Form type (10-Q, 10-K, etc.)
            year: Fiscal year
            quarter: Fiscal quarter (1-4)
            limit: Maximum number of results

        Returns:
            List of filing dicts
        """
        # Build query
        conditions = []
        params = []

        if ticker:
            conditions.append("c.ticker = %s")
            params.append(ticker.upper())  # Tickers are uppercase

        if company_search:
            conditions.append("c.company_name ILIKE %s")
            params.append(f'%{company_search}%')

        if cik:
            conditions.append("f.cik = %s")
            params.append(cik)

        if form_type:
            conditions.append("f.form_type = %s")
            params.append(form_type)

        if year:
            conditions.append("f.fiscal_year = %s")
            params.append(year)

        if quarter:
            conditions.append("f.fiscal_period = %s")
            params.append(f'Q{quarter}')

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            SELECT
                f.adsh, f.cik, f.form_type, f.filed_date, f.period_end_date,
                f.fiscal_year, f.fiscal_period, f.source_year, f.source_quarter,
                c.company_name
            FROM filings f
            JOIN companies c ON f.cik = c.cik
            WHERE {where_clause}
            ORDER BY f.filed_date DESC
            LIMIT %s
        """

        params.append(limit)

        self.cur.execute(query, params)
        return self.cur.fetchall()

    def export_filing(
        self,
        adsh: str,
        output_path: Optional[Path] = None,
        verbose: bool = True
    ) -> Dict:
        """
        Export a single filing to Excel

        Args:
            adsh: Accession number
            output_path: Custom output path (optional)
            verbose: Print progress messages

        Returns:
            Dict with export results and metadata
        """
        if verbose:
            print(f"\n{'='*70}")
            print(f"EXPORTING FILING: {adsh}")
            print(f"{'='*70}")

        # Step 1: Get filing metadata from database
        filing = self.find_filing_by_adsh(adsh)

        if not filing:
            return {
                'success': False,
                'error': f"Filing {adsh} not found in database"
            }

        if verbose:
            print(f"\n📄 Filing Information:")
            print(f"   Company: {filing['company_name']}")
            print(f"   CIK: {filing['cik']}")
            print(f"   Form: {filing['form_type']}")
            print(f"   Period: {filing['period_end_date']} (FY{filing['fiscal_year']}{filing['fiscal_period']})")
            print(f"   Filed: {filing['filed_date']}")
            print(f"   Dataset: {filing['source_year']}Q{filing['source_quarter']}")

        # Step 2: Initialize reconstructor with correct dataset
        reconstructor = StatementReconstructor(
            year=filing['source_year'],
            quarter=filing['source_quarter']
        )

        # Step 3: Reconstruct all statement types
        statement_types = ['BS', 'IS', 'CF', 'CI', 'EQ']
        results = {}

        if verbose:
            print(f"\n📊 Reconstructing statements...")

        for stmt_type in statement_types:
            try:
                result = reconstructor.reconstruct_statement_multi_period(
                    cik=filing['cik'],
                    adsh=adsh,
                    stmt_type=stmt_type
                )

                if result and result.get('line_items'):
                    periods_count = len(result.get('periods', []))
                    items_count = len(result['line_items'])

                    if verbose:
                        print(f"   ✅ {stmt_type}: {items_count} line items × {periods_count} periods")

                    results[stmt_type] = result
                else:
                    if verbose:
                        print(f"   ⚠️  {stmt_type}: No data found")

            except Exception as e:
                if verbose:
                    print(f"   ❌ {stmt_type}: Error - {e}")

        if not results:
            return {
                'success': False,
                'error': 'No statements could be reconstructed'
            }

        # Step 4: Generate output filename if not provided
        if output_path is None:
            # Clean company name for filename
            clean_name = filing['company_name'].replace('/', '_').replace('\\', '_').replace(',', '')
            clean_name = ''.join(c for c in clean_name if c.isalnum() or c in ' _-')[:50]
            clean_name = clean_name.strip()

            filename = f"{clean_name}_{filing['form_type']}_{filing['fiscal_year']}{filing['fiscal_period']}.xlsx"
            output_path = self.output_dir / filename

        # Step 5: Export to Excel
        if verbose:
            print(f"\n📁 Exporting to Excel...")
            print(f"   Output: {output_path}")

        exporter = ExcelExporter()

        try:
            # Add each statement
            for stmt_type, result in results.items():
                exporter.add_statement(stmt_type, result)

            # Export
            exporter.export(
                filepath=str(output_path),
                company_name=filing['company_name'],
                period=f"{filing['fiscal_year']}{filing['fiscal_period']}"
            )

            if verbose:
                print(f"   ✅ Export complete!")
                print(f"   File size: {output_path.stat().st_size / 1024:.1f} KB")

        except Exception as e:
            return {
                'success': False,
                'error': f'Export failed: {e}'
            }

        # Success!
        if verbose:
            print(f"\n{'='*70}")
            print(f"✅ EXPORT SUCCESSFUL")
            print(f"{'='*70}")

        return {
            'success': True,
            'output_path': str(output_path),
            'filing': filing,
            'statements': {
                stmt_type: {
                    'line_items': len(result['line_items']),
                    'periods': len(result.get('periods', []))
                }
                for stmt_type, result in results.items()
            }
        }

    def export_multiple(
        self,
        filings: List[Dict],
        verbose: bool = True
    ) -> List[Dict]:
        """
        Export multiple filings to Excel

        Args:
            filings: List of filing dicts (from find_filings_by_company)
            verbose: Print progress messages

        Returns:
            List of export result dicts
        """
        results = []

        if verbose:
            print(f"\n{'='*70}")
            print(f"BATCH EXPORT: {len(filings)} filings")
            print(f"{'='*70}")

        for i, filing in enumerate(filings, 1):
            if verbose:
                print(f"\n[{i}/{len(filings)}] Processing {filing['adsh']}...")

            result = self.export_filing(
                adsh=filing['adsh'],
                verbose=False  # Suppress individual verbose output in batch mode
            )

            if result['success']:
                if verbose:
                    print(f"   ✅ {result['output_path']}")
            else:
                if verbose:
                    print(f"   ❌ {result['error']}")

            results.append(result)

        # Summary
        if verbose:
            successful = sum(1 for r in results if r['success'])
            print(f"\n{'='*70}")
            print(f"BATCH COMPLETE: {successful}/{len(filings)} successful")
            print(f"{'='*70}")

        return results


def main():
    """Command-line interface"""
    parser = argparse.ArgumentParser(
        description='Export SEC filings to Excel',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export by ADSH
  python export_filing.py --adsh 0001018724-24-000161

  # Export by ticker (easiest!)
  python export_filing.py --ticker AMZN --form 10-Q --year 2024 --quarter 3

  # Export by company name
  python export_filing.py --company "Amazon" --form 10-Q --year 2024

  # Export by CIK
  python export_filing.py --cik 1018724 --form 10-K --year 2023

  # Export all 10-K filings for a ticker
  python export_filing.py --ticker AAPL --form 10-K --all

  # Custom output location
  python export_filing.py --ticker MSFT --form 10-Q --year 2024 --quarter 2 --output msft_q2.xlsx
        """
    )

    # Filing identification
    parser.add_argument('--adsh', help='Accession number (e.g., 0001018724-24-000161)')
    parser.add_argument('--ticker', help='Stock ticker symbol (e.g., AMZN, AAPL, MSFT)')
    parser.add_argument('--company', help='Company name (partial match)')
    parser.add_argument('--cik', help='Company CIK')
    parser.add_argument('--form', help='Form type (10-Q, 10-K, etc.)')
    parser.add_argument('--year', type=int, help='Fiscal year')
    parser.add_argument('--quarter', type=int, choices=[1, 2, 3, 4], help='Fiscal quarter')

    # Export options
    parser.add_argument('--output', help='Output file path (for single export)')
    parser.add_argument('--output-dir', help='Output directory (default: output/filings at project root)')
    parser.add_argument('--all', action='store_true', help='Export all matching filings')
    parser.add_argument('--limit', type=int, default=10, help='Maximum filings to export (default: 10)')
    parser.add_argument('--quiet', action='store_true', help='Suppress progress messages')

    args = parser.parse_args()

    # Validation
    if not args.adsh and not args.ticker and not args.company and not args.cik:
        parser.error("Must specify --adsh, --ticker, --company, or --cik")

    # Initialize exporter
    output_dir = Path(args.output_dir) if args.output_dir else None
    exporter = FilingExporter(output_dir=output_dir)
    verbose = not args.quiet

    # Export by ADSH (single filing)
    if args.adsh:
        output_path = Path(args.output) if args.output else None
        result = exporter.export_filing(args.adsh, output_path=output_path, verbose=verbose)
        sys.exit(0 if result['success'] else 1)

    # Export by search criteria
    filings = exporter.find_filings_by_company(
        ticker=args.ticker,
        company_search=args.company,
        cik=args.cik,
        form_type=args.form,
        year=args.year,
        quarter=args.quarter,
        limit=args.limit if not args.all else 1000
    )

    if not filings:
        print("❌ No filings found matching criteria")
        sys.exit(1)

    if verbose:
        print(f"\n✅ Found {len(filings)} matching filings")
        for i, filing in enumerate(filings[:5], 1):
            print(f"   {i}. {filing['company_name']} | {filing['form_type']} | {filing['fiscal_year']}{filing['fiscal_period']} | {filing['filed_date']}")
        if len(filings) > 5:
            print(f"   ... and {len(filings) - 5} more")

    # Export single or multiple
    if len(filings) == 1 or (not args.all and args.output):
        # Single export
        filing = filings[0]
        output_path = Path(args.output) if args.output else None
        result = exporter.export_filing(filing['adsh'], output_path=output_path, verbose=verbose)
        sys.exit(0 if result['success'] else 1)

    elif args.all or len(filings) > 1:
        # Batch export
        results = exporter.export_multiple(filings, verbose=verbose)
        successful = sum(1 for r in results if r['success'])
        sys.exit(0 if successful == len(results) else 1)

    else:
        print("❌ No filings to export")
        sys.exit(1)


if __name__ == '__main__':
    main()
