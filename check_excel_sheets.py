"""
Check what sheets are actually in the Excel files
"""

import openpyxl
from pathlib import Path

excel_file = Path('output/complete_statements/The_Home_Depot_Inc_complete.xlsx')

if excel_file.exists():
    wb = openpyxl.load_workbook(excel_file, read_only=True)

    print("Sheets in Excel file:")
    for sheet_name in wb.sheetnames:
        print(f"  - {sheet_name}")

    wb.close()
else:
    print(f"File not found: {excel_file}")
