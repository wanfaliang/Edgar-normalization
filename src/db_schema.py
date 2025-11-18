"""
PostgreSQL Database Schema for SEC Filing Index
================================================
Creates tables for indexing downloaded SEC financial statement data.

Tables:
- companies: Company master index
- filings: All SEC filings metadata
- datasets: Downloaded quarter datasets tracking

Author: Finexus Team
Date: November 2025
"""

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import logging
from pathlib import Path
import sys

# Add src to path
sys.path.append(str(Path(__file__).parent))
from config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# SQL Schema Definitions
SCHEMA_SQL = """
-- ============================================================================
-- COMPANIES TABLE
-- ============================================================================
-- Master index of all companies in the SEC database
CREATE TABLE IF NOT EXISTS companies (
    cik VARCHAR(10) PRIMARY KEY,
    company_name VARCHAR(500),
    sic VARCHAR(4),
    industry_description VARCHAR(255),
    first_filing_date DATE,
    last_filing_date DATE,
    total_filings INTEGER DEFAULT 0,
    forms_filed TEXT[],  -- Array of form types filed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(company_name);
CREATE INDEX IF NOT EXISTS idx_companies_sic ON companies(sic);
CREATE INDEX IF NOT EXISTS idx_companies_last_filing ON companies(last_filing_date);

-- ============================================================================
-- FILINGS TABLE
-- ============================================================================
-- Detailed index of all SEC filings from downloaded datasets
CREATE TABLE IF NOT EXISTS filings (
    adsh VARCHAR(20) PRIMARY KEY,
    cik VARCHAR(10) NOT NULL,
    company_name VARCHAR(500),
    form_type VARCHAR(20),
    filed_date DATE,
    period_end_date DATE,
    fiscal_year INTEGER,
    fiscal_period VARCHAR(10),

    -- Additional metadata from SUB table
    sic VARCHAR(4),
    countryba VARCHAR(2),
    stprba VARCHAR(2),
    cityba VARCHAR(50),
    zipba VARCHAR(10),
    bas1 VARCHAR(255),

    -- Filing details
    accepted_timestamp TIMESTAMP,
    prevrpt BOOLEAN,
    detail BOOLEAN,
    instance VARCHAR(100),
    nciks INTEGER,
    aciks TEXT[],

    -- Source tracking
    source_year INTEGER NOT NULL,
    source_quarter INTEGER NOT NULL,
    source_dataset VARCHAR(20),

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (cik) REFERENCES companies(cik) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_filings_cik ON filings(cik);
CREATE INDEX IF NOT EXISTS idx_filings_form_type ON filings(form_type);
CREATE INDEX IF NOT EXISTS idx_filings_filed_date ON filings(filed_date);
CREATE INDEX IF NOT EXISTS idx_filings_period_end ON filings(period_end_date);
CREATE INDEX IF NOT EXISTS idx_filings_fiscal_year ON filings(fiscal_year);
CREATE INDEX IF NOT EXISTS idx_filings_source ON filings(source_year, source_quarter);
CREATE INDEX IF NOT EXISTS idx_filings_company_form ON filings(cik, form_type);

-- ============================================================================
-- DATASETS TABLE
-- ============================================================================
-- Track downloaded and processed quarterly datasets
CREATE TABLE IF NOT EXISTS datasets (
    id SERIAL PRIMARY KEY,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    dataset_type VARCHAR(50) DEFAULT 'financial-statements',

    -- Download status
    download_status VARCHAR(20) DEFAULT 'pending',  -- pending, downloading, completed, failed
    download_started_at TIMESTAMP,
    download_completed_at TIMESTAMP,
    download_error TEXT,

    -- Processing status
    processing_status VARCHAR(20) DEFAULT 'pending',  -- pending, processing, completed, failed
    processing_started_at TIMESTAMP,
    processing_completed_at TIMESTAMP,
    processing_error TEXT,

    -- Statistics
    total_submissions INTEGER DEFAULT 0,
    total_companies INTEGER DEFAULT 0,
    total_tags INTEGER DEFAULT 0,
    total_num_records INTEGER DEFAULT 0,

    -- File information
    zip_file_path TEXT,
    zip_file_size_mb NUMERIC(10, 2),
    extracted_path TEXT,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(year, quarter, dataset_type)
);

CREATE INDEX IF NOT EXISTS idx_datasets_status ON datasets(download_status, processing_status);
CREATE INDEX IF NOT EXISTS idx_datasets_year_quarter ON datasets(year, quarter);

-- ============================================================================
-- FILING_TAGS TABLE (Optional - for detailed tag tracking)
-- ============================================================================
-- Track which tags appear in which filings (useful for standardization)
CREATE TABLE IF NOT EXISTS filing_tags (
    id BIGSERIAL PRIMARY KEY,
    adsh VARCHAR(20) NOT NULL,
    tag VARCHAR(255) NOT NULL,
    version VARCHAR(50),
    custom BOOLEAN DEFAULT false,
    abstract BOOLEAN DEFAULT false,
    datatype VARCHAR(50),
    iord VARCHAR(1),  -- I=Instant, D=Duration
    crdr VARCHAR(2),  -- CR=Credit, DR=Debit
    tlabel TEXT,
    value_count INTEGER DEFAULT 0,  -- How many values reported for this tag

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (adsh) REFERENCES filings(adsh) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_filing_tags_adsh ON filing_tags(adsh);
CREATE INDEX IF NOT EXISTS idx_filing_tags_tag ON filing_tags(tag);
CREATE INDEX IF NOT EXISTS idx_filing_tags_custom ON filing_tags(custom);

-- ============================================================================
-- VIEWS
-- ============================================================================

-- View: Recent filings by company
CREATE OR REPLACE VIEW recent_filings AS
SELECT
    f.cik,
    c.company_name,
    f.form_type,
    f.filed_date,
    f.period_end_date,
    f.fiscal_year,
    f.fiscal_period,
    f.adsh
FROM filings f
JOIN companies c ON f.cik = c.cik
ORDER BY f.filed_date DESC;

-- View: Dataset processing status
CREATE OR REPLACE VIEW dataset_status AS
SELECT
    year,
    quarter,
    dataset_type,
    download_status,
    processing_status,
    total_submissions,
    total_companies,
    download_completed_at,
    processing_completed_at
FROM datasets
ORDER BY year DESC, quarter DESC;

-- View: Company filing summary
CREATE OR REPLACE VIEW company_filing_summary AS
SELECT
    c.cik,
    c.company_name,
    c.sic,
    COUNT(f.adsh) as total_filings,
    MIN(f.filed_date) as first_filing,
    MAX(f.filed_date) as last_filing,
    ARRAY_AGG(DISTINCT f.form_type) as form_types
FROM companies c
LEFT JOIN filings f ON c.cik = f.cik
GROUP BY c.cik, c.company_name, c.sic;

"""

# Update trigger for updated_at timestamps
TRIGGER_SQL = """
-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for each table
DROP TRIGGER IF EXISTS update_companies_updated_at ON companies;
CREATE TRIGGER update_companies_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_filings_updated_at ON filings;
CREATE TRIGGER update_filings_updated_at
    BEFORE UPDATE ON filings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_datasets_updated_at ON datasets;
CREATE TRIGGER update_datasets_updated_at
    BEFORE UPDATE ON datasets
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
"""


class DatabaseManager:
    """Manage PostgreSQL database schema and connections"""

    def __init__(self):
        self.config = config

    def get_connection(self):
        """Get database connection"""
        conn_string = self.config.get_db_connection()
        logger.info(f"Connecting to database: {self.config.database.dev_name}")

        try:
            conn = psycopg2.connect(conn_string)
            return conn
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise

    def test_connection(self):
        """Test database connection"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()
            logger.info(f"✅ Database connection successful!")
            logger.info(f"PostgreSQL version: {version[0]}")
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            return False

    def create_schema(self, drop_existing=False):
        """Create database schema"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            if drop_existing:
                logger.warning("Dropping existing tables...")
                cursor.execute("""
                    DROP TABLE IF EXISTS filing_tags CASCADE;
                    DROP TABLE IF EXISTS filings CASCADE;
                    DROP TABLE IF EXISTS datasets CASCADE;
                    DROP TABLE IF EXISTS companies CASCADE;
                    DROP VIEW IF EXISTS recent_filings CASCADE;
                    DROP VIEW IF EXISTS dataset_status CASCADE;
                    DROP VIEW IF EXISTS company_filing_summary CASCADE;
                """)
                conn.commit()
                logger.info("✅ Existing tables dropped")

            # Create schema
            logger.info("Creating database schema...")
            cursor.execute(SCHEMA_SQL)
            conn.commit()
            logger.info("✅ Tables created successfully")

            # Create triggers
            logger.info("Creating triggers...")
            cursor.execute(TRIGGER_SQL)
            conn.commit()
            logger.info("✅ Triggers created successfully")

            # Verify tables
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)
            tables = cursor.fetchall()
            logger.info(f"✅ Schema created with {len(tables)} tables:")
            for table in tables:
                logger.info(f"   - {table[0]}")

            cursor.close()
            conn.close()

            return True

        except Exception as e:
            logger.error(f"❌ Schema creation failed: {e}")
            if conn:
                conn.rollback()
            raise

    def get_stats(self):
        """Get database statistics"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            stats = {}

            # Count companies
            cursor.execute("SELECT COUNT(*) FROM companies;")
            stats['companies'] = cursor.fetchone()[0]

            # Count filings
            cursor.execute("SELECT COUNT(*) FROM filings;")
            stats['filings'] = cursor.fetchone()[0]

            # Count datasets
            cursor.execute("SELECT COUNT(*) FROM datasets;")
            stats['datasets'] = cursor.fetchone()[0]

            # Latest filing date
            cursor.execute("SELECT MAX(filed_date) FROM filings;")
            latest = cursor.fetchone()[0]
            stats['latest_filing_date'] = str(latest) if latest else None

            cursor.close()
            conn.close()

            return stats

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}


def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(description='Manage SEC filing database schema')
    parser.add_argument('--test', action='store_true', help='Test database connection')
    parser.add_argument('--create', action='store_true', help='Create database schema')
    parser.add_argument('--drop', action='store_true', help='Drop existing tables before creating')
    parser.add_argument('--stats', action='store_true', help='Show database statistics')

    args = parser.parse_args()

    db = DatabaseManager()

    if args.test:
        db.test_connection()

    if args.create:
        db.create_schema(drop_existing=args.drop)

    if args.stats:
        stats = db.get_stats()
        print("\n" + "="*60)
        print("DATABASE STATISTICS")
        print("="*60)
        for key, value in stats.items():
            print(f"{key}: {value}")

    if not any([args.test, args.create, args.stats]):
        print("No action specified. Use --help for options.")


if __name__ == "__main__":
    main()
