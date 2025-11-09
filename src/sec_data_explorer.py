"""
SEC Financial Statement Data Sets - Data Structure Explorer
===========================================================
This script downloads a sample dataset and performs comprehensive analysis
to understand the data structure, relationships, and contents.

Author: Faliang
Date: November 2025
"""

import os
import requests
import zipfile
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import json
from datetime import datetime
import logging
from collections import Counter, defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SECDataExplorer:
    """
    Explores and documents the structure of SEC Financial Statement Data Sets
    """
    
    def __init__(self, sample_year: int = 2024, sample_quarter: int = 2):
        self.sample_year = sample_year
        self.sample_quarter = sample_quarter
        self.base_dir = Path.home() / 'sec_data_exploration'
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        self.sample_file = f"{sample_year}q{sample_quarter}.zip"
        self.sample_url = f"https://www.sec.gov/files/dera/data/financial-statement-data-sets/{self.sample_file}"
        
        # User agent for SEC compliance
        self.headers = {
            'User-Agent': 'Data Explorer (your.email@example.com)'
        }
        
        self.dataframes = {}
        self.analysis_results = {}
        
    def download_sample(self) -> bool:
        """Download a sample dataset for exploration"""
        file_path = self.base_dir / self.sample_file
        
        if file_path.exists():
            logger.info(f"Sample file {self.sample_file} already exists")
            return True
            
        try:
            logger.info(f"Downloading sample dataset: {self.sample_file}")
            response = requests.get(self.sample_url, headers=self.headers, stream=True)
            response.raise_for_status()
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        
            logger.info(f"Successfully downloaded {self.sample_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading sample: {e}")
            return False
            
    def extract_and_load(self) -> bool:
        """Extract the ZIP file and load all tables"""
        zip_path = self.base_dir / self.sample_file
        extract_path = self.base_dir / 'extracted'
        extract_path.mkdir(exist_ok=True)
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
                
            # Expected table files
            expected_tables = ['sub', 'tag', 'num', 'txt', 'ren', 'pre', 'cal', 'dim']
            
            for table_name in expected_tables:
                table_file = extract_path / f"{table_name}.txt"
                if table_file.exists():
                    logger.info(f"Loading {table_name}.txt...")
                    # Load with no type inference first to explore
                    df = pd.read_csv(table_file, sep='\t', low_memory=False, nrows=100000)
                    self.dataframes[table_name] = df
                    logger.info(f"Loaded {table_name}: {len(df)} rows, {len(df.columns)} columns")
                else:
                    logger.warning(f"Table {table_name}.txt not found")
                    
            return len(self.dataframes) > 0
            
        except Exception as e:
            logger.error(f"Error extracting/loading data: {e}")
            return False
            
    def analyze_table_structure(self, table_name: str, df: pd.DataFrame) -> Dict:
        """Analyze the structure of a single table"""
        analysis = {
            'table_name': table_name,
            'row_count': len(df),
            'column_count': len(df.columns),
            'columns': [],
            'memory_usage_mb': df.memory_usage(deep=True).sum() / 1024 / 1024,
            'sample_data': df.head(3).to_dict('records'),
            'relationships': []
        }
        
        for col in df.columns:
            col_analysis = {
                'name': col,
                'dtype': str(df[col].dtype),
                'null_count': df[col].isna().sum(),
                'null_percentage': (df[col].isna().sum() / len(df)) * 100,
                'unique_values': df[col].nunique(),
                'sample_values': df[col].dropna().head(5).tolist() if len(df[col].dropna()) > 0 else []
            }
            
            # Additional analysis for specific data types
            if pd.api.types.is_numeric_dtype(df[col]):
                col_analysis['min'] = df[col].min()
                col_analysis['max'] = df[col].max()
                col_analysis['mean'] = df[col].mean()
                col_analysis['median'] = df[col].median()
                
            elif pd.api.types.is_string_dtype(df[col]):
                col_analysis['max_length'] = df[col].astype(str).str.len().max()
                col_analysis['min_length'] = df[col].astype(str).str.len().min()
                
                # Check if it might be a date
                if col in ['date', 'ddate', 'filed', 'period', 'accepted']:
                    try:
                        sample_dates = pd.to_datetime(df[col].dropna().head(100), errors='coerce')
                        if sample_dates.notna().sum() > 80:  # 80% success rate
                            col_analysis['likely_date'] = True
                            col_analysis['date_range'] = {
                                'min': str(sample_dates.min()),
                                'max': str(sample_dates.max())
                            }
                    except:
                        pass
                        
            # Check for potential foreign keys
            if col in ['adsh', 'cik', 'tag', 'version']:
                col_analysis['potential_key'] = True
                
            analysis['columns'].append(col_analysis)
            
        return analysis
        
    def discover_relationships(self) -> Dict:
        """Discover relationships between tables"""
        relationships = {
            'primary_keys': {},
            'foreign_keys': [],
            'common_columns': defaultdict(list)
        }
        
        # Find common columns across tables
        all_columns = {}
        for table_name, df in self.dataframes.items():
            all_columns[table_name] = set(df.columns)
            
        # Identify common columns
        for table1 in all_columns:
            for table2 in all_columns:
                if table1 != table2:
                    common = all_columns[table1].intersection(all_columns[table2])
                    if common:
                        relationships['common_columns'][f"{table1}-{table2}"] = list(common)
                        
        # Identify likely primary keys
        for table_name, df in self.dataframes.items():
            # Check for columns that might be primary keys
            for col in df.columns:
                if df[col].nunique() == len(df):
                    relationships['primary_keys'][table_name] = col
                    break
                    
            # Check for composite keys
            if table_name not in relationships['primary_keys']:
                if 'adsh' in df.columns:
                    # Check combinations with adsh
                    for other_col in df.columns:
                        if other_col != 'adsh':
                            composite_key = df.groupby(['adsh', other_col]).size()
                            if len(composite_key) == len(df):
                                relationships['primary_keys'][table_name] = f"adsh+{other_col}"
                                break
                                
        # Identify foreign key relationships
        if 'adsh' in self.dataframes.get('sub', pd.DataFrame()).columns:
            for table_name, df in self.dataframes.items():
                if table_name != 'sub' and 'adsh' in df.columns:
                    relationships['foreign_keys'].append({
                        'from_table': table_name,
                        'from_column': 'adsh',
                        'to_table': 'sub',
                        'to_column': 'adsh'
                    })
                    
        return relationships
        
    def analyze_data_patterns(self) -> Dict:
        """Analyze data patterns and content types"""
        patterns = {
            'filing_types': {},
            'date_ranges': {},
            'company_info': {},
            'tag_categories': {},
            'numeric_patterns': {}
        }
        
        # Analyze SUB table for filing information
        if 'sub' in self.dataframes:
            sub_df = self.dataframes['sub']
            
            if 'form' in sub_df.columns:
                patterns['filing_types'] = sub_df['form'].value_counts().head(20).to_dict()
                
            if 'filed' in sub_df.columns:
                try:
                    filed_dates = pd.to_datetime(sub_df['filed'], errors='coerce')
                    patterns['date_ranges']['filing_dates'] = {
                        'min': str(filed_dates.min()),
                        'max': str(filed_dates.max()),
                        'span_days': (filed_dates.max() - filed_dates.min()).days
                    }
                except:
                    pass
                    
            if 'name' in sub_df.columns:
                patterns['company_info']['total_companies'] = sub_df['name'].nunique()
                patterns['company_info']['top_filers'] = sub_df['name'].value_counts().head(10).to_dict()
                
            if 'sic' in sub_df.columns:
                patterns['company_info']['industry_distribution'] = sub_df['sic'].value_counts().head(10).to_dict()
                
        # Analyze NUM table for numerical data patterns
        if 'num' in self.dataframes:
            num_df = self.dataframes['num']
            
            if 'tag' in num_df.columns:
                patterns['tag_categories']['total_tags'] = num_df['tag'].nunique()
                patterns['tag_categories']['most_common_tags'] = num_df['tag'].value_counts().head(20).to_dict()
                
                # Categorize tags
                tag_categories = {
                    'assets': [],
                    'liabilities': [],
                    'equity': [],
                    'revenue': [],
                    'expenses': [],
                    'cash_flow': []
                }
                
                for tag in num_df['tag'].unique()[:1000]:  # Sample first 1000
                    tag_lower = tag.lower()
                    if 'asset' in tag_lower:
                        tag_categories['assets'].append(tag)
                    elif 'liabilit' in tag_lower:
                        tag_categories['liabilities'].append(tag)
                    elif 'equity' in tag_lower or 'stock' in tag_lower:
                        tag_categories['equity'].append(tag)
                    elif 'revenue' in tag_lower or 'sale' in tag_lower:
                        tag_categories['revenue'].append(tag)
                    elif 'expense' in tag_lower or 'cost' in tag_lower:
                        tag_categories['expenses'].append(tag)
                    elif 'cash' in tag_lower:
                        tag_categories['cash_flow'].append(tag)
                        
                for category, tags in tag_categories.items():
                    patterns['tag_categories'][f'{category}_count'] = len(tags)
                    patterns['tag_categories'][f'{category}_examples'] = tags[:5]
                    
            if 'value' in num_df.columns:
                patterns['numeric_patterns']['value_statistics'] = {
                    'min': float(num_df['value'].min()),
                    'max': float(num_df['value'].max()),
                    'mean': float(num_df['value'].mean()),
                    'median': float(num_df['value'].median()),
                    'std': float(num_df['value'].std())
                }
                
            if 'uom' in num_df.columns:
                patterns['numeric_patterns']['units_of_measure'] = num_df['uom'].value_counts().head(10).to_dict()
                
        # Analyze TAG table for taxonomy information
        if 'tag' in self.dataframes:
            tag_df = self.dataframes['tag']
            
            if 'version' in tag_df.columns:
                patterns['tag_categories']['taxonomy_versions'] = tag_df['version'].value_counts().head(10).to_dict()
                
            if 'custom' in tag_df.columns:
                patterns['tag_categories']['custom_vs_standard'] = tag_df['custom'].value_counts().to_dict()
                
        return patterns
        
    def generate_sample_queries(self) -> List[Dict]:
        """Generate sample SQL queries for common use cases"""
        queries = []
        
        # Query 1: Get all financial data for a specific company
        queries.append({
            'name': 'Company Financial Data',
            'description': 'Get all numerical financial data for a specific company',
            'sql': """
                SELECT 
                    s.name as company_name,
                    s.cik,
                    n.tag,
                    n.value,
                    n.uom as unit_of_measure,
                    n.ddate as period_date,
                    s.form as form_type,
                    s.filed as filing_date
                FROM num n
                JOIN sub s ON n.adsh = s.adsh
                WHERE s.cik = '0000320193'  -- Apple Inc
                  AND s.form IN ('10-K', '10-Q')
                ORDER BY s.filed DESC, n.tag;
            """
        })
        
        # Query 2: Get balance sheet items
        queries.append({
            'name': 'Balance Sheet Items',
            'description': 'Extract common balance sheet items for all companies',
            'sql': """
                SELECT 
                    s.name,
                    s.cik,
                    n.tag,
                    n.value,
                    n.ddate
                FROM num n
                JOIN sub s ON n.adsh = s.adsh
                WHERE n.tag IN (
                    'Assets',
                    'AssetsCurrent',
                    'Liabilities',
                    'LiabilitiesCurrent',
                    'StockholdersEquity'
                )
                AND s.form = '10-K'
                ORDER BY s.name, n.ddate DESC;
            """
        })
        
        # Query 3: Revenue trend analysis
        queries.append({
            'name': 'Revenue Trend',
            'description': 'Track revenue over time for companies',
            'sql': """
                SELECT 
                    s.name,
                    n.ddate as period_end,
                    n.value as revenue,
                    n.qtrs as quarters_covered
                FROM num n
                JOIN sub s ON n.adsh = s.adsh
                WHERE n.tag IN ('Revenues', 'SalesRevenueNet', 'RevenueFromContractWithCustomerExcludingAssessedTax')
                  AND n.qtrs = 4  -- Annual values
                ORDER BY s.name, n.ddate;
            """
        })
        
        # Query 4: Industry comparison
        queries.append({
            'name': 'Industry Comparison',
            'description': 'Compare key metrics across companies in same industry',
            'sql': """
                SELECT 
                    s.sic,
                    s.name,
                    MAX(CASE WHEN n.tag = 'Assets' THEN n.value END) as total_assets,
                    MAX(CASE WHEN n.tag = 'Revenues' THEN n.value END) as total_revenue,
                    MAX(CASE WHEN n.tag = 'NetIncomeLoss' THEN n.value END) as net_income
                FROM num n
                JOIN sub s ON n.adsh = s.adsh
                WHERE s.form = '10-K'
                  AND n.ddate = (SELECT MAX(ddate) FROM num WHERE adsh = n.adsh)
                GROUP BY s.sic, s.name
                ORDER BY s.sic, total_assets DESC;
            """
        })
        
        return queries
        
    def create_data_dictionary(self) -> Dict:
        """Create a comprehensive data dictionary"""
        data_dict = {
            'dataset_info': {
                'year': self.sample_year,
                'quarter': self.sample_quarter,
                'download_date': str(datetime.now()),
                'file_name': self.sample_file
            },
            'tables': {}
        }
        
        # Define known column meanings (based on SEC documentation)
        column_definitions = {
            'adsh': 'Accession Number - Unique identifier for each filing',
            'cik': 'Central Index Key - Unique identifier for each entity',
            'name': 'Company name',
            'sic': 'Standard Industrial Classification code',
            'form': 'Form type (10-K, 10-Q, 8-K, etc.)',
            'filed': 'Filing date',
            'period': 'Balance sheet date',
            'tag': 'XBRL tag for the financial concept',
            'version': 'Taxonomy version',
            'value': 'Numerical value',
            'uom': 'Unit of measure',
            'qtrs': 'Number of quarters (0 for point-in-time, 1-4 for periods)',
            'ddate': 'End date of the period',
            'coreg': 'Co-registrant identifier',
            'stmt': 'Financial statement location',
            'report': 'Report section',
            'line': 'Line number in report',
            'custom': 'Flag for custom tag (1) vs standard (0)',
            'abstract': 'Abstract concept flag',
            'datatype': 'Data type of the tag',
            'iord': 'Balance type (Instant or Duration)',
            'crdr': 'Natural balance (Credit or Debit)',
            'tlabel': 'Tag label',
            'doc': 'Tag documentation'
        }
        
        for table_name, df in self.dataframes.items():
            table_dict = {
                'description': self.get_table_description(table_name),
                'row_count': len(df),
                'columns': {}
            }
            
            for col in df.columns:
                col_dict = {
                    'name': col,
                    'type': str(df[col].dtype),
                    'description': column_definitions.get(col, 'To be determined'),
                    'nullable': df[col].isna().any(),
                    'unique_count': df[col].nunique()
                }
                
                if df[col].nunique() < 20 and df[col].nunique() > 0:
                    col_dict['possible_values'] = df[col].dropna().unique().tolist()[:20]
                    
                table_dict['columns'][col] = col_dict
                
            data_dict['tables'][table_name] = table_dict
            
        return data_dict
        
    def get_table_description(self, table_name: str) -> str:
        """Get description for each table"""
        descriptions = {
            'sub': 'Submission metadata - One row per filing with company information',
            'num': 'Numerical data - All numerical values from financial statements',
            'tag': 'Tag definitions - Taxonomy tags and their properties',
            'txt': 'Textual data - Footnotes and text disclosures',
            'ren': 'Rendering information - How data is displayed in reports',
            'pre': 'Presentation relationships - Parent-child relationships for line items',
            'cal': 'Calculation relationships - Mathematical relationships between tags',
            'dim': 'Dimensional data - Segment and dimensional information for disaggregated data'
        }
        return descriptions.get(table_name, 'Financial statement data table')
        
    def run_full_exploration(self) -> Dict:
        """Run complete data exploration"""
        logger.info("Starting SEC data exploration...")
        
        results = {
            'exploration_date': str(datetime.now()),
            'sample_dataset': self.sample_file,
            'status': 'starting'
        }
        
        # Step 1: Download sample
        if not self.download_sample():
            results['status'] = 'download_failed'
            return results
            
        # Step 2: Extract and load
        if not self.extract_and_load():
            results['status'] = 'extraction_failed'
            return results
            
        # Step 3: Analyze each table
        results['table_analysis'] = {}
        for table_name, df in self.dataframes.items():
            logger.info(f"Analyzing table: {table_name}")
            results['table_analysis'][table_name] = self.analyze_table_structure(table_name, df)
            
        # Step 4: Discover relationships
        logger.info("Discovering relationships...")
        results['relationships'] = self.discover_relationships()
        
        # Step 5: Analyze data patterns
        logger.info("Analyzing data patterns...")
        results['data_patterns'] = self.analyze_data_patterns()
        
        # Step 6: Generate sample queries
        results['sample_queries'] = self.generate_sample_queries()
        
        # Step 7: Create data dictionary
        logger.info("Creating data dictionary...")
        results['data_dictionary'] = self.create_data_dictionary()
        
        results['status'] = 'completed'
        
        # Save results
        self.save_results(results)
        
        return results
        
    def save_results(self, results: Dict):
        """Save exploration results to files"""
        output_dir = self.base_dir / 'analysis_results'
        output_dir.mkdir(exist_ok=True)
        
        # Save as JSON
        json_file = output_dir / f'exploration_results_{self.sample_year}q{self.sample_quarter}.json'
        with open(json_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f"Results saved to {json_file}")
        
        # Save summary report as markdown
        self.generate_markdown_report(results, output_dir)
        
        # Save sample data as Excel for easy viewing
        self.save_sample_data_excel(output_dir)
        
    def generate_markdown_report(self, results: Dict, output_dir: Path):
        """Generate a human-readable markdown report"""
        report_file = output_dir / f'exploration_report_{self.sample_year}q{self.sample_quarter}.md'
        
        with open(report_file, 'w') as f:
            f.write(f"# SEC Financial Statement Data Exploration Report\n\n")
            f.write(f"**Dataset:** {self.sample_file}\n")
            f.write(f"**Exploration Date:** {results['exploration_date']}\n\n")
            
            f.write("## Table Overview\n\n")
            f.write("| Table | Rows | Columns | Description |\n")
            f.write("|-------|------|---------|-------------|\n")
            
            for table_name, analysis in results.get('table_analysis', {}).items():
                desc = self.get_table_description(table_name)
                f.write(f"| {table_name} | {analysis['row_count']:,} | {analysis['column_count']} | {desc} |\n")
                
            f.write("\n## Key Findings\n\n")
            
            patterns = results.get('data_patterns', {})
            
            if 'filing_types' in patterns:
                f.write("### Filing Types Distribution\n")
                for form_type, count in list(patterns['filing_types'].items())[:10]:
                    f.write(f"- {form_type}: {count:,} filings\n")
                f.write("\n")
                
            if 'company_info' in patterns:
                f.write("### Company Information\n")
                f.write(f"- Total unique companies: {patterns['company_info'].get('total_companies', 'N/A'):,}\n")
                f.write("\n")
                
            if 'tag_categories' in patterns:
                f.write("### XBRL Tag Statistics\n")
                f.write(f"- Total unique tags: {patterns['tag_categories'].get('total_tags', 'N/A'):,}\n")
                f.write("\n")
                
            f.write("## Table Relationships\n\n")
            relationships = results.get('relationships', {})
            
            if relationships.get('primary_keys'):
                f.write("### Primary Keys\n")
                for table, key in relationships['primary_keys'].items():
                    f.write(f"- {table}: {key}\n")
                f.write("\n")
                
            if relationships.get('foreign_keys'):
                f.write("### Foreign Key Relationships\n")
                for fk in relationships['foreign_keys']:
                    f.write(f"- {fk['from_table']}.{fk['from_column']} → {fk['to_table']}.{fk['to_column']}\n")
                    
        logger.info(f"Markdown report saved to {report_file}")
        
    def save_sample_data_excel(self, output_dir: Path):
        """Save sample data to Excel for manual inspection"""
        excel_file = output_dir / f'sample_data_{self.sample_year}q{self.sample_quarter}.xlsx'
        
        with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
            for table_name, df in self.dataframes.items():
                # Save first 1000 rows of each table
                df.head(1000).to_excel(writer, sheet_name=table_name, index=False)
                
        logger.info(f"Sample data saved to {excel_file}")

def main():
    """Main execution"""
    import sys
    
    # Determine year and quarter to explore
    if len(sys.argv) > 2:
        year = int(sys.argv[1])
        quarter = int(sys.argv[2])
    else:
        # Default to a recent quarter
        year = 2024
        quarter = 2
        
    logger.info(f"Exploring SEC data for {year}Q{quarter}")
    
    # Create explorer and run analysis
    explorer = SECDataExplorer(sample_year=year, sample_quarter=quarter)
    results = explorer.run_full_exploration()
    
    # Print summary
    print("\n" + "="*60)
    print("SEC DATA EXPLORATION COMPLETE")
    print("="*60)
    
    if results['status'] == 'completed':
        print(f"\nDataset: {year}Q{quarter}")
        print("\nTables Found:")
        for table_name, analysis in results['table_analysis'].items():
            print(f"  - {table_name}: {analysis['row_count']:,} rows, {analysis['column_count']} columns")
            
        patterns = results.get('data_patterns', {})
        if patterns.get('company_info'):
            print(f"\nTotal Companies: {patterns['company_info'].get('total_companies', 'N/A'):,}")
            
        if patterns.get('tag_categories'):
            print(f"Total XBRL Tags: {patterns['tag_categories'].get('total_tags', 'N/A'):,}")
            
        print(f"\nResults saved to: {explorer.base_dir / 'analysis_results'}")
        
        # Print a few sample queries
        print("\n" + "="*60)
        print("SAMPLE SQL QUERIES")
        print("="*60)
        for query in results.get('sample_queries', [])[:2]:
            print(f"\n{query['name']}:")
            print(f"{query['description']}")
            print("-" * 40)
            print(query['sql'][:500] + "..." if len(query['sql']) > 500 else query['sql'])
    else:
        print(f"Exploration failed with status: {results['status']}")

if __name__ == "__main__":
    main()