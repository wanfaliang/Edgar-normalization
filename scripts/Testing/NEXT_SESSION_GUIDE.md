# Quick Start Guide for Next Session
**Focus:** Build Statement Reconstruction & Aggregation Engine

---

## What to Do First

### 1. Read Context (5 minutes)
- Review `SESSION_SUMMARY_2025-11-10.md`
- Understand the 3-step aggregation approach
- Key insight: Aggregation > Simple mapping

### 2. Verify Data (2 minutes)
```bash
# Check data files exist
ls data/sec_data/extracted/2024q3/pre.txt
ls data/sec_data/extracted/2024q3/num.txt
ls data/sec_data/extracted/2024q3/tag.txt
ls data/sec_data/extracted/2024q3/company_tag_profiles/
```

---

## Implementation Checklist

### Phase 1A: Statement Reconstructor (First 2 hours)

**File to create:** `src/statement_reconstructor.py`

```python
"""
Statement Reconstruction Engine
================================
Rebuilds financial statements from EDGAR PRE/NUM tables
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass

@dataclass
class StatementNode:
    """Node in statement hierarchy"""
    tag: str
    plabel: str
    level: int  # indentation level
    line: int   # line number
    value: float = None
    children: List['StatementNode'] = None
    parent: 'StatementNode' = None

class StatementReconstructor:
    """Reconstructs financial statements from EDGAR data"""

    def __init__(self, year: int = 2024, quarter: int = 3):
        self.year = year
        self.quarter = quarter
        self.base_dir = Path(f'data/sec_data/extracted/{year}q{quarter}')

    def load_filing_data(self, adsh: str) -> Dict[str, pd.DataFrame]:
        """Load PRE, NUM, TAG for specific filing"""
        # TODO: Filter tables by adsh
        pass

    def build_hierarchy(self, pre_df: pd.DataFrame, stmt: str = 'BS') -> StatementNode:
        """
        Build tree structure from PRE table

        Uses:
        - inpth: indentation level (0, 1, 2, ...)
        - line: ordering
        - tag: XBRL tag name
        - plabel: presentation label
        """
        # TODO: Parse PRE table into tree
        pass

    def attach_values(self, hierarchy: StatementNode, num_df: pd.DataFrame) -> StatementNode:
        """Attach actual values from NUM table"""
        # TODO: Match tags and attach values
        pass

    def validate_rollups(self, hierarchy: StatementNode) -> Dict:
        """Verify parent = sum(children)"""
        # TODO: Validate aggregations
        pass

    def reconstruct_statement(self, cik: int, adsh: str, stmt_type: str = 'BS') -> Dict:
        """
        Main entry point: reconstruct a statement

        Args:
            cik: Company CIK
            adsh: Accession number
            stmt_type: 'BS', 'IS', 'CF', etc.

        Returns:
            Dict with hierarchy and values
        """
        # TODO: Orchestrate full reconstruction
        pass
```

**Test it:**
```python
# Test with Amazon 2024Q3
reconstructor = StatementReconstructor(2024, 3)
bs = reconstructor.reconstruct_statement(
    cik=1018724,
    adsh='0001018724-24-000130',
    stmt_type='BS'
)
print(bs['total_assets'])  # Should match EDGAR
```

### Phase 1B: PRE Table Parser (30 minutes)

**Key logic:**
```python
def parse_pre_hierarchy(pre_df: pd.DataFrame) -> StatementNode:
    """
    PRE table structure:
    - line: ordering (1, 2, 3, ...)
    - inpth: level (0 = parent, 1 = child, 2 = grandchild)
    - tag: XBRL tag
    - plabel: display label

    Algorithm:
    1. Sort by line number
    2. Track current parent at each level
    3. Attach children to parents based on inpth
    """

    sorted_rows = pre_df.sort_values('line')
    root = None
    stack = []  # Track parents at each level

    for _, row in sorted_rows.iterrows():
        node = StatementNode(
            tag=row['tag'],
            plabel=row['plabel'],
            level=row['inpth'],
            line=row['line']
        )

        if node.level == 0:
            root = node
            stack = [node]
        else:
            # Find parent (previous level)
            parent = stack[node.level - 1]
            parent.children.append(node)
            node.parent = parent

            # Update stack
            if len(stack) <= node.level:
                stack.append(node)
            else:
                stack[node.level] = node

    return root
```

### Phase 1C: Value Attachment (30 minutes)

**Key logic:**
```python
def attach_values_from_num(hierarchy: StatementNode, num_df: pd.DataFrame):
    """
    NUM table structure:
    - tag: XBRL tag
    - value: numeric value
    - ddate: date
    - qtrs: period (0 = point-in-time, 1 = quarterly, 4 = annual)

    Match:
    1. Filter NUM to relevant period
    2. For each node, find matching tag in NUM
    3. Attach value to node
    4. Recurse to children
    """

    def attach_to_node(node: StatementNode):
        # Find matching row in NUM table
        matches = num_df[num_df['tag'] == node.tag]

        if len(matches) > 0:
            # Take most recent/relevant value
            node.value = matches.iloc[0]['value']

        # Recurse
        if node.children:
            for child in node.children:
                attach_to_node(child)

    attach_to_node(hierarchy)
```

### Phase 1D: Validation (30 minutes)

**Key logic:**
```python
def validate_hierarchy(node: StatementNode, errors: List[str] = None):
    """
    Verify accounting equation:
    - Parent should equal sum of children
    - Tolerance: 0.01% for rounding

    Returns list of validation errors
    """
    if errors is None:
        errors = []

    if node.children and node.value:
        child_sum = sum(
            child.value for child in node.children
            if child.value is not None
        )

        if child_sum > 0:
            diff_pct = abs(node.value - child_sum) / child_sum * 100

            if diff_pct > 0.01:
                errors.append(
                    f"{node.tag} ({node.plabel}): "
                    f"${node.value:,.0f} != ${child_sum:,.0f} "
                    f"({diff_pct:.2f}% diff)"
                )

    # Recurse
    if node.children:
        for child in node.children:
            validate_hierarchy(child, errors)

    return errors
```

---

## Test Companies

**Use these for testing (diverse):**
1. Amazon (CIK: 1018724) - Large tech
2. Home Depot (CIK: 354950) - Retail
3. M&T Bank (CIK: 36270) - Financial
4. Procter & Gamble (CIK: 80424) - Consumer goods

**Get ADSH:**
```python
import pandas as pd
sub_df = pd.read_csv('data/sec_data/extracted/2024q3/sub.txt', sep='\t')
amazon = sub_df[sub_df['cik'] == 1018724]
print(amazon['adsh'].iloc[0])
# Output: 0001018724-24-000130
```

---

## Expected Output

### Example: Amazon Balance Sheet Hierarchy

```
Assets (Total: $500B)
├── AssetsCurrent (Total: $200B)
│   ├── CashAndCashEquivalents ($50B)
│   ├── MarketableSecurities ($30B)
│   ├── Inventories ($40B)
│   └── AccountsReceivableNet ($30B)
└── AssetsNoncurrent (Total: $300B)
    ├── PropertyPlantAndEquipment ($200B)
    ├── Goodwill ($50B)
    └── OtherAssetsNoncurrent ($50B)
```

**Validation:**
- ✅ Assets ($500B) = AssetsCurrent ($200B) + AssetsNoncurrent ($300B)
- ✅ AssetsCurrent ($200B) = sum of 4 children
- ✅ All totals reconcile

---

## Common Issues & Solutions

### Issue 1: Multiple tag instances
**Problem:** Same tag appears multiple times with different dimensions
**Solution:** Filter by most relevant dimension (usually latest period, no dimensions)

### Issue 2: Missing values
**Problem:** Tag in PRE but no value in NUM
**Solution:** Mark as None, don't fail validation

### Issue 3: Rounding differences
**Problem:** Parent != sum(children) by small amount
**Solution:** Use tolerance (0.01%)

### Issue 4: Complex hierarchies
**Problem:** Multiple levels of nesting
**Solution:** Recursive tree parsing handles any depth

---

## Success Criteria

Before moving to Phase 2, verify:
- ✅ Can parse PRE table into hierarchy
- ✅ Can attach values from NUM table
- ✅ Validation passes for all test companies
- ✅ Total Assets = Total Liabilities + Equity
- ✅ All major rollups reconcile (Current Assets, etc.)

---

## Files to Reference

**Data files:**
- `data/sec_data/extracted/2024q3/pre.txt` - Statement structure
- `data/sec_data/extracted/2024q3/num.txt` - Values
- `data/sec_data/extracted/2024q3/sub.txt` - Filing metadata

**Existing code to reference:**
- `src/company_tag_extractor.py` - Shows how to load EDGAR data
- `src/add_statement_type_to_tags.py` - Shows PRE table usage

**Target schema:**
- `src/database/models_from_finexus.py` - Our target fields

---

## Phase 2 Preview (Don't start yet)

Once Phase 1 works, Phase 2 will:
1. Define standard schema (~40 Balance Sheet items)
2. Create aggregation rules (tag → standard item)
3. Apply conservative bucketing
4. Generate confidence scores

**But first:** Get statement reconstruction working perfectly!

---

## Quick Commands

```bash
# Create the file
touch src/statement_reconstructor.py

# Test imports
python -c "import pandas as pd; print('OK')"

# Check data
python -c "
import pandas as pd
pre = pd.read_csv('data/sec_data/extracted/2024q3/pre.txt', sep='\t')
print(f'PRE: {len(pre):,} rows')
"

# Start coding!
```

---

**Ready to code? Start with Phase 1A!**
