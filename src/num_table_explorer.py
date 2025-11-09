"""
SEC NUM Table Deep Explorer
============================
Focused exploration of the NUM.txt file which contains all numerical financial data.
This is the most important table for financial analysis.

Author: Faliang
Date: November 2025
"""

import os
import requests
import zipfile
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
from datetime import datetime
import logging
from collections import Counter, defaultdict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NUMTableExplorer:
    """
    Deep exploration of the NUM table structure and contents
    """
    
    def __init__(self, year: int = 2024, quarter: int = 2):
        self.year = year
        self.quarter = quarter
        self.base_dir = Path.home() / 'sec_num_exploration'
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        self.zip_file = f"{year}q{quarter}.zip"
        self.url = f"https://www.sec.gov/files/dera/data/financial-statement-data-sets/{self.zip_file}"
        
        # We'll focus on these key financial tags
        self.key_financial_tags = [
            'Assets', 'AssetsCurrent', 'AssetsNoncurrent',
            'Liabilities', 'LiabilitiesCurrent', 'LiabilitiesNoncurrent',
            'StockholdersEquity', 'RetainedEarningsAccumulatedDeficit',
            'Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax',
            'CostOfGoodsAndServicesSold', 'GrossProfit',
            'OperatingIncomeLoss', 'NetIncomeLoss',
            'EarningsPerShareBasic', 'EarningsPerShareDiluted',
            'CashAndCashEquivalentsAtCarryingValue',
            'OperatingCashFlow', 'InvestingCashFlow', 'FinancingCashFlow'
        ]
        
    def download_and_extract(self) -> bool:
        """Download and extract only the NUM.txt file"""
        zip_path = self.base_dir / self.zip_file
        
        # Download if needed
        if not zip_path.exists():
            logger.info(f"Downloading {self.zip_file}...")
            headers = {'User-Agent': 'Financial Data Research (research@example.com)'}
            response = requests.get(self.url, headers=headers, stream=True)
            response.raise_for_status()
            
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logger.info("Download complete")
        
        # Extract only NUM.txt
        logger.info("Extracting NUM.txt...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extract('num.txt', self.base_dir)
        
        return True
    
    def explore_num_structure(self) -> Dict:
        """Deeply explore the NUM table structure"""
        num_file = self.base_dir / 'num.txt'
        
        # First, read just the header to understand columns
        logger.info("Reading NUM table header...")
        with open(num_file, 'r') as f:
            header = f.readline().strip()
        
        columns = header.split('\t')
        logger.info(f"NUM table has {len(columns)} columns: {columns}")
        
        # Read a sample to understand data
        logger.info("Loading NUM data sample (first 500,000 rows)...")
        df = pd.read_csv(num_file, sep='\t', nrows=500000, low_memory=False)
        
        analysis = {
            'basic_info': {
                'columns': columns,
                'column_count': len(columns),
                'sample_rows': len(df),
                'estimated_total_rows': self._estimate_total_rows(num_file),
                'file_size_mb': os.path.getsize(num_file) / (1024 * 1024)
            },
            'columns_analysis': {},
            'financial_tags': {},
            'value_analysis': {},
            'relationships': {},
            'data_patterns': {}
        }
        
        # Analyze each column
        for col in df.columns:
            col_analysis = {
                'dtype': str(df[col].dtype),
                'null_count': df[col].isna().sum(),
                'null_percentage': (df[col].isna().sum() / len(df)) * 100,
                'unique_values': df[col].nunique(),
                'sample_values': df[col].dropna().head(10).tolist()
            }
            
            # Special analysis for key columns
            if col == 'tag':
                col_analysis['top_tags'] = df[col].value_counts().head(20).to_dict()
                col_analysis['tag_examples'] = self._categorize_tags(df[col].unique()[:100])
                
            elif col == 'value':
                col_analysis['statistics'] = {
                    'min': float(df[col].min()),
                    'max': float(df[col].max()),
                    'mean': float(df[col].mean()),
                    'median': float(df[col].median()),
                    'std': float(df[col].std()),
                    'negative_count': (df[col] < 0).sum(),
                    'zero_count': (df[col] == 0).sum(),
                    'positive_count': (df[col] > 0).sum()
                }
                
            elif col == 'uom':  # Unit of measure
                col_analysis['units'] = df[col].value_counts().to_dict()
                
            elif col == 'qtrs':  # Quarters
                col_analysis['distribution'] = df[col].value_counts().to_dict()
                
            elif col == 'ddate':  # Date
                try:
                    dates = pd.to_datetime(df[col], format='%Y%m%d', errors='coerce')
                    col_analysis['date_range'] = {
                        'min': str(dates.min()),
                        'max': str(dates.max()),
                        'unique_dates': dates.nunique()
                    }
                except:
                    pass
            
            analysis['columns_analysis'][col] = col_analysis
        
        # Analyze key financial tags
        logger.info("Analyzing key financial tags...")
        for tag in self.key_financial_tags:
            tag_data = df[df['tag'] == tag]
            if len(tag_data) > 0:
                analysis['financial_tags'][tag] = {
                    'count': len(tag_data),
                    'companies': tag_data['adsh'].nunique(),
                    'value_range': {
                        'min': float(tag_data['value'].min()),
                        'max': float(tag_data['value'].max()),
                        'median': float(tag_data['value'].median())
                    },
                    'units': tag_data['uom'].value_counts().to_dict(),
                    'quarters': tag_data['qtrs'].value_counts().to_dict() if 'qtrs' in tag_data else {}
                }
        
        # Understand relationships
        logger.info("Analyzing data relationships...")
        analysis['relationships'] = self._analyze_relationships(df)
        
        # Identify data patterns
        logger.info("Identifying data patterns...")
        analysis['data_patterns'] = self._identify_patterns(df)
        
        return analysis
    
    def _estimate_total_rows(self, file_path: Path) -> int:
        """Estimate total rows without reading entire file"""
        # Read first 1000 lines to estimate average line size
        with open(file_path, 'rb') as f:
            sample = f.read(100000)  # Read 100KB
            lines_in_sample = sample.count(b'\n')
        
        file_size = os.path.getsize(file_path)
        estimated_rows = int((file_size / 100000) * lines_in_sample)
        return estimated_rows
    
    def _categorize_tags(self, tags: List[str]) -> Dict:
        """Categorize tags by financial statement type"""
        categories = {
            'balance_sheet': [],
            'income_statement': [],
            'cash_flow': [],
            'equity': [],
            'other': []
        }
        
        for tag in tags:
            tag_lower = tag.lower()
            if any(x in tag_lower for x in ['asset', 'liabilit', 'receivable', 'payable', 'inventory']):
                categories['balance_sheet'].append(tag)
            elif any(x in tag_lower for x in ['revenue', 'expense', 'income', 'cost', 'sales', 'profit']):
                categories['income_statement'].append(tag)
            elif any(x in tag_lower for x in ['cash', 'flow']):
                categories['cash_flow'].append(tag)
            elif any(x in tag_lower for x in ['equity', 'stock', 'retained', 'dividend']):
                categories['equity'].append(tag)
            else:
                categories['other'].append(tag)
        
        return {k: v[:10] for k, v in categories.items()}  # Return first 10 of each
    
    def _analyze_relationships(self, df: pd.DataFrame) -> Dict:
        """Analyze relationships between columns"""
        relationships = {}
        
        # Check if adsh is a foreign key
        if 'adsh' in df.columns:
            relationships['adsh_uniqueness'] = {
                'unique_values': df['adsh'].nunique(),
                'is_unique': df['adsh'].nunique() == len(df),
                'avg_records_per_adsh': len(df) / df['adsh'].nunique()
            }
        
        # Check composite keys
        if all(col in df.columns for col in ['adsh', 'tag', 'ddate']):
            composite = df.groupby(['adsh', 'tag', 'ddate']).size()
            relationships['composite_key'] = {
                'adsh_tag_ddate_unique': len(composite) == len(df),
                'duplicate_count': (composite > 1).sum()
            }
        
        # Check tag-value relationships
        if 'tag' in df.columns and 'value' in df.columns:
            # Find tags that are always positive/negative
            tag_signs = df.groupby('tag')['value'].agg(['min', 'max'])
            always_positive = tag_signs[(tag_signs['min'] >= 0)].index.tolist()[:10]
            always_negative = tag_signs[(tag_signs['max'] <= 0)].index.tolist()[:10]
            can_be_both = tag_signs[(tag_signs['min'] < 0) & (tag_signs['max'] > 0)].index.tolist()[:10]
            
            relationships['tag_value_signs'] = {
                'always_positive_tags': always_positive,
                'always_negative_tags': always_negative,
                'can_be_both': can_be_both
            }
        
        return relationships
    
    def _identify_patterns(self, df: pd.DataFrame) -> Dict:
        """Identify important patterns in the data"""
        patterns = {}
        
        # Filing patterns
        if 'adsh' in df.columns:
            records_per_filing = df.groupby('adsh').size()
            patterns['records_per_filing'] = {
                'min': int(records_per_filing.min()),
                'max': int(records_per_filing.max()),
                'mean': float(records_per_filing.mean()),
                'median': float(records_per_filing.median())
            }
        
        # Date patterns
        if 'ddate' in df.columns:
            try:
                dates = pd.to_datetime(df['ddate'], format='%Y%m%d', errors='coerce')
                patterns['reporting_dates'] = {
                    'most_common_days': dates.dt.day.value_counts().head(5).to_dict(),
                    'most_common_months': dates.dt.month.value_counts().to_dict()
                }
            except:
                pass
        
        # Value patterns
        if 'value' in df.columns:
            # Identify likely scales (thousands, millions)
            value_mods = df['value'].abs() % 1000
            patterns['value_scales'] = {
                'likely_in_thousands': (value_mods == 0).sum() / len(df),
                'decimal_places': df['value'].apply(lambda x: len(str(x).split('.')[-1]) if '.' in str(x) else 0).value_counts().head().to_dict()
            }
        
        # Quarter patterns
        if 'qtrs' in df.columns:
            patterns['quarter_types'] = {
                'instant_values': (df['qtrs'] == 0).sum(),
                'quarterly_values': (df['qtrs'] == 1).sum(),
                'semi_annual_values': (df['qtrs'] == 2).sum(),
                'nine_month_values': (df['qtrs'] == 3).sum(),
                'annual_values': (df['qtrs'] == 4).sum()
            }
        
        return patterns
    
    def create_sample_queries(self, analysis: Dict) -> List[Dict]:
        """Create sample queries based on discovered structure"""
        queries = []
        
        # Get actual column names from analysis
        columns = analysis['basic_info']['columns']
        
        queries.append({
            'name': 'Extract Balance Sheet for a Company',
            'description': 'Get all balance sheet items for a specific filing',
            'pseudo_sql': f"""
                SELECT {', '.join(columns[:6])}
                FROM num
                WHERE adsh = 'SPECIFIC_ADSH'
                  AND tag IN ('Assets', 'Liabilities', 'StockholdersEquity')
                  AND qtrs = 0  -- Point in time values
                ORDER BY tag;
            """
        })
        
        queries.append({
            'name': 'Revenue Time Series',
            'description': 'Track revenue over time for a company',
            'pseudo_sql': f"""
                SELECT adsh, tag, ddate, value, uom
                FROM num
                WHERE tag LIKE '%Revenue%'
                  AND qtrs = 1  -- Quarterly values
                ORDER BY ddate;
            """
        })
        
        queries.append({
            'name': 'Find Large Companies',
            'description': 'Identify companies with assets over $1 billion',
            'pseudo_sql': f"""
                SELECT DISTINCT adsh, value
                FROM num
                WHERE tag = 'Assets'
                  AND value > 1000000000
                  AND uom = 'USD'
                ORDER BY value DESC;
            """
        })
        
        return queries
    
    def generate_report(self, analysis: Dict) -> str:
        """Generate a comprehensive report"""
        report = []
        report.append(f"# NUM Table Structure Analysis Report")
        report.append(f"**Dataset**: {self.year}Q{self.quarter}")
        report.append(f"**Analysis Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        report.append("")
        
        # Basic Information
        report.append("## Basic Information")
        basic = analysis['basic_info']
        report.append(f"- **Columns**: {basic['column_count']}")
        report.append(f"- **Sample Rows Analyzed**: {basic['sample_rows']:,}")
        report.append(f"- **Estimated Total Rows**: {basic['estimated_total_rows']:,}")
        report.append(f"- **File Size**: {basic['file_size_mb']:.2f} MB")
        report.append("")
        
        # Column List
        report.append("## Column Structure")
        report.append("| Column | Type | Nulls % | Unique Values | Description |")
        report.append("|--------|------|---------|---------------|-------------|")
        
        for col, info in analysis['columns_analysis'].items():
            desc = self._get_column_description(col)
            report.append(f"| {col} | {info['dtype']} | {info['null_percentage']:.1f}% | {info['unique_values']:,} | {desc} |")
        
        report.append("")
        
        # Key Financial Tags
        report.append("## Key Financial Tags Found")
        for tag, info in analysis['financial_tags'].items():
            report.append(f"\n### {tag}")
            report.append(f"- **Occurrences**: {info['count']:,}")
            report.append(f"- **Companies**: {info['companies']:,}")
            report.append(f"- **Value Range**: ${info['value_range']['min']:,.0f} to ${info['value_range']['max']:,.0f}")
            report.append(f"- **Units**: {', '.join(info['units'].keys())}")
        
        report.append("")
        
        # Data Patterns
        report.append("## Data Patterns Discovered")
        patterns = analysis.get('data_patterns', {})
        
        if 'records_per_filing' in patterns:
            rpf = patterns['records_per_filing']
            report.append(f"\n### Records per Filing")
            report.append(f"- Average: {rpf['mean']:.0f} records")
            report.append(f"- Range: {rpf['min']} to {rpf['max']} records")
        
        if 'quarter_types' in patterns:
            qt = patterns['quarter_types']
            report.append(f"\n### Time Period Types")
            report.append(f"- Point-in-time values: {qt.get('instant_values', 0):,}")
            report.append(f"- Quarterly values: {qt.get('quarterly_values', 0):,}")
            report.append(f"- Annual values: {qt.get('annual_values', 0):,}")
        
        return '\n'.join(report)
    
    def _get_column_description(self, col: str) -> str:
        """Get description for a column based on common patterns"""
        descriptions = {
            'adsh': 'Accession number (filing ID)',
            'tag': 'XBRL tag name',
            'version': 'Taxonomy version',
            'coreg': 'Co-registrant',
            'ddate': 'End date (YYYYMMDD)',
            'qtrs': 'Quarters (0=instant, 1-4=duration)',
            'uom': 'Unit of measure',
            'value': 'Numerical value',
            'footnote': 'Footnote reference',
            'name': 'Company name',
            'sic': 'SIC code',
            'report': 'Report number',
            'line': 'Line number',
            'stmt': 'Statement type',
            'inpth': 'In presentation',
            'rfile': 'Report file',
            'plabel': 'Preferred label',
            'negating': 'Negating flag'
        }
        return descriptions.get(col, 'TBD')
    
    def run_exploration(self) -> Dict:
        """Run complete NUM table exploration"""
        logger.info(f"Starting NUM table exploration for {self.year}Q{self.quarter}")
        
        # Download and extract
        if not self.download_and_extract():
            return {'error': 'Failed to download/extract data'}
        
        # Explore structure
        analysis = self.explore_num_structure()
        
        # Add sample queries
        analysis['sample_queries'] = self.create_sample_queries(analysis)
        
        # Generate report
        report = self.generate_report(analysis)
        
        # Save results
        output_dir = self.base_dir / 'analysis'
        output_dir.mkdir(exist_ok=True)
        
        # Save JSON
        with open(output_dir / f'num_analysis_{self.year}q{self.quarter}.json', 'w') as f:
            json.dump(analysis, f, indent=2, default=str)
        
        # Save report
        with open(output_dir / f'num_report_{self.year}q{self.quarter}.md', 'w') as f:
            f.write(report)
        
        # Save sample data
        num_file = self.base_dir / 'num.txt'
        df_sample = pd.read_csv(num_file, sep='\t', nrows=10000)
        df_sample.to_excel(output_dir / f'num_sample_{self.year}q{self.quarter}.xlsx', index=False)
        
        logger.info(f"Analysis complete. Results saved to {output_dir}")
        
        # Print summary
        print("\n" + "="*60)
        print("NUM TABLE STRUCTURE DISCOVERED")
        print("="*60)
        print(f"Columns found: {', '.join(analysis['basic_info']['columns'])}")
        print(f"Estimated rows: {analysis['basic_info']['estimated_total_rows']:,}")
        print(f"\nTop 5 most common tags:")
        for tag, count in list(analysis['columns_analysis'].get('tag', {}).get('top_tags', {}).items())[:5]:
            print(f"  - {tag}: {count:,} occurrences")
        print(f"\nKey financial tags found: {len(analysis['financial_tags'])}")
        print(f"\nReports saved to: {output_dir}")
        
        return analysis

def main():
    """Main execution"""
    import sys
    
    # Get year and quarter from arguments or use defaults
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2024
    quarter = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    
    # Run exploration
    explorer = NUMTableExplorer(year, quarter)
    analysis = explorer.run_exploration()
    
    # Print instructions for next steps
    print("\n" + "="*60)
    print("NEXT STEPS")
    print("="*60)
    print("1. Review the generated report: num_report_*.md")
    print("2. Examine the Excel sample: num_sample_*.xlsx")
    print("3. Use the JSON analysis to generate schemas")
    print("4. Test queries with discovered column names")

if __name__ == "__main__":
    main()