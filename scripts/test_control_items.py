"""Test total_assets and total_liabilities_and_total_equity control items across 150 random companies"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import psycopg2
from psycopg2.extras import RealDictCursor
from config import config
from statement_reconstructor import StatementReconstructor
from map_financial_statements import find_bs_control_items

def normalize(s):
    if not s:
        return ''
    return ' '.join(s.lower().replace(',', ' ').replace('-', ' ').replace('/', ' ').split())

# Get 150 random companies with 2024 Q2 filings
conn = psycopg2.connect(config.get_db_connection())
cur = conn.cursor(cursor_factory=RealDictCursor)

cur.execute("""
    SELECT c.company_name, c.ticker, c.cik, f.adsh
    FROM companies c
    JOIN filings f ON c.cik = f.cik
    WHERE c.ticker IS NOT NULL AND c.ticker != ''
    AND f.source_year = 2024 AND f.source_quarter = 2
    ORDER BY RANDOM()
    LIMIT 150
""")

companies = cur.fetchall()
cur.close()
conn.close()

print(f"Testing {len(companies)} companies for total_assets and total_liabilities_and_total_equity control items\n")
print("=" * 100)

reconstructor = StatementReconstructor(year=2024, quarter=2)

# Track results
found_both = []
missing_total_assets = []
missing_total_l_and_e = []
missing_both = []
errors = []

for idx, company in enumerate(companies, 1):
    ticker = company['ticker']
    cik = company['cik']
    adsh = company['adsh']
    name = company['company_name']

    try:
        bs_result = reconstructor.reconstruct_statement_multi_period(cik=cik, adsh=adsh, stmt_type='BS')

        if not bs_result or not bs_result.get('line_items'):
            errors.append((ticker, name, "No BS data"))
            continue

        line_items = bs_result['line_items']
        control_lines = find_bs_control_items(line_items)

        has_total_assets = 'total_assets' in control_lines
        has_total_l_and_e = 'total_liabilities_and_total_equity' in control_lines

        if has_total_assets and has_total_l_and_e:
            found_both.append((ticker, name))
        elif not has_total_assets and not has_total_l_and_e:
            # Find potential candidates
            candidates = []
            for item in line_items:
                p = normalize(item.get('plabel', ''))
                tag = item.get('tag', '')
                if 'asset' in p or 'liabilit' in p or 'equity' in p or 'capital' in p:
                    if 'total' in p:
                        candidates.append((item.get('plabel', ''), tag, item.get('stmt_order', 0)))
            missing_both.append((ticker, name, candidates))
            print(f"[{idx}] {ticker}: MISSING BOTH")
        elif not has_total_assets:
            # Find potential total_assets candidates
            candidates = []
            for item in line_items:
                p = normalize(item.get('plabel', ''))
                tag = item.get('tag', '')
                if 'asset' in p and 'total' in p:
                    candidates.append((item.get('plabel', ''), tag, item.get('stmt_order', 0)))
            missing_total_assets.append((ticker, name, candidates))
            print(f"[{idx}] {ticker}: MISSING total_assets")
        else:  # missing total_l_and_e
            # Find potential total_liabilities_and_equity candidates
            candidates = []
            for item in line_items:
                p = normalize(item.get('plabel', ''))
                tag = item.get('tag', '')
                plabel = item.get('plabel', '')
                # Look for items that could be the bottom line
                if ('liabilit' in p and ('equity' in p or 'capital' in p or 'stockholder' in p or 'shareholder' in p or 'net asset' in p)) or \
                   (('total' in p) and (p.endswith('equity') or p.endswith('capital') or 'net asset' in p)):
                    candidates.append((plabel, tag, item.get('stmt_order', 0)))
            missing_total_l_and_e.append((ticker, name, candidates))
            print(f"[{idx}] {ticker}: MISSING total_liabilities_and_total_equity")

    except Exception as e:
        errors.append((ticker, name, str(e)[:80]))

print("\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)
print(f"Total companies tested: {len(companies)}")
print(f"Found BOTH control items: {len(found_both)}")
print(f"Missing total_assets: {len(missing_total_assets)}")
print(f"Missing total_liabilities_and_total_equity: {len(missing_total_l_and_e)}")
print(f"Missing BOTH: {len(missing_both)}")
print(f"Errors: {len(errors)}")

if missing_total_assets:
    print("\n" + "-" * 100)
    print("Companies MISSING total_assets:")
    print("-" * 100)
    for ticker, name, candidates in missing_total_assets:
        print(f"\n  {ticker:8s} {name[:50]}")
        if candidates:
            print("    Potential candidates:")
            for plabel, tag, line_num in candidates:
                print(f"      Line {line_num}: \"{plabel}\" ({tag})")
        else:
            print("    No candidates found with 'asset' and 'total'")

if missing_total_l_and_e:
    print("\n" + "-" * 100)
    print("Companies MISSING total_liabilities_and_total_equity:")
    print("-" * 100)
    for ticker, name, candidates in missing_total_l_and_e:
        print(f"\n  {ticker:8s} {name[:50]}")
        if candidates:
            print("    Potential candidates:")
            for plabel, tag, line_num in candidates:
                print(f"      Line {line_num}: \"{plabel}\" ({tag})")
        else:
            print("    No candidates found")

if missing_both:
    print("\n" + "-" * 100)
    print("Companies MISSING BOTH control items:")
    print("-" * 100)
    for ticker, name, candidates in missing_both:
        print(f"\n  {ticker:8s} {name[:50]}")
        if candidates:
            print("    Potential 'total' items with asset/liability/equity/capital:")
            for plabel, tag, line_num in candidates[:10]:  # Limit to 10
                print(f"      Line {line_num}: \"{plabel}\" ({tag})")
        else:
            print("    No 'total' candidates found")

if errors:
    print("\n" + "-" * 100)
    print(f"Errors ({len(errors)}):")
    print("-" * 100)
    for ticker, name, err in errors[:20]:
        print(f"  {ticker:8s} {name[:40]:40s} -> {err}")
