# Pattern Audit Report

**Date:** 2025-11-29
**Purpose:** Systematic comparison of CSV patterns vs code implementation

---

## Balance Sheet Patterns

### ✓ MATCHES (Correct Patterns)

| Field | CSV Pattern | Code Location | Status |
|-------|-------------|---------------|---------|
| short_term_investments | `[short-term AND investments] OR [marketable AND securities] OR [marketable AND investments]` | Lines 172-175 | ✓ FIXED |
| other_current_assets | `[contains 'other' and contains 'current assets']` | Line 186-187 | ✓ MATCH |
| other_non_current_assets | `[contains 'other' and (contains 'non current' or contains 'non-current') and contains 'assets']` | Line 207-208 | ✓ MATCH |
| account_payables | `[(contains 'accounts' or contains 'account') and (contains 'payable' or contains 'payables']` | Line 212-213 | ✓ MATCH |
| accrued_payroll | `[contains 'employment' or contains ' compensation' or contains ' wages' or contains 'salaries' or contains 'payroll']` | Line 214-215 | ✓ MATCH |
| other_current_liabilities | `[contains 'other' and contains 'current liabilities']` | Line 230-231 | ✓ MATCH |
| commitments_and_contingencies | `[contains 'commitment' or contains 'contigencies']` | Line 249-250 | ✓ MATCH |
| other_non_current_liabilities | `[contains 'other' and contains 'non-current' and contains 'liabilities']` | Line 253-254 | ✓ MATCH |

### ⚠️ PARTIAL MATCHES (Need Review)

| Field | Issue | CSV Pattern | Code Pattern | Line |
|-------|-------|-------------|--------------|------|
| cash_and_cash_equivalents | Code requires 'equivalents', CSV just needs 'cash' with exclusions | `[contains 'cash'] not [contains 'restricted'] not [contains 'cash and short-term investments']` | `'cash' in p and ('equivalent' in p or 'equivalents' in p)` | 169-170 |
| account_receivables_net | Missing 'notes receivable' variant | `min{[trade AND receivable] OR [accounts AND receivable] OR [notes AND receivable]}` | Two patterns: trade, accounts (missing notes) | 176-179 |
| inventory | Code uses substring, missing 'materials and supplies' | `[inventory/inventories] OR [materials and supplies NOT inventory]` | `'inventor' in p` | 180-181 |
| prepaids | CSV more specific, code more inclusive | `[prepayments OR prepaid expenses]` | `'prepaid' in p` | 182-183 |
| property_plant_equipment_net | CSV uses min{}, code requires 'net' | `min{[property OR plant OR plants OR premises OR equipment]}` | `('property' in p or 'plant' in p or 'equipment' in p or 'ppe' in p) and ('net' in p or 'property plant and equipment' in p)` | 191-192 |
| long_term_investments | CSV uses position_after, code uses line_num check | `[investments OR marketable securities] AND [position_after # total_current_assets]` | `('investment' in p or 'marketable securities' in p) and line_num > total_current_assets` | 193-194 |
| goodwill | Match but could use exact CSV | `[contains 'goodwill'] not [contains 'intangible']` | `'goodwill' in p and 'intangible' not in p` | 195-196 |
| intangible_assets | Missing 'intangibles' plural, no goodwill exclusion | `[contains 'intangible' or contains 'intangibles'] not [contains 'goodwill']` | `'intangible' in p` | 197-198 |
| tax_assets (deferred_tax_assets) | Code adds 'asset' requirement | `[deferred AND (tax OR taxes)] AND [position_before # total_assets]` | `'deferred' in p and ('tax' in p or 'taxes' in p) and 'asset' in p` | 203-204 |
| accrued_expenses | CSV has more exclusions | `[accrued] NOT [employment OR compensation OR wages OR salaries OR payroll OR taxes]` | `'accrued' in p and not any(x in p for x in ['employment', 'compensation', 'wages', 'salaries', 'payroll', 'tax', 'taxes'])` | 216-217 |
| short_term_debt | CSV more comprehensive | `[(borrowings OR debt OR notes OR loan OR loans) NOT (long-term OR long term)] OR [(one year OR long-term) AND within] OR [current maturities OR current portion]` | `('short term' in p or 'current portion' in p) and ('debt' in p or 'borrowing' in p or 'note' in p)` | 218-219 |
| long_term_debt | CSV more detailed | `[notes OR note OR borrowings OR debt] AND [long-term OR non-current OR after one year OR after 12 months OR after one year]` | `('note' in p or 'notes' in p or 'borrowing' in p or 'debt' in p) and ('long term' in p or 'non current' in p)` | 235-236 |

### ❌ MISSING PATTERNS (Not Implemented or Wrong Field Name)

| CSV Field | CSV Pattern | Notes |
|-----------|-------------|-------|
| cash_and_short_term_investments | `[contains 'cash and short-term investments']` | Not in code |
| other_receivables | `[contains 'other receivables' or contains 'other account receivables' or contains'other accounts rereceivables']` | Not in code |
| finance_lease_right_of_use_assets | `[(finance OR capital OR financial) AND (lease OR leases OR right of use OR rou)] AND [position_before # total_assets]` | Code has pattern but missing 'financial' variant (line 199-200) |
| operating_lease_right_of_use_assets | `[(operating OR operation) AND (lease OR leases OR right of use OR rou)] AND [position_before # total_assets]` | Code has pattern (line 201-202) but should verify position check |
| goodwill_and_intangible_assets | `[contains 'goodwill' and contains 'intangible']` | Not in code |
| total_non_current_assets | `[contains 'total' and (contains 'non current assets' or contains 'non-current assets')]` | Not in code (was removed per user request) |
| other_payables | `[contains 'other' and contains 'payables']` | Not in code |
| deferred_revenue | `[contains 'unearned' or contains 'unexpired']` | Code has it but missing 'unexpired' (line 220-221) |
| tax_payables | `[(contains 'payables' or contains 'payable') and contains 'income taxes']` | Code pattern different: `('tax' in p or 'taxes' in p) and ('payable' in p or 'current' in p)` (line 222-223) |
| finance_lease_obligations_current | `[current OR short-term] AND [(finance OR capital) AND (lease OR leases OR right of use OR rou)] AND [position_after # total_assets]` | Code returns 'capital_lease_obligations_current' (wrong name) (line 224-225) |
| operating_lease_obligations_current | `[current OR short-term] AND [(operating OR operation) AND (lease OR leases OR right of use OR rou)] AND [position_after # total_assets]` | Code has it (line 226-227) |
| deferred_tax_liabilities_non_current | `[deferred AND taxes] AND [position_after # total_current_liabilities]` | Code has it (lines 241-244) |
| finance_lease_obligations_non_current | `[(finance OR capital) AND (lease OR leases OR right of use OR rou)] AND [position_after # total_current_liabilities]` | Code returns 'finance_lease_obligations_non_current' ✓ (line 245-246) |
| operating_lease_obligations_non_current | `[(operating OR operation) AND (lease OR leases OR right of use OR rou)] AND [position_after # total_current_liabilities]` | Code has it (line 247-248) |
| pension_and_postretirement_benefits | `[(pension OR postrerirement OR retirement) AND (liabilities OR obligations)]` | Code has typo in CSV or code? (line 237-238) |
| deferred_revenue_non_current | `[(deferred revenue OR unearned) AND (long-term OR non-current OR net of current portion)]` | Code has it (line 239-240) |
| treasury_stock | `[(treasury stock OR treasury stocks) AND (cost OR par)]` | Code missing 'cost' or 'par' requirement (line 268-269) |
| preferred_stock | `[(preferred stock OR preferred stocks) AND (cost OR par)]` | Code missing 'cost' or 'par' requirement (line 260-261) |
| common_stock | `[(common stock OR common stocks OR common shares OR common share) AND (cost OR par)]` | Code missing 'cost' or 'par' requirement (line 258-259) |
| retained_earnings | `[(accumulated OR retained) AND (earnings AND deficit)]` | Code only checks 'retained earning' (line 264-265) |
| additional_paid_in_capital | `[(additional OR excess) AND (capital OR proceeds OR fund)]` | Code pattern simpler (line 262-263) |
| accumulated_other_comprehensive_income_loss | `[accumulated AND other AND comprehensive]` | Code has it (line 266-267) ✓ |
| minority_interest | `[noncontrolling OR non-controlling OR minority] AND [interest OR interests]` | Code has it (line 270-271) ✓ |
| total_stockholders_equity | `[total AND equity] NOT [other OR liabilities OR total equity]` | Direct mapping (line 272-273) |
| total_equity | `[equals to 'total equity' or equals to 'equity, total']` | Not in code |
| redeemable_non_controlling_interests | `[noncontrolling interests in subsidiaries]` | Not in code |

---

## Income Statement Patterns

### ✓ MATCHES

| Field | Status |
|-------|--------|
| gross_profit | Direct mapping ✓ |
| operating_income | Direct mapping ✓ |
| income_before_tax | Direct mapping ✓ |
| income_tax_expense | Direct mapping ✓ |
| net_income | Direct mapping ✓ |
| eps | Direct mapping ✓ |
| eps_diluted | Direct mapping ✓ |
| weighted_average_shares_outstanding | Direct mapping ✓ |
| weighted_average_shares_outstanding_diluted | Direct mapping ✓ |

### ⚠️ NEEDS REVIEW

| Field | CSV Pattern | Status |
|-------|-------------|--------|
| revenue | `[total revenues OR net revenue OR net revenues OR revenues OR net sales OR sales OR ...]` NOT [marketing OR administrative OR general] | Fixed (De Morgan's Law) ✓ |
| cost_of_revenue | `[cost AND (sold OR sale OR sales OR revenue OR revenues)]` | Need to verify |
| research_and_development_expenses | `[research OR development OR R&D OR technology]` | Need to verify |
| general_and_administrative_expenses | `[general AND administrative] NOT [selling OR marketing OR advertising OR promotion OR sales]` | Need to verify |
| sales_and_marketing_expenses | `[sales OR marketing OR selling OR sale OR advertising OR promotion] NOT [administrative]` | Need to verify |
| selling_general_and_administrative_expenses | `[sales OR marketing OR selling OR sale OR advertising OR promotion] AND [administrative]` | Need to verify |
| other_expenses | `[other AND (expenses OR expense OR income)]` | Need to verify |
| operating_expenses | `[total operating expenses OR total expenses]` | Need to verify |

---

## Cash Flow Patterns

### ✓ CONTROL ITEMS (Direct Mapping)

| Field | Status |
|-------|--------|
| net_income_starting_line | Direct mapping ✓ |
| net_cash_provided_by_operating_activities | Direct mapping ✓ |
| net_cash_provided_by_investing_activities | Direct mapping ✓ |
| net_cash_provided_by_financing_activities | Direct mapping ✓ |
| cash_at_beginning_of_period | Direct mapping ✓ (with tag fallback) |
| cash_at_end_of_period | Direct mapping ✓ (with tag fallback) |

### ⚠️ NEEDS REVIEW

All non-control cash flow line items need systematic review against CSV lines 93-161.

---

## Priority Fixes

### HIGH PRIORITY (Common Items)

1. **cash_and_cash_equivalents** - Add exclusions for 'restricted' and 'cash and short-term investments'
2. **inventory** - Add 'materials and supplies' variant
3. **account_receivables_net** - Add 'notes receivable' variant
4. **common_stock, preferred_stock, treasury_stock** - Add 'cost' or 'par' requirement
5. **retained_earnings** - Fix pattern to match CSV (accumulated OR retained) AND (earnings AND deficit)
6. **intangible_assets** - Add 'intangibles' plural and goodwill exclusion
7. **short_term_debt** - Expand to match CSV comprehensive pattern
8. **tax_payables** - Fix to require 'income taxes'
9. **deferred_revenue** - Add 'unexpired' variant
10. **finance_lease_obligations_current** - Fix field name from 'capital_lease_obligations_current'

### MEDIUM PRIORITY

11. **property_plant_equipment_net** - Review 'net' requirement vs CSV min{}
12. **additional_paid_in_capital** - Verify pattern completeness
13. All Income Statement line items (non-control)
14. All Cash Flow line items (non-control)

### LOW PRIORITY

15. **cash_and_short_term_investments** - Add if needed
16. **other_receivables** - Add if needed
17. **goodwill_and_intangible_assets** - Add combined field
18. **total_equity** - Add if different from total_stockholders_equity
19. **redeemable_non_controlling_interests** - Add if needed

---

**Next Steps:**
1. Fix HIGH PRIORITY patterns
2. Test on Amazon, Microsoft, Starbucks
3. Review MEDIUM PRIORITY patterns
4. Complete systematic audit of IS and CF patterns
