"""
Test Pattern Parser v2 with New Operators
==========================================
Tests the extended pattern parser with position_before, position_after, datatype, and min operators.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from pattern_parser import parse_pattern

def test_position_before():
    """Test position_before # operator"""
    print("\n=== Test position_before # ===")

    pattern = "[contains 'other'] and [position_before # accounts_receivables]"
    label = "Other current assets"

    # Test with proper context
    context = {
        'line_num': 5,
        'target_line_numbers': {
            'accounts_receivables': 10,
            'inventory': 12
        }
    }

    result = parse_pattern(pattern, label, context)
    print(f"Pattern: {pattern}")
    print(f"Label: {label}")
    print(f"Context: line_num={context['line_num']}, accounts_receivables at line 10")
    print(f"Result: {result} (expected: True)")

    # Test when position is after
    context['line_num'] = 15
    result = parse_pattern(pattern, label, context)
    print(f"\nWith line_num=15 (after accounts_receivables)")
    print(f"Result: {result} (expected: False)")


def test_position_after():
    """Test position_after # operator"""
    print("\n=== Test position_after # ===")

    pattern = "[contains 'investments'] and [position_after # total_current_assets]"
    label = "Long-term investments"

    context = {
        'line_num': 20,
        'target_line_numbers': {
            'total_current_assets': 15
        }
    }

    result = parse_pattern(pattern, label, context)
    print(f"Pattern: {pattern}")
    print(f"Label: {label}")
    print(f"Context: line_num={context['line_num']}, total_current_assets at line 15")
    print(f"Result: {result} (expected: True)")


def test_position_or():
    """Test position_before with OR logic"""
    print("\n=== Test position_before with OR ===")

    pattern = "[equals to 'other, net' or equals to 'other'] and [position_before # accounts_receivables or position_before # inventory or position_before # accounts_payables]"
    label = "Other, net"

    context = {
        'line_num': 8,
        'target_line_numbers': {
            'accounts_receivables': 10,
            'inventory': 12,
            'accounts_payables': 14
        }
    }

    result = parse_pattern(pattern, label, context)
    print(f"Pattern: {pattern}")
    print(f"Label: {label}")
    print(f"Result: {result} (expected: True)")


def test_datatype():
    """Test datatype = operator"""
    print("\n=== Test datatype = ===")

    pattern = "[contains 'basic'] and [datatype = perShare]"
    label = "Earnings per share - Basic"

    context = {
        'datatype': 'perShare'
    }

    result = parse_pattern(pattern, label, context)
    print(f"Pattern: {pattern}")
    print(f"Label: {label}")
    print(f"Context: datatype={context['datatype']}")
    print(f"Result: {result} (expected: True)")

    # Test with wrong datatype
    context['datatype'] = 'shares'
    result = parse_pattern(pattern, label, context)
    print(f"\nWith datatype='shares'")
    print(f"Result: {result} (expected: False)")


def test_min_selector():
    """Test min{} selector"""
    print("\n=== Test min{} selector ===")

    pattern = "min{[contains 'basic'] and [datatype = perShare]}"
    label = "Earnings per share - Basic"

    context = {
        'datatype': 'perShare'
    }

    result = parse_pattern(pattern, label, context)
    print(f"Pattern: {pattern}")
    print(f"Label: {label}")
    print(f"Result: {result} (expected: True)")
    print(f"Context flag '_select_min': {context.get('_select_min', False)} (expected: True)")


def test_complex_pattern():
    """Test complex pattern with multiple operators"""
    print("\n=== Test Complex Pattern ===")

    pattern = "min{[(contains 'account' or contains 'accounts') and (contains 'receivable' or contains 'receivables')] or [(contains 'trade') and (contains 'receivables')]}"
    label = "Trade accounts receivable"

    context = {}

    result = parse_pattern(pattern, label, context)
    print(f"Pattern: {pattern}")
    print(f"Label: {label}")
    print(f"Result: {result} (expected: True)")


if __name__ == "__main__":
    print("="*80)
    print("PATTERN PARSER V2 - NEW OPERATORS TEST")
    print("="*80)

    test_position_before()
    test_position_after()
    test_position_or()
    test_datatype()
    test_min_selector()
    test_complex_pattern()

    print("\n" + "="*80)
    print("ALL TESTS COMPLETED")
    print("="*80)
