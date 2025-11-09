"""
SEC Financial Statement Data Sets Downloader and Processor
===========================================================
A comprehensive strategy for downloading and processing SEC Financial Statement Data Sets

Author: Faliang
Date: November 2025
"""

import os
import requests
import zipfile
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import logging
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from dataclasses import dataclass
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Float, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

Base = declarative_base()

# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class DatasetInfo:
    """Information about a Financial Statement dataset"""
    year: int
    quarter: int
    filename: str
    url: str
    download_date: Optional[datetime] = None
    file_hash: Optional[str] = None
    status: str = 'pending'
    
class DatasetMetadata(Base):
    """SQLAlchemy model for tracking dataset metadata"""
    __tablename__ = 'dataset_metadata'
    
    id = Column(Integer, primary_key=True)
    year = Column(Integer, nullable=False)
    quarter = Column(Integer, nullable=False)
    filename = Column(String(100), nullable=False)
    url = Column(String(500), nullable=False)
    download_date = Column(DateTime)
    file_hash = Column(String(64))
    file_size = Column(Integer)
    status = Column(String(20))
    processing_date = Column(DateTime)
    error_message = Column(Text)
    
    __table_args__ = (
        Index('idx_year_quarter', 'year', 'quarter'),
    )

# ============================================================================
# CONFIGURATION
# ============================================================================

class SECDataConfig:
    """Configuration for SEC data downloads"""
    
    # Base URLs for different data types
    BASE_URLS = {
        'financial_statement': 'https://www.sec.gov/files/dera/data/financial-statement-data-sets/',
        'financial_statement_notes': 'https://www.sec.gov/files/dera/data/financial-statement-and-notes-data-sets/',
        'archive': 'https://www.sec.gov/files/dera/data/financial-statement-data-sets-archive/'
    }
    
    # Local storage configuration
    BASE_DIR = Path.home() / 'sec_data'
    DOWNLOAD_DIR = BASE_DIR / 'downloads'
    EXTRACTED_DIR = BASE_DIR / 'extracted'
    PARQUET_DIR = BASE_DIR / 'parquet'
    DB_DIR = BASE_DIR / 'database'
    
    # Download settings
    USER_AGENT = 'Your Company Name (your.email@example.com)'
    MAX_RETRIES = 3
    RETRY_DELAY = 5  # seconds
    CONCURRENT_DOWNLOADS = 3
    CHUNK_SIZE = 8192  # bytes
    
    # Rate limiting (SEC allows 10 requests/second)
    RATE_LIMIT_DELAY = 0.11  # seconds between requests
    
    @classmethod
    def init_directories(cls):
        """Create necessary directories if they don't exist"""
        for dir_path in [cls.DOWNLOAD_DIR, cls.EXTRACTED_DIR, cls.PARQUET_DIR, cls.DB_DIR]:
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Directory ensured: {dir_path}")

# ============================================================================
# DOWNLOAD STRATEGY
# ============================================================================

class SECDataDownloader:
    """Handles downloading of SEC Financial Statement Data Sets"""
    
    def __init__(self, config: SECDataConfig = None):
        self.config = config or SECDataConfig()
        self.config.init_directories()
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.config.USER_AGENT})
        
        # Initialize database
        self.db_path = self.config.DB_DIR / 'sec_data.db'
        self.engine = create_engine(f'sqlite:///{self.db_path}')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        
    def generate_dataset_urls(self, start_year: int = 2009, 
                            end_year: Optional[int] = None,
                            data_type: str = 'financial_statement') -> List[DatasetInfo]:
        """
        Generate URLs for all available datasets
        
        Strategy:
        1. From 2009-2019: Quarterly files (YYYY'q'Q.zip)
        2. From 2020 onwards: Monthly files might be available
        3. Handle both patterns
        """
        if end_year is None:
            end_year = datetime.now().year
            
        datasets = []
        base_url = self.config.BASE_URLS.get(data_type, self.config.BASE_URLS['financial_statement'])
        
        for year in range(start_year, end_year + 1):
            # Determine quarters to check based on current date
            if year == datetime.now().year:
                max_quarter = (datetime.now().month - 1) // 3 + 1
            else:
                max_quarter = 4
                
            for quarter in range(1, max_quarter + 1):
                filename = f"{year}q{quarter}.zip"
                url = base_url + filename
                
                datasets.append(DatasetInfo(
                    year=year,
                    quarter=quarter,
                    filename=filename,
                    url=url
                ))
                
        logger.info(f"Generated {len(datasets)} dataset URLs from {start_year} to {end_year}")
        return datasets
    
    def check_dataset_exists(self, dataset: DatasetInfo) -> bool:
        """Check if dataset has already been downloaded and is valid"""
        file_path = self.config.DOWNLOAD_DIR / dataset.filename
        
        if not file_path.exists():
            return False
            
        # Check file integrity using hash
        db_session = self.Session()
        try:
            record = db_session.query(DatasetMetadata).filter_by(
                year=dataset.year, 
                quarter=dataset.quarter
            ).first()
            
            if record and record.file_hash:
                current_hash = self.calculate_file_hash(file_path)
                return current_hash == record.file_hash
                
        finally:
            db_session.close()
            
        return False
    
    def calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def download_dataset(self, dataset: DatasetInfo, force: bool = False) -> bool:
        """
        Download a single dataset with retry logic
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not force and self.check_dataset_exists(dataset):
            logger.info(f"Dataset {dataset.filename} already exists and is valid")
            return True
            
        file_path = self.config.DOWNLOAD_DIR / dataset.filename
        
        for attempt in range(self.config.MAX_RETRIES):
            try:
                logger.info(f"Downloading {dataset.filename} (attempt {attempt + 1})")
                
                # Rate limiting
                time.sleep(self.config.RATE_LIMIT_DELAY)
                
                response = self.session.get(dataset.url, stream=True, timeout=30)
                
                if response.status_code == 404:
                    logger.warning(f"Dataset {dataset.filename} not found (404)")
                    return False
                    
                response.raise_for_status()
                
                # Download with progress tracking
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=self.config.CHUNK_SIZE):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            if total_size > 0:
                                progress = (downloaded / total_size) * 100
                                if downloaded % (self.config.CHUNK_SIZE * 100) == 0:
                                    logger.debug(f"Progress: {progress:.1f}%")
                
                # Calculate hash and save metadata
                file_hash = self.calculate_file_hash(file_path)
                self.save_metadata(dataset, file_hash, file_path.stat().st_size)
                
                logger.info(f"Successfully downloaded {dataset.filename}")
                return True
                
            except Exception as e:
                logger.error(f"Error downloading {dataset.filename}: {e}")
                if attempt < self.config.MAX_RETRIES - 1:
                    time.sleep(self.config.RETRY_DELAY)
                else:
                    self.save_error(dataset, str(e))
                    return False
                    
    def save_metadata(self, dataset: DatasetInfo, file_hash: str, file_size: int):
        """Save dataset metadata to database"""
        db_session = self.Session()
        try:
            record = db_session.query(DatasetMetadata).filter_by(
                year=dataset.year,
                quarter=dataset.quarter
            ).first()
            
            if not record:
                record = DatasetMetadata()
                record.year = dataset.year
                record.quarter = dataset.quarter
                
            record.filename = dataset.filename
            record.url = dataset.url
            record.download_date = datetime.now()
            record.file_hash = file_hash
            record.file_size = file_size
            record.status = 'downloaded'
            
            db_session.add(record)
            db_session.commit()
            
        finally:
            db_session.close()
            
    def save_error(self, dataset: DatasetInfo, error_message: str):
        """Save error information to database"""
        db_session = self.Session()
        try:
            record = db_session.query(DatasetMetadata).filter_by(
                year=dataset.year,
                quarter=dataset.quarter
            ).first()
            
            if not record:
                record = DatasetMetadata()
                record.year = dataset.year
                record.quarter = dataset.quarter
                record.filename = dataset.filename
                record.url = dataset.url
                
            record.status = 'error'
            record.error_message = error_message
            
            db_session.add(record)
            db_session.commit()
            
        finally:
            db_session.close()
    
    def download_all_datasets(self, datasets: List[DatasetInfo], 
                            concurrent: bool = True) -> Dict[str, int]:
        """
        Download all datasets with optional concurrent downloads
        
        Returns:
            Dict with counts of successful and failed downloads
        """
        results = {'success': 0, 'failed': 0, 'skipped': 0}
        
        if concurrent:
            with ThreadPoolExecutor(max_workers=self.config.CONCURRENT_DOWNLOADS) as executor:
                future_to_dataset = {
                    executor.submit(self.download_dataset, dataset): dataset 
                    for dataset in datasets
                }
                
                for future in as_completed(future_to_dataset):
                    dataset = future_to_dataset[future]
                    try:
                        success = future.result()
                        if success:
                            results['success'] += 1
                        else:
                            results['failed'] += 1
                    except Exception as e:
                        logger.error(f"Exception for {dataset.filename}: {e}")
                        results['failed'] += 1
        else:
            for dataset in datasets:
                if self.download_dataset(dataset):
                    results['success'] += 1
                else:
                    results['failed'] += 1
                    
        logger.info(f"Download complete: {results}")
        return results

# ============================================================================
# DATA PROCESSING STRATEGY
# ============================================================================

class SECDataProcessor:
    """Processes downloaded SEC Financial Statement Data Sets"""
    
    def __init__(self, config: SECDataConfig = None):
        self.config = config or SECDataConfig()
        self.table_names = ['sub', 'tag', 'num', 'txt', 'ren', 'pre', 'cal', 'dim']
        
    def extract_dataset(self, filename: str) -> Dict[str, pd.DataFrame]:
        """
        Extract a single dataset ZIP file
        
        Returns:
            Dictionary of DataFrames, one for each table
        """
        file_path = self.config.DOWNLOAD_DIR / filename
        extract_path = self.config.EXTRACTED_DIR / filename.replace('.zip', '')
        
        if not file_path.exists():
            raise FileNotFoundError(f"Dataset {filename} not found")
            
        extract_path.mkdir(parents=True, exist_ok=True)
        
        dataframes = {}
        
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
                
            # Load each table
            for table_name in self.table_names:
                table_file = extract_path / f"{table_name}.txt"
                if table_file.exists():
                    logger.info(f"Loading {table_name}.txt from {filename}")
                    
                    # Use appropriate dtypes to optimize memory
                    if table_name == 'num':
                        # Numerical data table
                        df = pd.read_csv(table_file, sep='\t', 
                                       dtype={'adsh': 'str', 'tag': 'str', 
                                             'version': 'str', 'ddate': 'str'})
                    elif table_name == 'sub':
                        # Submission data
                        df = pd.read_csv(table_file, sep='\t',
                                       dtype={'adsh': 'str', 'cik': 'str',
                                             'name': 'str', 'sic': 'str'})
                    else:
                        # Other tables
                        df = pd.read_csv(table_file, sep='\t', low_memory=False)
                        
                    dataframes[table_name] = df
                    logger.info(f"Loaded {table_name}: {len(df)} rows")
                    
        except Exception as e:
            logger.error(f"Error extracting {filename}: {e}")
            raise
            
        return dataframes
    
    def convert_to_parquet(self, filename: str) -> bool:
        """
        Convert extracted CSV files to Parquet format for better performance
        
        Returns:
            bool: True if successful
        """
        try:
            dataframes = self.extract_dataset(filename)
            
            parquet_dir = self.config.PARQUET_DIR / filename.replace('.zip', '')
            parquet_dir.mkdir(parents=True, exist_ok=True)
            
            for table_name, df in dataframes.items():
                parquet_file = parquet_dir / f"{table_name}.parquet"
                df.to_parquet(parquet_file, compression='snappy', index=False)
                logger.info(f"Saved {table_name} to Parquet: {parquet_file}")
                
            return True
            
        except Exception as e:
            logger.error(f"Error converting {filename} to Parquet: {e}")
            return False
    
    def load_parquet_table(self, year: int, quarter: int, table: str) -> pd.DataFrame:
        """
        Load a specific table from Parquet files
        
        Args:
            year: Year of the dataset
            quarter: Quarter of the dataset
            table: Table name (sub, tag, num, txt, ren, pre, cal, dim)
            
        Returns:
            DataFrame containing the requested data
        """
        parquet_file = self.config.PARQUET_DIR / f"{year}q{quarter}" / f"{table}.parquet"
        
        if not parquet_file.exists():
            # Try to create it from ZIP file
            filename = f"{year}q{quarter}.zip"
            if (self.config.DOWNLOAD_DIR / filename).exists():
                logger.info(f"Creating Parquet files for {filename}")
                if not self.convert_to_parquet(filename):
                    raise FileNotFoundError(f"Could not create Parquet for {filename}")
            else:
                raise FileNotFoundError(f"Dataset {year}q{quarter} not available")
                
        return pd.read_parquet(parquet_file)
    
    def query_financial_data(self, cik: str, 
                           start_year: int = 2020,
                           end_year: Optional[int] = None) -> pd.DataFrame:
        """
        Query financial data for a specific company across multiple periods
        
        Args:
            cik: Central Index Key of the company
            start_year: Starting year
            end_year: Ending year (None for current year)
            
        Returns:
            Consolidated DataFrame with financial data
        """
        if end_year is None:
            end_year = datetime.now().year
            
        all_data = []
        
        for year in range(start_year, end_year + 1):
            max_quarter = 4 if year < datetime.now().year else (datetime.now().month - 1) // 3 + 1
            
            for quarter in range(1, max_quarter + 1):
                try:
                    # Load submission data
                    sub_df = self.load_parquet_table(year, quarter, 'sub')
                    
                    # Filter for specific CIK
                    cik_padded = cik.zfill(10)  # CIK should be 10 digits with leading zeros
                    company_subs = sub_df[sub_df['cik'] == cik_padded]
                    
                    if company_subs.empty:
                        continue
                        
                    # Load numerical data
                    num_df = self.load_parquet_table(year, quarter, 'num')
                    
                    # Join with submission data
                    for adsh in company_subs['adsh'].unique():
                        company_data = num_df[num_df['adsh'] == adsh].copy()
                        if not company_data.empty:
                            company_data['year'] = year
                            company_data['quarter'] = quarter
                            company_data['company_name'] = company_subs[company_subs['adsh'] == adsh]['name'].iloc[0]
                            all_data.append(company_data)
                            
                except FileNotFoundError:
                    logger.warning(f"Data not available for {year}Q{quarter}")
                    continue
                    
        if all_data:
            return pd.concat(all_data, ignore_index=True)
        else:
            return pd.DataFrame()

# ============================================================================
# INCREMENTAL UPDATE STRATEGY
# ============================================================================

class SECDataUpdater:
    """Handles incremental updates of SEC data"""
    
    def __init__(self, downloader: SECDataDownloader, processor: SECDataProcessor):
        self.downloader = downloader
        self.processor = processor
        
    def check_for_updates(self) -> List[DatasetInfo]:
        """
        Check for new datasets that need to be downloaded
        
        Returns:
            List of datasets that need updating
        """
        current_year = datetime.now().year
        current_quarter = (datetime.now().month - 1) // 3 + 1
        
        # Get list of all expected datasets
        all_datasets = self.downloader.generate_dataset_urls(
            start_year=current_year - 2,  # Check last 2 years
            end_year=current_year
        )
        
        # Check which ones are missing or outdated
        updates_needed = []
        
        for dataset in all_datasets:
            if not self.downloader.check_dataset_exists(dataset):
                updates_needed.append(dataset)
                
        logger.info(f"Found {len(updates_needed)} datasets needing updates")
        return updates_needed
    
    def perform_update(self) -> Dict[str, int]:
        """
        Perform incremental update of SEC data
        
        Returns:
            Statistics about the update
        """
        updates_needed = self.check_for_updates()
        
        if not updates_needed:
            logger.info("No updates needed")
            return {'success': 0, 'failed': 0}
            
        # Download new datasets
        results = self.downloader.download_all_datasets(updates_needed)
        
        # Convert successful downloads to Parquet
        for dataset in updates_needed:
            if self.downloader.check_dataset_exists(dataset):
                self.processor.convert_to_parquet(dataset.filename)
                
        return results

# ============================================================================
# MAIN EXECUTION STRATEGY
# ============================================================================

def main():
    """
    Main execution strategy for SEC Financial Statement Data management
    """
    
    # Initialize configuration
    config = SECDataConfig()
    config.USER_AGENT = 'Faliang Financial Data Systems (faliang@example.com)'  # Update this
    
    # Initialize components
    downloader = SECDataDownloader(config)
    processor = SECDataProcessor(config)
    updater = SECDataUpdater(downloader, processor)
    
    # Strategy 1: Initial bulk download (run once)
    def initial_setup():
        """Perform initial bulk download of all historical data"""
        logger.info("Starting initial bulk download...")
        
        # Generate URLs for all historical data
        datasets = downloader.generate_dataset_urls(
            start_year=2009,
            end_year=datetime.now().year
        )
        
        # Download all datasets
        results = downloader.download_all_datasets(datasets, concurrent=True)
        logger.info(f"Initial download complete: {results}")
        
        # Convert all to Parquet
        for dataset in datasets:
            if downloader.check_dataset_exists(dataset):
                processor.convert_to_parquet(dataset.filename)
                
    # Strategy 2: Incremental updates (run daily/weekly)
    def incremental_update():
        """Perform incremental update for new data"""
        logger.info("Checking for updates...")
        results = updater.perform_update()
        logger.info(f"Update complete: {results}")
        
    # Strategy 3: Query specific company data
    def query_company_data(cik: str, company_name: str):
        """Query and analyze data for a specific company"""
        logger.info(f"Querying data for {company_name} (CIK: {cik})")
        
        df = processor.query_financial_data(
            cik=cik,
            start_year=2020,
            end_year=2024
        )
        
        if not df.empty:
            # Example analysis
            logger.info(f"Found {len(df)} data points")
            
            # Group by tag and period
            summary = df.groupby(['tag', 'year', 'quarter'])['value'].first().unstack(level=[1, 2])
            print(summary.head(20))
            
            # Save to Excel for analysis
            output_file = config.BASE_DIR / f"{company_name}_financial_data.xlsx"
            with pd.ExcelWriter(output_file) as writer:
                df.to_excel(writer, sheet_name='Raw Data', index=False)
                summary.to_excel(writer, sheet_name='Summary')
            logger.info(f"Data saved to {output_file}")
        else:
            logger.warning(f"No data found for {company_name}")
    
    # Execute based on command line arguments or configuration
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'init':
            initial_setup()
        elif command == 'update':
            incremental_update()
        elif command == 'query' and len(sys.argv) > 3:
            cik = sys.argv[2]
            company_name = sys.argv[3] if len(sys.argv) > 3 else f"CIK_{cik}"
            query_company_data(cik, company_name)
        else:
            print("Usage:")
            print("  python sec_downloader.py init     # Initial bulk download")
            print("  python sec_downloader.py update   # Incremental update")
            print("  python sec_downloader.py query CIK 'Company Name'  # Query company data")
    else:
        # Default: check for updates
        incremental_update()

if __name__ == "__main__":
    main()