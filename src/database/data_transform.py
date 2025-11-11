"""
Data Transformation Utilities
Converts FMP API responses (camelCase) to database model format (snake_case)
"""
import re
from typing import Dict, Any, List
from datetime import datetime


def camel_to_snake(camel_str: str) -> str:
    """
    Convert camelCase string to snake_case
    Handles acronyms properly (EBT, EBITDA, etc.)

    Args:
        camel_str: String in camelCase format

    Returns:
        String in snake_case format

    Examples:
        >>> camel_to_snake('fillingDate')
        'filling_date'
        >>> camel_to_snake('reportedCurrency')
        'reported_currency'
        >>> camel_to_snake('ebitda')
        'ebitda'
        >>> camel_to_snake('netIncomePerEBT')
        'net_income_per_ebt'
        >>> camel_to_snake('evToEBITDA')
        'ev_to_ebitda'
    """
    # Step 1: Insert underscore between lowercase and digit
    # Handles: 'value2' -> 'value_2'
    s1 = re.sub('([a-z])([0-9])', r'\1_\2', camel_str)

    # Step 2: Insert underscore between digit sequences and uppercase
    # Handles: 'value_13F' -> 'value_13_F'
    s2 = re.sub('([0-9]+)([A-Z])', r'\1_\2', s1)

    # Step 3: Insert underscore between lowercase and uppercase
    # Handles: 'numberOf' -> 'number_Of'
    s3 = re.sub('([a-z])([A-Z])', r'\1_\2', s2)

    # Step 4: Insert underscore between consecutive capitals followed by lowercase
    # Handles: 'HTMLParser' -> 'HTML_Parser', 'EBITDA' stays 'EBITDA'
    s4 = re.sub('([A-Z]+)([A-Z][a-z])', r'\1_\2', s3)

    return s4.lower()


def transform_keys(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform all keys in a dictionary from camelCase to snake_case

    Args:
        data: Dictionary with camelCase keys

    Returns:
        Dictionary with snake_case keys
    """
    return {camel_to_snake(key): value for key, value in data.items()}


def transform_income_statement(api_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform FMP income statement API response to match IncomeStatement model

    Args:
        api_data: Raw API response data

    Returns:
        Transformed data ready for database insertion
    """
    return transform_keys(api_data)


def transform_balance_sheet(api_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform FMP balance sheet API response to match BalanceSheet model

    Args:
        api_data: Raw API response data

    Returns:
        Transformed data ready for database insertion
    """
    return transform_keys(api_data)


def transform_cash_flow(api_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform FMP cash flow API response to match CashFlow model

    Args:
        api_data: Raw API response data

    Returns:
        Transformed data ready for database insertion
    """
    return transform_keys(api_data)


def transform_key_metrics(api_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform FMP key metrics API response to match KeyMetric model

    Args:
        api_data: Raw API response data

    Returns:
        Transformed data ready for database insertion
    """
    return transform_keys(api_data)


def transform_financial_ratios(api_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform FMP financial ratios API response to match FinancialRatio model

    Args:
        api_data: Raw API response data

    Returns:
        Transformed data ready for database insertion
    """
    return transform_keys(api_data)


def transform_price_data(api_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform FMP price data API response to match PriceDaily/PriceMonthly model

    Args:
        api_data: Raw API response data

    Returns:
        Transformed data ready for database insertion
    """
    return transform_keys(api_data)


def transform_batch(api_data_list: List[Dict[str, Any]],
                   transform_func=transform_keys) -> List[Dict[str, Any]]:
    """
    Transform a list of API responses

    Args:
        api_data_list: List of raw API response dictionaries
        transform_func: Transformation function to apply (default: transform_keys)

    Returns:
        List of transformed dictionaries
    """
    return [transform_func(item) for item in api_data_list]


# Example usage
if __name__ == "__main__":
    # Example API response
    sample_income_statement = {
        "date": "2023-09-30",
        "symbol": "AAPL",
        "reportedCurrency": "USD",
        "cik": "0000320193",
        "fillingDate": "2023-11-03",
        "acceptedDate": "2023-11-02 18:08:27",
        "calendarYear": "2023",
        "period": "FY",
        "revenue": 383285000000,
        "costOfRevenue": 214137000000,
        "grossProfit": 169148000000,
        "grossProfitRatio": 0.441,
        "ebitda": 125820000000,
        "netIncome": 96995000000
    }

    # Transform it
    transformed = transform_income_statement(sample_income_statement)

    print("Original keys:")
    print(list(sample_income_statement.keys())[:5])
    print("\nTransformed keys:")
    print(list(transformed.keys())[:5])
    print("\nFull transformed data:")
    for key, value in transformed.items():
        print(f"  {key}: {value}")
