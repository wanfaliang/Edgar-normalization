"""
Manual Taxonomy Comparison Tool
================================
Helps manually compare extracted SEC tags against Finexus taxonomy.
Generates a checklist for human review.

Usage:
    python tools/manual_taxonomy_comparison.py

Author: Faliang & Claude
Date: November 2025
"""

import json
import pandas as pd
from pathlib import Path
from typing import Dict, List
import sys

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / 'src'))
from database.models_from_finexus import IncomeStatement, BalanceSheet, CashFlow
from database.data_transform import camel_to_snake


def extract_finexus_fields() -> Dict[str, List[str]]:
    """Extract all field names from Finexus models"""

    fields = {
        'income_statement': [],
        'balance_sheet': [],
        'cash_flow': []
    }

    # Income Statement fields
    for column in IncomeStatement.__table__.columns:
        if column.name not in ['symbol', 'date', 'period', 'reported_currency',
                                'cik', 'filling_date', 'filing_date', 'accepted_date',
                                'calendar_year', 'fiscal_year', 'created_at', 'updated_at']:
            fields['income_statement'].append(column.name)

    # Balance Sheet fields
    for column in BalanceSheet.__table__.columns:
        if column.name not in ['symbol', 'date', 'period', 'reported_currency',
                                'cik', 'filling_date', 'filing_date', 'accepted_date',
                                'calendar_year', 'fiscal_year', 'created_at', 'updated_at']:
            fields['balance_sheet'].append(column.name)

    # Cash Flow fields
    for column in CashFlow.__table__.columns:
        if column.name not in ['symbol', 'date', 'period', 'reported_currency',
                                'cik', 'filing_date', 'accepted_date',
                                'fiscal_year', 'created_at', 'updated_at']:
            fields['cash_flow'].append(column.name)

    return fields


def load_sec_to_finexus_mapping() -> Dict:
    """Load SEC tag to Finexus field mapping"""
    mapping_file = Path('data/taxonomy/sec_to_finexus_mapping.json')

    if mapping_file.exists():
        with open(mapping_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        print("⚠️  Warning: sec_to_finexus_mapping.json not found. Run taxonomy_builder.py first.")
        return {}


def auto_match_tag_to_finexus(tag: str, tlabel: str, mapping: Dict) -> tuple:
    """
    Automatically match SEC tag to Finexus field using format conversion

    Args:
        tag: SEC tag (e.g., 'NetIncomeLoss')
        tlabel: SEC tag label (e.g., 'Net Income (Loss)')
        mapping: SEC to Finexus mapping dictionary

    Returns:
        (matched_field, confidence) tuple
        - matched_field: Finexus field name or None
        - confidence: 'exact', 'converted', or None
    """
    # Try exact match (for already CamelCase tags)
    if tag in mapping:
        return mapping[tag]['field'], 'exact'

    # Try converting tag to snake_case and see if it exists in Finexus
    snake_tag = camel_to_snake(tag)

    # Check if snake_tag matches any Finexus field
    for sec_tag, info in mapping.items():
        if info['field'] == snake_tag:
            return snake_tag, 'converted'

    return None, None


def load_extracted_tags(profiles_dir: Path) -> pd.DataFrame:
    """Load all extracted tag profiles"""

    all_tags = []

    profile_files = list(profiles_dir.glob('company_*_tags.json'))

    for file in profile_files:
        with open(file, 'r', encoding='utf-8') as f:
            profile = json.load(f)

            for tag_detail in profile['tag_details']:
                all_tags.append({
                    'company_cik': profile['cik'],
                    'company_name': profile['company_name'],
                    'industry': profile['industry'],
                    'tag': tag_detail['tag'],
                    'tlabel': tag_detail['tlabel'],
                    'custom': tag_detail['custom'],
                    'datatype': tag_detail['datatype'],
                    'iord': tag_detail['iord'],
                    'occurrence_count': tag_detail['occurrence_count'],
                    'doc': tag_detail.get('doc', '')[:200]  # First 200 chars
                })

    return pd.DataFrame(all_tags)


def generate_comparison_report(profiles_dir: Path, output_dir: Path):
    """Generate manual comparison report with auto-matching"""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading Finexus taxonomy...")
    finexus_fields = extract_finexus_fields()

    print("Loading SEC → Finexus mapping...")
    sec_mapping = load_sec_to_finexus_mapping()

    print("Loading extracted SEC tags...")
    sec_tags_df = load_extracted_tags(profiles_dir)

    # Get unique tags
    unique_tags = sec_tags_df.drop_duplicates(subset=['tag'])[
        ['tag', 'tlabel', 'custom', 'datatype', 'iord', 'doc']
    ].sort_values('tag')

    print(f"\nLoaded:")
    print(f"  - Finexus fields: {sum(len(v) for v in finexus_fields.values())}")
    print(f"  - Unique SEC tags: {len(unique_tags)}")
    print(f"  - Companies: {sec_tags_df['company_cik'].nunique()}")

    # Generate comparison spreadsheet
    print("\nGenerating comparison spreadsheet...")

    with pd.ExcelWriter(output_dir / 'MANUAL_TAXONOMY_COMPARISON.xlsx') as writer:

        # Sheet 1: Finexus Taxonomy
        finexus_df = pd.DataFrame([
            {'statement': 'Income Statement', 'field_name': f}
            for f in finexus_fields['income_statement']
        ] + [
            {'statement': 'Balance Sheet', 'field_name': f}
            for f in finexus_fields['balance_sheet']
        ] + [
            {'statement': 'Cash Flow', 'field_name': f}
            for f in finexus_fields['cash_flow']
        ])
        finexus_df.to_excel(writer, sheet_name='Finexus Taxonomy', index=False)

        # Sheet 2: SEC Tags (Top 500 most common) with auto-matching
        top_tags = sec_tags_df.groupby(['tag', 'tlabel', 'custom', 'datatype', 'doc']).agg({
            'occurrence_count': 'sum',
            'company_name': lambda x: ', '.join(x.unique()[:3])  # First 3 companies
        }).reset_index().sort_values('occurrence_count', ascending=False).head(500)

        # Auto-match tags to Finexus fields
        top_tags['auto_match'] = ''
        top_tags['match_confidence'] = ''

        for idx, row in top_tags.iterrows():
            matched_field, confidence = auto_match_tag_to_finexus(row['tag'], row['tlabel'], sec_mapping)
            if matched_field:
                top_tags.at[idx, 'auto_match'] = matched_field
                top_tags.at[idx, 'match_confidence'] = confidence

        # Reorder columns to show auto-match first
        column_order = ['tag', 'tlabel', 'auto_match', 'match_confidence', 'custom', 'datatype',
                       'occurrence_count', 'company_name', 'doc']
        top_tags = top_tags[column_order]

        # Add manual review columns
        top_tags['verified'] = ''     # User confirms auto-match is correct
        top_tags['manual_map'] = ''   # User's manual mapping if auto-match is wrong
        top_tags['notes'] = ''        # Additional notes

        top_tags.to_excel(writer, sheet_name='SEC Tags - Top 500', index=False)

        # Sheet 3: Standard (non-custom) tags only with auto-matching
        standard_tags = sec_tags_df[sec_tags_df['custom'] == False].groupby(
            ['tag', 'tlabel', 'datatype', 'doc']
        ).agg({
            'occurrence_count': 'sum',
            'company_name': lambda x: ', '.join(x.unique()[:3])
        }).reset_index().sort_values('occurrence_count', ascending=False)

        # Auto-match standard tags
        standard_tags['auto_match'] = ''
        standard_tags['match_confidence'] = ''

        for idx, row in standard_tags.iterrows():
            matched_field, confidence = auto_match_tag_to_finexus(row['tag'], row['tlabel'], sec_mapping)
            if matched_field:
                standard_tags.at[idx, 'auto_match'] = matched_field
                standard_tags.at[idx, 'match_confidence'] = confidence

        # Reorder columns
        standard_column_order = ['tag', 'tlabel', 'auto_match', 'match_confidence', 'datatype',
                                'occurrence_count', 'company_name', 'doc']
        standard_tags = standard_tags[standard_column_order]

        # Add manual review columns
        standard_tags['verified'] = ''
        standard_tags['manual_map'] = ''
        standard_tags['notes'] = ''

        standard_tags.to_excel(writer, sheet_name='Standard Tags Only', index=False)

        # Sheet 4: By Industry
        industry_tags = sec_tags_df.groupby(['industry', 'tag', 'custom']).agg({
            'occurrence_count': 'sum',
            'company_name': 'count'
        }).reset_index().sort_values(['industry', 'occurrence_count'], ascending=[True, False])

        industry_tags.to_excel(writer, sheet_name='Tags by Industry', index=False)

        # Sheet 5: Comparison Instructions (updated for auto-matching)
        instructions = pd.DataFrame([
            {'Step': 1, 'Action': 'Review "Finexus Taxonomy" sheet - familiarize yourself with existing fields'},
            {'Step': 2, 'Action': 'Go to "SEC Tags - Top 500" sheet - now includes AUTO-MATCHING!'},
            {'Step': 3, 'Action': 'Review "auto_match" column - shows automatic matches using format conversion'},
            {'Step': 4, 'Action': 'Check "match_confidence" - "exact" means perfect match, "converted" means format conversion applied'},
            {'Step': 5, 'Action': 'Verify auto-matches: mark "verified" column with Y if correct, N if incorrect'},
            {'Step': 6, 'Action': 'For incorrect auto-matches, provide correct mapping in "manual_map" column'},
            {'Step': 7, 'Action': 'For tags with NO auto-match, identify what they should map to (use "manual_map" column)'},
            {'Step': 8, 'Action': 'Focus on standard tags (custom=0) and high occurrence counts first'},
            {'Step': 9, 'Action': 'Use "Standard Tags Only" sheet for cleaner view (no company-specific tags)'},
            {'Step': 10, 'Action': 'Use "Tags by Industry" to spot industry-specific patterns'},
            {'Step': 11, 'Action': 'Identify gaps: common tags without matches = missing from Finexus taxonomy'},
            {'Step': 12, 'Action': 'Document findings and share for discussion'}
        ])
        instructions.to_excel(writer, sheet_name='INSTRUCTIONS', index=False)

    print(f"\n✅ Comparison spreadsheet created: {output_dir / 'MANUAL_TAXONOMY_COMPARISON.xlsx'}")

    # Generate summary CSV
    summary = {
        'total_finexus_fields': sum(len(v) for v in finexus_fields.values()),
        'income_statement_fields': len(finexus_fields['income_statement']),
        'balance_sheet_fields': len(finexus_fields['balance_sheet']),
        'cash_flow_fields': len(finexus_fields['cash_flow']),
        'unique_sec_tags': len(unique_tags),
        'standard_sec_tags': len(unique_tags[unique_tags['custom'] == False]),
        'custom_sec_tags': len(unique_tags[unique_tags['custom'] == True]),
        'companies_analyzed': sec_tags_df['company_cik'].nunique(),
        'industries': sec_tags_df['industry'].nunique()
    }

    pd.DataFrame([summary]).T.to_csv(output_dir / 'comparison_summary.csv', header=['value'])

    print(f"✅ Summary saved: {output_dir / 'comparison_summary.csv'}")

    # Generate text checklist
    print("\nGenerating manual checklist...")

    checklist = []
    checklist.append("=" * 80)
    checklist.append("MANUAL TAXONOMY COMPARISON CHECKLIST (WITH AUTO-MATCHING)")
    checklist.append("=" * 80)
    checklist.append("")
    checklist.append("GOAL: Identify gaps between SEC EDGAR tags and Finexus taxonomy")
    checklist.append("")
    checklist.append("✨ NEW: AUTO-MATCHING ENABLED!")
    checklist.append("The tool now automatically matches SEC tags (CamelCase) to Finexus fields (snake_case)")
    checklist.append("Your job: VERIFY auto-matches and identify gaps")
    checklist.append("")
    checklist.append("INSTRUCTIONS:")
    checklist.append("1. Open MANUAL_TAXONOMY_COMPARISON.xlsx")
    checklist.append("2. Check 'auto_match' column - many tags are already matched!")
    checklist.append("3. Review 'match_confidence': exact = perfect, converted = format conversion")
    checklist.append("4. Verify auto-matches are correct (mark in 'verified' column)")
    checklist.append("5. Focus on tags WITHOUT auto-matches - these are potential gaps")
    checklist.append("6. Note patterns and missing concepts")
    checklist.append("")
    checklist.append("-" * 80)
    checklist.append("WHAT TO LOOK FOR:")
    checklist.append("-" * 80)
    checklist.append("")
    checklist.append("✓ Common tags (high occurrence) missing from taxonomy")
    checklist.append("✓ Standard US-GAAP tags not mapped")
    checklist.append("✓ Industry-specific patterns (e.g., leases, derivatives, investments)")
    checklist.append("✓ Modern accounting standards (ASC 842 leases, ASC 606 revenue)")
    checklist.append("✓ Tags that should map to existing fields but with different names")
    checklist.append("")
    checklist.append("-" * 80)
    checklist.append("QUICK STATISTICS:")
    checklist.append("-" * 80)
    for key, value in summary.items():
        checklist.append(f"  {key.replace('_', ' ').title()}: {value:,}")
    checklist.append("")
    checklist.append("-" * 80)
    checklist.append("NEXT STEPS AFTER REVIEW:")
    checklist.append("-" * 80)
    checklist.append("1. Compile list of missing concepts")
    checklist.append("2. Categorize by priority (critical, important, nice-to-have)")
    checklist.append("3. Group by statement type (IS, BS, CF)")
    checklist.append("4. Share findings for AI taxonomy expansion")
    checklist.append("5. Re-run mapping with expanded taxonomy")
    checklist.append("")

    with open(output_dir / 'MANUAL_CHECKLIST.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(checklist))

    print(f"✅ Checklist created: {output_dir / 'MANUAL_CHECKLIST.txt'}")

    print("\n" + "=" * 80)
    print("READY FOR MANUAL REVIEW (WITH AUTO-MATCHING)!")
    print("=" * 80)
    print(f"\nFiles created in: {output_dir}")
    print("  1. MANUAL_TAXONOMY_COMPARISON.xlsx  ← START HERE (now with auto-matching!)")
    print("  2. comparison_summary.csv")
    print("  3. MANUAL_CHECKLIST.txt")
    print("\n✨ NEW: Auto-matching enabled using CamelCase ↔ snake_case conversion")
    print("Many tags are already matched - focus on verifying and finding gaps!")
    print("\nOpen the Excel file and review the 'auto_match' column.")


def main():
    """Main execution"""

    profiles_dir = Path('data/sec_data/extracted/2024q3/company_tag_profiles')
    output_dir = profiles_dir / 'manual_comparison'

    if not profiles_dir.exists():
        print(f"Error: Profiles directory not found: {profiles_dir}")
        print("Run company_tag_extractor.py first to generate profiles.")
        return

    generate_comparison_report(profiles_dir, output_dir)


if __name__ == "__main__":
    main()
