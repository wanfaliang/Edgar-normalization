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
from config import config


@dataclass
class StatementNode:
    """
    Node in financial statement hierarchy

    Represents a single line item (e.g., "Cash", "Total Assets") with:
    - Its position in the hierarchy (level, line number)
    - Its values from NUM table (multi-period support)
    - Rich metadata from PRE, NUM, and TAG tables
    - References to parent and children
    """
    # Core identification
    tag: str                    # XBRL tag name (e.g., 'Assets')
    plabel: str                 # Presentation label (e.g., 'Total assets')

    # PRE table fields
    stmt: str = None            # Statement type (BS, IS, CF, etc.)
    report: str = None          # Report number
    line: int = None            # Line number in presentation order
    level: int = 0              # Indentation level (inpth)
    negating: bool = False      # If True, subtract from parent

    # NUM table fields - Multi-period support
    values: Dict[Tuple[str, str], float] = field(default_factory=dict)  # {(ddate, qtrs): value}
    value: Optional[float] = None  # Kept for backward compatibility (last period)
    ddate: str = None           # Date (e.g., '20240630') - last period
    qtrs: str = None            # Duration quarters (0, 1, 2, 3, 4) - last period
    uom: str = None             # Unit of measure (USD, shares, etc.)
    segments: str = None        # Segment (should be NaN for consolidated)
    coreg: str = None           # Co-registrant (should be NaN for parent)

    # TAG table fields
    custom: str = None          # Is custom extension tag (0=standard, 1=custom)
    tlabel: str = None          # Standard taxonomy label
    datatype: str = None        # Data type (monetary, shares, etc.)
    iord: str = None            # Instant or Duration (I/D)
    crdr: str = None            # Credit or Debit (C/D)

    # Hierarchy
    children: List['StatementNode'] = field(default_factory=list)
    parent: Optional['StatementNode'] = None

    # Calc graph integration (from XBRL calculation linkbase)
    is_sum: bool = False  # True if this tag is a parent in calc graph
    calc_children: List[Tuple[str, float]] = field(default_factory=list)  # [(child_tag, weight), ...]

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
        self.base_dir = config.storage.extracted_dir / f'{year}q{quarter}'

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

    def load_filing_data(self, adsh: str) -> Dict:
        """
        Load PRE, NUM, TAG, SUB data for specific filing

        Args:
            adsh: Accession number (e.g., '0001018724-24-000130')

        Returns:
            Dict with 'pre', 'num', 'tag' DataFrames and 'sub' metadata Series
        """
        print(f"\nLoading filing data for {adsh}...")

        # Load full tables (cached)
        pre_df = self._load_table('pre')
        num_df = self._load_table('num')
        tag_df = self._load_table('tag')
        sub_df = self._load_table('sub')

        # Filter to this filing
        filing_pre = pre_df[pre_df['adsh'] == adsh].copy()
        filing_num = num_df[num_df['adsh'] == adsh].copy()
        filing_sub = sub_df[sub_df['adsh'] == adsh]

        if len(filing_sub) == 0:
            raise ValueError(f"Filing {adsh} not found in SUB table")

        filing_sub = filing_sub.iloc[0]  # Get as Series

        print(f"  PRE rows: {len(filing_pre):,}")
        print(f"  NUM rows: {len(filing_num):,}")
        print(f"  Filing: {filing_sub['name']} {filing_sub['form']} FY{filing_sub['fy']} {filing_sub['fp']}")

        return {
            'pre': filing_pre,
            'num': filing_num,
            'tag': tag_df,  # Full tag table (doesn't filter by adsh)
            'sub': filing_sub  # Submission metadata
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
        main_report = None
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
                stmt=stmt,
                report=main_report,
                level=-1,
                line=0
            )

            for _, row in stmt_df.iterrows():
                node = StatementNode(
                    tag=row['tag'],
                    plabel=row.get('plabel', row['tag']),
                    stmt=stmt,
                    report=main_report,
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
                stmt=stmt,
                report=main_report,
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
                            stmt=stmt,
                            report=main_report,
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
                     tag_df: pd.DataFrame, sub_metadata: pd.Series, stmt_type: str) -> StatementNode:
        """
        Attach actual values from NUM table to hierarchy, along with rich metadata
        from NUM and TAG tables.

        Uses SUB metadata to determine the correct period (ddate, qtrs) for each
        statement type, ensuring we extract the values that appear on the primary
        financial statements.

        Args:
            hierarchy: Root node of statement tree
            num_df: NUM table filtered to specific filing
            tag_df: Full TAG table for looking up tag metadata
            sub_metadata: Series from SUB table with period, fp, fy, etc.
            stmt_type: Statement type ('BS', 'IS', 'CF', etc.)

        Returns:
            Hierarchy with values and metadata attached
        """
        print(f"\nAttaching values from NUM table ({len(num_df):,} rows)...")

        # Convert value to float
        num_df = num_df.copy()
        num_df['value'] = pd.to_numeric(num_df['value'], errors='coerce')

        # Determine correct ddate and qtrs based on SUB metadata and statement type
        period = sub_metadata['period']  # e.g., '20240630'
        fp = sub_metadata['fp']          # e.g., 'Q2', 'FY'

        if stmt_type == 'BS':
            # Balance Sheet: instant/point-in-time at period end
            target_ddate = period
            target_qtrs = '0'
        elif stmt_type in ['IS', 'CI']:
            # Income Statement: quarterly for 10-Q, annual for 10-K
            target_ddate = period
            if fp == 'FY':
                target_qtrs = '4'  # Annual
            else:
                target_qtrs = '1'  # Quarterly (Q1, Q2, Q3)
        elif stmt_type == 'CF':
            # Cash Flow: YTD based on quarter for 10-Q, annual for 10-K
            target_ddate = period
            if fp == 'Q1':
                target_qtrs = '1'
            elif fp == 'Q2':
                target_qtrs = '2'
            elif fp == 'Q3':
                target_qtrs = '3'
            elif fp == 'FY':
                target_qtrs = '4'
            else:
                target_qtrs = '1'  # Fallback
        elif stmt_type == 'EQ':
            # Equity: typically duration for the period
            target_ddate = period
            target_qtrs = '1' if fp in ['Q1', 'Q2', 'Q3'] else '4'
        else:
            # Unknown statement type - use heuristic
            target_ddate = period
            target_qtrs = '0'

        print(f"  Filtering NUM to: ddate={target_ddate}, qtrs={target_qtrs}, segments=NaN, coreg=NaN")

        # Get all available instant dates for beginning cash inference
        instant_dates_all = num_df[(num_df['qtrs'] == '0') &
                                   (num_df['segments'].isna()) &
                                   (num_df['coreg'].isna())]['ddate'].unique()
        instant_dates_all = sorted(instant_dates_all)

        print(f"  Available instant dates: {len(instant_dates_all)} dates")

        def infer_beginning_cash_date(ending_ddate: str, qtrs: str) -> str:
            """
            Infer beginning cash balance date using duration calculation
            and closest match approach (validated 100% across test companies)
            """
            from datetime import datetime, timedelta

            # Calculate approximate beginning date
            end_date = datetime.strptime(ending_ddate, '%Y%m%d')
            months = int(qtrs) * 3
            days = months * 30.5  # Approximation (validated to be accurate enough)
            approx_beginning = end_date - timedelta(days=days)
            approx_str = approx_beginning.strftime('%Y%m%d')

            # Find closest actual instant date before ending date
            past_dates = [d for d in instant_dates_all if d < ending_ddate]
            if not past_dates:
                return ending_ddate  # Fallback (shouldn't happen in practice)

            # Find closest match to approximation
            closest = min(past_dates, key=lambda x: abs(int(x) - int(approx_str)))
            return closest

        def get_num_data_for_tag(tag: str, is_beginning_balance: bool = False) -> Optional[Dict]:
            """
            Find the NUM row for this tag in the primary financial statement

            Strategy:
            1. Filter to exact ddate and qtrs (determined from SUB metadata)
               SPECIAL: For mixed statements (like CF), check tag's iord field
                - If tag is Instant (I), use qtrs=0 even if stmt_type is CF
                - This handles beginning/ending cash balances in CF
            2. Filter to consolidated (segments=NaN)
            3. Filter to parent company (coreg=NaN)
            4. Prefer USD if multiple UOM

            Returns:
                Dict with value, ddate, qtrs, uom, segments, coreg
            """
            matches = num_df[num_df['tag'] == tag].copy()

            if len(matches) == 0:
                return None

            # Determine correct qtrs and ddate for this specific tag
            # Check if this tag is instant (balance) vs duration (flow)
            tag_info = tag_df[tag_df['tag'] == tag]
            tag_qtrs = target_qtrs
            tag_ddate = target_ddate

            if len(tag_info) > 0:
                iord = tag_info.iloc[0].get('iord')
                # If tag is Instant but we're in a duration statement (CF/IS),
                # use qtrs=0 for balance items
                if iord == 'I' and target_qtrs != '0':
                    tag_qtrs = '0'

                    # Special case: Beginning balance uses INFERRED prior date
                    if is_beginning_balance:
                        tag_ddate = infer_beginning_cash_date(target_ddate, target_qtrs)

            # 1. Filter to target date and period
            matches = matches[(matches['ddate'] == tag_ddate) &
                            (matches['qtrs'] == tag_qtrs)]

            if len(matches) == 0:
                return None

            # 2. Filter to consolidated (no segments)
            if 'segments' in matches.columns:
                no_segments = matches[matches['segments'].isna()]
                if len(no_segments) > 0:
                    matches = no_segments

            # 3. Filter to parent company (no coregistrant)
            if 'coreg' in matches.columns:
                no_coreg = matches[matches['coreg'].isna()]
                if len(no_coreg) > 0:
                    matches = no_coreg

            # 4. Prefer USD values
            if 'uom' in matches.columns and len(matches) > 1:
                usd_matches = matches[matches['uom'] == 'USD']
                if len(usd_matches) > 0:
                    matches = usd_matches

            if len(matches) == 0:
                return None

            # Take first match after filtering
            row = matches.iloc[0]
            return {
                'value': row['value'],
                'ddate': row['ddate'],
                'qtrs': row['qtrs'],
                'uom': row.get('uom'),
                'segments': row.get('segments'),
                'coreg': row.get('coreg')
            }

        def get_tag_metadata(tag: str) -> Dict:
            """
            Fetch metadata from TAG table

            Returns:
                Dict with custom, tlabel, datatype, iord, crdr
            """
            tag_row = tag_df[tag_df['tag'] == tag]
            if len(tag_row) == 0:
                return {
                    'custom': None,
                    'tlabel': None,
                    'datatype': None,
                    'iord': None,
                    'crdr': None
                }

            row = tag_row.iloc[0]
            return {
                'custom': row.get('custom'),
                'tlabel': row.get('tlabel'),
                'datatype': row.get('datatype'),
                'iord': row.get('iord'),
                'crdr': row.get('crdr')
            }

        def attach_recursive(node: StatementNode):
            """Recursively attach values and metadata to tree"""
            # Check if this is a beginning balance (for CF statements)
            is_beginning = False
            if node.plabel:
                plabel_lower = node.plabel.lower()
                # More flexible detection: just need 'beginning' keyword
                # Examples: "beginning balances", "beginning of period", "beginning of year"
                is_beginning = 'beginning' in plabel_lower

            # Get NUM data (value, ddate, qtrs, uom, segments, coreg)
            num_data = get_num_data_for_tag(node.tag, is_beginning_balance=is_beginning)
            if num_data:
                node.value = num_data['value']
                node.ddate = num_data['ddate']
                node.qtrs = num_data['qtrs']
                node.uom = num_data['uom']
                node.segments = num_data['segments']
                node.coreg = num_data['coreg']

            # Get TAG metadata (custom, tlabel, datatype, iord, crdr)
            tag_meta = get_tag_metadata(node.tag)
            node.custom = tag_meta['custom']
            node.tlabel = tag_meta['tlabel']
            node.datatype = tag_meta['datatype']
            node.iord = tag_meta['iord']
            node.crdr = tag_meta['crdr']

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

    def attach_values_for_period(self, hierarchy: StatementNode, num_df: pd.DataFrame,
                                 tag_df: pd.DataFrame, period: Dict, stmt_type: str) -> StatementNode:
        """
        Attach values for a SPECIFIC period to the hierarchy

        This is the multi-period version of attach_values. Instead of using SUB metadata
        to determine the period, it takes an explicit period dict from PeriodDiscovery.

        Args:
            hierarchy: Root node of statement tree
            num_df: NUM table filtered to specific filing
            tag_df: Full TAG table for looking up tag metadata
            period: Period dict from PeriodDiscovery:
                {
                    'ddate': '20240630',
                    'qtrs': '1',
                    'label': 'Three Months Ended Jun 30, 2024',
                    'type': 'duration' or 'instant'
                }
            stmt_type: Statement type ('BS', 'IS', 'CF', etc.)

        Returns:
            Hierarchy with values attached for this period (stored in values dict)
        """
        target_ddate = period['ddate']
        target_qtrs = period['qtrs']

        print(f"  Attaching values for period: {period['label']}")
        print(f"    ddate={target_ddate}, qtrs={target_qtrs}")

        # Convert value to float
        num_df = num_df.copy()
        num_df['value'] = pd.to_numeric(num_df['value'], errors='coerce')

        # Get all available instant dates for beginning cash inference
        instant_dates_all = num_df[(num_df['qtrs'] == '0') &
                                   (num_df['segments'].isna()) &
                                   (num_df['coreg'].isna())]['ddate'].unique()
        instant_dates_all = sorted(instant_dates_all)

        def infer_beginning_cash_date(ending_ddate: str, qtrs: str) -> str:
            """Infer beginning cash balance date"""
            from datetime import datetime, timedelta

            end_date = datetime.strptime(ending_ddate, '%Y%m%d')
            months = int(qtrs) * 3
            days = months * 30.5
            approx_beginning = end_date - timedelta(days=days)
            approx_str = approx_beginning.strftime('%Y%m%d')

            past_dates = [d for d in instant_dates_all if d < ending_ddate]
            if not past_dates:
                return ending_ddate

            closest = min(past_dates, key=lambda x: abs(int(x) - int(approx_str)))
            return closest

        def get_num_data_for_tag(tag: str, is_beginning_balance: bool = False) -> Optional[Dict]:
            """Find NUM row for this tag in this specific period"""
            matches = num_df[num_df['tag'] == tag].copy()

            if len(matches) == 0:
                return None

            # Determine correct qtrs and ddate for this specific tag
            tag_info = tag_df[tag_df['tag'] == tag]
            tag_qtrs = target_qtrs
            tag_ddate = target_ddate

            if len(tag_info) > 0:
                iord = tag_info.iloc[0].get('iord')
                # If tag is Instant but period is duration, use qtrs=0
                if iord == 'I' and target_qtrs != '0':
                    tag_qtrs = '0'

                    # Beginning balance uses inferred prior date
                    if is_beginning_balance:
                        tag_ddate = infer_beginning_cash_date(target_ddate, target_qtrs)

            # Filter to target date and period
            matches = matches[(matches['ddate'] == tag_ddate) &
                            (matches['qtrs'] == tag_qtrs)]

            if len(matches) == 0:
                return None

            # Filter to consolidated (no segments)
            if 'segments' in matches.columns:
                no_segments = matches[matches['segments'].isna()]
                if len(no_segments) > 0:
                    matches = no_segments

            # Filter to parent company (no coregistrant)
            if 'coreg' in matches.columns:
                no_coreg = matches[matches['coreg'].isna()]
                if len(no_coreg) > 0:
                    matches = no_coreg

            # Prefer USD values
            if 'uom' in matches.columns and len(matches) > 1:
                usd_matches = matches[matches['uom'] == 'USD']
                if len(usd_matches) > 0:
                    matches = usd_matches

            if len(matches) == 0:
                return None

            row = matches.iloc[0]
            return {
                'value': row['value'],
                'ddate': row['ddate'],
                'qtrs': row['qtrs'],
                'uom': row.get('uom')
            }

        def attach_recursive(node: StatementNode):
            """Recursively attach values for this period"""
            # Check if this is a beginning balance
            is_beginning = False
            if node.plabel:
                plabel_lower = node.plabel.lower()
                # More flexible detection: just need 'beginning' keyword
                # Examples: "beginning balances", "beginning of period", "beginning of year"
                is_beginning = 'beginning' in plabel_lower

            # Get NUM data for this period
            num_data = get_num_data_for_tag(node.tag, is_beginning_balance=is_beginning)
            if num_data:
                # Store in multi-period values dict
                period_key = (num_data['ddate'], num_data['qtrs'])
                node.values[period_key] = num_data['value']

                # Also update single-value fields for backward compatibility
                # (last period processed will win)
                node.value = num_data['value']
                node.ddate = num_data['ddate']
                node.qtrs = num_data['qtrs']
                node.uom = num_data.get('uom')

            # Recursively process children
            for child in node.children:
                attach_recursive(child)

        attach_recursive(hierarchy)

        # Count values found for this period
        def count_period_values(node: StatementNode, period_key: Tuple[str, str]) -> int:
            count = 1 if period_key in node.values else 0
            for child in node.children:
                count += count_period_values(child, period_key)
            return count

        # Note: period_key might be different from target if it's a beginning balance
        # So we count all new values in the values dict
        value_count = len([1 for node in self._get_all_nodes(hierarchy)
                          if len(node.values) > 0])

        print(f"    Attached values for {value_count} line items")

        return hierarchy

    def _get_all_nodes(self, root: StatementNode) -> List[StatementNode]:
        """Helper: Get all nodes in hierarchy as flat list"""
        nodes = []

        def collect(node):
            nodes.append(node)
            for child in node.children:
                collect(child)

        collect(root)
        return nodes

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

    def _mark_sum_items(self, hierarchy: StatementNode, calc_graph: Dict) -> int:
        """
        Mark nodes that appear as parents in the calc graph as sum items.

        This uses the XBRL calculation linkbase to identify which tags are
        sum/total items (i.e., they have defined calculation children).

        Args:
            hierarchy: Root node of statement tree
            calc_graph: Dict {parent_tag: [(child_tag, weight), ...], ...}
                       Tags may be prefixed (e.g., 'us-gaap_Assets') or not ('Assets')

        Returns:
            int: Number of nodes marked as sum items
        """
        # Build set of sum tags (both with and without prefix for flexible matching)
        sum_tags = set(calc_graph.keys())

        # Also add versions without prefix for matching
        sum_tags_no_prefix = set()
        for tag in calc_graph.keys():
            if '_' in tag:
                # us-gaap_Assets -> Assets
                sum_tags_no_prefix.add(tag.split('_', 1)[1])
            else:
                sum_tags_no_prefix.add(tag)

        marked_count = 0

        def mark_recursive(node: StatementNode):
            nonlocal marked_count

            # Try exact match first
            tag = node.tag
            matched_tag = None

            if tag in sum_tags:
                matched_tag = tag
            elif tag in sum_tags_no_prefix:
                # Find the full prefixed tag
                for full_tag in calc_graph.keys():
                    if full_tag.endswith('_' + tag) or full_tag == tag:
                        matched_tag = full_tag
                        break

            if matched_tag:
                node.is_sum = True
                node.calc_children = list(calc_graph[matched_tag])
                marked_count += 1

            for child in node.children:
                mark_recursive(child)

        mark_recursive(hierarchy)
        return marked_count

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

        # Step 3: Attach values and metadata
        hierarchy = self.attach_values(hierarchy, filing_data['num'],
                                       filing_data['tag'], filing_data['sub'], stmt_type)

        # Step 4: Validate
        validation = self.validate_rollups(hierarchy)

        # Step 5: Load calc graph and mark sum items
        calc_graph = {}
        calc_source = None
        try:
            from xbrl_loader import load_calc_graph_with_fallback
            calc_graph, calc_source = load_calc_graph_with_fallback(cik, adsh)
            marked_count = self._mark_sum_items(hierarchy, calc_graph)
            print(f"  Calc graph loaded ({calc_source}): {len(calc_graph)} parent tags, {marked_count} nodes marked as sum items")
        except Exception as e:
            print(f"  Warning: Could not load calc graph: {e}")

        # Step 6: Create flat list with full metadata for each line item
        line_items = []

        def flatten_recursive(node: StatementNode):
            """Extract all line items with full metadata"""
            # Skip virtual root nodes
            if node.tag.endswith('_ROOT'):
                for child in node.children:
                    flatten_recursive(child)
                return

            # Only include nodes with values
            if node.value is not None:
                line_items.append({
                    # Core identification
                    'tag': node.tag,
                    'plabel': node.plabel,

                    # PRE table fields
                    'stmt': node.stmt,
                    'report': node.report,
                    'line': node.line,
                    'stmt_order': node.line,  # For section classification
                    'inpth': node.level,
                    'negating': node.negating,

                    # NUM table fields
                    'value': node.value,
                    'ddate': node.ddate,
                    'qtrs': node.qtrs,
                    'uom': node.uom,
                    'segments': node.segments,
                    'coreg': node.coreg,

                    # TAG table fields
                    'custom': node.custom,
                    'tlabel': node.tlabel,
                    'datatype': node.datatype,
                    'iord': node.iord,
                    'crdr': node.crdr,

                    # Calc graph fields (from XBRL calculation linkbase)
                    'is_sum': node.is_sum,
                    'calc_children': node.calc_children if node.is_sum else []
                })

            for child in node.children:
                flatten_recursive(child)

        flatten_recursive(hierarchy)

        # Sort by line number to maintain presentation order
        line_items.sort(key=lambda x: x['line'] if x['line'] is not None else 0)

        # Also create simple tag->value dict for backward compatibility
        flat_data = {item['tag']: item['value'] for item in line_items}

        # Generate EDGAR viewer URL
        cik_padded = str(cik).zfill(10)
        edgar_url = f"https://www.sec.gov/cgi-bin/viewer?action=view&cik={cik_padded}&accession_number={adsh}&xbrl_type=v"

        print(f"\nReconstruction complete!")
        print(f"  Total line items: {len(line_items)}")
        print(f"  EDGAR viewer: {edgar_url}")

        return {
            'hierarchy': hierarchy,
            'validation': validation,
            'line_items': line_items,       # NEW: List of dicts with full metadata
            'flat_data': flat_data,         # KEPT: Simple tag->value dict for backward compatibility
            'metadata': {
                'cik': cik,
                'adsh': adsh,
                'stmt_type': stmt_type,
                'year': self.year,
                'quarter': self.quarter,
                'edgar_url': edgar_url
            }
        }

    def reconstruct_statement_multi_period(self, cik: int, adsh: str, stmt_type: str = 'BS') -> Dict:
        """
        Multi-period version: Reconstruct financial statement with ALL comparative periods

        This discovers and extracts all periods present in the filing (e.g., current quarter,
        prior quarter, YTD current, YTD prior, etc.) using the period discovery approach
        validated in the investigation.

        Pipeline:
        1. Load filing data (PRE/NUM/TAG/SUB tables)
        2. Build hierarchy from PRE table (structure - same for all periods)
        3. Discover all periods using representative tag approach
        4. For each period, attach values to hierarchy
        5. Flatten to line_items with multi-period values

        Args:
            cik: Company CIK (e.g., 1018724 for Amazon)
            adsh: Accession number (e.g., '0001018724-24-000130')
            stmt_type: Statement type ('BS', 'IS', 'CF', 'EQ')

        Returns:
            Dict with:
                - 'hierarchy': Root StatementNode (with multi-period values)
                - 'periods': List of period dicts
                - 'line_items': List of dicts with multi-period values
                - 'metadata': Filing metadata
        """
        print(f"\n{'='*60}")
        print(f"Reconstructing {stmt_type} statement (MULTI-PERIOD)")
        print(f"CIK: {cik}, ADSH: {adsh}")
        print(f"{'='*60}")

        # Step 1: Load filing data
        filing_data = self.load_filing_data(adsh)

        # Step 2: Build hierarchy (structure - same for all periods)
        hierarchy = self.build_hierarchy(filing_data['pre'], stmt_type)

        if hierarchy is None:
            return {
                'error': f"No {stmt_type} statement found",
                'hierarchy': None,
                'periods': [],
                'line_items': [],
                'metadata': {'cik': cik, 'adsh': adsh, 'stmt_type': stmt_type}
            }

        # Step 3: Discover periods using representative tag approach
        from period_discovery import PeriodDiscovery

        discoverer = PeriodDiscovery()
        periods = discoverer.discover_periods(
            filing_data['pre'],
            filing_data['num'],
            filing_data['tag'],
            stmt_type
        )

        print(f"\nDiscovered {len(periods)} periods:")
        for p in periods:
            print(f"  - {p['label']} (ddate={p['ddate']}, qtrs={p['qtrs']})")

        # Step 4: Attach metadata from TAG table (do once)
        # This sets iord, crdr, etc. which don't change across periods
        def attach_tag_metadata(node: StatementNode):
            """Attach TAG metadata to node"""
            tag_row = filing_data['tag'][filing_data['tag']['tag'] == node.tag]
            if len(tag_row) > 0:
                row = tag_row.iloc[0]
                node.custom = row.get('custom')
                node.tlabel = row.get('tlabel')
                node.datatype = row.get('datatype')
                node.iord = row.get('iord')
                node.crdr = row.get('crdr')

            for child in node.children:
                attach_tag_metadata(child)

        attach_tag_metadata(hierarchy)

        # Step 5: For each period, attach values
        for period in periods:
            self.attach_values_for_period(
                hierarchy,
                filing_data['num'],
                filing_data['tag'],
                period,
                stmt_type
            )

        # Step 5b: Load calc graph and mark sum items
        calc_graph = {}
        calc_source = None
        try:
            from xbrl_loader import load_calc_graph_with_fallback
            calc_graph, calc_source = load_calc_graph_with_fallback(cik, adsh)
            marked_count = self._mark_sum_items(hierarchy, calc_graph)
            print(f"  Calc graph loaded ({calc_source}): {len(calc_graph)} parent tags, {marked_count} nodes marked as sum items")
        except Exception as e:
            print(f"  Warning: Could not load calc graph: {e}")

        # Step 6: Create line_items with multi-period values
        line_items = []

        # Get available instant dates for beginning balance matching
        available_instant_dates = filing_data['num'][
            (filing_data['num']['qtrs'] == '0') &
            (filing_data['num']['segments'].isna()) &
            (filing_data['num']['coreg'].isna())
        ]['ddate'].unique().tolist()
        available_instant_dates = sorted(available_instant_dates)

        def flatten_multi_period(node: StatementNode):
            """Extract line items with multi-period values"""
            # Skip virtual root nodes
            if node.tag.endswith('_ROOT'):
                for child in node.children:
                    flatten_multi_period(child)
                return

            # Include nodes that have values in ANY period
            if len(node.values) > 0:
                # Check if this node is a beginning balance (do once per node)
                is_beginning_node = False
                if node.plabel:
                    plabel_lower = node.plabel.lower()
                    # More flexible detection: just need 'beginning' keyword
                    # Examples: "beginning balances", "beginning of period", "beginning of year"
                    is_beginning_node = 'beginning' in plabel_lower

                # Build values dict for this line item
                period_values = {}
                for period in periods:
                    period_ddate = period['ddate']
                    period_qtrs = period['qtrs']

                    # Find value for this period
                    # For most items: direct match on (ddate, qtrs)
                    # For instant items (qtrs=0) in duration statements: match to period by ddate
                    value = None

                    # First, try direct match
                    if (period_ddate, period_qtrs) in node.values:
                        value = node.values[(period_ddate, period_qtrs)]

                    # For BEGINNING balance nodes, skip instant match and go straight to
                    # expected beginning date calculation (because stored dates are inferred, not period dates)
                    elif is_beginning_node and node.iord == 'I' and period_qtrs != '0':
                        # Calculate expected beginning date for this period
                        expected_beginning_date = discoverer.infer_beginning_ddate(
                            period_ddate,
                            period_qtrs,
                            available_instant_dates
                        )

                        # Look for exact match first
                        if (expected_beginning_date, '0') in node.values:
                            value = node.values[(expected_beginning_date, '0')]
                        else:
                            # If no exact match, find closest instant date
                            best_match = None
                            min_diff_days = float('inf')

                            for (stored_ddate, stored_qtrs), stored_value in node.values.items():
                                if stored_qtrs == '0':
                                    # Calculate actual day difference
                                    from datetime import datetime
                                    try:
                                        expected_dt = datetime.strptime(expected_beginning_date, '%Y%m%d')
                                        stored_dt = datetime.strptime(stored_ddate, '%Y%m%d')
                                        diff_days = abs((stored_dt - expected_dt).days)

                                        # Accept if within 5 days of expected
                                        if diff_days < min_diff_days and diff_days <= 5:
                                            min_diff_days = diff_days
                                            best_match = stored_value
                                    except:
                                        pass

                            if best_match is not None:
                                value = best_match

                    else:
                        # For ENDING balance, other instant items, and all duration items
                        # Look for instant values (qtrs='0') matching this period's ddate
                        for (stored_ddate, stored_qtrs), stored_value in node.values.items():
                            if stored_qtrs == '0' and stored_ddate == period_ddate:
                                value = stored_value
                                break

                        # For instant items that are NOT beginning balances
                        # (fallback for edge cases)
                        if value is None and node.iord == 'I' and period_qtrs != '0' and not is_beginning_node:
                            # This is an instant item in a duration period (likely beginning balance)
                            # Calculate expected beginning date using same logic as attach_values_for_period
                            expected_beginning_date = discoverer.infer_beginning_ddate(
                                period_ddate,
                                period_qtrs,
                                available_instant_dates
                            )

                            # Look for exact match first
                            if (expected_beginning_date, '0') in node.values:
                                value = node.values[(expected_beginning_date, '0')]
                            else:
                                # If no exact match, find closest instant date
                                # (in case rounding caused slight difference)
                                best_match = None
                                min_diff_days = float('inf')

                                for (stored_ddate, stored_qtrs), stored_value in node.values.items():
                                    if stored_qtrs == '0':
                                        # Calculate actual day difference
                                        from datetime import datetime
                                        try:
                                            expected_dt = datetime.strptime(expected_beginning_date, '%Y%m%d')
                                            stored_dt = datetime.strptime(stored_ddate, '%Y%m%d')
                                            diff_days = abs((stored_dt - expected_dt).days)

                                            # Accept if within 5 days of expected
                                            if diff_days < min_diff_days and diff_days <= 5:
                                                min_diff_days = diff_days
                                                best_match = stored_value
                                        except:
                                            pass

                                if best_match is not None:
                                    value = best_match

                    if value is not None:
                        period_values[period['label']] = value

                line_items.append({
                    # Core identification
                    'tag': node.tag,
                    'plabel': node.plabel,

                    # PRE table fields
                    'stmt': node.stmt,
                    'report': node.report,
                    'line': node.line,
                    'stmt_order': node.line,  # For section classification
                    'inpth': node.level,
                    'negating': node.negating,

                    # Multi-period values
                    'values': period_values,  # Dict: {period_label: value}

                    # Backward compatibility - last period
                    'value': node.value,
                    'ddate': node.ddate,
                    'qtrs': node.qtrs,
                    'uom': node.uom,
                    'segments': node.segments,
                    'coreg': node.coreg,

                    # TAG table fields
                    'custom': node.custom,
                    'tlabel': node.tlabel,
                    'datatype': node.datatype,
                    'iord': node.iord,
                    'crdr': node.crdr,

                    # Calc graph fields (from XBRL calculation linkbase)
                    'is_sum': node.is_sum,
                    'calc_children': node.calc_children if node.is_sum else []
                })

            for child in node.children:
                flatten_multi_period(child)

        flatten_multi_period(hierarchy)

        # Sort by line number to maintain presentation order
        line_items.sort(key=lambda x: x['line'] if x['line'] is not None else 0)

        # Generate EDGAR viewer URL
        cik_padded = str(cik).zfill(10)
        edgar_url = f"https://www.sec.gov/cgi-bin/viewer?action=view&cik={cik_padded}&accession_number={adsh}&xbrl_type=v"

        print(f"\nMulti-period reconstruction complete!")
        print(f"  Total line items: {len(line_items)}")
        print(f"  Periods: {len(periods)}")
        print(f"  EDGAR viewer: {edgar_url}")

        return {
            'hierarchy': hierarchy,
            'periods': periods,             # List of period metadata dicts
            'line_items': line_items,       # List with multi-period values
            'metadata': {
                'cik': cik,
                'adsh': adsh,
                'stmt_type': stmt_type,
                'year': self.year,
                'quarter': self.quarter,
                'edgar_url': edgar_url,
                'num_periods': len(periods)
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
    sub_path = config.storage.extracted_dir / f'{year}q{quarter}' / 'sub.txt'

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
