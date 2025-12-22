"""
Test Control Item Detection for 200 Random Companies
=====================================================
Tests whether we can identify total_assets and total_liabilities_and_stockholders_equity
for 200 random companies from the database.
"""
import sys
sys.path.insert(0, 'src')

import psycopg2
from psycopg2.extras import RealDictCursor
from config import config
from statement_reconstructor import StatementReconstructor
from map_financial_statements import find_bs_control_items
import traceback


def get_random_companies(n=200):
    """Get n random companies that have filings with balance sheets."""
    conn = psycopg2.connect(config.get_db_connection())
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Get companies with 10-K or 10-Q filings (one filing per company)
    cur.execute("""
        SELECT * FROM (
            SELECT DISTINCT ON (c.cik) c.cik, c.company_name, c.ticker, f.adsh, f.form_type,
                   f.source_year, f.source_quarter
            FROM companies c
            JOIN filings f ON c.cik = f.cik
            WHERE c.ticker IS NOT NULL
            AND c.ticker != ''
            AND f.form_type IN ('10-K', '10-Q')
            ORDER BY c.cik, f.filed_date DESC
        ) AS latest_filings
        ORDER BY RANDOM()
        LIMIT %s
    """, (n,))

    results = cur.fetchall()
    cur.close()
    conn.close()

    return results


def test_control_items():
    """Test control item detection for 200 random companies."""
    print("=" * 80)
    print("Testing Control Item Detection for 200 Random Companies")
    print("=" * 80)

    companies = get_random_companies(200)
    print(f"\nFetched {len(companies)} companies with filings")

    # Track results
    success_count = 0
    failed_total_assets = []
    failed_total_le = []
    failed_both = []
    error_companies = []

    for i, company in enumerate(companies):
        cik = company['cik']
        company_name = company['company_name']
        ticker = company['ticker']
        adsh = company['adsh']
        year = company['source_year']
        quarter = company['source_quarter']

        try:
            # Initialize reconstructor
            reconstructor = StatementReconstructor(year=year, quarter=quarter, use_db=True, verbose=False)

            # Reconstruct balance sheet
            bs_result = reconstructor.reconstruct_statement_multi_period(cik=cik, adsh=adsh, stmt_type='BS')

            if not bs_result or not bs_result.get('line_items'):
                error_companies.append({
                    'cik': cik,
                    'company_name': company_name,
                    'ticker': ticker,
                    'adsh': adsh,
                    'error': 'No balance sheet line items'
                })
                continue

            # Find control items
            control_lines = find_bs_control_items(bs_result['line_items'])

            has_total_assets = 'total_assets' in control_lines
            has_total_le = 'total_liabilities_and_total_equity' in control_lines

            if has_total_assets and has_total_le:
                success_count += 1
                status = "OK"
            elif not has_total_assets and not has_total_le:
                failed_both.append({
                    'cik': cik,
                    'company_name': company_name,
                    'ticker': ticker,
                    'adsh': adsh,
                    'year': year,
                    'quarter': quarter,
                    'control_lines': control_lines
                })
                status = "FAIL (both)"
            elif not has_total_assets:
                failed_total_assets.append({
                    'cik': cik,
                    'company_name': company_name,
                    'ticker': ticker,
                    'adsh': adsh,
                    'year': year,
                    'quarter': quarter,
                    'control_lines': control_lines
                })
                status = "FAIL (total_assets)"
            else:
                failed_total_le.append({
                    'cik': cik,
                    'company_name': company_name,
                    'ticker': ticker,
                    'adsh': adsh,
                    'year': year,
                    'quarter': quarter,
                    'control_lines': control_lines
                })
                status = "FAIL (total_L&E)"

            # Progress indicator
            if (i + 1) % 20 == 0:
                print(f"  Processed {i + 1}/{len(companies)}...")

        except Exception as e:
            error_companies.append({
                'cik': cik,
                'company_name': company_name,
                'ticker': ticker,
                'adsh': adsh,
                'error': str(e)
            })

    # Print results
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)

    total_tested = len(companies) - len(error_companies)
    print(f"\nTotal companies tested: {total_tested}")
    print(f"Successful (both found): {success_count} ({success_count/total_tested*100:.1f}%)")
    print(f"Failed total_assets only: {len(failed_total_assets)}")
    print(f"Failed total_L&E only: {len(failed_total_le)}")
    print(f"Failed both: {len(failed_both)}")
    print(f"Errors: {len(error_companies)}")

    # Print failed companies details
    if failed_total_assets:
        print("\n" + "-" * 80)
        print("FAILED: Missing total_assets")
        print("-" * 80)
        for f in failed_total_assets:
            print(f"\n  {f['ticker']} - {f['company_name'][:50]}")
            print(f"    CIK: {f['cik']}, ADSH: {f['adsh']}")
            print(f"    Year: {f['year']}, Quarter: {f['quarter']}")
            print(f"    Found controls: {list(f['control_lines'].keys())}")

    if failed_total_le:
        print("\n" + "-" * 80)
        print("FAILED: Missing total_liabilities_and_total_equity")
        print("-" * 80)
        for f in failed_total_le:
            print(f"\n  {f['ticker']} - {f['company_name'][:50]}")
            print(f"    CIK: {f['cik']}, ADSH: {f['adsh']}")
            print(f"    Year: {f['year']}, Quarter: {f['quarter']}")
            print(f"    Found controls: {list(f['control_lines'].keys())}")

    if failed_both:
        print("\n" + "-" * 80)
        print("FAILED: Missing both total_assets AND total_liabilities_and_total_equity")
        print("-" * 80)
        for f in failed_both:
            print(f"\n  {f['ticker']} - {f['company_name'][:50]}")
            print(f"    CIK: {f['cik']}, ADSH: {f['adsh']}")
            print(f"    Year: {f['year']}, Quarter: {f['quarter']}")
            print(f"    Found controls: {list(f['control_lines'].keys())}")

    if error_companies:
        print("\n" + "-" * 80)
        print("ERRORS (could not process)")
        print("-" * 80)
        for e in error_companies[:10]:  # Show first 10 errors
            print(f"\n  {e['ticker']} - {e['company_name'][:50]}")
            print(f"    CIK: {e['cik']}, ADSH: {e['adsh']}")
            print(f"    Error: {e['error'][:100]}")
        if len(error_companies) > 10:
            print(f"\n  ... and {len(error_companies) - 10} more errors")

    # Return summary for programmatic use
    return {
        'total_tested': total_tested,
        'success_count': success_count,
        'failed_total_assets': failed_total_assets,
        'failed_total_le': failed_total_le,
        'failed_both': failed_both,
        'error_companies': error_companies
    }


if __name__ == '__main__':
    results = test_control_items()
