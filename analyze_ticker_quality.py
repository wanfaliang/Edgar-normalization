"""
Ticker Data Quality Analysis
=============================
Analyze the quality of ticker symbols in our database
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

import psycopg2
from psycopg2.extras import RealDictCursor
from config import config

def analyze_ticker_quality():
    """Analyze ticker data quality issues"""

    conn = psycopg2.connect(config.get_db_connection())
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print("\n" + "="*70)
    print("TICKER DATA QUALITY ANALYSIS")
    print("="*70)

    # 1. Overall coverage
    print("\n1. OVERALL COVERAGE:")
    print("-"*70)

    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(ticker) as with_ticker,
            COUNT(*) - COUNT(ticker) as no_ticker
        FROM companies
    """)

    stats = cur.fetchone()
    total = stats['total']
    with_ticker = stats['with_ticker']
    no_ticker = stats['no_ticker']

    print(f"Total companies: {total:,}")
    print(f"With ticker: {with_ticker:,} ({with_ticker/total*100:.1f}%)")
    print(f"No ticker: {no_ticker:,} ({no_ticker/total*100:.1f}%)")

    # 2. Suspicious ticker patterns
    print("\n2. SUSPICIOUS TICKER PATTERNS:")
    print("-"*70)

    # Tickers with hyphens (often preferred shares or special classes)
    cur.execute("""
        SELECT COUNT(*) as count
        FROM companies
        WHERE ticker LIKE '%-%'
    """)

    hyphen_count = cur.fetchone()['count']
    print(f"Tickers with hyphens (e.g., 'C-PN', 'MER-PK'): {hyphen_count:,} ({hyphen_count/with_ticker*100:.1f}% of tickers)")

    # Show examples
    cur.execute("""
        SELECT cik, company_name, ticker, total_filings
        FROM companies
        WHERE ticker LIKE '%-%'
        ORDER BY total_filings DESC
        LIMIT 10
    """)

    print(f"\n  Examples (top 10 by filings):")
    for row in cur.fetchall():
        print(f"    {row['ticker']:10s} | {row['company_name'][:50]:50s} | {row['total_filings']:4d} filings")

    # Tickers with numbers
    cur.execute("""
        SELECT COUNT(*) as count
        FROM companies
        WHERE ticker ~ '[0-9]'
    """)

    numeric_count = cur.fetchone()['count']
    print(f"\nTickers with numbers: {numeric_count:,} ({numeric_count/with_ticker*100:.1f}% of tickers)")

    # Tickers longer than 5 characters (unusual for US stocks)
    cur.execute("""
        SELECT COUNT(*) as count
        FROM companies
        WHERE LENGTH(ticker) > 5
    """)

    long_count = cur.fetchone()['count']
    print(f"Tickers longer than 5 chars: {long_count:,} ({long_count/with_ticker*100:.1f}% of tickers)")

    # 3. Well-known companies with potentially wrong tickers
    print("\n3. WELL-KNOWN COMPANIES - TICKER VERIFICATION:")
    print("-"*70)

    # Major companies with expected tickers
    major_companies = [
        ('APPLE INC', 'AAPL'),
        ('MICROSOFT CORP', 'MSFT'),
        ('AMAZON COM INC', 'AMZN'),
        ('ALPHABET INC', 'GOOG'),
        ('META PLATFORMS INC', 'META'),
        ('TESLA INC', 'TSLA'),
        ('BERKSHIRE HATHAWAY', 'BRK'),
        ('JPMORGAN CHASE', 'JPM'),
        ('JOHNSON & JOHNSON', 'JNJ'),
        ('VISA INC', 'V'),
        ('WALMART INC', 'WMT'),
        ('EXXON MOBIL', 'XOM'),
        ('NVIDIA CORP', 'NVDA'),
        ('PROCTER & GAMBLE', 'PG'),
        ('HOME DEPOT', 'HD'),
    ]

    mismatches = []

    for company_search, expected_ticker in major_companies:
        cur.execute("""
            SELECT cik, company_name, ticker
            FROM companies
            WHERE company_name ILIKE %s
            ORDER BY total_filings DESC
            LIMIT 1
        """, (f'%{company_search}%',))

        result = cur.fetchone()
        if result:
            actual_ticker = result['ticker']
            if actual_ticker != expected_ticker:
                mismatches.append({
                    'company': result['company_name'],
                    'expected': expected_ticker,
                    'actual': actual_ticker or 'NULL',
                    'cik': result['cik']
                })

    if mismatches:
        print(f"\n⚠️  Found {len(mismatches)} ticker mismatches in major companies:")
        for m in mismatches:
            print(f"  {m['company'][:40]:40s} | Expected: {m['expected']:6s} | Actual: {m['actual']:6s}")
    else:
        print(f"\n✅ All major companies have correct tickers!")

    # 4. Companies with most filings but no ticker
    print("\n4. ACTIVE COMPANIES WITHOUT TICKERS:")
    print("-"*70)

    cur.execute("""
        SELECT cik, company_name, total_filings
        FROM companies
        WHERE ticker IS NULL
        AND total_filings > 20
        ORDER BY total_filings DESC
        LIMIT 10
    """)

    no_ticker_active = cur.fetchall()
    if no_ticker_active:
        print(f"\nTop 10 active filers without tickers:")
        for row in no_ticker_active:
            print(f"  CIK {row['cik']:10s} | {row['total_filings']:4d} filings | {row['company_name'][:50]}")

    # 5. Exchange distribution
    print("\n5. EXCHANGE DISTRIBUTION:")
    print("-"*70)

    cur.execute("""
        SELECT exchange, COUNT(*) as count
        FROM companies
        WHERE exchange IS NOT NULL
        GROUP BY exchange
        ORDER BY count DESC
        LIMIT 15
    """)

    exchanges = cur.fetchall()
    print(f"\nTop exchanges:")
    for row in exchanges:
        print(f"  {row['exchange']:20s}: {row['count']:,} companies")

    # 6. Recommendations
    print("\n" + "="*70)
    print("SUMMARY & RECOMMENDATIONS")
    print("="*70)

    issues = []

    if hyphen_count > 1000:
        issues.append(f"• {hyphen_count:,} tickers with hyphens (likely preferred shares/special classes)")

    if len(mismatches) > 0:
        issues.append(f"• {len(mismatches)} major companies have incorrect tickers")

    if no_ticker / total > 0.5:
        issues.append(f"• {no_ticker/total*100:.1f}% of companies have no ticker")

    if issues:
        print(f"\n⚠️  Issues found:")
        for issue in issues:
            print(f"  {issue}")

        print(f"\nRecommendations:")
        print(f"  1. Create a manual ticker override file for major companies")
        print(f"  2. Filter out preferred share tickers (containing '-')")
        print(f"  3. Add a ticker validation/correction step")
        print(f"  4. Consider alternative ticker data sources (e.g., Yahoo Finance API)")
    else:
        print(f"\n✅ Ticker data quality looks good!")

    cur.close()
    conn.close()

if __name__ == "__main__":
    analyze_ticker_quality()
