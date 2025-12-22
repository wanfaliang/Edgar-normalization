"""
Test Home Depot beginning cash - should be fixed now!
"""
from src.statement_reconstructor import StatementReconstructor

print("=" * 80)
print("Testing Home Depot Cash Balance Fix")
print("=" * 80)

reconstructor = StatementReconstructor(2024, 3)
result = reconstructor.reconstruct_statement(
    cik=354950,
    adsh='0000354950-24-000201',
    stmt_type='CF'
)

line_items = result['line_items']

print("\nSearching for cash balances...")
for item in line_items:
    plabel_lower = item['plabel'].lower()
    if 'beginning' in plabel_lower and 'period' in plabel_lower:
        print(f"\n✅ BEGINNING CASH:")
        print(f"   Label: {item['plabel']}")
        print(f"   Value: ${item['value']:,.0f}")
        print(f"   Date: {item['ddate']}")
        print(f"   Expected: 20240131 (Jan 31, 2024 - FY2024 start)")
        if item['ddate'] == '20240131':
            print(f"   ✅ CORRECT!")
        else:
            print(f"   ❌ WRONG! Got {item['ddate']}")

    elif 'end' in plabel_lower and 'period' in plabel_lower:
        print(f"\n✅ ENDING CASH:")
        print(f"   Label: {item['plabel']}")
        print(f"   Value: ${item['value']:,.0f}")
        print(f"   Date: {item['ddate']}")
        print(f"   Expected: 20240731 (Jul 31, 2024)")
        if item['ddate'] == '20240731':
            print(f"   ✅ CORRECT!")
        else:
            print(f"   ❌ WRONG! Got {item['ddate']}")

print("\n" + "=" * 80)
