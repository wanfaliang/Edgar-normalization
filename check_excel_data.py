import openpyxl

wb = openpyxl.load_workbook('output/financial_statements/MSFT_789019_financial_statements.xlsx')
ws = wb['BS - Standardized']

print('First 15 rows of BS - Standardized:')
print()

for row in ws.iter_rows(min_row=1, max_row=15, values_only=True):
    print(row)
