"""
Verify cash balance fix across all 4 companies
"""
from src.statement_reconstructor import StatementReconstructor

COMPANIES = [
    {'name': 'Amazon', 'cik': 1018724, 'adsh': '0001018724-24-000130'},
    {'name': 'Home Depot', 'cik': 354950, 'adsh': '0000354950-24-000201'},
    {'name': 'P&G', 'cik': 80424, 'adsh': '0000080424-24-000083'},
    {'name': 'M&T Bank', 'cik': 36270, 'adsh': '0001628280-24-034695'}
]

reconstructor = StatementReconstructor(2024, 3)

for company in COMPANIES:
    print(f"\n{'=' * 60}")
    print(f"{company['name']}")
    print('=' * 60)

    result = reconstructor.reconstruct_statement(
        cik=company['cik'],
        adsh=company['adsh'],
        stmt_type='CF'
    )

    line_items = result['line_items']
    cash_items = [item for item in line_items
                  if 'BEGINNING' in item['plabel'].upper() or
                     'END OF PERIOD' in item['plabel'].upper() or
                     'end of period' in item['plabel'].lower()]

    print(f"CF items: {len(line_items)}")
    print(f"Cash balance items found: {len(cash_items)}")
    for item in cash_items:
        print(f"  - {item['plabel'][:60]}...")

print("\n" + "=" * 60)
print("Verification complete!")
print("=" * 60)
