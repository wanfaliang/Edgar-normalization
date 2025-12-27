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

## line items are dictionaries, not objects. Access with:

  item.get('is_sum', False)    # or item['is_sum']
  item.get('parent_line')
  item.get('calc_children', [])
  item.get('plabel')
  item.get('tag')
  item.get('stmt_order')

  Not item.is_sum.


### Check if root (no parent)
  if item.get('parent_line') is None:
      # it's a root item

### Get parent line number
  parent = item.get('parent_line')  # returns line number or None

  Available keys from reconstructor:
  - parent_line - parent's line number (None if root)
  - is_sum - True if has calc children
  - calc_children - list of [(child_tag, weight, plabel), ...]
  - stmt_order - line number
  - plabel, tag, values, etc.

## IS Mapping Reliability Hierarchy

1. **CRDR** (most reliable) - deterministic accounting attribute
   - 'C' = Credit = addition (revenue/income)
   - 'D' = Debit = deduction (expense/cost)
   - Example: "Cost of revenue" has 'D', so it's expense, not revenue

2. **parent_line** - structural relationship from calc graph
   - Identifies where item belongs in hierarchy
   - Example: If parent is "Total expenses", item is an expense

3. **is_sum** - identifies subtotals vs. line items
   - True = this is a calculated total with children
   - False = this is a leaf item

4. **Pattern matching** (least reliable) - depends on company naming
   - Companies use arbitrary labels
   - Same concept may have different names across filings

### Why CRDR is superior to label matching

Label matching accuracy depends on companies' professional rigorousness.
CRDR is reliably deterministic - based on fundamental accounting rules.

| Label | CRDR | Actual Type |
|-------|------|-------------|
| "Cost of revenue" | D | Expense (deduction) |
| "Revenue" | C | Revenue (addition) |
| "Cost of sales" | D | Expense |
| "Net sales" | C | Revenue |

Pattern matching on "revenue" alone would misclassify "Cost of revenue" as revenue.
With CRDR, we know immediately it's a deduction.

## IS Mapping Rules

### Revenue
1. **Pattern**: contains 'revenue' or 'sales'
2. **Parent check**: parent AND grandparent don't contain 'revenue' (get top-level, not sub-components)
3. **CRDR**: must be 'C' (Credit = addition)

Order for efficiency (fastest filters first):
1. CRDR check (quick)
2. Pattern match
3. Parent check (more expensive)