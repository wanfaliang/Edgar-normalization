"""
Map Amazon Balance Sheet to Standardized Schema
================================================
Using the official schema from Plabel Investigation.csv
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from statement_reconstructor import StatementReconstructor
import yaml

# Amazon 2024Q2
adsh = '0001018724-24-000083'
cik = '1018724'
year, quarter = 2024, 2

print("\n" + "="*80)
print("AMAZON BALANCE SHEET - COMPLETE MAPPING TO STANDARDIZED SCHEMA")
print("="*80)
print(f"\nCompany: Amazon.com Inc (CIK: {cik})")
print(f"Filing: {adsh}")
print(f"Period: 2024Q2 (March 31, 2024)")

# Reconstruct balance sheet
reconstructor = StatementReconstructor(year=year, quarter=quarter)

result = reconstructor.reconstruct_statement_multi_period(
    cik=cik,
    adsh=adsh,
    stmt_type='BS'
)

if not result or not result.get('line_items'):
    print("❌ Failed to reconstruct balance sheet")
    sys.exit(1)

line_items = result['line_items']
periods = result.get('periods', [])

print(f"\n✅ Reconstructed Balance Sheet")
print(f"   Line items: {len(line_items)}")
print(f"   Periods: {len(periods)}")

# Extract all line items with values
print(f"\n" + "="*80)
print("ALL BALANCE SHEET LINE ITEMS")
print("="*80)

items_with_values = []
for item in line_items:
    plabel = item['plabel']
    tag = item.get('tag', '')

    # Get value for first period (March 31, 2024)
    values = item.get('values', {})
    if isinstance(values, dict) and len(values) > 0:
        value = list(values.values())[0]
    elif isinstance(values, list) and len(values) > 0:
        value = values[0]
    else:
        value = None

    items_with_values.append({
        'plabel': plabel,
        'tag': tag,
        'value': value
    })

# Display all items
print(f"\nFound {len(items_with_values)} line items:\n")

for i, item in enumerate(items_with_values, 1):
    value_str = f"${item['value']:>18,.0f}" if item['value'] else "N/A"
    print(f"{i:2d}. {item['plabel'][:65]:<65s} {value_str}")

# Now manually map to standardized schema
print(f"\n" + "="*80)
print("MAPPING TO STANDARDIZED SCHEMA")
print("="*80)

# Manual mapping based on semantic understanding + schema
mapping = {
    # ========== ASSETS ==========
    # Current Assets
    "Cash and cash equivalents": {
        "target": "cash_and_cash_equivalents",
        "confidence": 1.0,
        "notes": "Direct match"
    },

    "Marketable securities": {
        "target": "short_term_investments",
        "confidence": 1.0,
        "notes": "Marketable securities (current) = short-term investments"
    },

    "Inventories": {
        "target": "inventory",
        "confidence": 1.0,
        "notes": "Direct match (singular vs plural)"
    },

    "Accounts receivable, net and other": {
        "target": "account_receivables_net",
        "confidence": 0.9,
        "notes": "Contains receivables + other current assets aggregated. Primary component is receivables.",
        "also_contains": ["prepaids", "other_current_assets"]
    },

    "Total current assets": {
        "target": "total_current_assets",
        "confidence": 1.0,
        "notes": "Control total - must equal sum of current assets",
        "control": True
    },

    # Non-Current Assets
    "Property and equipment, net": {
        "target": "property_plant_equipment_net",
        "confidence": 1.0,
        "notes": "PP&E net of depreciation. Includes finance lease ROU assets per tag."
    },

    "Operating leases": {
        "target": "operating_lease_right_of_use_assets",
        "confidence": 1.0,
        "notes": "Operating lease ROU asset per ASC 842"
    },

    "Goodwill": {
        "target": "goodwill",
        "confidence": 1.0,
        "notes": "Direct match"
    },

    "Other assets": {
        "target": "other_non_current_assets",
        "confidence": 0.9,
        "notes": "Catch-all for non-current assets. Likely contains intangibles, LT investments, deferred tax assets.",
        "likely_contains": ["intangible_assets", "long_term_investments", "deferred_tax_assets"]
    },

    "Total assets": {
        "target": "total_assets",
        "confidence": 1.0,
        "notes": "Ultimate control total",
        "control": True
    },

    # ========== LIABILITIES ==========
    # Current Liabilities
    "Accounts payable": {
        "target": "account_payables",
        "confidence": 1.0,
        "notes": "Direct match"
    },

    "Accrued expenses and other": {
        "target": "accrued_expenses",
        "confidence": 0.9,
        "notes": "Contains accrued expenses + other current liabilities aggregated",
        "also_contains": ["other_current_liabilities"]
    },

    "Unearned revenue": {
        "target": "deferred_revenue",
        "confidence": 1.0,
        "notes": "Unearned revenue = deferred revenue (synonyms)"
    },

    "Total current liabilities": {
        "target": "total_current_liabilities",
        "confidence": 1.0,
        "notes": "Control total",
        "control": True
    },

    # Non-Current Liabilities
    "Long-term lease liabilities": {
        "target": "operating_lease_obligations_non_current",
        "confidence": 1.0,
        "notes": "Long-term operating lease liabilities (ASC 842)"
    },

    "Long-term debt": {
        "target": "long_term_debt",
        "confidence": 1.0,
        "notes": "Direct match"
    },

    "Other long-term liabilities": {
        "target": "other_non_current_liabilities",
        "confidence": 1.0,
        "notes": "Catch-all for non-current liabilities"
    },

    "Commitments and contingencies": {
        "target": "commitments_and_contingencies",
        "confidence": 1.0,
        "notes": "Direct match (typically zero value, disclosure item)"
    },

    "Total liabilities": {
        "target": None,  # Not in standardized schema as separate item
        "confidence": 1.0,
        "notes": "Amazon reports this but schema doesn't have it. Can calculate as current + non-current liabilities.",
        "skip": True
    },

    # ========== EQUITY ==========
    "Stockholders' equity:": {
        "target": None,
        "confidence": 1.0,
        "notes": "Section header, not a line item",
        "skip": True
    },

    "Preferred stock": {
        "target": "preferred_stock",
        "confidence": 1.0,
        "notes": "Direct match"
    },

    "Common stock": {
        "target": "common_stock",
        "confidence": 1.0,
        "notes": "Direct match"
    },

    "Treasury stock, at cost": {
        "target": "treasury_stock",
        "confidence": 1.0,
        "notes": "Direct match"
    },

    "Additional paid-in capital": {
        "target": "additional_paid_in_capital",
        "confidence": 1.0,
        "notes": "Direct match"
    },

    "Accumulated other comprehensive income (loss)": {
        "target": "accumulated_other_comprehensive_income_loss",
        "confidence": 1.0,
        "notes": "Direct match"
    },

    "Retained earnings": {
        "target": "retained_earnings",
        "confidence": 1.0,
        "notes": "Direct match"
    },

    "Total stockholders' equity": {
        "target": "total_stockholders_equity",
        "confidence": 1.0,
        "notes": "Control total",
        "control": True
    },

    "Total liabilities and stockholders' equity": {
        "target": "total_liabilities_and_total_equity",
        "confidence": 1.0,
        "notes": "Ultimate control - must equal total assets",
        "control": True,
        "validation": "Must equal total_assets"
    }
}

# Generate mapping output
print("\n" + "="*80)
print("MAPPING RESULTS")
print("="*80)

mapped_count = 0
skipped_count = 0
unmapped_count = 0

for item in items_with_values:
    plabel = item['plabel']
    value = item['value']

    if plabel in mapping:
        map_info = mapping[plabel]

        if map_info.get('skip'):
            skipped_count += 1
            status = "⊘ SKIP"
            target = map_info.get('notes', '')
        else:
            mapped_count += 1
            status = "✅ MAP"
            target = map_info['target']

        conf = map_info.get('confidence', 0)
        notes = map_info.get('notes', '')

        value_str = f"${value:>15,.0f}" if value else "N/A"

        print(f"\n{status} | {plabel}")
        print(f"       → {target}")
        print(f"       Value: {value_str} | Confidence: {conf:.1f}")
        if notes:
            print(f"       Notes: {notes}")
    else:
        unmapped_count += 1
        value_str = f"${value:>15,.0f}" if value else "N/A"
        print(f"\n⚠️  UNMAPPED | {plabel}")
        print(f"            Value: {value_str}")

print(f"\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"\nTotal line items: {len(items_with_values)}")
print(f"  ✅ Mapped: {mapped_count}")
print(f"  ⊘ Skipped: {skipped_count}")
print(f"  ⚠️  Unmapped: {unmapped_count}")
print(f"\nCoverage: {mapped_count}/{len(items_with_values)} = {mapped_count/len(items_with_values)*100:.1f}%")

# Save mapping to YAML
output_path = Path('mappings') / 'AMZN_1018724_balance_sheet.yaml'
output_path.parent.mkdir(exist_ok=True)

yaml_data = {
    'company': {
        'cik': cik,
        'name': 'Amazon.com Inc',
        'ticker': 'AMZN'
    },
    'filing': {
        'adsh': adsh,
        'period_end': '2024-03-31',
        'form': '10-Q',
        'dataset': f'{year}Q{quarter}'
    },
    'statement': 'balance_sheet',
    'mappings': {}
}

# Add mappings
for plabel, map_info in mapping.items():
    if not map_info.get('skip'):
        yaml_data['mappings'][plabel] = {
            'target': map_info['target'],
            'confidence': map_info['confidence'],
            'notes': map_info.get('notes', '')
        }
        if 'also_contains' in map_info:
            yaml_data['mappings'][plabel]['also_contains'] = map_info['also_contains']
        if 'likely_contains' in map_info:
            yaml_data['mappings'][plabel]['likely_contains'] = map_info['likely_contains']

with open(output_path, 'w') as f:
    yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

print(f"\n✅ Mapping saved to: {output_path}")
