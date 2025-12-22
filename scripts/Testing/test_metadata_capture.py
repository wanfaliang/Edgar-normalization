"""
Test that the updated StatementReconstructor captures all metadata fields
"""
from src.statement_reconstructor import StatementReconstructor
import pandas as pd

print("=" * 80)
print("Testing Metadata Capture in StatementReconstructor")
print("=" * 80)

# Test with Amazon Q2 2024
reconstructor = StatementReconstructor(2024, 3)
result = reconstructor.reconstruct_statement(
    cik=1018724,
    adsh='0001018724-24-000130',
    stmt_type='BS'
)

print("\n" + "=" * 80)
print("TESTING LINE ITEMS OUTPUT")
print("=" * 80)

if 'line_items' in result:
    line_items = result['line_items']
    print(f"\nTotal line items: {len(line_items)}")

    # Show first 3 line items with all metadata
    print("\nFirst 3 line items with full metadata:")
    for i, item in enumerate(line_items[:3]):
        print(f"\n--- Line Item {i+1} ---")
        for key, value in item.items():
            if value is not None and not pd.isna(value):
                if key == 'value':
                    print(f"  {key}: ${value:,.0f}")
                else:
                    print(f"  {key}: {value}")

    # Check that all expected fields are present
    print("\n" + "=" * 80)
    print("FIELD VALIDATION")
    print("=" * 80)

    expected_fields = [
        # Core
        'tag', 'plabel',
        # PRE
        'stmt', 'report', 'line', 'inpth', 'negating',
        # NUM
        'value', 'ddate', 'qtrs', 'uom', 'segments', 'coreg',
        # TAG
        'custom', 'tlabel', 'datatype', 'iord', 'crdr'
    ]

    first_item = line_items[0]
    missing_fields = []
    present_fields = []

    for field in expected_fields:
        if field in first_item:
            present_fields.append(field)
        else:
            missing_fields.append(field)

    print(f"\n✅ Present fields ({len(present_fields)}/{len(expected_fields)}):")
    for field in present_fields:
        print(f"  - {field}")

    if missing_fields:
        print(f"\n❌ Missing fields ({len(missing_fields)}):")
        for field in missing_fields:
            print(f"  - {field}")
    else:
        print("\n✅ All expected fields are present!")

    # Check specific critical fields have values
    print("\n" + "=" * 80)
    print("CRITICAL FIELD VALUES CHECK")
    print("=" * 80)

    sample_item = line_items[0]
    print(f"\nSample: {sample_item['plabel']}")
    print(f"  tag: {sample_item['tag']}")
    print(f"  value: ${sample_item['value']:,.0f}")
    print(f"  ddate: {sample_item['ddate']}")
    print(f"  qtrs: {sample_item['qtrs']}")
    print(f"  stmt: {sample_item['stmt']}")
    print(f"  report: {sample_item['report']}")
    print(f"  line: {sample_item['line']}")
    print(f"  custom: {sample_item['custom']}")
    print(f"  tlabel: {sample_item['tlabel'][:50] if sample_item['tlabel'] else None}...")

    # Verify segments and coreg are NaN (consolidated, parent company)
    print("\n" + "=" * 80)
    print("CONSOLIDATION CHECK")
    print("=" * 80)

    segments_check = all(pd.isna(item['segments']) or item['segments'] is None for item in line_items)
    coreg_check = all(pd.isna(item['coreg']) or item['coreg'] is None for item in line_items)

    print(f"  All segments are NaN: {segments_check} ✅" if segments_check else f"  Some segments are NOT NaN: ❌")
    print(f"  All coreg are NaN: {coreg_check} ✅" if coreg_check else f"  Some coreg are NOT NaN: ❌")

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

    if missing_fields:
        print("\n❌ FAIL: Some fields are missing")
    elif not segments_check or not coreg_check:
        print("\n⚠️  WARNING: Consolidation check failed")
    else:
        print("\n✅ SUCCESS: All metadata fields captured correctly!")
else:
    print("\n❌ ERROR: 'line_items' not found in result")
    print(f"Available keys: {result.keys()}")
