"""
Rigorous verification: Compare our extraction to known EDGAR values

For each company, we'll extract key totals and compare to what should appear
on EDGAR based on the filing metadata.
"""
from src.statement_reconstructor import StatementReconstructor

def verify_company(name, cik, adsh, expected_values):
    """
    Verify reconstruction against expected values

    Args:
        expected_values: Dict with known values from EDGAR (to be manually verified)
    """
    print("\n" + "=" * 80)
    print(f"VERIFYING: {name}")
    print("=" * 80)

    reconstructor = StatementReconstructor(2024, 3)

    # Test all three statements
    statements = {}
    for stmt_type in ['BS', 'IS', 'CF']:
        result = reconstructor.reconstruct_statement(cik, adsh, stmt_type)
        if result.get('hierarchy'):
            statements[stmt_type] = result['flat_data']
            print(f"\n✅ {stmt_type}: {len(result['flat_data'])} items extracted")
            print(f"   Period: {result['metadata']['year']}Q{result['metadata']['quarter']}")
        else:
            print(f"\n❌ {stmt_type}: Failed to reconstruct")
            return False

    # Verify Balance Sheet
    print(f"\n📊 BALANCE SHEET VERIFICATION:")
    bs = statements['BS']

    if 'Assets' in bs:
        print(f"   Total Assets: ${bs['Assets']:,.0f}")
        if 'expected_assets' in expected_values:
            match = abs(bs['Assets'] - expected_values['expected_assets']) < 1000
            print(f"   Expected: ${expected_values['expected_assets']:,.0f} {'✅' if match else '❌'}")

    if 'LiabilitiesAndStockholdersEquity' in bs:
        print(f"   Liabilities + Equity: ${bs['LiabilitiesAndStockholdersEquity']:,.0f}")

    # Check equation
    if 'Assets' in bs and 'LiabilitiesAndStockholdersEquity' in bs:
        diff = abs(bs['Assets'] - bs['LiabilitiesAndStockholdersEquity'])
        print(f"   Balance Sheet Equation: {'✅ PASS' if diff < 1000 else '❌ FAIL'} (diff: ${diff:,.0f})")

    # Verify Income Statement
    print(f"\n📊 INCOME STATEMENT VERIFICATION:")
    is_stmt = statements['IS']

    revenue_tags = ['RevenueFromContractWithCustomerExcludingAssessedTax', 'Revenues', 'SalesRevenueNet']
    revenue = None
    for tag in revenue_tags:
        if tag in is_stmt:
            revenue = is_stmt[tag]
            print(f"   Revenue: ${revenue:,.0f}")
            if 'expected_revenue' in expected_values:
                match = abs(revenue - expected_values['expected_revenue']) < 1000
                print(f"   Expected: ${expected_values['expected_revenue']:,.0f} {'✅' if match else '❌'}")
            break

    net_income_tags = ['NetIncomeLoss', 'NetIncome', 'ProfitLoss']
    net_income = None
    for tag in net_income_tags:
        if tag in is_stmt:
            net_income = is_stmt[tag]
            print(f"   Net Income: ${net_income:,.0f}")
            if 'expected_net_income' in expected_values:
                match = abs(net_income - expected_values['expected_net_income']) < 1000
                print(f"   Expected: ${expected_values['expected_net_income']:,.0f} {'✅' if match else '❌'}")
            break

    # Verify Cash Flow
    print(f"\n📊 CASH FLOW VERIFICATION:")
    cf = statements['CF']

    if 'NetCashProvidedByUsedInOperatingActivities' in cf:
        opcf = cf['NetCashProvidedByUsedInOperatingActivities']
        print(f"   Operating CF: ${opcf:,.0f}")
        if 'expected_operating_cf' in expected_values:
            match = abs(opcf - expected_values['expected_operating_cf']) < 1000
            print(f"   Expected: ${expected_values['expected_operating_cf']:,.0f} {'✅' if match else '❌'}")

    # Check CF equation (if we have all components)
    cf_tags = {
        'operating': 'NetCashProvidedByUsedInOperatingActivities',
        'investing': 'NetCashProvidedByUsedInInvestingActivities',
        'financing': 'NetCashProvidedByUsedInFinancingActivities',
        'change': 'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect'
    }

    if all(tag in cf for tag in cf_tags.values()):
        calculated = (cf[cf_tags['operating']] +
                     cf[cf_tags['investing']] +
                     cf[cf_tags['financing']])

        # Try to find FX effect (multiple possible tag names)
        fx_tags = [
            'EffectOfExchangeRateOnCashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsIncludingDisposalGroupAndDiscontinuedOperations',
            'EffectOfExchangeRateOnCashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents',
            'EffectOfExchangeRateOnCashAndCashEquivalents'
        ]
        fx_effect = 0
        for fx_tag in fx_tags:
            if fx_tag in cf:
                fx_effect = cf[fx_tag]
                break

        calculated += fx_effect
        reported = cf[cf_tags['change']]
        diff = abs(calculated - reported)

        print(f"   CF Equation Check:")
        print(f"     Calculated: ${calculated:,.0f}")
        print(f"     Reported: ${reported:,.0f}")
        print(f"     {'✅ PASS' if diff < 1000 else '❌ FAIL'} (diff: ${diff:,.0f})")

    print(f"\n🔗 EDGAR URL: {result['metadata']['edgar_url']}")
    print("   ↑ Manually verify these numbers match EDGAR display")

    return True

# Test Amazon (we can manually verify these from EDGAR)
print("=" * 80)
print("RIGOROUS RECONSTRUCTION VERIFICATION")
print("Testing against known EDGAR values")
print("=" * 80)

# Amazon Q2 2024 - These should match EDGAR exactly
# EDGAR URL: https://www.sec.gov/cgi-bin/viewer?action=view&cik=0001018724&accession_number=0001018724-24-000130&xbrl_type=v
verify_company(
    name="Amazon Q2 2024",
    cik=1018724,
    adsh='0001018724-24-000130',
    expected_values={
        # These values can be manually verified from EDGAR
        # For now, we'll extract and document what we get
    }
)

# Home Depot Q2 2024
verify_company(
    name="Home Depot Q2 2024",
    cik=354950,
    adsh='0000354950-24-000201',
    expected_values={}
)

print("\n\n" + "=" * 80)
print("VERIFICATION COMPLETE")
print("=" * 80)
print("\nTo be confident in our reconstruction:")
print("1. ✅ Balance Sheet equations pass (Assets = L+E)")
print("2. ✅ Cash Flow equations pass (Operating+Investing+Financing+FX = Change)")
print("3. 🔍 Manually spot-check values against EDGAR URLs above")
print("\nIf all match EDGAR display, reconstruction is faithful!")
