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
        if  ('due from bank' in p) :
            return 'cash_and_cash_equivalents'
        if ('deposits with bank' in p) or ('interest' in p and 'deposit' in p) or ('time deposit' in p):
            return 'cash_and_cash_equivalents'
        
        if (('trading' in p  or 'equity securit' in p or 'investment' in p)  and \
            ('fair value' in p or 'asset' in p)) and 'income investment' not in p:
            return 'trading_and_derivative_assets_at_fair_value'
        if 'derivative' in p and ('asset' in p or 'assets' in p):
            return 'trading_and_derivative_assets_at_fair_value'
                
        if ('available for sale' in p or 'carried at fair value' in p) :
            return 'investment_securities'
        if 'held to maturity' in p or 'held as investment' in p or 'held for investment' in p or ('investment' in p and 'at amortized cost' in p):
            return 'investment_securities'
        
        if 'resell' in p or 'resale' in p:
            return 'loans_and_financing_receivables_net'
        if (('loan' in p or 'mortgage' in p or 'lease' in p) and ('held for sale' in p or 'held for investment' in p)) :
            return 'loans_and_financing_receivables_net'
        if (('loan' in p and 'net of allowance' in p ) or ('mortgage' in p and 'net of allowance' in p) or \
        'net loan' in p or 'net mortgage' in p or ('mortgage' in p and 'net' in p) or ('loan' in p and 'net' in p)) or \
            ('receivable' in p and 'financ' in p) :
            return 'loans_and_financing_receivables_net'
        if ('accrued' in p or 'receivable' in p or 'recoverable' in p) and ('interest' in p or 'dividend' in p 
                                                                            or 'mortgage' in p or 'premium' in p or 'financ' in p):
            return 'loans_and_financing_receivables_net'
        
        if 'life insurance' in p:
            return 'insurance_assets'
        if 'federal bank' in p or 'federal home loan bank' in p or 'fhlb' in p or \
            'frb' in p or 'regulatory stock' in p   :
            return 'long_term_investments'
        if 'real estate asset' in p : 
            return 'other_financial_assets'
        if 'foreclos' in p or 'repossessed' in p:
            return 'other_financial_assets'
        if 'acquisition' in p and ('intangible' in p or 'cost' in p):
            return 'intangible_assets'

        if is_sum and calc_children:
            for child_tag, weight, child_plabel in calc_children:
                cp = normalize(child_plabel) # we need to do this, right?

                if ('available for sale' in cp or 'afs' in cp or 'carried at fair value' in cp) or \
                    ('held to maturity' in cp or 'held as investment' in cp or 'held for investment' in cp):
                    return 'investment_securities' 

    # the following are for liabilities parts
    elif line_num > total_assets:
        # the following go after equity parts, are for liabilities parts
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
        
        if 'agreement' in p and ('repurchase' in p or 'repo' in p):
            return 'short_term_debt'
        
        if 'trading' in p  and ('liabilit' in p or 'at fair value' in p) :
            return 'trading_and_derivative_liabilities_at_fair_value'  
        if 'derivative' in p and 'liabilit' in p:
            return 'trading_and_derivative_liabilities_at_fair_value'
        
        if ('reserve' in p or 'settlement' in p) and ('loss' in p or 'claim' in p or 'legal' in p):
            return 'loss_and_claims_reserves_and_payables'
        if 'insurance' in p and 'assessment' in p:
            return 'loss_and_claims_reserves_and_payables'
        
        if 'securit' in p and 'loan' in p :
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
        if 'non recourse' in p and ('mortgage' in p):
            return 'long_term_debt'
        if 'intangible' in p and 'liabilit' in p:
            return 'other_financial_liabilities'
        