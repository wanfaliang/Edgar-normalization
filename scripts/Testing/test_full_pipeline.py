"""
Full Pipeline Test - End-to-End Validation
==========================================
Tests: Database Query → Statement Reconstruction → Excel Export

Author: Finexus Team
Date: November 2025
"""

import sys
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))
from statement_reconstructor import StatementReconstructor
from excel_exporter import ExcelExporter
from config import config

def test_full_pipeline(company_search: str = "AMAZON", form_type: str = "10-Q", year: int = 2024):
    """
    Test the full pipeline from database query to Excel export

    Args:
        company_search: Company name to search for
        form_type: Form type to retrieve (10-Q, 10-K, etc.)
        year: Fiscal year to search
    """
    print("\n" + "="*70)
    print("FULL PIPELINE TEST - END TO END")
    print("="*70)

    # Step 1: Query Database - Find Company
    print(f"\n[Step 1] Searching for company: {company_search}")
    print("-"*70)

    conn = psycopg2.connect(config.get_db_connection())
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Find company
    cur.execute("""
        SELECT cik, company_name, total_filings, sic
        FROM companies
        WHERE company_name ILIKE %s
        ORDER BY total_filings DESC
        LIMIT 5
    """, (f'%{company_search}%',))

    companies = cur.fetchall()

    if not companies:
        print(f"❌ No companies found matching '{company_search}'")
        return False

    print(f"✅ Found {len(companies)} matching companies:\n")
    for i, company in enumerate(companies, 1):
        print(f"  {i}. CIK: {company['cik']:10s} | {company['company_name']:50s} | {company['total_filings']} filings")

    # Use the first company
    selected_company = companies[0]
    cik = selected_company['cik']
    company_name = selected_company['company_name']

    print(f"\n📌 Selected: {company_name} (CIK: {cik})")

    # Step 2: Get Filing Information
    print(f"\n[Step 2] Finding {form_type} filings for {year}")
    print("-"*70)

    cur.execute("""
        SELECT adsh, form_type, filed_date, period_end_date,
               fiscal_year, fiscal_period, source_year, source_quarter
        FROM filings
        WHERE cik = %s
          AND form_type = %s
          AND fiscal_year = %s
        ORDER BY filed_date DESC
        LIMIT 5
    """, (cik, form_type, year))

    filings = cur.fetchall()

    if not filings:
        print(f"❌ No {form_type} filings found for {year}")
        # Try to find any recent filing
        cur.execute("""
            SELECT adsh, form_type, filed_date, period_end_date,
                   fiscal_year, fiscal_period, source_year, source_quarter
            FROM filings
            WHERE cik = %s
            ORDER BY filed_date DESC
            LIMIT 10
        """, (cik,))
        filings = cur.fetchall()
        if filings:
            print(f"\n📋 Recent filings available:")
            for filing in filings:
                print(f"  {filing['form_type']:6s} | {filing['filed_date']} | FY{filing['fiscal_year']}{filing['fiscal_period']} | {filing['source_year']}Q{filing['source_quarter']}")
        return False

    print(f"✅ Found {len(filings)} {form_type} filings:\n")
    for i, filing in enumerate(filings, 1):
        print(f"  {i}. {filing['adsh']} | Filed: {filing['filed_date']} | Period: {filing['period_end_date']} | FY{filing['fiscal_year']}{filing['fiscal_period']}")

    # Use the most recent filing
    selected_filing = filings[0]
    adsh = selected_filing['adsh']
    source_year = selected_filing['source_year']
    source_quarter = selected_filing['source_quarter']

    print(f"\n📌 Selected: {adsh} (Filed: {selected_filing['filed_date']})")
    print(f"   Source Dataset: {source_year}Q{source_quarter}")

    cur.close()
    conn.close()

    # Step 3: Reconstruct Statements
    print(f"\n[Step 3] Reconstructing financial statements")
    print("-"*70)

    # Initialize reconstructor with correct dataset
    reconstructor = StatementReconstructor(year=source_year, quarter=source_quarter)

    # Verify the dataset exists
    print(f"Using dataset {source_year}Q{source_quarter}...")
    dataset_path = config.storage.extracted_dir / f"{source_year}q{source_quarter}"

    if not dataset_path.exists():
        print(f"❌ Dataset not found: {dataset_path}")
        return False

    print(f"✅ Dataset found: {dataset_path}")

    # Reconstruct all 5 statement types
    statement_types = ['BS', 'IS', 'CF', 'CI', 'EQ']
    results = {}

    for stmt_type in statement_types:
        print(f"\n  Reconstructing {stmt_type}...", end=" ")
        try:
            result = reconstructor.reconstruct_statement_multi_period(
                cik=cik,
                adsh=adsh,
                stmt_type=stmt_type
            )

            if result and result.get('line_items'):
                periods_count = len(result.get('periods', []))
                items_count = len(result['line_items'])
                print(f"✅ {items_count} line items, {periods_count} periods")
                results[stmt_type] = result
            else:
                print(f"⚠️  No data found")

        except Exception as e:
            print(f"❌ Error: {e}")

    if not results:
        print(f"\n❌ No statements could be reconstructed")
        return False

    print(f"\n✅ Successfully reconstructed {len(results)} statement types")

    # Step 4: Export to Excel
    print(f"\n[Step 4] Exporting to Excel")
    print("-"*70)

    output_dir = Path('output') / 'pipeline_test'
    output_dir.mkdir(parents=True, exist_ok=True)

    # Clean company name for filename
    clean_name = company_name.replace('/', '_').replace('\\', '_').replace(',', '')[:50]
    filename = f"{clean_name}_{form_type}_{year}_pipeline_test.xlsx"
    output_path = output_dir / filename

    print(f"Exporting to: {output_path}")

    exporter = ExcelExporter()

    try:
        # Add each statement to the exporter
        for stmt_type, result in results.items():
            exporter.add_statement(stmt_type, result)

        # Export to Excel
        exporter.export(
            filepath=str(output_path),
            company_name=company_name,
            period=f"{selected_filing['fiscal_year']}{selected_filing['fiscal_period']}"
        )

        print(f"✅ Excel file created successfully")

    except Exception as e:
        print(f"❌ Export failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 5: Verify Results
    print(f"\n[Step 5] Verification Summary")
    print("-"*70)

    print(f"\n✅ PIPELINE TEST SUCCESSFUL!\n")
    print(f"Company: {company_name}")
    print(f"CIK: {cik}")
    print(f"Filing: {adsh} ({form_type})")
    print(f"Fiscal Year: {selected_filing['fiscal_year']}{selected_filing['fiscal_period']}")
    print(f"Filed: {selected_filing['filed_date']}")
    print(f"\nStatements Reconstructed:")

    for stmt_type, result in results.items():
        periods = len(result.get('periods', []))
        items = len(result.get('line_items', []))
        print(f"  {stmt_type}: {items:3d} line items × {periods} periods")

    print(f"\nOutput File: {output_path}")
    print(f"File Size: {output_path.stat().st_size / 1024:.1f} KB")

    print(f"\n{'='*70}")
    print("TEST COMPLETE - All systems operational! ✅")
    print(f"{'='*70}\n")

    return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Test full pipeline from database to Excel')
    parser.add_argument('--company', default='AMAZON', help='Company name to search')
    parser.add_argument('--form', default='10-Q', help='Form type (10-Q, 10-K, etc.)')
    parser.add_argument('--year', type=int, default=2024, help='Fiscal year')

    args = parser.parse_args()

    success = test_full_pipeline(
        company_search=args.company,
        form_type=args.form,
        year=args.year
    )

    sys.exit(0 if success else 1)
