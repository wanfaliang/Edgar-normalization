import openpyxl

wb = openpyxl.load_workbook('output/financial_statements/MSFT_789019_financial_statements.xlsx')
ws = wb['Balance Sheet']

print("Balance Sheet Structure:")
print("=" * 80)

# Show first 20 rows, columns A through E
for row in ws.iter_rows(min_row=1, max_row=20, min_col=1, max_col=5, values_only=True):
    # Format each column with fixed width
    formatted = []
    for i, cell in enumerate(row):
        if cell is None:
            formatted.append(' ' * 20)
        elif isinstance(cell, (int, float)):
            formatted.append(f"{cell:>20,.0f}")
        else:
            formatted.append(f"{str(cell)[:20]:<20}")
    print(" | ".join(formatted))
