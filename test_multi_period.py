"""
Test Multi-Period Extraction

Tests the new multi-period extraction capability across all 4 test companies.
This validates:
- Period discovery using representative tags
- Multi-period value extraction
- Excel export with multiple period columns
"""

from src.statement_reconstructor import StatementReconstructor
from src.excel_exporter import ExcelExporter
from pathlib import Path

# Test companies
COMPANIES = [
    {
        'name': 'Amazon.com Inc',
        'cik': 1018724,
        'adsh': '0001018724-24-000130',
        'year': 2024,
        'quarter': 3,
        'filing': '10-Q Q2 2024'
    },
    {
        'name': 'The Home Depot Inc',
        'cik': 354950,
        'adsh': '0000354950-24-000201',
        'year': 2024,
        'quarter': 3,
        'filing': '10-Q Q2 2024'
    },
    {
        'name': 'Procter & Gamble Co',
        'cik': 80424,
        'adsh': '0000080424-24-000083',
        'year': 2024,
        'quarter': 3,
        'filing': '10-K FY 2024'
    },
    {
        'name': 'M&T Bank Corp',
        'cik': 36270,
        'adsh': '0001628280-24-034695',
        'year': 2024,
        'quarter': 3,
        'filing': '10-Q Q2 2024'
    }
]

def test_company(company):
    """Test multi-period extraction for one company"""
    print(f"\n{'='*80}")
    print(f"Testing: {company['name']} - {company['filing']}")
    print(f"{'='*80}")

    # Initialize reconstructor
    reconstructor = StatementReconstructor(company['year'], company['quarter'])

    # Reconstruct all statements with multi-period
    exporter = ExcelExporter()
    results = {}

    for stmt_type in ['BS', 'IS', 'CF']:
        print(f"\n--- {stmt_type} Statement ---")

        result = reconstructor.reconstruct_statement_multi_period(
            cik=company['cik'],
            adsh=company['adsh'],
            stmt_type=stmt_type
        )

        if result.get('line_items'):
            results[stmt_type] = result
            exporter.add_statement(stmt_type, result)

            # Print summary
            print(f"\nSummary:")
            print(f"  Periods discovered: {len(result.get('periods', []))}")
            if result.get('periods'):
                for p in result['periods']:
                    print(f"    - {p['label']}")

            print(f"  Line items: {len(result['line_items'])}")

            # Sample first line item to show multi-period values
            if result['line_items']:
                sample = result['line_items'][0]
                print(f"\n  Sample line item: {sample['plabel']}")
                if 'values' in sample:
                    for period_label, value in sample['values'].items():
                        print(f"    {period_label}: ${value:,.0f}")

        else:
            print(f"  Warning: No line items found for {stmt_type}")

    # Export to Excel
    output_dir = Path('output/multi_period')
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"{company['name'].replace(' ', '_').replace('.', '')}_multi_period.xlsx"

    exporter.export(
        str(output_file),
        company_name=company['name'],
        period=company['filing']
    )

    print(f"\n✅ Multi-period Excel export complete: {output_file}")

    return results


def main():
    """Test all companies"""
    print("="*80)
    print("MULTI-PERIOD EXTRACTION TEST")
    print("="*80)

    all_results = {}

    for company in COMPANIES:
        try:
            results = test_company(company)
            all_results[company['name']] = results
        except Exception as e:
            print(f"\n❌ Error processing {company['name']}: {e}")
            import traceback
            traceback.print_exc()
            continue

    # Summary
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")

    for company in COMPANIES:
        company_name = company['name']
        if company_name in all_results:
            print(f"\n✅ {company_name}")
            results = all_results[company_name]
            for stmt_type, result in results.items():
                num_periods = len(result.get('periods', []))
                num_items = len(result.get('line_items', []))
                print(f"   {stmt_type}: {num_periods} periods, {num_items} line items")
        else:
            print(f"\n❌ {company_name}: FAILED")

    print(f"\n{'='*80}")
    print("All multi-period Excel files exported to: output/multi_period/")
    print(f"{'='*80}")


if __name__ == '__main__':
    main()
