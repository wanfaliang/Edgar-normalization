"""
SQLAlchemy Models for SEC Filing Database
==========================================
Defines database schema using SQLAlchemy ORM.

Storage Strategy (Hybrid Approach):
- PostgreSQL: Filing index, company index, dataset tracking
- File System: Raw .txt files (num, pre, tag, sub) - read by statement_reconstructor

Author: Finexus Team
Date: November 2025
"""

from sqlalchemy import (
    Column, String, Integer, Date, DateTime, Boolean,
    Numeric, Text, ARRAY, ForeignKey, Index
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
    fiscal_period = Column(String(10))

    # Additional metadata from SUB table
    sic = Column(String(4))
    countryba = Column(String(2))
    stprba = Column(String(2))
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
