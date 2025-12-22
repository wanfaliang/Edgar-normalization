"""Test total_current_assets labels across 100 random companies"""
import sys
sys.path.insert(0, 'src')

import psycopg2
from psycopg2.extras import RealDictCursor
from config import config
from statement_reconstructor import StatementReconstructor

def normalize(s):
    if not s:
        return ''
    return ' '.join(s.lower().replace(',', ' ').replace('-', ' ').replace('/', ' ').split())

# Get 100 random companies with 2024 Q2 filings
conn = psycopg2.connect(config.get_db_connection())
cur = conn.cursor(cursor_factory=RealDictCursor)

cur.execute("""
    SELECT c.company_name, c.ticker, c.cik, f.adsh
    FROM companies c
    JOIN filings f ON c.cik = f.cik
    WHERE c.ticker IS NOT NULL AND c.ticker != ''
    AND f.source_year = 2024 AND f.source_quarter = 2
    ORDER BY RANDOM()
    LIMIT 100
""")

companies = cur.fetchall()
cur.close()
conn.close()

print(f"Testing {len(companies)} companies for total_current_assets patterns\n")
print("=" * 80)

reconstructor = StatementReconstructor(year=2024, quarter=2)

# Track results
has_total_keyword = []
no_total_keyword = []
no_current_assets_found = []

for idx, company in enumerate(companies, 1):
    ticker = company['ticker']
    cik = company['cik']
    adsh = company['adsh']

    try:
        bs_result = reconstructor.reconstruct_statement_multi_period(cik=cik, adsh=adsh, stmt_type='BS')

        if not bs_result or not bs_result.get('line_items'):
            no_current_assets_found.append((ticker, company['company_name'], "No BS data"))
            continue

        # Find total_current_assets using current pattern logic
        found_item = None
        for item in bs_result['line_items']:
            p = normalize(item.get('plabel', ''))
            if ('total current assets' in p) or ('current assets' in p and 'other' not in p):
                found_item = item
                break

        if found_item:
            plabel = found_item.get('plabel', '')
            p_norm = normalize(plabel)

            if 'total' in p_norm:
                has_total_keyword.append((ticker, company['company_name'], plabel))
            else:
                no_total_keyword.append((ticker, company['company_name'], plabel))
                print(f"[{idx}] {ticker}: NO 'total' keyword -> \"{plabel}\"")
        else:
            no_current_assets_found.append((ticker, company['company_name'], "Pattern not matched"))

    except Exception as e:
        no_current_assets_found.append((ticker, company['company_name'], str(e)[:50]))

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Total companies tested: {len(companies)}")
print(f"Has 'total' keyword: {len(has_total_keyword)}")
print(f"NO 'total' keyword: {len(no_total_keyword)}")
print(f"No current assets found: {len(no_current_assets_found)}")

if no_total_keyword:
    print("\n" + "-" * 80)
    print("Companies WITHOUT 'total' keyword in total_current_assets:")
    print("-" * 80)
    for ticker, name, plabel in no_total_keyword:
        print(f"  {ticker:8s} {name[:40]:40s} -> \"{plabel}\"")

if no_current_assets_found:
    print("\n" + "-" * 80)
    print(f"Companies with no current assets found ({len(no_current_assets_found)}):")
    print("-" * 80)
    for ticker, name, reason in no_current_assets_found[:20]:  # Show first 20
        print(f"  {ticker:8s} {name[:40]:40s} -> {reason}")
    if len(no_current_assets_found) > 20:
        print(f"  ... and {len(no_current_assets_found) - 20} more")
