"""
Diagnose beginning cash issue
Show exactly what dates are being calculated and matched
"""

from src.statement_reconstructor import StatementReconstructor
from src.period_discovery import PeriodDiscovery
from datetime import datetime, timedelta

print("="*80)
print("DIAGNOSING AMAZON BEGINNING CASH")
print("="*80)

reconstructor = StatementReconstructor(2024, 3)

# Load filing data
filing_data = reconstructor.load_filing_data('0001018724-24-000130')

# Get available instant dates
available_instant_dates = filing_data['num'][
    (filing_data['num']['qtrs'] == '0') &
    (filing_data['num']['segments'].isna()) &
    (filing_data['num']['coreg'].isna())
]['ddate'].unique().tolist()
available_instant_dates = sorted(available_instant_dates)

print(f"\nAvailable instant dates in NUM table:")
for date in available_instant_dates:
    print(f"  {date}")

# Test date inference for each CF period
discoverer = PeriodDiscovery()

cf_periods = [
    {'label': 'Year Ended Jun 30, 2024', 'ddate': '20240630', 'qtrs': '4'},
    {'label': 'Six Months Ended Jun 30, 2024', 'ddate': '20240630', 'qtrs': '2'},
    {'label': 'Three Months Ended Jun 30, 2024', 'ddate': '20240630', 'qtrs': '1'},
    {'label': 'Year Ended Jun 30, 2023', 'ddate': '20230630', 'qtrs': '4'},
    {'label': 'Six Months Ended Jun 30, 2023', 'ddate': '20230630', 'qtrs': '2'},
    {'label': 'Three Months Ended Jun 30, 2023', 'ddate': '20230630', 'qtrs': '1'},
]

print(f"\n{'='*80}")
print("DATE INFERENCE FOR EACH PERIOD:")
print(f"{'='*80}")

for period in cf_periods:
    print(f"\nPeriod: {period['label']}")
    print(f"  Ending date: {period['ddate']}")
    print(f"  Duration qtrs: {period['qtrs']}")

    # Calculate approximate beginning
    end_date = datetime.strptime(period['ddate'], '%Y%m%d')
    months = int(period['qtrs']) * 3
    days = months * 30.5
    approx_beginning = end_date - timedelta(days=days)
    approx_str = approx_beginning.strftime('%Y%m%d')
    print(f"  Calculated approximate beginning: {approx_str}")

    # Use discoverer to find closest
    inferred = discoverer.infer_beginning_ddate(
        period['ddate'],
        period['qtrs'],
        available_instant_dates
    )
    print(f"  Inferred beginning (closest match): {inferred}")

    # Check what value is stored for this date in NUM
    cash_tag = 'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents'
    matches = filing_data['num'][
        (filing_data['num']['tag'] == cash_tag) &
        (filing_data['num']['ddate'] == inferred) &
        (filing_data['num']['qtrs'] == '0') &
        (filing_data['num']['segments'].isna()) &
        (filing_data['num']['coreg'].isna())
    ]

    if len(matches) > 0:
        value = float(matches.iloc[0]['value'])
        print(f"  Value in NUM for ({inferred}, '0'): ${value:,.0f}")
    else:
        print(f"  ❌ NO VALUE found in NUM for ({inferred}, '0')")

print(f"\n{'='*80}")
