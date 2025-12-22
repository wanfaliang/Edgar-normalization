"""
Comprehensive Validation Test
==============================

Tests fundamental accounting equations for all statement types:
1. Balance Sheet: Assets = Liabilities + Equity
2. Income Statement: Revenue - Expenses = Net Income
3. Cash Flow: Operating + Investing + Financing = Change in Cash
"""

from src.statement_reconstructor import StatementReconstructor, get_adsh_for_company
from src.statement_validator import StatementValidator


def test_company_full_validation(name: str, cik: int, year: int = 2024, quarter: int = 3):
    """Test all statements for a company with comprehensive validation"""

    print("\n" + "=" * 80)
    print(f"{name.upper()} - COMPREHENSIVE VALIDATION TEST")
    print("=" * 80)

    # Get filing
    adsh = get_adsh_for_company(cik, year, quarter)
    if not adsh:
        print(f"❌ No filing found for {name}")
        return

    print(f"CIK: {cik}, ADSH: {adsh}")

    # Initialize
    reconstructor = StatementReconstructor(year, quarter)
    validator = StatementValidator(tolerance_pct=0.01)

    # Reconstruct all statements
    statements = {}
    for stmt_code, stmt_name in [('BS', 'Balance Sheet'), ('IS', 'Income Statement'), ('CF', 'Cash Flow')]:
        result = reconstructor.reconstruct_statement(cik, adsh, stmt_code)
        if result.get('hierarchy'):
            statements[stmt_code] = result['flat_data']
            print(f"\n✅ {stmt_name}: {len(result['flat_data'])} line items")
        else:
            print(f"\n❌ {stmt_name}: Failed to reconstruct")
            statements[stmt_code] = {}

    # Validate Balance Sheet
    if statements['BS']:
        print("\n" + "-" * 80)
        print("BALANCE SHEET VALIDATION")
        print("-" * 80)

        bs_result = validator.validate_balance_sheet(statements['BS'])

        for equation in bs_result.equations_checked:
            status = "✅" if equation in bs_result.equations_passed else "❌"
            print(f"  {status} {equation}")

        if bs_result.equations_failed:
            for error in bs_result.equations_failed:
                print(f"\n  ❌ FAILED: {error['equation']}")
                print(f"     Left:  ${error['left']:,.0f}")
                print(f"     Right: ${error['right']:,.0f}")
                print(f"     Diff:  ${error['diff']:,.0f} ({error.get('diff_pct', 0):.4f}%)")

        if bs_result.warnings:
            for warning in bs_result.warnings:
                print(f"  ⚠️  {warning}")

        print(f"\n  Overall: {'✅ VALID' if bs_result.valid else '❌ INVALID'}")

    # Validate Income Statement
    if statements['IS']:
        print("\n" + "-" * 80)
        print("INCOME STATEMENT VALIDATION")
        print("-" * 80)

        is_result = validator.validate_income_statement(statements['IS'])

        for equation in is_result.equations_checked:
            status = "✅" if equation in is_result.equations_passed else "❌"
            print(f"  {status} {equation}")

        if is_result.equations_failed:
            for error in is_result.equations_failed:
                print(f"\n  ❌ FAILED: {error['equation']}")
                print(f"     Left:  ${error['left']:,.0f}")
                print(f"     Right: ${error['right']:,.0f}")
                print(f"     Diff:  ${error['diff']:,.0f} ({error.get('diff_pct', 0):.4f}%)")

        if is_result.warnings:
            for warning in is_result.warnings:
                print(f"  ⚠️  {warning}")

        print(f"\n  Overall: {'✅ VALID' if is_result.valid else '❌ INVALID'}")

    # Validate Cash Flow Statement
    if statements['CF']:
        print("\n" + "-" * 80)
        print("CASH FLOW STATEMENT VALIDATION")
        print("-" * 80)

        cf_result = validator.validate_cash_flow_statement(statements['CF'])

        for equation in cf_result.equations_checked:
            status = "✅" if equation in cf_result.equations_passed else "❌"
            print(f"  {status} {equation}")

        if cf_result.equations_failed:
            for error in cf_result.equations_failed:
                print(f"\n  ❌ FAILED: {error['equation']}")
                print(f"     Left:  ${error['left']:,.0f}")
                print(f"     Right: ${error['right']:,.0f}")
                print(f"     Diff:  ${error['diff']:,.0f} ({error.get('diff_pct', 0):.4f}%)")

        if cf_result.warnings:
            for warning in cf_result.warnings:
                print(f"  ⚠️  {warning}")

        print(f"\n  Overall: {'✅ VALID' if cf_result.valid else '❌ INVALID'}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    bs_valid = validator.validate_balance_sheet(statements['BS']).valid if statements['BS'] else False
    is_valid = validator.validate_income_statement(statements['IS']).valid if statements['IS'] else False
    cf_valid = validator.validate_cash_flow_statement(statements['CF']).valid if statements['CF'] else False

    print(f"  Balance Sheet:     {'✅ VALID' if bs_valid else '❌ INVALID'}")
    print(f"  Income Statement:  {'✅ VALID' if is_valid else '❌ INVALID'}")
    print(f"  Cash Flow:         {'✅ VALID' if cf_valid else '❌ INVALID'}")

    all_valid = bs_valid and is_valid and cf_valid
    print(f"\n  All Statements:    {'✅ ALL VALID' if all_valid else '❌ SOME INVALID'}")

    return all_valid


if __name__ == '__main__':
    print("=" * 80)
    print("COMPREHENSIVE FINANCIAL STATEMENT VALIDATION")
    print("Testing fundamental accounting equations across multiple companies")
    print("=" * 80)

    test_companies = [
        ('Amazon', 1018724),
        ('Home Depot', 354950),
        ('Procter & Gamble', 80424),
        ('M&T Bank', 36270),
    ]

    results = {}
    for name, cik in test_companies:
        results[name] = test_company_full_validation(name, cik)

    # Final Summary
    print("\n\n" + "=" * 80)
    print("FINAL SUMMARY - ALL COMPANIES")
    print("=" * 80)

    for name, valid in results.items():
        status = "✅ ALL VALID" if valid else "❌ SOME INVALID"
        print(f"  {name:<20} {status}")

    all_companies_valid = all(results.values())
    print("\n" + "=" * 80)
    if all_companies_valid:
        print("🎉 SUCCESS: All companies pass all validation equations!")
    else:
        print("⚠️  Some companies have validation issues - see details above")
    print("=" * 80)
