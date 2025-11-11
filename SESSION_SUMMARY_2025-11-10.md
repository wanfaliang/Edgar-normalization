# Session Summary: EDGAR Tag Mapping Progress
**Date:** November 10, 2025
**Session Focus:** Russell 3000 Tag Analysis & Strategic Pivot to Aggregation Approach

---

## Executive Summary

This session made significant progress on EDGAR-to-Finexus mapping but revealed a critical insight: **simple 1:1 tag mapping is insufficient**. We need an **aggregation/standardization engine** to correctly handle complex tag relationships.

### Key Accomplishment
- Extracted and analyzed tags from 80 Russell 3000 companies (2024Q3)
- Enhanced tag profiles with statement type identification
- Generated comprehensive manual review file with actual filing labels
- **CRITICAL INSIGHT:** Discovered need for aggregation approach

### Strategic Pivot
Moved from simple tag mapping → **3-step aggregation/standardization engine**

---

## Session Progress

### 1. Russell 3000 Tag Extraction ✅

**Created:** `src/russell_3000_matcher.py`
- Matched 2,549/2,572 Russell 3000 tickers to SEC CIKs (99.1%)
- Created stratified sample of 50 companies by market cap and sector
- 2,455 companies (96.3%) available in 2024Q3 data

**Sample Distribution:**
- Large-cap (1-200): 20 companies
- Mid-cap (201-1000): 20 companies
- Small-cap (1001+): 10 companies
- Across 11 sectors

**Results:**
- 80 companies successfully extracted
- Average: 119 tags/company
- Only 10.3% custom tags (vs 63% for BDCs - much better!)
- Files: `data/sec_data/extracted/2024q3/company_tag_profiles/`

### 2. Statement Type Identification ✅

**Created:** `src/add_statement_type_to_tags.py`
- Enhanced all 80 company profiles with statement type metadata
- Uses hierarchy: PRE table → iord field → tag naming conventions

**Statement Types Added:**
- `balance_sheet` - Items from Balance Sheet
- `income_statement` - Items from Income Statement
- `cash_flow` - Items from Cash Flow Statement
- `equity` - Items from Statement of Stockholders' Equity

**Example Enhancement:**
```json
{
  "tag": "Assets",
  "iord": "I",
  "statement_type": "balance_sheet",
  "most_common_plabel": "Total assets"
}
```

### 3. Presentation Label Analysis ✅

**Key Discovery:** Tags have different labels in actual filings

**Created:** Enhanced `tools/generate_manual_review_file.py`
- Analyzes PRE table (741,760 rows) to extract actual filing labels
- Shows what companies ACTUALLY call each tag on statements

**Example:**
- XBRL Tag: `Assets`
- US-GAAP Label: "Assets"
- **Actual Filing Label:** "Total assets" (used 4,565 times)
- Variations: "Total Assets" (1,171x), "TOTAL ASSETS" (1,032x)

**Output Files:**
- `data/russell_3000_matched/manual_review/MANUAL_REVIEW_TOP_1000_TAGS.xlsx`
- `data/russell_3000_matched/manual_review/all_tags_full_metadata.csv`

**File Contains:**
- Top 1000 tags with full metadata
- 1,234 standard tags NOT in current taxonomy
- 12 sheets organized by statement type and tag nature
- Actual presentation labels from filings

### 4. Current Taxonomy Status

**Source:** Fields from `src/database/models_from_finexus.py`
- BalanceSheet model: `total_assets`, `total_liabilities`, `stockholders_equity`, etc.
- IncomeStatement model: `revenue`, `net_income`, `cost_of_revenue`, etc.
- CashFlow model: `operating_cash_flow`, `investing_cash_flow`, etc.

**Current Mapping:** `data/taxonomy/sec_to_finexus_mapping.json`
- 146 SEC tag variations mapped
- Balance Sheet: 51 variations
- Income Statement: 54 variations
- Cash Flow: 41 variations

**Gap Analysis:**
- 2,218 unique tags in Russell 3000 sample
- Only 21 tags (0.9%) currently mapped
- **Top missing tags used by 70-100% of companies:**
  - Assets (80/80) → should map to `total_assets`
  - StockholdersEquity (73/80) → should map to `stockholders_equity`
  - Liabilities (67/80) → should map to `total_liabilities`
  - RetainedEarningsAccumulatedDeficit (79/80)
  - NetCashProvidedByUsedInOperatingActivities (78/80)

---

## Critical Insight: Why Simple Mapping Fails

### The Problem

**One-to-many relationship:**
```
PrepaidExpenseAndOtherAssetsCurrent ──┐
                                      ├──> other_current_assets
OtherOtherAssetsCurrent ──────────────┘
```

**Many-to-one relationship:**
```
AssetsCurrent ──> current_assets + noncurrent_assets
```

**Reality:** Financial statement items have complex aggregation relationships that can't be captured with simple 1:1 mapping.

### Real-World Example

Company A Balance Sheet:
```
Current Assets:
  - CashAndCashEquivalents: $100M
  - AccountsReceivableNet: $50M
  - PrepaidExpenseAndOtherAssetsCurrent: $20M  ─┐
  - OtherAssetsCurrent: $10M                    ├─> Both should aggregate
Total Current Assets: $180M                     ┘   to "other_current_assets"
```

With simple mapping:
- ❌ Both tags map to same field = potential double counting
- ❌ Or one overwrites the other = missing data
- ❌ No way to handle "sum of multiple tags → one field"

---

## New Approach: 3-Step Aggregation/Standardization Engine

### Step 1: Rebuild Financial Statements from EDGAR

**Input:** Raw EDGAR data
- PRE table: Presentation structure and hierarchies
- NUM table: Actual numeric values
- TAG table: Tag metadata

**Process:** Reconstruct statements as companies filed them
- Use PRE table to understand statement hierarchy
- Map line items to their position and parent items
- Preserve rollup/aggregation relationships

**Output:** Company-specific financial statements
```json
{
  "cik": 1018724,
  "company_name": "AMAZON COM INC",
  "period": "2024Q3",
  "balance_sheet": {
    "Assets": 500000000,
    "AssetsCurrent": 200000000,
    "CashAndCashEquivalents": 50000000,
    "AccountsReceivableNet": 30000000,
    // ... full hierarchy preserved
  }
}
```

**Feasibility:** ✅ DOABLE
- We have all necessary EDGAR data
- PRE table shows exact structure
- Clear parent-child relationships

### Step 2: Transform to Standardized Statements

**Input:** Company-specific statements from Step 1

**Process:** Apply aggregation rules to create standardized format
- **High-confidence items:** Direct mapping to standard line items
- **Uncertain items:** Conservative bucketing to "other_" categories
- **Validation:** Verify totals match (Assets, Liabilities, Equity must reconcile)

**Aggregation Rule Examples:**

```python
# Balance Sheet - High Confidence Items
total_assets = find_tag(['Assets'])  # Always clear
total_liabilities = find_tag(['Liabilities', 'LiabilitiesCurrent + LiabilitiesNoncurrent'])
stockholders_equity = find_tag(['StockholdersEquity', 'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'])

current_assets = find_tag(['AssetsCurrent'])
current_liabilities = find_tag(['LiabilitiesCurrent'])

# Specific current assets (by hierarchy in PRE table)
cash_and_equivalents = aggregate_tags([
    'CashAndCashEquivalents',
    'CashAndCashEquivalentsAtCarryingValue',
    'Cash'
])

accounts_receivable = aggregate_tags([
    'AccountsReceivableNet',
    'AccountsReceivableNetCurrent',
    'ReceivablesNetCurrent'
])

inventory = aggregate_tags([
    'InventoryNet',
    'Inventory'
])

# Conservative fallback
other_current_assets = current_assets - (
    cash_and_equivalents +
    accounts_receivable +
    inventory +
    marketable_securities +
    # ... other classified items
)
```

**Confidence Levels:**
1. **Very High (always correct):**
   - Total Assets, Total Liabilities, Total Equity
   - Current vs Noncurrent split
   - Statement totals

2. **High (correct for 95%+ companies):**
   - Cash & Equivalents
   - Accounts Receivable
   - Inventory
   - Property, Plant & Equipment
   - Common Stock
   - Retained Earnings

3. **Medium (conservative bucketing):**
   - Other Current Assets (catch-all)
   - Other Noncurrent Assets (catch-all)
   - Other Current Liabilities (catch-all)
   - Other Noncurrent Liabilities (catch-all)

**Output:** Standardized financial statements
```json
{
  "cik": 1018724,
  "period": "2024Q3",
  "standardized_balance_sheet": {
    "total_assets": 500000000,
    "current_assets": 200000000,
    "cash_and_cash_equivalents": 50000000,
    "accounts_receivable": 30000000,
    "inventory": 40000000,
    "other_current_assets": 80000000,  // Aggregated uncertain items
    "noncurrent_assets": 300000000,
    // ...
  },
  "confidence_scores": {
    "total_assets": "very_high",
    "cash_and_cash_equivalents": "high",
    "other_current_assets": "medium"
  }
}
```

**Feasibility:** ✅ DOABLE WITH CONTROLLED RISK
- We define the standard schema (30-50 line items)
- We control aggregation rules
- Conservative bucketing for uncertain items
- Validation ensures no substantial errors

### Step 3: Map Standardized → Finexus Taxonomy

**Input:** Standardized statements from Step 2

**Process:** Direct 1:1 mapping (we control both sides!)
```python
# Direct mapping - no ambiguity
finexus_balance_sheet = {
    'total_assets': standardized['total_assets'],
    'total_current_assets': standardized['current_assets'],
    'cash_and_cash_equivalents': standardized['cash_and_cash_equivalents'],
    'net_receivables': standardized['accounts_receivable'],
    'inventory': standardized['inventory'],
    'other_current_assets': standardized['other_current_assets'],
    # ...
}
```

**Output:** Data ready for Finexus database

**Feasibility:** ✅ EASY
- Both schemas under our control
- Simple field mapping
- No aggregation complexity

---

## Why This Approach is Superior

### 1. Accuracy for Financial Analysis
- **Totals always correct:** Assets = Liabilities + Equity (validated)
- **No double counting:** Aggregation rules prevent duplication
- **No missing data:** Conservative bucketing catches everything

### 2. Scalable Across All Companies
- Works for any company structure
- Handles variations in reporting
- Same rules apply to all 2,500+ Russell 3000 companies

### 3. Transparent and Auditable
- Clear aggregation rules documented
- Confidence scores for each line item
- Can trace back to original EDGAR filing

### 4. Conservative on Details
- High confidence on important items (totals, key ratios)
- Conservative bucketing for uncertain items
- "Other" buckets won't impact fundamental analysis

### 5. Leverages EDGAR Structure
- PRE table provides hierarchy information
- Rollup relationships already defined by companies
- We're using official filing structure

### 6. Verifiable
- Link to EDGAR viewer for each filing
- Compare our totals to company-reported totals
- Visual inspection available

---

## Implementation Plan for Next Session

### Phase 1: Statement Reconstruction Engine (Week 1)

**Goal:** Rebuild financial statements from EDGAR data

**Tasks:**
1. **Create `StatementReconstructor` class**
   - Input: CIK, period (ADSH)
   - Load: PRE, NUM, TAG tables for that filing
   - Output: Hierarchical statement structure

2. **Parse PRE table hierarchy**
   ```python
   def parse_statement_hierarchy(pre_df, stmt_type='BS'):
       """
       Build tree structure from PRE table
       - Uses 'inpth' field for indentation level
       - Uses 'line' field for ordering
       - Returns nested dict with parent-child relationships
       """
   ```

3. **Map values from NUM table**
   ```python
   def attach_values(hierarchy, num_df):
       """
       Attach actual values to hierarchy nodes
       - Match by tag name and period
       - Handle multiple instances (different dimensions)
       - Return hierarchy with values
       """
   ```

4. **Validate totals**
   ```python
   def validate_rollups(hierarchy):
       """
       Verify that parent = sum(children)
       - Flag inconsistencies
       - Return validation report
       """
   ```

**Deliverable:** Function that takes (CIK, period) → reconstructed statements

### Phase 2: Standardization Engine (Week 2)

**Goal:** Transform company statements → standardized format

**Tasks:**
1. **Define standard schema**
   ```python
   STANDARD_BALANCE_SHEET_SCHEMA = {
       'total_assets': {'confidence': 'very_high', 'required': True},
       'current_assets': {'confidence': 'very_high', 'required': True},
       'cash_and_cash_equivalents': {'confidence': 'high', 'required': False},
       # ... 30-50 line items
   }
   ```

2. **Create tag mapping rules**
   ```python
   TAG_MAPPING_RULES = {
       'total_assets': {
           'primary_tags': ['Assets'],
           'fallback_calculation': 'AssetsCurrent + AssetsNoncurrent',
           'validation': 'must_equal_liabilities_plus_equity'
       },
       'cash_and_cash_equivalents': {
           'tags': [
               'CashAndCashEquivalents',
               'CashAndCashEquivalentsAtCarryingValue',
               'Cash'
           ],
           'aggregation': 'sum_if_multiple'
       }
   }
   ```

3. **Build aggregation functions**
   ```python
   def aggregate_to_standard(company_statement, schema, rules):
       """
       Apply aggregation rules to create standardized statement
       - Try primary tags first
       - Use fallback calculations if needed
       - Apply conservative bucketing for unmatched items
       - Calculate confidence scores
       """
   ```

4. **Implement validation**
   ```python
   def validate_standardized_statement(standardized, original):
       """
       Verify standardization didn't lose/add value
       - Total assets must match
       - Total liabilities + equity must match
       - Flag any discrepancies > 0.01%
       """
   ```

**Deliverable:** Function that transforms company statement → standardized statement with confidence scores

### Phase 3: Finexus Mapping (Week 3)

**Goal:** Map standardized format → Finexus database schema

**Tasks:**
1. **Create simple field mapping**
   ```python
   FINEXUS_FIELD_MAPPING = {
       'balance_sheet': {
           'total_assets': 'total_assets',
           'current_assets': 'total_current_assets',
           'cash_and_cash_equivalents': 'cash_and_cash_equivalents',
           # ... straightforward 1:1 mapping
       }
   }
   ```

2. **Build transformation function**
   ```python
   def map_to_finexus(standardized_statement):
       """Simple field renaming - both schemas under our control"""
   ```

3. **Add metadata**
   ```python
   def add_filing_metadata(finexus_data, adsh, cik):
       """
       Add:
       - EDGAR viewer URL
       - Filing date
       - Source accession number
       - Confidence scores
       """
   ```

**Deliverable:** Complete pipeline from EDGAR → Finexus database

### Phase 4: Testing & Validation (Week 4)

**Testing Strategy:**
1. **Unit tests** for each component
2. **Integration tests** for full pipeline
3. **Validation tests** comparing our calculations to EDGAR
4. **Sample review** of 10 companies across sectors

**Validation Metrics:**
- 100% of totals must match (Assets, Liabilities, Equity)
- 95%+ accuracy on high-confidence items
- Conservative bucketing for medium-confidence items

---

## Key Files Reference

### Created This Session

1. **`src/russell_3000_matcher.py`**
   - Matches Russell 3000 tickers to CIKs
   - Creates stratified sample
   - Outputs: `data/russell_3000_matched/sample_ciks.txt`

2. **`src/extract_russell_sample_tags.py`**
   - Extracts tags for sample companies
   - Outputs: `data/sec_data/extracted/2024q3/company_tag_profiles/company_*_tags.json`

3. **`src/add_statement_type_to_tags.py`**
   - Adds statement type to tag profiles
   - Uses PRE table + iord field + naming conventions
   - Enriches existing company profiles

4. **`tools/generate_manual_review_file.py`**
   - Generates comprehensive manual review file
   - Extracts presentation labels from PRE table
   - Outputs: `MANUAL_REVIEW_TOP_1000_TAGS.xlsx`

5. **`src/taxonomy_builder.py`** (from previous session)
   - Extracts fields from Finexus models
   - Creates format conversion (snake_case ↔ CamelCase)
   - Outputs: `data/taxonomy/*.json`

### Data Files

**Input Data:**
- `data/sec_data/extracted/2024q3/sub.txt` - Submissions metadata
- `data/sec_data/extracted/2024q3/num.txt` - Numerical data (3.5M rows)
- `data/sec_data/extracted/2024q3/tag.txt` - Tag taxonomy (83K rows)
- `data/sec_data/extracted/2024q3/pre.txt` - Presentation structure (741K rows)

**Generated Data:**
- `data/russell_3000_matched/sample_ciks.txt` - 50 sample company CIKs
- `data/sec_data/extracted/2024q3/company_tag_profiles/*.json` - 80 company profiles
- `data/russell_3000_matched/manual_review/MANUAL_REVIEW_TOP_1000_TAGS.xlsx` - Review file
- `data/taxonomy/sec_to_finexus_mapping.json` - Current 146 mappings (will be superseded)

### Source Schema

**`src/database/models_from_finexus.py`**
- BalanceSheet model - Target database schema
- IncomeStatement model
- CashFlow model
- These define our target fields

---

## EDGAR Filing Viewer Integration

### URL Format
```
https://www.sec.gov/cgi-bin/viewer?action=view&cik={cik}&accession_number={adsh}&xbrl_type=v
```

### Example
Amazon 2024Q3 filing:
```
https://www.sec.gov/cgi-bin/viewer?action=view&cik=0001018724&accession_number=0001018724-25-000004&xbrl_type=v
```

### Integration Points
1. **Add to company profiles** - Include viewer URL for each filing
2. **Add to database records** - Store URL with each statement
3. **Add to validation reports** - Link to source for verification
4. **User interface** - Allow users to view source filing

### Implementation
```python
def generate_edgar_viewer_url(cik: str, adsh: str) -> str:
    """
    Generate EDGAR inline XBRL viewer URL

    Args:
        cik: Company CIK (with or without leading zeros)
        adsh: Accession number (format: 0001018724-25-000004)

    Returns:
        Full URL to EDGAR viewer
    """
    # Ensure CIK has 10 digits with leading zeros
    cik_padded = str(cik).zfill(10)

    return f"https://www.sec.gov/cgi-bin/viewer?action=view&cik={cik_padded}&accession_number={adsh}&xbrl_type=v"
```

---

## Next Session Priorities

### Immediate (Session Start)
1. Review this summary document
2. Create `StatementReconstructor` class
3. Parse PRE table hierarchy for 1-2 test companies
4. Validate reconstruction accuracy

### Short-term (Week 1)
1. Complete statement reconstruction engine
2. Test on 10 diverse companies
3. Validate totals match EDGAR

### Medium-term (Weeks 2-3)
1. Build standardization engine
2. Define aggregation rules
3. Implement conservative bucketing
4. Add confidence scoring

### Long-term (Week 4+)
1. Complete Finexus mapping
2. Full pipeline testing
3. Deploy to production
4. Scale to all Russell 3000 companies

---

## Technical Notes

### PRE Table Structure
```
Columns: adsh, report, line, stmt, inpth, rfile, tag, version, plabel, negating

Key fields:
- stmt: Statement type (BS, IS, CF, etc.)
- inpth: Indentation level (0 = top-level, 1 = child, 2 = grandchild)
- line: Line number in presentation order
- tag: XBRL tag name
- plabel: Presentation label (what appears on statement)
```

### Statement Hierarchy Example
```
line  inpth  tag                              plabel
1     0      Assets                           Total assets
2     1      AssetsCurrent                    Total current assets
3     2      CashAndCashEquivalents          Cash and cash equivalents
4     2      AccountsReceivableNet           Accounts receivable, net
5     2      Inventory                        Inventory
6     1      AssetsNoncurrent                 Total noncurrent assets
```

### Aggregation Strategy
```python
# Parent-child validation
def validate_hierarchy(node):
    if node.children:
        child_sum = sum(child.value for child in node.children)
        if abs(node.value - child_sum) > 0.01:  # Tolerance for rounding
            log_warning(f"{node.tag}: {node.value} != {child_sum}")
```

---

## Questions for Next Session

1. **Standard schema scope:** How many line items should we include?
   - Balance Sheet: 30-40 items?
   - Income Statement: 20-30 items?
   - Cash Flow: 15-20 items?

2. **Confidence thresholds:** What % accuracy required for "high confidence"?
   - 95%? 99%?

3. **"Other" buckets:** How granular?
   - Just "other_current_assets" and "other_noncurrent_assets"?
   - Or more specific buckets?

4. **Validation tolerance:** What's acceptable rounding error?
   - 0.01%? 0.1%?

5. **Edge cases:** How to handle:
   - Missing required tags?
   - Conflicting values?
   - Multiple instances of same tag?

---

## Context for Future Claude Sessions

**What we learned:**
- Simple 1:1 tag mapping is insufficient
- Need aggregation rules to handle complex relationships
- EDGAR data has all information needed for reconstruction
- Conservative approach with "other" buckets minimizes risk

**Why this matters:**
- Financial analysis requires accurate totals
- Details less critical than overall accuracy
- Can't afford double-counting or missing values
- Need verifiable, auditable process

**Core insight:**
Rather than mapping 2,000+ individual tags, we:
1. Rebuild statements from EDGAR (structured data)
2. Standardize to ~100 line items with aggregation rules
3. Map standardized format to Finexus (controlled mapping)

This is MORE accurate, MORE maintainable, and MORE scalable.

---

## Session Metrics

- **Time:** ~3 hours
- **Files created:** 5 Python scripts
- **Companies analyzed:** 80 Russell 3000 companies
- **Tags analyzed:** 2,218 unique tags
- **Presentation labels extracted:** 59,542 variations
- **Key insight:** Aggregation approach > simple mapping
- **Tokens used:** ~90,000 / 200,000

---

**End of Session Summary**
