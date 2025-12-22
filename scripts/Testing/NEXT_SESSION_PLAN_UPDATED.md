# Next Session Plan - Multi-Period Extraction
**Updated:** 2025-11-12 with validated period discovery approach
**Status:** Issue #1 complete, ready for Issue #2

---

## Current Status Summary

### ✅ Completed (Issue #1):
- Rich metadata capture (18 fields)
- Excel export system
- Cash balance extraction (instant vs duration handling)
- Verified across 4 companies (3 fully correct, 1 with beginning balance issue)

### ❌ Remaining Issues:
1. **Home Depot beginning cash incorrect** - Uses July 2023 instead of Jan/Feb 2024
2. **Only extracting ONE period** - Should extract ALL periods (comparative columns)

### 🎯 Root Cause:
Both issues stem from NOT implementing **dynamic period discovery**. Currently hardcoded to extract single (ddate, qtrs) based on SUB metadata.

---

## Validated Approach (from User Investigation)

### **Principle: Discover Periods Dynamically**

Each filing contains different numbers of periods. Don't assume - DISCOVER!

### **Step 1: Period Discovery by Statement Type**

#### **Balance Sheet (Instant, qtrs=0):**
```python
# 1. Get all BS tags from PRE table
bs_tags = pre_df[pre_df['stmt'] == 'BS']['tag'].unique()

# 2. Find all values in NUM for these tags
bs_nums = num_df[num_df['tag'].isin(bs_tags)]
bs_nums = bs_nums[bs_nums['segments'].isna()]  # Filter consolidated

# 3. Find unique ddate values (each = one BS column)
periods = bs_nums['ddate'].unique()

# Result: List of ddate values representing each BS column
# Amazon: ['20240630', '20231231'] → 2 balance sheets
```

#### **Income Statement (Duration, qtrs≠0):**
```python
# 1. Get all IS tags from PRE
is_tags = pre_df[pre_df['stmt'] == 'IS']['tag'].unique()

# 2. Find all values in NUM
is_nums = num_df[num_df['tag'].isin(is_tags)]
is_nums = is_nums[is_nums['segments'].isna()]

# 3. Find unique (ddate, qtrs) combinations
periods = is_nums[['ddate', 'qtrs']].drop_duplicates()

# Result: List of (ddate, qtrs) tuples
# Amazon: [
#   ('20240630', '1'),  # Q2 2024 quarterly
#   ('20230630', '1'),  # Q2 2023 quarterly
#   ('20240630', '2'),  # 2024 YTD
#   ('20230630', '2')   # 2023 YTD
# ] → 4 income statements
```

#### **Cash Flow (Mixed - Duration + Instant):**

**For flow items (most tags, iord=D):**
```python
# Same as Income Statement
cf_tags = pre_df[pre_df['stmt'] == 'CF']['tag'].unique()

# Filter to duration tags only (exclude cash balance tags)
cf_tags_duration = [tag for tag in cf_tags
                    if tag_df[tag_df['tag'] == tag]['iord'].iloc[0] == 'D']

cf_nums = num_df[num_df['tag'].isin(cf_tags_duration)]
cf_nums = cf_nums[cf_nums['segments'].isna()]

periods = cf_nums[['ddate', 'qtrs']].drop_duplicates()

# Amazon example: 6 periods (but typically 2 for display)
```

**For ending cash (iord=I):**
```python
# Ending cash ddate matches the CF period end date
# Just use ddate from the period
ending_ddate = period['ddate']  # e.g., '20240630'
```

**For beginning cash (iord=I) - CRITICAL:**
```python
# INFER the beginning ddate from ending ddate and duration
def calculate_beginning_ddate(ending_ddate: str, qtrs: str) -> str:
    """
    Calculate approximate beginning date for cash balance

    Args:
        ending_ddate: Period end date (e.g., '20240630')
        qtrs: Duration quarters ('1', '2', '3', '4')

    Returns:
        Approximate beginning date
    """
    from datetime import datetime, timedelta

    end_date = datetime.strptime(ending_ddate, '%Y%m%d')

    # Calculate months based on qtrs
    months = int(qtrs) * 3

    # Approximate: subtract months (rough calculation)
    # For 6 months (qtrs=2): ~182 days
    # For 12 months (qtrs=4): ~365 days
    days = months * 30.5  # Approximation

    beginning_date = end_date - timedelta(days=days)

    return beginning_date.strftime('%Y%m%d')

# Then find CLOSEST match in available instant dates
beginning_approx = calculate_beginning_ddate('20240630', '2')
# Result: ~'20231231'

# Find closest actual instant date in NUM table
instant_dates = num_df[num_df['qtrs'] == '0']['ddate'].unique()
beginning_actual = min(instant_dates,
                      key=lambda x: abs(int(x) - int(beginning_approx)))

# For Amazon Q2 2024 (qtrs=2):
# - Calculated: ~20231231
# - Available: [20231231, 20240331, 20240630]
# - Closest: 20231231 ✅
```

---

## Implementation Plan

### **Phase 1: Period Discovery Engine**

**File:** `src/period_discovery.py` (new)

```python
class PeriodDiscovery:
    """Discover all periods present in a filing's financial statements"""

    def discover_periods(self, pre_df, num_df, tag_df, stmt_type):
        """
        Find all unique periods for a statement type

        Returns:
            List of period dicts:
            [
                {
                    'ddate': '20240630',
                    'qtrs': '1',
                    'label': 'Three Months Ended Jun 30, 2024',
                    'type': 'duration'  # or 'instant'
                },
                ...
            ]
        """
        pass

    def infer_beginning_ddate(self, ending_ddate, qtrs, available_dates):
        """
        Infer beginning cash ddate using duration calculation
        and closest match
        """
        pass
```

### **Phase 2: Multi-Period Extraction**

**File:** `src/statement_reconstructor.py` (modify)

**Changes needed:**
1. ✅ Keep current `attach_values()` but make it period-aware
2. ✅ Call it multiple times - once per discovered period
3. ✅ Store values in dict keyed by (ddate, qtrs)

**New structure:**
```python
# StatementNode modification
@dataclass
class StatementNode:
    # ... existing fields ...
    values: Dict[Tuple[str, str], float] = field(default_factory=dict)
    # Key: (ddate, qtrs), Value: amount
    # Example: {('20240630', '1'): 147977000000, ('20230630', '1'): 134383000000}
```

**Modified reconstruct_statement():**
```python
def reconstruct_statement(self, cik, adsh, stmt_type):
    # Step 1: Load data
    filing_data = self.load_filing_data(adsh)

    # Step 2: Build hierarchy (structure - same for all periods)
    hierarchy = self.build_hierarchy(filing_data['pre'], stmt_type)

    # Step 3: DISCOVER PERIODS
    discoverer = PeriodDiscovery()
    periods = discoverer.discover_periods(
        filing_data['pre'],
        filing_data['num'],
        filing_data['tag'],
        stmt_type
    )

    # Step 4: Extract values for EACH period
    for period in periods:
        self.attach_values_for_period(
            hierarchy,
            filing_data['num'],
            filing_data['tag'],
            period
        )

    # Step 5: Create line_items with multi-period values
    line_items = self.flatten_with_periods(hierarchy, periods)

    return {
        'hierarchy': hierarchy,
        'periods': periods,  # List of period metadata
        'line_items': line_items,  # Each item has values dict
        'metadata': {...}
    }
```

### **Phase 3: Excel Export Update**

**File:** `src/excel_exporter.py` (modify)

**Changes:**
1. Read `periods` from result
2. Create column headers for each period
3. Write values for each period in separate columns

**Excel Layout:**
```
Line Item                       | Jun 30, 2024 | Jun 30, 2023 | YTD 2024 | YTD 2023 |
--------------------------------|--------------|--------------|----------|----------|
Total net sales                 | 147,977      | 134,383      | 291,290  | 258,224  |
Cash at beginning               | 73,890       | 50,067       | 73,890   | 50,067   |
Cash at end                     | 71,673       | 48,881       | 71,673   | 48,881   |
```

---

## Testing Strategy

### **Test Cases:**

**1. Amazon 10-Q Q2 2024**
- BS: 2 periods
- IS: 4 periods (Q2 2024, Q2 2023, YTD 2024, YTD 2023)
- CF: 2 periods (YTD 2024, YTD 2023)
- Verify beginning cash uses inferred ddate

**2. Home Depot 10-Q Q2 2024**
- Different fiscal calendar (Feb-Jan)
- Verify beginning cash for fiscal year start (not calendar)
- This is the critical test case!

**3. P&G 10-K FY 2024**
- Annual filing
- IS/CF: 3 years of data
- BS: 2 years

---

## Key Implementation Notes

### **1. Beginning Cash Inference Algorithm:**
```python
# Must handle:
# - Non-month-end dates (Home Depot: July 28)
# - Different fiscal calendars
# - Approximate calculation + closest match approach
```

### **2. Period Labeling:**
```python
def generate_period_label(ddate, qtrs):
    """
    Generate human-readable period labels

    Examples:
    - ('20240630', '0') → 'As of Jun 30, 2024'
    - ('20240630', '1') → 'Three Months Ended Jun 30, 2024'
    - ('20240630', '2') → 'Six Months Ended Jun 30, 2024'
    - ('20240630', '4') → 'Year Ended Jun 30, 2024'
    """
```

### **3. Excel Column Ordering:**
```python
# Order periods logically:
# - Current year before prior years
# - Quarterly before YTD (or vice versa based on company preference)
# May need to analyze PRE table 'line' numbers to determine display order
```

---

## Estimated Effort

- **Period Discovery Engine:** 2-3 hours
- **Multi-Period Extraction:** 2-3 hours
- **Excel Export Updates:** 1-2 hours
- **Testing & Debugging:** 2-3 hours
- **Total:** 7-11 hours

---

## After Completion: Phase 1 Will Be Complete!

✅ Faithful statement reconstruction
✅ Rich metadata capture
✅ All line items (including cash balances)
✅ **Multi-period extraction** ← Final milestone
✅ Professional Excel output
✅ Ready for production use

Then: Download all historical datasets (Issue #3)
Then: Phase 2 - Standardization engine!

---

## Current Session State

**Token usage:** ~83k / 200k remaining
**Ready to implement when you return with investigation findings!**

---

## Questions for Separate Investigation Session:

1. ✅ Validate ddate inference formula for beginning cash
2. ✅ Test across Amazon (calendar year) and Home Depot (fiscal Feb-Jan)
3. ✅ Determine best matching algorithm (closest date vs other methods)
4. What's the typical difference between calculated and actual dates?
5. Are there edge cases where inference fails?

**Bring findings back to continue implementation here! 🚀**
