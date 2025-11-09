"""
SEC Financial Statement Data - Schema Design Strategy
======================================================
This module provides schema design patterns based on discovered data structures
to optimize storage, querying, and maintenance of SEC financial data.

Author: Faliang
Date: November 2025
"""

import sqlalchemy as sa
from sqlalchemy import create_engine, Column, String, Integer, BigInteger, Float, DateTime, Boolean, Text, Date, Index, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY, NUMERIC
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd

Base = declarative_base()

# ============================================================================
# STAGE 1: RAW DATA SCHEMA (Mirrors SEC structure exactly)
# ============================================================================

class RawSubmission(Base):
    """
    Raw SUB table - Submission metadata
    This table stores data exactly as it comes from SEC
    """
    __tablename__ = 'raw_submissions'
    
    # Primary key
    adsh = Column(String(20), primary_key=True, comment='Accession number, unique filing identifier')
    
    # Company identifiers
    cik = Column(String(10), nullable=False, index=True, comment='Central Index Key (10 digits with leading zeros)')
    name = Column(String(150), nullable=False, comment='Company name')
    sic = Column(String(4), index=True, comment='Standard Industrial Classification code')
    countryba = Column(String(2), comment='Business address country')
    stprba = Column(String(2), comment='Business address state/province')
    cityba = Column(String(30), comment='Business address city')
    zipba = Column(String(10), comment='Business address ZIP code')
    bas1 = Column(String(40), comment='Business address street 1')
    bas2 = Column(String(40), comment='Business address street 2')
    
    # Filing information
    form = Column(String(10), nullable=False, index=True, comment='Form type (10-K, 10-Q, 8-K, etc.)')
    period = Column(Date, index=True, comment='Balance sheet date')
    filed = Column(Date, nullable=False, index=True, comment='Filing date with SEC')
    accepted = Column(DateTime, comment='Acceptance datetime by EDGAR')
    fp = Column(String(2), comment='Fiscal period (Q1, Q2, Q3, Q4, FY)')
    fy = Column(Integer, comment='Fiscal year')
    
    # Additional metadata
    ein = Column(String(10), comment='Employer Identification Number')
    former = Column(String(150), comment='Former company name')
    changed = Column(Date, comment='Date of name change')
    afs = Column(String(5), comment='Filer status')
    wksi = Column(Boolean, comment='Well Known Seasoned Issuer flag')
    fye = Column(String(4), comment='Fiscal year end (MMDD format)')
    
    # Relationships
    numerical_data = relationship("RawNumericalData", back_populates="submission", cascade="all, delete-orphan")
    textual_data = relationship("RawTextualData", back_populates="submission", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_raw_sub_cik_period', 'cik', 'period'),
        Index('idx_raw_sub_form_filed', 'form', 'filed'),
        {'comment': 'Raw submission data from SEC SUB file'}
    )

class RawNumericalData(Base):
    """
    Raw NUM table - All numerical values from financial statements
    """
    __tablename__ = 'raw_numerical_data'
    
    # Composite primary key
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Foreign key to submission
    adsh = Column(String(20), ForeignKey('raw_submissions.adsh'), nullable=False, index=True)
    
    # Tag information
    tag = Column(String(256), nullable=False, index=True, comment='XBRL tag name')
    version = Column(String(20), comment='Taxonomy version')
    
    # Values
    value = Column(NUMERIC(28, 10), comment='Numerical value')
    uom = Column(String(20), comment='Unit of measure')
    
    # Period information
    ddate = Column(Date, index=True, comment='End date of period')
    qtrs = Column(Integer, comment='Number of quarters (0=point-in-time, 1-4=duration)')
    iprx = Column(Integer, comment='Imputed precision')
    
    # Additional fields
    coreg = Column(String(256), comment='Co-registrant')
    durp = Column(Float, comment='Duration in days')
    datp = Column(Date, comment='Date of point-in-time value')
    dcml = Column(Integer, comment='Decimals')
    
    # Relationship
    submission = relationship("RawSubmission", back_populates="numerical_data")
    
    __table_args__ = (
        Index('idx_raw_num_tag_ddate', 'tag', 'ddate'),
        Index('idx_raw_num_adsh_tag', 'adsh', 'tag'),
        {'comment': 'Raw numerical data from SEC NUM file'}
    )

class RawTag(Base):
    """
    Raw TAG table - Taxonomy tag definitions
    """
    __tablename__ = 'raw_tags'
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Tag identification
    tag = Column(String(256), nullable=False, index=True, comment='Tag name')
    version = Column(String(20), nullable=False, comment='Taxonomy version')
    
    # Tag properties
    custom = Column(Boolean, default=False, comment='Custom (1) or standard (0) tag')
    abstract = Column(Boolean, comment='Abstract concept flag')
    datatype = Column(String(20), comment='Data type')
    iord = Column(String(1), comment='I=Instant, D=Duration')
    crdr = Column(String(1), comment='D=Debit, C=Credit')
    tlabel = Column(Text, comment='Tag label')
    doc = Column(Text, comment='Tag documentation')
    
    __table_args__ = (
        UniqueConstraint('tag', 'version', name='uq_tag_version'),
        Index('idx_raw_tag_custom', 'custom'),
        {'comment': 'Raw tag definitions from SEC TAG file'}
    )

class RawTextualData(Base):
    """
    Raw TXT table - Textual disclosures and footnotes
    """
    __tablename__ = 'raw_textual_data'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    adsh = Column(String(20), ForeignKey('raw_submissions.adsh'), nullable=False, index=True)
    tag = Column(String(256), nullable=False, index=True)
    version = Column(String(20))
    ddate = Column(Date, index=True)
    qtrs = Column(Integer)
    iprx = Column(Integer)
    lang = Column(String(5), comment='Language code')
    dcml = Column(Integer)
    durp = Column(Float)
    datp = Column(Date)
    dimn = Column(Integer)
    coreg = Column(String(256))
    escaped = Column(Boolean)
    srclen = Column(Integer, comment='Source text length')
    txtlen = Column(Integer, comment='Plain text length')
    footnote = Column(Text, comment='Footnote text')
    footlen = Column(Integer, comment='Footnote length')
    context = Column(String(256))
    value = Column(Text, comment='Text value')
    
    # Relationship
    submission = relationship("RawSubmission", back_populates="textual_data")
    
    __table_args__ = (
        Index('idx_raw_txt_adsh_tag', 'adsh', 'tag'),
        {'comment': 'Raw textual data from SEC TXT file'}
    )

# ============================================================================
# STAGE 2: NORMALIZED SCHEMA (Optimized for querying and analysis)
# ============================================================================

class Company(Base):
    """
    Normalized company master table
    """
    __tablename__ = 'companies'
    
    # Primary key
    cik = Column(String(10), primary_key=True, comment='Central Index Key')
    
    # Company information
    name = Column(String(150), nullable=False, index=True)
    ticker = Column(String(10), index=True, comment='Stock ticker symbol')
    exchange = Column(String(10), comment='Stock exchange')
    sic = Column(String(4), index=True, comment='SIC code')
    naics = Column(String(6), index=True, comment='NAICS code')
    
    # Current status
    status = Column(String(20), default='active', comment='active, inactive, delisted')
    incorporated_state = Column(String(2))
    incorporated_country = Column(String(2), default='US')
    
    # Business address
    address_line1 = Column(String(100))
    address_line2 = Column(String(100))
    city = Column(String(50))
    state = Column(String(2))
    zip_code = Column(String(10))
    country = Column(String(2))
    
    # Additional metadata
    ein = Column(String(10), comment='Employer ID Number')
    fiscal_year_end = Column(String(4), comment='MMDD format')
    
    # Tracking
    first_filing_date = Column(Date)
    last_filing_date = Column(Date)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    filings = relationship("Filing", back_populates="company")
    financial_facts = relationship("FinancialFact", back_populates="company")
    
    __table_args__ = (
        Index('idx_company_name', 'name'),
        Index('idx_company_ticker', 'ticker'),
        {'comment': 'Company master table with current information'}
    )

class Filing(Base):
    """
    Normalized filing information
    """
    __tablename__ = 'filings'
    
    # Primary key
    adsh = Column(String(20), primary_key=True, comment='Accession number')
    
    # Foreign keys
    cik = Column(String(10), ForeignKey('companies.cik'), nullable=False, index=True)
    
    # Filing details
    form_type = Column(String(10), nullable=False, index=True)
    filing_date = Column(Date, nullable=False, index=True)
    period_date = Column(Date, nullable=False, index=True)
    fiscal_year = Column(Integer)
    fiscal_period = Column(String(2), comment='Q1, Q2, Q3, Q4, FY')
    
    # Status
    is_amended = Column(Boolean, default=False)
    is_restated = Column(Boolean, default=False)
    amendment_flag = Column(String(10))
    
    # Metadata
    accepted_datetime = Column(DateTime)
    documents_count = Column(Integer)
    
    # Relationships
    company = relationship("Company", back_populates="filings")
    financial_facts = relationship("FinancialFact", back_populates="filing")
    
    __table_args__ = (
        Index('idx_filing_cik_period', 'cik', 'period_date'),
        Index('idx_filing_form_date', 'form_type', 'filing_date'),
        UniqueConstraint('cik', 'form_type', 'period_date', 'amendment_flag', name='uq_filing'),
        {'comment': 'Normalized filing information'}
    )

class FinancialFact(Base):
    """
    Normalized financial facts table - optimized for time series analysis
    """
    __tablename__ = 'financial_facts'
    
    # Primary key
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Foreign keys
    cik = Column(String(10), ForeignKey('companies.cik'), nullable=False, index=True)
    adsh = Column(String(20), ForeignKey('filings.adsh'), nullable=False, index=True)
    concept_id = Column(Integer, ForeignKey('financial_concepts.id'), nullable=False, index=True)
    
    # Period information
    period_start = Column(Date, index=True)
    period_end = Column(Date, nullable=False, index=True)
    period_type = Column(String(10), comment='instant, duration')
    
    # Values
    value = Column(NUMERIC(28, 10), nullable=False)
    unit = Column(String(20), nullable=False)
    decimals = Column(Integer)
    
    # Dimensions (for segment reporting)
    segment = Column(String(100), index=True)
    dimension_hash = Column(String(32), index=True, comment='MD5 hash of dimensions')
    dimensions = Column(JSONB, comment='Full dimension data as JSON')
    
    # Quality indicators
    is_primary = Column(Boolean, default=True, comment='Primary vs dimensional fact')
    is_extended = Column(Boolean, default=False, comment='Uses extension taxonomy')
    confidence_score = Column(Float, comment='Data quality score 0-1')
    
    # Tracking
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    company = relationship("Company", back_populates="financial_facts")
    filing = relationship("Filing", back_populates="financial_facts")
    concept = relationship("FinancialConcept", back_populates="facts")
    
    __table_args__ = (
        Index('idx_fact_cik_concept_period', 'cik', 'concept_id', 'period_end'),
        Index('idx_fact_concept_period', 'concept_id', 'period_end'),
        Index('idx_fact_segment', 'segment'),
        UniqueConstraint('adsh', 'concept_id', 'period_end', 'segment', 'dimension_hash', 
                        name='uq_financial_fact'),
        {'comment': 'Normalized financial facts optimized for analysis'}
    )

class FinancialConcept(Base):
    """
    Financial concept taxonomy table
    """
    __tablename__ = 'financial_concepts'
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Concept identification
    tag = Column(String(256), nullable=False, index=True)
    taxonomy = Column(String(50), nullable=False, comment='us-gaap, ifrs, dei, etc.')
    version = Column(String(20))
    
    # Concept properties
    label = Column(String(512))
    documentation = Column(Text)
    data_type = Column(String(20))
    period_type = Column(String(10), comment='instant, duration')
    balance_type = Column(String(10), comment='debit, credit')
    
    # Classification
    financial_statement = Column(String(20), comment='BS, IS, CF, EQ, CI')
    category = Column(String(50), comment='Assets, Liabilities, Revenue, etc.')
    subcategory = Column(String(50))
    is_monetary = Column(Boolean, default=True)
    is_abstract = Column(Boolean, default=False)
    
    # Mapping to common concepts
    common_name = Column(String(100), index=True, comment='Standardized name across taxonomies')
    
    # Usage statistics
    usage_count = Column(Integer, default=0)
    first_seen = Column(Date)
    last_seen = Column(Date)
    
    # Relationships
    facts = relationship("FinancialFact", back_populates="concept")
    
    __table_args__ = (
        UniqueConstraint('tag', 'taxonomy', 'version', name='uq_concept'),
        Index('idx_concept_common_name', 'common_name'),
        Index('idx_concept_statement', 'financial_statement'),
        {'comment': 'Financial concept taxonomy and metadata'}
    )

# ============================================================================
# STAGE 3: ANALYTICAL SCHEMA (Pre-aggregated for performance)
# ============================================================================

class CompanyQuarterlyFinancials(Base):
    """
    Pre-aggregated quarterly financial statements for fast retrieval
    """
    __tablename__ = 'company_quarterly_financials'
    
    # Composite primary key
    cik = Column(String(10), ForeignKey('companies.cik'), primary_key=True)
    period_end = Column(Date, primary_key=True)
    
    # Period information
    fiscal_year = Column(Integer, nullable=False)
    fiscal_quarter = Column(String(2), nullable=False)
    
    # Income Statement (Quarterly)
    revenue = Column(NUMERIC(20, 2))
    cost_of_revenue = Column(NUMERIC(20, 2))
    gross_profit = Column(NUMERIC(20, 2))
    operating_expenses = Column(NUMERIC(20, 2))
    operating_income = Column(NUMERIC(20, 2))
    net_income = Column(NUMERIC(20, 2))
    eps_basic = Column(NUMERIC(10, 4))
    eps_diluted = Column(NUMERIC(10, 4))
    shares_outstanding = Column(BigInteger)
    
    # Balance Sheet (Point in time)
    total_assets = Column(NUMERIC(20, 2))
    current_assets = Column(NUMERIC(20, 2))
    cash_and_equivalents = Column(NUMERIC(20, 2))
    total_liabilities = Column(NUMERIC(20, 2))
    current_liabilities = Column(NUMERIC(20, 2))
    long_term_debt = Column(NUMERIC(20, 2))
    total_equity = Column(NUMERIC(20, 2))
    retained_earnings = Column(NUMERIC(20, 2))
    
    # Cash Flow (Quarterly)
    operating_cash_flow = Column(NUMERIC(20, 2))
    investing_cash_flow = Column(NUMERIC(20, 2))
    financing_cash_flow = Column(NUMERIC(20, 2))
    free_cash_flow = Column(NUMERIC(20, 2))
    
    # Key Ratios (Calculated)
    current_ratio = Column(NUMERIC(10, 4))
    debt_to_equity = Column(NUMERIC(10, 4))
    roe = Column(NUMERIC(10, 4), comment='Return on Equity')
    roa = Column(NUMERIC(10, 4), comment='Return on Assets')
    gross_margin = Column(NUMERIC(10, 4))
    operating_margin = Column(NUMERIC(10, 4))
    net_margin = Column(NUMERIC(10, 4))
    
    # Metadata
    filing_date = Column(Date)
    form_type = Column(String(10))
    is_restated = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_quarterly_cik_year', 'cik', 'fiscal_year'),
        Index('idx_quarterly_period', 'period_end'),
        {'comment': 'Pre-aggregated quarterly financials for fast access'}
    )

class IndustryMetrics(Base):
    """
    Industry-level aggregated metrics
    """
    __tablename__ = 'industry_metrics'
    
    # Composite primary key
    sic = Column(String(4), primary_key=True)
    period_end = Column(Date, primary_key=True)
    
    # Industry identification
    industry_name = Column(String(100))
    company_count = Column(Integer)
    
    # Aggregated metrics (medians)
    median_revenue = Column(NUMERIC(20, 2))
    median_net_income = Column(NUMERIC(20, 2))
    median_total_assets = Column(NUMERIC(20, 2))
    median_roe = Column(NUMERIC(10, 4))
    median_roa = Column(NUMERIC(10, 4))
    median_current_ratio = Column(NUMERIC(10, 4))
    median_debt_to_equity = Column(NUMERIC(10, 4))
    median_gross_margin = Column(NUMERIC(10, 4))
    median_operating_margin = Column(NUMERIC(10, 4))
    median_net_margin = Column(NUMERIC(10, 4))
    
    # Percentiles
    revenue_p25 = Column(NUMERIC(20, 2))
    revenue_p75 = Column(NUMERIC(20, 2))
    net_income_p25 = Column(NUMERIC(20, 2))
    net_income_p75 = Column(NUMERIC(20, 2))
    
    # Metadata
    calculated_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_industry_period', 'period_end'),
        {'comment': 'Industry-level aggregated metrics'}
    )

# ============================================================================
# STAGE 4: SUPPORT TABLES
# ============================================================================

class DataLoadLog(Base):
    """
    Track data loading history
    """
    __tablename__ = 'data_load_log'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Load information
    dataset_year = Column(Integer, nullable=False)
    dataset_quarter = Column(Integer, nullable=False)
    dataset_filename = Column(String(50))
    
    # Status
    load_started = Column(DateTime, nullable=False)
    load_completed = Column(DateTime)
    status = Column(String(20), nullable=False, comment='running, completed, failed')
    
    # Statistics
    submissions_loaded = Column(Integer)
    numerical_facts_loaded = Column(Integer)
    textual_facts_loaded = Column(Integer)
    tags_loaded = Column(Integer)
    
    # Error tracking
    error_count = Column(Integer, default=0)
    error_messages = Column(Text)
    
    __table_args__ = (
        Index('idx_load_log_dataset', 'dataset_year', 'dataset_quarter'),
        {'comment': 'Data loading audit log'}
    )

class TagMapping(Base):
    """
    Map XBRL tags to standardized concepts
    """
    __tablename__ = 'tag_mappings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Source tag
    source_tag = Column(String(256), nullable=False, index=True)
    source_taxonomy = Column(String(50))
    
    # Target mapping
    target_concept = Column(String(100), nullable=False, index=True)
    target_category = Column(String(50))
    
    # Mapping metadata
    confidence = Column(Float, default=1.0)
    mapping_rule = Column(Text)
    is_active = Column(Boolean, default=True)
    
    # Tracking
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(50))
    
    __table_args__ = (
        UniqueConstraint('source_tag', 'source_taxonomy', name='uq_tag_mapping'),
        {'comment': 'XBRL tag to standardized concept mappings'}
    )

# ============================================================================
# SCHEMA GENERATION FUNCTIONS
# ============================================================================

class SchemaGenerator:
    """
    Generate optimal schemas based on discovered data characteristics
    """
    
    def __init__(self, discovery_results: Dict):
        """
        Initialize with discovery results from data exploration
        """
        self.discovery = discovery_results
        self.engine = None
        
    def analyze_data_characteristics(self) -> Dict:
        """
        Analyze discovered data to make schema decisions
        """
        analysis = {
            'total_rows': {},
            'cardinality': {},
            'data_types': {},
            'relationships': {},
            'optimization_hints': []
        }
        
        # Analyze each table's characteristics
        for table_name, table_info in self.discovery.get('table_analysis', {}).items():
            analysis['total_rows'][table_name] = table_info.get('row_count', 0)
            
            # Analyze cardinality for indexing decisions
            for col_info in table_info.get('columns', []):
                col_name = col_info['name']
                unique_ratio = col_info['unique_values'] / table_info['row_count'] if table_info['row_count'] > 0 else 0
                
                if unique_ratio > 0.9:
                    analysis['optimization_hints'].append(f"High cardinality on {table_name}.{col_name} - good for primary key or unique index")
                elif unique_ratio < 0.1:
                    analysis['optimization_hints'].append(f"Low cardinality on {table_name}.{col_name} - consider bitmap index")
                    
        return analysis
        
    def generate_optimized_schema(self, schema_type: str = 'normalized') -> str:
        """
        Generate DDL for optimized schema based on discoveries
        
        Args:
            schema_type: 'raw', 'normalized', or 'analytical'
        """
        ddl = []
        
        if schema_type == 'raw':
            ddl.append("-- Raw Schema: Preserves original SEC data structure")
            ddl.extend(self._generate_raw_schema())
        elif schema_type == 'normalized':
            ddl.append("-- Normalized Schema: Optimized for querying and relationships")
            ddl.extend(self._generate_normalized_schema())
        elif schema_type == 'analytical':
            ddl.append("-- Analytical Schema: Pre-aggregated for performance")
            ddl.extend(self._generate_analytical_schema())
            
        return '\n'.join(ddl)
        
    def _generate_raw_schema(self) -> List[str]:
        """Generate DDL for raw data tables"""
        ddl = []
        
        # Based on discovered tables
        for table_name, table_info in self.discovery.get('table_analysis', {}).items():
            table_ddl = f"\nCREATE TABLE raw_{table_name} ("
            
            columns = []
            for col_info in table_info.get('columns', []):
                col_name = col_info['name']
                col_type = self._map_to_sql_type(col_info)
                nullable = "NULL" if col_info.get('null_percentage', 0) > 10 else "NOT NULL"
                columns.append(f"    {col_name} {col_type} {nullable}")
                
            table_ddl += '\n' + ',\n'.join(columns)
            table_ddl += "\n);"
            
            ddl.append(table_ddl)
            
            # Add indexes based on cardinality
            for col_info in table_info.get('columns', []):
                if col_info.get('potential_key', False):
                    ddl.append(f"CREATE INDEX idx_raw_{table_name}_{col_info['name']} ON raw_{table_name}({col_info['name']});")
                    
        return ddl
        
    def _generate_normalized_schema(self) -> List[str]:
        """Generate DDL for normalized schema"""
        # This would use the SQLAlchemy models defined above
        # and customize based on discovery results
        return [
            "-- See normalized schema models in code",
            "-- Customized based on discovered data patterns"
        ]
        
    def _generate_analytical_schema(self) -> List[str]:
        """Generate DDL for analytical schema"""
        return [
            "-- Pre-aggregated tables for fast analytics",
            "-- Based on common query patterns discovered"
        ]
        
    def _map_to_sql_type(self, col_info: Dict) -> str:
        """Map discovered data type to SQL type"""
        dtype = col_info.get('dtype', 'object')
        
        if 'int' in str(dtype):
            if col_info.get('max', 0) > 2147483647:
                return 'BIGINT'
            return 'INTEGER'
        elif 'float' in str(dtype):
            return 'NUMERIC(28,10)'
        elif col_info.get('likely_date', False):
            return 'DATE'
        elif col_info.get('max_length', 0) > 255:
            return 'TEXT'
        elif col_info.get('max_length', 0) > 0:
            return f"VARCHAR({min(col_info['max_length'] * 2, 1000)})"
        else:
            return 'TEXT'
            
    def generate_migration_strategy(self) -> Dict:
        """
        Generate a migration strategy from raw to normalized schema
        """
        strategy = {
            'steps': [],
            'sql_scripts': [],
            'validation_queries': []
        }
        
        # Step 1: Load raw data
        strategy['steps'].append({
            'step': 1,
            'action': 'Load raw data from SEC files',
            'tables': ['raw_sub', 'raw_num', 'raw_tag', 'raw_txt']
        })
        
        # Step 2: Normalize companies
        strategy['sql_scripts'].append("""
            -- Normalize company data
            INSERT INTO companies (cik, name, ticker, sic, ein, fiscal_year_end)
            SELECT DISTINCT
                cik,
                name,
                -- ticker would come from separate mapping
                NULL as ticker,
                sic,
                ein,
                fye
            FROM raw_sub
            ON CONFLICT (cik) DO UPDATE SET
                name = EXCLUDED.name,
                sic = EXCLUDED.sic,
                last_filing_date = CURRENT_DATE;
        """)
        
        # Step 3: Normalize filings
        strategy['sql_scripts'].append("""
            -- Normalize filing data
            INSERT INTO filings (adsh, cik, form_type, filing_date, period_date, fiscal_year, fiscal_period)
            SELECT
                adsh,
                cik,
                form,
                filed,
                period,
                fy,
                fp
            FROM raw_sub;
        """)
        
        # Step 4: Normalize financial facts
        strategy['sql_scripts'].append("""
            -- Normalize financial facts
            INSERT INTO financial_facts (cik, adsh, concept_id, period_end, value, unit)
            SELECT
                s.cik,
                n.adsh,
                c.id as concept_id,
                n.ddate,
                n.value,
                n.uom
            FROM raw_num n
            JOIN raw_sub s ON n.adsh = s.adsh
            JOIN financial_concepts c ON n.tag = c.tag
            WHERE n.value IS NOT NULL;
        """)
        
        # Validation queries
        strategy['validation_queries'].extend([
            "SELECT COUNT(*) FROM companies",
            "SELECT COUNT(*) FROM filings",
            "SELECT COUNT(*) FROM financial_facts",
            """
            -- Check data integrity
            SELECT 
                'Missing CIKs' as check_type,
                COUNT(*) as count
            FROM raw_sub s
            LEFT JOIN companies c ON s.cik = c.cik
            WHERE c.cik IS NULL
            """
        ])
        
        return strategy

# ============================================================================
# USAGE EXAMPLE
# ============================================================================

def design_schema_from_discovery(discovery_results_file: str):
    """
    Design optimal schema based on discovery results
    
    Args:
        discovery_results_file: Path to JSON file from data exploration
    """
    import json
    
    # Load discovery results
    with open(discovery_results_file, 'r') as f:
        discovery_results = json.load(f)
        
    # Create schema generator
    generator = SchemaGenerator(discovery_results)
    
    # Analyze data characteristics
    analysis = generator.analyze_data_characteristics()
    print("Data Characteristics Analysis:")
    print(json.dumps(analysis, indent=2))
    
    # Generate schemas
    print("\n" + "="*60)
    print("RAW SCHEMA DDL")
    print("="*60)
    print(generator.generate_optimized_schema('raw'))
    
    print("\n" + "="*60)
    print("MIGRATION STRATEGY")
    print("="*60)
    strategy = generator.generate_migration_strategy()
    for step in strategy['steps']:
        print(f"Step {step['step']}: {step['action']}")
        
    return generator

if __name__ == "__main__":
    # This would be run after data discovery
    import sys
    
    if len(sys.argv) > 1:
        discovery_file = sys.argv[1]
        generator = design_schema_from_discovery(discovery_file)
    else:
        print("Usage: python schema_design.py <discovery_results.json>")
        print("\nThis script generates optimal schemas based on SEC data discovery results.")