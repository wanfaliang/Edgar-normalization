"""
Add Statement Type Identification to Extracted Tags
===================================================
Enhances existing tag profiles with statement type identification using:
- PRE (Presentation) table for statement context
- TAG table iord field (I=Balance Sheet, D=Income/Cash Flow)
- TAG table crdr field (C=Credit, D=Debit)
- Tag naming conventions

Usage:
    python src/add_statement_type_to_tags.py

Author: Faliang & Claude
Date: November 2025
"""

import pandas as pd
import json
from pathlib import Path
from typing import Dict, List
import logging
from config import StorageConfig

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class StatementTypeIdentifier:
    """Identifies which financial statement each tag belongs to"""

    def __init__(self, year: int = 2024, quarter: int = 3):
        self.year = year
        self.quarter = quarter

        # Use StorageConfig
        storage = StorageConfig()
        self.base_dir = storage.extracted_dir / f'{year}q{quarter}'
        self.profiles_dir = self.base_dir / 'company_tag_profiles'

        # Statement type mappings
        self.STATEMENT_TYPES = {
            'balance_sheet': 'Balance Sheet',
            'income_statement': 'Income Statement',
            'cash_flow': 'Cash Flow Statement',
            'equity': 'Statement of Equity',
            'unknown': 'Unknown'
        }

    def load_pre_table(self) -> pd.DataFrame:
        """Load PRE (Presentation) table for statement identification"""
        pre_file = self.base_dir / 'pre.txt'

        if not pre_file.exists():
            logger.warning(f"PRE table not found: {pre_file}")
            return pd.DataFrame()

        logger.info(f"Loading PRE table from {pre_file}...")
        pre_df = pd.read_csv(pre_file, sep='\t', low_memory=False)
        logger.info(f"PRE table loaded: {len(pre_df):,} rows")

        return pre_df

    def load_tag_table(self) -> pd.DataFrame:
        """Load TAG table for metadata"""
        tag_file = self.base_dir / 'tag.txt'

        logger.info(f"Loading TAG table from {tag_file}...")
        tag_df = pd.read_csv(tag_file, sep='\t', low_memory=False)
        logger.info(f"TAG table loaded: {len(tag_df):,} rows")

        return tag_df

    def identify_statement_from_iord(self, iord: str, crdr: str = None) -> str:
        """
        Identify statement type from iord (Instant or Duration) and crdr fields

        Args:
            iord: I = Instant (Balance Sheet), D = Duration (Income/Cash Flow)
            crdr: C = Credit, D = Debit (helps distinguish within BS)

        Returns:
            Statement type identifier
        """
        if pd.isna(iord) or iord == '':
            return 'unknown'

        iord = str(iord).upper()

        if iord == 'I':
            # Instant = Balance Sheet item
            return 'balance_sheet'
        elif iord == 'D':
            # Duration = could be Income Statement or Cash Flow
            # Need additional signals to distinguish
            return 'income_or_cash_flow'
        else:
            return 'unknown'

    def identify_statement_from_tag_name(self, tag: str) -> str:
        """
        Identify statement from tag naming conventions

        Args:
            tag: Tag name

        Returns:
            Statement type identifier
        """
        tag_lower = tag.lower()

        # Balance Sheet indicators
        if any(keyword in tag_lower for keyword in ['asset', 'liability', 'liabilities', 'equity',
                                                      'stockholder', 'shareholder', 'payable',
                                                      'receivable', 'inventory', 'property']):
            return 'balance_sheet'

        # Income Statement indicators
        if any(keyword in tag_lower for keyword in ['revenue', 'income', 'expense', 'profit',
                                                      'loss', 'earnings', 'ebitda', 'ebit',
                                                      'gross', 'operating', 'netincome']):
            return 'income_statement'

        # Cash Flow indicators
        if any(keyword in tag_lower for keyword in ['cashflow', 'cashprovided', 'cashused',
                                                      'operatingactivities', 'investingactivities',
                                                      'financingactivities']):
            return 'cash_flow'

        # Equity statement indicators
        if any(keyword in tag_lower for keyword in ['stockissued', 'stockrepurchase',
                                                      'dividendspaid', 'comprehensiveincome']):
            return 'equity'

        return 'unknown'

    def identify_statement_from_pre(self, tag: str, pre_df: pd.DataFrame) -> str:
        """
        Identify statement from PRE table presentation data

        Args:
            tag: Tag name
            pre_df: PRE table dataframe

        Returns:
            Statement type identifier
        """
        if pre_df.empty:
            return 'unknown'

        # Find tag in PRE table
        tag_pres = pre_df[pre_df['tag'] == tag]

        if tag_pres.empty:
            return 'unknown'

        # Check stmt field in PRE table (statement identifier)
        # Common values: BS (Balance Sheet), IS (Income Statement), CF (Cash Flow), etc.
        if 'stmt' in tag_pres.columns:
            stmt_values = tag_pres['stmt'].unique()

            for stmt in stmt_values:
                if pd.isna(stmt):
                    continue

                stmt_str = str(stmt).upper()

                if 'BS' in stmt_str or 'BAL' in stmt_str:
                    return 'balance_sheet'
                elif 'IS' in stmt_str or 'INC' in stmt_str or 'OPS' in stmt_str:
                    return 'income_statement'
                elif 'CF' in stmt_str or 'CASH' in stmt_str:
                    return 'cash_flow'
                elif 'EQ' in stmt_str or 'EQUITY' in stmt_str or 'COMP' in stmt_str:
                    return 'equity'

        return 'unknown'

    def identify_statement_type(self, tag: str, tag_metadata: Dict, pre_df: pd.DataFrame) -> str:
        """
        Identify statement type using multiple signals (confidence hierarchy)

        Priority:
        1. PRE table (most reliable - actual presentation)
        2. iord field (reliable - accounting standard)
        3. Tag naming conventions (fallback)

        Args:
            tag: Tag name
            tag_metadata: Metadata from TAG table
            pre_df: PRE table dataframe

        Returns:
            Statement type identifier
        """
        # Try PRE table first (most reliable)
        from_pre = self.identify_statement_from_pre(tag, pre_df)
        if from_pre != 'unknown':
            return from_pre

        # Try iord field
        iord = tag_metadata.get('iord', '')
        crdr = tag_metadata.get('crdr', '')
        from_iord = self.identify_statement_from_iord(iord, crdr)

        if from_iord == 'balance_sheet':
            return 'balance_sheet'
        elif from_iord == 'income_or_cash_flow':
            # Need to distinguish - use tag name
            from_name = self.identify_statement_from_tag_name(tag)
            if from_name in ['income_statement', 'cash_flow']:
                return from_name
            # Default to income statement for duration items
            return 'income_statement'

        # Fallback to tag naming
        from_name = self.identify_statement_from_tag_name(tag)
        if from_name != 'unknown':
            return from_name

        return 'unknown'

    def enrich_profile_with_statement_types(self, profile: Dict, tag_df: pd.DataFrame,
                                           pre_df: pd.DataFrame) -> Dict:
        """
        Enrich existing profile with statement type information

        Args:
            profile: Company tag profile
            tag_df: TAG table dataframe
            pre_df: PRE table dataframe

        Returns:
            Enriched profile
        """
        # Add statement type to each tag detail
        for tag_detail in profile['tag_details']:
            tag = tag_detail['tag']

            # Get tag metadata
            tag_metadata = {
                'iord': tag_detail.get('iord', ''),
                'crdr': tag_detail.get('crdr', ''),
            }

            # Identify statement type
            stmt_type = self.identify_statement_type(tag, tag_metadata, pre_df)
            tag_detail['statement_type'] = stmt_type

        # Add summary statistics by statement
        stmt_counts = {}
        for tag_detail in profile['tag_details']:
            stmt = tag_detail['statement_type']
            stmt_counts[stmt] = stmt_counts.get(stmt, 0) + 1

        profile['tags_by_statement'] = stmt_counts

        return profile

    def process_all_profiles(self):
        """Process all existing profiles and add statement type information"""

        logger.info("Loading TAG and PRE tables...")
        tag_df = self.load_tag_table()
        pre_df = self.load_pre_table()

        # Get all profile files
        profile_files = list(self.profiles_dir.glob('company_*_tags.json'))
        logger.info(f"\nFound {len(profile_files)} profiles to enrich")

        successful = 0
        failed = 0

        for i, profile_file in enumerate(profile_files, 1):
            logger.info(f"[{i}/{len(profile_files)}] Processing {profile_file.name}...")

            try:
                # Load profile
                with open(profile_file, 'r', encoding='utf-8') as f:
                    profile = json.load(f)

                # Enrich with statement types
                enriched_profile = self.enrich_profile_with_statement_types(profile, tag_df, pre_df)

                # Save enriched profile (overwrite)
                with open(profile_file, 'w', encoding='utf-8') as f:
                    json.dump(enriched_profile, f, indent=2, ensure_ascii=False)

                successful += 1
                logger.info(f"  ✅ Enriched: {enriched_profile.get('tags_by_statement', {})}")

            except Exception as e:
                failed += 1
                logger.error(f"  ❌ Error: {e}")

        logger.info("\n" + "=" * 80)
        logger.info("ENRICHMENT COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Successful: {successful}/{len(profile_files)}")
        logger.info(f"Failed: {failed}/{len(profile_files)}")


def main():
    """Main execution"""

    identifier = StatementTypeIdentifier(year=2024, quarter=3)
    identifier.process_all_profiles()


if __name__ == "__main__":
    main()
