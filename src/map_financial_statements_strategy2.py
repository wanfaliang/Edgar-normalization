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


def map_bs_item_strategy2(plabel, line_num, control_lines, tag='', negating=0, datatype='', is_sum=False, calc_children=None):
    """
    Map a balance sheet line item for unclassified balance sheets.

    Uses pattern matching instead of line number position to determine current vs non-current.
    Items that can't be distinguished go to combined buckets.

    Args:
        plabel: Presentation label
        line_num: Line number in statement
        control_lines: Dict of control item line numbers
        tag: XBRL tag name
        negating: Whether value is negated
        datatype: XBRL data type
        is_sum: True if this item is a parent in the calc graph (sum of children)
        calc_children: List of (child_tag, weight) tuples from calc graph
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
        if 'cash and short term' in p or 'cash cash equivalents and short term investments' in p or 'cash cash equivalents and marketable securities' in p:
            return 'cash_and_short_term_investments'
        if ('cash' in p and 'restricted cash' != p) and ('total cash cash equivalents and marketable securities' != p) and ('total cash cash equivalents and short term investments' != p):
            return 'cash_and_cash_equivalents'

        # Investments - use pattern to determine current vs non-current
        if (('investment' in p or 'marketable' in p) and ('securities' in p or 'security' in p)) and ('held to maturity' not in p and 'available for sale' not in p ):
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
           (('receivable' in p and 'net' in p) 
                            and ('other' not in p and 'tax' not in p and 'financ' not in p and 'loan' not in p  
                                            and 'interest' not in p and 'accrued' not in p )):
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
        if (('property' in p or 'plant' in p or 'equipment' in p or 'ppe' in p 
             or 'fixed assets' in p or 'premise' in p) and
            ('net' in p or 'less' in p)) and ('gross' not in t and 'gross' not in p and 'cost' not in p):
            return 'property_plant_equipment_net'
        
        if 'equity method' in p and 'investment' in p:
            return 'long_term_investments'


        # Goodwill and intangibles
        if 'goodwill' in p and ('intangible' in p or 'intangibles' in p):
            return 'goodwill_and_intangible_assets'
        if 'goodwill' in p:
            return 'goodwill'
        if ('intangible' in p or 'acquired client' in p or 'customer list' in p
             or 'trademark' in p or 'patent' in p or 'copyright' in p or 'brand' in p):
            return 'intangible_assets'

        # Lease assets - use pattern to distinguish
        if ('finance' in p or 'capital' in p) and ('lease' in p or 'leases' in p or 'right of use' in p ):
            return 'finance_lease_right_of_use_assets'
        if ('operating' in p or 'operation' in p) and ('lease' in p or 'leases' in p or 'right of use' in p ):
            return 'operating_lease_right_of_use_assets'
        # Generic lease assets (catch-all)
        if ('lease' in p or 'right of use' in p) and ('loan' not in p):
            return 'lease_assets'

        # Deferred tax assets
        if 'deferred' in p and 'tax' in p and 'liabilit' not in p:
            return 'deferred_tax_assets'

        # =====================================================================
        # FINANCIAL COMPANY ASSET PATTERNS
        # =====================================================================
        # Cash equivalents for financial companies
        if ('due from bank' in p):
            return 'cash_and_cash_equivalents'
        if ('deposits with bank' in p) or ('interest' in p and 'deposit' in p) or ('time deposit' in p):
            return 'cash_and_cash_equivalents'

        # Trading and derivative assets
        if (('trading' in p or 'equity securit' in p or 'investment' in p) and \
            'fair value' in p) and ('income investment' not in p and 'loan' not in p):
            return 'trading_and_derivative_assets_at_fair_value'
        if 'derivative' in p and ('asset' in p or 'assets' in p):
            return 'trading_and_derivative_assets_at_fair_value'

        # Investment securities
        if (('available for sale' in p or 'carried at fair value' in p) or ('investment' in p and 'at fair value' in p)) and ('trading' 
                                    not in p and 'income investment' not in p and 'loan' not in p):
            return 'investment_securities'
        if ('held to maturity' in p or 'held as investment' in p or 'held for investment' in p or ('investment' in p and 'at amortized cost' in p)) and ('trading' not in p and 'income investment' not in p and 'loan' not in p):
            return 'investment_securities'

        # Loans and financing receivables
        if 'resell' in p or 'resale' in p:
            return 'loans_and_financing_receivables_net'
        if (('loan' in p or 'mortgage' in p or 'lease' in p) and ('held for sale' in p or 'held for investment' in p)):
            return 'loans_and_financing_receivables_net'
        if (('loan' in p and 'net of allowance' in p) or ('mortgage' in p and 'net of allowance' in p) or \
            'net loan' in p or 'net mortgage' in p or ('mortgage' in p and 'net' in p) or ('loan' in p and 'net' in p)) or \
            ('receivable' in p and 'financ' in p):
            return 'loans_and_financing_receivables_net'
        if ('accrued' in p or 'receivable' in p or 'recoverable' in p) and ('interest' in p or 'dividend' in p
                                                                            or 'mortgage' in p or 'premium' in p or 'financ' in p):
            return 'loans_and_financing_receivables_net'

        # Insurance assets
        if 'life insurance' in p or 'surrender value' in p or 'reinsurance' in p or 'policy loans' in p:
            return 'insurance_assets'

        # FHLB/FRB stock (long-term investments)
        if 'federal bank' in p or 'federal home loan bank' in p or 'fhlb' in p or \
            'frb' in p or 'regulatory stock' in p:
            return 'long_term_investments'

        # Other financial assets
        if 'real estate asset' in p:
            return 'other_financial_assets'
        if 'foreclos' in p or 'repossessed' in p:
            return 'other_financial_assets'

        # Acquisition-related intangibles
        if 'acquisition' in p and ('intangible' in p or 'cost' in p):
            return 'intangible_assets'

        # Check calc_children for investment securities (parent item detection)
        if is_sum and calc_children:
            for child_entry in calc_children:
                if isinstance(child_entry, (list, tuple)) and len(child_entry) >= 3:
                    child_plabel = child_entry[2]
                    cp = normalize(child_plabel)
                    if ('available for sale' in cp or 'afs' in cp or 'carried at fair value' in cp) or \
                        ('held to maturity' in cp or 'held as investment' in cp or 'held for investment' in cp):
                        return 'investment_securities'

        # Don't return None yet - will be other_assets at the end

    # =========================================================================
    # LIABILITIES AND EQUITY SECTION (after total_assets)
    # Combined section like map_financial_statements.py - check all patterns
    # =========================================================================
    elif line_num > total_assets:
        # Special case: CommonStock tags with negating=1 are treasury stock
        if ('commonstock' in t or 'commonshare' in t):
            negating_str = str(negating).strip().upper() if negating else ""
            if negating in (1, True) or negating_str in ("1", "TRUE"):
                return 'treasury_stock'

        # EQUITY PATTERNS
        # Common stock
        if 'monetary' in dt and (((('common stock' in p or 'common stocks' in p or 'common share' in p or 'common shares' in p) and
             ('cost' in p or 'par' in p or 'issued' in p) and
             ('treasury' not in p and 'purchase' not in p)) or
            (('commonstock' in t or 'commonshare' in t) and ('additional' not in p and 'paid in' not in p and 'excess' not in p and 'surplus' not in p and 'treasury' not in p and 'purchase' not in p))) or 
            ('common stock' == p) or ('common stocks' == p) or ('common shares' == p) or ('common share' == p) or 'capital stock' == p):
            return 'common_stock'

        # Preferred stock - match any label containing "preferred stock"
        if 'preferred stock' in p or 'preferred stocks' in p:
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

        # LIABILITIES PATTERNS
        # Accounts payable
        if ('account' in p or 'trade' in p) and 'payable' in p:
            return 'account_payables'
        if 'accrued' in p and 'interest' in p:
                return 'accrued_interest_payable'
        # Dividends payable
        if 'dividend' in p and ('payable' in p or 'liability' in p or 'accrued' in p):
                return 'dividends_payable'
        # Accrued items
        if 'employ' in p or 'compensation' in p or 'wages' in p or 'salaries' in p or 'payroll' in p:
            return 'accrued_payroll'
        if 'accrued' in p and not any(x in p for x in ['employment', 'compensation', 'wages', 'salaries', 'payroll', 'tax', 'taxes']):
            return 'accrued_expenses'

        # Deferred revenue - use pattern for current vs non-current
        # Exclude FHLB, BTFP (Federal Reserve lending programs - these are borrowings, not deferred revenue)
        if ('unearned' in p or 'unexpired' in p) or ('deferred' in p and ('income' in p or 'revenue' in p or 'premium' in p or 'fees' in p)) or ('advance' in p and 'fhlb' not in p and 'federal home loan' not in p and 'btfp' not in p and 'bank term funding' not in p):
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
        if 'lease' in p or 'right of use' in p:
            if is_non_current_pattern(p):
                return 'lease_obligation_non_current'
            elif is_current_pattern(p):
                return 'lease_obligation_current'
            else:
                return 'lease_obligations'  # Combined

        # Pension and benefits
        if ('pension' in p or 'retir' in p or 'employ' in p) and ('liabilit' in p or 'obligation' in p or 'benefit' in p or 'accrued' in p) :
            return 'pension_and_postretirement_benefits'

        # Deferred tax liabilities
        if 'deferred' in p and 'tax' in p and 'asset' not in p:
            return 'deferred_tax_liabilities_non_current'

        # =====================================================================
        # FINANCIAL COMPANY LIABILITY PATTERNS
        # =====================================================================
        # Customer and policyholder deposits
        if ('deposit' in p or 'interest bearing' in p or 'savings' in p or 'checking' in p or 'time deposit' in p
            or 'time account' in p
            or 'money market' in p or 'certificate of deposit' in p):
            return 'customer_and_policyholder_deposits'
        if 'acceptance' in p:
            return 'customer_and_policyholder_deposits'
        if 'policyholder' in p and 'deposit' in p:
            return 'customer_and_policyholder_deposits'
        if 'security deposit' in p:
            return 'customer_and_policyholder_deposits'

        # Repurchase agreements (short-term debt)
        if 'agreement' in p and ('repurchase' in p or 'repo' in p):
            return 'short_term_debt'

        # Trading and derivative liabilities
        if 'trading' in p and ('liabilit' in p or 'at fair value' in p):
            return 'trading_and_derivative_liabilities_at_fair_value'
        if 'derivative' in p and 'liabilit' in p:
            return 'trading_and_derivative_liabilities_at_fair_value'

        # Loss and claims reserves
        if ('reserve' in p or 'settlement' in p) and ('loss' in p or 'claim' in p or 'legal' in p):
            return 'loss_and_claims_reserves_and_payables'
        if 'insurance' in p and 'assessment' in p:
            return 'loss_and_claims_reserves_and_payables'

        # Financial company debt patterns (long-term)
        if 'securit' in p and 'loan' in p:
            return 'long_term_debt'
        if 'secured' in p and ('borrowing' in p or 'debt' in p or 'loan' in p or 'financing' in p):
            return 'long_term_debt'
        if 'unsecured' in p and ('borrowing' in p or 'debt' in p or 'loan' in p
                                 or 'financing' in p or 'debenture' in p or 'revolving credit facility' in p):
            return 'long_term_debt'
        if 'federal home loan bank' in p or 'fhlb' in p or 'frb' in p or 'bank term funding program' in p or 'btfp' in p:
            return 'long_term_debt'
        if 'subordinated' in p and ('debt' in p or 'note' in p or 'loan' in p or
                                    'borrowings' in p or 'financing' in p or 'debenture' in p):
            return 'long_term_debt'
        if 'senior note' in p or 'senior debt' in p:
            return 'long_term_debt'
        if 'bond' in p:
            return 'long_term_debt'
        if 'non recourse' in p and 'mortgage' in p:
            return 'long_term_debt'

        # Other financial liabilities
        if 'intangible' in p and 'liabilit' in p:
            return 'other_financial_liabilities'

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

    Args:
        line_items: List of line items from reconstructor
        control_lines: Dict of control line numbers

    Returns:
        tuple: (mappings list, target_to_plabels dict)
    """
    mappings = []
    target_to_plabels = defaultdict(list)

    # Build set of control line numbers for quick lookup
    control_line_nums = set(control_lines.values())

    for item in line_items:
        plabel = item.get('plabel', '')
        line_num = item.get('stmt_order', 0)
        tag = item.get('tag', '')
        negating = item.get('negating', 0)
        datatype = item.get('datatype', '')
        is_sum = item.get('is_sum', False)
        calc_children = item.get('calc_children', [])

        # Check if we should skip based on parent_line
        # Skip if parent is NOT a control item (i.e., this item is a grandchild or deeper)
        parent_line = item.get('parent_line')
        is_control_line = line_num in control_line_nums
        # Skip if: not a control item itself AND has a parent AND parent is not a control item
        if not is_control_line and parent_line is not None and parent_line not in control_line_nums:
            # Skip this item - its parent is not a control item
            continue

        # Get value from most recent period
        value = None
        for key, val in item.items():
            if key.startswith('value_') and val is not None:
                value = val
                break

        target = map_bs_item_strategy2(plabel, line_num, control_lines, tag, negating, datatype, is_sum, calc_children)

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
        'deferred_tax_assets',
        # Financial company asset items
        'trading_and_derivative_assets_at_fair_value', 'investment_securities', 'loans_and_financing_receivables_net',
        'insurance_assets', 'other_financial_assets'
    ]

    # Liability items that are summed for other_liabilities calculation
    liability_items = [
        'account_payables', 'accrued_payroll', 'accrued_expenses', 'short_term_debt', 'long_term_debt',
        'deferred_revenue', 'deferred_revenue_non_current', 'tax_payables', 'tax_payables_non_current',
        'dividends_payable', 'finance_lease_obligations_current', 'finance_lease_obligations_non_current',
        'finance_lease_obligations', 'operating_lease_obligations_current', 'operating_lease_obligations_non_current',
        'operating_lease_obligations', 'lease_obligation_current', 'lease_obligation_non_current',
        'lease_obligations', 'pension_and_postretirement_benefits', 'deferred_tax_liabilities_non_current',
        'commitments_and_contingencies',
        # Financial company liability items
        'customer_and_policyholder_deposits', 'trading_and_derivative_liabilities_at_fair_value',
        'loss_and_claims_reserves_and_payables', 'other_financial_liabilities'
    ]

    # Equity items
    equity_items = ['common_stock', 'preferred_stock', 'additional_paid_in_capital', 'treasury_stock',
                    'retained_earnings', 'accumulated_other_comprehensive_income_loss']

    # Calculate other_assets (skip items whose parent is also mapped)
    total_assets_periods = get_period_values('total_assets')
    if total_assets_periods:
        other_assets_periods = {}
        for period in total_assets_periods:
            total_val = total_assets_periods[period]
            sum_val = sum(
                get_period_values(item).get(period, 0) or 0
                for item in asset_items
                if item in standardized and not standardized[item].get('has_mapped_parent', False)
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

    # Calculate other_liabilities (skip items whose parent is also mapped)
    total_liabilities_periods = get_period_values('total_liabilities')
    if total_liabilities_periods:
        other_liabilities_periods = {}
        for period in total_liabilities_periods:
            total_val = total_liabilities_periods[period]
            sum_val = sum(
                get_period_values(item).get(period, 0) or 0
                for item in liability_items
                if item in standardized and not standardized[item].get('has_mapped_parent', False)
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
    # Try total_stockholders_equity first, fall back to total_equity if not present
    total_se_periods = get_period_values('total_stockholders_equity')
    use_total_equity_fallback = False
    if not total_se_periods:
        # Fall back to total_equity if total_stockholders_equity is not mapped
        total_se_periods = get_period_values('total_equity')
        use_total_equity_fallback = True

    if total_se_periods:
        # If using total_stockholders_equity and total_equity exists, NCI items are between them
        if not use_total_equity_fallback and 'total_equity' not in standardized:
            equity_items.extend(['minority_interest', 'redeemable_non_controlling_interests'])
        # If using total_equity fallback, include NCI items in the equity calculation
        if use_total_equity_fallback:
            equity_items.extend(['minority_interest', 'redeemable_non_controlling_interests'])

        other_equity_periods = {}
        for period in total_se_periods:
            total_val = total_se_periods[period]
            sum_val = 0
            for item in equity_items:
                if item in standardized:
                    # Skip if parent is also mapped
                    if standardized[item].get('has_mapped_parent', False):
                        continue
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
        # Financial company asset items
        {'type': 'item', 'field': 'trading_and_derivative_assets_at_fair_value', 'label': 'Trading assets and derivative instruments', 'indent': 1},
        {'type': 'item', 'field': 'investment_securities', 'label': 'Investment securities', 'indent': 1},
        {'type': 'item', 'field': 'loans_and_financing_receivables_net', 'label': 'Loans and financing receivables, net', 'indent': 1},
        {'type': 'item', 'field': 'insurance_assets', 'label': 'Insurance-related assets', 'indent': 1},
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
        {'type': 'item', 'field': 'other_financial_assets', 'label': 'Other financial assets', 'indent': 1},
        {'type': 'item', 'field': 'other_assets', 'label': 'Other assets', 'indent': 1},
        {'type': 'subtotal', 'field': 'total_assets', 'label': 'TOTAL ASSETS'},
        {'type': 'blank'},
        {'type': 'major_section', 'label': 'LIABILITIES AND STOCKHOLDERS\' EQUITY'},
        {'type': 'section_header', 'label': 'Liabilities'},
        # Financial company liability items
        {'type': 'item', 'field': 'customer_and_policyholder_deposits', 'label': 'Customer and policyholder deposits', 'indent': 1},
        {'type': 'item', 'field': 'trading_and_derivative_liabilities_at_fair_value', 'label': 'Trading liabilities and derivative instruments', 'indent': 1},
        {'type': 'item', 'field': 'loss_and_claims_reserves_and_payables', 'label': 'Loss reserves and claims payable', 'indent': 1},
        {'type': 'item', 'field': 'short_term_debt', 'label': 'Short-term debt', 'indent': 1},
        {'type': 'item', 'field': 'long_term_debt', 'label': 'Long-term debt', 'indent': 1},
        {'type': 'item', 'field': 'account_payables', 'label': 'Accounts payable', 'indent': 1},
        {'type': 'item', 'field': 'accrued_payroll', 'label': 'Accrued compensation', 'indent': 1},
        {'type': 'item', 'field': 'accrued_expenses', 'label': 'Accrued expenses', 'indent': 1},
        {'type': 'item', 'field': 'accrued_interest_payable', 'label': 'Accrued interest payable', 'indent': 1},
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
        {'type': 'item', 'field': 'other_financial_liabilities', 'label': 'Other financial liabilities', 'indent': 1},
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
