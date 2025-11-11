"""
Generate Enhanced Manual Review File for Taxonomy Expansion
===========================================================
Creates comprehensive tag analysis with statement types and indicators
for manual review and variation list creation.

Usage:
    python tools/generate_manual_review_file.py

Author: Faliang & Claude
Date: November 2025
"""

import json
import pandas as pd
from pathlib import Path
from collections import Counter
from typing import Dict, List
import sys

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / 'src'))


def load_all_profiles(profiles_dir: Path) -> List[Dict]:
    """Load all Russell sample company profiles"""
    profiles = []
    profile_files = list(profiles_dir.glob('company_*_tags.json'))

    # Filter to only Russell sample companies
    russell_summary = profiles_dir / 'russell_sample_summary.csv'
    if russell_summary.exists():
        russell_df = pd.read_csv(russell_summary)
        russell_ciks = set(str(cik) for cik in russell_df['cik'])

        for file in profile_files:
            with open(file, 'r', encoding='utf-8') as f:
                profile = json.load(f)
                if str(profile['cik']) in russell_ciks:
                    profiles.append(profile)
    else:
        # Load all if no summary exists
        for file in profile_files:
            with open(file, 'r', encoding='utf-8') as f:
                profiles.append(json.load(f))

    return profiles


def classify_tag_nature(tag: str, tlabel: str, statement_type: str, crdr: str) -> str:
    """
    Classify the nature of the tag for easier review

    Returns:
        Category like 'Asset', 'Liability', 'Revenue', 'Expense', etc.
    """
    tag_lower = tag.lower()
    tlabel_lower = tlabel.lower() if tlabel else ""

    # Balance Sheet items
    if statement_type == 'balance_sheet':
        # Assets
        if any(kw in tag_lower for kw in ['asset', 'cash', 'receivable', 'inventory',
                                            'property', 'equipment', 'investment', 'goodwill',
                                            'intangible', 'deferred']):
            return 'Asset'
        # Liabilities
        if any(kw in tag_lower for kw in ['liability', 'liabilities', 'payable', 'debt',
                                            'loan', 'obligation', 'accrued']):
            return 'Liability'
        # Equity
        if any(kw in tag_lower for kw in ['equity', 'stock', 'capital', 'retained',
                                            'surplus', 'shares']):
            return 'Equity'
        # Use crdr as fallback
        if crdr == 'D':
            return 'Asset'
        elif crdr == 'C':
            return 'Liability/Equity'
        return 'Balance Sheet Item'

    # Income Statement items
    elif statement_type == 'income_statement':
        # Revenue
        if any(kw in tag_lower for kw in ['revenue', 'sales', 'income', 'gain']):
            if not any(kw in tag_lower for kw in ['expense', 'cost', 'loss']):
                return 'Revenue'
        # Expenses
        if any(kw in tag_lower for kw in ['expense', 'cost', 'depreciation', 'amortization',
                                            'interest', 'tax', 'loss']):
            return 'Expense'
        # Net Income
        if any(kw in tag_lower for kw in ['netincome', 'earnings', 'profit']):
            return 'Net Income'
        # Use crdr as fallback
        if crdr == 'C':
            return 'Revenue'
        elif crdr == 'D':
            return 'Expense'
        return 'Income Statement Item'

    # Cash Flow items
    elif statement_type == 'cash_flow':
        if any(kw in tag_lower for kw in ['operating', 'operatingactivities']):
            return 'Operating Activity'
        if any(kw in tag_lower for kw in ['investing', 'investingactivities']):
            return 'Investing Activity'
        if any(kw in tag_lower for kw in ['financing', 'financingactivities']):
            return 'Financing Activity'
        return 'Cash Flow Item'

    # Equity statement
    elif statement_type == 'equity':
        return 'Equity Statement Item'

    return 'Unknown'


def get_presentation_labels_from_pre(pre_df: pd.DataFrame) -> Dict[str, Dict]:
    """
    Extract actual presentation labels from PRE table (optimized with groupby)

    Returns:
        Dict mapping tag -> {most_common_plabel, plabel_variations, plabel_count}
    """
    print("  Analyzing presentation labels from PRE table...")

    # Group by tag and plabel, count occurrences - much faster than looping
    plabel_counts = pre_df.groupby(['tag', 'plabel']).size().reset_index(name='count')

    # For each tag, get the most common plabel and variations
    tag_plabels = {}

    for tag in plabel_counts['tag'].unique():
        tag_data = plabel_counts[plabel_counts['tag'] == tag].sort_values('count', ascending=False)

        # Get most common plabel (first after sorting by count)
        most_common = ''
        if len(tag_data) > 0:
            first_plabel = tag_data.iloc[0]['plabel']
            if pd.notna(first_plabel) and first_plabel != '':
                most_common = first_plabel

        # Get top 3 variations
        variations = []
        for idx, row in tag_data.head(3).iterrows():
            plabel = row['plabel']
            count = row['count']
            if pd.notna(plabel) and plabel != '':
                variations.append(f'"{plabel}" ({count}x)')

        tag_plabels[tag] = {
            'most_common_plabel': most_common,
            'plabel_variations': ' | '.join(variations) if variations else '',
            'plabel_count': len(tag_data)
        }

    print(f"  ✅ Found presentation labels for {len(tag_plabels)} tags")
    return tag_plabels


def analyze_tag_frequency_with_metadata(profiles: List[Dict], pre_df: pd.DataFrame = None) -> pd.DataFrame:
    """Analyze tag frequency with all metadata for manual review"""

    tag_stats = {}

    for profile in profiles:
        for tag_detail in profile['tag_details']:
            tag = tag_detail['tag']

            if tag not in tag_stats:
                # First occurrence - capture metadata
                tag_stats[tag] = {
                    'tag': tag,
                    'companies_using': 0,
                    'total_occurrences': 0,
                    'custom': tag_detail['custom'],
                    'abstract': tag_detail.get('abstract', False),
                    'datatype': tag_detail.get('datatype', ''),
                    'iord': tag_detail.get('iord', ''),
                    'crdr': tag_detail.get('crdr', ''),
                    'statement_type': tag_detail.get('statement_type', 'unknown'),
                    'tlabel': tag_detail.get('tlabel', ''),
                    'doc': tag_detail.get('doc', ''),
                    'example_companies': []
                }

            tag_stats[tag]['companies_using'] += 1
            tag_stats[tag]['total_occurrences'] += tag_detail['occurrence_count']

            if len(tag_stats[tag]['example_companies']) < 3:
                tag_stats[tag]['example_companies'].append(profile['company_name'])

    df = pd.DataFrame(tag_stats.values())
    df['usage_pct'] = (df['companies_using'] / len(profiles) * 100).round(1)

    # Add presentation labels from PRE table
    if pre_df is not None:
        plabel_info = get_presentation_labels_from_pre(pre_df)
        df['most_common_plabel'] = df['tag'].apply(
            lambda x: plabel_info.get(x, {}).get('most_common_plabel', '')
        )
        df['plabel_variations'] = df['tag'].apply(
            lambda x: plabel_info.get(x, {}).get('plabel_variations', '')
        )
        df['plabel_count'] = df['tag'].apply(
            lambda x: plabel_info.get(x, {}).get('plabel_count', 0)
        )
    else:
        df['most_common_plabel'] = ''
        df['plabel_variations'] = ''
        df['plabel_count'] = 0

    # Add tag nature classification (use most_common_plabel if available, else tlabel)
    df['tag_nature'] = df.apply(
        lambda row: classify_tag_nature(row['tag'],
                                       row['most_common_plabel'] if row['most_common_plabel'] else row['tlabel'],
                                       row['statement_type'], row['crdr']),
        axis=1
    )

    # Format example companies
    df['example_companies'] = df['example_companies'].apply(lambda x: ', '.join(x))

    return df.sort_values('companies_using', ascending=False)


def load_finexus_taxonomy() -> Dict[str, str]:
    """Load Finexus taxonomy from taxonomy files"""
    taxonomy_file = Path('data/taxonomy/sec_to_finexus_mapping.json')

    if not taxonomy_file.exists():
        print(f"⚠️  Taxonomy file not found: {taxonomy_file}")
        return {}

    with open(taxonomy_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def generate_manual_review_file(profiles_dir: Path, output_dir: Path, top_n: int = 1000):
    """Generate comprehensive manual review file"""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading Russell 3000 sample profiles...")
    profiles = load_all_profiles(profiles_dir)
    print(f"  ✅ Loaded {len(profiles)} company profiles")

    print("\nLoading PRE table for presentation labels...")
    pre_file = Path('data/sec_data/extracted/2024q3/pre.txt')
    if pre_file.exists():
        pre_df = pd.read_csv(pre_file, sep='\t', low_memory=False)
        print(f"  ✅ Loaded PRE table with {len(pre_df):,} rows")
    else:
        print(f"  ⚠️  PRE table not found: {pre_file}")
        pre_df = None

    print("\nAnalyzing tag frequency with metadata...")
    tag_df = analyze_tag_frequency_with_metadata(profiles, pre_df)
    print(f"  ✅ Analyzed {len(tag_df)} unique tags")

    print("\nLoading Finexus taxonomy...")
    taxonomy = load_finexus_taxonomy()
    print(f"  ✅ Loaded taxonomy with {len(taxonomy)} variations")

    print("\nComparing tags with taxonomy...")
    tag_df['in_taxonomy'] = tag_df['tag'].apply(lambda x: 'Yes' if x in taxonomy else 'No')
    tag_df['mapped_field'] = tag_df['tag'].apply(lambda x: taxonomy.get(x, {}).get('field', ''))

    # Calculate statistics
    total_tags = len(tag_df)
    in_taxonomy = (tag_df['in_taxonomy'] == 'Yes').sum()
    not_in_taxonomy = total_tags - in_taxonomy

    standard_tags = tag_df[~tag_df['custom']]
    standard_in_tax = (standard_tags['in_taxonomy'] == 'Yes').sum()
    standard_not_in_tax = len(standard_tags) - standard_in_tax

    print(f"\n  Total unique tags: {total_tags}")
    print(f"  In taxonomy: {in_taxonomy} ({in_taxonomy/total_tags*100:.1f}%)")
    print(f"  Not in taxonomy: {not_in_taxonomy} ({not_in_taxonomy/total_tags*100:.1f}%)")
    print(f"\n  Standard tags: {len(standard_tags)}")
    print(f"  Standard in taxonomy: {standard_in_tax} ({standard_in_tax/len(standard_tags)*100:.1f}%)")
    print(f"  Standard NOT in taxonomy: {standard_not_in_tax} ({standard_not_in_tax/len(standard_tags)*100:.1f}%)")

    # Generate Excel file for manual review
    excel_file = output_dir / f'MANUAL_REVIEW_TOP_{top_n}_TAGS.xlsx'

    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:

        # Sheet 1: Top N tags - ALL metadata for review
        top_tags = tag_df.head(top_n).copy()

        # Reorder columns for easier review
        review_columns = [
            'tag',                      # SEC tag name
            'most_common_plabel',       # What companies call it (ACTUAL)
            'companies_using',          # How many companies use it
            'usage_pct',               # Percentage
            'in_taxonomy',             # Already mapped?
            'mapped_field',            # What it maps to
            'statement_type',          # BS, IS, CF, Equity
            'tag_nature',              # Asset, Liability, Revenue, etc.
            'iord',                    # I=Instant, D=Duration
            'crdr',                    # C=Credit, D=Debit
            'plabel_variations',       # Other ways companies label it
            'plabel_count',            # How many different labels used
            'custom',                  # Custom vs standard
            'abstract',                # Abstract element?
            'datatype',                # monetary, string, etc.
            'tlabel',                  # US-GAAP taxonomy label
            'example_companies',       # Which companies use it
            'total_occurrences',       # Total times used
            'doc'                      # Documentation
        ]

        top_tags[review_columns].to_excel(writer, sheet_name=f'Top {top_n} Tags', index=False)

        # Sheet 2: Standard tags NOT in taxonomy - prioritized for addition
        standard_missing = tag_df[(~tag_df['custom']) & (tag_df['in_taxonomy'] == 'No')].copy()
        standard_missing = standard_missing.sort_values('companies_using', ascending=False)
        standard_missing[review_columns].to_excel(
            writer, sheet_name='Standard Tags Missing', index=False
        )

        # Sheet 3: By Statement Type - Balance Sheet
        bs_tags = tag_df[tag_df['statement_type'] == 'balance_sheet'].head(500)
        bs_tags[review_columns].to_excel(writer, sheet_name='Balance Sheet Tags', index=False)

        # Sheet 4: By Statement Type - Income Statement
        is_tags = tag_df[tag_df['statement_type'] == 'income_statement'].head(500)
        is_tags[review_columns].to_excel(writer, sheet_name='Income Statement Tags', index=False)

        # Sheet 5: By Statement Type - Cash Flow
        cf_tags = tag_df[tag_df['statement_type'] == 'cash_flow'].head(500)
        cf_tags[review_columns].to_excel(writer, sheet_name='Cash Flow Tags', index=False)

        # Sheet 6: By Tag Nature - Assets
        asset_tags = tag_df[tag_df['tag_nature'] == 'Asset'].head(200)
        asset_tags[review_columns].to_excel(writer, sheet_name='Asset Tags', index=False)

        # Sheet 7: By Tag Nature - Liabilities
        liability_tags = tag_df[tag_df['tag_nature'] == 'Liability'].head(200)
        liability_tags[review_columns].to_excel(writer, sheet_name='Liability Tags', index=False)

        # Sheet 8: By Tag Nature - Revenue
        revenue_tags = tag_df[tag_df['tag_nature'] == 'Revenue'].head(200)
        revenue_tags[review_columns].to_excel(writer, sheet_name='Revenue Tags', index=False)

        # Sheet 9: By Tag Nature - Expense
        expense_tags = tag_df[tag_df['tag_nature'] == 'Expense'].head(200)
        expense_tags[review_columns].to_excel(writer, sheet_name='Expense Tags', index=False)

        # Sheet 10: Summary Statistics by Statement Type
        stmt_summary = tag_df.groupby('statement_type').agg({
            'tag': 'count',
            'companies_using': 'sum',
            'in_taxonomy': lambda x: (x == 'Yes').sum()
        }).reset_index()
        stmt_summary.columns = ['Statement Type', 'Total Tags', 'Total Usage', 'In Taxonomy']
        stmt_summary['Not in Taxonomy'] = stmt_summary['Total Tags'] - stmt_summary['In Taxonomy']
        stmt_summary.to_excel(writer, sheet_name='Summary by Statement', index=False)

        # Sheet 11: Summary Statistics by Tag Nature
        nature_summary = tag_df.groupby('tag_nature').agg({
            'tag': 'count',
            'companies_using': 'sum',
            'in_taxonomy': lambda x: (x == 'Yes').sum()
        }).reset_index()
        nature_summary.columns = ['Tag Nature', 'Total Tags', 'Total Usage', 'In Taxonomy']
        nature_summary['Not in Taxonomy'] = nature_summary['Total Tags'] - nature_summary['In Taxonomy']
        nature_summary = nature_summary.sort_values('Total Tags', ascending=False)
        nature_summary.to_excel(writer, sheet_name='Summary by Nature', index=False)

        # Sheet 12: Instructions
        instructions = pd.DataFrame([
            {'Step': 1, 'Action': 'Start with "Top 1000 Tags" sheet - sorted by usage frequency'},
            {'Step': 2, 'Action': 'MOST IMPORTANT: "most_common_plabel" shows what companies ACTUALLY call this on statements'},
            {'Step': 3, 'Action': 'Example: tag="Assets" but most_common_plabel="Total assets" (what you see in 10-K)'},
            {'Step': 4, 'Action': 'Focus on tags with high usage_pct (used by many companies)'},
            {'Step': 5, 'Action': 'Check "in_taxonomy" column - "No" means it needs review'},
            {'Step': 6, 'Action': 'Use "plabel_variations" to see other ways companies label the same tag'},
            {'Step': 7, 'Action': 'Use "statement_type" to understand where tag belongs (BS/IS/CF)'},
            {'Step': 8, 'Action': 'Use "tag_nature" for quick classification (Asset/Liability/Revenue/etc)'},
            {'Step': 9, 'Action': 'Use "iord" field: I=Balance Sheet item, D=Flow item'},
            {'Step': 10, 'Action': 'Use "crdr" field: C=Credit normal, D=Debit normal'},
            {'Step': 11, 'Action': 'Review "Standard Tags Missing" sheet - high priority additions'},
            {'Step': 12, 'Action': 'Use statement-specific sheets (BS/IS/CF) for focused review'},
            {'Step': 13, 'Action': 'Use nature-specific sheets (Asset/Liability/Revenue) for classification'},
            {'Step': 14, 'Action': 'Check "tlabel" (US-GAAP) and "doc" for technical definition'},
            {'Step': 15, 'Action': 'Add missing tags as variations to existing Finexus fields'},
            {'Step': 16, 'Action': 'Create new Finexus fields if tag represents new concept'},
            {'Step': 17, 'Action': 'Ignore "custom=True" tags unless widely used'},
        ])
        instructions.to_excel(writer, sheet_name='INSTRUCTIONS', index=False)

    print(f"\n✅ Saved Excel file: {excel_file}")

    # Also save full dataset as CSV for filtering
    csv_file = output_dir / 'all_tags_full_metadata.csv'
    tag_df.to_csv(csv_file, index=False)
    print(f"✅ Saved CSV: {csv_file}")

    # Generate summary text
    print("\n" + "=" * 80)
    print("MANUAL REVIEW FILE GENERATED")
    print("=" * 80)
    print(f"\nOpen: {excel_file}")
    print(f"\nFile contains:")
    print(f"  - Top {top_n} tags with full metadata")
    print(f"  - {len(standard_missing)} standard tags not in taxonomy")
    print(f"  - Statement-specific sheets (BS, IS, CF)")
    print(f"  - Nature-specific sheets (Asset, Liability, Revenue, Expense)")
    print(f"  - Summary statistics")
    print(f"  - Detailed instructions")

    print(f"\nKey columns for review:")
    print(f"  - most_common_plabel: What companies ACTUALLY call this tag (e.g., 'Total assets')")
    print(f"  - plabel_variations: Other ways companies label it")
    print(f"  - statement_type: Which financial statement")
    print(f"  - tag_nature: Asset/Liability/Revenue/Expense classification")
    print(f"  - iord: I=Instant (BS), D=Duration (IS/CF)")
    print(f"  - crdr: C=Credit normal, D=Debit normal")
    print(f"  - tlabel: US-GAAP taxonomy label (technical)")
    print(f"  - in_taxonomy: Already mapped?")


def main():
    """Main execution"""

    profiles_dir = Path('data/sec_data/extracted/2024q3/company_tag_profiles')
    output_dir = Path('data/russell_3000_matched/manual_review')

    if not profiles_dir.exists():
        print(f"Error: Profiles directory not found: {profiles_dir}")
        return

    # Generate top 1000 by default (can adjust if needed)
    generate_manual_review_file(profiles_dir, output_dir, top_n=1000)

    print("\n" + "=" * 80)
    print("READY FOR MANUAL REVIEW")
    print("=" * 80)


if __name__ == "__main__":
    main()
