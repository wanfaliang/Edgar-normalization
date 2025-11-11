"""
Analyze Russell 3000 Sample Tags
=================================
Analyzes most common tags across Russell 3000 sample to identify
taxonomy gaps and needed variations.

Usage:
    python tools/analyze_russell_tags.py

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

    # Filter to only Russell sample companies (exclude previous BDC extractions)
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


def analyze_tag_frequency(profiles: List[Dict]) -> pd.DataFrame:
    """Analyze tag frequency across all companies"""

    tag_stats = {}

    for profile in profiles:
        for tag_detail in profile['tag_details']:
            tag = tag_detail['tag']

            if tag not in tag_stats:
                tag_stats[tag] = {
                    'tag': tag,
                    'companies_using': 0,
                    'total_occurrences': 0,
                    'custom': tag_detail['custom'],
                    'tlabel': tag_detail['tlabel'],
                    'datatype': tag_detail['datatype'],
                    'example_companies': []
                }

            tag_stats[tag]['companies_using'] += 1
            tag_stats[tag]['total_occurrences'] += tag_detail['occurrence_count']

            if len(tag_stats[tag]['example_companies']) < 3:
                tag_stats[tag]['example_companies'].append(profile['company_name'])

    df = pd.DataFrame(tag_stats.values())
    df['usage_pct'] = (df['companies_using'] / len(profiles) * 100).round(1)
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


def compare_with_taxonomy(tag_df: pd.DataFrame, taxonomy: Dict) -> pd.DataFrame:
    """Compare extracted tags with Finexus taxonomy"""

    tag_df['in_taxonomy'] = tag_df['tag'].apply(lambda x: 'Yes' if x in taxonomy else 'No')
    tag_df['mapped_field'] = tag_df['tag'].apply(lambda x: taxonomy.get(x, {}).get('field', ''))

    return tag_df


def generate_reports(profiles_dir: Path, output_dir: Path):
    """Generate comprehensive tag analysis reports"""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading Russell 3000 sample profiles...")
    profiles = load_all_profiles(profiles_dir)
    print(f"  ✅ Loaded {len(profiles)} company profiles")

    print("\nAnalyzing tag frequency...")
    tag_df = analyze_tag_frequency(profiles)
    print(f"  ✅ Analyzed {len(tag_df)} unique tags")

    print("\nLoading Finexus taxonomy...")
    taxonomy = load_finexus_taxonomy()
    print(f"  ✅ Loaded taxonomy with {len(taxonomy)} variations")

    print("\nComparing tags with taxonomy...")
    tag_df = compare_with_taxonomy(tag_df, taxonomy)

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

    # Save comprehensive report
    with pd.ExcelWriter(output_dir / 'RUSSELL_TAG_ANALYSIS.xlsx') as writer:

        # Sheet 1: Top 100 most common tags
        top_100 = tag_df.head(100)[['tag', 'companies_using', 'usage_pct', 'in_taxonomy',
                                     'mapped_field', 'custom', 'tlabel', 'example_companies']]
        top_100.to_excel(writer, sheet_name='Top 100 Tags', index=False)

        # Sheet 2: Standard tags NOT in taxonomy (high priority)
        standard_missing = tag_df[(~tag_df['custom']) & (tag_df['in_taxonomy'] == 'No')]
        standard_missing = standard_missing.sort_values('companies_using', ascending=False)
        standard_missing[['tag', 'companies_using', 'usage_pct', 'tlabel', 'datatype', 'example_companies']].to_excel(
            writer, sheet_name='Standard Tags Missing', index=False)

        # Sheet 3: Universal tags (used by 70%+ companies)
        universal = tag_df[tag_df['usage_pct'] >= 70].sort_values('usage_pct', ascending=False)
        universal[['tag', 'companies_using', 'usage_pct', 'in_taxonomy', 'mapped_field', 'custom', 'tlabel']].to_excel(
            writer, sheet_name='Universal Tags (70%+)', index=False)

        # Sheet 4: Standard tags IN taxonomy (verify correct)
        standard_matched = tag_df[(~tag_df['custom']) & (tag_df['in_taxonomy'] == 'Yes')]
        standard_matched = standard_matched.sort_values('companies_using', ascending=False)
        standard_matched[['tag', 'companies_using', 'usage_pct', 'mapped_field', 'tlabel']].to_excel(
            writer, sheet_name='Standard Tags Matched', index=False)

        # Sheet 5: Instructions
        instructions = pd.DataFrame([
            {'Step': 1, 'Action': 'Review "Top 100 Tags" - most commonly used across 50 companies'},
            {'Step': 2, 'Action': 'Check "Standard Tags Missing" - these should likely be in taxonomy'},
            {'Step': 3, 'Action': 'Prioritize by "usage_pct" - tags used by many companies are more important'},
            {'Step': 4, 'Action': 'Review "Universal Tags (70%+)" - these are critical for all companies'},
            {'Step': 5, 'Action': 'Verify "Standard Tags Matched" - check if mappings look correct'},
            {'Step': 6, 'Action': 'Look for patterns: variations of same concept (e.g., Revenue vs Revenues)'},
            {'Step': 7, 'Action': 'Add missing variations to taxonomy or note if new field needed'},
            {'Step': 8, 'Action': 'Custom tags can be ignored - they are company-specific'},
        ])
        instructions.to_excel(writer, sheet_name='INSTRUCTIONS', index=False)

    print(f"\n✅ Saved Excel report: {output_dir / 'RUSSELL_TAG_ANALYSIS.xlsx'}")

    # Save CSV for easy filtering
    tag_df.to_csv(output_dir / 'all_tags_with_taxonomy.csv', index=False)
    print(f"✅ Saved CSV: {output_dir / 'all_tags_with_taxonomy.csv'}")

    # Generate text summary
    summary = []
    summary.append("=" * 80)
    summary.append("RUSSELL 3000 TAG ANALYSIS SUMMARY")
    summary.append("=" * 80)
    summary.append("")
    summary.append(f"Companies analyzed: {len(profiles)}")
    summary.append(f"Total unique tags: {total_tags}")
    summary.append(f"  - Standard tags: {len(standard_tags)}")
    summary.append(f"  - Custom tags: {(tag_df['custom']).sum()}")
    summary.append("")
    summary.append(f"Taxonomy coverage:")
    summary.append(f"  - Tags in taxonomy: {in_taxonomy} ({in_taxonomy/total_tags*100:.1f}%)")
    summary.append(f"  - Tags NOT in taxonomy: {not_in_taxonomy} ({not_in_taxonomy/total_tags*100:.1f}%)")
    summary.append("")
    summary.append(f"Standard tag coverage (most important):")
    summary.append(f"  - In taxonomy: {standard_in_tax} ({standard_in_tax/len(standard_tags)*100:.1f}%)")
    summary.append(f"  - NOT in taxonomy: {standard_not_in_tax} ({standard_not_in_tax/len(standard_tags)*100:.1f}%)")
    summary.append("")
    summary.append("-" * 80)
    summary.append("TOP 20 MOST COMMON TAGS (ALL COMPANIES)")
    summary.append("-" * 80)
    for idx, row in tag_df.head(20).iterrows():
        in_tax = "✅" if row['in_taxonomy'] == 'Yes' else "❌"
        custom = "[CUSTOM]" if row['custom'] else "[STD]"
        summary.append(f"{in_tax} {row['tag']:50} {row['companies_using']:2d}/{len(profiles)} ({row['usage_pct']:5.1f}%) {custom}")
    summary.append("")
    summary.append("-" * 80)
    summary.append("TOP 20 STANDARD TAGS NOT IN TAXONOMY (GAPS)")
    summary.append("-" * 80)
    missing_top = standard_missing.head(20)
    for idx, row in missing_top.iterrows():
        summary.append(f"❌ {row['tag']:50} {row['companies_using']:2d}/{len(profiles)} ({row['usage_pct']:5.1f}%)")
        summary.append(f"   Label: {row['tlabel'][:70]}")
    summary.append("")

    with open(output_dir / 'TAG_ANALYSIS_SUMMARY.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(summary))

    print(f"✅ Saved summary: {output_dir / 'TAG_ANALYSIS_SUMMARY.txt'}")

    # Print to console
    print("\n" + "\n".join(summary))


def main():
    """Main execution"""

    profiles_dir = Path('data/sec_data/extracted/2024q3/company_tag_profiles')
    output_dir = Path('data/russell_3000_matched/tag_analysis')

    if not profiles_dir.exists():
        print(f"Error: Profiles directory not found: {profiles_dir}")
        return

    generate_reports(profiles_dir, output_dir)

    print("\n" + "=" * 80)
    print("READY FOR MANUAL REVIEW")
    print("=" * 80)
    print(f"\nOpen: {output_dir / 'RUSSELL_TAG_ANALYSIS.xlsx'}")
    print("\nFocus on:")
    print("  1. 'Standard Tags Missing' sheet - high priority gaps")
    print("  2. 'Universal Tags (70%+)' sheet - must-have coverage")
    print("  3. Check if variations should be added (e.g., Revenues vs Revenue)")


if __name__ == "__main__":
    main()
