# Testing Framework Documentation

## Overview
This document defines the testing workflow, file structure, and reporting format for the Financial Statement Mapping Engine.

**Last Updated:** 2024-11-27
**Version:** 1.0

---

## File Structure

```
/src/                           # Core engine code ONLY
  - statement_reconstructor.py  # Phase 1: Statement reconstruction
  - map_financial_statements.py # Phase 2: Mapping engine
  - excel_exporter.py           # Excel export utilities
  - period_discovery.py         # Multi-period discovery
  - config.py                   # Database configuration

/scripts/                       # All test and utility scripts
  - test_control_items.py       # Single company control item test
  - batch_test_control_items.py # Batch test across multiple companies
  - debug_*.py                  # Debugging utilities

/output/
  /financial_statements/        # Generated financial statements
    # Naming: {TICKER}_{PERIOD}_{TIMESTAMP}.xlsx
    # Example: MSFT_2024Q3_20241127_143022.xlsx

  /results/                     # Test results and reports
    # Naming: {DESCRIPTION}_{TIMESTAMP}.xlsx
    # Example: control_items_test_20241127_143022.xlsx

/docs/                          # Documentation
  - MAPPING_ENGINE_INSTRUCTIONS.md  # Master architecture doc
  - TESTING_FRAMEWORK.md            # This file
  - Plabel_Investigation_v4.csv     # CSV specification (source of truth)

/tests/                         # Unit tests (future)
```

---

## Testing Workflow

### Phase 1: Control Item Identification Testing

**Goal:** Validate that control items are correctly identified across diverse companies.

**Process:**
1. Select 50 diverse companies across industries
2. Run batch test script
3. Generate Excel report with results matrix
4. Review failures and pattern issues
5. Fix patterns as needed
6. Re-test to verify fixes
7. Document results

### Phase 2: Mapping Function Testing (Future)

**Goal:** Validate that line items are correctly mapped to standardized field names.

### Phase 3: End-to-End Testing (Future)

**Goal:** Validate complete financial statement generation.

---

## Report Format: Excel-Based Matrix

### File Structure
```
Sheet 1: Summary Dashboard
  - Total companies tested
  - Overall success rates (by statement type)
  - Charts and visualizations
  - Test metadata (date, version, etc.)

Sheet 2: Balance Sheet Matrix
  - Rows: Companies (50 rows)
  - Columns: 8 control items
  - Cells: ✓ (success) or ✗ (failed)
  - Cell comments contain details (line_num, plabel, pattern matched)
  - Conditional formatting (green=success, red=failed)
  - Bottom row: Success count and percentage per control item

Sheet 3: Income Statement Matrix
  - Same format as Sheet 2
  - 8 control items

Sheet 4: Cash Flow Matrix
  - Same format as Sheet 2
  - 6 control items

Sheet 5: Failed Items Detail
  - List view of all failures
  - Columns: Company, Ticker, CIK, ADSH, Statement, Control_Item, Reason
  - Sortable and filterable

Sheet 6: Pattern Issues
  - List of pattern-specific problems detected
  - False positives, false negatives
  - Recommendations for fixes
```

### Excel Features Used
- **Conditional Formatting:** Visual success/failure indicators
- **Cell Comments:** Detailed information on hover
- **Formulas:** Auto-calculated statistics
- **Data Validation:** Consistent cell values
- **Freeze Panes:** Keep headers visible
- **Hyperlinks:** Link to detailed logs (future enhancement)

---

## Control Item Definitions

### Balance Sheet (8 items)
1. `total_current_assets` **(REQUIRED)**
2. `total_non_current_assets` (optional)
3. `total_assets` **(REQUIRED)**
4. `total_current_liabilities` **(REQUIRED)**
5. `total_liabilities` (optional)
6. `total_stockholders_equity` **(REQUIRED)**
7. `total_equity` (optional)
8. `total_liabilities_and_total_equity` **(REQUIRED)**

**Required Items:** 5/8

### Income Statement (8 items)
1. `revenue` (optional)
2. `operating_income` (optional)
3. `income_tax_expense` **(REQUIRED)**
4. `net_income` **(REQUIRED)**
5. `eps` **(REQUIRED)** - datatype=perShare
6. `eps_diluted` **(REQUIRED)** - datatype=perShare
7. `weighted_average_shares_outstanding` (optional) - datatype=shares
8. `weighted_average_shares_outstanding_diluted` (optional) - datatype=shares

**Required Items:** 4/8

### Cash Flow (6 items)
1. `net_income` **(REQUIRED)**
2. `net_cash_provided_by_operating_activities` **(REQUIRED)**
3. `net_cash_provided_by_investing_activities` **(REQUIRED)**
4. `net_cash_provided_by_financing_activities` **(REQUIRED)**
5. `cash_at_beginning_of_period` **(REQUIRED)**
6. `cash_at_end_of_period` **(REQUIRED)**

**Required Items:** 6/6

---

## Success Criteria

### Control Item Identification
- **Pass:** ALL required control items found for all 3 statements
- **Acceptable:** 95%+ required items found across all companies
- **Review Needed:** <95% required items found
- **Critical:** False positives detected (wrong items matched)

### Pattern Accuracy
- **No false positives:** Items matched must be semantically correct
- **Consistent results:** Same pattern should work across companies
- **Edge case handling:** Unusual naming conventions handled gracefully

---

## Test Company Selection Criteria

**Diversity Requirements:**
1. **Industry Coverage:** Tech, Retail, Manufacturing, Financial, Healthcare, Energy, Consumer Goods
2. **Market Cap:** Large cap, mid cap, small cap
3. **Filing Types:** 10-K and 10-Q
4. **Fiscal Year Ends:** Various (Jan, Mar, Jun, Sep, Dec)
5. **Complexity:** Simple statements to complex multi-segment reporting
6. **Edge Cases:** Non-standard naming conventions, missing optional items

**Total Companies:** 50

---

## Batch Test Script Requirements

### Input
- List of companies (CIK, ADSH, year, quarter)
- Configuration for report generation

### Processing
1. For each company:
   - Reconstruct BS, IS, CF statements
   - Identify control items
   - Log results (success/failure, line numbers, plabels)
   - Capture any errors/exceptions
2. Aggregate results
3. Generate Excel report

### Output
- Excel file: `control_items_test_{TIMESTAMP}.xlsx`
- Console output: Progress and summary statistics
- Error log: Any exceptions encountered

### Performance
- Progress indicator (company X of 50)
- Estimated time remaining
- Error handling (skip failed companies, continue testing)

---

## Version Control

All test results should be versioned with:
- Timestamp
- Code version/commit hash (future)
- List of companies tested
- Pattern version

This enables:
- Regression testing
- Pattern evolution tracking
- Issue traceability

---

## Future Enhancements

1. **HTML Dashboard:** Interactive web-based visualization
2. **Automated Testing:** CI/CD integration
3. **Pattern Library:** Versioned pattern configs
4. **Issue Tracker:** Link failed tests to GitHub issues
5. **Comparative Analysis:** Compare results across test runs
6. **Performance Metrics:** Track test execution time
