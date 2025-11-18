"""
Discover all statement types available in test filings
"""

from src.statement_reconstructor import StatementReconstructor

COMPANIES = [
    {'name': 'Amazon Q2 2024', 'cik': 1018724, 'adsh': '0001018724-24-000130'},
    {'name': 'Home Depot Q2 2024', 'cik': 354950, 'adsh': '0000354950-24-000201'},
    {'name': 'P&G FY2024', 'cik': 80424, 'adsh': '0000080424-24-000083'},
    {'name': 'M&T Bank Q2 2024', 'cik': 36270, 'adsh': '0001628280-24-034695'}
]

print("="*80)
print("DISCOVERING ALL STATEMENT TYPES IN FILINGS")
print("="*80)

reconstructor = StatementReconstructor(2024, 3)

for company in COMPANIES:
    print(f"\n{'='*80}")
    print(f"{company['name']}")
    print(f"{'='*80}")

    # Load filing data
    filing_data = reconstructor.load_filing_data(company['adsh'])

    # Get unique statement types
    stmt_types = filing_data['pre']['stmt'].unique()

    print(f"\nStatement types found in PRE table:")
    for stmt in sorted(stmt_types):
        # Count line items
        count = len(filing_data['pre'][filing_data['pre']['stmt'] == stmt])
        print(f"  {stmt}: {count} line items")

print(f"\n{'='*80}")
print("Summary: These are all the statement types we should test")
print(f"{'='*80}")
