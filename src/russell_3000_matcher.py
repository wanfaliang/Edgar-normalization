"""
Russell 3000 Ticker to CIK Matcher
===================================
Matches Russell 3000 tickers to SEC CIK numbers and filters by 2024Q3 availability.

Usage:
    python src/russell_3000_matcher.py

Author: Faliang & Claude
Date: November 2025
"""

import pandas as pd
import requests
import json
from pathlib import Path
from typing import Dict, List, Set
import sys

# Add src to path
sys.path.append(str(Path(__file__).parent))
from config import SECConfig, StorageConfig


class Russell3000Matcher:
    """Match Russell 3000 tickers to CIK numbers"""

    def __init__(self, russell_file: Path):
        self.russell_file = Path(russell_file)

        # Use config for paths
        storage_config = StorageConfig()
        self.extracted_dir = storage_config.extracted_dir

        sec_config = SECConfig()
        # Build proper User-Agent: "Company (email)"
        self.user_agent = f"{sec_config.user_agent_company} ({sec_config.user_agent_email})"

    def load_russell_3000(self) -> pd.DataFrame:
        """Load Russell 3000 ticker list"""
        print("Loading Russell 3000 list...")
        df = pd.read_csv(self.russell_file)
        print(f"  ✅ Loaded {len(df)} companies")
        return df

    def fetch_sec_ticker_cik_mapping(self) -> Dict[str, Dict]:
        """
        Fetch SEC's official ticker → CIK mapping

        Returns:
            Dict mapping ticker to company info
            Example: {'AAPL': {'cik_str': 320193, 'title': 'Apple Inc.'}}
        """
        print("\nFetching SEC ticker → CIK mapping...")
        url = "https://www.sec.gov/files/company_tickers.json"
        headers = {"User-Agent": self.user_agent}

        response = requests.get(url, headers=headers)
        response.raise_for_status()

        raw_data = response.json()

        # Reformat: {ticker: {cik, title}}
        ticker_map = {}
        for entry in raw_data.values():
            ticker = entry['ticker'].upper()
            ticker_map[ticker] = {
                'cik': str(entry['cik_str']).zfill(10),  # Pad to 10 digits
                'cik_int': entry['cik_str'],
                'title': entry['title']
            }

        print(f"  ✅ Fetched {len(ticker_map)} ticker → CIK mappings")
        return ticker_map

    def load_2024q3_companies(self) -> Set[str]:
        """
        Load CIKs that filed in 2024Q3

        Returns:
            Set of CIKs (10-digit strings with leading zeros)
        """
        print("\nLoading 2024Q3 filing companies...")
        sub_file = self.extracted_dir / '2024q3' / 'sub.txt'

        if not sub_file.exists():
            print(f"  ⚠️  Warning: {sub_file} not found")
            return set()

        # Read SUB table (only CIK column for memory efficiency)
        sub_df = pd.read_csv(sub_file, sep='\t', encoding='latin-1',
                            usecols=['cik'], low_memory=False)

        # Convert CIKs to 10-digit strings
        ciks = set(str(cik).zfill(10) for cik in sub_df['cik'].unique())

        print(f"  ✅ Found {len(ciks)} companies in 2024Q3 data")
        return ciks

    def match_russell_to_cik(self, russell_df: pd.DataFrame,
                            sec_mapping: Dict,
                            q3_ciks: Set[str]) -> pd.DataFrame:
        """
        Match Russell 3000 tickers to CIKs and check 2024Q3 availability

        Args:
            russell_df: Russell 3000 DataFrame
            sec_mapping: SEC ticker → CIK mapping
            q3_ciks: Set of CIKs in 2024Q3 data

        Returns:
            DataFrame with matched companies
        """
        print("\nMatching Russell 3000 to SEC CIKs...")

        results = []

        for idx, row in russell_df.iterrows():
            # Handle NaN or empty symbols
            symbol = row['Symbol']
            if pd.isna(symbol) or symbol == '':
                continue

            ticker = str(symbol).upper()

            # Try to match ticker
            if ticker in sec_mapping:
                sec_info = sec_mapping[ticker]
                cik = sec_info['cik']
                in_q3 = cik in q3_ciks

                results.append({
                    'ticker': ticker,
                    'name_russell': row['Name'],
                    'name_sec': sec_info['title'],
                    'cik': cik,
                    'cik_int': sec_info['cik_int'],
                    'sector': row['Sector'],
                    'market_value': row['Market Value'],
                    'weight_pct': row['Weight(%)'],
                    'in_2024q3': in_q3
                })
            else:
                # No match found
                results.append({
                    'ticker': ticker,
                    'name_russell': row['Name'],
                    'name_sec': None,
                    'cik': None,
                    'cik_int': None,
                    'sector': row['Sector'],
                    'market_value': row['Market Value'],
                    'weight_pct': row['Weight(%)'],
                    'in_2024q3': False
                })

        matched_df = pd.DataFrame(results)

        # Statistics
        total = len(matched_df)
        matched = matched_df['cik'].notna().sum()
        in_q3 = matched_df['in_2024q3'].sum()

        print(f"\n  ✅ Matched {matched}/{total} tickers to CIKs ({matched/total*100:.1f}%)")
        print(f"  ✅ Found {in_q3}/{matched} in 2024Q3 data ({in_q3/matched*100:.1f}%)")

        return matched_df

    def create_stratified_sample(self, matched_df: pd.DataFrame,
                                total_sample: int = 50) -> pd.DataFrame:
        """
        Create stratified sample by market cap and sector

        Strategy:
        - Large-cap (top 200): 20 companies
        - Mid-cap (200-1000): 20 companies
        - Small-cap (1000+): 10 companies
        - Diversified across sectors

        Args:
            matched_df: Matched Russell 3000 DataFrame
            total_sample: Total companies to sample (default: 50)

        Returns:
            DataFrame with sampled companies
        """
        print(f"\nCreating stratified sample ({total_sample} companies)...")

        # Filter to companies in 2024Q3 data
        available = matched_df[matched_df['in_2024q3']].copy()

        # Parse market value (remove $ and commas)
        available['market_value_num'] = available['market_value'].str.replace(
            r'[\$,]', '', regex=True).astype(float)

        # Sort by market value
        available = available.sort_values('market_value_num', ascending=False).reset_index(drop=True)

        # Define strata
        large_cap = available.iloc[:200]      # Top 200
        mid_cap = available.iloc[200:1000]    # 200-1000
        small_cap = available.iloc[1000:]     # 1000+

        print(f"  Available by size:")
        print(f"    Large-cap (1-200): {len(large_cap)}")
        print(f"    Mid-cap (201-1000): {len(mid_cap)}")
        print(f"    Small-cap (1001+): {len(small_cap)}")

        # Sample from each stratum
        sample_large = self._sample_by_sector(large_cap, 20)
        sample_mid = self._sample_by_sector(mid_cap, 20)
        sample_small = self._sample_by_sector(small_cap, 10)

        # Combine
        sample = pd.concat([sample_large, sample_mid, sample_small])

        print(f"\n  ✅ Selected {len(sample)} companies:")
        print(f"    Large-cap: {len(sample_large)}")
        print(f"    Mid-cap: {len(sample_mid)}")
        print(f"    Small-cap: {len(sample_small)}")

        return sample

    def _sample_by_sector(self, df: pd.DataFrame, n: int) -> pd.DataFrame:
        """
        Sample n companies with sector diversity

        Strategy: Proportional to sector representation in stratum
        """
        if len(df) == 0:
            return pd.DataFrame()

        # Get sector distribution
        sector_counts = df['sector'].value_counts()

        # Calculate proportional sample sizes
        samples = []
        remaining = n

        for sector, count in sector_counts.items():
            # Proportional allocation (at least 1 if sector exists and space available)
            sector_sample_size = max(1, int(count / len(df) * n))
            sector_sample_size = min(sector_sample_size, remaining, count)

            if sector_sample_size > 0:
                sector_df = df[df['sector'] == sector]
                sample = sector_df.sample(min(sector_sample_size, len(sector_df)),
                                         random_state=42)
                samples.append(sample)
                remaining -= len(sample)

            if remaining == 0:
                break

        result = pd.concat(samples) if samples else pd.DataFrame()

        # If we haven't reached n yet, add more randomly
        if len(result) < n and len(result) < len(df):
            additional_needed = n - len(result)
            remaining_df = df[~df.index.isin(result.index)]
            additional = remaining_df.sample(min(additional_needed, len(remaining_df)),
                                            random_state=42)
            result = pd.concat([result, additional])

        return result

    def save_results(self, matched_df: pd.DataFrame,
                    sample_df: pd.DataFrame,
                    output_dir: Path):
        """Save matching results and sample"""

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save full matched list
        matched_file = output_dir / 'russell_3000_with_ciks.csv'
        matched_df.to_csv(matched_file, index=False)
        print(f"\n✅ Saved full matched list: {matched_file}")

        # Save sample
        sample_file = output_dir / 'russell_3000_sample_50.csv'
        sample_df.to_csv(sample_file, index=False)
        print(f"✅ Saved stratified sample: {sample_file}")

        # Save CIK list for tag extraction
        cik_list_file = output_dir / 'sample_ciks.txt'
        with open(cik_list_file, 'w') as f:
            for cik in sample_df['cik'].values:
                f.write(f"{cik}\n")
        print(f"✅ Saved CIK list: {cik_list_file}")

        # Generate summary report
        self._generate_summary_report(matched_df, sample_df, output_dir)

    def _generate_summary_report(self, matched_df: pd.DataFrame,
                                sample_df: pd.DataFrame,
                                output_dir: Path):
        """Generate summary statistics report"""

        report = []
        report.append("=" * 80)
        report.append("RUSSELL 3000 MATCHING SUMMARY")
        report.append("=" * 80)
        report.append("")

        # Overall stats
        total = len(matched_df)
        matched = matched_df['cik'].notna().sum()
        in_q3 = matched_df['in_2024q3'].sum()

        report.append(f"Total Russell 3000 companies: {total}")
        report.append(f"Matched to SEC CIK: {matched} ({matched/total*100:.1f}%)")
        report.append(f"Available in 2024Q3: {in_q3} ({in_q3/matched*100:.1f}% of matched)")
        report.append("")

        # Sample stats
        report.append("-" * 80)
        report.append("STRATIFIED SAMPLE (50 companies)")
        report.append("-" * 80)
        report.append("")

        # By market cap tier
        sample_df_sorted = sample_df.copy()
        sample_df_sorted['market_value_num'] = sample_df_sorted['market_value'].str.replace(
            r'[\$,]', '', regex=True).astype(float)
        sample_df_sorted = sample_df_sorted.sort_values('market_value_num', ascending=False)

        report.append("By Market Cap Tier:")
        report.append(f"  Large-cap (1-200): {len(sample_df_sorted.iloc[:20])}")
        report.append(f"  Mid-cap (201-1000): {len(sample_df_sorted.iloc[20:40])}")
        report.append(f"  Small-cap (1001+): {len(sample_df_sorted.iloc[40:])}")
        report.append("")

        # By sector
        report.append("By Sector:")
        sector_counts = sample_df['sector'].value_counts().sort_values(ascending=False)
        for sector, count in sector_counts.items():
            report.append(f"  {sector:30} {count}")
        report.append("")

        # Top 10 companies in sample
        report.append("-" * 80)
        report.append("TOP 10 COMPANIES IN SAMPLE")
        report.append("-" * 80)
        for idx, row in sample_df_sorted.head(10).iterrows():
            report.append(f"  {row['ticker']:6} {row['name_russell']:40} {row['sector']}")
        report.append("")

        # Save report
        report_file = output_dir / 'matching_summary.txt'
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report))

        print(f"✅ Saved summary report: {report_file}")

        # Print to console
        print("\n" + "\n".join(report))


def main():
    """Main execution"""

    russell_file = Path('data/Russell_3000.csv')
    output_dir = Path('data/russell_3000_matched')

    if not russell_file.exists():
        print(f"Error: {russell_file} not found")
        return

    # Initialize matcher
    matcher = Russell3000Matcher(russell_file)

    # Load Russell 3000
    russell_df = matcher.load_russell_3000()

    # Fetch SEC mapping
    sec_mapping = matcher.fetch_sec_ticker_cik_mapping()

    # Load 2024Q3 companies
    q3_ciks = matcher.load_2024q3_companies()

    # Match
    matched_df = matcher.match_russell_to_cik(russell_df, sec_mapping, q3_ciks)

    # Create stratified sample
    sample_df = matcher.create_stratified_sample(matched_df, total_sample=50)

    # Save results
    matcher.save_results(matched_df, sample_df, output_dir)

    print("\n" + "=" * 80)
    print("READY TO EXTRACT TAGS FOR 50 MAINSTREAM COMPANIES!")
    print("=" * 80)
    print(f"\nNext step: Run tag extraction on {len(sample_df)} companies")
    print(f"CIK list: {output_dir / 'sample_ciks.txt'}")


if __name__ == "__main__":
    main()
