"""
Test beginning cash in multi-period extraction

Checks if beginning and ending cash values are correctly extracted
for all periods.
"""

from src.statement_reconstructor import StatementReconstructor

print("="*80)
print("Testing Beginning/Ending Cash in Multi-Period Extraction")
print("="*80)

# Test with Amazon
reconstructor = StatementReconstructor(2024, 3)

result = reconstructor.reconstruct_statement_multi_period(
    cik=1018724,
    adsh='0001018724-24-000130',
    stmt_type='CF'
)

print(f"\nPeriods discovered: {len(result['periods'])}")
for p in result['periods']:
    print(f"  - {p['label']}")

print(f"\nLine items: {len(result['line_items'])}")

# Find beginning and ending cash
for item in result['line_items']:
    plabel_lower = item['plabel'].lower()

    if 'beginning' in plabel_lower and 'period' in plabel_lower:
        print(f"\n{'='*80}")
        print(f"BEGINNING CASH")
        print(f"{'='*80}")
        print(f"Label: {item['plabel']}")
        print(f"Tag: {item['tag']}")
        print(f"Values dict: {item.get('values', {})}")

        # Check raw node values
        print(f"\nBackward compatibility fields:")
        print(f"  value: {item.get('value')}")
        print(f"  ddate: {item.get('ddate')}")
        print(f"  qtrs: {item.get('qtrs')}")

    if 'end' in plabel_lower and 'period' in plabel_lower and 'beginning' not in plabel_lower:
        print(f"\n{'='*80}")
        print(f"ENDING CASH")
        print(f"{'='*80}")
        print(f"Label: {item['plabel']}")
        print(f"Tag: {item['tag']}")
        print(f"Values dict: {item.get('values', {})}")

        print(f"\nBackward compatibility fields:")
        print(f"  value: {item.get('value')}")
        print(f"  ddate: {item.get('ddate')}")
        print(f"  qtrs: {item.get('qtrs')}")

print(f"\n{'='*80}")
print("Test complete")
print(f"{'='*80}")
