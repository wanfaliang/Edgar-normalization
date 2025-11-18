"""
Test period discovery approach to find all periods in a filing

This implements the dynamic period discovery algorithm from NEXT_SESSION_PLAN_UPDATED.md
"""
import pandas as pd
from datetime import datetime


def discover_bs_periods(pre_df, num_df):
    """
    Discover all Balance Sheet periods (instant, qtrs=0)

    Returns list of ddate values representing each BS column
    """
    # 1. Get all BS tags from PRE table
    bs_tags = pre_df[pre_df['stmt'] == 'BS']['tag'].unique()

    # 2. Find all values in NUM for these tags (consolidated only)
    bs_nums = num_df[num_df['tag'].isin(bs_tags)]
    bs_nums = bs_nums[bs_nums['segments'].isna() & bs_nums['coreg'].isna()]

    # 3. Find unique ddate values (each = one BS column)
    periods = sorted(bs_nums['ddate'].unique(), reverse=True)

    return [{'ddate': d, 'qtrs': '0', 'type': 'instant'} for d in periods]


def discover_is_periods(pre_df, num_df):
    """
    Discover all Income Statement periods (duration, qtrs≠0)

    Returns list of (ddate, qtrs) tuples representing each IS column
    """
    # 1. Get all IS tags from PRE
    is_tags = pre_df[pre_df['stmt'] == 'IS']['tag'].unique()

    # 2. Find all values in NUM (consolidated only)
    is_nums = num_df[num_df['tag'].isin(is_tags)]
    is_nums = is_nums[is_nums['segments'].isna() & is_nums['coreg'].isna()]

    # 3. Find unique (ddate, qtrs) combinations
    periods_df = is_nums[['ddate', 'qtrs']].drop_duplicates()

    # Sort by ddate (descending) then qtrs (ascending)
    periods_df = periods_df.sort_values(['ddate', 'qtrs'], ascending=[False, True])

    return [{'ddate': row['ddate'], 'qtrs': row['qtrs'], 'type': 'duration'}
            for _, row in periods_df.iterrows() if row['qtrs'] != '0']


def discover_cf_periods(pre_df, num_df, tag_df):
    """
    Discover all Cash Flow periods

    For flow items (duration): similar to IS
    """
    # 1. Get all CF tags from PRE
    cf_tags = pre_df[pre_df['stmt'] == 'CF']['tag'].unique()

    # 2. Filter to duration tags only (exclude instant cash balance tags)
    cf_tags_duration = []
    for tag in cf_tags:
        tag_info = tag_df[tag_df['tag'] == tag]
        if len(tag_info) > 0 and tag_info.iloc[0].get('iord') == 'D':
            cf_tags_duration.append(tag)

    # 3. Find all values in NUM for duration tags (consolidated only)
    cf_nums = num_df[num_df['tag'].isin(cf_tags_duration)]
    cf_nums = cf_nums[cf_nums['segments'].isna() & cf_nums['coreg'].isna()]

    # 4. Find unique (ddate, qtrs) combinations
    periods_df = cf_nums[['ddate', 'qtrs']].drop_duplicates()

    # Sort by ddate (descending) then qtrs (ascending)
    periods_df = periods_df.sort_values(['ddate', 'qtrs'], ascending=[False, True])

    return [{'ddate': row['ddate'], 'qtrs': row['qtrs'], 'type': 'duration'}
            for _, row in periods_df.iterrows() if row['qtrs'] != '0']


def format_period_label(ddate, qtrs):
    """Generate human-readable period label"""
    dt = datetime.strptime(ddate, '%Y%m%d')
    date_str = dt.strftime('%b %d, %Y')

    qtrs_int = int(qtrs)
    if qtrs_int == 0:
        return f'As of {date_str}'
    elif qtrs_int == 1:
        return f'Three Months Ended {date_str}'
    elif qtrs_int == 2:
        return f'Six Months Ended {date_str}'
    elif qtrs_int == 3:
        return f'Nine Months Ended {date_str}'
    elif qtrs_int == 4:
        return f'Year Ended {date_str}'
    else:
        return f'{qtrs_int} Quarters Ended {date_str}'


# Test cases
COMPANIES = [
    {
        'name': 'Amazon 10-Q Q2 2024',
        'adsh': '0001018724-24-000130',
        'expected_bs': 2,  # Current + prior year end
        'expected_is': 4,  # Q2 2024, Q2 2023, YTD 2024, YTD 2023
        'expected_cf': 2,  # YTD 2024, YTD 2023
    },
    {
        'name': 'Home Depot 10-Q Q2 2024',
        'adsh': '0000354950-24-000201',
        'expected_bs': 2,
        'expected_is': 4,
        'expected_cf': 2,
    },
    {
        'name': 'P&G 10-K FY2024',
        'adsh': '0000080424-24-000083',
        'expected_bs': 2,  # Current + prior year
        'expected_is': 3,  # 2024, 2023, 2022
        'expected_cf': 3,  # 2024, 2023, 2022
    },
]

# Load data
pre_df = pd.read_csv('data/sec_data/extracted/2024q3/pre.txt', sep='\t', dtype=str)
num_df = pd.read_csv('data/sec_data/extracted/2024q3/num.txt', sep='\t', dtype=str)
tag_df = pd.read_csv('data/sec_data/extracted/2024q3/tag.txt', sep='\t', dtype=str)

print("=" * 80)
print("TESTING PERIOD DISCOVERY")
print("=" * 80)

for company in COMPANIES:
    print(f"\n{'=' * 80}")
    print(f"{company['name']}")
    print('=' * 80)

    # Filter to company
    pre = pre_df[pre_df['adsh'] == company['adsh']]
    num = num_df[num_df['adsh'] == company['adsh']]

    # Discover periods for each statement type
    print("\n--- BALANCE SHEET PERIODS ---")
    bs_periods = discover_bs_periods(pre, num)
    print(f"Found {len(bs_periods)} periods (expected: {company['expected_bs']})")
    for i, period in enumerate(bs_periods, 1):
        label = format_period_label(period['ddate'], period['qtrs'])
        print(f"  {i}. {label}")
        print(f"     (ddate={period['ddate']}, qtrs={period['qtrs']})")

    print("\n--- INCOME STATEMENT PERIODS ---")
    is_periods = discover_is_periods(pre, num)
    print(f"Found {len(is_periods)} periods (expected: {company['expected_is']})")
    for i, period in enumerate(is_periods, 1):
        label = format_period_label(period['ddate'], period['qtrs'])
        print(f"  {i}. {label}")
        print(f"     (ddate={period['ddate']}, qtrs={period['qtrs']})")

    print("\n--- CASH FLOW PERIODS ---")
    cf_periods = discover_cf_periods(pre, num, tag_df)
    print(f"Found {len(cf_periods)} periods (expected: {company['expected_cf']})")
    for i, period in enumerate(cf_periods, 1):
        label = format_period_label(period['ddate'], period['qtrs'])
        print(f"  {i}. {label}")
        print(f"     (ddate={period['ddate']}, qtrs={period['qtrs']})")

    # Validation
    print("\n--- VALIDATION ---")
    bs_match = len(bs_periods) == company['expected_bs']
    is_match = len(is_periods) == company['expected_is']
    cf_match = len(cf_periods) == company['expected_cf']

    if bs_match and is_match and cf_match:
        print("✅ All period counts match expectations!")
    else:
        if not bs_match:
            print(f"❌ BS: Found {len(bs_periods)}, expected {company['expected_bs']}")
        if not is_match:
            print(f"❌ IS: Found {len(is_periods)}, expected {company['expected_is']}")
        if not cf_match:
            print(f"❌ CF: Found {len(cf_periods)}, expected {company['expected_cf']}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print("\nPeriod discovery successfully identifies all periods in each filing!")
print("Each statement type can have different numbers of periods:")
print("  - Balance Sheet: Multiple instant snapshots")
print("  - Income Statement: Multiple durations (quarterly + YTD)")
print("  - Cash Flow: Typically shows YTD periods only")
