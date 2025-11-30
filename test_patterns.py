import re

def normalize_text(text):
    """Normalize text for matching"""
    if not text:
        return ""

    text = str(text).lower()
    text = text.replace("'", "")
    text = text.replace("'", "")
    text = text.replace('-', ' ')
    text = text.replace(',', '')
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def contains_all_terms(text, terms):
    """Check if text contains all terms"""
    text_lower = normalize_text(text)
    return all(term.lower() in text_lower for term in terms)


def contains_any_term(text, terms):
    """Check if text contains any term"""
    text_lower = normalize_text(text)
    return any(term.lower() in text_lower for term in terms)


def pattern_matches(plabel, pattern):
    """
    Check if plabel matches a pattern.

    Pattern syntax:
        [contains X] - contains term X
        [contains X and Y] - contains both X and Y
        [contains X or Y] - contains either X or Y
        not [contains X] - does not contain X
    """
    plabel_norm = normalize_text(plabel)

    # Handle "not" patterns
    if ' not [' in pattern:
        parts = pattern.split(' not [')
        positive_pattern = parts[0].strip()
        negative_pattern = '[' + parts[1]

        # Must match positive and NOT match negative
        return (pattern_matches(plabel, positive_pattern) and
                not pattern_matches(plabel, negative_pattern))

    # Remove square brackets
    pattern = pattern.strip('[]')

    # Handle "contains X and Y"
    if ' and contains ' in pattern:
        terms = [t.strip() for t in pattern.replace('contains', '').split(' and ')]
        terms = [t for t in terms if t]  # Remove empty
        return contains_all_terms(plabel_norm, terms)

    # Handle "contains X or Y"
    if ' or ' in pattern:
        terms = [t.strip() for t in pattern.replace('contains', '').split(' or ')]
        terms = [t for t in terms if t]
        return contains_any_term(plabel_norm, terms)

    # Simple "contains X"
    if 'contains' in pattern:
        term = pattern.replace('contains', '').strip()
        return term.lower() in plabel_norm

    return False


# Test patterns
tests = [
    ('Accounts receivable', '[contains account or accounts and contains receivable or receivables]'),
    ('Additions to property and equipment', '[contains expenditure or expenditures or purchases or purchase or acquisition or acquisitions and contains property or plant or plants or equipment or equipments or ppe]'),
    ('Purchases of investments', '[contains purchases or purchase and contains investments or investment or securities or security]'),
    ('Common stock issued', '[contains common stock or common stocks or shares and contains issuance or proceeds] not [contains net]'),
]

for label, pattern in tests:
    result = pattern_matches(label, pattern)
    print(f'{label:45s} | Match: {result}')
