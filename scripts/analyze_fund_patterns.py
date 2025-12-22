"""Analyze calc graph patterns for fund companies"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import psycopg2
from psycopg2.extras import RealDictCursor
from config import config
from statement_reconstructor import StatementReconstructor
from map_financial_statements import find_bs_control_items

# Get fund companies
conn = psycopg2.connect(config.get_db_connection())
cur = conn.cursor(cursor_factory=RealDictCursor)

cur.execute('''
    SELECT c.company_name, c.ticker, c.cik, c.sic, f.adsh
    FROM companies c
    JOIN filings f ON c.cik = f.cik
    WHERE f.source_year = 2024 AND f.source_quarter = 2
    AND (c.sic IN ('6722', '6726', '6221', '6500')
         OR LOWER(c.company_name) LIKE '%fund%'
         OR LOWER(c.company_name) LIKE '%etf%'
         OR LOWER(c.company_name) LIKE '%trust%')
    AND c.ticker IS NOT NULL AND c.ticker != ''
    ORDER BY RANDOM()
    LIMIT 30
''')

funds = cur.fetchall()
cur.close()
conn.close()

print(f'Analyzing {len(funds)} fund companies')
print('=' * 120)

reconstructor = StatementReconstructor(year=2024, quarter=2)

# Track patterns
pattern_a = []  # AssetsNet as root (Assets/Liabilities are children)
pattern_b = []  # LiabilitiesAndStockholdersEquity as root (traditional)
pattern_c = []  # No connecting parent (all separate roots)
no_bs = []
errors = []

# Track control item detection
control_success = []
control_fail = []

for idx, fund in enumerate(funds, 1):
    ticker = fund['ticker'] or 'N/A'
    cik = fund['cik']
    adsh = fund['adsh']
    name = fund['company_name'][:50]

    try:
        bs_result = reconstructor.reconstruct_statement_multi_period(cik=cik, adsh=adsh, stmt_type='BS')

        if not bs_result or not bs_result.get('line_items'):
            no_bs.append((ticker, name))
            continue

        line_items = bs_result['line_items']

        # Find key items
        assets_item = None
        liabilities_item = None
        net_assets_item = None
        liab_and_equity_item = None

        for item in line_items:
            tag = item.get('tag', '').lower()
            plabel = (item.get('plabel', '') or '').lower()

            # Assets
            if tag == 'assets' or (tag.endswith('assets') and 'net' not in tag and 'other' not in tag):
                if 'total' in plabel or plabel == 'assets':
                    if assets_item is None or item.get('line', 0) > assets_item.get('line', 0):
                        assets_item = item

            # Liabilities
            if tag == 'liabilities' or (tag.endswith('liabilities') and 'other' not in tag):
                if 'total' in plabel or plabel == 'liabilities':
                    if liabilities_item is None or item.get('line', 0) > liabilities_item.get('line', 0):
                        liabilities_item = item

            # Net Assets (AssetsNet or StockholdersEquity with net assets label)
            if tag == 'assetsnet' or (('net asset' in plabel or plabel == 'net assets') and 'stockholdersequity' in tag.lower()):
                if net_assets_item is None or item.get('line', 0) > net_assets_item.get('line', 0):
                    net_assets_item = item

            # LiabilitiesAndStockholdersEquity
            if 'liabilitiesandstockholdersequity' in tag.lower() or 'liabilitiesandequity' in tag.lower():
                liab_and_equity_item = item

        # Determine pattern
        pattern = 'unknown'
        details = {}

        if assets_item:
            assets_parent = assets_item.get('parent_line')
            assets_is_sum = assets_item.get('is_sum', False)
            details['assets'] = {
                'line': assets_item.get('line'),
                'parent_line': assets_parent,
                'is_sum': assets_is_sum,
                'tag': assets_item.get('tag'),
                'plabel': assets_item.get('plabel', '')
            }

        if liabilities_item:
            liab_parent = liabilities_item.get('parent_line')
            liab_is_sum = liabilities_item.get('is_sum', False)
            details['liabilities'] = {
                'line': liabilities_item.get('line'),
                'parent_line': liab_parent,
                'is_sum': liab_is_sum,
                'tag': liabilities_item.get('tag'),
                'plabel': liabilities_item.get('plabel', '')
            }

        if net_assets_item:
            na_parent = net_assets_item.get('parent_line')
            na_is_sum = net_assets_item.get('is_sum', False)
            na_children = net_assets_item.get('calc_children', [])
            details['net_assets'] = {
                'line': net_assets_item.get('line'),
                'parent_line': na_parent,
                'is_sum': na_is_sum,
                'tag': net_assets_item.get('tag'),
                'plabel': net_assets_item.get('plabel', ''),
                'children_count': len(na_children)
            }

        if liab_and_equity_item:
            le_parent = liab_and_equity_item.get('parent_line')
            le_is_sum = liab_and_equity_item.get('is_sum', False)
            details['liab_and_equity'] = {
                'line': liab_and_equity_item.get('line'),
                'parent_line': le_parent,
                'is_sum': le_is_sum,
                'tag': liab_and_equity_item.get('tag'),
                'plabel': liab_and_equity_item.get('plabel', '')
            }

        # Classify pattern
        if liab_and_equity_item:
            pattern = 'B'  # Traditional with LiabilitiesAndStockholdersEquity
            pattern_b.append((ticker, name, details))
        elif net_assets_item:
            na_children = net_assets_item.get('calc_children', [])
            # Check if Assets and Liabilities are children of NetAssets
            child_tags = [c[0].lower() if isinstance(c, (list, tuple)) else '' for c in na_children]
            has_assets_child = any('assets' in ct and 'net' not in ct for ct in child_tags)
            has_liab_child = any('liabilities' in ct for ct in child_tags)

            if has_assets_child or has_liab_child:
                pattern = 'A'  # AssetsNet as root
                pattern_a.append((ticker, name, details))
            else:
                pattern = 'C'  # Separate roots
                pattern_c.append((ticker, name, details))
        elif assets_item and liabilities_item:
            pattern = 'C'  # Separate roots (no net assets found)
            pattern_c.append((ticker, name, details))
        else:
            pattern = 'unknown'

        # Test control item detection
        control_lines = find_bs_control_items(line_items)
        has_total_assets = 'total_assets' in control_lines
        has_total_l_and_e = 'total_liabilities_and_total_equity' in control_lines
        has_total_se = 'total_stockholders_equity' in control_lines

        if has_total_assets and (has_total_l_and_e or has_total_se):
            control_success.append((ticker, name, pattern, control_lines))
        else:
            control_fail.append((ticker, name, pattern, control_lines, details))

    except Exception as e:
        errors.append((ticker, name, str(e)[:60]))

print()
print('=' * 120)
print('PATTERN DISTRIBUTION')
print('=' * 120)
print(f'Pattern A (AssetsNet as root):                    {len(pattern_a)}')
print(f'Pattern B (LiabilitiesAndStockholdersEquity):     {len(pattern_b)}')
print(f'Pattern C (Separate roots / no connecting):      {len(pattern_c)}')
print(f'No BS data:                                       {len(no_bs)}')
print(f'Errors:                                           {len(errors)}')

print()
print('=' * 120)
print('CONTROL ITEM DETECTION RESULTS')
print('=' * 120)
total_with_bs = len(pattern_a) + len(pattern_b) + len(pattern_c)
if total_with_bs > 0:
    print(f'Total funds with BS data: {total_with_bs}')
    print(f'Control items detected:   {len(control_success)} ({len(control_success)*100/total_with_bs:.1f}%)')
    print(f'Control items FAILED:     {len(control_fail)} ({len(control_fail)*100/total_with_bs:.1f}%)')

if control_fail:
    print()
    print('-' * 120)
    print('FAILED CONTROL ITEM DETECTION:')
    print('-' * 120)
    for ticker, name, pattern, ctrl, details in control_fail:
        print(f'\n  {ticker:8s} {name} (Pattern {pattern})')
        print(f'    Control lines found: {list(ctrl.keys())}')
        print(f'    Details:')
        for key, val in details.items():
            line = val.get("line")
            parent = val.get("parent_line")
            is_sum = val.get("is_sum")
            tag = val.get("tag")
            plabel = val.get("plabel", "")
            print(f'      {key}: line={line}, parent_line={parent}, is_sum={is_sum}')
            print(f'             tag={tag}')
            print(f'             plabel="{plabel}"')

if pattern_a:
    print()
    print('-' * 120)
    print('PATTERN A EXAMPLES (AssetsNet as root):')
    print('-' * 120)
    for ticker, name, details in pattern_a[:5]:
        print(f'\n  {ticker:8s} {name}')
        for key, val in details.items():
            line = val.get("line")
            parent = val.get("parent_line")
            tag = val.get("tag")
            plabel = val.get("plabel", "")
            print(f'    {key}: line={line}, parent_line={parent}')
            print(f'           tag={tag}, plabel="{plabel}"')

if pattern_c:
    print()
    print('-' * 120)
    print('PATTERN C EXAMPLES (Separate roots):')
    print('-' * 120)
    for ticker, name, details in pattern_c[:5]:
        print(f'\n  {ticker:8s} {name}')
        for key, val in details.items():
            line = val.get("line")
            parent = val.get("parent_line")
            tag = val.get("tag")
            plabel = val.get("plabel", "")
            print(f'    {key}: line={line}, parent_line={parent}')
            print(f'           tag={tag}, plabel="{plabel}"')

if errors:
    print()
    print('-' * 120)
    print(f'ERRORS ({len(errors)}):')
    print('-' * 120)
    for ticker, name, err in errors[:10]:
        print(f'  {ticker:8s} {name:40s} -> {err}')
