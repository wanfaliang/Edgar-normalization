"""
Test Home Depot beginning cash in multi-period extraction
Verify fiscal year fix still works
"""

from src.statement_reconstructor import StatementReconstructor

print("="*80)
print("Testing Home Depot Beginning Cash (Fiscal Year Feb-Jan)")
print("="*80)

reconstructor = StatementReconstructor(2024, 3)

result = reconstructor.reconstruct_statement_multi_period(
    cik=354950,
    adsh='0000354950-24-000201',
    stmt_type='CF'
)

print(f"\nPeriods discovered: {len(result['periods'])}")
for p in result['periods']:
    print(f"  - {p['label']}")

# Find beginning and ending cash
for item in result['line_items']:
    plabel_lower = item['plabel'].lower()

    if 'beginning' in plabel_lower and 'cash' in plabel_lower:
        print(f"\n{'='*80}")
        print(f"BEGINNING CASH")
        print(f"{'='*80}")
        print(f"Label: {item['plabel']}")

        values_dict = item.get('values', {})
        for period_label, value in values_dict.items():
            print(f"  {period_label}: ${value:,.0f}")

        # Expected values for fiscal year (Feb-Jan):
        print(f"\nExpected:")
        print(f"  Six Months Ended Jul 31, 2024: Should start from Jan 31, 2024 (FY2024 start)")
        print(f"  Six Months Ended Jul 31, 2023: Should start from Jan 31, 2023 (FY2023 start)")

    if 'end' in plabel_lower and 'cash' in plabel_lower and 'beginning' not in plabel_lower:
        print(f"\n{'='*80}")
        print(f"ENDING CASH")
        print(f"{'='*80}")
        print(f"Label: {item['plabel']}")

        values_dict = item.get('values', {})
        for period_label, value in values_dict.items():
            print(f"  {period_label}: ${value:,.0f}")

print(f"\n{'='*80}")
print("✅ Home Depot fiscal year test complete")
print(f"{'='*80}")
