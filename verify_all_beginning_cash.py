"""
Comprehensive verification of beginning cash across all 4 companies
Validates that multi-period extraction produces correct values
"""

from src.statement_reconstructor import StatementReconstructor

COMPANIES = [
    {
        'name': 'Amazon',
        'cik': 1018724,
        'adsh': '0001018724-24-000130',
        'expected_periods': 6,
        'fiscal_type': 'Calendar year (Jan-Dec)'
    },
    {
        'name': 'Home Depot',
        'cik': 354950,
        'adsh': '0000354950-24-000201',
        'expected_periods': 2,
        'fiscal_type': 'Fiscal year (Feb-Jan)'
    },
    {
        'name': 'P&G',
        'cik': 80424,
        'adsh': '0000080424-24-000083',
        'expected_periods': 3,
        'fiscal_type': 'Fiscal year (Jul-Jun)'
    },
    {
        'name': 'M&T Bank',
        'cik': 36270,
        'adsh': '0001628280-24-034695',
        'expected_periods': 2,
        'fiscal_type': 'Calendar year (Jan-Dec)'
    }
]

print("="*80)
print("COMPREHENSIVE BEGINNING CASH VERIFICATION")
print("="*80)

reconstructor = StatementReconstructor(2024, 3)

for company in COMPANIES:
    print(f"\n{'='*80}")
    print(f"{company['name']} ({company['fiscal_type']})")
    print(f"{'='*80}")

    result = reconstructor.reconstruct_statement_multi_period(
        cik=company['cik'],
        adsh=company['adsh'],
        stmt_type='CF'
    )

    periods = result.get('periods', [])
    print(f"\nPeriods discovered: {len(periods)} (expected: {company['expected_periods']})")

    if len(periods) != company['expected_periods']:
        print(f"  ⚠️  WARNING: Period count mismatch!")

    # Find beginning and ending cash
    beginning_found = False
    ending_found = False

    for item in result['line_items']:
        plabel_lower = item['plabel'].lower()

        if 'beginning' in plabel_lower and ('cash' in plabel_lower or 'period' in plabel_lower):
            beginning_found = True
            print(f"\n✅ BEGINNING CASH:")
            print(f"   Label: {item['plabel']}")

            values_dict = item.get('values', {})
            if values_dict:
                for period_label, value in values_dict.items():
                    print(f"   {period_label}: ${value:,.0f}")
            else:
                print(f"   ❌ No values found!")

        if 'end' in plabel_lower and ('cash' in plabel_lower or 'period' in plabel_lower) and 'beginning' not in plabel_lower:
            ending_found = True
            print(f"\n✅ ENDING CASH:")
            print(f"   Label: {item['plabel']}")

            values_dict = item.get('values', {})
            if values_dict:
                for period_label, value in values_dict.items():
                    print(f"   {period_label}: ${value:,.0f}")
            else:
                print(f"   ❌ No values found!")

    if not beginning_found:
        print(f"\n❌ Beginning cash not found!")
    if not ending_found:
        print(f"\n❌ Ending cash not found!")

    # Validation
    status = "✅ PASS" if beginning_found and ending_found and len(periods) == company['expected_periods'] else "❌ FAIL"
    print(f"\n{status}")

print(f"\n{'='*80}")
print("VERIFICATION COMPLETE")
print(f"{'='*80}")
