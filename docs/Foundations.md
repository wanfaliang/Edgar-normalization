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
