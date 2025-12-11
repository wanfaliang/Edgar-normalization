"""
Financial Statements Mapper - Strategy 2
=========================================
Mapper for Balance Sheets without total_current_assets or total_current_liabilities.

This strategy is used for unclassified balance sheets (common in financial companies like
banks, insurance companies, REITs).

Key differences from Strategy 1:
- Maps Assets section → Equity section → Liabilities section (no current/non-current split)
- Uses pattern matching (not line numbers) to distinguish current vs non-current items
- Has combined items for when current/non-current can't be distinguished
- Uses other_assets and other_liabilities as residuals instead of other_current_assets, etc.

Usage:
    Called automatically from map_financial_statements.py when total_current_assets
    or total_current_liabilities is not found.
"""

from collections import defaultdict


def normalize(text):
    """Normalize text for matching"""
    if not text:
        return ""
    return text.lower().replace('-', ' ').replace(',', '').replace('  ', ' ').strip()


def is_non_current_pattern(p):
    """Check if plabel indicates non-current item"""
    return ('non current' in p or 'noncurrent' in p or 'non-current' in p or
            'long term' in p or 'long-term' in p)


def is_current_pattern(p):
    """Check if plabel indicates current item (but not non-current)"""
    return ('current' in p or 'short term' in p or 'short-term' in p) and not is_non_current_pattern(p)


def map_bs_item_strategy2(plabel, line_num, control_lines, tag='', negating=0, datatype=''):
    """
    Map a balance sheet line item for unclassified balance sheets.

    Uses pattern matching instead of line number position to determine current vs non-current.
    Items that can't be distinguished go to combined buckets.
    """
    p = normalize(plabel)
    t = tag.lower() if tag else ''
    dt = datatype.lower() if datatype else ''

    total_assets = control_lines.get('total_assets', float('inf'))
    total_liabilities = control_lines.get('total_liabilities', float('inf'))
    total_stockholders_equity_line = control_lines.get('total_stockholders_equity', float('inf'))
    total_liabilities_and_equity_line = control_lines.get('total_liabilities_and_total_equity', float('inf'))

    # Map control items DIRECTLY by line number
    if line_num == control_lines.get('total_assets'):
        return 'total_assets'
    if line_num == control_lines.get('total_liabilities'):
        return 'total_liabilities'
    if line_num == control_lines.get('total_stockholders_equity'):
        return 'total_stockholders_equity'
    if line_num == control_lines.get('total_equity'):
        return 'total_equity'
    if line_num == control_lines.get('total_liabilities_and_total_equity'):
        return 'total_liabilities_and_total_equity'

    # =========================================================================
    # ASSETS SECTION (line_num <= total_assets)
    # =========================================================================
    if line_num <= total_assets:
        # Cash items
        if 'cash' in p and 'restricted' in p:
            return 'cash_cash_equivalent_and_restricted_cash'
        if 'cash and short term' in p:
            return 'cash_and_short_term_investments'
        if ('cash' in p and 'restricted cash' != p) and ('total cash cash equivalents and marketable securities' != p) and ('total cash cash equivalents and short term investments' != p):
            return 'cash_and_cash_equivalents'

        # Investments - use pattern to determine current vs non-current
        if ('investment' in p or 'marketable' in p) and ('securities' in p or 'security' in p):
            if is_non_current_pattern(p):
                return 'long_term_investments'
            elif is_current_pattern(p):
                return 'short_term_investments'
            else:
                # Default: if mentioned with "marketable securities", likely short-term
                if 'marketable' in p:
                    return 'short_term_investments'
                return 'long_term_investments'

        # Receivables
        if ('trade' in p and ('receivable' in p or 'receivables' in p)) or \
           (('account' in p or 'accounts' in p) and ('receivable' in p or 'receivables' in p)) or \
           (('note' in p or 'notes' in p) and ('receivable' in p or 'receivables' in p)) or \
           ('receivables net' in p and ('other' not in p and 'tax' not in p)):
            return 'account_receivables_net'
        if 'other receivable' in p or 'other account receivable' in p or 'other accounts receivable' in p:
            return 'other_receivables'

        # Inventory
        if ('inventory' in p or 'inventories' in p) or \
           ('materials and supplies' in p and "inventorynet" in t):
            return 'inventory'

        # Prepaids
        if 'prepaid' in p:
            return 'prepaids'

        # Property, plant and equipment
        if (('property' in p or 'plant' in p or 'equipment' in p or 'ppe' in p or 'fixed assets' in p) and
            ('net' in p or 'less' in p)) and ('gross' not in t and 'gross' not in p and 'cost' not in p):
            return 'property_plant_equipment_net'

        # Goodwill and intangibles
        if 'goodwill' in p and ('intangible' in p or 'intangibles' in p):
            return 'goodwill_and_intangible_assets'
        if 'goodwill' in p:
            return 'goodwill'
        if 'intangible' in p or 'intangibles' in p:
            return 'intangible_assets'

        # Lease assets - use pattern to distinguish
        if ('finance' in p or 'capital' in p) and ('lease' in p or 'leases' in p or 'right of use' in p or 'rou' in p):
            return 'finance_lease_right_of_use_assets'
        if ('operating' in p or 'operation' in p) and ('lease' in p or 'leases' in p or 'right of use' in p or 'rou' in p):
            return 'operating_lease_right_of_use_assets'
        # Generic lease assets (catch-all)
        if 'lease' in p or 'right of use' in p or 'rou' in p:
            return 'lease_assets'

        # Deferred tax assets
        if 'deferred' in p and 'tax' in p and 'liabilit' not in p:
            return 'deferred_tax_assets'

        # Loans (common in financial companies)
        if ('loan' in p or 'loans' in p) and ('receivable' in p or 'net' in p or 'gross' in p):
            return 'loans_receivable'

        # Securities (financial companies)
        if 'securities' in p and ('held to maturity' in p or 'available for sale' in p or 'trading' in p):
            return 'investment_securities'

        # Bank-specific: Federal funds, deposits at banks
        if 'federal funds' in p and 'sold' in p:
            return 'federal_funds_sold'
        if 'interest bearing' in p and ('deposit' in p or 'deposits' in p) and 'bank' in p:
            return 'interest_bearing_deposits_at_banks'

        # Don't return None yet - will be other_assets at the end

    # =========================================================================
    # EQUITY SECTION (after total_assets, before or at total_stockholders_equity)
    # =========================================================================
    elif line_num > total_assets and line_num <= max(total_stockholders_equity_line,
                                                       control_lines.get('total_equity', total_stockholders_equity_line)):
        # Special case: CommonStock tags with negating=1 are treasury stock
        if ('commonstock' in t or 'commonshare' in t):
            negating_str = str(negating).strip().upper() if negating else ""
            if negating in (1, True) or negating_str in ("1", "TRUE"):
                return 'treasury_stock'

        # Common stock
        if 'monetary' in dt and (((('common stock' in p or 'common stocks' in p or 'common share' in p or 'common shares' in p) and
             ('cost' in p or 'par' in p or 'issued' in p) and
             ('treasury' not in p and 'purchase' not in p)) or
            (('commonstock' in t or 'commonshare' in t) and ('additional' not in p and 'paid in' not in p and 'excess' not in p and 'surplus' not in p and 'treasury' not in p and 'purchase' not in p))) or ('common stock' == p) or ('common stocks' == p) or ('common shares' == p) or ('common share' == p)):
            return 'common_stock'

        # Preferred stock
        if (('preferred stock' in p or 'preferred stocks' in p) and ('cost' in p or 'par' in p)) or ('preferred stock' == p) or ('preferred stocks' == p):
            return 'preferred_stock'

        # Additional paid-in capital
        if ('additional' in p or 'paid in' in p or 'excess' in p or 'surplus' in p) and \
           ('capital' in p or 'proceeds' in p or 'fund' in p or 'amount' in p):
            return 'additional_paid_in_capital'

        # Retained earnings
        if ('accumulated' in p or 'retained' in p or 'employed' in p or 'reinvest' in p) and ('earning' in p or 'deficit' in p or 'profit' in p):
            return 'retained_earnings'

        # Accumulated other comprehensive income
        if 'accumulated' in p and 'other' in p and 'comprehensive' in p:
            if 'stockholdersequityincludingportionattributabletononcontrolling' in t:
                return 'total_equity'
            return 'accumulated_other_comprehensive_income_loss'

        # Treasury stock
        if (('treasury' in p or 'purchase' in p) and ('stock' in p or 'share' in p)) or ('esop' in p or 'option' in p):
            return 'treasury_stock'

        # Noncontrolling interests
        if 'noncontrolling interests in subsidiaries' in p:
            return 'redeemable_non_controlling_interests'
        if 'noncontrolling' in p or 'non controlling' in p or 'minority interest' in p:
            return 'minority_interest'

        # Total stockholders equity pattern
        if ('stockholder' in p or 'shareholder' in p or 'owner' in p) and ('equity' in p or 'deficit' in p) and 'liabilit' not in p:
            return 'total_stockholders_equity'

        # Total equity
        if p in ['total equity', 'equity total', 'equity, total', 'total deficit']:
            return 'total_equity'

    # =========================================================================
    # LIABILITIES SECTION (after equity, before total_liabilities_and_total_equity)
    # =========================================================================
    elif line_num > total_assets:
        # Accounts payable
        if ('account' in p or 'trade' in p) and 'payable' in p:
            return 'account_payables'

        # Accrued items
        if 'employ' in p or 'compensation' in p or 'wages' in p or 'salaries' in p or 'payroll' in p:
            return 'accrued_payroll'
        if 'accrued' in p and not any(x in p for x in ['employment', 'compensation', 'wages', 'salaries', 'payroll', 'tax', 'taxes']):
            return 'accrued_expenses'

        # Deferred revenue - use pattern for current vs non-current
        if ('unearned' in p or 'unexpired' in p) or ('deferred' in p and ('income' in p or 'revenue' in p)) or ('advance' in p):
            if is_non_current_pattern(p):
                return 'deferred_revenue_non_current'
            else:
                return 'deferred_revenue'

        # Debt - use pattern for current vs non-current
        if ('borrowing' in p or 'borrowings' in p or 'debt' in p or 'notes' in p or 'loan' in p or 'loans' in p):
            if is_non_current_pattern(p) or 'long term' in p or 'long-term' in p:
                return 'long_term_debt'
            elif is_current_pattern(p) or 'short term' in p or 'short-term' in p:
                return 'short_term_debt'
            elif 'current maturities' in p or 'current portion' in p or 'current installment' in p:
                return 'short_term_debt'
            else:
                # Default to long-term for ambiguous debt
                return 'long_term_debt'

        # Dividends payable
        if 'dividend' in p and ('payable' in p or 'liability' in p):
            return 'dividends_payable'

        # Tax payables - use pattern for current vs non-current
        if ('payable' in p or 'accrued' in p or 'liabilit' in p or 'obligation' in p) and 'tax' in p and 'deferred' not in p:
            if is_non_current_pattern(p):
                return 'tax_payables_non_current'
            else:
                return 'tax_payables'

        # Lease obligations - use pattern to distinguish
        if ('finance' in p or 'capital' in p) and ('lease' in p or 'leases' in p):
            if is_non_current_pattern(p):
                return 'finance_lease_obligations_non_current'
            elif is_current_pattern(p):
                return 'finance_lease_obligations_current'
            else:
                return 'finance_lease_obligations'  # Combined

        if 'operating' in p and ('lease' in p or 'leases' in p):
            if is_non_current_pattern(p):
                return 'operating_lease_obligations_non_current'
            elif is_current_pattern(p):
                return 'operating_lease_obligations_current'
            else:
                return 'operating_lease_obligations'  # Combined

        # Generic lease obligations (catch-all)
        if 'lease' in p or 'right of use' in p or 'rou' in p:
            if is_non_current_pattern(p):
                return 'lease_obligation_non_current'
            elif is_current_pattern(p):
                return 'lease_obligation_current'
            else:
                return 'lease_obligations'  # Combined

        # Pension and benefits
        if ('pension' in p or 'retirement' in p or 'employ' in p) and ('liabilit' in p or 'obligation' in p or 'benefit' in p):
            return 'pension_and_postretirement_benefits'

        # Deferred tax liabilities
        if 'deferred' in p and 'tax' in p and 'asset' not in p:
            return 'deferred_tax_liabilities_non_current'

        # Bank-specific: Deposits
        if 'deposit' in p and ('customer' in p or 'liabilit' in p or p == 'deposits' or p == 'total deposits'):
            return 'customer_deposits'

        # Commitments and contingencies
        if 'commitments' in p or 'contingencies' in p:
            return 'commitments_and_contingencies'

        # Total liabilities pattern
        if p in ['total liabilities', 'liabilities total'] or ('total' in p and 'liabilit' in p and 'current' not in p and 'stockholder' not in p and 'equity' not in p):
            return 'total_liabilities'

    return None


def map_balance_sheet_strategy2(line_items, control_lines):
    """
    Map balance sheet items using Strategy 2 (unclassified balance sheet).

    Returns:
        tuple: (mappings list, target_to_plabels dict)
    """
    mappings = []
    target_to_plabels = defaultdict(list)

    for item in line_items:
        plabel = item.get('plabel', '')
        line_num = item.get('stmt_order', 0)
        tag = item.get('tag', '')
        negating = item.get('negating', 0)
        datatype = item.get('datatype', '')

        # Get value from most recent period
        value = None
        for key, val in item.items():
            if key.startswith('value_') and val is not None:
                value = val
                break

        target = map_bs_item_strategy2(plabel, line_num, control_lines, tag, negating, datatype)

        if target:
            mappings.append({
                'plabel': plabel,
                'target': target,
                'value': value,
                'section': 'strategy2'  # Mark as strategy 2
            })
            target_to_plabels[target].append((plabel, line_num))

    return mappings, target_to_plabels


def calculate_residuals_strategy2(standardized, control_lines):
    """
    Calculate residual items for Strategy 2:
    - other_assets = total_assets - sum of all mapped assets
    - other_liabilities = total_liabilities - sum of all mapped liabilities
    - other_total_stockholders_equity (same as Strategy 1)
    """

    def get_period_values(field):
        """Get all period values for a field"""
        if field not in standardized:
            return {}
        field_data = standardized[field]
        # Handle the actual structure: {'period_values': {...}, 'total_value': ..., ...}
        if isinstance(field_data, dict) and 'period_values' in field_data:
            return field_data['period_values']
        return {}

    # Asset items that are summed for other_assets calculation
    asset_items = [
        'cash_and_cash_equivalents', 'cash_and_short_term_investments', 'cash_cash_equivalent_and_restricted_cash',
        'short_term_investments', 'account_receivables_net', 'other_receivables', 'inventory', 'prepaids',
        'property_plant_equipment_net', 'finance_lease_right_of_use_assets', 'operating_lease_right_of_use_assets',
        'lease_assets', 'long_term_investments', 'goodwill', 'intangible_assets', 'goodwill_and_intangible_assets',
        'deferred_tax_assets', 'loans_receivable', 'investment_securities', 'federal_funds_sold',
        'interest_bearing_deposits_at_banks'
    ]

    # Liability items that are summed for other_liabilities calculation
    liability_items = [
        'account_payables', 'accrued_payroll', 'accrued_expenses', 'short_term_debt', 'long_term_debt',
        'deferred_revenue', 'deferred_revenue_non_current', 'tax_payables', 'tax_payables_non_current',
        'dividends_payable', 'finance_lease_obligations_current', 'finance_lease_obligations_non_current',
        'finance_lease_obligations', 'operating_lease_obligations_current', 'operating_lease_obligations_non_current',
        'operating_lease_obligations', 'lease_obligation_current', 'lease_obligation_non_current',
        'lease_obligations', 'pension_and_postretirement_benefits', 'deferred_tax_liabilities_non_current',
        'customer_deposits', 'commitments_and_contingencies'
    ]

    # Equity items
    equity_items = ['common_stock', 'preferred_stock', 'additional_paid_in_capital', 'treasury_stock',
                    'retained_earnings', 'accumulated_other_comprehensive_income_loss']

    # Calculate other_assets
    total_assets_periods = get_period_values('total_assets')
    if total_assets_periods:
        other_assets_periods = {}
        for period in total_assets_periods:
            total_val = total_assets_periods[period]
            sum_val = sum(
                get_period_values(item).get(period, 0) or 0
                for item in asset_items
                if item in standardized
            )
            residual = total_val - sum_val if total_val is not None else None
            if residual is not None and abs(residual) > 0.01:
                other_assets_periods[period] = residual

        if other_assets_periods:
            standardized['other_assets'] = {
                'total_value': list(other_assets_periods.values())[0] if other_assets_periods else None,
                'period_values': other_assets_periods,
                'count': 1,
                'source_items': ['(calculated residual)']
            }

    # Calculate other_liabilities
    total_liabilities_periods = get_period_values('total_liabilities')
    if total_liabilities_periods:
        other_liabilities_periods = {}
        for period in total_liabilities_periods:
            total_val = total_liabilities_periods[period]
            sum_val = sum(
                get_period_values(item).get(period, 0) or 0
                for item in liability_items
                if item in standardized
            )
            residual = total_val - sum_val if total_val is not None else None
            if residual is not None and abs(residual) > 0.01:
                other_liabilities_periods[period] = residual

        if other_liabilities_periods:
            standardized['other_liabilities'] = {
                'total_value': list(other_liabilities_periods.values())[0] if other_liabilities_periods else None,
                'period_values': other_liabilities_periods,
                'count': 1,
                'source_items': ['(calculated residual)']
            }

    # Calculate other_total_stockholders_equity (same logic as Strategy 1)
    total_se_periods = get_period_values('total_stockholders_equity')
    if total_se_periods:
        # If total_equity exists, NCI items are between total_stockholders_equity and total_equity
        if 'total_equity' not in standardized:
            equity_items.extend(['minority_interest', 'redeemable_non_controlling_interests'])

        other_equity_periods = {}
        for period in total_se_periods:
            total_val = total_se_periods[period]
            sum_val = 0
            for item in equity_items:
                if item in standardized:
                    item_val = get_period_values(item).get(period, 0) or 0
                    # Treasury stock is contra-equity
                    if item == 'treasury_stock':
                        sum_val -= item_val
                    else:
                        sum_val += item_val

            residual = total_val - sum_val if total_val is not None else None
            if residual is not None and abs(residual) > 0.01:
                other_equity_periods[period] = residual

        if other_equity_periods:
            standardized['other_total_stockholders_equity'] = {
                'total_value': list(other_equity_periods.values())[0] if other_equity_periods else None,
                'period_values': other_equity_periods,
                'count': 1,
                'source_items': ['(calculated residual)']
            }

    return standardized


def get_balance_sheet_structure_strategy2():
    """
    Define standardized balance sheet structure for Strategy 2 (unclassified).

    Similar to Strategy 1 but:
    - No current/non-current subtotals
    - Has other_assets and other_liabilities
    - Has combined lease items
    """
    return [
        {'type': 'major_section', 'label': 'ASSETS'},
        {'type': 'item', 'field': 'cash_and_cash_equivalents', 'label': 'Cash and cash equivalents', 'indent': 1},
        {'type': 'item', 'field': 'cash_and_short_term_investments', 'label': 'Cash and short-term investments', 'indent': 1},
        {'type': 'item', 'field': 'cash_cash_equivalent_and_restricted_cash', 'label': 'Cash, cash equivalents and restricted cash', 'indent': 1},
        {'type': 'item', 'field': 'short_term_investments', 'label': 'Short-term investments', 'indent': 1},
        {'type': 'item', 'field': 'interest_bearing_deposits_at_banks', 'label': 'Interest-bearing deposits at banks', 'indent': 1},
        {'type': 'item', 'field': 'federal_funds_sold', 'label': 'Federal funds sold', 'indent': 1},
        {'type': 'item', 'field': 'investment_securities', 'label': 'Investment securities', 'indent': 1},
        {'type': 'item', 'field': 'loans_receivable', 'label': 'Loans receivable, net', 'indent': 1},
        {'type': 'item', 'field': 'account_receivables_net', 'label': 'Accounts receivable, net', 'indent': 1},
        {'type': 'item', 'field': 'other_receivables', 'label': 'Other receivables', 'indent': 1},
        {'type': 'item', 'field': 'inventory', 'label': 'Inventory', 'indent': 1},
        {'type': 'item', 'field': 'prepaids', 'label': 'Prepaid expenses', 'indent': 1},
        {'type': 'item', 'field': 'property_plant_equipment_net', 'label': 'Property, plant and equipment, net', 'indent': 1},
        {'type': 'item', 'field': 'finance_lease_right_of_use_assets', 'label': 'Finance lease right-of-use assets', 'indent': 1},
        {'type': 'item', 'field': 'operating_lease_right_of_use_assets', 'label': 'Operating lease right-of-use assets', 'indent': 1},
        {'type': 'item', 'field': 'lease_assets', 'label': 'Lease right-of-use assets', 'indent': 1},
        {'type': 'item', 'field': 'long_term_investments', 'label': 'Long-term investments', 'indent': 1},
        {'type': 'item', 'field': 'goodwill', 'label': 'Goodwill', 'indent': 1},
        {'type': 'item', 'field': 'intangible_assets', 'label': 'Intangible assets, net', 'indent': 1},
        {'type': 'item', 'field': 'goodwill_and_intangible_assets', 'label': 'Goodwill and intangible assets', 'indent': 1},
        {'type': 'item', 'field': 'deferred_tax_assets', 'label': 'Deferred tax assets', 'indent': 1},
        {'type': 'item', 'field': 'other_assets', 'label': 'Other assets', 'indent': 1},
        {'type': 'subtotal', 'field': 'total_assets', 'label': 'TOTAL ASSETS'},
        {'type': 'blank'},
        {'type': 'major_section', 'label': 'LIABILITIES AND STOCKHOLDERS\' EQUITY'},
        {'type': 'section_header', 'label': 'Liabilities'},
        {'type': 'item', 'field': 'customer_deposits', 'label': 'Customer deposits', 'indent': 1},
        {'type': 'item', 'field': 'short_term_debt', 'label': 'Short-term debt', 'indent': 1},
        {'type': 'item', 'field': 'long_term_debt', 'label': 'Long-term debt', 'indent': 1},
        {'type': 'item', 'field': 'account_payables', 'label': 'Accounts payable', 'indent': 1},
        {'type': 'item', 'field': 'accrued_payroll', 'label': 'Accrued compensation', 'indent': 1},
        {'type': 'item', 'field': 'accrued_expenses', 'label': 'Accrued expenses', 'indent': 1},
        {'type': 'item', 'field': 'deferred_revenue', 'label': 'Deferred revenue', 'indent': 1},
        {'type': 'item', 'field': 'deferred_revenue_non_current', 'label': 'Deferred revenue, non-current', 'indent': 1},
        {'type': 'item', 'field': 'tax_payables', 'label': 'Income taxes payable', 'indent': 1},
        {'type': 'item', 'field': 'tax_payables_non_current', 'label': 'Income taxes payable, non-current', 'indent': 1},
        {'type': 'item', 'field': 'dividends_payable', 'label': 'Dividends payable', 'indent': 1},
        {'type': 'item', 'field': 'finance_lease_obligations_current', 'label': 'Finance lease liabilities - current', 'indent': 1},
        {'type': 'item', 'field': 'finance_lease_obligations_non_current', 'label': 'Finance lease liabilities - non-current', 'indent': 1},
        {'type': 'item', 'field': 'finance_lease_obligations', 'label': 'Finance lease liabilities', 'indent': 1},
        {'type': 'item', 'field': 'operating_lease_obligations_current', 'label': 'Operating lease liabilities - current', 'indent': 1},
        {'type': 'item', 'field': 'operating_lease_obligations_non_current', 'label': 'Operating lease liabilities - non-current', 'indent': 1},
        {'type': 'item', 'field': 'operating_lease_obligations', 'label': 'Operating lease liabilities', 'indent': 1},
        {'type': 'item', 'field': 'lease_obligation_current', 'label': 'Lease liabilities - current', 'indent': 1},
        {'type': 'item', 'field': 'lease_obligation_non_current', 'label': 'Lease liabilities - non-current', 'indent': 1},
        {'type': 'item', 'field': 'lease_obligations', 'label': 'Lease liabilities', 'indent': 1},
        {'type': 'item', 'field': 'pension_and_postretirement_benefits', 'label': 'Pension and postretirement benefits', 'indent': 1},
        {'type': 'item', 'field': 'deferred_tax_liabilities_non_current', 'label': 'Deferred tax liabilities', 'indent': 1},
        {'type': 'item', 'field': 'commitments_and_contingencies', 'label': 'Commitments and contingencies', 'indent': 1},
        {'type': 'item', 'field': 'other_liabilities', 'label': 'Other liabilities', 'indent': 1},
        {'type': 'subtotal', 'field': 'total_liabilities', 'label': 'Total Liabilities'},
        {'type': 'section_header', 'label': 'Stockholders\' Equity'},
        {'type': 'item', 'field': 'common_stock', 'label': 'Common stock', 'indent': 1},
        {'type': 'item', 'field': 'preferred_stock', 'label': 'Preferred stock', 'indent': 1},
        {'type': 'item', 'field': 'additional_paid_in_capital', 'label': 'Additional paid-in capital', 'indent': 1},
        {'type': 'item', 'field': 'treasury_stock', 'label': 'Treasury stock', 'indent': 1},
        {'type': 'item', 'field': 'retained_earnings', 'label': 'Retained earnings', 'indent': 1},
        {'type': 'item', 'field': 'accumulated_other_comprehensive_income_loss', 'label': 'Accumulated other comprehensive income (loss)', 'indent': 1},
        {'type': 'item', 'field': 'other_total_stockholders_equity', 'label': 'Other stockholders\' equity', 'indent': 1},
        {'type': 'subtotal', 'field': 'total_stockholders_equity', 'label': 'Total Stockholders\' Equity'},
        {'type': 'item', 'field': 'minority_interest', 'label': 'Noncontrolling interests', 'indent': 1},
        {'type': 'item', 'field': 'redeemable_non_controlling_interests', 'label': 'Redeemable noncontrolling interests', 'indent': 1},
        {'type': 'subtotal', 'field': 'total_equity', 'label': 'Total Equity'},
        {'type': 'total', 'field': 'total_liabilities_and_total_equity', 'label': 'TOTAL LIABILITIES AND STOCKHOLDERS\' EQUITY'},
    ]


def should_use_strategy2(control_lines):
    """
    Determine if Strategy 2 should be used based on control items found.

    Returns True if:
    - total_current_assets is not found, OR
    - total_current_liabilities is not found

    AND total_assets and total_liabilities_and_total_equity ARE found.
    """
    has_total_assets = 'total_assets' in control_lines
    has_total_l_and_e = 'total_liabilities_and_total_equity' in control_lines
    has_total_current_assets = 'total_current_assets' in control_lines
    has_total_current_liabilities = 'total_current_liabilities' in control_lines

    # Must have the essential control items
    if not has_total_assets or not has_total_l_and_e:
        return False

    # Use Strategy 2 if missing current assets OR current liabilities
    return not has_total_current_assets or not has_total_current_liabilities
