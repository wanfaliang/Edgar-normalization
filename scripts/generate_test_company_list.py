"""
Generate Test Company List
===========================
Query database for recent filings of 50 test companies.
Output: CSV file with company info ready for batch testing.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import psycopg2
from psycopg2.extras import RealDictCursor
from config import config
import csv

# 50 test companies - CIK only (we'll look up the rest)
TEST_COMPANIES = [
    # Technology (10)
    '789019',    # Microsoft
    '320193',    # Apple
    '1652044',   # Alphabet
    '1018724',   # Amazon
    '1326801',   # Meta
    '1045810',   # NVIDIA
    '50863',     # Intel
    '1341439',   # Oracle
    '1108524',   # Salesforce
    '796343',    # Adobe

    # Retail (8)
    '104169',    # Walmart
    '27419',     # Target
    '909832',    # Costco
    '354950',    # Home Depot
    '60667',     # Lowe's
    '109198',    # TJX Companies
    '29534',     # Dollar General
    '764478',    # Best Buy

    # Manufacturing (7)
    '66740',     # 3M
    '18230',     # Caterpillar
    '12927',     # Boeing
    '936468',    # Lockheed Martin
    '315189',    # Deere
    '40545',     # General Electric
    '773840',    # Honeywell

    # Financial (8)
    '19617',     # JPMorgan
    '70858',     # Bank of America
    '72971',     # Wells Fargo
    '886982',    # Goldman Sachs
    '895421',    # Morgan Stanley
    '4962',      # American Express
    '1403161',   # Visa
    '1141391',   # Mastercard

    # Healthcare (6)
    '200406',    # Johnson & Johnson
    '78003',     # Pfizer
    '731766',    # UnitedHealth
    '1800',      # Abbott
    '310158',    # Merck
    '64803',     # CVS

    # Energy (4)
    '34088',     # Exxon
    '93410',     # Chevron
    '1163165',   # ConocoPhillips
    '87347',     # Schlumberger

    # Consumer Goods (7)
    '21344',     # Coca-Cola
    '77476',     # PepsiCo
    '80424',     # Procter & Gamble
    '320187',    # Nike
    '63908',     # McDonald's
    '829224',    # Starbucks
    '21665',     # Colgate-Palmolive
]

def get_recent_filing(cik, conn):
    """Get most recent filing for a CIK"""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT
            c.company_name,
            c.ticker,
            c.cik,
            f.adsh,
            f.source_year,
            f.source_quarter,
            f.filed_date,
            f.form_type
        FROM companies c
        JOIN filings f ON c.cik = f.cik
        WHERE c.cik = %s
        ORDER BY f.filed_date DESC
        LIMIT 1
    """, (cik,))

    result = cur.fetchone()
    cur.close()
    return result

def main():
    print("Generating Test Company List")
    print("=" * 80)

    conn = psycopg2.connect(config.get_db_connection())

    companies = []
    found = 0
    missing = 0

    for cik in TEST_COMPANIES:
        filing = get_recent_filing(cik, conn)

        if filing:
            companies.append({
                'company_name': filing['company_name'],
                'ticker': filing['ticker'] or 'N/A',
                'cik': filing['cik'],
                'adsh': filing['adsh'],
                'year': filing['source_year'],
                'quarter': filing['source_quarter'],
                'filed_date': filing['filed_date'],
                'form_type': filing['form_type']
            })
            found += 1
            print(f"✓ {filing['ticker']:6s} {filing['company_name'][:40]:40s} {filing['adsh']}")
        else:
            print(f"✗ CIK {cik} - No filing found in database")
            missing += 1

    conn.close()

    # Write to CSV
    output_file = Path(__file__).parent.parent / 'docs' / 'test_companies_list.csv'

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'company_name', 'ticker', 'cik', 'adsh', 'year', 'quarter', 'filed_date', 'form_type'
        ])
        writer.writeheader()
        writer.writerows(companies)

    print("\n" + "=" * 80)
    print(f"Results:")
    print(f"  Found: {found}")
    print(f"  Missing: {missing}")
    print(f"  Total: {len(TEST_COMPANIES)}")
    print(f"\nCSV file created: {output_file}")

if __name__ == "__main__":
    main()
