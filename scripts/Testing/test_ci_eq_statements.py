"""
Test Comprehensive Income (CI) and Equity (EQ) statements
Complete Phase 2 by validating all statement types
"""

from src.statement_reconstructor import StatementReconstructor
from src.excel_exporter import ExcelExporter
from pathlib import Path

COMPANIES = [
    {
        'name': 'Amazon.com Inc',
        'cik': 1018724,
        'adsh': '0001018724-24-000130',
        'year': 2024,
        'quarter': 3,
        'has_ci': True,
        'has_eq': False
    },
    {
        'name': 'The Home Depot Inc',
        'cik': 354950,
        'adsh': '0000354950-24-000201',
        'year': 2024,
        'quarter': 3,
        'has_ci': True,
        'has_eq': True
    },
    {
        'name': 'Procter & Gamble Co',
        'cik': 80424,
        'adsh': '0000080424-24-000083',
        'year': 2024,
        'quarter': 3,
        'has_ci': True,
        'has_eq': True
    },
    {
        'name': 'M&T Bank Corp',
        'cik': 36270,
        'adsh': '0001628280-24-034695',
        'year': 2024,
        'quarter': 3,
        'has_ci': True,
        'has_eq': True
    }
]

def test_statement(reconstructor, company, stmt_type):
    """Test a specific statement type"""
    print(f"\n--- {stmt_type} Statement ---")

    result = reconstructor.reconstruct_statement_multi_period(
        cik=company['cik'],
        adsh=company['adsh'],
        stmt_type=stmt_type
    )

    if 'error' in result:
        print(f"  ❌ Error: {result['error']}")
        return None

    periods = result.get('periods', [])
    line_items = result.get('line_items', [])

    print(f"\n  ✅ Success!")
    print(f"  Periods: {len(periods)}")
    for p in periods:
        print(f"    - {p['label']}")
    print(f"  Line items: {len(line_items)}")

    # Show sample line items
    if line_items:
        print(f"\n  Sample line items:")
        for item in line_items[:3]:
            print(f"    - {item['plabel']}")
            values_dict = item.get('values', {})
            if values_dict:
                # Show first value as example
                first_period, first_value = next(iter(values_dict.items()))
                print(f"      {first_period}: ${first_value:,.0f}")

    return result


def main():
    print("="*80)
    print("TESTING CI (COMPREHENSIVE INCOME) AND EQ (EQUITY) STATEMENTS")
    print("="*80)

    all_results = {}

    for company in COMPANIES:
        print(f"\n{'='*80}")
        print(f"{company['name']}")
        print(f"{'='*80}")

        reconstructor = StatementReconstructor(company['year'], company['quarter'])
        company_results = {}

        # Test CI statement
        if company['has_ci']:
            ci_result = test_statement(reconstructor, company, 'CI')
            if ci_result:
                company_results['CI'] = ci_result

        # Test EQ statement
        if company['has_eq']:
            eq_result = test_statement(reconstructor, company, 'EQ')
            if eq_result:
                company_results['EQ'] = eq_result

        # Export to Excel (CI and EQ together with BS, IS, CF)
        if company_results:
            print(f"\n  Exporting to Excel with all statements...")

            exporter = ExcelExporter()

            # Add all 5 statement types
            for stmt_type in ['BS', 'IS', 'CF', 'CI', 'EQ']:
                if stmt_type in ['BS', 'IS', 'CF']:
                    # Re-extract primary statements
                    result = reconstructor.reconstruct_statement_multi_period(
                        cik=company['cik'],
                        adsh=company['adsh'],
                        stmt_type=stmt_type
                    )
                    if result.get('line_items'):
                        exporter.add_statement(stmt_type, result)
                elif stmt_type in company_results:
                    # Add CI/EQ if available
                    exporter.add_statement(stmt_type, result=company_results[stmt_type])

            # Export to separate directory for complete statements
            output_dir = Path('output/complete_statements')
            output_dir.mkdir(parents=True, exist_ok=True)

            output_file = output_dir / f"{company['name'].replace(' ', '_').replace('.', '')}_complete.xlsx"

            exporter.export(
                str(output_file),
                company_name=company['name'],
                period=f"{company['year']} Q{company['quarter']}"
            )

            print(f"  ✅ Excel exported: {output_file}")

        all_results[company['name']] = company_results

    # Summary
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")

    for company in COMPANIES:
        company_name = company['name']
        print(f"\n{company_name}:")

        if company_name in all_results:
            results = all_results[company_name]

            if company['has_ci']:
                if 'CI' in results:
                    ci = results['CI']
                    print(f"  ✅ CI: {len(ci['periods'])} periods, {len(ci['line_items'])} items")
                else:
                    print(f"  ❌ CI: Failed")

            if company['has_eq']:
                if 'EQ' in results:
                    eq = results['EQ']
                    print(f"  ✅ EQ: {len(eq['periods'])} periods, {len(eq['line_items'])} items")
                else:
                    print(f"  ❌ EQ: Failed")
        else:
            print(f"  ❌ No results")

    print(f"\n{'='*80}")
    print("Complete financial statements (BS+IS+CF+CI+EQ) exported to: output/complete_statements/")
    print(f"{'='*80}")


if __name__ == '__main__':
    main()
