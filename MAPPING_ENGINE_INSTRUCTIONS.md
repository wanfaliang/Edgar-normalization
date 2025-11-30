# Financial Statement Mapping Engine - Complete Instructions

## Foundations

### 1. Infrastructure (Already Built)
- **Database**: PostgreSQL with `companies` and `filings` tables
- **XBRL Data**: Downloaded quarterly filings (num.txt, pre.txt, sub.txt, tag.txt)
- **StatementReconstructor**: Phase 1 complete - reconstructs statements from XBRL as they appear in filings
  - Outputs: line items with plabels, tags, values (multi-period), datatype, statement order
  - Already has Excel export capability (reconstructed view only)

### 2. CSV Specification (The Source of Truth)
- **File**: `docs/Plabel_Investigation_v4.csv`
- **Purpose**: Defines the universal standardized schema
- **Structure**:
  - Column 1: **Field Names in DB** - Exact standardized field names (e.g., `net_income`, `accounts_receivables`)
  - Column 2: By Calculation - Calculation rules for derived fields
  - Column 3: Target - Human-readable labels
  - Column 4: **Common Variations** - Matching patterns (e.g., `[contains 'net income' or 'net earnings']`)
  - Column 5: Statements - Statement type (balance sheet, income statement, cash flow statement)

### 3. Pattern Parser (Available but NOT Used)
- **File**: `src/pattern_parser.py`
- **Purpose**: Can dynamically parse CSV patterns
- **Decision**: We CODE patterns manually in Python, use CSV as reference to understand patterns
- **Why**: Better control, explicit logic, easier to debug

## Goals

### Primary Goal
Map company-specific XBRL filings to a universal standardized schema defined in the CSV.

### Success Metrics
- **Unique standardized targets**: Number of distinct standardized fields populated (NOT coverage %)
- **Field name accuracy**: All returns must exactly match CSV column 1
- **Pattern accuracy**: All matching logic must exactly follow CSV column 4
- **Multi-period support**: Handle any number of periods dynamically

### Outputs
1. **Standardized financial statements** with hierarchical structure
2. **Excel export** showing reconstructed and standardized side-by-side
3. **Aggregation** of multiple source items to single standardized targets

## Architecture

### Data Flow
```
XBRL Filings → StatementReconstructor → Mapping Engine → Standardized Schema → Excel Export
                (Phase 1 - Complete)    (Phase 2 - Current)
```

### Components

#### 1. Control Item Identification
**Purpose**: Find key line items that divide statement sections and enable position-based matching

**Critical**: This is STEP 1 - must be done BEFORE mapping

**Balance Sheet Control Items** - `find_bs_control_items(line_items)`:
Returns dict with line numbers for 8 items:
1. `total_current_assets` (required) - CSV line 10
2. `total_non_current_assets` - CSV line 20
3. `total_assets` (required) - CSV line 21
4. `total_current_liabilities` (required) - CSV line 32
5. `total_liabilities` - CSV line 41
6. `total_stockholders_equity` (required) - CSV line 49
7. `total_equity` - CSV line 50
8. `total_liabilities_and_total_equity` (required) - CSV line 53

**Income Statement Control Items** - `find_is_control_items(line_items)`:
Returns dict with line numbers for 8 items:
1. `revenue` - CSV line 54
2. `operating_income` - CSV line 69
3. `income_tax_expense` (required) - CSV line 72
4. `net_income` (required) - CSV line 75
5. `eps` (required) - CSV line 78 - **Requires datatype = perShare**
6. `eps_diluted` (required) - CSV line 79 - **Requires datatype = perShare**
7. `weighted_average_shares_outstanding` - CSV line 80 - **Requires datatype = shares**
8. `weighted_average_shares_outstanding_diluted` - CSV line 81 - **Requires datatype = shares**

**Note**: Items 5-8 require checking the `datatype` metadata from the item

**Cash Flow Control Items** - `find_cf_control_items(line_items)`:
Returns dict with line numbers for 6 items:
1. `net_income` (required) - CSV line 93
2. `net_cash_provided_by_operating_activities` (required) - CSV line 117
3. `net_cash_provided_by_investing_activities` (required) - CSV line 126
4. `net_cash_provided_by_financing_activities` (required) - CSV line 152
5. `cash_at_beginning_of_period` (required) - CSV line 156
6. `cash_at_end_of_period` (required) - CSV line 155

**Implementation Rules**:
1. Each control item uses EXACT pattern from CSV column 4
2. Items marked (required) are essential for statement processing
3. All patterns must be implemented exactly as specified in CSV
4. For Income Statement items requiring datatype, must extract `item.get('datatype')` and check it
5. Control items are found in FIRST pass through line_items
6. Mapping happens in SECOND pass using control item line numbers

#### 2. Section Classification
**Purpose**: Classify each line item into sections based on control items

**Functions**:
- `classify_bs_section(line_num, control_lines)` - Returns section name
- `classify_is_section(line_num, control_lines)` - Returns section name
- `classify_cf_section(line_num, control_lines)` - Returns section name

#### 3. Mapping Functions
**Purpose**: Map source plabels to standardized field names

**Functions**:
- `map_bs_item(plabel, line_num, control_lines)` - Returns field name or None
- `map_is_item(plabel, line_num, control_lines, datatype=None)` - Returns field name or None
- `map_cf_item(plabel, line_num, control_lines)` - Returns field name or None

**Critical Requirements**:
1. Return values MUST exactly match CSV column 1 field names
2. Pattern logic MUST exactly follow CSV column 4
3. Use `line_num` and `control_lines` for position checking
4. Use `datatype` parameter when CSV pattern specifies it (e.g., `[datatype = perShare]`)

#### 4. Aggregation
**Purpose**: Combine multiple source items mapped to same target

**Function**: `aggregate_by_target(target_to_plabels, line_items)`

**Requirements**:
- Track values for EACH period separately in `period_values` dict
- Maintain list of source items for transparency
- Support dynamic number of periods

#### 5. Structure Definitions
**Purpose**: Define hierarchical layout for Excel export

**Functions**:
- `get_balance_sheet_structure()` - Returns list of structure elements
- `get_income_statement_structure()` - Returns list of structure elements
- `get_cash_flow_structure()` - Returns list of structure elements

**Critical**: Field names in structures MUST exactly match CSV column 1

#### 6. Excel Export
**Purpose**: Create workbooks with side-by-side views

**Function**: `create_excel_workbook(results, company_name, ticker)`

**Layout per sheet**:
- Left side: Reconstructed (as-filed)
- Separator column
- Right side: Standardized (with hierarchical structure)
- All periods shown dynamically

## Step-by-Step Process

### For Each Statement Type (BS, IS, CF):

1. **Reconstruct Statement**
   ```python
   result = reconstructor.reconstruct_statement_multi_period(cik, adsh, stmt_type)
   line_items = result['line_items']
   periods = result['periods']
   ```

2. **Identify Control Items** (FIRST PASS)
   ```python
   control_lines = find_bs_control_items(line_items)
   # Returns: {'total_current_assets': 15, 'total_assets': 28, ...}
   ```

3. **Map Each Line Item** (SECOND PASS)
   ```python
   for item in line_items:
       plabel = item['plabel']
       line_num = item['stmt_order']
       datatype = item.get('datatype')  # For IS only

       target = map_bs_item(plabel, line_num, control_lines)
       # Returns: 'cash_and_cash_equivalents' or None
   ```

4. **Aggregate by Target**
   ```python
   standardized = aggregate_by_target(target_to_plabels, line_items)
   # Returns: {'cash_and_cash_equivalents': {'period_values': {...}, 'source_items': [...]}}
   ```

5. **Build Structure and Export**
   ```python
   structure = get_balance_sheet_structure()
   create_excel_workbook(results, company_name, ticker)
   ```

## Critical Implementation Rules

### Rule 1: Field Names from CSV Column 1
**Always return EXACT field names from CSV column 1**

Examples:
- CSV line 93: `net_income` ← Return this
- CSV line 105: `accounts_receivables` ← Return this (NOT `accounts_receivable_change`)
- CSV line 78: `eps` ← Return this (NOT `earnings_per_share_basic`)

### Rule 2: Patterns from CSV Column 4
**Implement patterns EXACTLY as specified in CSV column 4**

Example from CSV line 93:
- Pattern: `[contains 'net income' or 'net earnings' or 'net income (loss)']`
- Implementation:
  ```python
  if 'net income' in p or 'net earnings' in p or 'net income (loss)' in p:
      return 'net_income'
  ```

### Rule 3: Position-Based Matching
**Many patterns require position checking using control items**

Example from CSV line 18:
- Pattern: `[contains 'deferred' and (contains 'tax' or contains 'taxes')] and [position_before # total_assets]`
- Implementation:
  ```python
  if 'deferred' in p and ('tax' in p or 'taxes' in p) and line_num < total_assets:
      return 'deferred_tax_assets'
  ```

**Note**: Control items must be identified FIRST to enable position checking

### Rule 4: Datatype Metadata
**Use datatype to distinguish similar items when CSV specifies it**

Example from CSV lines 78-81:
- Line 78: `eps` - Pattern: `min{[contains 'basic'] and [datatype = perShare]}`
- Line 80: `weighted_average_shares_outstanding` - Pattern: `[contains 'basic'] and [datatype = shares]`
- Implementation:
  ```python
  if 'basic' in p:
      if datatype == 'perShare':
          return 'eps'
      elif datatype == 'shares':
          return 'weighted_average_shares_outstanding'
  ```

### Rule 5: AND vs OR Logic
**Pay attention to operators - `and` requires ALL conditions, `or` requires ANY**

- `[contains 'a' and contains 'b']` → Both must be present
- `[contains 'a' or contains 'b']` → Either can be present
- `([contains 'a' or 'b']) and [contains 'c']` → (a OR b) AND c

### Rule 6: Min Selector
**Pattern `min{...}` means select item with minimum value matching pattern**

Example from CSV line 78:
- Pattern: `min{[contains 'basic'] and [datatype = perShare]}`
- Meaning: Among all items matching the pattern, select the one with minimum value
- Implementation: For now, just match the pattern (min selection in aggregation)

### Rule 7: Multi-Period Support
**Always track values per period, never assume single period**

```python
# Wrong:
value = item['values'][0]

# Right:
period_values = {}
for period_label, value in item['values'].items():
    if value and not pd.isna(value):
        period_values[period_label] = value
```

### Rule 8: Structure Field Names Must Match
**Field names in structure definitions MUST match mapping function returns**

If mapping function returns `'net_income'`, structure must use:
```python
{'type': 'item', 'field': 'net_income', 'label': 'Net Income'}
```

## Common Mistakes to Avoid

1. **Making up field names** - Always use CSV column 1 exactly
2. **Ignoring position checks** - Many patterns require `position_before` or `position_after`
3. **Wrong AND/OR logic** - Carefully implement boolean operators from patterns
4. **Forgetting datatype** - Income statement EPS/shares require datatype checks
5. **Missing control items** - Must identify control items BEFORE mapping
6. **Single period assumption** - Always handle multiple periods
7. **Mapping ≠ Success** - Mapping to wrong field name is failure
8. **Structure mismatch** - Structure field names must match mapping returns

## Testing Approach

### Test on MSFT (CIK: 789019, ADSH: 0000950170-24-118967)

Expected results:
- Balance Sheet: 30+ unique targets
- Income Statement: 15+ unique targets (with datatype fixes)
- Cash Flow: 25+ unique targets

### Validation:
1. Check field names match CSV column 1 exactly
2. Verify patterns work correctly (review mappings output)
3. Confirm Excel shows both reconstructed and standardized
4. Verify all periods appear in Excel
5. Check aggregation correctly sums multiple source items

## Files Modified

### Main file:
- `map_financial_statements.py` - Complete mapping engine

### Supporting files (reference only):
- `map_balance_sheet_v2.py` - Example of pattern-based matching (reference)
- `map_cash_flow_v2.py` - Example of pattern-based matching (reference)
- `src/pattern_parser.py` - Available but not used

### CSV specification:
- `docs/Plabel_Investigation_v4.csv` - The source of truth

## Summary

**The entire mapping system must follow this principle:**

1. CSV column 1 = What to return (exact field names)
2. CSV column 4 = How to match (pattern logic)
3. Control items FIRST, then mapping
4. Position checks require control item line numbers
5. Datatype when CSV specifies it
6. Multi-period always
7. Structure field names = Mapping return values

**Success = Populating as many unique standardized fields as possible with correct values from correct source items.**
