import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from statement_reconstructor import StatementReconstructor

# Reconstruct MSFT cash flow
reconstructor = StatementReconstructor(year=2024, quarter=4)
cf_result = reconstructor.reconstruct_statement_multi_period(cik='789019', adsh='0000950170-24-118967', stmt_type='CF')

print("MICROSOFT CASH FLOW LINE ITEMS:")
print("=" * 80)
for i, item in enumerate(cf_result['line_items'], 1):
    print(f"{i:2d}. {item['plabel']}")

print("\n" + "=" * 80)
print(f"Total items: {len(cf_result['line_items'])}")
