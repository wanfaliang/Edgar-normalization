"""
Statement Validator - Fundamental Accounting Equations
=======================================================

Validates financial statements using fundamental accounting principles:
1. Balance Sheet: Assets = Liabilities + Equity
2. Income Statement: Revenue - Expenses = Net Income
3. Cash Flow: Operating + Investing + Financing = Change in Cash

These validations work for flat statements (most common in EDGAR data)
and provide stronger guarantees than just parent-child rollup validation.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of statement validation"""
    statement_type: str
    valid: bool
    equations_checked: List[str]
    equations_passed: List[str]
    equations_failed: List[Dict]
    warnings: List[str]

    def __str__(self):
        status = "✅ VALID" if self.valid else "❌ INVALID"
        return f"""
Validation Result: {status}
Statement Type: {self.statement_type}
Equations Checked: {len(self.equations_checked)}
Equations Passed: {len(self.equations_passed)}
Equations Failed: {len(self.equations_failed)}
Warnings: {len(self.warnings)}
"""


class StatementValidator:
    """
    Validates financial statements using accounting equations

    Usage:
        validator = StatementValidator()
        result = validator.validate_balance_sheet(flat_data)
        print(result)
    """

    def __init__(self, tolerance_pct: float = 0.01):
        """
        Initialize validator

        Args:
            tolerance_pct: Acceptable difference percentage (default 0.01%)
        """
        self.tolerance_pct = tolerance_pct

    def _check_equation(self, left: float, right: float, equation: str) -> Tuple[bool, Optional[Dict]]:
        """
        Check if left == right within tolerance

        Returns:
            (is_valid, error_dict if invalid)
        """
        if left is None or right is None:
            return False, {
                'equation': equation,
                'reason': 'Missing values',
                'left': left,
                'right': right
            }

        diff = abs(left - right)

        # Avoid division by zero
        if right == 0:
            if diff < 1000:  # Allow $1000 rounding for zero values
                return True, None
            else:
                return False, {
                    'equation': equation,
                    'left': left,
                    'right': right,
                    'diff': diff,
                    'reason': 'Right side is zero'
                }

        diff_pct = (diff / abs(right)) * 100

        if diff_pct <= self.tolerance_pct:
            return True, None
        else:
            return False, {
                'equation': equation,
                'left': left,
                'right': right,
                'diff': diff,
                'diff_pct': diff_pct
            }

    def validate_balance_sheet(self, flat_data: Dict[str, float]) -> ValidationResult:
        """
        Validate Balance Sheet using fundamental equation:
        Assets = Liabilities + Equity

        Also checks:
        - Assets = Current Assets + Noncurrent Assets
        - Liabilities = Current Liabilities + Noncurrent Liabilities

        Args:
            flat_data: Dict of tag->value from reconstructed statement

        Returns:
            ValidationResult
        """
        equations_checked = []
        equations_passed = []
        equations_failed = []
        warnings = []

        # Main equation: Assets = Liabilities + Equity
        assets = flat_data.get('Assets')
        liabilities = flat_data.get('Liabilities')
        equity = flat_data.get('StockholdersEquity')
        liab_and_equity = flat_data.get('LiabilitiesAndStockholdersEquity')

        if assets and liab_and_equity:
            equations_checked.append('Assets = Liabilities + Equity')
            valid, error = self._check_equation(
                assets,
                liab_and_equity,
                'Assets = LiabilitiesAndStockholdersEquity'
            )
            if valid:
                equations_passed.append('Assets = Liabilities + Equity')
            else:
                equations_failed.append(error)

        elif assets and liabilities and equity:
            equations_checked.append('Assets = Liabilities + Equity')
            valid, error = self._check_equation(
                assets,
                liabilities + equity,
                'Assets = Liabilities + StockholdersEquity'
            )
            if valid:
                equations_passed.append('Assets = Liabilities + Equity')
            else:
                equations_failed.append(error)
        else:
            warnings.append('Cannot validate main equation: missing Assets, Liabilities, or Equity')

        # Check: Total Assets = Current Assets + Noncurrent Assets
        current_assets = flat_data.get('AssetsCurrent')
        noncurrent_assets = flat_data.get('AssetsNoncurrent')

        if assets and current_assets and noncurrent_assets:
            equations_checked.append('Assets = Current + Noncurrent')
            valid, error = self._check_equation(
                assets,
                current_assets + noncurrent_assets,
                'Assets = AssetsCurrent + AssetsNoncurrent'
            )
            if valid:
                equations_passed.append('Assets = Current + Noncurrent')
            else:
                equations_failed.append(error)

        # Check: Total Liabilities = Current Liabilities + Noncurrent Liabilities
        current_liab = flat_data.get('LiabilitiesCurrent')
        noncurrent_liab = flat_data.get('LiabilitiesNoncurrent')

        if liabilities and current_liab and noncurrent_liab:
            equations_checked.append('Liabilities = Current + Noncurrent')
            valid, error = self._check_equation(
                liabilities,
                current_liab + noncurrent_liab,
                'Liabilities = LiabilitiesCurrent + LiabilitiesNoncurrent'
            )
            if valid:
                equations_passed.append('Liabilities = Current + Noncurrent')
            else:
                equations_failed.append(error)

        return ValidationResult(
            statement_type='Balance Sheet',
            valid=(len(equations_failed) == 0 and len(equations_checked) > 0),
            equations_checked=equations_checked,
            equations_passed=equations_passed,
            equations_failed=equations_failed,
            warnings=warnings
        )

    def validate_income_statement(self, flat_data: Dict[str, float]) -> ValidationResult:
        """
        Validate Income Statement using fundamental relationships:

        1. Gross Profit = Revenue - Cost of Revenue
        2. Operating Income = Gross Profit - Operating Expenses
        3. Income Before Tax = Operating Income + Non-Operating Income - Non-Operating Expenses
        4. Net Income = Income Before Tax - Tax Expense

        Args:
            flat_data: Dict of tag->value from reconstructed statement

        Returns:
            ValidationResult
        """
        equations_checked = []
        equations_passed = []
        equations_failed = []
        warnings = []

        # Get common income statement tags (with variations)
        revenue = (flat_data.get('Revenues') or
                  flat_data.get('RevenueFromContractWithCustomerExcludingAssessedTax') or
                  flat_data.get('SalesRevenueNet'))

        cost_of_revenue = (flat_data.get('CostOfRevenue') or
                          flat_data.get('CostOfGoodsAndServicesSold') or
                          flat_data.get('CostOfSales'))

        gross_profit = flat_data.get('GrossProfit')

        operating_income = (flat_data.get('OperatingIncomeLoss') or
                           flat_data.get('OperatingIncome'))

        operating_expenses = flat_data.get('OperatingExpenses')

        income_before_tax = (flat_data.get('IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest') or
                            flat_data.get('IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments') or
                            flat_data.get('IncomeLossBeforeIncomeTaxes'))

        tax_expense = (flat_data.get('IncomeTaxExpenseBenefit') or
                      flat_data.get('IncomeTaxesPaid'))

        net_income = (flat_data.get('NetIncomeLoss') or
                     flat_data.get('NetIncome') or
                     flat_data.get('ProfitLoss'))

        # Check: Gross Profit = Revenue - Cost of Revenue
        if revenue and cost_of_revenue and gross_profit:
            equations_checked.append('Gross Profit = Revenue - Cost of Revenue')
            valid, error = self._check_equation(
                gross_profit,
                revenue - cost_of_revenue,
                'GrossProfit = Revenue - CostOfRevenue'
            )
            if valid:
                equations_passed.append('Gross Profit = Revenue - Cost of Revenue')
            else:
                equations_failed.append(error)

        # Check: Operating Income = Gross Profit - Operating Expenses
        if gross_profit and operating_expenses and operating_income:
            equations_checked.append('Operating Income = Gross Profit - Operating Expenses')
            valid, error = self._check_equation(
                operating_income,
                gross_profit - operating_expenses,
                'OperatingIncome = GrossProfit - OperatingExpenses'
            )
            if valid:
                equations_passed.append('Operating Income = Gross Profit - Operating Expenses')
            else:
                equations_failed.append(error)

        # Check: Net Income = Income Before Tax - Tax Expense
        if income_before_tax and tax_expense and net_income:
            equations_checked.append('Net Income = Income Before Tax - Tax')

            # Handle equity method adjustments
            equity_method = flat_data.get('IncomeLossFromEquityMethodInvestments', 0)

            valid, error = self._check_equation(
                net_income,
                income_before_tax - tax_expense + equity_method,
                'NetIncome = IncomeTax - Tax + EquityMethod'
            )
            if valid:
                equations_passed.append('Net Income = Income Before Tax - Tax')
            else:
                equations_failed.append(error)

        if len(equations_checked) == 0:
            warnings.append('Cannot validate income statement: missing required tags')
            warnings.append('Looking for: Revenue, Cost of Revenue, Operating Income, Net Income')

        return ValidationResult(
            statement_type='Income Statement',
            valid=(len(equations_failed) == 0 and len(equations_checked) > 0),
            equations_checked=equations_checked,
            equations_passed=equations_passed,
            equations_failed=equations_failed,
            warnings=warnings
        )

    def validate_cash_flow_statement(self, flat_data: Dict[str, float]) -> ValidationResult:
        """
        Validate Cash Flow Statement using fundamental equation:

        Operating Cash Flow + Investing Cash Flow + Financing Cash Flow = Change in Cash

        And:
        Beginning Cash + Change in Cash = Ending Cash

        Args:
            flat_data: Dict of tag->value from reconstructed statement

        Returns:
            ValidationResult
        """
        equations_checked = []
        equations_passed = []
        equations_failed = []
        warnings = []

        # Get cash flow components
        operating_cf = (flat_data.get('NetCashProvidedByUsedInOperatingActivities') or
                       flat_data.get('NetCashProvidedByUsedInOperatingActivitiesContinuingOperations'))

        investing_cf = (flat_data.get('NetCashProvidedByUsedInInvestingActivities') or
                       flat_data.get('NetCashProvidedByUsedInInvestingActivitiesContinuingOperations'))

        financing_cf = (flat_data.get('NetCashProvidedByUsedInFinancingActivities') or
                       flat_data.get('NetCashProvidedByUsedInFinancingActivitiesContinuingOperations'))

        change_in_cash = (flat_data.get('CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect') or
                         flat_data.get('CashAndCashEquivalentsPeriodIncreaseDecrease'))

        fx_effect = flat_data.get('EffectOfExchangeRateOnCashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents', 0)

        beginning_cash = (flat_data.get('CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsBeginningOfPeriod') or
                         flat_data.get('CashAndCashEquivalentsAtCarryingValueBeginningOfPeriod'))

        ending_cash = (flat_data.get('CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsEndOfPeriod') or
                      flat_data.get('CashAndCashEquivalentsAtCarryingValue'))

        # Check: Operating + Investing + Financing (+FX) = Change in Cash
        if operating_cf is not None and investing_cf is not None and financing_cf is not None and change_in_cash is not None:
            equations_checked.append('Operating + Investing + Financing = Change in Cash')

            calculated_change = operating_cf + investing_cf + financing_cf
            if fx_effect != 0:
                calculated_change += fx_effect

            valid, error = self._check_equation(
                change_in_cash,
                calculated_change,
                'ChangeInCash = Operating + Investing + Financing + FX'
            )
            if valid:
                equations_passed.append('Operating + Investing + Financing = Change in Cash')
            else:
                equations_failed.append(error)

        # Check: Beginning Cash + Change = Ending Cash
        if beginning_cash is not None and change_in_cash is not None and ending_cash is not None:
            equations_checked.append('Beginning Cash + Change = Ending Cash')
            valid, error = self._check_equation(
                ending_cash,
                beginning_cash + change_in_cash,
                'EndingCash = BeginningCash + Change'
            )
            if valid:
                equations_passed.append('Beginning Cash + Change = Ending Cash')
            else:
                equations_failed.append(error)

        if len(equations_checked) == 0:
            warnings.append('Cannot validate cash flow statement: missing required tags')
            warnings.append('Looking for: Operating CF, Investing CF, Financing CF, Change in Cash')

        return ValidationResult(
            statement_type='Cash Flow Statement',
            valid=(len(equations_failed) == 0 and len(equations_checked) > 0),
            equations_checked=equations_checked,
            equations_passed=equations_passed,
            equations_failed=equations_failed,
            warnings=warnings
        )

    def validate_all_statements(self, balance_sheet: Dict[str, float],
                               income_statement: Dict[str, float],
                               cash_flow: Dict[str, float]) -> Dict[str, ValidationResult]:
        """
        Validate all three statements

        Returns:
            Dict with 'BS', 'IS', 'CF' keys containing ValidationResults
        """
        return {
            'BS': self.validate_balance_sheet(balance_sheet),
            'IS': self.validate_income_statement(income_statement),
            'CF': self.validate_cash_flow_statement(cash_flow)
        }


if __name__ == '__main__':
    """Test validator with sample data"""

    # Sample Balance Sheet (should pass)
    bs_data = {
        'Assets': 1000000,
        'LiabilitiesAndStockholdersEquity': 1000000,
        'AssetsCurrent': 400000,
        'AssetsNoncurrent': 600000
    }

    # Sample Income Statement (should pass)
    is_data = {
        'RevenueFromContractWithCustomerExcludingAssessedTax': 500000,
        'CostOfRevenue': 300000,
        'GrossProfit': 200000
    }

    # Sample Cash Flow (should pass)
    cf_data = {
        'NetCashProvidedByUsedInOperatingActivities': 100000,
        'NetCashProvidedByUsedInInvestingActivities': -50000,
        'NetCashProvidedByUsedInFinancingActivities': -30000,
        'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect': 20000
    }

    validator = StatementValidator()

    print("Testing Balance Sheet:")
    bs_result = validator.validate_balance_sheet(bs_data)
    print(bs_result)

    print("\nTesting Income Statement:")
    is_result = validator.validate_income_statement(is_data)
    print(is_result)

    print("\nTesting Cash Flow:")
    cf_result = validator.validate_cash_flow_statement(cf_data)
    print(cf_result)
