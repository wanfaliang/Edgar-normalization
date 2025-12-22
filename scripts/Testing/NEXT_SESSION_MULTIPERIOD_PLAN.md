# Next Session: Multi-Period Extraction Plan

**Session Date:** 2025-11-12 (continued)
**Status:** Issue #1 complete, ready for Issue #2

---

## Current State

### ✅ What Works:
- Faithful reconstruction of financial statements
- Rich metadata capture (18 fields)
- Excel export with professional formatting
- Missing cash balances fixed (instant/duration handling)
- Verified across 4 companies (Amazon, Home Depot, P&G, M&T Bank)

### ❌ What's Missing:
- **Only ONE period extracted per statement**
- EDGAR shows multiple comparative periods
- Need to extract ALL periods for complete product

---

## Issue #2: Multi-Period Extraction

### Problem Statement

Financial statements on EDGAR display multiple periods for comparison:

**Balance Sheet (10-Q):** 2 columns
- Current quarter end (e.g., Jun 30, 2024)
- Prior fiscal year end (e.g., Dec 31, 2023)

**Income Statement (10-Q):** 4 columns
- Current quarter: qtrs=1, ddate=20240630
- Prior year quarter: qtrs=1, ddate=20230630
- YTD current: qtrs=2, ddate=20240630
- YTD prior: qtrs=2, ddate=20230630

**Income Statement (10-K):** 3 columns
- FY 2024: qtrs=4, ddate=20240630
- FY 2023: qtrs=4, ddate=20230630
- FY 2022: qtrs=4, ddate=20220630

**Cash Flow:** Similar to Income Statement

### Current Extraction Logic (Single Period)

```python
# In attach_values()
if stmt_type == 'BS':
    target_ddate = period  # e.g., '20240630'
    target_qtrs = '0'      # ONE period only
elif stmt_type == 'IS':
    target_ddate = period
    target_qtrs = '1' if fp in ['Q1','Q2','Q3'] else '4'  # ONE period
```

**Result:** Only extracts ONE (ddate, qtrs) combination

### New Logic Needed (Multi-Period)

**Step 1:** Identify ALL (ddate, qtrs) combinations present in NUM table for this statement's tags

```python
# Pseudo-code
def identify_periods(stmt_df, num_df):
    """Find all (ddate, qtrs) combinations for this statement"""
    tags = stmt_df['tag'].unique()
    tag_nums = num_df[num_df['tag'].isin(tags)]

    # Filter to consolidated, parent company
    tag_nums = tag_nums[tag_nums['segments'].isna() & tag_nums['coreg'].isna()]

    # Get unique (ddate, qtrs) combinations
    periods = tag_nums[['ddate', 'qtrs']].drop_duplicates()

    # Filter to relevant periods based on stmt_type
    # BS: qtrs=0 only
    # IS/CF: qtrs=1,2,3,4 depending on filing type

    return periods  # List of (ddate, qtrs) tuples
```

**Step 2:** Extract values for EACH period

```python
# Return structure
{
    'periods': [
        {'ddate': '20240630', 'qtrs': '1', 'label': 'Three Months Ended Jun 30, 2024'},
        {'ddate': '20230630', 'qtrs': '1', 'label': 'Three Months Ended Jun 30, 2023'},
        {'ddate': '20240630', 'qtrs': '2', 'label': 'Six Months Ended Jun 30, 2024'},
        {'ddate': '20230630', 'qtrs': '2', 'label': 'Six Months Ended Jun 30, 2023'}
    ],
    'line_items': [
        {
            'tag': 'RevenueFromContractWithCustomerExcludingAssessedTax',
            'plabel': 'Total net sales',
            'values': {
                ('20240630', '1'): 147977000000,
                ('20230630', '1'): 134383000000,
                ('20240630', '2'): 291290000000,
                ('20230630', '2'): 258224000000
            },
            # ... other metadata
        }
    ]
}
```

---

## Implementation Steps

### Phase 1: Core Logic Changes

**File:** `src/statement_reconstructor.py`

**1. Add `identify_periods()` method to StatementReconstructor**
- Input: stmt_df (PRE), num_df (NUM), stmt_type
- Output: List of period dictionaries

**2. Modify `attach_values()` to accept list of periods**
- Loop through each period
- Extract values for each (ddate, qtrs) combination
- Store in multi-period structure

**3. Update `StatementNode` to hold multi-period values**
```python
@dataclass
class StatementNode:
    # ... existing fields
    values: Dict[Tuple[str, str], float] = None  # (ddate, qtrs) -> value
    # Keep single 'value' for backward compatibility
```

**4. Update `reconstruct_statement()` return structure**
```python
return {
    'hierarchy': hierarchy,
    'validation': validation,
    'periods': periods,  # NEW: List of period metadata
    'line_items': line_items,  # Modified: values dict instead of single value
    'flat_data': flat_data,  # Deprecated but kept for compatibility
    'metadata': {...}
}
```

### Phase 2: Excel Export Updates

**File:** `src/excel_exporter.py`

**1. Modify `_export_formatted_statement()` to handle multiple periods**
- Column headers: Period labels (e.g., "Jun 30, 2024", "Jun 30, 2023")
- Each line item: Multiple value columns

**Excel Layout:**
```
                                | Jun 30, 2024 | Jun 30, 2023 |
Line Item                       |              |              |
--------------------------------|--------------|--------------|
Total net sales                 | 147,977      | 134,383      |
Cost of sales                   | 85,283       | 77,386       |
...
```

**2. Update metadata sheet to show period info**
- Add 'period_label' column
- Multiple rows per tag (one per period)

---

## Testing Plan

### Test Cases:

**1. Amazon 10-Q (Q2 2024)**
- Balance Sheet: 2 periods (Jun 30 2024, Dec 31 2023)
- Income Statement: 4 periods (Q2 2024, Q2 2023, YTD 2024, YTD 2023)
- Cash Flow: 2 periods (YTD 2024, YTD 2023)

**2. P&G 10-K (FY 2024)**
- Balance Sheet: 2 periods (Jun 30 2024, Jun 30 2023)
- Income Statement: 3 periods (FY 2024, FY 2023, FY 2022)
- Cash Flow: 3 periods (FY 2024, FY 2023, FY 2022)

### Verification:
- Open Excel files
- Compare to EDGAR viewer column by column
- All periods and values should match exactly

---

## Edge Cases to Handle

1. **Instant vs Duration in CF** (already fixed)
   - Use iord field to determine correct qtrs

2. **Different number of periods per statement**
   - IS might have 4 columns, CF might have 2
   - Handle gracefully

3. **Missing values for some periods**
   - Some tags may not have values for all periods
   - Show empty/blank cells

4. **Period labeling**
   - Generate human-readable labels from ddate/qtrs
   - "Three Months Ended Jun 30, 2024"
   - "Year Ended Jun 30, 2024"

---

## Estimated Effort

- **Core logic changes:** 2-3 hours
- **Excel export updates:** 1-2 hours
- **Testing & debugging:** 1-2 hours
- **Total:** 4-7 hours of focused work

---

## After Multi-Period is Complete

### Then tackle Issue #3: Complete Dataset Download

**Goal:** Download all quarterly datasets from SEC (2009-2025)

**Existing files to review:**
- `src/simple_explorer.py` - downloads one period
- `src/sec_data_explorer.py` - extraction/load with issues

**Plan:**
1. Review existing download logic
2. Build systematic downloader
3. Handle retries, checksums, storage
4. Batch process to test across all quarters

---

## Success Criteria for Phase 1 Complete Product

- [x] Faithful statement reconstruction
- [x] Rich metadata capture
- [x] Excel export capability
- [x] All line items captured (including cash balances)
- [ ] **Multi-period extraction** ← Next milestone
- [ ] **Complete dataset coverage** ← Final milestone

Once these are done, Phase 1 is a complete, production-ready product!

---

**Status:** Ready to implement multi-period extraction
**Next step:** Start with `identify_periods()` method
**Token budget:** ~99k tokens available for continued work
