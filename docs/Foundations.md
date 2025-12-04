# EDGAR Explorer - Database-Centric Architecture

## Overview

This document outlines the evolution from file-based to database-centric architecture for financial statement reconstruction, mapping, and standardization.

---

## Problem Statement

**Current Challenge:**
- Reconstructing financial statements requires repeatedly loading large TXT files (NUM, TAG, PRE)
- Testing 50 companies means 50× file I/O + CSV parsing overhead
- Slow iteration on mapping pattern refinement
- Not scalable for production use across thousands of filings

**Performance Bottleneck:**
Each reconstruction loads multi-million row datasets from disk, filters for specific CIK/ADSH, and processes. For batch testing, this becomes prohibitively slow.

---

## Solution: Multi-Phase Database Architecture

### Phase 1: Raw Data Storage
**Goal:** Store SEC quarterly datasets in database for fast querying

**Process:**
- Load NUM.txt, TAG.txt, PRE.txt into database tables
- Create indexes on: adsh, cik, tag, stmt
- One-time operation per quarter
- Replaces file-based data access

**Benefits:**
- Fast filtered queries (indexed lookups)
- No repeated CSV parsing
- Shared data across all tools

---

### Phase 2: Database-Backed Tools
**Goal:** Build versions of reconstructor/exporter that read from database

**Components:**
- `StatementReconstructorDB` - queries database instead of reading TXT files
- `ExporterDB` - uses database reconstructor
- `MapperDB` - uses database reconstructor

**Design Principle:**
- Same interface as file-based versions
- Different data source (DB vs TXT)
- Transparent to users

**Benefits:**
- Significantly faster reconstruction
- Enables scalable batch processing
- Foundation for production system

---

### Phase 3: Reconstructed Statement Caching
**Goal:** Store reconstructed financial statements for all filings

**Process:**
- Run reconstructor on all filings in database
- Store results: line_items, periods, metadata
- One-time reconstruction per filing
- Cache expensive computation work

**What Gets Stored:**
- Complete reconstructed statements (BS, IS, CF, CI, EQ)
- All line items with full metadata (plabel, tag, ddate, qtrs, iord, crdr, tlabel, etc.)
- Period information and filing metadata
- EDGAR viewer URLs

**Benefits:**
- Reconstruction happens once per filing
- Mapping/analysis tools read from cache
- Fast iteration on downstream processes
- No re-processing unless reconstructor logic changes

---

### Phase 4: AI-Generated Company Mappings
**Goal:** Generate company-specific mappings from reconstructed statements to standardized fields

**Process:**
1. For each company/filing, AI analyzes reconstructed statements
2. Maps company's specific line items to universal standardized fields
3. Generates mapping data stored in database
4. Human review and approval of mappings

**Mapping Approach:**
- **Company-specific** rather than universal pattern matching
- Each company has unique terminology and line item names
- Tailored mappings capture exact relationships
- More reliable than complex pattern-based rules

**Storage:**
- Mappings stored in database tables (not YAML files)
- Links target fields to source plabels/tags
- Versioned and auditable
- Easy to query and update

**Example Mappings:**

*Apple Inc.:*
- `revenue` → "Net sales"
- `cost_of_revenue` → "Cost of sales"
- `research_and_development_expenses` → "Research and development"

*Microsoft Corp:*
- `revenue` → "Total revenue"
- `cost_of_revenue` → "Cost of revenue"
- `research_and_development_expenses` → "Research and development"

**Benefits:**
- Accurate, company-specific mappings
- No complex universal pattern logic needed
- Reviewable and maintainable
- AI handles variations and edge cases
- Deterministic application in production

---

### Phase 5: Production Mapping & Export
**Goal:** Fast, reliable generation of standardized financial statements

**Process:**
1. Read reconstructed statements from database cache
2. Load company-specific mappings from database
3. Apply mappings deterministically
4. Export standardized statements to Excel/API

**Benefits:**
- Near-instant processing (all data cached)
- Reliable, consistent mappings
- Scalable to thousands of companies
- Easy to audit and verify results

---

## Architecture Comparison

### File-Based (Current)
```
TXT Files → Reconstructor → Mapping Patterns → Excel
         ↑                ↑
    Slow I/O        Complex patterns
```

### Database-Centric (Target)
```
Database Tables:
├── Raw Data (NUM, TAG, PRE)
├── Reconstructed Statements (cached)
└── Company Mappings (AI-generated)
         ↓
    Fast Queries → Mapper → Excel/API
```

---

## Key Principles

1. **Cache Expensive Work:** Reconstruct once, use many times
2. **Database-Centric:** Everything in PostgreSQL for performance and scalability
3. **Company-Specific Mappings:** Tailored approach beats universal patterns
4. **AI-Assisted Generation:** Leverage AI for mapping creation, not production matching
5. **Deterministic Execution:** Production uses pre-generated mappings for reliability
6. **Incremental Processing:** New filings added without reprocessing existing ones

---

## Performance Expectations

**File-Based:**
- 50 companies: 30+ minutes
- Each test requires full reconstruction
- Not practical for thousands of filings

**Database-Centric:**
- Initial reconstruction: One-time cost
- Mapping iteration: Seconds
- 50 companies: < 1 minute
- Production ready for thousands of filings

---

## Implementation Priority

1. **Phase 1 & 2:** Database foundation and tools (enables fast reconstruction)
2. **Phase 3:** Cache all reconstructed statements (one-time investment)
3. **Phase 4:** AI-generated mappings (covers test companies first)
4. **Phase 5:** Production mapping system (reliable, scalable output)

---

## Future Enhancements

- API endpoints for real-time queries
- Incremental updates for new quarterly datasets
- Mapping quality metrics and validation
- Multi-period comparative analysis
- Historical trend analysis across companies
- Machine learning for mapping confidence scoring

---

**Last Updated:** 2024-11-29
**Status:** Architecture planning phase

## The following lists the concept of mapping the deriving to balance the standardized items of balance sheet
We need to implement approaches strategically.We remove both explicit patterns and auto-assignment, then      
how do we apply the residual method? We need to implement this strategically.We need to get the meta data about the companies’ sectors, if the companies are in financial sector, we      
go to step 5(a lot of financial companies don’t present total_current_assets and total_current_liabilities      
1. We must be able to identify total_assets and total_liabilities_and_total_equity, if we can’t we stop. Any  
 attempts to go further could not be reliable. (for now, this is true for the 50 companies). And they should  
 equal to each other, if not, stop. (Be mindful with the data type to make sure we don’t wrongfully throw away
those they are essentially equivalent. For now, all companies conform to this.
2. Now we have total_assets and total_liabilities_and_total_equity
We should be able to identify either total_equity or total_stockholders_equity or total_liabilities. (for 
now, it’s true). If we can’t identify any of the three, we stop.
Therefore, we know the numbers of total_liabilities.
If there is total_liabilities, then here it is.
If there is no total_liabilities, total_liabilities equal to the residual of 
total_liabilities_and_total_equity minus total_equity or total_stockholders_equity, if both total_equity and
 total_stockholders_equity exist, total_liabilities equal to the residual of 
total_liabilities_and_total_equity minus total_equity
3. Now we have total_assets, total_liabilities_and_total_equity, total_liabilities, and total_equity or 
total_stockholders_equity
We need to identify total_current_assets, and we can get total_non_current_assets. 
We also need to identify total_current_liabilities then we can get total_non_current_liabilities.
Otherwise, we stop.
4. Now we have total_assets, total_liabilities_and_total_equity, total_liabilities, and total_equity or 
total_stockholders_equity
Also, we have total_current_assets,  total_non_current_assets, total_current_liabilities and 
total_non_current_liabilities
We use other_current_assets, other_non_current_assets, other_current_liabilities,  
other_non_current_liabilities, and  other_total_stockholders_equity to take the residual, that is:
other_current_assets = total_current_assets – sum (items in this section and mapped into and presented in 
standardized items other than all the above identified in steps 1-3)
other_non_current_assets = total_non_current_assets – sum (items in this section and mapped into and 
presented in standardized items other than all the above identified in steps 1-3)
other_current_liabilities = total_current_liabilities – sum (items in this section and mapped into and 
presented in standardized items other than all the above identified in steps 1-3)
other_non_current_liabilities = total_non_current_liabilities – sum (items in this section and mapped into 
and presented in standardized items other than all the above identified in steps 1-3)
More than 95% of non-financial companies have total_assets, total_liabilities_and_total_equity, 
total_liabilities, total_equity or total_stockholders_equity, total_current_assets, and 
total_current_liabilities
5. For those we fail to map, we will deal with them with other approaches, not too much.
6. Financial sector has distinctive assets and liabilities classification we will map later. They have 
similar patterns.
The approaches will substantially ensure the accuracy of our approach; even if we can’t map 100%, the 
numbers we get are good enough for financial or equity analysis.
Make sure this is clear with you. If there are typos or anything unclear, please let me know. What do you 
think? 

● This is an excellent strategic approach! Very well thought out. Let me confirm my understanding:

  Strategic Residual Calculation Approach

  Step 0: Sector Check

  - Get company sector metadata (SIC code?)
  - If financial sector → skip to Step 5 (different patterns)

  Step 1: Core Validation (MUST HAVE)

  - ✓ Must identify: total_assets AND total_liabilities_and_total_equity
  - ✓ Must verify: total_assets == total_liabilities_and_total_equity (with type safety)
  - ✗ If either missing or not equal → STOP (unreliable)

  Step 2: Determine total_liabilities

  - Try to identify at least one of: total_equity, total_stockholders_equity, OR total_liabilities
  - ✗ If none found → STOP
  - Calculate total_liabilities:
    - If total_liabilities exists directly → use it
    - Else if both total_equity AND total_stockholders_equity exist → total_liabilities =
  total_liabilities_and_total_equity - total_equity
    - Else → total_liabilities = total_liabilities_and_total_equity - (whichever equity exists)

  Step 3: Current/Non-Current Split

  - ✓ Must identify: total_current_assets → calculate total_non_current_assets = total_assets -
  total_current_assets
  - ✓ Must identify: total_current_liabilities → calculate total_non_current_liabilities = total_liabilities    
   - total_current_liabilities
  - ✗ If either missing → STOP

  Step 4: Residual Calculation

  Now calculate:
  - other_current_assets = total_current_assets - sum(mapped current assets excluding control totals)
  - other_non_current_assets = total_non_current_assets - sum(mapped non-current assets excluding control       
  totals)
  - other_current_liabilities = total_current_liabilities - sum(mapped current liabilities excluding control    
   totals)
  - other_non_current_liabilities = total_non_current_liabilities - sum(mapped non-current liabilities
  excluding control totals)
  - other_total_stockholders_equity = total_stockholders_equity - sum(mapped equity items excluding control     
  totals)

  Step 5-6: Edge Cases

  - Financial sector: separate handling
  - Failed mappings: manual review

  Questions:

  1. Sector metadata: How to get it? SIC code from SUB.txt?
  2. Equality tolerance: Exact match or allow small rounding difference (e.g., $1)?
  3. Step 2 logic: Use total_equity over total_stockholders_equity because it's more comprehensive (includes    
   minority interests)?
  4. Data type safety: Cast to float and compare, or handle as Decimal?
  5. "Mapped items": Means items successfully mapped to standardized fields, excluding all control totals,      
  correct?

  Otherwise crystal clear! Ready to implement once you confirm.

> Excellent understanding and questions. 1. both the sub.txt and the table companies have sic code and we     
need to parse them. 2. To be safe we can use percentage of diff, if <0.1%, we are good. 3. Right, if the      
balance sheet has minority item, the equation should be minus total_equity,4. It's up to you. 5. Right, if    
you mean those which should be summed and to derive the values of the 'other's, does this make sense to you?    

● Perfect! All clear now. Let me summarize the implementation plan:

  Implementation Plan

  Answers Applied:

  1. SIC code: Parse from SUB.txt or companies table (financial sector = 6000-6999)
  2. Tolerance: abs(val1 - val2) / avg(val1, val2) < 0.001 (0.1%)
  3. total_equity priority: Use when minority interests exist
  4. Data types: Convert to float, handle None/NaN safely
  5. Mapped items for sum: All successfully mapped items that should contribute to section totals (exclude      
  control totals themselves)

  Implementation Steps:

  Step 1: Remove existing "other" logic
  - Remove explicit "other_*" patterns from map_bs_item
  - Remove auto-assignment logic (lines 1032-1044)

  Step 2: Add validation function
  def validate_and_calculate_balance_sheet(standardized, control_lines, sic_code=None):
      # Step 0: Check if financial sector
      # Step 1: Validate core (total_assets == total_liabilities_and_total_equity)
      # Step 2: Determine total_liabilities
      # Step 3: Calculate current/non-current splits
      # Step 4: Calculate residual "other_*" items
      # Return: validated standardized dict or None if validation fails

  Step 3: Integration
  - Get SIC code from company data
  - Call validation function after mapping
  - Handle failures gracefully (log reason, skip company)

  Control Items to Exclude from Sums:

  All totals identified in steps 1-3:
  - total_assets, total_liabilities_and_total_equity
  - total_liabilities, total_equity, total_stockholders_equity
  - total_current_assets, total_non_current_assets
  - total_current_liabilities, total_non_current_liabilities

  I just backed up with map_financial_statements_old.py and marked with comments.

  Afterwards, we have modified and implemented a lot of patterns. 