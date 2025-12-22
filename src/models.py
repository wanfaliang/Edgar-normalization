"""
SQLAlchemy Models for SEC Filing Database
==========================================
Defines database schema using SQLAlchemy ORM.

Storage Strategy:
- PostgreSQL: All data including pre, num, tag tables for fast queries

Author: Finexus Team
Date: November 2025
"""

from sqlalchemy import (
    Column, String, Integer, Date, DateTime, Boolean,
    Numeric, Text, ARRAY, ForeignKey, Index, BigInteger, Float
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class Company(Base):
    """Master index of all companies in SEC database"""
    __tablename__ = 'companies'

    cik = Column(String(10), primary_key=True)
    company_name = Column(String(500))
    sic = Column(String(4))
    industry_description = Column(String(255))
    ticker = Column(String(10))
    exchange = Column(String(10))
    first_filing_date = Column(Date)
    last_filing_date = Column(Date)
    total_filings = Column(Integer, default=0)
    forms_filed = Column(ARRAY(Text))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    filings = relationship("Filing", back_populates="company", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_companies_name', 'company_name'),
        Index('idx_companies_sic', 'sic'),
        Index('idx_companies_last_filing', 'last_filing_date'),
        Index('ix_companies_ticker', 'ticker'),
    )

    def __repr__(self):
        return f"<Company(cik='{self.cik}', name='{self.company_name}')>"


class Filing(Base):
    """
    Detailed index of all SEC filings (from sub.txt)
    Note: Actual financial data (num.txt, pre.txt) stored as files on disk
    """
    __tablename__ = 'filings'

    adsh = Column(String(20), primary_key=True)
    cik = Column(String(10), ForeignKey('companies.cik', ondelete='CASCADE'), nullable=False)
    company_name = Column(String(500))
    form_type = Column(String(20))
    filed_date = Column(Date)
    period_end_date = Column(Date)
    fiscal_year = Column(Integer)
    fiscal_period = Column(String(20))

    # Additional metadata from SUB table
    sic = Column(String(4))
    countryba = Column(String(5))
    stprba = Column(String(5))
    cityba = Column(String(50))
    zipba = Column(String(10))
    bas1 = Column(String(255))

    # Filing details
    accepted_timestamp = Column(DateTime)
    prevrpt = Column(Boolean)
    detail = Column(Boolean)
    instance = Column(String(100))
    nciks = Column(Integer)
    aciks = Column(ARRAY(Text))

    # Source tracking (which dataset this came from)
    source_year = Column(Integer, nullable=False)
    source_quarter = Column(Integer, nullable=False)
    source_dataset = Column(String(20))

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    company = relationship("Company", back_populates="filings")

    __table_args__ = (
        Index('idx_filings_cik', 'cik'),
        Index('idx_filings_form_type', 'form_type'),
        Index('idx_filings_filed_date', 'filed_date'),
        Index('idx_filings_period_end', 'period_end_date'),
        Index('idx_filings_fiscal_year', 'fiscal_year'),
        Index('idx_filings_source', 'source_year', 'source_quarter'),
        Index('idx_filings_company_form', 'cik', 'form_type'),
    )

    def __repr__(self):
        return f"<Filing(adsh='{self.adsh}', cik='{self.cik}', form='{self.form_type}')>"


class Dataset(Base):
    """
    Track downloaded and processed quarterly datasets
    Maps to file system: data/sec_datasets/{year}q{quarter}/
    """
    __tablename__ = 'datasets'

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False)
    quarter = Column(Integer, nullable=False)
    dataset_type = Column(String(50), default='financial-statements')

    # Download status
    download_status = Column(String(20), default='pending')  # pending, downloading, completed, failed
    download_started_at = Column(DateTime)
    download_completed_at = Column(DateTime)
    download_error = Column(Text)

    # Processing status (indexing into PostgreSQL)
    processing_status = Column(String(20), default='pending')  # pending, processing, completed, failed
    processing_started_at = Column(DateTime)
    processing_completed_at = Column(DateTime)
    processing_error = Column(Text)

    # Statistics (from sub.txt indexing)
    total_submissions = Column(Integer, default=0)
    total_companies = Column(Integer, default=0)
    total_tags = Column(Integer, default=0)
    total_num_records = Column(Integer, default=0)

    # File paths
    zip_file_path = Column(Text)
    zip_file_size_mb = Column(Numeric(10, 2))
    extracted_path = Column(Text)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_datasets_status', 'download_status', 'processing_status'),
        Index('idx_datasets_year_quarter', 'year', 'quarter'),
    )

    def __repr__(self):
        return f"<Dataset(year={self.year}, quarter={self.quarter}, status={self.download_status})>"


class EdgarPre(Base):
    """
    Presentation linkbase data (from pre.txt)
    Defines statement structure: which tags appear in which statements, in what order
    """
    __tablename__ = 'edgar_pre'

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # Filing reference (no FK - SEC data has orphaned records)
    adsh = Column(String(20), nullable=False)

    # Statement structure
    report = Column(Integer)  # Report number within filing
    line = Column(Integer)    # Line number within report
    stmt = Column(String(2))  # Statement type: BS, IS, CF, EQ, CI, UN
    inpth = Column(Integer)   # Indentation level (0=parent, 1=child, etc.)
    rfile = Column(String(1)) # Report file: H=htm, X=xml

    # Tag reference
    tag = Column(String(256), nullable=False)
    version = Column(String(20))  # Taxonomy version (e.g., us-gaap/2024)

    # Presentation
    plabel = Column(String(512))  # Preferred label
    negating = Column(String(1))  # '1' if value should be negated

    # Source tracking
    source_year = Column(Integer, nullable=False)
    source_quarter = Column(Integer, nullable=False)

    __table_args__ = (
        Index('idx_edgar_pre_adsh', 'adsh'),
        Index('idx_edgar_pre_adsh_stmt', 'adsh', 'stmt'),
        Index('idx_edgar_pre_tag', 'tag'),
        Index('idx_edgar_pre_source', 'source_year', 'source_quarter'),
    )

    def __repr__(self):
        return f"<EdgarPre(adsh='{self.adsh}', stmt='{self.stmt}', line={self.line}, tag='{self.tag}')>"


class EdgarNum(Base):
    """
    Numeric facts data (from num.txt)
    Contains actual financial values reported in filings
    """
    __tablename__ = 'edgar_num'

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # Filing reference (no FK - SEC data has orphaned records)
    adsh = Column(String(20), nullable=False)

    # Tag reference
    tag = Column(String(256), nullable=False)
    version = Column(String(20))  # Taxonomy version

    # Period information
    ddate = Column(String(8))   # Period end date (YYYYMMDD format)
    qtrs = Column(String(8))    # Number of quarters (0=instant, 1=Q, 4=FY)

    # Value details
    uom = Column(String(20))    # Unit of measure (USD, shares, etc.)
    segments = Column(Text)     # Dimensional segments (JSON-like)
    coreg = Column(String(256)) # Co-registrant
    value = Column(Numeric(28, 4))  # The actual numeric value (28 digits, 4 decimal places for large financials)
    footnote = Column(Text)     # Footnote reference

    # Source tracking
    source_year = Column(Integer, nullable=False)
    source_quarter = Column(Integer, nullable=False)

    __table_args__ = (
        Index('idx_edgar_num_adsh', 'adsh'),
        Index('idx_edgar_num_adsh_tag', 'adsh', 'tag'),
        Index('idx_edgar_num_tag', 'tag'),
        Index('idx_edgar_num_ddate', 'ddate'),
        Index('idx_edgar_num_source', 'source_year', 'source_quarter'),
    )

    def __repr__(self):
        return f"<EdgarNum(adsh='{self.adsh}', tag='{self.tag}', value={self.value})>"


class EdgarTag(Base):
    """
    Tag definitions (from tag.txt)
    Contains metadata about XBRL tags used in filings
    """
    __tablename__ = 'edgar_tag'

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # Tag identification (composite unique)
    tag = Column(String(256), nullable=False)
    version = Column(String(20), nullable=False)  # Taxonomy version

    # Tag properties
    custom = Column(String(1))    # '1' if custom tag (not standard taxonomy)
    abstract = Column(String(1))  # '1' if abstract (no value)
    datatype = Column(String(50)) # Data type (monetary, shares, etc.)
    iord = Column(String(1))      # I=instant, D=duration
    crdr = Column(String(1))      # C=credit, D=debit

    # Documentation
    tlabel = Column(String(512))  # Tag label
    doc = Column(Text)            # Tag documentation

    # Source tracking
    source_year = Column(Integer, nullable=False)
    source_quarter = Column(Integer, nullable=False)

    __table_args__ = (
        Index('idx_edgar_tag_tag', 'tag'),
        Index('idx_edgar_tag_tag_version', 'tag', 'version'),
        Index('idx_edgar_tag_source', 'source_year', 'source_quarter'),
    )

    def __repr__(self):
        return f"<EdgarTag(tag='{self.tag}', version='{self.version}')>"
