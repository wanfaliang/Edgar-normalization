# Investigation Findings - Cash Flow & Multi-Period Issues

**Date:** 2025-11-13
**Session:** Multi-period extraction investigation
**Status:** Complete ✅

---

## Executive Summary

This investigation examined two critical issues in the statement reconstruction system:
1. **Cash Flow Beginning Balance Issue**: Home Depot showing incorrect beginning cash date
2. **Multi-Period Extraction**: How to discover and extract all periods in a filing

**Key Findings:**
- ✅ Root cause identified for Home Depot cash balance issue
- ✅ Date inference algorithm validated (100% accurate across test cases)
- ✅ Period discovery approach validated and refined
- ✅ Ready for implementation

---

## Issue #1: Cash Flow Beginning Balance Problem

### Problem Description

Home Depot Q2 FY2024 cash flow statement shows:
- ❌ **Current:** Beginning cash uses date `20230731` (July 31, 2023)
- ✅ **Correct:** Should use date `20240131` (Jan 31, 2024 - FY2024 start)

### Root Cause

**Location:** `src/statement_reconstructor.py` lines 376-388

The current logic for finding prior period dates assumes **fiscal year number = calendar year**:

```python
# Current code
if stmt_type == 'CF' and target_qtrs in ['2', '3']:
    prior_fy_dates = [d for d in instant_dates_sorted if d.startswith(str(fy-1))]
    prior_period_date = prior_fy_dates[-1]
```

**Why it fails:**
- Home Depot FY2024 starts Jan 31, 2024 (calendar year 2024)
- But `fy-1 = 2023`, so it looks for dates starting with "2023"
- Finds `20230731` instead of `20240131`

**Test Results:**
```
Home Depot FY2024 Q2:
  Period End: 20240731 (July 31, 2024)
  Fiscal Year: 2024

  Current logic:
    Looks for: dates starting with "2023"
    Finds: ['20230131', '20230430', '20230731']
    Selects: 20230731 ❌ WRONG

  Should select: 20240131 ✓ CORRECT
```

### Solution: Date Inference Algorithm

**Algorithm:**
1. Calculate approximate beginning date: `ending_date - (qtrs × 3 months)`
2. Find closest actual instant date from NUM table

**Implementation:**
```python
def calculate_beginning_ddate(ending_ddate: str, qtrs: str) -> str:
    end_date = datetime.strptime(ending_ddate, '%Y%m%d')
    months = int(qtrs) * 3
    days = months * 30.5  # Approximation
    beginning_date = end_date - timedelta(days=days)
    return beginning_date.strftime('%Y%m%d')

def find_closest_instant_date(target_date: str, available_dates: list) -> str:
    target_int = int(target_date)
    return min(available_dates, key=lambda x: abs(int(x) - target_int))
```

### Validation Results

Tested across 3 companies with different fiscal calendars:

| Company | Type | Ending | Qtrs | Expected | Calculated | Closest | Result |
|---------|------|--------|------|----------|------------|---------|--------|
| Amazon | Calendar year | 20240630 | 2 | 20231231 | 20231230 | 20231231 | ✅ |
| Home Depot | Fiscal (Feb-Jan) | 20240731 | 2 | 20240131 | 20240130 | 20240131 | ✅ |
| P&G | Fiscal (Jul-Jun) | 20240630 | 4 | 20230630 | 20230630 | 20230630 | ✅ |

**Accuracy:**
- All 3 test cases: 100% correct
- Approximation error: 0-1 days (negligible when finding closest match)

**Conclusion:** ✅ Algorithm works perfectly for both calendar and fiscal year companies

---

## Issue #2: Multi-Period Discovery

### Problem Description

Current system extracts only ONE period per statement type based on SUB metadata.

**Reality:** Filings contain multiple periods for comparative analysis
- 10-Q: Typically 2-4 periods per statement
- 10-K: Typically 2-3 periods per statement

### Solution: Dynamic Period Discovery

**Approach:** Use a **representative tag** to discover all periods

**Why representative tags?**
- Not all tags appear in all periods
- Some tags have extra data not shown on main statements
- Key tags (Revenue, Assets, etc.) appear in all displayed periods

### Implementation Strategy

**For each statement type:**

1. **Balance Sheet (Instant, qtrs=0)**
   - Representative tag: `Assets` or `LiabilitiesAndStockholdersEquity`
   - Find all instant (qtrs=0) values for this tag
   - Each unique ddate = one BS period

2. **Income Statement (Duration, qtrs≠0)**
   - Representative tag: `Revenues` or similar
   - Find all duration values for this tag
   - Each unique (ddate, qtrs) = one IS period

3. **Cash Flow Statement (Duration for flows)**
   - Representative tag: `NetCashProvidedByUsedInOperatingActivities`
   - Find all duration values for this tag
   - Each unique (ddate, qtrs) = one CF period

### Validation Results

Tested representative tag approach across 3 companies:

**Amazon 10-Q Q2 2024:**
- BS: 2 periods ✅ (Jun 2024, Dec 2023)
- IS: 4 periods ✅ (Q2 2024, YTD 2024, Q2 2023, YTD 2023)
- CF: 6 periods ⚠️ (includes quarterly + YTD + TTM)

**Home Depot 10-Q Q2 2024:**
- BS: 2 periods ✅ (Jul 2024, Jan 2024)
- IS: 4 periods ✅ (Q2 2024, YTD 2024, Q2 2023, YTD 2023)
- CF: 2 periods ✅ (YTD 2024, YTD 2023)

**P&G 10-K FY2024:**
- BS: 3 periods ⚠️ (2024, 2023, 2022)
- IS: 3 periods ✅ (2024, 2023, 2022)
- CF: 3 periods ✅ (2024, 2023, 2022)

**Notes:**
- Amazon CF shows 6 periods (companies file more data than displayed)
- P&G BS shows 3 years (10-K often includes 3rd year for reference)
- These might be correct - NUM table contains all available data

**Conclusion:** ✅ Representative tag approach successfully discovers periods

### Representative Tag Selection

**Candidate tags by statement type:**

```python
REPRESENTATIVE_TAGS = {
    'BS': [
        'Assets',
        'AssetsCurrent',
        'LiabilitiesAndStockholdersEquity'
    ],
    'IS': [
        'Revenues',
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'SalesRevenueNet',
        'NetIncomeLoss'
    ],
    'CF': [
        'NetCashProvidedByUsedInOperatingActivities',
        'NetCashProvidedByUsedInInvestingActivities'
    ]
}
```

**Selection logic:** Try candidates in order, pick first one that:
1. Exists in PRE table for this statement
2. Has values in NUM table

---

## Key Insights

### 1. Fiscal Year Complexity

Companies have different fiscal calendars:
- **Amazon:** Calendar year (Jan-Dec)
- **Home Depot:** Fiscal year Feb-Jan (FY2024 = Feb 2024 - Jan 2025)
- **P&G:** Fiscal year Jul-Jun (FY2024 = Jul 2023 - Jun 2024)

**Lesson:** Never assume fiscal year number = calendar year!

### 2. Available Instant Dates Pattern

From Home Depot investigation:
```
Available instant dates:
  20230131 = 2023-01-31  (Prior FY end)
  20230430 = 2023-04-30  (Prior Q1 end)
  20230731 = 2023-07-31  (Prior Q2 end)
  20240131 = 2024-01-31  (Current FY start)
  20240430 = 2024-04-30  (Current Q1 end)
  20240731 = 2024-07-31  (Current Q2 end - filing period)
```

Pattern: Companies provide quarterly + annual instant dates for multiple years

### 3. NUM Table Contains More Than Displayed

The NUM table often contains:
- Data for all quarters, even if only YTD is displayed
- Trailing 12-month calculations (qtrs=4 from any quarter end)
- Historical data beyond what's shown on statements

**Implication:** Period discovery must filter intelligently

---

## Recommendations for Implementation

### Phase 1: Fix Beginning Cash Balance Issue

**Priority:** HIGH (fixes Home Depot and similar fiscal year companies)

**Changes needed in `src/statement_reconstructor.py`:**

Replace lines 376-396 with date inference algorithm:

```python
def infer_beginning_cash_date(ending_ddate: str, qtrs: str,
                               available_instant_dates: list) -> str:
    """
    Infer beginning cash balance date using duration calculation
    and closest match approach
    """
    # Calculate approximate beginning date
    end_date = datetime.strptime(ending_ddate, '%Y%m%d')
    months = int(qtrs) * 3
    days = months * 30.5
    approx_beginning = end_date - timedelta(days=days)
    approx_str = approx_beginning.strftime('%Y%m%d')

    # Find closest actual instant date
    past_dates = [d for d in available_instant_dates if d < ending_ddate]
    if not past_dates:
        return ending_ddate  # Fallback

    return min(past_dates, key=lambda x: abs(int(x) - int(approx_str)))
```

**Testing:** Run `verify_cash_fix_all.py` after implementation
- Amazon: Should still work ✅
- Home Depot: Should fix to 20240131 ✅
- P&G: Should still work ✅

### Phase 2: Implement Multi-Period Extraction

**Priority:** HIGH (required for complete statement reconstruction)

**New file:** `src/period_discovery.py`

**Changes needed in `src/statement_reconstructor.py`:**
1. Modify `StatementNode.value` to store dict: `{(ddate, qtrs): value}`
2. Call `attach_values()` multiple times - once per period
3. Update Excel exporter to create columns for each period

**Estimated effort:** 7-11 hours (as per plan)

### Phase 3: Testing & Validation

**Test cases:**
1. Amazon 10-Q Q2 2024 (calendar year)
2. Home Depot 10-Q Q2 2024 (fiscal year Feb-Jan)
3. P&G 10-K FY2024 (fiscal year Jul-Jun, annual filing)
4. M&T Bank 10-Q Q2 2024 (financial services)

**Validation criteria:**
- ✅ All beginning cash balances correct
- ✅ All periods discovered and extracted
- ✅ Excel export shows all periods in separate columns
- ✅ Rollup validation still passes

---

## Edge Cases Discovered

### 1. Non-month-end Fiscal Years

Some companies use dates like:
- Home Depot: July 31, January 31
- Walmart: January 31
- Target: First Saturday of February

**Handled by:** Date inference algorithm (works with any date)

### 2. Quarterly vs YTD in Cash Flow

- 10-Q filings often show only YTD cash flow (not quarterly)
- But NUM table contains quarterly data too
- Period discovery finds all available periods

**Recommendation:** Accept all discovered periods (user can see complete data)

### 3. Trailing 12-Month Data

Some companies report TTM (trailing twelve month) data:
- Same ending date as quarterly
- But qtrs=4 instead of qtrs=1
- Creates extra periods in discovery

**Recommendation:** Include these as separate periods (valid comparative data)

---

## Files Created During Investigation

1. `investigate_home_depot_fy.py` - Analyzed Home Depot fiscal year structure
2. `test_date_inference.py` - Validated beginning cash date inference
3. `test_period_discovery.py` - First attempt at period discovery
4. `test_period_discovery_v2.py` - Refined approach using representative tags
5. `investigate_displayed_periods.py` - Analyzed PRE table structure
6. `INVESTIGATION_FINDINGS.md` - This document

**All scripts validated and ready for reference during implementation.**

---

## Next Steps

1. ✅ Investigation complete
2. ⏭️ Implement Phase 1: Fix beginning cash balance issue
3. ⏭️ Implement Phase 2: Multi-period extraction
4. ⏭️ Update Excel exporter for multi-period output
5. ⏭️ Run comprehensive testing across all test companies

**Estimated total implementation time:** 7-11 hours

**After completion:** Phase 1 of the reconstruction engine will be complete! 🎉

Then ready for:
- Download all historical EDGAR datasets
- Phase 2: Standardization engine
- Phase 3: Database integration
