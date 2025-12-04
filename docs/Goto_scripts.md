# This is to reconstruct and export financial reports in Excel file with meta data sheet.
    python src/export_filing.py --ticker UBER --form 10-Q --year 2024 --quarter 3

## The success logging
    Multi-period reconstruction complete!
    Total line items: 26
    Periods: 8
    EDGAR viewer: https://www.sec.gov/cgi-bin/viewer?action=view&cik=0001543151&accession_number=0001543151-24-000036&xbrl_type=v
    ✅ EQ: 26 line items × 8 periods

    📁 Exporting to Excel...
    Output: E:\edgar-explorer\output\filings\UBER TECHNOLOGIES INC_10-Q_2024Q3.xlsx

    Exporting financial statements to Excel...
    Output: E:\edgar-explorer\output\filings\UBER TECHNOLOGIES INC_10-Q_2024Q3.xlsx
    ✅ Export complete!
    Sheets created: 5 formatted + 1 metadata
    ✅ Export complete!
   File size: 25.6 KB
#   Output reconstructed financial statements and mapped out financial statements along with meta data
    python scripts/batch_test_control_items.py --year 2024 --quarter 2
    python scripts/batch_test_control_items.py --year 2024 --quarter 2 --ticker XOM

## Part of the success logging

    Multi-period reconstruction complete!
    Total line items: 8
    Periods: 2
    EDGAR viewer: https://www.sec.gov/cgi-bin/viewer?action=view&cik=0000034088&accession_number=0000034088-24-000029&xbrl_type=v
    ✅ Comprehensive Income: 8 items, 2 periods

    📊 Creating Excel workbook...
   ✅ Excel saved to: output\financial_statements\XOM_34088_financial_statements.xlsx
    ✓ Statements saved

# Filter txt filing files and export to Excel file

##  Filter all the numbers for a specific companies joined by rich meta data
    python scripts/filter_num_with_pre.py data/sec_datasets/extracted/2024q2 --name "NIKE"

##  filter pre.txt by name of a company
    python scripts/filter_pre.py data/sec_datasets/extracted/2024q2/pre.txt --name "NIKE" 

##  filter pre.txt by plain string and output pre table joined by rich fields

    python scripts/filter_pre_by_plabel.py data/sec_datasets/extracted/2024q2/pre.txt --plabel "Total cash, cash equivalents, and marketable securities"

## Convert tag.txt to an Excel file

    python scripts/export_tag.py data/sec_datasets/extracted/2024q2/tag.txt 
