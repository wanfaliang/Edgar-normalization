# Income Statement & Cash Flow Statement Mapping Implementation Plan

## Schema Overview

### Balance Sheet (Lines 2-56) - IGNORE
- 55 items from old version
- **Action**: Use our updated version in `map_company_balance_sheet.py`

### Income Statement (Lines 57-95)
- **Total**: 39 items
- **Mappable**: 28 items (lines 57-84)
- **Calculated**: 11 items (lines 85-95) - ignore during mapping
- **Matching Type**: **ACCURATE matching** (exact string variations, no patterns)

### Cash Flow Statement (Lines 96-160)
- **Total**: 65 items
- **Mappable**: 59 items (lines 96-154)
- **Calculated**: 5 items (lines 155-159) - ignore during mapping
- **Matching Type**: **PATTERN matching** (square bracket notation)

---

## Income Statement - Implementation Strategy

### Key Characteristics
1. **No strict control items** - hierarchy can vary by company
2. **Arbitrary levels** - some companies detailed, others aggregated
3. **Changing sum/deduction relationships** - income/expense items flip unpredictably
4. **Less defined items** - many similar "income" and "expense" items
5. **ACCURATE matching required** - no wildcards, exact string variations only

### Critical Items to Identify

#### 1. Revenue (Line 57)
```
Target: revenue
Variations:
  - total revenues
  - net revenue / net revenues
  - revenues
  - net sales / sales
  - Total net sales
  - Total revenues net of interest expense
  - Total revenues net of expense
  - revenues net of expenses
  - Total net revenue
  - Total net sales and revenue
  - Sales to customers
  - Cost of revenue (excluding depreciation and amortization)
  - Total operating revenues
```

#### 2. EPS Items (Lines 81-82)
**eps (Line 81)** - Contains "basic", monetary
```
Variations:
  - earnings per share basic
  - loss per share basic
  - earnings (loss) per share basic
  - earnings per share basic (in dollars)
  - Basic earnings per share (in dollars per share)
  - Net income per share basic
  - Earnings (loss) per common share attributable to XXX common shareholders - basic
  - Basic EPS
  - Net Income Per Common Share - Basic (USD per share)
```

**eps_diluted (Line 82)** - Contains "diluted", monetary
```
Variations:
  - earnings per share diluted
  - loss per share diluted
  - earnings (loss) per share diluted
  - Diluted earnings per share (in dollars per share)
  - Net income per share diluted
  - diluted EPS
  - Net Income Per Common Share - Diluted (USD per share)
```

**Special Rule**: If two EPS items found, take the one attributable to controlling shareholders

#### 3. Share Count Items (Lines 83-84)
**weighted_average_shares_outstanding (Line 83)** - Contains "basic", non-monetary
```
Variations:
  - weighted average common shares outstanding
  - weighted average common shares outstanding basic
  - weighted average common shares outstanding - basic
  - Weighted-average basic shares outstanding (in shares)
  - Basic (in shares)
  - basic
```

**weighted_average_shares_outstanding_diluted (Line 84)** - Contains "diluted", non-monetary
```
Variations:
  - weighted average common shares outstanding diluted
  - weighted average common shares outstanding, diluted
  - Weighted-average diluted shares outstanding (in shares)
  - Diluted (in shares)
  - diluted
```

### Items to Calculate (Ignore During Mapping)
- Line 85: other_adjustments_to_net_income
- Line 86: net_income_deductions
- Line 87: bottom_line_net_income
- Line 88: gross_profit_ratio
- Line 89: ebitda
- Line 90: ebitda_ratio
- Line 91: ebit
- Line 92: ebit_ratio
- Line 93: operating_income_ratio
- Line 94: income_before_tax_ratio
- Line 95: net_income_ratio

### Mapping Challenges

1. **Detail vs Aggregation**
   - Some companies report detailed revenue breakdown (ignore details)
   - Some companies report detailed COGS breakdown (ignore details)
   - Only map items that exist in schema

2. **Hierarchy Variations**
   - No guaranteed order
   - Items can appear at different levels
   - Sum relationships not consistent

3. **Income vs Expense Classification**
   - Same item can be income or expense depending on sign
   - "Other income (expense), net" combines both
   - Need to map regardless of sign

### Implementation Approach

```python
def map_income_statement(line_items, schema_variations):
    """
    Map income statement items using ACCURATE matching
    """
    mapped_items = []
    unmapped_items = []

    for item in line_items:
        plabel = item['plabel']

        # Normalize for exact matching
        plabel_norm = normalize_text_exact(plabel)

        # Try exact match against all schema variations
        target = find_exact_match(plabel_norm, schema_variations)

        if target:
            # Check if this is a calculated item - skip it
            if target in CALCULATED_ITEMS:
                continue

            mapped_items.append({
                'plabel': plabel,
                'target': target,
                'values': item['values']
            })
        else:
            # Check if this is a detail item to ignore
            if should_ignore_detail_item(plabel, item['level']):
                continue

            unmapped_items.append(item)

    return mapped_items, unmapped_items

def normalize_text_exact(text):
    """
    Normalize for exact matching:
    - Case insensitive
    - Plural/singular insensitive
    - Ignore hyphens and commas
    """
    text = text.lower()
    text = text.replace('-', ' ')
    text = text.replace(',', '')
    text = text.replace("'", "")
    # Handle plural/singular
    # Remove parentheticals for variations like (in dollars)
    return text
```

---

## Cash Flow Statement - Implementation Strategy

### Key Characteristics
1. **3 control items** always in same order
2. **Line position determines activity type**
3. **Pattern matching** using square bracket notation
4. **Aggregation into "other_*_activities"** for unmappable items

### Critical Control Items (Always in This Order)

```python
CONTROL_ITEMS = [
    'net_cash_provided_by_operating_activities',  # Line 119
    'net_cash_provided_by_investing_activities',   # Line 128
    'net_cash_provided_by_financing_activities'    # Line 150
]
```

### Activity Classification by Line Position

```python
def classify_cash_flow_item(item_line_num, control_line_nums):
    """
    Classify item based on line position relative to control items

    Args:
        item_line_num: Line number (stmt_order) of the item
        control_line_nums: Dict with keys 'operating', 'investing', 'financing'

    Returns:
        'operating' | 'investing' | 'financing' | 'other'
    """
    if item_line_num < control_line_nums['operating']:
        return 'operating'
    elif item_line_num < control_line_nums['investing']:
        return 'investing'
    elif item_line_num < control_line_nums['financing']:
        return 'financing'
    else:
        return 'other'  # Items after financing (e.g., exchange rate effects)
```

### Pattern Matching Logic

Patterns are in square brackets with boolean logic:

#### Pattern Syntax
- `[contains X]` - plabel contains term X
- `[contains X or Y]` - contains either X or Y
- `[contains X and Y]` - contains both X and Y
- `not [contains X]` - does not contain X
- `[equals to X]` - exact match to X
- `[position line before that of X]` - line number comparison

#### Examples

**Line 96**: `net_income`
```
Pattern: [contains net income or net earnings or net income (loss)]
Logic: plabel_lower contains "net income" OR "net earnings" OR "net income (loss)"
```

**Line 97**: `depreciation_and_amortization`
```
Pattern: [contains depreciation and contains amortization]
Logic: plabel_lower contains "depreciation" AND contains "amortization"
```

**Line 103**: `stock_based_compensation`
```
Pattern: [contains stock-based and contains compensation]
Logic: plabel_lower contains "stock-based" AND contains "compensation"
```

**Line 108**: `accounts_receivables`
```
Pattern: [contains account or accounts and contains receivable or receivables]
Logic: (contains "account" OR "accounts") AND (contains "receivable" OR "receivables")
```

**Line 119**: `net_cash_provided_by_operating_activities`
```
Pattern: [contains cash and contains operating activities] not [contains other or others]
Logic: (contains "cash" AND "operating activities") AND NOT (contains "other" OR "others")
```

### Pattern Matching Implementation

```python
def parse_pattern(pattern_str):
    """
    Parse pattern string into executable logic

    Examples:
        '[contains X and Y]' → lambda text: 'x' in text and 'y' in text
        '[contains X or Y]' → lambda text: 'x' in text or 'y' in text
        '[contains X] not [contains Y]' → lambda text: 'x' in text and 'y' not in text
    """
    # Remove square brackets
    pattern = pattern_str.strip('[]')

    # Split by 'not' first
    if ' not ' in pattern:
        positive, negative = pattern.split(' not ')
        return lambda text: (
            evaluate_contains(positive, text) and
            not evaluate_contains(negative, text)
        )
    else:
        return lambda text: evaluate_contains(pattern, text)

def evaluate_contains(expr, text):
    """
    Evaluate 'contains X and Y' or 'contains X or Y' expressions
    """
    text_lower = text.lower()

    # Handle 'and' logic
    if ' and ' in expr:
        parts = expr.split(' and ')
        return all(
            any(term in text_lower for term in extract_terms(part))
            for part in parts
        )

    # Handle 'or' logic
    elif ' or ' in expr:
        terms = extract_terms(expr)
        return any(term in text_lower for term in terms)

    # Single term
    else:
        terms = extract_terms(expr)
        return any(term in text_lower for term in terms)

def extract_terms(expr):
    """
    Extract search terms from 'contains X' expression
    """
    # Remove 'contains' keyword
    expr = expr.replace('contains', '').strip()
    # Split by 'or'
    terms = [t.strip() for t in expr.split(' or ')]
    return terms
```

### Special Patterns

**Line 106**: `Other_adjustments`
```
Pattern: [equals to other, net or other, with position line before that of accounts_receivables or accounts_payables or inventory]

Implementation:
- Check if plabel exactly equals "other, net" OR "other"
- AND line position is before accounts receivable/payable/inventory line numbers
```

**Line 118**: `other_operating_activities`
```
Pattern: [contains other or others and contains operating] or
         [contains other or others and position line is smaller than that of net cash provided by operating activities by one or two]
         plus [any other items not fitting into operating activities]

Implementation:
- Pattern match for "other" + "operating"
- OR within 1-2 lines above the control item
- PLUS aggregate any unmapped operating items
```

### Items to Calculate (Ignore During Mapping)
- Line 155: operating_cash_flow
- Line 156: capital_expenditure
- Line 157: free_cash_flow
- Line 158: income_taxes_paid (supplemental disclosure)
- Line 159: interest_paid (supplemental disclosure)

### Cash Flow Mapping Implementation

```python
def map_cash_flow_statement(line_items, schema_patterns):
    """
    Map cash flow statement items using PATTERN matching
    """
    # 1. Find control items first
    control_lines = find_control_items(line_items)

    # 2. Classify items by section
    classified_items = {}
    for item in line_items:
        section = classify_cash_flow_item(item['line_num'], control_lines)
        if section not in classified_items:
            classified_items[section] = []
        classified_items[section].append(item)

    # 3. Map each item using patterns
    mapped_items = []
    unmapped_by_section = {
        'operating': [],
        'investing': [],
        'financing': []
    }

    for section, items in classified_items.items():
        for item in items:
            plabel = item['plabel']

            # Try pattern matching
            target = find_pattern_match(plabel, item['line_num'], schema_patterns)

            if target:
                # Check if calculated item - skip
                if target in CALCULATED_CF_ITEMS:
                    continue

                mapped_items.append({
                    'plabel': plabel,
                    'target': target,
                    'values': item['values'],
                    'section': section
                })
            else:
                if section in unmapped_by_section:
                    unmapped_by_section[section].append(item)

    # 4. Aggregate unmapped items into other_*_activities
    for section, items in unmapped_by_section.items():
        if items:
            aggregate_target = f'other_{section}_activities'
            # Sum up values from unmapped items
            aggregated_values = aggregate_values(items)

            mapped_items.append({
                'plabel': f'Other {section} activities (aggregated)',
                'target': aggregate_target,
                'values': aggregated_values,
                'section': section,
                'aggregated_from': [i['plabel'] for i in items]
            })

    return mapped_items

def find_control_items(line_items):
    """
    Find the 3 control items and return their line numbers
    """
    control_patterns = {
        'operating': '[contains cash and contains operating activities] not [contains other or others]',
        'investing': '[contains cash and contains investing activities] not [contains other or others]',
        'financing': '[contains cash and contains financing activities] not [contains other or others]'
    }

    control_lines = {}
    for item in line_items:
        for section, pattern in control_patterns.items():
            if pattern_matches(item['plabel'], pattern):
                control_lines[section] = item['line_num']
                break

    return control_lines
```

---

## Implementation Priority

### Phase 1: Income Statement Mapper
1. Build exact string matching system
2. Handle EPS and share count special logic
3. Implement detail item filtering
4. Test with Apple, Microsoft, Amazon

### Phase 2: Cash Flow Statement Mapper
1. Build pattern parsing engine
2. Implement control item detection
3. Build section classification logic
4. Implement aggregation for unmapped items
5. Test with Apple, Microsoft, Amazon

### Phase 3: Integration
1. Extend `map_company_balance_sheet.py` to support all 3 statement types
2. Create unified YAML format for all statements
3. Build comprehensive test suite

---

## Data Structures

### Income Statement YAML Output
```yaml
company:
  cik: "1018724"
  name: "Amazon.com Inc"
  ticker: "AMZN"
filing:
  adsh: "0001018724-24-000083"
  dataset: "2024Q2"
statement: income_statement
mappings:
  "Total net sales":
    target: revenue
    confidence: 1.0
    notes: "Direct match"

  "Cost of sales":
    target: cost_of_revenue
    confidence: 1.0

  # ... more mappings

  "Earnings per share - Basic":
    target: eps
    confidence: 1.0
    is_monetary: true
    contains_basic: true

  "Earnings per share - Diluted":
    target: eps_diluted
    confidence: 1.0
    is_monetary: true
    contains_diluted: true
```

### Cash Flow Statement YAML Output
```yaml
company:
  cik: "1018724"
  name: "Amazon.com Inc"
  ticker: "AMZN"
filing:
  adsh: "0001018724-24-000083"
  dataset: "2024Q2"
statement: cash_flow_statement
control_items:
  net_cash_provided_by_operating_activities:
    line_num: 25
    plabel: "Net cash provided by operating activities"
  net_cash_provided_by_investing_activities:
    line_num: 42
    plabel: "Net cash used in investing activities"
  net_cash_provided_by_financing_activities:
    line_num: 58
    plabel: "Net cash used in financing activities"

mappings:
  operating_activities:
    "Net income":
      target: net_income
      line_num: 10
      pattern_matched: "[contains net income]"
      confidence: 1.0

    "Depreciation and amortization":
      target: depreciation_and_amortization
      line_num: 12
      pattern_matched: "[contains depreciation and contains amortization]"
      confidence: 1.0

    # Aggregated item example
    "Other operating activities (aggregated)":
      target: other_operating_activities
      line_num: null
      aggregated_from:
        - "Other adjustments to reconcile net income"
        - "Foreign currency effect on cash"
      confidence: 0.8

  investing_activities:
    # ... investing mappings

  financing_activities:
    # ... financing mappings
```

---

## Next Steps

1. **Fix CSV spelling errors** (documented in CSV_SPELLING_ERRORS.md)
2. **Build income statement mapper** with exact matching
3. **Build cash flow pattern parser** and matching engine
4. **Test with 3 companies** (Amazon, Apple, Microsoft)
5. **Expand to 10-20 companies** for pattern validation
6. **Integrate with update workflow** (YAML cache + AI fallback)
