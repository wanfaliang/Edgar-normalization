# Pattern Review and Fix Plan

## Current Foundations Summary

### What We've Built

**1. Statement Reconstructor (Phase 1 - COMPLETE)**
- Reads NUM, TAG, PRE from TXT files
- Reconstructs all 5 statement types (BS, IS, CF, CI, EQ)
- Multi-period support
- 100% functional for all test companies

**2. Mapping Engine (Phase 2 - IN PROGRESS)**
- Two-tier system:
  - **Control item identification:** Find key dividers for section classification
  - **Line item mapping:** Map individual items to standardized fields
- Export to Excel with side-by-side comparison

### Recent Fixes

**Control Item Direct Mapping:**
- Control items now mapped DIRECTLY by line number (no duplicate patterns)
- Eliminates redundancy between control patterns and mapping patterns
- Balance Sheet: total_current_assets, total_assets, total_liabilities, total_stockholders_equity, total_liabilities_and_total_equity
- Income Statement: revenue, gross_profit, operating_income, income_before_tax, income_tax_expense, net_income, eps, eps_diluted, weighted_average_shares_outstanding, weighted_average_shares_outstanding_diluted
- Cash Flow: net_income, operating/investing/financing totals, beginning/ending cash

**Starbucks Cash Fix:**
- Added tag field checking for cash items (plabel OR tag contains 'cash')
- Handles cases where plabel doesn't contain 'cash' but tag does

**Revenue Pattern Fix:**
- Fixed De Morgan's Law issue: AND instead of OR for exclusions
- Excludes marketing, administrative, general expenses correctly

### Current Issues

**Pattern Mismatches:**
- Many patterns don't match CSV specification exactly
- Example: short_term_investments pattern was wrong (fixed)
- Need systematic review of ALL patterns against CSV Column 4

**Common Missing Items:**
- Marketable securities (NOW FIXED)
- Accrued expenses and other
- Unearned revenue
- Common stock (with par value text)
- Treasury stock
- Additional paid-in capital
- Accumulated other comprehensive income
- Retained earnings

---

## Pattern Review Plan

### Phase 1: Read and Validate CSV Specification

**Objective:** Understand the authoritative pattern definitions

**Tasks:**
1. Read `docs/Plabel_Investigation_v4.csv` completely
2. Document all field names (Column 1)
3. Document all pattern specifications (Column 4)
4. Create mapping: field_name → CSV pattern

**Deliverable:** Pattern specification reference document

---

### Phase 2: Audit Current Implementation

**Objective:** Find all discrepancies between CSV and code

**Tasks:**

**Balance Sheet Patterns (Lines 167-273):**
- [ ] Cash and equivalents
- [ ] Short-term investments (FIXED ✓)
- [ ] Account receivables
- [ ] Inventory
- [ ] Prepaids
- [ ] Other current assets
- [ ] Total current assets
- [ ] Property, plant, equipment
- [ ] Long-term investments
- [ ] Goodwill
- [ ] Intangible assets
- [ ] Finance/operating lease ROU assets
- [ ] Deferred tax assets
- [ ] Other non-current assets
- [ ] Total assets (DIRECT MAPPING ✓)
- [ ] Accounts payable
- [ ] Accrued payroll
- [ ] Accrued expenses
- [ ] Short-term debt
- [ ] Deferred revenue (current)
- [ ] Tax payables
- [ ] Lease obligations (current)
- [ ] Other current liabilities
- [ ] Total current liabilities (DIRECT MAPPING ✓)
- [ ] Long-term debt
- [ ] Pension liabilities
- [ ] Deferred revenue (non-current)
- [ ] Deferred tax liabilities
- [ ] Lease obligations (non-current)
- [ ] Commitments and contingencies
- [ ] Other non-current liabilities
- [ ] Total liabilities (DIRECT MAPPING ✓)
- [ ] Common stock
- [ ] Preferred stock
- [ ] Additional paid-in capital (APIC)
- [ ] Retained earnings
- [ ] Accumulated OCI
- [ ] Treasury stock
- [ ] Minority interest
- [ ] Total stockholders' equity (DIRECT MAPPING ✓)
- [ ] Total liabilities and equity (DIRECT MAPPING ✓)

**Income Statement Patterns (Lines 396-475):**
- [ ] Revenue (DIRECT MAPPING ✓ + pattern for non-control)
- [ ] Cost of revenue
- [ ] Gross profit (DIRECT MAPPING ✓)
- [ ] R&D expenses
- [ ] Sales & marketing expenses
- [ ] SG&A expenses
- [ ] G&A expenses
- [ ] Operating expenses
- [ ] Other expenses
- [ ] Operating income (DIRECT MAPPING ✓)
- [ ] Interest income
- [ ] Interest expense
- [ ] Other income/expense
- [ ] Income before tax (DIRECT MAPPING ✓)
- [ ] Income tax expense (DIRECT MAPPING ✓)
- [ ] Net income (DIRECT MAPPING ✓)
- [ ] EPS basic (DIRECT MAPPING ✓)
- [ ] EPS diluted (DIRECT MAPPING ✓)
- [ ] Weighted avg shares basic (DIRECT MAPPING ✓)
- [ ] Weighted avg shares diluted (DIRECT MAPPING ✓)

**Cash Flow Patterns (Lines 597-689):**
- [ ] Net income starting line (DIRECT MAPPING ✓)
- [ ] Depreciation & amortization
- [ ] Stock-based compensation
- [ ] Deferred taxes
- [ ] Other non-cash items
- [ ] Accounts receivable change
- [ ] Inventory change
- [ ] Accounts payable change
- [ ] Deferred revenue change
- [ ] Income taxes payable change
- [ ] Other operating activities
- [ ] Net cash from operating (DIRECT MAPPING ✓)
- [ ] Capital expenditures
- [ ] Acquisitions
- [ ] Investment purchases/sales
- [ ] Other investing activities
- [ ] Net cash from investing (DIRECT MAPPING ✓)
- [ ] Dividends paid
- [ ] Stock repurchased
- [ ] Stock issuance
- [ ] Debt proceeds/repayments
- [ ] Other financing activities
- [ ] Net cash from financing (DIRECT MAPPING ✓)
- [ ] Cash beginning (DIRECT MAPPING ✓)
- [ ] Cash ending (DIRECT MAPPING ✓)
- [ ] Net change in cash

**Deliverable:** List of all pattern discrepancies

---

### Phase 3: Fix Patterns Systematically

**Approach:**
1. For each field in CSV:
   - Read CSV pattern (Column 4)
   - Find corresponding code pattern
   - Compare for exact match
   - Fix if different
   - Test on sample companies

**Priority Order:**
1. **High Priority:** Commonly appearing items (cash, receivables, inventory, etc.)
2. **Medium Priority:** Less common but important (leases, OCI, etc.)
3. **Low Priority:** Rare or company-specific items

**Testing Strategy:**
- Test each fix against Amazon (complex)
- Test against Microsoft (standard)
- Test against Starbucks (edge cases)
- Verify no regressions

**Deliverable:** All patterns match CSV specification exactly

---

### Phase 4: Handle Special Cases

**Issues to Address:**

1. **Extra text in plabels:**
   - "Common stock ($0.01 par value; 100,000 shares authorized...)"
   - Solution: More flexible patterns that ignore parenthetical text

2. **Section boundary edge cases:**
   - Items classified in wrong section
   - Solution: Review section classification logic

3. **Missing pattern variations:**
   - CSV shows min{...} meaning "first match"
   - Ensure we're matching correctly

4. **Negating field:**
   - Some items should be subtracted not added
   - Check if we're handling negating field correctly

**Deliverable:** Robust pattern matching that handles real-world variations

---

### Phase 5: Validation Testing

**Test Suite:**
1. Run all 50 test companies
2. Check mapping coverage %
3. Identify items that should map but don't
4. Review false negatives
5. Review false positives (wrong mappings)

**Success Criteria:**
- Balance Sheet: >80% mapping coverage
- Income Statement: >75% mapping coverage
- Cash Flow: >85% mapping coverage
- All control items: 100% mapped and displayed

**Deliverable:** Comprehensive test results

---

## Alternative Path: AI-Generated Mappings

**Per Foundations.md:**
Instead of perfecting universal patterns, we could:

1. **Store reconstructed statements in database**
2. **Use AI to generate company-specific mappings**
3. **Store mappings in database**
4. **Apply mappings deterministically**

**Pros:**
- More accurate than universal patterns
- Easier to maintain
- Handles company-specific terminology
- Scalable to thousands of filings

**Cons:**
- Requires database infrastructure (Phase 1 & 2 of Foundations.md)
- More upfront work
- But much better long-term solution

---

## Recommendation

**Short-term (Next Session):**
- Complete Pattern Review Phase 1-3
- Fix critical patterns (common items)
- Get to 80%+ coverage

**Medium-term (Next 2-3 Sessions):**
- Implement database architecture (Foundations.md Phase 1-2)
- Build reconstruction caching
- Start AI-generated mappings for test companies

**Long-term (Production):**
- Full database-backed system
- AI-generated mappings for all companies
- Pattern-based approach as fallback only

---

**Last Updated:** 2024-11-29
**Status:** Pattern review needed before proceeding
