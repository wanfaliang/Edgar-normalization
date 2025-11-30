"""
Diagnose Apple 10-K Beginning Cash Issue
=========================================
Examine the cash flow statement to see why beginning and ending cash are the same
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from statement_reconstructor import StatementReconstructor
import pandas as pd

def diagnose_apple_cash():
    """Diagnose Apple's cash flow statement"""

    # Apple's latest 10-K
    adsh = '0000320193-24-000123'
    cik = '320193'

    print("\n" + "="*70)
    print("DIAGNOSING APPLE 10-K CASH FLOW STATEMENT")
    print("="*70)
    print(f"\nADSH: {adsh}")
    print(f"CIK: {cik}")

    # Initialize reconstructor
    reconstructor = StatementReconstructor(year=2024, quarter=4)

    # Reconstruct cash flow statement
    print("\n" + "-"*70)
    print("Reconstructing Cash Flow Statement...")
    print("-"*70)

    result = reconstructor.reconstruct_statement_multi_period(
        cik=cik,
        adsh=adsh,
        stmt_type='CF'
    )

    if not result or not result.get('line_items'):
        print("❌ Failed to reconstruct CF statement")
        return

    # Find beginning and ending cash line items
    line_items = result['line_items']
    periods = result.get('periods', [])

    print(f"\n✅ Reconstructed CF with {len(line_items)} line items and {len(periods)} periods")
    print(f"\nPeriods:")
    for i, period in enumerate(periods, 1):
        period_name = period.get('period_name') or period.get('name') or f"Period {i}"
        ddate = period.get('ddate', 'N/A')
        qtrs = period.get('qtrs', 'N/A')
        print(f"  {i}. {period_name} (ddate={ddate}, qtrs={qtrs})")
        print(f"     Period dict keys: {list(period.keys())}")

    # Find cash line items
    cash_items = []
    for item in line_items:
        plabel_lower = item['plabel'].lower()
        if 'cash' in plabel_lower and ('beginning' in plabel_lower or 'ending' in plabel_lower or 'end of' in plabel_lower):
            cash_items.append(item)

    print(f"\n" + "="*70)
    print("CASH BALANCE LINE ITEMS")
    print("="*70)

    for item in cash_items:
        print(f"\n{item['plabel']}")
        print(f"  Tag: {item.get('tag', 'N/A')}")
        if 'level' in item:
            print(f"  Level: {item['level']}")

        # Print all values
        if 'values' in item:
            values = item['values']
            if isinstance(values, dict):
                for key, val in values.items():
                    print(f"  {key}: {val}")
            elif isinstance(values, list):
                for i, val in enumerate(values):
                    period_name = periods[i].get('label', f"Period {i+1}") if i < len(periods) else f"Period {i+1}"
                    print(f"  {period_name}: {val}")
            else:
                print(f"  Values: {values}")

    # Check if beginning and ending are the same for first period
    if len(cash_items) >= 2 and len(periods) > 0:
        beginning_item = cash_items[0]
        ending_item = cash_items[-1]

        beginning_values = beginning_item.get('values', [])
        ending_values = ending_item.get('values', [])

        print(f"\n" + "="*70)
        print("ISSUE VERIFICATION")
        print("="*70)

        # Handle both list and dict values
        if isinstance(beginning_values, list) and isinstance(ending_values, list):
            for i, period in enumerate(periods):
                if i < len(beginning_values) and i < len(ending_values):
                    beg_val = beginning_values[i]
                    end_val = ending_values[i]

                    period_name = period.get('label', f"Period {i+1}")
                    print(f"\n{period_name}:")
                    print(f"  Beginning: {beg_val}")
                    print(f"  Ending: {end_val}")

                    if beg_val == end_val:
                        print(f"  ⚠️  ISSUE CONFIRMED: Beginning == Ending!")
                    else:
                        print(f"  ✅ OK: Values are different")
        else:
            print("\n⚠️  Values are not in list format, skipping verification")

    # Now let's examine the actual data from num.txt to see what dates are available
    print(f"\n" + "="*70)
    print("EXAMINING ACTUAL DATA FROM NUM.TXT")
    print("="*70)

    # Load num.txt directly
    num_path = reconstructor.base_dir / 'num.txt'
    num_df = pd.read_csv(num_path, sep='\t', dtype=str, na_values=[''])

    # Filter to this filing
    filing_num = num_df[num_df['adsh'] == adsh].copy()

    # Find cash balance tags (CashAndCashEquivalentsAtCarryingValue)
    cash_tags = filing_num[filing_num['tag'].str.contains('Cash', case=False, na=False)]
    instant_cash = cash_tags[cash_tags['tag'].str.contains('CashAndCashEquivalentsAtCarryingValue', case=False, na=False)]

    print(f"\nCash balance tags found: {len(instant_cash)}")

    if len(instant_cash) > 0:
        print("\nInstant cash values (CashAndCashEquivalentsAtCarryingValue):")
        instant_cash_sorted = instant_cash.sort_values('ddate')
        for _, row in instant_cash_sorted.iterrows():
            print(f"  ddate={row['ddate']}, qtrs={row['qtrs']}, value={row['value']}, uom={row['uom']}")

    # Check what instant dates are available
    all_instant = filing_num[filing_num['qtrs'] == '0']
    unique_dates = sorted(all_instant['ddate'].unique())

    print(f"\n\nAll instant dates (qtrs=0) available in this filing:")
    for date in unique_dates:
        print(f"  {date}")

    # Now let's manually calculate what the beginning date should be
    print(f"\n" + "="*70)
    print("BEGINNING DATE CALCULATION ANALYSIS")
    print("="*70)

    for period in periods:
        ending_date = period.get('ddate', '')
        qtrs = period.get('qtrs', '0')

        period_name = period.get('period_name') or period.get('name') or 'Period'
        print(f"\n{period_name}:")
        print(f"  Ending date: {ending_date}")
        print(f"  Quarters: {qtrs}")

        # Calculate what the algorithm would compute
        from datetime import datetime, timedelta

        end_date = datetime.strptime(ending_date, '%Y%m%d')
        months = int(qtrs) * 3
        days = months * 30.5
        approx_beginning = end_date - timedelta(days=days)
        approx_str = approx_beginning.strftime('%Y%m%d')

        print(f"  Calculated beginning (approx): {approx_str} ({int(days)} days back)")

        # Find closest instant date
        past_dates = [d for d in unique_dates if d < ending_date]
        if past_dates:
            closest = min(past_dates, key=lambda x: abs(int(x) - int(approx_str)))
            print(f"  Closest instant date found: {closest}")

            # Check actual values at both dates
            end_cash = instant_cash[instant_cash['ddate'] == ending_date]
            beg_cash = instant_cash[instant_cash['ddate'] == closest]

            if len(end_cash) > 0:
                print(f"  Ending cash value: {end_cash.iloc[0]['value']}")

            if len(beg_cash) > 0:
                print(f"  Beginning cash value: {beg_cash.iloc[0]['value']}")
            else:
                print(f"  ⚠️  No beginning cash value found at {closest}!")
        else:
            print(f"  ⚠️  No past instant dates found!")

if __name__ == "__main__":
    diagnose_apple_cash()
