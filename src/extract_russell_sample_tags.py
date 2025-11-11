"""
Extract Tags for Russell 3000 Sample Companies
==============================================
Extracts tag sets for the 50 stratified Russell 3000 sample companies.

Usage:
    python src/extract_russell_sample_tags.py

Author: Faliang & Claude
Date: November 2025
"""

import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent))

from company_tag_extractor import CompanyTagExtractor
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    """Extract tags for Russell 3000 sample companies"""

    # Load CIK list
    cik_file = Path('data/russell_3000_matched/sample_ciks.txt')

    if not cik_file.exists():
        logger.error(f"CIK list not found: {cik_file}")
        logger.error("Run russell_3000_matcher.py first to generate the sample.")
        return

    logger.info(f"Loading CIK list from {cik_file}")
    with open(cik_file, 'r') as f:
        ciks = [line.strip() for line in f if line.strip()]

    logger.info(f"Found {len(ciks)} CIKs to process")

    # Initialize extractor
    extractor = CompanyTagExtractor(year=2024, quarter=3)

    # Load data once
    logger.info("Loading 2024Q3 data (this may take a minute)...")
    extractor.load_data()

    # Extract tags for each company
    logger.info(f"\nExtracting tags for {len(ciks)} companies...")
    logger.info("=" * 80)

    successful = 0
    failed = 0

    for i, cik in enumerate(ciks, 1):
        logger.info(f"\n[{i}/{len(ciks)}] Processing CIK: {cik}")

        try:
            # Convert CIK to int for matching (data has no leading zeros)
            cik_int = int(cik)

            # Extract tag profile
            profile = extractor.extract_company_tag_set(cik_int)

            if profile:
                # Save profile
                extractor._save_company_profile(profile)
                successful += 1
                logger.info(f"  ✅ Success: {profile['company_name']} - {profile['total_unique_tags']} tags")
            else:
                failed += 1
                logger.warning(f"  ⚠️  No data found for CIK {cik}")

        except Exception as e:
            failed += 1
            logger.error(f"  ❌ Error processing CIK {cik}: {e}")

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("EXTRACTION COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Total companies: {len(ciks)}")
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Success rate: {successful/len(ciks)*100:.1f}%")
    logger.info(f"\nProfiles saved to: {extractor.output_dir}")

    # Generate summary statistics
    generate_summary_stats(extractor.output_dir)


def generate_summary_stats(output_dir: Path):
    """Generate summary statistics for extracted profiles"""
    import json
    import pandas as pd

    logger.info("\nGenerating summary statistics...")

    profile_files = list(output_dir.glob('company_*_tags.json'))

    if not profile_files:
        logger.warning("No profiles found")
        return

    stats = []

    for file in profile_files:
        with open(file, 'r', encoding='utf-8') as f:
            profile = json.load(f)

        stats.append({
            'cik': profile['cik'],
            'company_name': profile['company_name'],
            'industry': profile['industry'],
            'total_tags': profile['total_unique_tags'],
            'standard_tags': profile['standard_tags_count'],
            'custom_tags': profile['custom_tags_count'],
            'custom_pct': profile['custom_tags_count'] / profile['total_unique_tags'] * 100 if profile['total_unique_tags'] > 0 else 0
        })

    stats_df = pd.DataFrame(stats)

    # Save summary
    summary_file = output_dir / 'russell_sample_summary.csv'
    stats_df.to_csv(summary_file, index=False)
    logger.info(f"✅ Summary saved: {summary_file}")

    # Print statistics
    logger.info("\n" + "-" * 80)
    logger.info("SUMMARY STATISTICS")
    logger.info("-" * 80)
    logger.info(f"Total companies profiled: {len(stats_df)}")
    logger.info(f"Avg tags per company: {stats_df['total_tags'].mean():.0f}")
    logger.info(f"Avg standard tags: {stats_df['standard_tags'].mean():.0f}")
    logger.info(f"Avg custom tags: {stats_df['custom_tags'].mean():.0f}")
    logger.info(f"Avg custom %: {stats_df['custom_pct'].mean():.1f}%")

    logger.info("\nTop 10 companies by tag count:")
    top10 = stats_df.nlargest(10, 'total_tags')[['company_name', 'total_tags', 'custom_pct']]
    for idx, row in top10.iterrows():
        logger.info(f"  {row['company_name']:40} {row['total_tags']:4.0f} tags ({row['custom_pct']:.1f}% custom)")


if __name__ == "__main__":
    main()
