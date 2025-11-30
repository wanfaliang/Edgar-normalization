"""
Income Statement Mapper
=======================
Map company income statements to standardized schema.

Strategy: Mix of exact matching + patterns - whatever works!
Goal: Generate YAML files, not perfect patterns.

Usage:
    python map_income_statement.py --cik 1018724 --adsh 0001018724-24-000083
"""

import sys
import re
import argparse
from pathlib import Path
import yaml

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from statement_reconstructor import StatementReconstructor
import psycopg2
from psycopg2.extras import RealDictCursor
from config import config


# Items to skip - they're calculated, not mapped
CALCULATED_ITEMS = {
    'other_adjustments_to_net_income',
    'net_income_deductions',
    'bottom_line_net_income',
    'gross_profit_ratio',
    'ebitda',
    'ebitda_ratio',
    'ebit',
    'ebit_ratio',
    'operating_income_ratio',
    'income_before_tax_ratio',
    'net_income_ratio'
}


def normalize_text(text):
    """Normalize text for matching"""
    if not text:
        return ""

    text = str(text).lower()
    text = text.replace("'", "")
    text = text.replace("'", "")
    text = text.replace('-', ' ')
    text = text.replace(',', '')
    text = re.sub(r'\([^)]*\)', '', text)  # Remove parentheticals
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def contains_all(text, terms):
    """Check if text contains all terms"""
    text_lower = text.lower()
    return all(term.lower() in text_lower for term in terms)


def contains_any(text, terms):
    """Check if text contains any of the terms"""
    text_lower = text.lower()
    return any(term.lower() in text_lower for term in terms)


def load_income_statement_schema():
    """
    Load income statement schema with variations.
    Mix of exact matches + pattern logic - pragmatic approach!
    """

    schema = {
        # Revenue
        'revenue': [
            'revenue',
            'total revenues',
            'net revenue',
            'net revenues',
            'revenues',
            'net sales',
            'sales',
            'total net sales',
            'total revenues net of interest expense',
            'total revenues net of expense',
            'revenues net of expenses',
            'total net revenue',
            'total net sales and revenue',
            'sales to customers',
            'total operating revenues'
        ],

        # Cost of Revenue
        'cost_of_revenue': [
            'cost of revenue',
            'cost of sales',
            'cost of sales net',
            'cost of products sold',
            'cost of goods sold',
            'total cost of sales',
            'total cost of revenues'
        ],

        # Gross Profit
        'gross_profit': ['gross profit', 'gross margin'],

        # Operating Expenses
        'research_and_development_expenses': [
            'research and development expenses',
            'research development and related expenses',
            'research development expenses',
            'r&d expenses',
            'research and development',
            'research and development expense',
            'technology and development',
            'product development'
        ],

        'general_and_administrative_expenses': [
            'general and administrative expenses',
            'general and administrative',
            'other selling and administrative expenses'
        ],

        'sales_and_marketing_expenses': [
            'sales and marketing',
            'selling and marketing',
            'selling and marketing expenses',
            'advertising and marketing',
            'advertising and promotion expenses',
            'marketing and sales'
        ],

        'selling_general_and_administrative_expenses': [
            'selling general and administrative expenses',
            'selling general and administrative',
            'marketing administration and research costs',
            'operating selling general and administrative expenses'
        ],

        'other_expenses': [
            'other expenses',
            'other expense net',
            'other expenses income net',
            'other operating expense income net'
        ],

        'operating_expenses': [
            'operating expenses',
            'total operating expenses',
            'total expenses'
        ],

        'cost_and_expenses': [
            'cost and expenses',
            'total cost and expenses',
            'total operating costs and expenses',
            'total operating costs'
        ],

        # Interest
        'interest_income': [
            'interest income',
            'interest income net'
        ],

        'interest_expense': [
            'interest expense',
            'interest expenses net',
            'interest expense net of amounts capitalized'
        ],

        'net_interest_income': [
            'net interest income',
            'interest income net',
            'interest expense net'
        ],

        # Depreciation
        'depreciation_and_amortization': [
            'depreciation and amortization',
            'depreciation and amortization expenses',
            'depreciation and amortization charges',
            'amortization of intangible assets'
        ],

        # Other Income
        'total_other_income_expenses_net': [
            'total other income expenses net',
            'other income expense net',
            'other income expenses',
            'total other income',
            'interest and other income expense',
            'interest income and other net',
            'total other income and expense',
            'other income (expense) net'  # Added from Amazon/Apple/Microsoft
        ],

        # Operating Income
        'operating_income': [
            'operating income',
            'operating loss',
            'operating income loss',
            'income loss',
            'operating income before income taxes',
            'operating loss before income taxes',
            'operating earnings',
            'loss from operations',
            'income from operations',
            'operating profit'
        ],

        'non_operating_income': [
            'non operating income',
            'non operating income loss',
            'non operating income net',
            'non operating loss net',
            'total non operating income expense',
            'other non operating income loss net'
        ],

        # Income Before Tax
        'income_before_tax': [
            'income before tax',
            'income before taxes',
            'earnings before tax',
            'earnings before taxes',
            'income before income tax',
            'income before income taxes',
            'earnings before income tax',
            'earnings before income taxes',
            'pretax income',
            'income before provision for income taxes',
            'earnings before provision for taxes on income'
        ],

        # Income Tax
        'income_tax_expense': [
            'income tax expense',
            'provision for income tax',
            'provision for income taxes',
            'income tax provision',
            'provision for taxes on income'
        ],

        # Net Income from Continuing Operations
        'net_income_from_continuing_operations': [
            'net income from continuing operations',
            'net loss from continuing operations',
            'net earnings from continuing operations'
        ],

        # Net Income from Discontinued Operations
        'net_income_from_discontinued_operations': [
            'net income from discontinued operations',
            'net loss from discontinued operations',
            'income from discontinued operations net of tax',
            'loss from discontinued operations net of tax'
        ],

        # Net Income
        'net_income': [
            'net income',
            'net earnings',
            'net loss',
            'consolidated net income',
            'consolidated net loss',
            'net income including noncontrolling interests',
            'net income including non controlling interests'
        ],

        # Attribution
        'net_income_attributed_to_non_controlling_interests': [
            'net income attributed to non controlling interests',
            'net income attributed to minority interests',
            'net income attributable to noncontrolling interests',
            'net earnings attributable to noncontrolling interests',
            'net loss attributable to noncontrolling interests'
        ],

        'net_income_attributable_to_controlling_interests': [
            'net income attributable to controlling interests',
            'net income attributable to common stockholders',
            'net income attributable to common stock',
            'net loss attributable to common stockholders'
        ]
    }

    return schema


def is_eps_or_shares_item(plabel, datatype):
    """
    Detect EPS or shares items using DATATYPE

    Simple & Accurate method:
    - datatype = "perShare" + basic/diluted → EPS
    - datatype = "shares" + basic/diluted → Share count

    Args:
        plabel: Plain text label
        datatype: XBRL datatype ("perShare", "shares", "monetary", etc.)

    Returns: target name or None
    """
    if not datatype:
        return None

    plabel_lower = plabel.lower()

    # Check for basic vs diluted in plabel
    has_basic = 'basic' in plabel_lower
    has_diluted = 'diluted' in plabel_lower

    if datatype == 'perShare':
        # EPS items
        if has_diluted:
            return 'eps_diluted'
        else:
            return 'eps'  # basic or unspecified

    elif datatype == 'shares':
        # Share count items
        if has_diluted:
            return 'weighted_average_shares_outstanding_diluted'
        else:
            return 'weighted_average_shares_outstanding'  # basic or unspecified

    return None


def find_best_match(plabel, datatype, schema_variations):
    """Find best matching schema item"""
    plabel_norm = normalize_text(plabel)

    # First check for EPS/shares items using DATATYPE
    eps_shares_target = is_eps_or_shares_item(plabel, datatype)
    if eps_shares_target:
        return eps_shares_target, 0.95, None

    # Regular matching
    best_match = None
    best_confidence = 0

    for target, variations in schema_variations.items():
        for variation in variations:
            variation_norm = normalize_text(variation)

            if plabel_norm == variation_norm:
                confidence = 1.0
                if confidence > best_confidence:
                    best_match = target
                    best_confidence = confidence

    return best_match, best_confidence, None


def map_income_statement(cik, adsh, year, quarter, company_name, ticker):
    """Map a company's income statement to standardized schema"""

    print(f"\n{'='*80}")
    print(f"MAPPING INCOME STATEMENT TO STANDARDIZED SCHEMA")
    print(f"{'='*80}")
    print(f"\nCompany: {company_name} (Ticker: {ticker}, CIK: {cik})")
    print(f"Filing: {adsh}")
    print(f"Dataset: {year}Q{quarter}")

    # Reconstruct income statement
    reconstructor = StatementReconstructor(year=year, quarter=quarter)

    result = reconstructor.reconstruct_statement_multi_period(
        cik=cik,
        adsh=adsh,
        stmt_type='IS'
    )

    if not result or not result.get('line_items'):
        print("❌ Failed to reconstruct income statement")
        return None

    line_items = result['line_items']
    periods = result.get('periods', [])

    print(f"\n✅ Reconstructed Income Statement")
    print(f"   Line items: {len(line_items)}")
    print(f"   Periods: {len(periods)}")

    # Load schema
    schema_variations = load_income_statement_schema()

    # Map each line item
    mappings = []
    unmapped = []
    learned_variations = []  # Track what we learned

    for item in line_items:
        plabel = item['plabel']
        tag = item.get('tag', '')
        datatype = item.get('datatype', '')  # perShare, shares, monetary, etc.

        # Get value for first period
        values = item.get('values', {})
        if isinstance(values, dict) and len(values) > 0:
            value = list(values.values())[0]
        elif isinstance(values, list) and len(values) > 0:
            value = values[0]
        else:
            value = None

        # Find best match (with DATATYPE for EPS/shares detection)
        target, confidence, learned_variation = find_best_match(plabel, datatype, schema_variations)

        if target:
            # Skip calculated items
            if target in CALCULATED_ITEMS:
                continue

            mappings.append({
                'plabel': plabel,
                'target': target,
                'confidence': confidence,
                'value': value,
                'tag': tag,
                'datatype': datatype
            })

            # Track learned variations
            if learned_variation:
                learned_variations.append(learned_variation)
        else:
            unmapped.append({
                'plabel': plabel,
                'value': value,
                'tag': tag,
                'datatype': datatype
            })

    # Display results
    print(f"\n{'='*80}")
    print("MAPPING RESULTS")
    print(f"{'='*80}")

    print(f"\n✅ Mapped Items ({len(mappings)}):")
    for m in mappings:
        import pandas as pd
        value_str = f"${m['value']:>18,.0f}" if m['value'] and not pd.isna(m['value']) else "N/A"
        conf_marker = "●" if m['confidence'] == 1.0 else "○"
        print(f"\n{conf_marker} {m['plabel'][:60]}")
        print(f"   → {m['target']}")
        print(f"   Value: {value_str} | Confidence: {m['confidence']:.2f}")

    if unmapped:
        print(f"\n⚠️  Unmapped Items ({len(unmapped)}):")
        for u in unmapped:
            import pandas as pd
            value_str = f"${u['value']:>18,.0f}" if u['value'] and not pd.isna(u['value']) else "N/A"
            print(f"   • {u['plabel'][:60]} | {value_str}")

    # Summary
    total = len(mappings) + len(unmapped)
    coverage = len(mappings) / total * 100 if total > 0 else 0

    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"\nTotal items: {total}")
    print(f"Mapped: {len(mappings)} ({coverage:.1f}%)")
    print(f"Unmapped: {len(unmapped)}")
    print(f"Average confidence: {sum(m['confidence'] for m in mappings) / len(mappings):.2f}" if mappings else "N/A")

    # Save to YAML
    output_dir = Path('mappings')
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / f"{ticker}_{cik}_income_statement.yaml"

    yaml_data = {
        'company': {
            'cik': cik,
            'name': company_name,
            'ticker': ticker
        },
        'filing': {
            'adsh': adsh,
            'dataset': f'{year}Q{quarter}'
        },
        'statement': 'income_statement',
        'mappings': {}
    }

    for m in mappings:
        yaml_data['mappings'][m['plabel']] = {
            'target': m['target'],
            'confidence': m['confidence']
        }

    with open(output_file, 'w') as f:
        yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)

    print(f"\n✅ Mapping saved to: {output_file}")

    return {
        'mappings': mappings,
        'unmapped': unmapped,
        'coverage': coverage
    }


if __name__ == "__main__":
    import pandas as pd

    parser = argparse.ArgumentParser(description='Map company income statement to standardized schema')
    parser.add_argument('--cik', required=True, help='Company CIK')
    parser.add_argument('--adsh', required=True, help='Filing ADSH')

    args = parser.parse_args()

    # Get company info from database
    conn = psycopg2.connect(config.get_db_connection())
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT c.company_name, c.ticker, f.source_year, f.source_quarter
        FROM companies c
        JOIN filings f ON c.cik = f.cik
        WHERE c.cik = %s AND f.adsh = %s
    """, (args.cik, args.adsh))

    info = cur.fetchone()
    cur.close()
    conn.close()

    if not info:
        print(f"❌ Filing not found: CIK {args.cik}, ADSH {args.adsh}")
        sys.exit(1)

    map_income_statement(
        cik=args.cik,
        adsh=args.adsh,
        year=info['source_year'],
        quarter=info['source_quarter'],
        company_name=info['company_name'],
        ticker=info['ticker'] or 'N/A'
    )
