# Financial Statement Mapping Workflow

This document describes the end-to-end process for mapping XBRL financial statements to standardized fields.

## Overview

```
1. Data Retrieval (DB or txt files → pre, num, tag DataFrames)
       ↓
2. Hierarchy Building (pre DataFrame → StatementNode tree)
       ↓
3. XBRL Calc Graph Loading (SEC EDGAR → 3-step fallback)
       ↓
4. Mark Sum Items (calc_graph → node.is_sum, node.calc_children)
       ↓
5. Build calc_parent_lookup (calc_children → child_tag → parent_line)
       ↓
6. Create line_items (flatten hierarchy, attach parent_line)
       ↓
7. Control Item Identification (find totals → control_lines dict)
       ↓
8. Mapping (patterns → target fields)
       ↓
9. Aggregation (group by target, set has_mapped_parent)
       ↓
10. Residual Calculation (other_assets, other_liabilities, etc.)
       ↓
11. Final Presentation (structured output)
```

---

## Stage 1: Data Retrieval

**File:** `src/statement_reconstructor.py` - `load_filing_data()`

Loads filing data from either database or text files.

### Option A: Database (PostgreSQL)

```python
# Tables used:
edgar_pre  → presentation data (line order, labels, stmt type)
edgar_num  → numeric values (facts with dates, periods)
edgar_tag  → tag definitions (datatype, crdr, iord)
filings    → submission metadata (company name, form type, fiscal year)
```

### Option B: Text Files (SEC bulk downloads)

```python
# Files in {year}q{quarter}/ directory:
pre.txt  → presentation linkbase data
num.txt  → numeric facts
tag.txt  → tag definitions
sub.txt  → submission metadata
```

### Output

```python
filing_data = {
    'pre': DataFrame,  # adsh, report, line, stmt, inpth, tag, plabel, negating
    'num': DataFrame,  # adsh, tag, ddate, qtrs, value, uom, segments, coreg
    'tag': DataFrame,  # tag, datatype, iord, crdr, tlabel, custom
    'sub': Series      # Company metadata (name, form, fy, fp)
}
```

---

## Stage 2: Hierarchy Building

**File:** `src/statement_reconstructor.py` - `_build_hierarchy()`

Builds a tree structure from presentation data.

### Process

1. Filter `pre` DataFrame by statement type (BS, IS, CF) and report number
2. Sort by line number
3. Create `StatementNode` for each row
4. Build parent-child relationships based on indentation level (`inpth`)

### StatementNode Structure

```python
@dataclass
class StatementNode:
    # Core identification
    tag: str              # XBRL tag (e.g., 'Assets', 'Liabilities')
    plabel: str           # Presentation label (e.g., 'Total assets')

    # Position
    line: int             # Line number in statement
    level: int            # Indentation level (from inpth)

    # Values (multi-period)
    values: Dict          # {(ddate, qtrs): value}

    # From TAG table
    datatype: str         # 'monetary', 'shares', etc.
    iord: str             # 'I' (instant) or 'D' (duration)
    crdr: str             # 'C' (credit) or 'D' (debit)

    # Hierarchy
    children: List[StatementNode]
    parent: StatementNode

    # Calc graph (populated later)
    is_sum: bool          # True if parent in calc graph
    calc_children: List   # [(child_tag, weight, plabel), ...]
```

---

## Stage 3: XBRL Calc Graph Loading

**File:** `src/xbrl_loader.py` - `load_calc_graph_with_fallback()`

Fetches and parses XBRL calculation linkbase from SEC EDGAR.

### 3-Step Fallback Chain

1. **Filing-specific calc linkbase** (`*_cal.xml`)
   - Best source - company's own calculation relationships
   - Downloaded from: `https://www.sec.gov/Archives/edgar/data/{cik}/{adsh_no_dash}/`
   - Source label: `"filing"`

2. **Embedded calc linkbase in schema** (`.xsd`)
   - Some filings embed calc links in their schema file
   - Source label: `"schema"`

3. **US-GAAP standard taxonomy**
   - FASB standard taxonomy from xbrl.fasb.org
   - Multiple linkbases combined (balance sheet, income statement, cash flow)
   - Source label: `"us-gaap-{year}"`

### Calc Graph Structure

```python
calc_graph = {
    'us-gaap_Assets': [
        ('us-gaap_AssetsCurrent', 1.0),
        ('us-gaap_AssetsNoncurrent', 1.0)
    ],
    'us-gaap_Liabilities': [
        ('us-gaap_DebtLongtermAndShorttermCombinedAmount', 1.0),
        ('us-gaap_OtherLiabilities', 1.0),
        ('us-gaap_InterestPayableCurrentAndNoncurrent', 1.0)
    ],
    # parent_tag: [(child_tag, weight), ...]
}
```

**Meaning:** `Assets = AssetsCurrent + AssetsNoncurrent` (weights are typically 1.0 or -1.0)

---

## Stage 4: Mark Sum Items

**File:** `src/statement_reconstructor.py` - `_mark_sum_items()`

Marks nodes that are parents in the calc graph.

### Process

For each node in hierarchy:
1. Check if `node.tag` exists as a key in `calc_graph`
2. If yes: set `node.is_sum = True`
3. Copy calc children: `node.calc_children = calc_graph[node.tag]`
4. Enrich with plabel: `[(child_tag, weight, plabel), ...]`

### Example

```
Before: node.tag = 'Liabilities', node.is_sum = False

After:  node.is_sum = True
        node.calc_children = [
            ('us-gaap_DebtLongtermAndShorttermCombinedAmount', 1.0, 'Debt'),
            ('us-gaap_OtherLiabilities', 1.0, 'Other liabilities'),
            ('us-gaap_InterestPayableCurrentAndNoncurrent', 1.0, 'Accrued interest payable')
        ]
```

---

## Stage 5: Build calc_parent_lookup

**File:** `src/statement_reconstructor.py` - `build_calc_parent_lookup()`

Creates reverse lookup: child_tag → parent's line number.

### Process

```python
calc_parent_lookup = {}  # child_tag (lowercase) → parent_line

def build_calc_parent_lookup(node):
    if node.is_sum and node.calc_children:
        parent_line = node.line
        for (child_tag, weight, plabel) in node.calc_children:
            # Normalize: remove prefix, lowercase
            child_tag_lower = normalize_tag(child_tag)

            # If child already has parent, prefer greater line number
            # (higher-level control items have greater line numbers)
            if child_tag_lower not in lookup or parent_line > existing:
                calc_parent_lookup[child_tag_lower] = parent_line
```

### Example

```
Liabilities (line 21) has calc_children: [Debt, OtherLiabilities, AccruedInterestPayable]

calc_parent_lookup = {
    'debtlongtermandshortermcombinedamount': 21,
    'otherliabilities': 21,
    'interestpayablecurrentandnoncurrent': 21
}
```

**Key Point:** This tells us the CALC graph parent, NOT the presentation hierarchy parent.

---

## Stage 6: Create line_items

**File:** `src/statement_reconstructor.py` - `flatten_multi_period()`

Flattens hierarchy into a list with all metadata.

### Output

```python
line_item = {
    # From PRE
    'tag': 'DebtLongtermAndShorttermCombinedAmount',
    'plabel': 'Debt',
    'line': 19,
    'stmt_order': 19,
    'negating': 0,

    # Multi-period values
    'values': {
        'As of Mar 31, 2024': 3211793000000.0,
        'As of Dec 31, 2023': 3150000000000.0
    },

    # From TAG
    'datatype': 'xbrli:monetaryItemType',
    'iord': 'I',
    'crdr': 'C',

    # From calc graph
    'is_sum': True,
    'calc_children': [('us-gaap_ShortTermBorrowings', 1.0), ...],

    # FROM calc_parent_lookup - CRITICAL!
    'parent_line': 21,  # Line number of calc graph parent (Liabilities)
}
```

**CRITICAL:** `parent_line` comes from `calc_parent_lookup`, NOT presentation hierarchy.

---

## Stage 7: Control Item Identification

**File:** `src/map_financial_statements.py` - `find_bs_control_items()`

Identifies structural totals and their line numbers.

### Process

Scans line_items looking for control item patterns:
- `total_assets` - tag='Assets' or plabel contains 'total assets'
- `total_current_assets` - tag='AssetsCurrent' or plabel pattern
- `total_liabilities` - tag='Liabilities' or plabel pattern
- etc.

### Output

```python
control_lines = {
    'total_assets': 15,
    'total_current_assets': 8,         # May be None for unclassified BS
    'total_non_current_assets': 14,    # May be None
    'total_liabilities': 21,
    'total_current_liabilities': None,  # None for unclassified BS
    'total_stockholders_equity': 30,
    'total_liabilities_and_total_equity': 33
}

control_line_nums = {8, 14, 15, 21, 30, 33}  # Set for quick lookup
```

### Strategy Selection

```python
def should_use_strategy2(control_lines):
    # Use Strategy 2 if missing current/non-current splits
    return (control_lines.get('total_current_assets') is None or
            control_lines.get('total_current_liabilities') is None)
```

- **Strategy 1:** Classified balance sheet (has current/non-current sections)
- **Strategy 2:** Unclassified balance sheet (common for financial companies)

---

## Stage 8: Mapping

### Strategy 1: Classified Balance Sheet

**File:** `src/map_financial_statements.py` - `map_bs_item()`

Uses **position** (relative to control lines) AND **patterns**:

```python
def map_bs_item(plabel, line_num, control_lines, ...):
    # Position determines section
    if line_num < total_current_assets:
        # CURRENT ASSETS section
        if 'cash' in plabel:
            return 'cash_and_cash_equivalents'
        if 'receivable' in plabel:
            return 'account_receivables_net'
        # ...

    elif line_num < total_assets:
        # NON-CURRENT ASSETS section
        if 'property' in plabel:
            return 'property_plant_equipment_net'
        # ...
```

### Strategy 2: Unclassified Balance Sheet

**File:** `src/map_financial_statements_strategy2.py` - `map_bs_item_strategy2()`

Uses **patterns only** (no current/non-current position):

```python
def map_bs_item_strategy2(plabel, line_num, control_lines, ...):
    total_liabilities = control_lines.get('total_liabilities', float('inf'))

    # IMPORTANT: For liabilities, check line_num < total_liabilities
    # to exclude equity section items (e.g., AOCI containing "debt")
    if 'debt' in plabel and line_num < total_liabilities:
        return 'long_term_debt'
```

### Skip Logic (Both Strategies)

Items are skipped if parent is a NON-control mapped item:

```python
if not is_control_line and parent_line is not None and parent_line not in control_line_nums:
    continue  # Skip - parent will be mapped instead
```

This prevents double-counting.

---

## Stage 9: Aggregation

**File:** `src/map_financial_statements.py` - `aggregate_by_target()`

Groups mapped items by target and sets `has_mapped_parent`.

### Process

```python
# Step 1: Build set of NON-control mapped line numbers
mapped_non_control_line_nums = set()
for target, sources in target_to_plabels.items():
    for plabel, line_num in sources:
        if line_num not in control_line_nums:
            mapped_non_control_line_nums.add(line_num)

# Step 2: For each target, determine has_mapped_parent
for target, sources in target_to_plabels.items():
    has_mapped_parent = True  # Assume skip

    for plabel, line_num in sources:
        parent_line = item.get('parent_line')

        # If ANY source has parent in control_line_nums (or no parent),
        # then DON'T skip this target
        if parent_line is None or parent_line in control_line_nums:
            has_mapped_parent = False
```

### Key Logic

| parent_line | In control_line_nums? | has_mapped_parent | Skip in residual? |
|-------------|----------------------|-------------------|-------------------|
| None        | N/A                  | False             | No                |
| 21 (total_liabilities) | Yes       | False             | No                |
| 19 (mapped debt)       | No        | True              | Yes               |

---

## Stage 10: Residual Calculation

### Strategy 1

**File:** `src/map_financial_statements.py` - `validate_and_calculate_bs_residuals()`

```python
sections = {
    'other_current_assets': ('total_current_assets', [
        'cash_and_cash_equivalents', 'account_receivables_net',
        'inventory', 'prepaids', ...
    ]),
    'other_current_liabilities': ('total_current_liabilities', [
        'account_payables', 'accrued_expenses', 'accrued_interest_payable',
        'short_term_debt', ...
    ]),
    # ...
}

# Calculate: other_X = total_X - sum(items where has_mapped_parent=False)
```

### Strategy 2

**File:** `src/map_financial_statements_strategy2.py` - `calculate_residuals_strategy2()`

```python
liability_items = [
    'account_payables', 'accrued_expenses', 'accrued_interest_payable',
    'short_term_debt', 'long_term_debt', ...
]

# other_liabilities = total_liabilities - sum(liability_items)
for period in periods:
    total_val = total_liabilities_periods[period]
    sum_val = sum(
        get_value(item, period)
        for item in liability_items
        if item in standardized and not has_mapped_parent
    )
    other_liabilities = total_val - sum_val
```

### Why Skip Items with has_mapped_parent=True?

If an item's parent is also mapped (as a non-control item), its value is already included in the parent's value. Subtracting it again would cause double-counting.

**Example:** If "Debt" maps to `long_term_debt` and has children "Short-term debt" and "Long-term notes" that also got mapped, we should only subtract "Debt", not its children.

---

## Stage 11: Final Presentation

### Standardized Output

```python
standardized = {
    'total_assets': {
        'total_value': 1000000000,
        'period_values': {'As of Mar 31, 2024': 1000000000, ...},
        'source_items': ['Total assets'],
        'has_mapped_parent': False
    },
    'cash_and_cash_equivalents': {...},
    'long_term_debt': {...},
    'other_liabilities': {
        'total_value': 50000000,
        'period_values': {...},
        'source_items': ['(calculated residual)']
    },
    # ...
}
```

---

## Common Issues and Debugging

### Issue: `other_liabilities = total_liabilities`

**Symptom:** No items subtracted in residual calculation.

**Check:**
1. Are mapped targets in `liability_items` list?
2. Is `has_mapped_parent` incorrectly True?
3. Are items mapped to wrong target due to patterns?

### Issue: Item skipped in residual (has_mapped_parent=True incorrectly)

**Debug:**
```python
# Check parent_line for the item
parent_line = item.get('parent_line')

# If parent_line is a control item line, has_mapped_parent should be False
print(f"parent_line: {parent_line}")
print(f"control_line_nums: {control_line_nums}")
print(f"parent in control_line_nums: {parent_line in control_line_nums}")
```

### Issue: Wrong items mapped to a target

**Example:** "AOCI, Debt Securities..." mapped to `long_term_debt`

**Fix:** Add position check `line_num < total_liabilities` to exclude equity section.

---

## Key Files Reference

| File | Key Functions |
|------|---------------|
| `src/statement_reconstructor.py` | `load_filing_data()`, `_build_hierarchy()`, `_mark_sum_items()`, `build_calc_parent_lookup()` |
| `src/xbrl_loader.py` | `load_calc_graph_with_fallback()`, `load_us_gaap_calc_linkbase()` |
| `src/map_financial_statements.py` | `find_bs_control_items()`, `map_bs_item()`, `aggregate_by_target()`, `validate_and_calculate_bs_residuals()` |
| `src/map_financial_statements_strategy2.py` | `map_bs_item_strategy2()`, `calculate_residuals_strategy2()` |

---

## Glossary

| Term | Definition |
|------|------------|
| `calc_graph` | Parent-child relationships from XBRL calculation linkbase |
| `calc_parent_lookup` | Reverse lookup: child_tag → parent's line number |
| `parent_line` | Line number of the CALC GRAPH parent (NOT presentation hierarchy) |
| `control_line_nums` | Set of line numbers for control items (totals) |
| `mapped_non_control_line_nums` | Set of line numbers for mapped non-control items |
| `has_mapped_parent` | True if parent_line is a mapped non-control item → skip in residual |
| `is_sum` | True if node is a parent in calc graph (has calc_children) |
| Strategy 1 | Classified balance sheet (has current/non-current sections) |
| Strategy 2 | Unclassified balance sheet (no current/non-current splits) |
