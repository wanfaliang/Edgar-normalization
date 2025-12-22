"""
Compare our extracted values to what appears on EDGAR
"""
from src.statement_reconstructor import StatementReconstructor

# Amazon Q2 2024
reconstructor = StatementReconstructor(2024, 3)

# Income Statement
is_result = reconstructor.reconstruct_statement(
    cik=1018724,
    adsh='0001018724-24-000130',
    stmt_type='IS'
)

print("=" * 80)
print("AMAZON Q2 2024 INCOME STATEMENT")
print("Comparing our extraction to EDGAR filing")
print("=" * 80)

is_data = is_result['flat_data']

print("\nOur Extracted Values:")
print(f"  Revenue: ${is_data.get('RevenueFromContractWithCustomerExcludingAssessedTax', 0):,.0f}")
print(f"  Cost of Sales: ${is_data.get('CostOfGoodsAndServicesSold', 0):,.0f}")
print(f"  Operating Income: ${is_data.get('OperatingIncomeLoss', 0):,.0f}")
print(f"  Income Before Tax: ${is_data.get('IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments', 0):,.0f}")
print(f"  Tax Expense: ${is_data.get('IncomeTaxExpenseBenefit', 0):,.0f}")
print(f"  Equity Method: ${is_data.get('IncomeLossFromEquityMethodInvestments', 0):,.0f}")
print(f"  Net Income: ${is_data.get('NetIncomeLoss', 0):,.0f}")

print("\n" + "=" * 80)
print("EDGAR URL to verify:")
print(is_result['metadata']['edgar_url'])
print("=" * 80)

print("\nIncome Statement structure check:")
print(f"  Revenue - Cost = Gross?: {is_data.get('RevenueFromContractWithCustomerExcludingAssessedTax', 0) - is_data.get('CostOfGoodsAndServicesSold', 0):,.0f}")
print(f"  (But Amazon doesn't report Gross Profit as a separate line)")

print(f"\n  Income Before Tax - Tax = {is_data.get('IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments', 0) - is_data.get('IncomeTaxExpenseBenefit', 0):,.0f}")
print(f"  But Net Income is: ${is_data.get('NetIncomeLoss', 0):,.0f}")
print(f"  Difference: Equity method investment activity: ${is_data.get('IncomeLossFromEquityMethodInvestments', 0):,.0f}")

print("\n" + "=" * 80)

# Cash Flow
cf_result = reconstructor.reconstruct_statement(
    cik=1018724,
    adsh='0001018724-24-000130',
    stmt_type='CF'
)

print("AMAZON Q2 2024 CASH FLOW STATEMENT")
print("=" * 80)

cf_data = cf_result['flat_data']

print("\nOur Extracted Values:")
print(f"  Operating CF: ${cf_data.get('NetCashProvidedByUsedInOperatingActivities', 0):,.0f}")
print(f"  Investing CF: ${cf_data.get('NetCashProvidedByUsedInInvestingActivities', 0):,.0f}")
print(f"  Financing CF: ${cf_data.get('NetCashProvidedByUsedInFinancingActivities', 0):,.0f}")
print(f"  FX Effect: ${cf_data.get('EffectOfExchangeRateOnCashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsIncludingDisposalGroupAndDiscontinuedOperations', 0):,.0f}")
print(f"  Change in Cash: ${cf_data.get('CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect', 0):,.0f}")

print("\nCash Flow equation check:")
sum_cf = (cf_data.get('NetCashProvidedByUsedInOperatingActivities', 0) +
          cf_data.get('NetCashProvidedByUsedInInvestingActivities', 0) +
          cf_data.get('NetCashProvidedByUsedInFinancingActivities', 0) +
          cf_data.get('EffectOfExchangeRateOnCashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsIncludingDisposalGroupAndDiscontinuedOperations', 0))
print(f"  Operating + Investing + Financing + FX = ${sum_cf:,.0f}")
print(f"  Reported Change in Cash = ${cf_data.get('CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect', 0):,.0f}")
print(f"  Difference: ${abs(sum_cf - cf_data.get('CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect', 0)):,.0f}")

print("\nQuestion: Does EDGAR show these same values?")
print("Check the URL above to verify!")
