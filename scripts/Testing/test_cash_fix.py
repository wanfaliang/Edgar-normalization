"""
Test that the fix captures beginning/ending cash balances
"""
from src.statement_reconstructor import StatementReconstructor

print("=" * 80)
print("Testing Cash Balance Fix")
print("=" * 80)

reconstructor = StatementReconstructor(2024, 3)
result = reconstructor.reconstruct_statement(
    cik=1018724,
    adsh='0001018724-24-000130',
    stmt_type='CF'
)

print("\n" + "=" * 80)
print("CHECKING FOR CASH BALANCES")
print("=" * 80)

line_items = result['line_items']
print(f"\nTotal CF line items: {len(line_items)}")

# Look for cash balances
cash_keywords = ['BEGINNING', 'END OF PERIOD', 'beginning', 'end of period']
found_items = []

for item in line_items:
    plabel = item['plabel']
    if any(keyword in plabel for keyword in cash_keywords):
        found_items.append(item)
        print(f"\n✅ Found: {plabel}")
        print(f"   Value: ${item['value']:,.0f}")
        print(f"   Tag: {item['tag']}")
        print(f"   qtrs: {item['qtrs']} (should be '0' for instant)")
        print(f"   iord: {item['iord']} (should be 'I' for instant)")

if len(found_items) >= 2:
    print("\n" + "=" * 80)
    print("✅ SUCCESS: Both beginning and ending cash balances captured!")
    print("=" * 80)
elif len(found_items) == 1:
    print("\n" + "=" * 80)
    print("⚠️  PARTIAL: Only one cash balance found")
    print("=" * 80)
else:
    print("\n" + "=" * 80)
    print("❌ FAILED: No cash balances found")
    print("=" * 80)
