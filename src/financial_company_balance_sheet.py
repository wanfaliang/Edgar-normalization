def normalize(text):
    """Normalize text for matching"""
    if not text:
        return ""
    return text.lower().replace('-', ' ').replace(',', '').replace('  ', ' ').strip()


def map_financial_bs_items(plabel, line_num, control_lines, tag='', negating=0, datatype='', is_sum=False, calc_children=None):
    p = normalize(plabel)
    t = tag.lower()  # Lowercase tag for pattern matching
    dt = datatype.lower() if datatype else ''  # Lowercase datatype for matching

    
    # Get control line numbers
    total_current_assets = control_lines.get('total_current_assets', float('inf'))
    total_non_current_assets = control_lines.get('total_non_current_assets', float('inf'))
    total_assets = control_lines.get('total_assets', float('inf'))
    total_current_liabilities = control_lines.get('total_current_liabilities', float('inf'))
    total_non_current_liabilities = control_lines.get('total_non_current_liabilities', float('inf'))
    total_liabilities = control_lines.get('total_liabilities', float('inf'))
    total_stockholders_equity_line = control_lines.get('total_stockholders_equity', float('inf'))
    total_liabilities_and_equity_line = control_lines.get('total_liabilities_and_total_equity', float('inf'))

    # run conditions to map out those whose parent is not a control item based on line_num of the control_lines
    # in such situation, what should we return? for now, we just return None


    if line_num < total_assets:
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
        if 'life insurance' in p:
            return 'owned_life_insurance'
        if 'federal bank' in p or 'federal home loan bank' in p or 'fhlb' in p or \
            'frb' in p or 'regulatory stock' in p   :
            return 'fedral_bank_stock'
        if 'real estate asset' in p : 
            return 'real_estate_assets_net'
        if 'foreclos' in p or 'repossesed' in p:
            return 'foreclosed_assets'
        if 'accquisiion' in p and ('intangible' in p or 'cost' in p):
            return 'acquisition_intangible_assets'
        if 'derivative' in p and ('asset' in p or 'assets' in p):
            return 'derivative_assets'
        if 'investment' in p and 'long term' in p:
            return 'long_term_investments'
        


        if is_sum and calc_children:
            for child_tag, weight, child_plabel in calc_children:
                cp = normalize(child_plabel) # we need to do this, right?

                if ('available for sale' in cp or 'afS' in cp or 'carried at fair value' in cp) or \
                    ('held to maturity' in cp or 'helf for investment' in cp or 'held for investment' in cp):
                    return 'investment_securities_total' 

    # the following are for liabilities parts
    elif line_num > total_assets:
        # the following go after equity parts, are for liabilities parts
        if ('deposit' in p or 'interest bearing' in p or 'savings' in p or 'checking' in p or 'time' in p 
            or 'money market' in p or 'time account' in p or 'certifictae of deposit' in p):
            return 'customer_deposits'
        if 'agreement' in p and ('repurchase' in p or 'repo' in p):
            return 'repurchase_agreements'
        if 'securit' in p and 'loan' in p :
            return 'securitized_loans'
        if 'secured' in p and ('borrowing' in p or 'debt' in p or 'loan' in p or 'financing' in p): 
            return 'secured_borrowings'
        if 'unsecured' in p and ('borrowing' in p or 'debt' in p or 'loan' in p 
                                 or 'financing' in p or 'debenture' in p or 'revolving credit facility' in p):
            return 'unsecured_borrowings'
        if 'trading' in p  and ('liabilit' in p or 'at fair value' in p) :
            return 'trading_liabilities_at_fair_value'  
        if 'derivative' in p and 'liabilit' in p:
            return 'derivative_liabilities'
        if ('reserve' in p or 'settlement' in p) and ('loss' in p or 'claim' in p or 'legal' in p):
            return 'reserves_for_losses'
        if 'federal home loan bank' in p or 'fhlb' in p or 'frb' in p or 'bank term funding program' in p or 'bTfb' in p:
            return 'federal_home_loan_bank_and_others_borrowings'
        if 'subordinated' in p and ('debt' in p or 'note' in p or 'loan' in p or 
                                    'borrowings' in p or 'financing' in p or 'debenture' in p):
            return 'subordinated_debt'
        if 'insurance' in p and 'assessment' in p:
            return 'insurance_assessments_payable'
        if 'federal income tax' in p or 'income tax payable' in p:
            return 'income_tax_payable'
        if 'unearned' in p and ('revenue' in p or 'income' in p or 'fee' in p or 'premium' in p):
            return 'unearned_revenue'
        if 'policyholder' in p and ('deposit'):
            return 'policyholder_deposits'
        if 'security deposit' in p:
            return 'security_deposits'
        if 'senior note' in p or 'senior debt' in p:
            return 'senior_notes_and_debt'
        if 'bond' in p:
            return 'bonds'
        if 'acceptance' in p:
            return 'acceptances_outstanding'
        if 'non recourse' in p and ('mortgage' in p):
            return 'non_recourse_mortgage'
        if 'intangible' in p and 'liabilit' in p:
            return 'intangible_liabilities'
        