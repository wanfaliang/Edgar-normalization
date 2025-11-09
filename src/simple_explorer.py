"""
SEC NUM+SUB Simple Explorer
===========================
Simple exploration script that merges NUM and SUB tables 
and outputs CSV/Excel files for manual analysis.
No filtering - we want to see EVERYTHING.

Author: Faliang
Date: November 2025
"""

import os
import requests
import zipfile
import pandas as pd
from pathlib import Path
from datetime import datetime
import logging
from config import StorageConfig

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleDataExplorer:
    """
    Simple explorer that merges NUM and SUB data and outputs files
    """
    
    def __init__(self, year: int = 2024, quarter: int = 2):
        self.year = year
        self.quarter = quarter

         # Use StorageConfig
        storage = StorageConfig()
        storage.create_directories()

        self.base_dir = storage.extracted_dir / f'{year}q{quarter}'
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        self.zip_file = f"{year}q{quarter}.zip"
        self.url = f"https://www.sec.gov/files/dera/data/financial-statement-data-sets/{self.zip_file}"
        
    def download_and_extract(self):
        """Download and extract the ZIP file"""
        zip_path = self.base_dir / self.zip_file
        
        # Download if needed
        if not zip_path.exists():
            logger.info(f"Downloading {self.zip_file}...")
            headers = {'User-Agent': 'Data Explorer (your.email@example.com)'}
            
            response = requests.get(self.url, headers=headers, stream=True)
            response.raise_for_status()
            
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info("Download complete")
        
        # Extract all files
        logger.info("Extracting all files...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(self.base_dir)
        logger.info("Extraction complete")
        
    def explore_and_merge(self):
        """Load, merge, and explore the data"""
        
        output_dir = self.base_dir / f'output_{self.year}q{self.quarter}'
        output_dir.mkdir(exist_ok=True)
        
        # ===== STEP 1: Load SUB table (company info) =====
        logger.info("Loading SUB table...")
        sub_file = self.base_dir / 'sub.txt'
        sub_df = pd.read_csv(sub_file, sep='\t', low_memory=False)
        logger.info(f"SUB loaded: {len(sub_df):,} rows, {len(sub_df.columns)} columns")
        logger.info(f"SUB columns: {list(sub_df.columns)}")
        
        # Save SUB sample
        sub_df.head(1000).to_csv(output_dir / 'sub_sample.csv', index=False)
        logger.info("Saved sub_sample.csv")
        
        # ===== STEP 2: Load NUM table (numerical data) =====
        logger.info("Loading NUM table (this may take a minute)...")
        num_file = self.base_dir / 'num.txt'
        
        # First, check the size
        file_size_mb = os.path.getsize(num_file) / (1024 * 1024)
        logger.info(f"NUM file size: {file_size_mb:.1f} MB")
        
        # Load in chunks if file is large
        if file_size_mb > 500:
            logger.info("Large file detected, loading first 1 million rows for exploration...")
            num_df = pd.read_csv(num_file, sep='\t', nrows=1000000, low_memory=False)
        else:
            num_df = pd.read_csv(num_file, sep='\t', low_memory=False)
            
        logger.info(f"NUM loaded: {len(num_df):,} rows, {len(num_df.columns)} columns")
        logger.info(f"NUM columns: {list(num_df.columns)}")
        
        # Save NUM sample (before merge)
        num_df.head(1000).to_csv(output_dir / 'num_sample_before_merge.csv', index=False)
        logger.info("Saved num_sample_before_merge.csv")
        
        # ===== STEP 3: Merge NUM with SUB =====
        logger.info("Merging NUM with SUB data...")
        
        # Select key columns from SUB to merge
        # You're right - left merge adds SUB columns to NUM dataframe
        sub_columns_to_merge = ['adsh', 'cik', 'name', 'sic', 'form', 'filed', 'period', 'fy', 'fp']
        
        # Make sure we only use columns that exist
        available_columns = [col for col in sub_columns_to_merge if col in sub_df.columns]
        logger.info(f"Merging these SUB columns: {available_columns}")
        
        # Left merge: keeps all NUM records, adds SUB info where available
        merged_df = pd.merge(
            num_df,
            sub_df[available_columns],
            on='adsh',
            how='left',
            suffixes=('', '_from_sub')  # In case of column name conflicts
        )
        
        logger.info(f"Merged data: {len(merged_df):,} rows, {len(merged_df.columns)} columns")
        logger.info(f"Merged columns: {list(merged_df.columns)}")
        
        # Check merge quality
        missing_cik = merged_df['cik'].isna().sum()
        logger.info(f"Records with CIK: {len(merged_df) - missing_cik:,}")
        logger.info(f"Records missing CIK: {missing_cik:,}")
        
        # ===== STEP 4: Analyze all tags (no filtering!) =====
        logger.info("Analyzing ALL tags in the dataset...")
        
        # Get tag frequency
        tag_counts = merged_df['tag'].value_counts()
        logger.info(f"Total unique tags: {len(tag_counts):,}")
        
        # Save tag analysis
        tag_analysis = pd.DataFrame({
            'tag': tag_counts.index,
            'count': tag_counts.values,
            'percentage': (tag_counts.values / len(merged_df)) * 100
        })
        tag_analysis.to_csv(output_dir / 'all_tags_frequency.csv', index=False)
        tag_analysis.head(500).to_excel(output_dir / 'top_500_tags.xlsx', index=False)
        logger.info("Saved all_tags_frequency.csv and top_500_tags.xlsx")
        
        # ===== STEP 5: Create various exploratory outputs =====
        
        # 1. General sample with company info
        logger.info("Creating general merged sample...")
        merged_sample = merged_df.head(10000)
        merged_sample.to_csv(output_dir / 'merged_sample.csv', index=False)
        merged_sample.head(5000).to_excel(output_dir / 'merged_sample.xlsx', index=False)
        logger.info("Saved merged_sample.csv and .xlsx")
        
        # 2. Group by company to see what each company reports
        logger.info("Creating company tag summary...")
        company_tags = merged_df.groupby(['cik', 'name'])['tag'].agg(['count', 'nunique']).reset_index()
        company_tags.columns = ['cik', 'name', 'total_records', 'unique_tags']
        company_tags = company_tags.sort_values('total_records', ascending=False)
        company_tags.head(1000).to_csv(output_dir / 'company_tag_summary.csv', index=False)
        company_tags.head(500).to_excel(output_dir / 'company_tag_summary.xlsx', index=False)
        logger.info("Saved company_tag_summary files")
        
        # 3. Random sample of different tags with values
        logger.info("Creating tag value samples...")
        # Get 100 random tags
        sample_tags = tag_counts.head(100).index
        tag_samples = []
        for tag in sample_tags:
            tag_data = merged_df[merged_df['tag'] == tag].head(10)
            if len(tag_data) > 0:
                tag_samples.append(tag_data)
        
        if tag_samples:
            tag_sample_df = pd.concat(tag_samples, ignore_index=True)
            tag_sample_df.to_csv(output_dir / 'tag_value_samples.csv', index=False)
            logger.info("Saved tag_value_samples.csv")
        
        # 4. Company-specific extracts for manual review
        logger.info("Creating company-specific extracts...")
        
        # Find a few companies with lots of data
        top_companies = company_tags.head(5)
        for _, company in top_companies.iterrows():
            company_cik = company['cik']
            company_name = str(company['name']).replace('/', '_').replace('\\', '_')[:50]  # Clean name for filename
            
            company_data = merged_df[merged_df['cik'] == company_cik].head(1000)
            if len(company_data) > 0:
                filename = f'company_{company_cik}_{company_name}.csv'
                company_data.to_csv(output_dir / filename, index=False)
                logger.info(f"Saved {filename}")
        
        # 5. Pivot table showing companies vs tags (small sample)
        logger.info("Creating company-tag pivot sample...")
        
        # Take top 20 companies and top 50 tags
        top_20_companies = company_tags.head(20)['cik'].tolist()
        top_50_tags = tag_counts.head(50).index.tolist()
        
        pivot_data = merged_df[
            (merged_df['cik'].isin(top_20_companies)) & 
            (merged_df['tag'].isin(top_50_tags))
        ]
        
        if len(pivot_data) > 0:
            pivot_table = pivot_data.pivot_table(
                index=['cik', 'name'],
                columns='tag',
                values='value',
                aggfunc='first'  # Just take first value for now
            )
            pivot_table.to_csv(output_dir / 'company_tag_pivot.csv')
            logger.info("Saved company_tag_pivot.csv")
        
        # ===== STEP 6: Create summary statistics =====
        logger.info("Creating summary statistics...")
        
        summary = {
            'Dataset': f'{self.year}Q{self.quarter}',
            'NUM Records': len(num_df),
            'SUB Records': len(sub_df),
            'Merged Records': len(merged_df),
            'Unique Tags': len(tag_counts),
            'Unique Companies (CIK)': merged_df['cik'].nunique(),
            'Unique Submissions (adsh)': merged_df['adsh'].nunique(),
            'Records with company name': len(merged_df) - merged_df['name'].isna().sum(),
            'File generated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        summary_df = pd.DataFrame([summary]).T
        summary_df.columns = ['Value']
        summary_df.to_csv(output_dir / 'exploration_summary.csv')
        logger.info("Saved exploration_summary.csv")
        
        # Print summary
        print("\n" + "="*60)
        print("EXPLORATION COMPLETE")
        print("="*60)
        for key, value in summary.items():
            print(f"{key}: {value}")
        print(f"\nAll files saved to: {output_dir}")
        
        return output_dir

def main():
    """Main execution"""
    import sys
    
    # Get year and quarter from arguments
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2024
    quarter = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    
    print(f"\nExploring SEC data for {year}Q{quarter}")
    print("This will download ~200-500MB and create exploration files")
    print("-" * 60)
    
    # Create explorer and run
    explorer = SimpleDataExplorer(year, quarter)
    
    # Download and extract
    explorer.download_and_extract()
    
    # Explore and merge
    output_dir = explorer.explore_and_merge()
    
    print("\n" + "="*60)
    print("FILES TO REVIEW")
    print("="*60)
    print("1. merged_sample.xlsx - General sample with company names")
    print("2. all_tags_frequency.csv - ALL tags and their frequencies")
    print("3. company_tag_summary.xlsx - What each company reports")
    print("4. tag_value_samples.csv - Sample values for different tags")
    print("5. company_*.csv - Specific company data")
    print("6. company_tag_pivot.csv - Pivot table of companies vs tags")
    print("\nOpen these files in Excel to explore the actual data structure!")

if __name__ == "__main__":
    main()