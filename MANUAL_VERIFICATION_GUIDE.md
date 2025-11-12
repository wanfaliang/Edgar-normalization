# Manual Verification Guide

**Purpose:** Verify our StatementReconstructor extracts correct values by comparing to EDGAR display

---

## Amazon Q2 2024 - Verification Checklist

### Step 1: Open EDGAR Filing

**URL:** https://www.sec.gov/cgi-bin/viewer?action=view&cik=0001018724&accession_number=0001018724-24-000130&xbrl_type=v

**Filing Details:**
- Company: Amazon.com Inc
- Form: 10-Q
- Period: Q2 2024 (ending June 30, 2024)
- Filed: August 2, 2024

---

### Step 2: Verify Balance Sheet

**Navigate to:** Consolidated Balance Sheets (should be first financial statement)

**Our Extracted Values:**
```
Total Assets: $554,818,000,000 (as of June 30, 2024)
Total Liabilities and Stockholders' Equity: $554,818,000,000
```

**Check on EDGAR:**
- [ ] Find "Total assets" line → Should show **$554,818** (in millions)
- [ ] Find "Total liabilities and stockholders' equity" → Should show **$554,818** (in millions)
- [ ] Verify date column is "June 30, 2024" (not December 31, 2023)

**Expected Result:** ✅ Numbers match exactly

---

### Step 3: Verify Income Statement

**Navigate to:** Consolidated Statements of Operations (usually second statement)

**Our Extracted Values (Three Months Ended June 30, 2024):**
```
Total net sales (Revenue): $147,977,000,000
Net income: $13,485,000,000
```

**Check on EDGAR:**
- [ ] Find "Total net sales" row
- [ ] Look in the "Three Months Ended June 30, 2024" column (NOT the six months column)
- [ ] Should show **$147,977** (in millions)
- [ ] Find "Net income" row in same column → Should show **$13,485** (in millions)

**Expected Result:** ✅ Numbers match exactly

**Common Mistake to Avoid:**
- Don't look at "Six Months Ended June 30, 2024" column (that would be $291,290M)
- We're extracting quarterly (three months), not YTD

---

### Step 4: Verify Cash Flow Statement

**Navigate to:** Consolidated Statements of Cash Flows

**Our Extracted Values (Six Months Ended June 30, 2024):**
```
Net cash provided by operating activities: $44,270,000,000
Net cash used in investing activities: $-40,000,000,000
Net cash used in financing activities: $-5,746,000,000
Effect of exchange rate changes: $-741,000,000
Net decrease in cash: $-2,217,000,000
```

**Check on EDGAR:**
- [ ] Find "Net cash provided by operating activities"
- [ ] Look in "Six Months Ended June 30, 2024" column
- [ ] Should show **$44,270** (in millions)
- [ ] Find "Net cash used in investing activities" → Should show **($40,000)** (in millions)
- [ ] Find "Foreign currency effect on cash" → Should show **($741)** (in millions)

**Expected Result:** ✅ Numbers match exactly

**Note on Cash Flow Period:**
- Cash Flow uses YTD (six months) for Q2 10-Q
- This is different from Income Statement which uses quarterly

---

## Home Depot Q2 2024 - Verification Checklist (Optional)

### Step 1: Open EDGAR Filing

**URL:** https://www.sec.gov/cgi-bin/viewer?action=view&cik=0000354950&accession_number=0000354950-24-000201&xbrl_type=v

**Filing Details:**
- Company: The Home Depot, Inc.
- Form: 10-Q
- Period: Q2 2024 (ending July 28, 2024)
- Filed: August 27, 2024

### Quick Check:

**Our Extracted Values:**
```
Balance Sheet (July 28, 2024):
  Total Assets: $96,846,000,000

Income Statement (Three Months Ended July 28, 2024):
  Total Net Sales: $43,175,000,000
  Net Earnings: $4,561,000,000
```

**Check on EDGAR:**
- [ ] Balance Sheet → Total Assets as of July 28, 2024 = **$96,846** million
- [ ] Income Statement → Net Sales (3 months) = **$43,175** million
- [ ] Income Statement → Net Earnings (3 months) = **$4,561** million

---

## What to Look For

### ✅ PASS Criteria:
1. Numbers match exactly (in millions)
2. Date columns are correct (June 30, 2024 for Amazon)
3. Period is correct (3 months for IS, 6 months for CF in Q2 10-Q)

### ❌ FAIL Indicators:
1. Numbers don't match
2. We extracted from wrong date column
3. We extracted YTD when should be quarterly (or vice versa)

---

## Common EDGAR Display Notes

1. **Units:** EDGAR displays in **millions**, our code stores **actual amounts**
   - EDGAR: $554,818 million
   - Our code: $554,818,000,000
   - Just divide our number by 1,000,000 to compare

2. **Negative Numbers:** EDGAR shows as **(amount)** in parentheses
   - EDGAR: ($40,000)
   - Our code: -$40,000,000,000

3. **Column Selection:**
   - Balance Sheet: One date column (June 30, 2024)
   - Income Statement: Usually 2 columns (3 months and 6 months)
   - Cash Flow: Usually 2 columns (6 months current year and prior year)

---

## After Verification

### If All Numbers Match ✅
- **Conclusion:** Reconstruction is faithful and production-ready
- **Confidence Level:** High - we extract exactly what EDGAR displays
- **Ready for:** Phase 2 (Standardization Engine)

### If Numbers Don't Match ❌
- **Action:** Report which specific numbers don't match
- **Need:** Debug the period selection or filtering logic
- **Format:** "Amazon Revenue: Expected $X, Got $Y"

---

## Quick Verification (Minimum)

If you only have time for minimal check:
1. ✅ Check Amazon Total Assets = $554,818M (Balance Sheet)
2. ✅ Check Amazon Revenue = $147,977M (Income Statement, 3-month column)
3. ✅ Check Amazon Operating CF = $44,270M (Cash Flow, 6-month column)

**These 3 numbers prove:**
- Balance Sheet extraction works (instant/point-in-time)
- Income Statement extraction works (quarterly)
- Cash Flow extraction works (YTD)

---

**Ready to verify?** Open the EDGAR URL and check any/all of the numbers above!
