"""
Statement Reconstruction Engine
================================
Rebuilds financial statements from EDGAR PRE/NUM tables

This module implements Step 1 of the 3-step aggregation approach:
1. Rebuild statements from EDGAR data (this module)
2. Transform to standardized statements (future)
3. Map to Finexus database (future)

Key insight: Rather than mapping 2000+ individual tags, we:
- Rebuild company statements from EDGAR using PRE table hierarchy
- Preserve parent-child aggregation relationships
- Validate that totals reconcile

Author: Generated with Claude Code
Date: 2025-11-10
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class StatementNode:
    """
    Node in financial statement hierarchy

    Represents a single line item (e.g., "Cash", "Total Assets") with:
    - Its position in the hierarchy (level, line number)
    - Its value from NUM table
    - References to parent and children
    """
    tag: str                    # XBRL tag name (e.g., 'Assets')
    plabel: str                 # Presentation label (e.g., 'Total assets')
    level: int                  # Indentation level (0 = root, 1 = child, etc.)
    line: int                   # Line number in presentation order
    value: Optional[float] = None
    children: List['StatementNode'] = field(default_factory=list)
    parent: Optional['StatementNode'] = None
    negating: bool = False      # If True, subtract from parent

    def __repr__(self):
        value_str = f"${self.value:,.0f}" if self.value else "None"
        return f"{'  ' * self.level}{self.plabel} ({self.tag}): {value_str}"


class StatementReconstructor:
    """
    Reconstructs financial statements from EDGAR data

    Usage:
        reconstructor = StatementReconstructor(2024, 3)
        statements = reconstructor.reconstruct_statement(
            cik=1018724,
            adsh='0001018724-24-000130'
        )
    """

    def __init__(self, year: int = 2024, quarter: int = 3):
        """
        Initialize reconstructor for specific quarter

        Args:
            year: Year (e.g., 2024)
            quarter: Quarter (1-4)
        """
        self.year = year
        self.quarter = quarter
        self.base_dir = Path(f'data/sec_data/extracted/{year}q{quarter}')

        # Cache for loaded data (avoid reloading large files)
        self._pre_df: Optional[pd.DataFrame] = None
        self._num_df: Optional[pd.DataFrame] = None
        self._tag_df: Optional[pd.DataFrame] = None
        self._sub_df: Optional[pd.DataFrame] = None

    def _load_table(self, table_name: str) -> pd.DataFrame:
        """Load EDGAR table with caching"""
        cache_attr = f'_{table_name}_df'

        if getattr(self, cache_attr) is None:
            file_path = self.base_dir / f'{table_name}.txt'
            print(f"Loading {table_name}.txt...")
            df = pd.read_csv(file_path, sep='\t', dtype=str, low_memory=False)
            setattr(self, cache_attr, df)
            print(f"  Loaded {len(df):,} rows")

        return getattr(self, cache_attr)

    def load_filing_data(self, adsh: str) -> Dict[str, pd.DataFrame]:
        """
        Load PRE, NUM, TAG data for specific filing

        Args:
            adsh: Accession number (e.g., '0001018724-24-000130')

        Returns:
            Dict with 'pre', 'num', 'tag' DataFrames filtered to this filing
        """
        print(f"\nLoading filing data for {adsh}...")

        # Load full tables (cached)
        pre_df = self._load_table('pre')
        num_df = self._load_table('num')
        tag_df = self._load_table('tag')

        # Filter to this filing
        filing_pre = pre_df[pre_df['adsh'] == adsh].copy()
        filing_num = num_df[num_df['adsh'] == adsh].copy()

        print(f"  PRE rows: {len(filing_pre):,}")
        print(f"  NUM rows: {len(filing_num):,}")

        return {
            'pre': filing_pre,
            'num': filing_num,
            'tag': tag_df  # Full tag table (doesn't filter by adsh)
        }

    def build_hierarchy(self, pre_df: pd.DataFrame, stmt: str = 'BS') -> Optional[StatementNode]:
        """
        Build tree structure from PRE table

        The PRE table shows how companies present their financial statements:
        - report: Report number (one statement may have multiple reports)
        - line: ordering (1, 2, 3, ...)
        - inpth: indentation level (0 = parent, 1 = child, 2 = grandchild)
        - tag: XBRL tag name
        - plabel: presentation label (what appears on statement)
        - negating: whether to subtract from parent

        Note: Some statements (like Amazon) use flat structure (all level 0)
        while others use hierarchical structure (multiple levels)

        Args:
            pre_df: PRE table filtered to specific filing
            stmt: Statement type ('BS', 'IS', 'CF', 'EQ', etc.)

        Returns:
            Root node of statement hierarchy, or None if no data
        """
        # Filter to specific statement type
        stmt_df = pre_df[pre_df['stmt'] == stmt].copy()

        if len(stmt_df) == 0:
            print(f"  Warning: No {stmt} statement found in PRE table")
            return None

        # Many filings have multiple "reports" for one statement
        # (e.g., main statement + parenthetical details)
        # Focus on the largest report (usually the main statement)
        if 'report' in stmt_df.columns:
            report_counts = stmt_df.groupby('report').size()
            main_report = report_counts.idxmax()
            stmt_df = stmt_df[stmt_df['report'] == main_report].copy()
            print(f"\nBuilding hierarchy for {stmt} statement (report {main_report}, {len(stmt_df)} rows)...")
        else:
            print(f"\nBuilding hierarchy for {stmt} statement ({len(stmt_df)} rows)...")

        # Sort by line number to process in presentation order
        stmt_df = stmt_df.sort_values('line')

        # Convert inpth to int (indentation level)
        stmt_df['inpth'] = stmt_df['inpth'].astype(int)
        stmt_df['line'] = stmt_df['line'].astype(int)

        # Handle negating field (may be NaN)
        stmt_df['negating'] = stmt_df['negating'].fillna('false')

        # Check if this is a flat structure (all items at level 0)
        is_flat = (stmt_df['inpth'] == 0).all()

        if is_flat:
            # Flat structure: Create a virtual root and attach all as children
            print("  Detected flat structure (all items at level 0)")
            root = StatementNode(
                tag=f'{stmt}_ROOT',
                plabel=f'{stmt} Statement',
                level=-1,
                line=0
            )

            for _, row in stmt_df.iterrows():
                node = StatementNode(
                    tag=row['tag'],
                    plabel=row.get('plabel', row['tag']),
                    level=row['inpth'],
                    line=row['line'],
                    negating=(row['negating'].lower() == 'true'),
                    parent=root
                )
                root.children.append(node)

            return root

        # Hierarchical structure: Build tree
        print("  Detected hierarchical structure")
        root = None
        stack = []  # Track current parent at each level

        for _, row in stmt_df.iterrows():
            node = StatementNode(
                tag=row['tag'],
                plabel=row.get('plabel', row['tag']),
                level=row['inpth'],
                line=row['line'],
                negating=(row['negating'].lower() == 'true')
            )

            if node.level == 0:
                # Root level (e.g., "Total Assets")
                if root is None:
                    root = node
                    stack = [node]
                else:
                    # Multiple level-0 items
                    # Create virtual root to hold them
                    if root.level != -1:
                        old_root = root
                        root = StatementNode(
                            tag=f'{stmt}_ROOT',
                            plabel=f'{stmt} Statement',
                            level=-1,
                            line=0
                        )
                        root.children.append(old_root)
                        old_root.parent = root

                    root.children.append(node)
                    node.parent = root
                    stack = [root, node]
            else:
                # Child item - attach to parent
                parent_level = node.level - 1

                if parent_level < len(stack):
                    parent = stack[parent_level]
                    parent.children.append(node)
                    node.parent = parent

                    # Update stack for this level
                    if node.level >= len(stack):
                        stack.append(node)
                    else:
                        stack[node.level] = node
                else:
                    print(f"  Warning: Orphan node {node.tag} at level {node.level}")

        return root

    def attach_values(self, hierarchy: StatementNode, num_df: pd.DataFrame,
                     period_focus: str = 'I') -> StatementNode:
        """
        Attach actual values from NUM table to hierarchy

        NUM table contains actual numbers with:
        - tag: XBRL tag name
        - value: numeric value
        - ddate: date (for point-in-time items)
        - qtrs: period (0 = point-in-time, 1 = quarterly, 4 = annual)
        - uom: unit of measure (USD, shares, etc.)

        Strategy:
        - For Balance Sheet (I = Instant): Use most recent point-in-time (qtrs=0)
        - For Income/Cash Flow (D = Duration): Use quarterly (qtrs=1) or YTD

        Args:
            hierarchy: Root node of statement tree
            num_df: NUM table filtered to specific filing
            period_focus: 'I' for instant (BS), 'D' for duration (IS, CF)

        Returns:
            Hierarchy with values attached
        """
        print(f"\nAttaching values from NUM table ({len(num_df):,} rows)...")

        # Convert value to float
        num_df['value'] = pd.to_numeric(num_df['value'], errors='coerce')

        # Build tag->value lookup
        # For each tag, we may have multiple values (different dimensions, dates)
        # Strategy: Take the most common/relevant one

        def get_value_for_tag(tag: str) -> Optional[float]:
            """
            Find best value for this tag

            Strategy to handle dimensional data (segments, axes):
            1. Filter to most recent date
            2. Prefer values with no segments (total/consolidated)
            3. Prefer USD values
            4. Prefer point-in-time for BS, duration for IS/CF
            """
            matches = num_df[num_df['tag'] == tag].copy()

            if len(matches) == 0:
                return None

            # 1. Filter to most recent date
            if 'ddate' in matches.columns:
                max_date = matches['ddate'].max()
                matches = matches[matches['ddate'] == max_date]

            # 2. Prefer values with no segments (consolidated totals)
            # Companies report segment breakdowns, but we want the total
            if 'segments' in matches.columns:
                no_segments = matches[matches['segments'].isna()]
                if len(no_segments) > 0:
                    matches = no_segments

            # 3. Prefer USD values
            if 'uom' in matches.columns:
                usd_matches = matches[matches['uom'] == 'USD']
                if len(usd_matches) > 0:
                    matches = usd_matches

            # 4. Filter by period type if possible
            if 'iord' in matches.columns:
                period_matches = matches[matches['iord'] == period_focus]
                if len(period_matches) > 0:
                    matches = period_matches

            # 5. Prefer qtrs=0 for balance sheet (point-in-time)
            if period_focus == 'I' and 'qtrs' in matches.columns:
                qtrs_0 = matches[matches['qtrs'] == '0']
                if len(qtrs_0) > 0:
                    matches = qtrs_0

            # Take first match after filtering
            return matches.iloc[0]['value']

        def attach_recursive(node: StatementNode):
            """Recursively attach values to tree"""
            node.value = get_value_for_tag(node.tag)

            for child in node.children:
                attach_recursive(child)

        attach_recursive(hierarchy)

        # Count how many values we found
        def count_values(node: StatementNode) -> int:
            count = 1 if node.value is not None else 0
            for child in node.children:
                count += count_values(child)
            return count

        value_count = count_values(hierarchy)
        print(f"  Attached {value_count} values")

        return hierarchy

    def validate_rollups(self, hierarchy: StatementNode, tolerance: float = 0.01) -> Dict:
        """
        Verify that parent = sum(children) for all rollups

        Accounting principle: Parent items should equal sum of children
        Example: Total Assets = Current Assets + Noncurrent Assets

        Args:
            hierarchy: Root node with values attached
            tolerance: Acceptable difference percentage (default 0.01%)

        Returns:
            Dict with validation results:
                - 'valid': bool
                - 'errors': List of validation errors
                - 'warnings': List of warnings
        """
        print(f"\nValidating hierarchy rollups (tolerance: {tolerance}%)...")

        errors = []
        warnings = []

        def validate_node(node: StatementNode):
            """Validate this node and recurse"""
            if not node.children or node.value is None:
                # Leaf node or missing value - skip
                for child in node.children:
                    validate_node(child)
                return

            # Calculate sum of children
            child_sum = 0
            missing_values = []

            for child in node.children:
                if child.value is not None:
                    # Handle negating items (subtract instead of add)
                    if child.negating:
                        child_sum -= child.value
                    else:
                        child_sum += child.value
                else:
                    missing_values.append(child.tag)

            # Compare parent to child sum
            if child_sum != 0:  # Avoid division by zero
                diff = abs(node.value - child_sum)
                diff_pct = (diff / abs(child_sum)) * 100

                if diff_pct > tolerance:
                    errors.append({
                        'node': node.tag,
                        'label': node.plabel,
                        'parent_value': node.value,
                        'child_sum': child_sum,
                        'diff': diff,
                        'diff_pct': diff_pct
                    })

            if missing_values:
                warnings.append({
                    'node': node.tag,
                    'missing_children': missing_values
                })

            # Recurse to children
            for child in node.children:
                validate_node(child)

        validate_node(hierarchy)

        is_valid = len(errors) == 0

        print(f"  Validation: {'PASS' if is_valid else 'FAIL'}")
        print(f"  Errors: {len(errors)}")
        print(f"  Warnings: {len(warnings)}")

        if errors:
            print("\n  Top errors:")
            for err in errors[:5]:
                print(f"    {err['label']}: ${err['parent_value']:,.0f} != ${err['child_sum']:,.0f} ({err['diff_pct']:.2f}% diff)")

        return {
            'valid': is_valid,
            'errors': errors,
            'warnings': warnings
        }

    def reconstruct_statement(self, cik: int, adsh: str, stmt_type: str = 'BS') -> Dict:
        """
        Main entry point: Reconstruct a financial statement

        This is the complete pipeline:
        1. Load filing data (PRE/NUM tables)
        2. Build hierarchy from PRE table
        3. Attach values from NUM table
        4. Validate rollups

        Args:
            cik: Company CIK (e.g., 1018724 for Amazon)
            adsh: Accession number (e.g., '0001018724-24-000130')
            stmt_type: Statement type ('BS', 'IS', 'CF', 'EQ')

        Returns:
            Dict with:
                - 'hierarchy': Root StatementNode
                - 'validation': Validation results
                - 'metadata': Filing metadata
                - 'flat_data': Flattened tag->value dict
        """
        print(f"\n{'='*60}")
        print(f"Reconstructing {stmt_type} statement")
        print(f"CIK: {cik}, ADSH: {adsh}")
        print(f"{'='*60}")

        # Step 1: Load filing data
        filing_data = self.load_filing_data(adsh)

        # Step 2: Build hierarchy
        hierarchy = self.build_hierarchy(filing_data['pre'], stmt_type)

        if hierarchy is None:
            return {
                'error': f"No {stmt_type} statement found",
                'hierarchy': None,
                'validation': None,
                'metadata': {'cik': cik, 'adsh': adsh, 'stmt_type': stmt_type}
            }

        # Step 3: Attach values
        period_focus = 'I' if stmt_type == 'BS' else 'D'
        hierarchy = self.attach_values(hierarchy, filing_data['num'], period_focus)

        # Step 4: Validate
        validation = self.validate_rollups(hierarchy)

        # Step 5: Create flat dict for easy access
        flat_data = {}

        def flatten_recursive(node: StatementNode):
            if node.value is not None:
                flat_data[node.tag] = node.value
            for child in node.children:
                flatten_recursive(child)

        flatten_recursive(hierarchy)

        # Generate EDGAR viewer URL
        cik_padded = str(cik).zfill(10)
        edgar_url = f"https://www.sec.gov/cgi-bin/viewer?action=view&cik={cik_padded}&accession_number={adsh}&xbrl_type=v"

        print(f"\nReconstruction complete!")
        print(f"  Total line items: {len(flat_data)}")
        print(f"  EDGAR viewer: {edgar_url}")

        return {
            'hierarchy': hierarchy,
            'validation': validation,
            'flat_data': flat_data,
            'metadata': {
                'cik': cik,
                'adsh': adsh,
                'stmt_type': stmt_type,
                'year': self.year,
                'quarter': self.quarter,
                'edgar_url': edgar_url
            }
        }

    def print_hierarchy(self, node: StatementNode, max_depth: int = 10):
        """
        Pretty-print statement hierarchy

        Args:
            node: Root node to print
            max_depth: Maximum depth to print (avoid too much output)
        """
        def print_recursive(n: StatementNode, depth: int = 0):
            if depth > max_depth:
                return

            indent = "  " * depth
            value_str = f"${n.value:,.0f}" if n.value else "N/A"
            negating_str = " (subtract)" if n.negating else ""

            print(f"{indent}{n.plabel}: {value_str}{negating_str}")

            for child in n.children:
                print_recursive(child, depth + 1)

        print_recursive(node)


def get_adsh_for_company(cik: int, year: int, quarter: int) -> Optional[str]:
    """
    Helper: Find ADSH for a company in a specific quarter

    Args:
        cik: Company CIK
        year: Year
        quarter: Quarter (1-4)

    Returns:
        ADSH string, or None if not found
    """
    sub_path = Path(f'data/sec_data/extracted/{year}q{quarter}/sub.txt')

    if not sub_path.exists():
        print(f"Error: {sub_path} not found")
        return None

    sub_df = pd.read_csv(sub_path, sep='\t', dtype=str)
    sub_df['cik'] = sub_df['cik'].astype(int)

    matches = sub_df[sub_df['cik'] == cik]

    if len(matches) == 0:
        print(f"No filing found for CIK {cik} in {year}Q{quarter}")
        return None

    # Return first match (most recent if multiple)
    return matches.iloc[0]['adsh']


if __name__ == '__main__':
    """Test the reconstructor with Amazon"""

    print("Testing StatementReconstructor with Amazon (CIK: 1018724)")
    print("=" * 60)

    # Get ADSH for Amazon 2024Q3
    adsh = get_adsh_for_company(cik=1018724, year=2024, quarter=3)

    if adsh:
        print(f"Found ADSH: {adsh}")

        # Reconstruct balance sheet
        reconstructor = StatementReconstructor(2024, 3)
        result = reconstructor.reconstruct_statement(
            cik=1018724,
            adsh=adsh,
            stmt_type='BS'
        )

        if result['hierarchy']:
            print("\n" + "=" * 60)
            print("BALANCE SHEET HIERARCHY (top 2 levels)")
            print("=" * 60)
            reconstructor.print_hierarchy(result['hierarchy'], max_depth=2)

            print("\n" + "=" * 60)
            print("KEY METRICS")
            print("=" * 60)
            flat = result['flat_data']

            if 'Assets' in flat:
                print(f"Total Assets: ${flat['Assets']:,.0f}")
            if 'Liabilities' in flat:
                print(f"Total Liabilities: ${flat['Liabilities']:,.0f}")
            if 'StockholdersEquity' in flat:
                print(f"Stockholders Equity: ${flat['StockholdersEquity']:,.0f}")
            if 'LiabilitiesAndStockholdersEquity' in flat:
                print(f"Total Liabilities + Equity: ${flat['LiabilitiesAndStockholdersEquity']:,.0f}")

            print(f"\nAll balance sheet tags found:")
            for tag in sorted(flat.keys()):
                print(f"  {tag}: ${flat[tag]:,.0f}" if not pd.isna(flat[tag]) else f"  {tag}: N/A")

            # Check balance sheet equation
            # Note: Some companies report total liabilities separately, others don't
            assets = flat.get('Assets')
            equity = flat.get('StockholdersEquity')
            liab_and_equity = flat.get('LiabilitiesAndStockholdersEquity')

            if assets and liab_and_equity:
                diff = abs(assets - liab_and_equity)
                print(f"\nBalance Sheet Equation Check:")
                print(f"  Assets: ${assets:,.0f}")
                print(f"  Liabilities + Equity: ${liab_and_equity:,.0f}")
                print(f"  Difference: ${diff:,.0f}")
                print(f"  Valid: {diff < 1000}")  # Allow small rounding
