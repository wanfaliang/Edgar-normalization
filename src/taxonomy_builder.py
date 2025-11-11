"""
Taxonomy Builder
================
Builds comprehensive taxonomy from Finexus database models with format conversion.
Handles CamelCase (SEC/API) ↔ snake_case (Database) bidirectional mapping.

Usage:
    python src/taxonomy_builder.py

Author: Faliang & Claude
Date: November 2025
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Set
import sys

# Add src to path
sys.path.append(str(Path(__file__).parent))
from database.models_from_finexus import IncomeStatement, BalanceSheet, CashFlow
from database.data_transform import camel_to_snake


def snake_to_camel(snake_str: str) -> str:
    """
    Convert snake_case to CamelCase (PascalCase)

    Args:
        snake_str: String in snake_case format

    Returns:
        String in CamelCase format

    Examples:
        >>> snake_to_camel('net_income')
        'NetIncome'
        >>> snake_to_camel('stockholders_equity')
        'StockholdersEquity'
        >>> snake_to_camel('eps_diluted')
        'EpsDiluted'
    """
    components = snake_str.split('_')
    return ''.join(x.title() for x in components)


def generate_sec_tag_variations(base_camel: str) -> List[str]:
    """
    Generate common SEC tag variations for a base concept

    SEC tags often have prefixes like 'us-gaap:', suffixes, or slight variations

    Args:
        base_camel: Base CamelCase field name (e.g., 'NetIncome')

    Returns:
        List of possible SEC tag variations

    Examples:
        >>> generate_sec_tag_variations('NetIncome')
        ['NetIncome', 'NetIncomeLoss', 'ProfitLoss', ...]
    """
    variations = [base_camel]

    # Common SEC tag patterns
    if 'Income' in base_camel and 'Loss' not in base_camel:
        variations.append(base_camel.replace('Income', 'IncomeLoss'))

    if 'Profit' in base_camel and 'Loss' not in base_camel:
        variations.append(base_camel.replace('Profit', 'ProfitLoss'))

    if 'Expense' in base_camel and 'Expenses' not in base_camel:
        variations.append(base_camel + 's')

    # Add common suffixes
    if base_camel.endswith('Asset') or base_camel.endswith('Liability'):
        variations.append(base_camel + 's')

    return variations


def extract_finexus_fields() -> Dict[str, List[str]]:
    """
    Extract all field names from Finexus models

    Returns:
        Dictionary with statement types and their field names (snake_case)
    """
    # Fields to exclude (metadata, not financial concepts)
    excluded_fields = {
        'symbol', 'date', 'period', 'reported_currency', 'cik',
        'filling_date', 'filing_date', 'accepted_date',
        'calendar_year', 'fiscal_year', 'created_at', 'updated_at'
    }

    fields = {
        'income_statement': [],
        'balance_sheet': [],
        'cash_flow': []
    }

    # Income Statement fields
    for column in IncomeStatement.__table__.columns:
        if column.name not in excluded_fields:
            fields['income_statement'].append(column.name)

    # Balance Sheet fields
    for column in BalanceSheet.__table__.columns:
        if column.name not in excluded_fields:
            fields['balance_sheet'].append(column.name)

    # Cash Flow fields
    for column in CashFlow.__table__.columns:
        if column.name not in excluded_fields:
            fields['cash_flow'].append(column.name)

    return fields


def build_finexus_taxonomy() -> Dict:
    """
    Build comprehensive taxonomy from Finexus database models
    Maps both snake_case (database) and CamelCase (SEC/API) versions

    Returns:
        Dictionary with full taxonomy including both formats
    """
    fields = extract_finexus_fields()

    taxonomy = {
        'income_statement': [],
        'balance_sheet': [],
        'cash_flow': []
    }

    for statement_type, field_list in fields.items():
        for snake_field in field_list:
            camel_field = snake_to_camel(snake_field)

            taxonomy[statement_type].append({
                'snake_case': snake_field,
                'camel_case': camel_field,
                'sec_variations': generate_sec_tag_variations(camel_field),
                'statement': statement_type
            })

    # Add metadata
    taxonomy['metadata'] = {
        'total_concepts': sum(len(v) for v in fields.values()),
        'income_statement_count': len(fields['income_statement']),
        'balance_sheet_count': len(fields['balance_sheet']),
        'cash_flow_count': len(fields['cash_flow']),
        'format_note': 'snake_case for database, CamelCase for SEC/API matching'
    }

    return taxonomy


def generate_sec_to_finexus_mapping() -> Dict:
    """
    Generate mapping: SEC CamelCase Tag → Finexus snake_case field
    Includes all common variations

    Returns:
        Dictionary mapping SEC tag variations to database field names
    """
    taxonomy = build_finexus_taxonomy()
    mapping = {}

    for statement_type in ['income_statement', 'balance_sheet', 'cash_flow']:
        for concept in taxonomy[statement_type]:
            snake_field = concept['snake_case']

            # Map base CamelCase
            mapping[concept['camel_case']] = {
                'field': snake_field,
                'statement': statement_type
            }

            # Map all SEC variations
            for variation in concept['sec_variations']:
                if variation not in mapping:  # Don't overwrite if already mapped
                    mapping[variation] = {
                        'field': snake_field,
                        'statement': statement_type,
                        'note': 'variation'
                    }

    return mapping


def generate_standard_concepts_for_ai() -> List[str]:
    """
    Generate clean list of standard concepts for AI mapping
    Uses descriptive names based on snake_case fields

    Returns:
        List of human-readable concept names
    """
    fields = extract_finexus_fields()
    concepts = []

    for statement_type, field_list in fields.items():
        for snake_field in field_list:
            # Convert to readable format: net_income → Net Income
            readable = snake_field.replace('_', ' ').title()
            concepts.append(readable)

    return sorted(concepts)


def save_taxonomy(output_dir: Path):
    """
    Save all taxonomy artifacts

    Args:
        output_dir: Directory to save taxonomy files
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Building Finexus taxonomy...")
    taxonomy = build_finexus_taxonomy()

    print("Generating SEC → Finexus mapping...")
    sec_mapping = generate_sec_to_finexus_mapping()

    print("Generating standard concepts list...")
    concepts = generate_standard_concepts_for_ai()

    # Save taxonomy (full details)
    with open(output_dir / 'finexus_taxonomy_full.json', 'w', encoding='utf-8') as f:
        json.dump(taxonomy, f, indent=2)

    print(f"✅ Saved: {output_dir / 'finexus_taxonomy_full.json'}")

    # Save SEC → Finexus mapping
    with open(output_dir / 'sec_to_finexus_mapping.json', 'w', encoding='utf-8') as f:
        json.dump(sec_mapping, f, indent=2)

    print(f"✅ Saved: {output_dir / 'sec_to_finexus_mapping.json'}")

    # Save concepts list (for AI mapping)
    with open(output_dir / 'standard_concepts.json', 'w', encoding='utf-8') as f:
        json.dump(concepts, f, indent=2)

    print(f"✅ Saved: {output_dir / 'standard_concepts.json'}")

    # Save summary CSV
    import pandas as pd

    summary_data = []
    for statement_type in ['income_statement', 'balance_sheet', 'cash_flow']:
        for concept in taxonomy[statement_type]:
            summary_data.append({
                'statement': statement_type,
                'database_field': concept['snake_case'],
                'sec_tag_base': concept['camel_case'],
                'sec_variations': ', '.join(concept['sec_variations'])
            })

    df = pd.DataFrame(summary_data)
    df.to_csv(output_dir / 'taxonomy_summary.csv', index=False)

    print(f"✅ Saved: {output_dir / 'taxonomy_summary.csv'}")

    # Print statistics
    print("\n" + "=" * 80)
    print("TAXONOMY BUILD COMPLETE")
    print("=" * 80)
    print(f"\nTotal Concepts: {taxonomy['metadata']['total_concepts']}")
    print(f"  - Income Statement: {taxonomy['metadata']['income_statement_count']}")
    print(f"  - Balance Sheet: {taxonomy['metadata']['balance_sheet_count']}")
    print(f"  - Cash Flow: {taxonomy['metadata']['cash_flow_count']}")
    print(f"\nSEC Tag Variations: {len(sec_mapping)}")
    print(f"\nFiles created in: {output_dir}")
    print("  1. finexus_taxonomy_full.json    ← Full taxonomy with both formats")
    print("  2. sec_to_finexus_mapping.json   ← SEC tag → DB field lookup")
    print("  3. standard_concepts.json        ← Concepts list for AI mapping")
    print("  4. taxonomy_summary.csv          ← Human-readable summary")

    # Show sample mappings
    print("\n" + "-" * 80)
    print("SAMPLE MAPPINGS:")
    print("-" * 80)
    sample_count = 0
    for sec_tag, mapping_info in sec_mapping.items():
        if sample_count < 10:
            print(f"  {sec_tag:35} → {mapping_info['field']:35} ({mapping_info['statement']})")
            sample_count += 1
        else:
            break

    print("\n✅ Ready for AI-powered tag mapping with proper format conversion!")


def main():
    """Main execution"""
    output_dir = Path('data/taxonomy')
    save_taxonomy(output_dir)


if __name__ == "__main__":
    main()
