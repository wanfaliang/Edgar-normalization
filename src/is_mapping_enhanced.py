"""
Financial Statements Mapper
===========================
This script enhances mapping financial statement line items (Income Statement, Cash Flow) by utilizing
an not only pattern mapping but also calc graph.

Features:
- Maps BS, IS, CF with consistent naming from CSV v4 "Field Names in DB" column
- Auto-assignment to other_* categories for unmapped items
- 100% coverage for all statements
- ONE YAML file with all three statements
- ONE Excel file with reconstructed + standardized sheets

Usage:
    python map_financial_statements.py --cik 789019 --adsh 0000950170-24-118967
"""

import sys
import argparse
from pathlib import Path
import yaml
import pandas as pd
from collections import defaultdict
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from statement_reconstructor import StatementReconstructor
from map_financial_statements_strategy2 import (
    should_use_strategy2,
    map_balance_sheet_strategy2,
    calculate_residuals_strategy2,
    get_balance_sheet_structure_strategy2
)
import psycopg2
from psycopg2.extras import RealDictCursor
from config import config


def normalize(text):
    """Normalize text for matching"""
    if not text:
        return ""
    return text.lower().replace('-', ' ').replace(',', '').replace(':', '').replace("'", "").replace('  ', ' ').strip()





# ============================================================================
# INCOME STATEMENT MAPPING
# ============================================================================

def find_is_control_items(line_items):
    """
    Find control items for income statement.

    Returns dict with line numbers for:
    - revenue
    - operating_income
    - income_tax_expense (required)
    - net_income (required)
    - eps (required)
    - eps_diluted (required)
    - weighted_average_shares_outstanding
    - weighted_average_shares_outstanding_diluted
    """
    control_lines = {}

    for item in line_items:
        p = normalize(item['plabel'])
        line_num = item.get('stmt_order', 0)
        datatype = item.get('datatype')
        

        # 1. revenue (CSV line 54)
        # Pattern: [contains 'total revenues' or contains 'net revenue' or contains 'net revenues' or contains 'revenues' or contains 'net sales' or contains 'sales' or contains 'total net sales' or contains 'total net revenue' or contains 'total net sales and revenue'  or (contains 'total' and contains 'revenues')]
        if 'revenue' not in control_lines:
            if ('total revenue' in p or 'net revenue' in p or 'net revenues' in p or 'revenues' in p or \
               'net sales' in p or 'sales' in p or 'total net sales' in p or 'total net revenue' in p or \
               'total net sales and revenue' in p or ('total' in p and 'revenues' in p) or 'revenue'== p or 'revenue:' ==p) and ('marketing' not in p and 'admini' not in p and 'general' not in p):
                if 'cost' not in p and 'deferred' not in p:
                    control_lines['revenue'] = line_num

        # 2. operating_income (CSV line 69)
        # Pattern: [(contains 'operating' or contains 'operation' or contains 'continuing') and (contains 'income' or contains 'loss' or contains 'profit' or contains 'earnings')]
        if 'operating_income' not in control_lines:
            if (('operating' in p or 'operation' in p or 'continuing' in p) and \
               ('income' in p or 'loss' in p or 'profit' in p or 'earnings' in p)) and ('other' not in p):
                control_lines['operating_income'] = line_num

        # 3. income_tax_expense (CSV line 72) - REQUIRED
        # Pattern: [(contains 'taxes' or contains 'tax') and (contains 'provision' or contains 'benefit' or contains 'expense' or contains 'expenses')]
        if 'income_tax_expense' not in control_lines:
            if ('taxes' in p or 'tax' in p) and ('provision' in p or 'benefit' in p or 'expense' in p or 'expenses' in p or 'on' in p or 'income' in p) and ('before' not in p):
                control_lines['income_tax_expense'] = line_num

        # 4. net_income (CSV line 75) - REQUIRED
        # Pattern: [(contains 'net income' or contains 'net loss' or contains 'net earings' or contains 'net profit') not (contains 'other' or contains 'continuing' or contains 'discontinuing' or contains 'operating' or contains 'operation')]
        if 'net_income' not in control_lines:
            if ('net income' in p or 'net loss' in p or 'net earings' in p or 'net profit' in p):
                if 'other' not in p and 'continuing' not in p and 'discontinuing' not in p and 'operating' not in p and 'operation' not in p:
                    control_lines['net_income'] = line_num

        # 5. eps (CSV line 78) - REQUIRED
        # Pattern: min{[contains 'basic'] and [datatype = perShare]}
        if 'eps' not in control_lines:
            if 'basic' in p and datatype == 'perShare':
                control_lines['eps'] = line_num

        # 6. eps_diluted (CSV line 79) - REQUIRED
        # Pattern: min{[contains 'diluted'] and [datatype = perShare]}
        if 'eps_diluted' not in control_lines:
            if 'diluted' in p and datatype == 'perShare':
                control_lines['eps_diluted'] = line_num

        # 7. weighted_average_shares_outstanding (CSV line 80)
        # Pattern: [contains 'basic'] and [datatype = shares]
        if 'weighted_average_shares_outstanding' not in control_lines:
            if 'basic' in p and datatype == 'shares':
                control_lines['weighted_average_shares_outstanding'] = line_num

        # 8. weighted_average_shares_outstanding_diluted (CSV line 81)
        # Pattern: [contains 'diluted'] and [datatype = shares]
        if 'weighted_average_shares_outstanding_diluted' not in control_lines:
            if 'diluted' in p and datatype == 'shares':
                control_lines['weighted_average_shares_outstanding_diluted'] = line_num

    return control_lines


def classify_is_section(line_num, control_lines):
    """Classify IS item into section"""
    revenue = control_lines.get('revenue', 0)
    gross_profit = control_lines.get('gross_profit', float('inf'))
    operating_income = control_lines.get('operating_income', float('inf'))
    income_before_tax = control_lines.get('income_before_tax', float('inf'))
    net_income = control_lines.get('net_income', float('inf'))

    if line_num <= gross_profit:
        return 'revenue_and_cogs'
    elif line_num <= operating_income:
        return 'operating_expenses'
    elif line_num <= income_before_tax:
        return 'non_operating'
    elif line_num <= net_income:
        return 'tax_and_net_income'
    else:
        return 'below_net_income'


def map_is_item(plabel, line_num, control_lines, datatype=None):
    """Map an income statement line item to standardized target"""
    p = normalize(plabel)

    # Map control items DIRECTLY by line number (no duplicate patterns)
    if line_num == control_lines.get('revenue'):
        return 'revenue'
    if line_num == control_lines.get('gross_profit'):
        return 'gross_profit'
    if line_num == control_lines.get('operating_income'):
        return 'operating_income'
    if line_num == control_lines.get('income_before_tax'):
        return 'income_before_tax'
    if line_num == control_lines.get('income_tax_expense'):
        return 'income_tax_expense'
    if line_num == control_lines.get('net_income'):
        return 'net_income'
    if line_num == control_lines.get('eps'):
        return 'eps'
    if line_num == control_lines.get('eps_diluted'):
        return 'eps_diluted'
    if line_num == control_lines.get('weighted_average_shares_outstanding'):
        return 'weighted_average_shares_outstanding'
    if line_num == control_lines.get('weighted_average_shares_outstanding_diluted'):
        return 'weighted_average_shares_outstanding_diluted'

    # Revenue - CSV line 54
    if 'revenue' in p or 'sales' in p:
        if 'marketing' not in p and 'admini' not in p and 'general' not in p:
            if 'cost' not in p and 'deferred' not in p and 'unearned' not in p:
                return 'revenue'

    # Cost of revenue - CSV line 55
    if ('cost' in p and ('revenue' in p or 'sales' in p or 'sold' in p or 'sale' in p)) or 'cogs' in p:
        return 'cost_of_revenue'

    # Gross profit - CSV line 56
    if 'gross profit' in p or 'gross margin' in p or 'gross income' in p:
        return 'gross_profit'

    # CSV line 63: Cost and expenses
    if 'total costs and expenses' in p or 'total cost and expenses' in p or 'total operating costs and expenses' in p or 'total operating costs' in p:
        return 'cost_and_expenses'

    section = classify_is_section(line_num, control_lines)

    # Operating expenses - match CSV field names
    # CSV line 57: R&D
    if 'research' in p or 'development' in p or 'r&d' in p or 'technology' in p:
        return 'research_and_development_expenses'

    # CSV line 60: SG&A (combined)
    if ('sales' in p or 'marketing' in p or 'selling' in p or 'sale' in p or 'advertising' in p or 'promotion' in p) and 'administrative' in p:
        return 'selling_general_and_administrative_expenses'

    # CSV line 59: Sales and marketing (not administrative)
    if ('sales' in p or 'marketing' in p or 'selling' in p or 'sale' in p or 'advertising' in p or 'promotion' in p) and 'administrative' not in p:
        return 'sales_and_marketing_expenses'

    # CSV line 58: G&A (not selling/marketing)
    if ('general' in p and 'administrative' in p) and 'selling' not in p and 'marketing' not in p and 'advertising' not in p and 'promotion' not in p and 'sales' not in p:
        return 'general_and_administrative_expenses'

    # CSV line 67: Depreciation and amortization (IS version)
    if 'depreciation' in p or 'amortization' in p:
        return 'depreciation_and_amortization'

    # CSV line 62: Operating expenses
    if 'total operating expenses' in p or 'total expenses' in p:
        return 'operating_expenses'

    # CSV line 61: Other expenses
    if 'other' in p and ('expense' in p or 'expenses' in p or 'income' in p):
        return 'other_expenses'

    # Operating income - CSV line 69
    if ('operating' in p or 'operation' in p or 'continuing' in p) and ('income' in p or 'loss' in p or 'profit' in p or 'earnings' in p):
        return 'operating_income'

    # CSV line 64: Interest income
    if 'interest' in p and 'income' in p:
        return 'interest_income'

    # CSV line 65: Interest expense
    if ('interest' in p or 'interests' in p) and ('expense' in p or 'expenses' in p):
        return 'interest_expense'

    # CSV line 66: Net interest income
    if ('interest' in p or 'interests' in p) and ('expense' in p or 'expenses' in p) and 'income' in p:
        return 'net_interest_income'

    # CSV line 68: Total other income/expenses net
    if 'other' in p and ('income' in p or 'gains' in p or 'gain' in p or 'loss' in p or 'losses' in p or 'expenses' in p):
        return 'total_other_income_expenses_net'

    # CSV line 70: Non-operating income
    if ('non-operating' in p or 'non-operation' in p or 'discontinued' in p) and ('income' in p or 'loss' in p or 'earnings' in p or 'expenses' in p or 'expense' in p):
        return 'non_operating_income'

    # Income before tax - CSV line 71
    if 'pretax' in p or ('before' in p and ('tax' in p or 'taxes' in p)):
        return 'income_before_tax'

    # Income tax expense - CSV line 72
    if ('tax' in p or 'taxes' in p) and ('provision' in p or 'benefit' in p or 'expense' in p or 'expenses' in p) and ('before' not in p):
        return 'income_tax_expense'

    # CSV line 73: Net income from continuing operations
    if ('net income' in p or 'net loss' in p or 'net earnings' in p) and 'continuing' in p:
        return 'net_income_from_continuing_operations'

    # CSV line 74: Net income from discontinued operations
    if ('net income' in p or 'net loss' in p or 'net earnings' in p or 'income' in p or 'loss' in p or 'earnings' in p or 'deficit' in p) and 'discontinued' in p:
        return 'net_income_from_discontinued_operations'

    # CSV line 76: Net income attributed to non-controlling interests
    if ('net income' in p or 'net loss' in p or 'net earnings' in p or 'net profit' in p) and 'attributable to' in p and ('non-controlling' in p or 'noncontrolling' in p or 'minority' in p):
        return 'net_income_attributed_to_non_controlling_interests'

    # CSV line 77: Net income attributable to controlling interests
    if ('net income' in p or 'net loss' in p or 'net earnings' in p or 'net profit' in p) and 'attributable to' in p and 'non-controlling' not in p and 'noncontrolling' not in p and 'minority' not in p:
        return 'net_income_attributable_to_controlling_interests'

    # CSV line 75: Net income (general)
    if ('net income' in p or 'net loss' in p or 'net earnings' in p or 'net profit' in p) and 'other' not in p and 'continuing' not in p and 'discontinuing' not in p and 'operating' not in p and 'operation' not in p:
        return 'net_income'

    # EPS and Shares - use datatype metadata to distinguish - match CSV field names
    if section == 'below_net_income':
        # Use datatype to distinguish EPS (perShare) from share counts (shares)
        if p == 'basic' or 'earnings per share' in p or 'eps' in p:
            if datatype == 'perShare' or 'earnings per share' in p or 'eps' in p:
                return 'eps'
            elif datatype == 'shares' or 'weighted average' in p:
                return 'weighted_average_shares_outstanding'
        if p == 'diluted':
            if datatype == 'perShare':
                return 'eps_diluted'
            elif datatype == 'shares':
                return 'weighted_average_shares_outstanding_diluted'
        # Explicit matches
        if 'weighted average' in p and 'shares' in p:
            if 'diluted' in p:
                return 'weighted_average_shares_outstanding_diluted'
            else:
                return 'weighted_average_shares_outstanding'

    return None


# ============================================================================
# CASH FLOW MAPPING
# ============================================================================

def find_cf_control_items(line_items):
    """
    Find control items for cash flow.

    Returns dict with line numbers for:
    - net_income (required)
    - net_cash_provided_by_operating_activities (required)
    - net_cash_provided_by_investing_activities (required)
    - net_cash_provided_by_financing_activities (required)
    - cash_at_beginning_of_period (required)
    - cash_at_end_of_period (required)
    """
    control_lines = {}

    for item in line_items:
        p = normalize(item['plabel'])
        line_num = item.get('stmt_order', 0)
        iord = item.get('iord', '')
        ddate = item.get('ddate', '')
        qtrs = item.get('qtrs', '')
        tag = normalize(item.get('tag', ''))

        # 1. net_income (CSV line 93) - REQUIRED
        # Pattern: [ contains 'net income' or 'net earnings' or 'net income (loss)']
        if 'net_income' not in control_lines:
            if 'net income' in p or 'net earnings' in p or 'net income (loss)' in p or 'profit' in p or 'net loss' in p or ('net' in p and 'loss' in p):
                control_lines['net_income'] = line_num

        # 2. net_cash_provided_by_operating_activities (CSV line 117) - REQUIRED
        # Pattern: [contains 'cash' and (contains 'operating' or contains 'operations')] not [contains 'other' or contains 'others']
        if 'net_cash_provided_by_operating_activities' not in control_lines:
            if ('cash' in p and ('operating' in p or 'operations' in p) and 'other' not in p and 'others' not in p) or ('total operating' in p):
                control_lines['net_cash_provided_by_operating_activities'] = line_num

        # 3. net_cash_provided_by_investing_activities (CSV line 126) - REQUIRED
        # Pattern: [contains 'cash' and contains 'investing'] not [contains 'other' or contains 'others']
        if 'net_cash_provided_by_investing_activities' not in control_lines:
            if ('cash' in p and 'investing' in p and 'other' not in p and 'others' not in p) or ('total investing' in p):
                control_lines['net_cash_provided_by_investing_activities'] = line_num

        # 4. net_cash_provided_by_financing_activities (CSV line 152) - REQUIRED
        # Pattern: [contains 'cash' and contains 'financing'] not [contains 'other' or  contains 'others']
        if 'net_cash_provided_by_financing_activities' not in control_lines:
            if ('cash' in p and 'financing' in p and 'other' not in p and 'others' not in p) or ('total financing' in p):
                control_lines['net_cash_provided_by_financing_activities'] = line_num

        # 5. cash_at_beginning_of_period (CSV line 156) - REQUIRED
        # Pattern: [iord='I' (instant) and (contains 'cash' in plabel OR tag) and contains 'beginning']
        # Use TAG metadata (iord) like reconstructor does
        # Handle cases like Starbucks where plabel is just "Beginning of period" without 'cash'
        if 'cash_at_beginning_of_period' not in control_lines:
            if iord == 'I':
                # Check if it's a cash-related item (plabel or tag contains 'cash')
                is_cash_item = 'cash' in p or 'cash' in tag
                if is_cash_item:
                    if 'beginning' in p or 'begin' in p or qtrs == '0':
                        control_lines['cash_at_beginning_of_period'] = line_num

        # 6. cash_at_end_of_period (CSV line 155) - REQUIRED
        # Pattern: [iord='I' (instant) and (contains 'cash' in plabel OR tag) and contains 'end']
        # Use TAG metadata (iord) like reconstructor does
        # Handle cases like Starbucks where plabel is just "End of period" without 'cash'
        if 'cash_at_end_of_period' not in control_lines:
            if iord == 'I':
                # Check if it's a cash-related item (plabel or tag contains 'cash')
                is_cash_item = 'cash' in p or 'cash' in tag
                if is_cash_item:
                    if 'end' in p or 'ending' in p or 'close' in p or qtrs == '0':
                        # Prefer ending over beginning (ending usually appears later)
                        if 'cash_at_beginning_of_period' in control_lines:
                            control_lines['cash_at_end_of_period'] = line_num
                        elif 'beginning' not in p and 'begin' not in p:
                            control_lines['cash_at_end_of_period'] = line_num

    return control_lines


def classify_cf_section(line_num, control_lines):
    """Classify CF item into section - returns 'operating', 'investing', 'financing', or 'supplemental'"""
    if not control_lines:
        return 'unknown'

    operating_end = control_lines.get('net_cash_provided_by_operating_activities', 0)
    investing_end = control_lines.get('net_cash_provided_by_investing_activities', 0)
    financing_end = control_lines.get('net_cash_provided_by_financing_activities', 0)

    # Classify based on which section this line falls into
    if line_num <= operating_end:
        return 'operating'
    elif line_num <= investing_end:
        return 'investing'
    elif line_num <= financing_end:
        return 'financing'
    else:
        return 'supplemental'


def map_cf_item(plabel, line_num, control_lines, tag='', line_items=None):
    """Map a cash flow line item to standardized target - matches structure field names"""
    p = normalize(plabel)
    t = normalize(tag)

    # Find position of working capital items for other_adjustments check
    wc_positions = []
    if line_items:
        for item in line_items:
            item_p = normalize(item['plabel'])
            item_line = item.get('stmt_order', float('inf'))
            # Check for accounts_receivables, inventory, or accounts_payables
            if (('account' in item_p or 'accounts' in item_p) and ('receivable' in item_p or 'receivables' in item_p)) or \
               ('inventory' in item_p or 'inventories' in item_p) or \
               (('account' in item_p or 'accounts' in item_p) and ('payable' in item_p or 'payables' in item_p)):
                wc_positions.append(item_line)
    min_wc_position = min(wc_positions) if wc_positions else float('inf')

    # Map control items DIRECTLY by line number (no duplicate patterns)
    if line_num == control_lines.get('net_income'):
        return 'net_income_starting_line'
    if line_num == control_lines.get('net_cash_provided_by_operating_activities'):
        return 'net_cash_provided_by_operating_activities'
    if line_num == control_lines.get('net_cash_provided_by_investing_activities'):
        return 'net_cash_provided_by_investing_activities'
    if line_num == control_lines.get('net_cash_provided_by_financing_activities'):
        return 'net_cash_provided_by_financing_activities'
    if line_num == control_lines.get('cash_at_beginning_of_period'):
        return 'cash_at_beginning_of_period'
    if line_num == control_lines.get('cash_at_end_of_period'):
        return 'cash_at_end_of_period'

    # Apply ALL specific patterns WITHOUT section restrictions

    # ========================================================================
    # OPERATING ACTIVITIES
    # ========================================================================

    # CSV line 94: Depreciation and amortization (combined)
    if ('depreciation' in p) and ('amortization' in p):
        return 'depreciation_and_amortization'

    # CSV line 95: Depreciation only
    if 'depreciation' in p and 'amortization' not in p:
        return 'depreciation'

    # CSV line 96: Amortization only
    if 'amortization' in p and 'depreciation' not in p:
        return 'amortization'

    # CSV line 98: Impairments
    if 'impairment' in p or 'impairments' in p:
        return 'impairments'

    # CSV line 99: Pension and postretirement
    if 'pension' in p or 'postretirement' in p:
        return 'pension_and_postretirement'

    # CSV line 100: Stock-based compensation
    if ('stock-based' in p or 'stock based' in p or 'share-based' in p or 'share based' in p) and 'compensation' in p:
        return 'stock_based_compensation'

    # CSV line 101: Non-operating expense/income
    if ('non-operating' in p or 'non operating' in p) and ('expense' in p or 'expenses' in p or 'income' in p):
        return 'non_operating_expense_income'
    if 'non-cash' in p and 'expenses' in p:
        return 'non_operating_expense_income'

    # CSV line 102: Investment gains/losses
    if ('gain' in p or 'gains' in p or 'loss' in p or 'losses' in p) and ('investment' in p or 'investments' in p):
        return 'investment_gains_losses'

    # CSV line 97: Deferred income tax
    if 'deferred' in p and ('tax' in p or 'taxes' in p):
        return 'deferred_income_tax'

    # CSV: Other adjustments - exact match "other" or "other, net" AND position_before working capital items
    if p in ['other', 'other net', 'other, net'] and line_num < min_wc_position:
        return 'other_adjustments'

    # CSV line 104: Change in other working capital
    if 'other working capital' in p or ('other' in p and 'assets' in p):
        return 'change_in_other_working_capital'

    # CSV line 105: Accounts receivables
    if ('account' in p or 'accounts' in p) and ('receivable' in p or 'receivables' in p):
        return 'accounts_receivables'

    # CSV line 106: Vendor receivables
    if 'vendor' in p and ('receivable' in p or 'receivables' in p):
        return 'vendor_receivables'

    # CSV line 107: Inventory
    if 'inventory' in p or 'inventories' in p:
        return 'inventory'

    # CSV line 108: Prepaids
    if 'prepaid' in p or 'prepaids' in p or 'prepayment' in p or 'prepayments' in p:
        return 'prepaids'

    # CSV line 109: Accounts payables
    if ('account' in p or 'accounts' in p) and ('payable' in p or 'payables' in p):
        return 'accounts_payables'

    # CSV line 110: Accrued expenses
    if 'accrued' in p:
        return 'accrued_expenses'

    # CSV line 111: Unearned revenue
    if 'unearned' in p:
        return 'unearned_revenue'

    # CSV line 112: Income taxes payable
    if 'income taxes' in p and ('payable' in p or 'payables' in p):
        return 'income_taxes_payable'

    # CSV line 113: Income taxes (not payable, not deferred, not paid)
    if ('income taxes' in p or 'income tax' in p) and 'payable' not in p and 'deferred' not in p and 'paid' not in p:
        return 'income_taxes'

    # CSV line 114: Other assets
    if 'other' in p and 'assets' in p:
        return 'other_assets'

    # CSV line 115: Other liabilities
    if 'other' in p and 'liabilities' in p:
        return 'other_liabilities'

    # ========================================================================
    # INVESTING ACTIVITIES
    # ========================================================================

    # CSV line 118: Capital expenditures (investments in PP&E)
    if ('expenditure' in p or 'expenditures' in p or 'purchase' in p or 'purchases' in p or 'acquisition' in p or 'acquisitions' in p or 'addition' in p or 'additions' in p) and \
       ('property' in p or 'plant' in p or 'plants' in p or 'equipment' in p or 'equipments' in p or 'ppe' in p):
        return 'investments_in_property_plant_and_equipment'

    # CSV line 119: Proceeds from sales of PP&E
    if ('proceeds' in p or 'sale' in p or 'sales' in p or 'disposition' in p) and \
       ('property' in p or 'plant' in p or 'plants' in p or 'equipment' in p or 'equipments' in p or 'ppe' in p):
        return 'proceeds_from_sales_of_ppe'

    # CSV line 120: Acquisitions of business
    if ('business' in p or 'businesses' in p) and ('acquisition' in p or 'acquisitions' in p):
        return 'acquisitions_of_business_net'

    # CSV line 121: Proceeds from divestiture
    if ('divestiture' in p or 'sale' in p or 'sales' in p or 'disposition' in p) and ('business' in p or 'businesses' in p):
        return 'proceeds_from_divestiture'

    # CSV line 122: Other acquisitions and investments
    if 'other' in p and ('acquisition' in p or 'acquisitions' in p or 'investments' in p):
        return 'other_aquisitons_and_investments'

    # CSV line 123: Purchases of investments
    if ('purchase' in p or 'purchases' in p or 'acquisition' in p or 'acquisitions' in p) and ('investment' in p or 'investments' in p or 'securities' in p):
        return 'purchases_of_investments'

    # CSV line 124: Sales/maturities of investments
    if ('sale' in p or 'sales' in p or 'maturity' in p or 'maturities' in p or 'proceeds' in p) and ('investment' in p or 'investments' in p or 'securities' in p):
        return 'sales_maturities_of_investments'

    # ========================================================================
    # FINANCING ACTIVITIES
    # ========================================================================

    # CSV line 127: Short-term debt issuance
    if 'short-term' in p and ('issuance' in p or 'proceeds' in p):
        return 'short_term_debt_issuance'

    # CSV line 128: Long-term debt issuance
    if 'long-term' in p and ('issuance' in p or 'proceeds' in p):
        return 'long_term_net_debt_issuance'

    # CSV line 129: Short-term debt repayment
    if 'short-term' in p and ('repayment' in p or 'repayments' in p):
        return 'short_term_debt_repayment'

    # CSV line 130: Long-term debt repayment
    if 'long-term' in p and ('repayment' in p or 'repayments' in p):
        return 'long_term_net_debt_repayment'

    # CSV line 131: Change in short-term debt net
    if ('change' in p or 'changes' in p) and ('short-term debt' in p or 'short-term' in p):
        return 'change_in_short_term_debt_net'

    # CSV line 132: Commercial paper net
    if 'commercial paper' in p:
        return 'commercial_paper_net'

    # CSV line 133: Change in long-term debt net
    if ('change' in p or 'changes' in p) and ('long-term debt' in p or 'long-term' in p):
        return 'change_in_long_term_debt_net'

    # CSV line 134: Term debt issuance (not short/long term specific)
    if 'debt' in p and ('issuance' in p or 'proceeds' in p) and 'short-term' not in p and 'long-term' not in p:
        return 'term_debt_issuance'

    # CSV line 135: Term debt repayment (not short/long term specific)
    if 'debt' in p and ('repayment' in p or 'repayments' in p) and 'short-term' not in p and 'long-term' not in p:
        return 'term_debt_repayment'

    # CSV line 136: Change in term debt
    if 'debt' in p and ('change' in p or 'changes' in p) and 'short-term' not in p and 'long-term' not in p:
        return 'change_in_term_debt'

    # CSV line 137: Finance lease repayment
    if ('finance lease' in p or 'finance leases' in p) and ('repayment' in p or 'repayments' in p or 'principal' in p):
        return 'finance_lease_repayment'

    # CSV line 138: Financing obligations repayment
    if ('financing obligation' in p or 'financing obligations' in p) and ('repayment' in p or 'repayments' in p or 'principal' in p):
        return 'financing_obligations_repayment'

    # CSV line 139: Net stock issuance
    if 'net stock issuance' in p:
        return 'net_stock_issuance'

    # CSV line 140: Net common stock issuance
    if 'net' in p and ('common stock' in p or 'common stocks' in p) and ('issuance' in p or 'proceeds' in p):
        return 'net_common_stock_issuance'

    # CSV line 141: Common stock issuance (not net)
    if ('common stock' in p or 'common stocks' in p or 'shares' in p) and ('issuance' in p or 'issued' in p or 'proceeds' in p) and 'net' not in p:
        return 'common_stock_issuance'

    # CSV line 142: Taxes on share settlement
    if ('tax' in p or 'taxes' in p) and ('share' in p or 'shares' in p) and ('settlement' in p or 'vesting' in p):
        return 'taxes_on_share_settlement'

    # CSV line 143: Net preferred stock issuance
    if 'net' in p and ('preferred stock' in p or 'preferred stocks' in p) and ('issuance' in p or 'proceeds' in p):
        return 'net_preferred_stock_issuance'

    # CSV line 144: Preferred stock issuance (not net)
    if ('preferred stock' in p or 'preferred stocks' in p) and ('issuance' in p or 'proceeds' in p) and 'net' not in p:
        return 'preferred_stock_issuance'

    # CSV line 145: Common stock repurchased
    if (('treasury' in p or 'share' in p or 'stock' in p or 'stocks' in p) and ('purchase' in p or 'purchases' in p)) or \
       ('repurchase' in p or 'repurchases' in p or 'repurchased' in p):
        return 'common_stock_repurchased'

    # CSV line 146: Proceeds from issuance of stock (special purpose)
    if (('treasury stock' in p or 'treasury stocks' in p) and ('issuance' in p or 'proceeds' in p)) or \
       ('proceeds' in p and 'options' in p) or ('proceeds' in p and 'compensation' in p):
        return 'proceeds_from_issuance_of_stock_sp'

    # CSV line 147-149: Dividends paid
    if 'dividend' in p or 'dividends' in p:
        if 'common' in p and 'preferred' not in p:
            return 'common_dividends_paid'
        elif 'preferred' in p and 'common' not in p:
            return 'preferred_dividends_paid'
        else:
            return 'dividends_paid'

    # CSV line 150: Issuance costs
    if 'issuance costs' in p:
        return 'issuance_costs'

    # ========================================================================
    # OTHER ITEMS
    # ========================================================================

    # CSV line 153: Effect of foreign exchange rate changes
    if 'exchange' in p or 'foreign currency' in p or 'foreign currencies' in p:
        return 'effect_of_foreign_exchanges_rate_changes_on_cash'

    # CSV line 154: Net change in cash
    if ('net change' in p or 'net increase' in p or 'net decrease' in p or 'increase' in p or 'decrease' in p) and 'cash' in p and \
       'operating' not in p and 'investing' not in p and 'financing' not in p:
        return 'net_change_in_cash'

    # CSV line 160: Income taxes paid
    if 'income taxes' in p and ('payment' in p or 'payments' in p or 'paid' in p):
        return 'income_taxes_paid'

    # CSV line 161: Interest paid
    if ('payment' in p or 'payments' in p or 'paid' in p) and ('interest' in p or 'interests' in p):
        return 'interest_paid'

    # Section totals
    if 'net cash' in p:
        if 'operating' in p or 'operations' in p:
            return 'net_cash_provided_by_operating_activities'
        elif 'investing' in p:
            return 'net_cash_provided_by_investing_activities'
        elif 'financing' in p:
            return 'net_cash_provided_by_financing_activities'

    # Supplemental - cash beginning/ending
    is_cash_item = 'cash' in p or 'cash' in t
    if is_cash_item and ('beginning' in p or 'start' in p):
        return 'cash_at_beginning_of_period'
    if is_cash_item and ('end' in p or 'close' in p or 'ending' in p):
        return 'cash_at_end_of_period'

    # CSV line 116, 125, 151: ONLY use section for "other" items (no distinctive keywords)
    if 'other' in p:
        section = classify_cf_section(line_num, control_lines)
        if section == 'operating':
            return 'other_operating_activities'
        elif section == 'investing':
            return 'other_investing_activities'
        elif section == 'financing':
            return 'other_financing_activities'

    return None
