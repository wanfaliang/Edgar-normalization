"""Test the pattern parser with examples from CSV"""
import sys
sys.path.insert(0, 'src')

from pattern_parser import parse_pattern

# Test cases from the CSV
tests = [
    # Simple contains with OR
    ("[contains 'net income' or 'net earnings' or 'net income (loss)']", "Net income", True),
    ("[contains 'net income' or 'net earnings']", "Net earnings", True),
    ("[contains 'net income' or 'net earnings']", "Revenue", False),

    # Contains with AND
    ("[contains 'depreciation' and contains 'amortization']", "Depreciation and amortization", True),
    ("[contains 'depreciation' and contains 'amortization']", "Depreciation only", False),

    # Contains with grouped OR and AND
    ("[contains 'deferred' and (contains 'tax' or contains 'taxes')]", "Deferred income taxes", True),
    ("[contains 'deferred' and (contains 'tax' or contains 'taxes')]", "Deferred tax", True),
    ("[contains 'deferred' and (contains 'tax' or contains 'taxes')]", "Deferred income", False),

    # Complex grouped OR with AND
    ("[(contains 'account' or contains 'accounts') and (contains 'receivable' or contains 'receivables')]",
     "Accounts receivable", True),
    ("[(contains 'account' or contains 'accounts') and (contains 'receivable' or contains 'receivables')]",
     "Account receivable", True),
    ("[(contains 'account' or contains 'accounts') and (contains 'receivable' or contains 'receivables')]",
     "Accounts payable", False),

    # Pattern with multiple alternatives using ] or [
    ("[(contains 'treasury' or contains 'share' or contains 'stock' or contains 'stocks') and (contains 'purchases' or contains 'purchase')] or [contains 'repurchase' or contains 'repurchases' or contains 'repurchased']",
     "Treasury stock purchases", True),
    ("[(contains 'treasury' or contains 'share' or contains 'stock' or contains 'stocks') and (contains 'purchases' or contains 'purchase')] or [contains 'repurchase' or contains 'repurchases' or contains 'repurchased']",
     "Common stock repurchased", True),
    ("[(contains 'treasury' or contains 'share' or contains 'stock' or contains 'stocks') and (contains 'purchases' or contains 'purchase')] or [contains 'repurchase' or contains 'repurchases' or contains 'repurchased']",
     "Stock issuance", False),

    # Equals to
    ("[equals to 'other, net' or equals to 'other']", "Other, net", True),
    ("[equals to 'other, net' or equals to 'other']", "Other", True),
    ("[equals to 'other, net' or equals to 'other']", "Other income", False),
]

print("Testing Pattern Parser")
print("=" * 80)

passed = 0
failed = 0

for pattern, label, expected in tests:
    result = parse_pattern(pattern, label)
    status = "✓" if result == expected else "✗"

    if result == expected:
        passed += 1
    else:
        failed += 1
        print(f"\n{status} FAILED:")
        print(f"  Pattern: {pattern[:80]}...")
        print(f"  Label: {label}")
        print(f"  Expected: {expected}, Got: {result}")

print(f"\n{passed} passed, {failed} failed out of {len(tests)} tests")

if failed == 0:
    print("\n✓ All tests passed!")
