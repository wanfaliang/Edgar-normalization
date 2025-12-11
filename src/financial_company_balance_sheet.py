def normalize(text):
    """Normalize text for matching"""
    if not text:
        return ""
    return text.lower().replace('-', ' ').replace(',', '').replace('  ', ' ').strip()


def map_financial_balance_sheet_label_assets(p):
    p = normalize(p)
    if 'cash and cash equivalents' ==p:
        return 'cash_and_cash_equivalents'
    if  ('due from bank' in p) or ('due' in p and 'bank' in p):
        return 'due_from_bank'
    if ('deposits with bank' in p) or ('interest' in p and 'deposit' in p) or ('time deposit' in p):
        return 'deposits_with_bank'
    if 'resell' in p or 'resale' in p:
        return 'resale_agreement'
    if ('trading' in p  or 'equity securit' in p or 'investment' in p)  and \
        ('fair value' in p or 'asset' in p) :
        return 'trading_assets_at_fair_value'
    if ('available for sale' in p or 'afS' in p or 'carried at fair value' in p) :
        return 'available_for_sale_securities'
    if 'held to maturity' in p or 'helf for investment' in p or 'held for investment' in p:
        return 'held_to_maturity_securities'
    if (('loan' in p or 'mortgage' in p or 'lease' in p) and ('held for sale' in p or 'held for investment' in p)) or \
        ('net' in p or 'after' in p or 'allowance' in p):
        return 'loans_held_for_sale'
    if ('loan' in p and 'net of allowance' in p ) or ('mortgage' in p and 'net of allowance' in p) or \
       'net loan' in p or 'net mortgage' in p or ('mortgage' in p and 'net' in p) or ('loan' in p and 'net' in p):
        return 'loans_net_of_allowance'
    if 'accrued' in p or 'receivable' in p or 'recoverable' in p:
        return 'accrued_receivables'
    if 'premise' in p or 'equipment' in p or 'fixed asset' in p:
        return 'premises_and_equipment'
    if 'life insurance' in p:
        return 'owned_life_insurance'
    if 'federal bank' in p or 'federal home loan bank' in p or 'fhlb' in p or \
        'frb' in p or 'regulatory stock' in p   :
        return 'fedral_bank_stock'
    if 'real estate asset' in p and  'net' in p: # not complete
        return 'real_estate_assets_net'
    if 'foreclos' in p or 'repossesed' in p:
        return 'foreclosed_assets'
    if 'accquisiion' in p and ('intangible' in p or 'cost' in p):
        return 'acquisition_intangible_assets'