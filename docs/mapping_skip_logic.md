# Balance Sheet Mapping Skip Logic

## Overview

When mapping balance sheet line items to standardized fields, we need to avoid mapping items that are "grandchildren" or deeper in the calculation hierarchy. This prevents double counting and confusing mappings.

## The Problem

In XBRL, the calculation linkbase defines parent-child relationships:

```
Assets (control item)
├── AssetsCurrent (control item)
│   ├── CashAndCashEquivalents (direct child - MAP)
│   │   ├── CashOnHand (grandchild - SKIP)
│   │   └── CashInBank (grandchild - SKIP)
│   ├── AccountsReceivable (direct child - MAP)
│   └── Inventory (direct child - MAP)
└── AssetsNoncurrent (control item)
    ├── PropertyPlantEquipmentNet (direct child - MAP)
    └── ...
```

If we map both `CashAndCashEquivalents` AND its children (`CashOnHand`, `CashInBank`), we would double count.

## The Solution

**Simple rule: Only map items whose parent is a control item.**

### Control Items

Control items are the structural totals we use to organize the balance sheet:

- `total_current_assets` (tag: `AssetsCurrent`)
- `total_non_current_assets` (tag: `AssetsNoncurrent`)
- `total_assets` (tag: `Assets`)
- `total_current_liabilities` (tag: `LiabilitiesCurrent`)
- `total_non_current_liabilities` (tag: `LiabilitiesNoncurrent`)
- `total_liabilities` (tag: `Liabilities`)
- `total_stockholders_equity` (tag: `StockholdersEquity`)
- `total_equity` (tag: `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest`)
- `total_liabilities_and_total_equity` (tag: `LiabilitiesAndStockholdersEquity`)

### Algorithm

For each line item (excluding control items themselves):

1. Look up the item's tag in the **reverse calc graph** to find its parent tag
2. Check if the parent tag is a **control item tag**
3. If **yes** → **map the item** (it's a direct child of a control item)
4. If **no** → **skip the item** (it's a grandchild or deeper)

### Data Structures Needed

1. **Reverse calc graph** (child → parent lookup):
   ```python
   parent_lookup = {
       'CashAndCashEquivalentsAtCarryingValue': 'AssetsCurrent',
       'CashOnHand': 'CashAndCashEquivalentsAtCarryingValue',
       'AccountsReceivableNetCurrent': 'AssetsCurrent',
       ...
   }
   ```

2. **Control item tags set**:
   ```python
   control_tags = {
       'assetscurrent',
       'assetsnoncurrent',
       'assets',
       'liabilitiescurrent',
       'liabilitiesnoncurrent',
       'liabilities',
       'stockholdersequity',
       'stockholdersequityincludingportionattributabletononcontrollinginterest',
       'liabilitiesandstockholdersequity',
       # ... other variations
   }
   ```

### Example

Given these line items:
- `Cash and Cash Equivalents` (tag: `CashAndCashEquivalentsAtCarryingValue`)
- `Cash on Hand` (tag: `CashOnHand`)
- `Accounts Receivable` (tag: `AccountsReceivableNetCurrent`)

Processing:
1. `Cash and Cash Equivalents`:
   - Parent: `AssetsCurrent`
   - Is `AssetsCurrent` a control tag? **Yes**
   - **MAP** this item

2. `Cash on Hand`:
   - Parent: `CashAndCashEquivalentsAtCarryingValue`
   - Is `CashAndCashEquivalentsAtCarryingValue` a control tag? **No**
   - **SKIP** this item

3. `Accounts Receivable`:
   - Parent: `AssetsCurrent`
   - Is `AssetsCurrent` a control tag? **Yes**
   - **MAP** this item

## Implementation Notes

### Where to Apply

This skip logic should be applied in:
- `map_statement()` in `map_financial_statements.py`
- `map_balance_sheet_strategy2()` in `map_financial_statements_strategy2.py`

### Building the Reverse Lookup

When loading the calc graph in `statement_reconstructor.py`, also build the reverse lookup:

```python
def build_calc_graph(cal_tree):
    # ... existing code to build calc_graph ...

    # Build reverse lookup (child → parent)
    parent_lookup = {}
    for parent_tag, children in calc_graph.items():
        for child_tag, weight in children:
            parent_lookup[child_tag] = parent_tag

    return calc_graph, parent_lookup
```

### Handling Missing Parents

Some items may not have a parent in the calc graph (e.g., custom extension tags). In this case:
- If no parent found → **map the item** (assume it's a direct child)

This is safer than skipping, as we don't want to miss legitimate items.

## Benefits

1. **No double counting**: Only map items at one level of the hierarchy
2. **Cleaner mappings**: Avoid mapping obscure sub-items that are hard to categorize
3. **Simpler residual calculation**: The "other_*" residuals capture everything not mapped at the direct child level
4. **Consistent behavior**: Same logic for all companies regardless of how detailed their XBRL is
