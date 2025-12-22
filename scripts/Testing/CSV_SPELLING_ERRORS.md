# Spelling Errors in Plabel Investigation v2.csv

## Errors to Fix:

1. **Line 12** - Field name typo
   - Current: `property_plant_equipment_ne`
   - Should be: `property_plant_equipment_net`

2. **Line 14** - Field name has extra spaces and typo
   - Current: `operating_lease_ right_of_use _ssets`
   - Should be: `operating_lease_right_of_use_assets`

3. **Line 76** - Inconsistent naming convention
   - Current: `Net-income-from-continuing-operations` (uses hyphens)
   - Should be: `net_income_from_continuing_operations` (uses underscores)

4. **Line 99** - Logic error in pattern
   - Current: `[contains amortization] not [contains amortization]`
   - Should be: `[contains amortization] not [contains depreciation]`
   - Note: Currently says "contains amortization but not amortization" which is impossible

5. **Line 117** - Typo in field name
   - Current: `other_liablilities` (3 i's)
   - Should be: `other_liabilities` (2 i's)

6. **Line 124** - Typo in field name and target
   - Current: `other_aquisitons_and_investments`
   - Should be: `other_acquisitions_and_investments`

## Summary
- **6 spelling/formatting errors** found
- **1 logic error** in pattern matching (line 99)
- All other entries appear correctly formatted
