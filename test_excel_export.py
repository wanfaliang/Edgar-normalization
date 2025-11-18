"""
Test Excel Export functionality
Export Amazon Q2 2024 statements to Excel
"""
from src.statement_reconstructor import StatementReconstructor
from src.excel_exporter import export_company_to_excel

print("=" * 80)
print("Testing Excel Export with Amazon Q2 2024")
print("=" * 80)

# Create reconstructor
reconstructor = StatementReconstructor(2024, 3)

# Export Amazon Q2 2024
output_file = export_company_to_excel(
    reconstructor=reconstructor,
    cik=1018724,
    adsh='0001018724-24-000130',
    output_path='output/amazon_q2_2024.xlsx',
    company_name='Amazon.com Inc'
)

print("\n" + "=" * 80)
print("✅ EXPORT COMPLETE")
print("=" * 80)
print(f"\nExcel file created: {output_file}")
print("\nYou can now:")
print("1. Open the Excel file to view formatted statements")
print("2. Compare values to EDGAR viewer side-by-side")
print("3. Review metadata sheet for all captured fields")
print("\nEDGAR URL for comparison:")
print("https://www.sec.gov/cgi-bin/viewer?action=view&cik=0001018724&accession_number=0001018724-24-000130&xbrl_type=v")
