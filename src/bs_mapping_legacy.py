"""
Balance Sheet Legacy Mapping
=============================
Pattern-based mapping for balance sheets without total_current_assets or total_current_liabilities.
Used as fallback when residual calculation logic cannot be applied.

This module contains the old "other_*" pattern matching approach.
"""


def get_legacy_other_patterns():
    """
    Returns dict of "other_*" field patterns for pattern-based matching.
    These patterns are added back when control items are missing.

    Returns mapping of field_name -> (section, pattern_check_function)
    """

    def check_other_current_assets(p, line_num, control_lines):
        return 'other' in p and 'current' in p and 'asset' in p

    def check_other_non_current_assets(p, line_num, control_lines):
        return ('other' in p and ('non current' in p or 'long term' in p) and
                'asset' in p and 'total' not in p)

    def check_other_payables(p, line_num, control_lines):
        return 'other' in p and ('payable' in p or 'payables' in p)

    def check_other_current_liabilities(p, line_num, control_lines):
        return 'other' in p and 'current' in p and 'liabilit' in p

    def check_other_non_current_liabilities(p, line_num, control_lines):
        return ('other' in p and ('non current' in p or 'long term' in p) and
                'liabilit' in p)

    def check_other_total_stockholders_equity(p, line_num, control_lines):
        return 'other' in p and 'equity' in p

    return {
        'other_current_assets': check_other_current_assets,
        'other_non_current_assets': check_other_non_current_assets,
        'other_payables': check_other_payables,
        'other_current_liabilities': check_other_current_liabilities,
        'other_non_current_liabilities': check_other_non_current_liabilities,
        'other_total_stockholders_equity': check_other_total_stockholders_equity,
    }


def map_bs_item_with_legacy_others(plabel, line_num, control_lines, primary_mapper):
    """
    Map balance sheet item using primary mapper, with fallback to legacy "other_*" patterns.

    Args:
        plabel: Plain label text
        line_num: Statement order line number
        control_lines: Dict of control item line numbers
        primary_mapper: Function that does primary pattern matching (without "other_*")

    Returns:
        Standardized field name or None
    """
    # Try primary mapping first
    target = primary_mapper(plabel, line_num, control_lines)

    if target:
        return target

    # Fallback: try legacy "other_*" patterns
    p = plabel.lower().strip()
    legacy_patterns = get_legacy_other_patterns()

    for field_name, check_func in legacy_patterns.items():
        if check_func(p, line_num, control_lines):
            return field_name

    return None
