"""
Test Control Item Identification
=================================
Comprehensive test to verify control items are identified correctly
for Balance Sheet, Income Statement, and Cash Flow.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from statement_reconstructor import StatementReconstructor
from map_financial_statements import (
    find_bs_control_items,
    find_is_control_items,
    find_cf_control_items
)


def test_control_items(cik, adsh, year, quarter):
    """Test control item identification for all three statements"""

    print("=" * 100)
    print("CONTROL ITEM IDENTIFICATION TEST")
    print("=" * 100)
    print(f"\nCompany: CIK {cik}")
    print(f"Filing: {adsh}")
    print(f"Dataset: {year}Q{quarter}\n")

    reconstructor = StatementReconstructor(year=year, quarter=quarter)

    # =========================================================================
    # BALANCE SHEET
    # =========================================================================
    print("\n" + "=" * 100)
    print("BALANCE SHEET CONTROL ITEMS")
    print("=" * 100)

    bs_result = reconstructor.reconstruct_statement_multi_period(cik=cik, adsh=adsh, stmt_type='BS')

    if bs_result and bs_result.get('line_items'):
        bs_control_items = find_bs_control_items(bs_result['line_items'])

        required_bs = ['total_current_assets', 'total_assets', 'total_current_liabilities',
                       'total_stockholders_equity', 'total_liabilities_and_total_equity']

        print(f"\n✓ Found {len(bs_control_items)}/8 control items:")
        for item_name, line_num in sorted(bs_control_items.items(), key=lambda x: x[1]):
            required_mark = " (REQUIRED)" if item_name in required_bs else ""
            # Find the plabel for this line
            plabel = next((item['plabel'] for item in bs_result['line_items']
                          if item.get('stmt_order') == line_num), "")
            print(f"  [{line_num:3d}] {item_name}{required_mark}")
            print(f"        → {plabel}")

        # Check for missing required items
        missing_required = [item for item in required_bs if item not in bs_control_items]
        if missing_required:
            print(f"\n⚠️  MISSING REQUIRED ITEMS: {', '.join(missing_required)}")
        else:
            print(f"\n✅ All required control items found!")
    else:
        print("❌ Failed to reconstruct Balance Sheet")

    # =========================================================================
    # INCOME STATEMENT
    # =========================================================================
    print("\n" + "=" * 100)
    print("INCOME STATEMENT CONTROL ITEMS")
    print("=" * 100)

    is_result = reconstructor.reconstruct_statement_multi_period(cik=cik, adsh=adsh, stmt_type='IS')

    if is_result and is_result.get('line_items'):
        is_control_items = find_is_control_items(is_result['line_items'])

        required_is = ['income_tax_expense', 'net_income', 'eps', 'eps_diluted']

        print(f"\n✓ Found {len(is_control_items)}/8 control items:")
        for item_name, line_num in sorted(is_control_items.items(), key=lambda x: x[1]):
            required_mark = " (REQUIRED)" if item_name in required_is else ""
            # Find the plabel and datatype for this line
            item = next((item for item in is_result['line_items']
                        if item.get('stmt_order') == line_num), None)
            if item:
                plabel = item['plabel']
                datatype = item.get('datatype', 'N/A')
                print(f"  [{line_num:3d}] {item_name}{required_mark}")
                print(f"        → {plabel} [datatype={datatype}]")

        # Check for missing required items
        missing_required = [item for item in required_is if item not in is_control_items]
        if missing_required:
            print(f"\n⚠️  MISSING REQUIRED ITEMS: {', '.join(missing_required)}")
        else:
            print(f"\n✅ All required control items found!")
    else:
        print("❌ Failed to reconstruct Income Statement")

    # =========================================================================
    # CASH FLOW
    # =========================================================================
    print("\n" + "=" * 100)
    print("CASH FLOW CONTROL ITEMS")
    print("=" * 100)

    cf_result = reconstructor.reconstruct_statement_multi_period(cik=cik, adsh=adsh, stmt_type='CF')

    if cf_result and cf_result.get('line_items'):
        cf_control_items = find_cf_control_items(cf_result['line_items'])

        required_cf = ['net_income', 'net_cash_provided_by_operating_activities',
                       'net_cash_provided_by_investing_activities',
                       'net_cash_provided_by_financing_activities',
                       'cash_at_beginning_of_period', 'cash_at_end_of_period']

        print(f"\n✓ Found {len(cf_control_items)}/6 control items:")
        for item_name, line_num in sorted(cf_control_items.items(), key=lambda x: x[1]):
            required_mark = " (REQUIRED)" if item_name in required_cf else ""
            # Find the plabel for this line
            plabel = next((item['plabel'] for item in cf_result['line_items']
                          if item.get('stmt_order') == line_num), "")
            print(f"  [{line_num:3d}] {item_name}{required_mark}")
            print(f"        → {plabel}")

        # Check for missing required items
        missing_required = [item for item in required_cf if item not in cf_control_items]
        if missing_required:
            print(f"\n⚠️  MISSING REQUIRED ITEMS: {', '.join(missing_required)}")
        else:
            print(f"\n✅ All required control items found!")
    else:
        print("❌ Failed to reconstruct Cash Flow")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)

    total_found = len(bs_control_items) + len(is_control_items) + len(cf_control_items)
    total_expected = 8 + 8 + 6  # BS + IS + CF

    print(f"\nTotal control items found: {total_found}/{total_expected}")
    print(f"  Balance Sheet: {len(bs_control_items)}/8")
    print(f"  Income Statement: {len(is_control_items)}/8")
    print(f"  Cash Flow: {len(cf_control_items)}/6")

    if total_found == total_expected:
        print("\n🎉 SUCCESS: All control items identified!")
    else:
        print(f"\n⚠️  WARNING: Missing {total_expected - total_found} control items")


if __name__ == "__main__":
    # Test on Microsoft
    test_control_items(
        cik='789019',
        adsh='0000950170-24-118967',
        year=2024,
        quarter=4
    )
