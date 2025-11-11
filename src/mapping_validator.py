"""
Mapping Validator
=================
Validates AI-generated tag mappings for quality assurance.
Analyzes patterns, generates reports, and identifies issues.

Author: Faliang & Claude
Date: November 2025
"""

import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple
import logging
from collections import defaultdict
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MappingValidator:
    """
    Validates and analyzes AI-generated tag mappings
    """

    def __init__(self, mappings_dir: Path):
        """
        Initialize validator with directory containing mapping JSON files

        Args:
            mappings_dir: Directory with AI mapping JSON files
        """
        self.mappings_dir = Path(mappings_dir)
        self.mappings = []
        self.all_mappings_flat = []

        logger.info(f"Initialized MappingValidator with {mappings_dir}")

    def load_all_mappings(self) -> List[Dict]:
        """Load all mapping files"""
        mapping_files = list(self.mappings_dir.glob('mapping_*.json'))

        logger.info(f"Found {len(mapping_files)} mapping files")

        for file in mapping_files:
            with open(file, 'r', encoding='utf-8') as f:
                mapping = json.load(f)
                self.mappings.append(mapping)

                # Flatten for analysis
                for m in mapping['mappings']:
                    self.all_mappings_flat.append({
                        'cik': mapping['cik'],
                        'company_name': mapping['company_name'],
                        'tag': m['tag'],
                        'standard_concept': m['standard_concept'],
                        'confidence': m['confidence'],
                        'reasoning': m['reasoning']
                    })

        logger.info(f"Loaded {len(self.all_mappings_flat)} total mappings from {len(self.mappings)} companies")
        return self.mappings

    def categorize_by_confidence(self) -> Dict:
        """Categorize mappings by confidence level"""
        categories = {
            'perfect': [],      # 1.0
            'very_high': [],    # 0.9
            'high': [],         # 0.8
            'medium': [],       # 0.5-0.7
            'low': [],          # 0.1-0.4
            'custom': []        # 0.0 (unmappable)
        }

        for m in self.all_mappings_flat:
            conf = m['confidence']
            if conf == 1.0:
                categories['perfect'].append(m)
            elif conf >= 0.9:
                categories['very_high'].append(m)
            elif conf >= 0.8:
                categories['high'].append(m)
            elif conf >= 0.5:
                categories['medium'].append(m)
            elif conf > 0.0:
                categories['low'].append(m)
            else:
                categories['custom'].append(m)

        return categories

    def analyze_confidence_distribution(self) -> pd.DataFrame:
        """Analyze distribution of confidence scores"""
        df = pd.DataFrame(self.all_mappings_flat)

        # Group by company
        company_stats = df.groupby('company_name').agg({
            'confidence': ['count', 'mean', 'min', 'max'],
            'tag': 'count'
        }).round(3)

        # Overall stats
        overall_stats = {
            'total_mappings': len(df),
            'unique_tags': df['tag'].nunique(),
            'unique_concepts': df[df['confidence'] > 0]['standard_concept'].nunique(),
            'mean_confidence': df['confidence'].mean(),
            'median_confidence': df['confidence'].median(),
            'perfect_matches': len(df[df['confidence'] == 1.0]),
            'high_confidence': len(df[df['confidence'] >= 0.8]),
            'medium_confidence': len(df[(df['confidence'] >= 0.5) & (df['confidence'] < 0.8)]),
            'low_confidence': len(df[(df['confidence'] > 0.0) & (df['confidence'] < 0.5)]),
            'custom_tags': len(df[df['confidence'] == 0.0]),
        }

        return company_stats, overall_stats

    def find_duplicate_mappings(self) -> List[Dict]:
        """Find tags mapped to same concept across companies"""
        # Group by tag
        tag_mappings = defaultdict(list)

        for m in self.all_mappings_flat:
            if m['confidence'] > 0:  # Exclude custom
                tag_mappings[m['tag']].append(m)

        # Find tags that appear in multiple companies
        common_tags = []
        for tag, mappings in tag_mappings.items():
            if len(mappings) > 1:
                # Check if they map to the same concept
                concepts = [m['standard_concept'] for m in mappings]
                if len(set(concepts)) == 1:
                    # Consistent mapping across companies
                    common_tags.append({
                        'tag': tag,
                        'standard_concept': concepts[0],
                        'companies': len(mappings),
                        'avg_confidence': sum(m['confidence'] for m in mappings) / len(mappings),
                        'consistent': True
                    })
                else:
                    # Inconsistent mapping!
                    common_tags.append({
                        'tag': tag,
                        'standard_concept': 'INCONSISTENT',
                        'companies': len(mappings),
                        'concepts_used': concepts,
                        'consistent': False,
                        'WARNING': 'Same tag mapped differently across companies!'
                    })

        return common_tags

    def analyze_standard_concepts(self) -> pd.DataFrame:
        """Analyze which standard concepts are most used"""
        df = pd.DataFrame(self.all_mappings_flat)

        # Filter out custom tags
        df_mapped = df[df['confidence'] > 0]

        concept_usage = df_mapped.groupby('standard_concept').agg({
            'tag': ['count', lambda x: list(x.unique())],
            'confidence': ['mean', 'min', 'max'],
            'company_name': lambda x: list(x.unique())
        }).round(3)

        concept_usage.columns = ['count', 'tags', 'avg_confidence', 'min_confidence', 'max_confidence', 'companies']
        concept_usage = concept_usage.sort_values('count', ascending=False)

        return concept_usage

    def identify_review_candidates(self) -> Dict:
        """Identify mappings that need human review"""
        candidates = {
            'medium_confidence': [],      # 0.5-0.79 - need review
            'inconsistent_across_companies': [],  # Same tag, different concepts
            'unusual_patterns': [],       # Unexpected mappings
            'high_priority_review': []   # Most important to validate
        }

        # Medium confidence - manual review needed
        for m in self.all_mappings_flat:
            if 0.5 <= m['confidence'] < 0.8:
                candidates['medium_confidence'].append(m)

        # Find inconsistent mappings
        common_tags = self.find_duplicate_mappings()
        for tag_info in common_tags:
            if not tag_info.get('consistent', True):
                candidates['inconsistent_across_companies'].append(tag_info)

        # High priority: frequently used tags with medium confidence
        df = pd.DataFrame(self.all_mappings_flat)
        df_medium = df[(df['confidence'] >= 0.5) & (df['confidence'] < 0.8)]

        # Tags that appear in multiple companies but have medium confidence
        for tag in df_medium['tag'].unique():
            tag_data = df_medium[df_medium['tag'] == tag]
            if len(tag_data) >= 2:  # Appears in 2+ companies
                candidates['high_priority_review'].append({
                    'tag': tag,
                    'companies': len(tag_data),
                    'avg_confidence': tag_data['confidence'].mean(),
                    'concepts': tag_data['standard_concept'].unique().tolist(),
                    'reason': 'Frequently used but medium confidence'
                })

        return candidates

    def generate_validation_report(self, output_dir: Path):
        """Generate comprehensive validation report"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Generating validation report...")

        # 1. Confidence distribution
        company_stats, overall_stats = self.analyze_confidence_distribution()

        # 2. Categorize by confidence
        categories = self.categorize_by_confidence()

        # 3. Standard concept usage
        concept_usage = self.analyze_standard_concepts()

        # 4. Review candidates
        review_candidates = self.identify_review_candidates()

        # 5. Cross-company consistency
        common_tags = self.find_duplicate_mappings()

        # Save overall statistics
        with open(output_dir / 'validation_summary.json', 'w') as f:
            json.dump({
                'generated_at': datetime.now().isoformat(),
                'overall_stats': overall_stats,
                'categories': {k: len(v) for k, v in categories.items()},
                'review_needed': len(review_candidates['medium_confidence']),
                'high_priority_review': len(review_candidates['high_priority_review']),
                'inconsistent_mappings': len(review_candidates['inconsistent_across_companies'])
            }, f, indent=2)

        # Save detailed breakdowns

        # Perfect matches
        pd.DataFrame(categories['perfect']).to_csv(
            output_dir / '1_perfect_matches.csv', index=False
        )

        # Very high confidence
        pd.DataFrame(categories['very_high']).to_csv(
            output_dir / '2_very_high_confidence.csv', index=False
        )

        # High confidence
        pd.DataFrame(categories['high']).to_csv(
            output_dir / '3_high_confidence.csv', index=False
        )

        # Medium confidence (NEEDS REVIEW)
        pd.DataFrame(categories['medium']).to_csv(
            output_dir / '4_REVIEW_medium_confidence.csv', index=False
        )

        # Custom tags
        pd.DataFrame(categories['custom']).to_csv(
            output_dir / '5_custom_tags.csv', index=False
        )

        # Standard concept usage
        concept_usage.to_csv(output_dir / 'concept_usage_analysis.csv')

        # Review candidates
        pd.DataFrame(review_candidates['high_priority_review']).to_csv(
            output_dir / 'REVIEW_high_priority.csv', index=False
        )

        # Cross-company consistency
        pd.DataFrame(common_tags).to_csv(
            output_dir / 'cross_company_consistency.csv', index=False
        )

        # Create human-friendly validation checklist
        self._create_validation_checklist(categories, output_dir)

        logger.info(f"Validation report saved to {output_dir}")

        return {
            'overall_stats': overall_stats,
            'categories': categories,
            'review_candidates': review_candidates,
            'concept_usage': concept_usage,
            'common_tags': common_tags
        }

    def _create_validation_checklist(self, categories: Dict, output_dir: Path):
        """Create human-friendly validation checklist"""

        checklist = []

        # Section 1: Perfect matches (should be obvious)
        checklist.append("# VALIDATION CHECKLIST")
        checklist.append("=" * 80)
        checklist.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        checklist.append("")

        checklist.append("## SECTION 1: Perfect Matches (Confidence = 1.0)")
        checklist.append(f"Total: {len(categories['perfect'])}")
        checklist.append("These should be obvious semantic matches. Quick review to confirm.")
        checklist.append("")

        for i, m in enumerate(categories['perfect'][:10], 1):
            checklist.append(f"{i}. [{m['company_name']}]")
            checklist.append(f"   Tag: {m['tag']}")
            checklist.append(f"   → Concept: {m['standard_concept']}")
            checklist.append(f"   Reasoning: {m['reasoning'][:100]}...")
            checklist.append(f"   ☐ VALIDATED  ☐ NEEDS CORRECTION")
            checklist.append("")

        if len(categories['perfect']) > 10:
            checklist.append(f"   ... and {len(categories['perfect']) - 10} more (see 1_perfect_matches.csv)")
            checklist.append("")

        # Section 2: High confidence (0.8-0.9)
        high_conf = categories['very_high'] + categories['high']
        checklist.append("## SECTION 2: High Confidence (0.8-0.9)")
        checklist.append(f"Total: {len(high_conf)}")
        checklist.append("These are very good matches. Spot check for accuracy.")
        checklist.append("")

        for i, m in enumerate(high_conf[:10], 1):
            checklist.append(f"{i}. [{m['company_name']}] (Confidence: {m['confidence']})")
            checklist.append(f"   Tag: {m['tag']}")
            checklist.append(f"   → Concept: {m['standard_concept']}")
            checklist.append(f"   Reasoning: {m['reasoning'][:100]}...")
            checklist.append(f"   ☐ VALIDATED  ☐ NEEDS CORRECTION")
            checklist.append("")

        if len(high_conf) > 10:
            checklist.append(f"   ... and {len(high_conf) - 10} more (see CSV files)")
            checklist.append("")

        # Section 3: NEEDS REVIEW (medium confidence)
        checklist.append("## SECTION 3: NEEDS HUMAN REVIEW (0.5-0.79)")
        checklist.append(f"Total: {len(categories['medium'])}")
        checklist.append("⚠️  These require careful review and decision.")
        checklist.append("")

        for i, m in enumerate(categories['medium'][:20], 1):
            checklist.append(f"{i}. [{m['company_name']}] (Confidence: {m['confidence']})")
            checklist.append(f"   Tag: {m['tag']}")
            checklist.append(f"   → Concept: {m['standard_concept']}")
            checklist.append(f"   Reasoning: {m['reasoning']}")
            checklist.append(f"   DECISION: ☐ APPROVE  ☐ REJECT  ☐ MODIFY TO: ___________")
            checklist.append("")

        # Section 4: Custom tags (just verify they should be custom)
        checklist.append("## SECTION 4: Custom/Unmappable Tags (Confidence = 0.0)")
        checklist.append(f"Total: {len(categories['custom'])}")
        checklist.append("Verify these truly cannot be mapped to standard concepts.")
        checklist.append("")

        for i, m in enumerate(categories['custom'][:10], 1):
            checklist.append(f"{i}. [{m['company_name']}]")
            checklist.append(f"   Tag: {m['tag']}")
            checklist.append(f"   Reasoning: {m['reasoning'][:150]}...")
            checklist.append(f"   ☐ CORRECT (truly custom)  ☐ SHOULD MAP TO: ___________")
            checklist.append("")

        checklist.append("=" * 80)
        checklist.append("## SUMMARY")
        checklist.append(f"- Perfect matches: {len(categories['perfect'])}")
        checklist.append(f"- High confidence: {len(high_conf)}")
        checklist.append(f"- NEEDS REVIEW: {len(categories['medium'])}")
        checklist.append(f"- Custom tags: {len(categories['custom'])}")
        checklist.append("")
        checklist.append("Next steps:")
        checklist.append("1. Review SECTION 3 (medium confidence) carefully")
        checklist.append("2. Spot check SECTION 1-2 (high confidence)")
        checklist.append("3. Verify SECTION 4 (custom tags)")
        checklist.append("4. Document any corrections needed")
        checklist.append("5. Update standard concepts taxonomy based on findings")

        # Save checklist
        with open(output_dir / 'VALIDATION_CHECKLIST.txt', 'w', encoding='utf-8') as f:
            f.write('\n'.join(checklist))

        logger.info("Validation checklist created")

    def print_summary(self):
        """Print summary to console"""
        _, overall_stats = self.analyze_confidence_distribution()
        categories = self.categorize_by_confidence()

        print("\n" + "=" * 80)
        print("MAPPING VALIDATION SUMMARY")
        print("=" * 80)
        print(f"Total mappings analyzed: {overall_stats['total_mappings']}")
        print(f"Companies: {len(self.mappings)}")
        print(f"Unique tags: {overall_stats['unique_tags']}")
        print(f"Unique standard concepts: {overall_stats['unique_concepts']}")
        print("")
        print("CONFIDENCE DISTRIBUTION:")
        print(f"  Perfect (1.0):          {len(categories['perfect']):3d} ({len(categories['perfect'])/overall_stats['total_mappings']*100:5.1f}%)")
        print(f"  Very High (0.9):        {len(categories['very_high']):3d} ({len(categories['very_high'])/overall_stats['total_mappings']*100:5.1f}%)")
        print(f"  High (0.8):             {len(categories['high']):3d} ({len(categories['high'])/overall_stats['total_mappings']*100:5.1f}%)")
        print(f"  Medium (0.5-0.79):      {len(categories['medium']):3d} ({len(categories['medium'])/overall_stats['total_mappings']*100:5.1f}%) ⚠️  NEEDS REVIEW")
        print(f"  Low (0.01-0.49):        {len(categories['low']):3d} ({len(categories['low'])/overall_stats['total_mappings']*100:5.1f}%)")
        print(f"  Custom (0.0):           {len(categories['custom']):3d} ({len(categories['custom'])/overall_stats['total_mappings']*100:5.1f}%)")
        print("")
        print("QUALITY METRICS:")
        print(f"  Mappable (>0):          {overall_stats['total_mappings'] - overall_stats['custom_tags']} ({(overall_stats['total_mappings'] - overall_stats['custom_tags'])/overall_stats['total_mappings']*100:.1f}%)")
        print(f"  High confidence (≥0.8): {overall_stats['high_confidence']} ({overall_stats['high_confidence']/overall_stats['total_mappings']*100:.1f}%)")
        print(f"  Avg confidence:         {overall_stats['mean_confidence']:.3f}")
        print("=" * 80)


def main():
    """Run validation on AI mappings"""
    import sys

    # Get mappings directory
    if len(sys.argv) > 1:
        mappings_dir = Path(sys.argv[1])
    else:
        mappings_dir = Path('data/sec_data/extracted/2024q3/company_tag_profiles/ai_mappings')

    if not mappings_dir.exists():
        logger.error(f"Mappings directory not found: {mappings_dir}")
        return

    # Create validator
    validator = MappingValidator(mappings_dir)

    # Load all mappings
    validator.load_all_mappings()

    # Print summary
    validator.print_summary()

    # Generate detailed validation report
    output_dir = mappings_dir / 'validation_report'
    results = validator.generate_validation_report(output_dir)

    print(f"\n✅ Validation report generated: {output_dir}")
    print("\nKey files to review:")
    print("  1. VALIDATION_CHECKLIST.txt - Start here!")
    print("  2. 4_REVIEW_medium_confidence.csv - Needs your decision")
    print("  3. REVIEW_high_priority.csv - Most important to validate")
    print("  4. validation_summary.json - Overall statistics")


if __name__ == "__main__":
    main()
