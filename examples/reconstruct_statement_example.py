"""
Example: How to use StatementReconstructor

This example shows how to reconstruct financial statements from EDGAR data
for any company in the dataset.
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.statement_reconstructor import StatementReconstructor, get_adsh_for_company
import pandas as pd


def example_1_basic_usage():
    """Basic usage: Reconstruct Amazon's Balance Sheet"""
    print("=" * 80)
    print("EXAMPLE 1: Basic Usage")
    print("=" * 80)

    # Initialize reconstructor for 2024 Q3
    reconstructor = StatementReconstructor(year=2024, quarter=3)

    # Reconstruct Amazon's Balance Sheet
    result = reconstructor.reconstruct_statement(
        cik=1018724,  # Amazon
        adsh='0001018724-24-000130',
        stmt_type='BS'
    )

    # Access the data
    flat_data = result['flat_data']
    total_assets = flat_data['Assets']

    print(f"\nAmazon Total Assets: ${total_assets:,.0f}")
    print(f"Total line items: {len(flat_data)}")
    print(f"Validation: {'✅ PASS' if result['validation']['valid'] else '❌ FAIL'}")


def example_2_all_statements():
    """Reconstruct all statement types for a company"""
    print("\n\n" + "=" * 80)
    print("EXAMPLE 2: Reconstruct All Statement Types")
    print("=" * 80)

    reconstructor = StatementReconstructor(2024, 3)
    adsh = '0001018724-24-000130'  # Amazon

    statements = {
        'BS': 'Balance Sheet',
        'IS': 'Income Statement',
        'CF': 'Cash Flow Statement'
    }

    for stmt_code, stmt_name in statements.items():
        result = reconstructor.reconstruct_statement(
            cik=1018724,
            adsh=adsh,
            stmt_type=stmt_code
        )

        print(f"\n{stmt_name}:")
        print(f"  Line items: {len(result['flat_data'])}")
        print(f"  Validation: {'✅' if result['validation']['valid'] else '❌'}")


def example_3_find_company():
    """Find and reconstruct any company by CIK"""
    print("\n\n" + "=" * 80)
    print("EXAMPLE 3: Find Company by CIK")
    print("=" * 80)

    # Look up ADSH for Procter & Gamble
    cik = 80424
    adsh = get_adsh_for_company(cik, year=2024, quarter=3)

    if adsh:
        print(f"Found filing for CIK {cik}: {adsh}")

        reconstructor = StatementReconstructor(2024, 3)
        result = reconstructor.reconstruct_statement(cik=cik, adsh=adsh, stmt_type='BS')

        flat = result['flat_data']
        print(f"\nTotal Assets: ${flat['Assets']:,.0f}")
        print(f"Stockholders Equity: ${flat['StockholdersEquity']:,.0f}")
        print(f"EDGAR Viewer: {result['metadata']['edgar_url']}")


def example_4_compare_companies():
    """Compare key metrics across multiple companies"""
    print("\n\n" + "=" * 80)
    print("EXAMPLE 4: Compare Multiple Companies")
    print("=" * 80)

    companies = [
        {'name': 'Amazon', 'cik': 1018724},
        {'name': 'Home Depot', 'cik': 354950},
        {'name': 'P&G', 'cik': 80424},
    ]

    reconstructor = StatementReconstructor(2024, 3)

    print(f"\n{'Company':<15} {'Total Assets':>20} {'Equity':>20}")
    print("-" * 60)

    for company in companies:
        adsh = get_adsh_for_company(company['cik'], 2024, 3)
        if adsh:
            result = reconstructor.reconstruct_statement(
                cik=company['cik'],
                adsh=adsh,
                stmt_type='BS'
            )

            flat = result['flat_data']
            assets = flat['Assets']
            equity = flat.get('StockholdersEquity', 0)

            print(f"{company['name']:<15} ${assets:>18,.0f} ${equity:>18,.0f}")


def example_5_validation():
    """Check validation and balance sheet equation"""
    print("\n\n" + "=" * 80)
    print("EXAMPLE 5: Validation and Balance Sheet Equation")
    print("=" * 80)

    reconstructor = StatementReconstructor(2024, 3)
    result = reconstructor.reconstruct_statement(
        cik=1018724,
        adsh='0001018724-24-000130',
        stmt_type='BS'
    )

    flat = result['flat_data']
    validation = result['validation']

    # Check balance sheet equation: A = L + E
    assets = flat['Assets']
    liab_and_equity = flat['LiabilitiesAndStockholdersEquity']

    print("\nBalance Sheet Equation Check:")
    print(f"  Assets:                    ${assets:>20,.0f}")
    print(f"  Liabilities + Equity:      ${liab_and_equity:>20,.0f}")
    print(f"  Difference:                ${abs(assets - liab_and_equity):>20,.0f}")
    print(f"  Valid: {assets == liab_and_equity}")

    print(f"\nValidation Results:")
    print(f"  Errors: {len(validation['errors'])}")
    print(f"  Warnings: {len(validation['warnings'])}")


def example_6_hierarchy():
    """Print statement hierarchy"""
    print("\n\n" + "=" * 80)
    print("EXAMPLE 6: Print Statement Hierarchy")
    print("=" * 80)

    reconstructor = StatementReconstructor(2024, 3)
    result = reconstructor.reconstruct_statement(
        cik=1018724,
        adsh='0001018724-24-000130',
        stmt_type='IS'  # Income Statement
    )

    print("\nIncome Statement Hierarchy:")
    reconstructor.print_hierarchy(result['hierarchy'], max_depth=2)


if __name__ == '__main__':
    # Run all examples
    example_1_basic_usage()
    example_2_all_statements()
    example_3_find_company()
    example_4_compare_companies()
    example_5_validation()
    example_6_hierarchy()

    print("\n\n" + "=" * 80)
    print("All examples completed!")
    print("=" * 80)
