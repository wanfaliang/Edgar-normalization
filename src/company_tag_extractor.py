"""
Company Tag Extractor
====================
Extracts unique tag sets used by each company across SEC filings.
Creates structured profiles for AI-powered tag mapping.

Author: Faliang & Claude
Date: November 2025
"""

import pandas as pd
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set
import logging
from collections import defaultdict
from config import StorageConfig

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CompanyTagExtractor:
    """
    Extracts and analyzes tag usage patterns for individual companies
    """

    def __init__(self, year: int = 2024, quarter: int = 3):
        self.year = year
        self.quarter = quarter

        # Use StorageConfig
        storage = StorageConfig()
        self.base_dir = storage.extracted_dir / f'{year}q{quarter}'
        self.output_dir = self.base_dir / 'company_tag_profiles'
        self.output_dir.mkdir(exist_ok=True)

        logger.info(f"Initialized CompanyTagExtractor for {year}Q{quarter}")
        logger.info(f"Output directory: {self.output_dir}")

    def load_data(self):
        """Load NUM, SUB, and TAG tables"""
        logger.info("Loading data files...")

        # Load NUM table
        num_file = self.base_dir / 'num.txt'
        logger.info(f"Loading NUM table from {num_file}...")
        self.num_df = pd.read_csv(num_file, sep='\t', low_memory=False)
        logger.info(f"NUM table loaded: {len(self.num_df):,} rows")

        # Load SUB table
        sub_file = self.base_dir / 'sub.txt'
        logger.info(f"Loading SUB table from {sub_file}...")
        self.sub_df = pd.read_csv(sub_file, sep='\t', low_memory=False)
        logger.info(f"SUB table loaded: {len(self.sub_df):,} rows")

        # Load TAG table
        tag_file = self.base_dir / 'tag.txt'
        logger.info(f"Loading TAG table from {tag_file}...")
        self.tag_df = pd.read_csv(tag_file, sep='\t', low_memory=False)
        logger.info(f"TAG table loaded: {len(self.tag_df):,} rows")

        # Merge NUM with SUB to get company info
        logger.info("Merging NUM with SUB...")
        self.merged_df = pd.merge(
            self.num_df,
            self.sub_df[['adsh', 'cik', 'name', 'sic', 'form', 'fy', 'fp']],
            on='adsh',
            how='left'
        )
        logger.info(f"Merged data: {len(self.merged_df):,} rows")

    def extract_company_tag_set(self, cik: str) -> Dict:
        """
        Extract all unique tags used by a specific company

        Args:
            cik: Central Index Key of the company

        Returns:
            Dictionary with company info and tag details
        """
        # Get company data
        company_data = self.merged_df[self.merged_df['cik'] == cik]

        if company_data.empty:
            logger.warning(f"No data found for CIK {cik}")
            return None

        # Get company metadata
        company_name = company_data['name'].iloc[0]
        sic = company_data['sic'].iloc[0] if 'sic' in company_data.columns else None

        # Extract unique tags
        unique_tags = company_data['tag'].unique()
        unique_versions = company_data['version'].unique()

        logger.info(f"Company {company_name} (CIK: {cik}): {len(unique_tags)} unique tags")

        # Get tag metadata from TAG table
        tag_details = []
        for tag in unique_tags:
            # Find tag in TAG table (match on tag name, may have multiple versions)
            tag_info = self.tag_df[self.tag_df['tag'] == tag]

            if not tag_info.empty:
                # Take the first version (usually most recent)
                tag_record = tag_info.iloc[0]

                tag_details.append({
                    'tag': tag,
                    'version': tag_record.get('version', 'unknown'),
                    'custom': bool(tag_record.get('custom', 0)),
                    'abstract': bool(tag_record.get('abstract', 0)),
                    'datatype': tag_record.get('datatype', ''),
                    'iord': tag_record.get('iord', ''),  # I=Instant, D=Duration
                    'crdr': tag_record.get('crdr', ''),  # C=Credit, D=Debit
                    'tlabel': tag_record.get('tlabel', ''),
                    'doc': tag_record.get('doc', '')[:500] if pd.notna(tag_record.get('doc')) else '',  # Truncate doc
                })
            else:
                # Tag not found in TAG table (might be very custom)
                tag_details.append({
                    'tag': tag,
                    'version': 'unknown',
                    'custom': True,
                    'abstract': False,
                    'datatype': 'unknown',
                    'iord': '',
                    'crdr': '',
                    'tlabel': '',
                    'doc': ''
                })

        # Get usage statistics
        tag_usage = company_data.groupby('tag').agg({
            'value': 'count',
            'uom': lambda x: x.mode()[0] if len(x.mode()) > 0 else None,  # Most common unit
        }).reset_index()
        tag_usage.columns = ['tag', 'occurrence_count', 'common_unit']

        # Merge tag details with usage stats
        for tag_detail in tag_details:
            usage = tag_usage[tag_usage['tag'] == tag_detail['tag']]
            if not usage.empty:
                tag_detail['occurrence_count'] = int(usage['occurrence_count'].iloc[0])
                tag_detail['common_unit'] = usage['common_unit'].iloc[0]
            else:
                tag_detail['occurrence_count'] = 0
                tag_detail['common_unit'] = None

        # Sort by occurrence count (most used first)
        tag_details.sort(key=lambda x: x['occurrence_count'], reverse=True)

        # Categorize tags
        standard_tags = [t for t in tag_details if not t['custom']]
        custom_tags = [t for t in tag_details if t['custom']]

        # Build company profile
        profile = {
            'cik': cik,
            'company_name': company_name,
            'sic': str(sic) if pd.notna(sic) else None,
            'industry': self._get_industry_name(sic),
            'total_records': len(company_data),
            'total_unique_tags': len(unique_tags),
            'standard_tags_count': len(standard_tags),
            'custom_tags_count': len(custom_tags),
            'versions_used': list(unique_versions),
            'filings': company_data['adsh'].nunique(),
            'forms': company_data['form'].unique().tolist() if 'form' in company_data.columns else [],
            'tag_details': tag_details,
            'standard_tags': [t['tag'] for t in standard_tags],
            'custom_tags': [t['tag'] for t in custom_tags],
            'extracted_date': datetime.now().isoformat(),
            'data_period': f"{self.year}Q{self.quarter}"
        }

        return profile

    def _get_industry_name(self, sic) -> str:
        """Convert SIC code to industry name (simplified)"""
        if pd.isna(sic):
            return "Unknown"

        sic = int(float(sic))

        # Simplified SIC mapping
        if 6000 <= sic < 7000:
            return "Finance, Insurance & Real Estate"
        elif 2000 <= sic < 4000:
            return "Manufacturing"
        elif 5000 <= sic < 6000:
            return "Wholesale & Retail Trade"
        elif 7000 <= sic < 9000:
            return "Services"
        elif 4000 <= sic < 5000:
            return "Transportation & Utilities"
        else:
            return "Other"

    def extract_top_companies(self, n: int = 10) -> List[Dict]:
        """
        Extract tag profiles for top N companies by data volume

        Args:
            n: Number of top companies to extract

        Returns:
            List of company tag profiles
        """
        logger.info(f"Extracting tag profiles for top {n} companies...")

        # Get companies by record count
        company_counts = self.merged_df.groupby(['cik', 'name']).size().reset_index(name='record_count')
        company_counts = company_counts.sort_values('record_count', ascending=False)

        top_companies = company_counts.head(n)

        profiles = []
        for idx, row in top_companies.iterrows():
            cik = row['cik']
            logger.info(f"Processing {idx+1}/{n}: {row['name']} (CIK: {cik})")

            profile = self.extract_company_tag_set(cik)
            if profile:
                profiles.append(profile)

                # Save individual company profile
                self._save_company_profile(profile)

        return profiles

    def _save_company_profile(self, profile: Dict):
        """Save individual company profile to JSON file"""
        cik = profile['cik']
        company_name = profile['company_name'].replace('/', '_').replace('\\', '_')[:50]

        filename = f"company_{cik}_{company_name}_tags.json"
        filepath = self.output_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved profile to {filepath}")

    def create_summary_report(self, profiles: List[Dict]):
        """Create summary report of all extracted profiles"""
        summary = {
            'extraction_date': datetime.now().isoformat(),
            'data_period': f"{self.year}Q{self.quarter}",
            'total_companies': len(profiles),
            'companies': []
        }

        for profile in profiles:
            summary['companies'].append({
                'cik': profile['cik'],
                'name': profile['company_name'],
                'sic': profile['sic'],
                'industry': profile['industry'],
                'total_tags': profile['total_unique_tags'],
                'standard_tags': profile['standard_tags_count'],
                'custom_tags': profile['custom_tags_count'],
                'total_records': profile['total_records'],
                'forms': profile['forms']
            })

        # Save summary
        summary_file = self.output_dir / 'extraction_summary.json'
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved summary report to {summary_file}")

        # Create CSV for easy viewing
        summary_df = pd.DataFrame(summary['companies'])
        summary_csv = self.output_dir / 'extraction_summary.csv'
        summary_df.to_csv(summary_csv, index=False)
        logger.info(f"Saved summary CSV to {summary_csv}")

        return summary

    def analyze_tag_overlap(self, profiles: List[Dict]):
        """Analyze tag overlap across companies"""
        logger.info("Analyzing tag overlap across companies...")

        # Collect all tags
        all_tags = defaultdict(set)

        for profile in profiles:
            for tag in profile['standard_tags']:
                all_tags[tag].add(profile['cik'])
            for tag in profile['custom_tags']:
                all_tags[tag].add(profile['cik'])

        # Calculate overlap statistics
        tag_usage = []
        for tag, ciks in all_tags.items():
            tag_usage.append({
                'tag': tag,
                'companies_using': len(ciks),
                'percentage': len(ciks) / len(profiles) * 100,
                'ciks': list(ciks)
            })

        # Sort by usage
        tag_usage.sort(key=lambda x: x['companies_using'], reverse=True)

        # Save overlap analysis
        overlap_file = self.output_dir / 'tag_overlap_analysis.json'
        with open(overlap_file, 'w', encoding='utf-8') as f:
            json.dump(tag_usage, f, indent=2)

        # Create summary
        common_tags = [t for t in tag_usage if t['companies_using'] == len(profiles)]
        mostly_common = [t for t in tag_usage if t['companies_using'] >= len(profiles) * 0.7]
        unique_tags = [t for t in tag_usage if t['companies_using'] == 1]

        logger.info(f"Tags used by ALL companies: {len(common_tags)}")
        logger.info(f"Tags used by 70%+ companies: {len(mostly_common)}")
        logger.info(f"Company-unique tags: {len(unique_tags)}")

        return {
            'common_tags': common_tags,
            'mostly_common': mostly_common,
            'unique_tags': unique_tags,
            'all_tag_usage': tag_usage
        }


def main():
    """Main execution"""
    import sys

    # Get year and quarter from arguments
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2024
    quarter = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    n_companies = int(sys.argv[3]) if len(sys.argv) > 3 else 10

    print(f"\n{'='*60}")
    print(f"Company Tag Extractor - {year}Q{quarter}")
    print(f"Extracting tag profiles for top {n_companies} companies")
    print(f"{'='*60}\n")

    # Create extractor
    extractor = CompanyTagExtractor(year, quarter)

    # Load data
    extractor.load_data()

    # Extract top companies
    profiles = extractor.extract_top_companies(n_companies)

    # Create summary report
    summary = extractor.create_summary_report(profiles)

    # Analyze tag overlap
    overlap = extractor.analyze_tag_overlap(profiles)

    print(f"\n{'='*60}")
    print("EXTRACTION COMPLETE")
    print(f"{'='*60}")
    print(f"Companies processed: {len(profiles)}")
    print(f"Output directory: {extractor.output_dir}")
    print(f"\nFiles created:")
    print(f"  - {n_companies} individual company tag profiles (JSON)")
    print(f"  - extraction_summary.json")
    print(f"  - extraction_summary.csv")
    print(f"  - tag_overlap_analysis.json")
    print(f"\nTag Overlap Statistics:")
    print(f"  - Universal tags (100% companies): {len(overlap['common_tags'])}")
    print(f"  - Common tags (70%+ companies): {len(overlap['mostly_common'])}")
    print(f"  - Unique tags (single company): {len(overlap['unique_tags'])}")

    return profiles, summary, overlap


if __name__ == "__main__":
    profiles, summary, overlap = main()
