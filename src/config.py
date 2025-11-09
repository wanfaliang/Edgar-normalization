"""
Configuration loader for SEC Financial Data Project
Loads settings from .env file and provides typed access to configuration values
"""

import os
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
from dotenv import load_dotenv

# Load .env file
load_dotenv()

@dataclass
class SECConfig:
    """SEC EDGAR specific configuration"""
    user_agent_email: str = os.getenv('SEC_USER_AGENT_EMAIL', 'default@example.com')
    user_agent_company: str = os.getenv('SEC_USER_AGENT_COMPANY', 'Default Company')
    user_agent: str = os.getenv('SEC_USER_AGENT', 'Default Company (default@example.com)')
    rate_limit_requests: int = int(os.getenv('SEC_RATE_LIMIT_REQUESTS_PER_SECOND', '10'))
    rate_limit_delay: float = float(os.getenv('SEC_RATE_LIMIT_DELAY', '0.11'))
    
    # URLs
    base_url: str = os.getenv('SEC_BASE_URL', 'https://www.sec.gov/files/dera/data/')
    financial_statements_url: str = os.getenv('SEC_FINANCIAL_STATEMENTS_URL', 
                                               'https://www.sec.gov/files/dera/data/financial-statement-data-sets/')
    api_base_url: str = os.getenv('SEC_API_BASE_URL', 'https://data.sec.gov/')

@dataclass
class StorageConfig:
    """Local storage configuration with relative path support"""
    
    def __init__(self):
        # Get the project root (where the script is run from)
        self.project_root = Path.cwd()
        
        # Or if you want relative to the config.py file location:
        # self.project_root = Path(__file__).parent
        
        # Build paths from environment variables or defaults
        self.base_dir = self.project_root / Path(os.getenv('DATA_BASE_DIR', 'data/sec_data'))
        self.download_dir = self.project_root / Path(os.getenv('DOWNLOAD_DIR', 'data/sec_data/downloads'))
        self.extracted_dir = self.project_root / Path(os.getenv('EXTRACTED_DIR', 'data/sec_data/extracted'))
        self.parquet_dir = self.project_root / Path(os.getenv('PARQUET_DIR', 'data/sec_data/parquet'))
        self.database_dir = self.project_root / Path(os.getenv('DATABASE_DIR', 'data/sec_data/database'))
        self.logs_dir = self.project_root / Path(os.getenv('LOGS_DIR', 'data/sec_data/logs'))
        self.reports_dir = self.project_root / Path(os.getenv('REPORTS_DIR', 'data/sec_data/reports'))
    
    def create_directories(self):
        """Create all required directories if they don't exist"""
        directories = [
            self.base_dir,
            self.download_dir,
            self.extracted_dir,
            self.parquet_dir,
            self.database_dir,
            self.logs_dir,
            self.reports_dir
        ]
        
        for dir_path in directories:
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"✓ Directory ensured: {dir_path.relative_to(self.project_root)}")
    
    def get_paths_info(self):
        """Get information about all configured paths"""
        info = {
            'project_root': str(self.project_root),
            'base_dir': str(self.base_dir),
            'download_dir': str(self.download_dir),
            'extracted_dir': str(self.extracted_dir),
            'parquet_dir': str(self.parquet_dir),
            'database_dir': str(self.database_dir),
            'logs_dir': str(self.logs_dir),
            'reports_dir': str(self.reports_dir)
        }
        return info
    
    def __str__(self):
        """String representation showing all paths"""
        paths = self.get_paths_info()
        output = ["Storage Configuration:"]
        output.append(f"  Project Root: {paths['project_root']}")
        output.append("  Data Directories:")
        for key, value in paths.items():
            if key != 'project_root':
                # Show relative path for readability
                rel_path = Path(value).relative_to(self.project_root)
                output.append(f"    {key}: {rel_path}")
        return '\n'.join(output)

@dataclass
class DatabaseConfig:
    """Database configuration"""
    # Development
    dev_host: str = os.getenv('DEV_DB_HOST', 'localhost')
    dev_port: int = int(os.getenv('DEV_DB_PORT', '5432'))
    dev_name: str = os.getenv('DEV_DB_NAME', 'sec_financial_dev')
    dev_user: str = os.getenv('DEV_DB_USER', 'postgres')
    dev_password: str = os.getenv('DEV_DB_PASSWORD', '')
    
    # Production
    prod_host: str = os.getenv('PROD_DB_HOST', 'localhost')
    prod_port: int = int(os.getenv('PROD_DB_PORT', '5432'))
    prod_name: str = os.getenv('PROD_DB_NAME', 'sec_financial_prod')
    prod_user: str = os.getenv('PROD_DB_USER', 'postgres')
    prod_password: str = os.getenv('PROD_DB_PASSWORD', '')
    
    # Pool settings
    pool_size: int = int(os.getenv('DB_POOL_SIZE', '20'))
    max_overflow: int = int(os.getenv('DB_MAX_OVERFLOW', '40'))
    pool_timeout: int = int(os.getenv('DB_POOL_TIMEOUT', '30'))
    
    def get_connection_string(self, env: str = 'dev') -> str:
        """Get database connection string"""
        if env == 'prod':
            return f"postgresql://{self.prod_user}:{self.prod_password}@{self.prod_host}:{self.prod_port}/{self.prod_name}"
        else:
            return f"postgresql://{self.dev_user}:{self.dev_password}@{self.dev_host}:{self.dev_port}/{self.dev_name}"

@dataclass
class ProcessingConfig:
    """Data processing configuration"""
    batch_size: int = int(os.getenv('BATCH_SIZE', '10000'))
    chunk_size: int = int(os.getenv('CHUNK_SIZE', '50000'))
    max_workers: int = int(os.getenv('MAX_WORKERS', '4'))
    concurrent_downloads: int = int(os.getenv('CONCURRENT_DOWNLOADS', '3'))
    
    # Retry settings
    max_retries: int = int(os.getenv('MAX_RETRIES', '3'))
    retry_delay: int = int(os.getenv('RETRY_DELAY', '5'))
    
    # Data coverage
    start_year: int = int(os.getenv('START_YEAR', '2009'))
    end_year: int = int(os.getenv('END_YEAR', '2024'))
    skip_existing: bool = os.getenv('SKIP_EXISTING', 'true').lower() == 'true'
    force_redownload: bool = os.getenv('FORCE_REDOWNLOAD', 'false').lower() == 'true'

@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = os.getenv('LOG_LEVEL', 'INFO')
    format: str = os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_max_bytes: int = int(os.getenv('LOG_FILE_MAX_BYTES', '10485760'))
    file_backup_count: int = int(os.getenv('LOG_FILE_BACKUP_COUNT', '5'))
    enable_console: bool = os.getenv('ENABLE_CONSOLE_LOG', 'true').lower() == 'true'
    enable_file: bool = os.getenv('ENABLE_FILE_LOG', 'true').lower() == 'true'

class Config:
    """Main configuration class"""
    
    def __init__(self):
        self.env = os.getenv('ENV', 'development')
        self.debug = os.getenv('DEBUG', 'true').lower() == 'true'
        
        # Load sub-configurations
        self.sec = SECConfig()
        self.storage = StorageConfig()
        self.database = DatabaseConfig()
        self.processing = ProcessingConfig()
        self.logging = LoggingConfig()
        
        # Feature flags
        self.enable_raw_data = os.getenv('ENABLE_RAW_DATA_STORAGE', 'true').lower() == 'true'
        self.enable_normalized = os.getenv('ENABLE_NORMALIZED_SCHEMA', 'true').lower() == 'true'
        self.enable_analytical = os.getenv('ENABLE_ANALYTICAL_SCHEMA', 'true').lower() == 'true'
        
    def setup(self):
        """Initialize configuration (create directories, etc.)"""
        self.storage.create_directories()
        
    def get_db_connection(self) -> str:
        """Get appropriate database connection string based on environment"""
        return self.database.get_connection_string(self.env)
    
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.env == 'production'
    
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.env == 'development'

# Singleton instance
config = Config()

# Usage example
if __name__ == "__main__":
    # Load configuration
    config.setup()
    
    print(f"Environment: {config.env}")
    print(f"SEC User Agent: {config.sec.user_agent}")
    print(f"Data Directory: {config.storage.base_dir}")
    print(f"Database URL: {config.get_db_connection()}")
    print(f"Processing workers: {config.processing.max_workers}")
    print(f"Start Year: {config.processing.start_year}")
    print(f"Debug Mode: {config.debug}")