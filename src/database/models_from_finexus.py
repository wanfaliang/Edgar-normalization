"""
These are part of the SQLAlchemy Models for FinExus Data Collection System
Defines all database tables with proper relationships and constraints
"""
from datetime import datetime, date
from typing import Optional
from decimal import Decimal

from sqlalchemy import (
    Column, Integer, String, Numeric, Date, DateTime, 
    Boolean, Text, ForeignKey, Index, CheckConstraint,
    UniqueConstraint, BigInteger, Float
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class Company(Base):
    """Master company/ticker table with profile information"""
    __tablename__ = 'companies'
    
    company_id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), unique=True, nullable=False, index=True)
    company_name = Column(String(200), nullable=False)
    
    # Profile data from FMP
    price = Column(Numeric(20, 4))
    market_cap = Column(BigInteger)
    beta = Column(Numeric(20, 4))
    last_dividend = Column(Numeric(20, 4))
    range = Column(String(50))
    change = Column(Numeric(20, 4))
    change_percentage = Column(Numeric(20, 4))
    volume = Column(BigInteger)
    average_volume = Column(BigInteger)
    currency = Column(String(10))
    cik = Column(String(20), index=True)
    isin = Column(String(20))
    cusip = Column(String(20))
    exchange = Column(String(20))
    exchange_full_name = Column(String(100))
    industry = Column(String(100), index=True)
    sector = Column(String(100), index=True)
    country = Column(String(100))
    website = Column(String(200))
    description = Column(Text)
    ceo = Column(String(100))
    full_time_employees = Column(String(20))  # API returns as string
    phone = Column(String(50))
    address = Column(String(200))
    city = Column(String(100))
    state = Column(String(50))
    zip = Column(String(20))
    image = Column(String(200))
    ipo_date = Column(Date)
    default_image = Column(Boolean)
    is_etf = Column(Boolean)
    is_actively_trading = Column(Boolean)
    is_adr = Column(Boolean)
    is_fund = Column(Boolean)
    
    # Metadata
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<Company(symbol='{self.symbol}', name='{self.company_name}')>"


class IncomeStatement(Base):
    """Income statement data for all companies"""
    __tablename__ = 'income_statements'

    # Composite primary key
    symbol = Column(String(20), ForeignKey('companies.symbol'), primary_key=True)
    date = Column(Date, primary_key=True)
    period = Column(String(10), primary_key=True)  # 'Q1', 'Q2', 'Q3', 'Q4', 'FY'

    # Income statement fields
    reported_currency = Column(String(10))
    cik = Column(String(20))
    filling_date = Column(Date)  # Note: API uses 'fillingDate' (typo in their API)
    filing_date = Column(Date)  # API also returns properly spelled version
    accepted_date = Column(DateTime)
    calendar_year = Column(String(10))
    fiscal_year = Column(Integer)  # API returns this too

    revenue = Column(Numeric(20, 2))
    cost_of_revenue = Column(Numeric(20, 2))
    gross_profit = Column(Numeric(20, 2))
    gross_profit_ratio = Column(Numeric(20, 6))

    research_and_development_expenses = Column(Numeric(20, 2))
    general_and_administrative_expenses = Column(Numeric(20, 2))
    selling_and_marketing_expenses = Column(Numeric(20, 2))
    selling_general_and_administrative_expenses = Column(Numeric(20, 2))
    other_expenses = Column(Numeric(20, 2))
    operating_expenses = Column(Numeric(20, 2))
    cost_and_expenses = Column(Numeric(20, 2))

    interest_income = Column(Numeric(20, 2))
    interest_expense = Column(Numeric(20, 2))
    net_interest_income = Column(Numeric(20, 2))

    depreciation_and_amortization = Column(Numeric(20, 2))
    ebitda = Column(Numeric(20, 2))
    ebitda_ratio = Column(Numeric(20, 6))
    ebit = Column(Numeric(20, 2))

    non_operating_income_excluding_interest = Column(Numeric(20, 2))
    operating_income = Column(Numeric(20, 2))
    operating_income_ratio = Column(Numeric(20, 6))
    total_other_income_expenses_net = Column(Numeric(20, 2))
    income_before_tax = Column(Numeric(20, 2))
    income_before_tax_ratio = Column(Numeric(20, 6))
    income_tax_expense = Column(Numeric(20, 2))

    net_income = Column(Numeric(20, 2))
    net_income_ratio = Column(Numeric(20, 6))
    net_income_from_continuing_operations = Column(Numeric(20, 2))
    net_income_from_discontinued_operations = Column(Numeric(20, 2))
    other_adjustments_to_net_income = Column(Numeric(20, 2))
    net_income_deductions = Column(Numeric(20, 2))
    bottom_line_net_income = Column(Numeric(20, 2))

    eps = Column(Numeric(20, 4))
    eps_diluted = Column(Numeric(20, 4))
    weighted_average_shs_out = Column(BigInteger)
    weighted_average_shs_out_dil = Column(BigInteger)

    # Metadata
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index('ix_income_statements_symbol_date', 'symbol', 'date'),
        Index('ix_income_statements_fiscal_year', 'fiscal_year'),
    )


class BalanceSheet(Base):
    """Balance sheet data for all companies"""
    __tablename__ = 'balance_sheets'

    symbol = Column(String(20), ForeignKey('companies.symbol'), primary_key=True)
    date = Column(Date, primary_key=True)
    period = Column(String(10), primary_key=True)

    reported_currency = Column(String(10))
    cik = Column(String(20))
    filling_date = Column(Date)
    filing_date = Column(Date)
    accepted_date = Column(DateTime)
    calendar_year = Column(String(10))
    fiscal_year = Column(Integer)

    # Assets
    cash_and_cash_equivalents = Column(Numeric(20, 2))
    short_term_investments = Column(Numeric(20, 2))
    cash_and_short_term_investments = Column(Numeric(20, 2))
    net_receivables = Column(Numeric(20, 2))
    accounts_receivables = Column(Numeric(20, 2))
    other_receivables = Column(Numeric(20, 2))
    inventory = Column(Numeric(20, 2))
    prepaids = Column(Numeric(20, 2))
    other_current_assets = Column(Numeric(20, 2))
    total_current_assets = Column(Numeric(20, 2))

    property_plant_equipment_net = Column(Numeric(20, 2))
    goodwill = Column(Numeric(20, 2))
    intangible_assets = Column(Numeric(20, 2))
    goodwill_and_intangible_assets = Column(Numeric(20, 2))
    long_term_investments = Column(Numeric(20, 2))
    tax_assets = Column(Numeric(20, 2))
    other_non_current_assets = Column(Numeric(20, 2))
    total_non_current_assets = Column(Numeric(20, 2))
    other_assets = Column(Numeric(20, 2))
    total_assets = Column(Numeric(20, 2))

    # Liabilities
    total_payables = Column(Numeric(20, 2))
    account_payables = Column(Numeric(20, 2))
    other_payables = Column(Numeric(20, 2))
    accrued_expenses = Column(Numeric(20, 2))
    short_term_debt = Column(Numeric(20, 2))
    capital_lease_obligations_current = Column(Numeric(20, 2))
    capital_lease_obligations_non_current = Column(Numeric(20, 2))
    tax_payables = Column(Numeric(20, 2))
    deferred_revenue = Column(Numeric(20, 2))
    other_current_liabilities = Column(Numeric(20, 2))
    total_current_liabilities = Column(Numeric(20, 2))

    long_term_debt = Column(Numeric(20, 2))
    deferred_revenue_non_current = Column(Numeric(20, 2))
    deferred_tax_liabilities_non_current = Column(Numeric(20, 2))
    other_non_current_liabilities = Column(Numeric(20, 2))
    total_non_current_liabilities = Column(Numeric(20, 2))
    other_liabilities = Column(Numeric(20, 2))
    capital_lease_obligations = Column(Numeric(20, 2))
    total_liabilities = Column(Numeric(20, 2))

    # Equity
    treasury_stock = Column(Numeric(20, 2))
    preferred_stock = Column(Numeric(20, 2))
    common_stock = Column(Numeric(20, 2))
    retained_earnings = Column(Numeric(20, 2))
    additional_paid_in_capital = Column(Numeric(20, 2))
    accumulated_other_comprehensive_income_loss = Column(Numeric(20, 2))
    other_total_stockholders_equity = Column(Numeric(20, 2))
    total_stockholders_equity = Column(Numeric(20, 2))
    total_equity = Column(Numeric(20, 2))
    minority_interest = Column(Numeric(20, 2))
    total_liabilities_and_total_equity = Column(Numeric(20, 2))

    total_investments = Column(Numeric(20, 2))
    total_debt = Column(Numeric(20, 2))
    net_debt = Column(Numeric(20, 2))

    # Metadata
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index('ix_balance_sheets_symbol_date', 'symbol', 'date'),
        Index('ix_balance_sheets_fiscal_year', 'fiscal_year'),
    )


class CashFlow(Base):
    """Cash flow statement data for all companies"""
    __tablename__ = 'cash_flows'

    symbol = Column(String(20), ForeignKey('companies.symbol'), primary_key=True)
    date = Column(Date, primary_key=True)
    period = Column(String(10), primary_key=True)

    reported_currency = Column(String(10))
    cik = Column(String(20))
    filing_date = Column(Date)
    accepted_date = Column(DateTime)
    fiscal_year = Column(Integer)

    # Operating activities
    net_income = Column(Numeric(20, 2))
    depreciation_and_amortization = Column(Numeric(20, 2))
    deferred_income_tax = Column(Numeric(20, 2))
    stock_based_compensation = Column(Numeric(20, 2))
    change_in_working_capital = Column(Numeric(20, 2))
    accounts_receivables = Column(Numeric(20, 2))
    inventory = Column(Numeric(20, 2))
    accounts_payables = Column(Numeric(20, 2))
    other_working_capital = Column(Numeric(20, 2))
    other_non_cash_items = Column(Numeric(20, 2))
    net_cash_provided_by_operating_activities = Column(Numeric(20, 2))

    # Investing activities
    investments_in_property_plant_and_equipment = Column(Numeric(20, 2))
    acquisitions_net = Column(Numeric(20, 2))
    purchases_of_investments = Column(Numeric(20, 2))
    sales_maturities_of_investments = Column(Numeric(20, 2))
    other_investing_activities = Column(Numeric(20, 2))
    net_cash_provided_by_investing_activities = Column(Numeric(20, 2))

    # Financing activities
    net_debt_issuance = Column(Numeric(20, 2))
    long_term_net_debt_issuance = Column(Numeric(20, 2))
    short_term_net_debt_issuance = Column(Numeric(20, 2))
    net_stock_issuance = Column(Numeric(20, 2))
    net_common_stock_issuance = Column(Numeric(20, 2))
    common_stock_issuance = Column(Numeric(20, 2))
    common_stock_repurchased = Column(Numeric(20, 2))
    net_preferred_stock_issuance = Column(Numeric(20, 2))
    net_dividends_paid = Column(Numeric(20, 2))
    common_dividends_paid = Column(Numeric(20, 2))
    preferred_dividends_paid = Column(Numeric(20, 2))
    other_financing_activities = Column(Numeric(20, 2))
    net_cash_provided_by_financing_activities = Column(Numeric(20, 2))

    # Summary
    effect_of_forex_changes_on_cash = Column(Numeric(20, 2))
    net_change_in_cash = Column(Numeric(20, 2))
    cash_at_end_of_period = Column(Numeric(20, 2))
    cash_at_beginning_of_period = Column(Numeric(20, 2))

    operating_cash_flow = Column(Numeric(20, 2))
    capital_expenditure = Column(Numeric(20, 2))
    free_cash_flow = Column(Numeric(20, 2))
    income_taxes_paid = Column(Numeric(20, 2))
    interest_paid = Column(Numeric(20, 2))

    # Metadata
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index('ix_cash_flows_symbol_date', 'symbol', 'date'),
        Index('ix_cash_flows_fiscal_year', 'fiscal_year'),
    )


class FinancialRatio(Base):
    """Financial ratios for all companies"""
    __tablename__ = 'financial_ratios'

    symbol = Column(String(20), ForeignKey('companies.symbol'), primary_key=True)
    date = Column(Date, primary_key=True)
    period = Column(String(10), primary_key=True)

    fiscal_year = Column(Integer)
    reported_currency = Column(String(10))

    # Profitability ratios
    gross_profit_margin = Column(Numeric(20, 6))
    ebit_margin = Column(Numeric(20, 6))
    ebitda_margin = Column(Numeric(20, 6))
    operating_profit_margin = Column(Numeric(20, 6))
    pretax_profit_margin = Column(Numeric(20, 6))
    continuous_operations_profit_margin = Column(Numeric(20, 6))
    net_profit_margin = Column(Numeric(20, 6))
    bottom_line_profit_margin = Column(Numeric(20, 6))

    # Activity ratios
    receivables_turnover = Column(Numeric(20, 4))
    payables_turnover = Column(Numeric(20, 4))
    inventory_turnover = Column(Numeric(20, 4))
    fixed_asset_turnover = Column(Numeric(20, 4))
    asset_turnover = Column(Numeric(20, 4))

    # Liquidity ratios
    current_ratio = Column(Numeric(20, 4))
    quick_ratio = Column(Numeric(20, 4))
    solvency_ratio = Column(Numeric(20, 4))
    cash_ratio = Column(Numeric(20, 4))

    # Valuation ratios
    price_to_earnings_ratio = Column(Numeric(20, 4))
    price_to_earnings_growth_ratio = Column(Numeric(20, 4))
    forward_price_to_earnings_growth_ratio = Column(Numeric(20, 4))
    price_to_book_ratio = Column(Numeric(20, 4))
    price_to_sales_ratio = Column(Numeric(20, 4))
    price_to_free_cash_flow_ratio = Column(Numeric(20, 4))
    price_to_operating_cash_flow_ratio = Column(Numeric(20, 4))

    # Leverage ratios
    debt_to_assets_ratio = Column(Numeric(20, 6))
    debt_to_equity_ratio = Column(Numeric(20, 4))
    debt_to_capital_ratio = Column(Numeric(20, 6))
    long_term_debt_to_capital_ratio = Column(Numeric(20, 6))
    financial_leverage_ratio = Column(Numeric(20, 4))

    # Other ratios
    working_capital_turnover_ratio = Column(Numeric(20, 4))
    operating_cash_flow_ratio = Column(Numeric(20, 4))
    operating_cash_flow_sales_ratio = Column(Numeric(20, 6))
    free_cash_flow_operating_cash_flow_ratio = Column(Numeric(20, 6))

    # Coverage ratios
    debt_service_coverage_ratio = Column(Numeric(20, 4))
    interest_coverage_ratio = Column(Numeric(20, 4))
    short_term_operating_cash_flow_coverage_ratio = Column(Numeric(20, 4))
    operating_cash_flow_coverage_ratio = Column(Numeric(20, 4))
    capital_expenditure_coverage_ratio = Column(Numeric(20, 4))
    dividend_paid_and_capex_coverage_ratio = Column(Numeric(20, 4))

    # Dividend ratios
    dividend_payout_ratio = Column(Numeric(20, 6))
    dividend_yield = Column(Numeric(20, 6))
    dividend_yield_percentage = Column(Numeric(20, 6))

    # Per share metrics
    revenue_per_share = Column(Numeric(20, 4))
    net_income_per_share = Column(Numeric(20, 4))
    dividend_per_share = Column(Numeric(20, 4))
    interest_debt_per_share = Column(Numeric(20, 4))
    cash_per_share = Column(Numeric(20, 4))
    book_value_per_share = Column(Numeric(20, 4))
    tangible_book_value_per_share = Column(Numeric(20, 4))
    shareholders_equity_per_share = Column(Numeric(20, 4))
    operating_cash_flow_per_share = Column(Numeric(20, 4))
    capex_per_share = Column(Numeric(20, 4))
    free_cash_flow_per_share = Column(Numeric(20, 4))

    # Other metrics
    net_income_per_ebt = Column(Numeric(20, 6))
    ebt_per_ebit = Column(Numeric(20, 6))
    price_to_fair_value = Column(Numeric(20, 4))
    debt_to_market_cap = Column(Numeric(20, 6))
    effective_tax_rate = Column(Numeric(20, 6))
    enterprise_value_multiple = Column(Numeric(20, 4))

    # Metadata
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index('ix_financial_ratios_symbol_date', 'symbol', 'date'),
        Index('ix_financial_ratios_fiscal_year', 'fiscal_year'),
    )


class KeyMetric(Base):
    """Key financial metrics for all companies"""
    __tablename__ = 'key_metrics'

    symbol = Column(String(20), ForeignKey('companies.symbol'), primary_key=True)
    date = Column(Date, primary_key=True)
    period = Column(String(10), primary_key=True)

    fiscal_year = Column(Integer)
    reported_currency = Column(String(10))

    # Valuation metrics
    market_cap = Column(BigInteger)
    enterprise_value = Column(BigInteger)
    ev_to_sales = Column(Numeric(20, 4))
    ev_to_operating_cash_flow = Column(Numeric(20, 4))
    ev_to_free_cash_flow = Column(Numeric(20, 4))
    ev_to_ebitda = Column(Numeric(20, 4))
    net_debt_to_ebitda = Column(Numeric(20, 4))

    # Liquidity metrics
    current_ratio = Column(Numeric(20, 4))

    # Quality metrics
    income_quality = Column(Numeric(20, 6))
    graham_number = Column(Numeric(20, 4))
    graham_net_net = Column(Numeric(20, 4))

    # Burden metrics
    tax_burden = Column(Numeric(20, 6))
    interest_burden = Column(Numeric(20, 6))

    # Working capital metrics
    working_capital = Column(Numeric(20, 2))
    invested_capital = Column(Numeric(20, 2))

    # Return metrics
    return_on_assets = Column(Numeric(20, 6))
    operating_return_on_assets = Column(Numeric(20, 6))
    return_on_tangible_assets = Column(Numeric(20, 6))
    return_on_equity = Column(Numeric(20, 6))
    return_on_invested_capital = Column(Numeric(20, 6))
    return_on_capital_employed = Column(Numeric(20, 6))

    # Yield metrics
    earnings_yield = Column(Numeric(20, 6))
    free_cash_flow_yield = Column(Numeric(20, 6))

    # Capital allocation metrics
    capex_to_operating_cash_flow = Column(Numeric(20, 6))
    capex_to_depreciation = Column(Numeric(20, 4))
    capex_to_revenue = Column(Numeric(20, 6))

    # Expense ratios
    sales_general_and_administrative_to_revenue = Column(Numeric(20, 6))
    research_and_developement_to_revenue = Column(Numeric(20, 6))  # Note: API has typo "Developement"
    stock_based_compensation_to_revenue = Column(Numeric(20, 6))
    intangibles_to_total_assets = Column(Numeric(20, 6))

    # Average metrics
    average_receivables = Column(Numeric(20, 2))
    average_payables = Column(Numeric(20, 2))
    average_inventory = Column(Numeric(20, 2))

    # Working capital days
    days_of_sales_outstanding = Column(Numeric(20, 2))
    days_of_payables_outstanding = Column(Numeric(20, 2))
    days_of_inventory_on_hand = Column(Numeric(20, 2))
    days_of_inventory_outstanding = Column(Numeric(20, 2))
    operating_cycle = Column(Numeric(20, 2))
    cash_conversion_cycle = Column(Numeric(20, 2))

    # Free cash flow metrics
    free_cash_flow_to_equity = Column(Numeric(20, 2))
    free_cash_flow_to_firm = Column(Numeric(20, 2))

    # Asset value metrics
    tangible_asset_value = Column(Numeric(20, 2))
    net_current_asset_value = Column(Numeric(20, 2))

    # Metadata
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index('ix_key_metrics_symbol_date', 'symbol', 'date'),
    )




if __name__ == "__main__":
    # Example usage
    from sqlalchemy import create_engine
    
    # Replace with your actual database URL
    DATABASE_URL = "postgresql://user:password@localhost:5432/finexus"
    
    engine = create_engine(DATABASE_URL, echo=True)
    create_all_tables(engine)
