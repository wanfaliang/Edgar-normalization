"""
Period Discovery Module

Discovers all periods (comparative columns) present in a filing's financial statements.
Uses representative tag approach validated across multiple companies.

Based on INVESTIGATION_FINDINGS.md (2025-11-13)
"""

from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import pandas as pd


class PeriodDiscovery:
    """Discover all periods present in a filing's financial statements"""

    # Representative tags that appear in all displayed periods
    # Try in order - use first one found
    REPRESENTATIVE_TAGS = {
        'BS': [
            'Assets',
            'AssetsCurrent',
            'LiabilitiesAndStockholdersEquity'
        ],
        'IS': [
            'Revenues',
            'RevenueFromContractWithCustomerExcludingAssessedTax',
            'SalesRevenueNet',
            'NetIncomeLoss'
        ],
        'CF': [
            'NetCashProvidedByUsedInOperatingActivities',
            'NetCashProvidedByUsedInInvestingActivities',
            'NetCashProvidedByUsedInFinancingActivities'
        ]
    }

    def __init__(self):
        pass

    def discover_periods(self, pre_df: pd.DataFrame, num_df: pd.DataFrame,
                        tag_df: pd.DataFrame, stmt_type: str) -> List[Dict]:
        """
        Find all unique periods for a statement type

        Args:
            pre_df: PRE table (presentation) - filtered to this filing
            num_df: NUM table (values) - filtered to this filing
            tag_df: TAG table (tag definitions) - full table
            stmt_type: 'BS', 'IS', or 'CF'

        Returns:
            List of period dicts:
            [
                {
                    'ddate': '20240630',
                    'qtrs': '1',
                    'label': 'Three Months Ended Jun 30, 2024',
                    'type': 'duration'  # or 'instant'
                },
                ...
            ]
        """
        # Find a representative tag for this statement type
        rep_tag = self._find_representative_tag(pre_df, num_df, stmt_type)

        if not rep_tag:
            # Fallback: use all tags from statement
            print(f"Warning: No representative tag found for {stmt_type}, using all tags")
            return self._discover_from_all_tags(pre_df, num_df, stmt_type)

        # Get all values for representative tag (consolidated only)
        tag_values = num_df[num_df['tag'] == rep_tag].copy()
        tag_values = tag_values[tag_values['segments'].isna() & tag_values['coreg'].isna()]

        # Discover periods based on statement type
        if stmt_type == 'BS':
            return self._discover_bs_periods(tag_values, rep_tag)
        elif stmt_type in ['IS', 'CF']:
            return self._discover_duration_periods(tag_values, rep_tag, stmt_type)
        else:
            raise ValueError(f"Unknown statement type: {stmt_type}")

    def _find_representative_tag(self, pre_df: pd.DataFrame, num_df: pd.DataFrame,
                                 stmt_type: str) -> str:
        """
        Find a representative tag that exists in both PRE and NUM

        Returns:
            Tag name, or None if not found
        """
        candidates = self.REPRESENTATIVE_TAGS.get(stmt_type, [])

        # Get tags that appear in this statement's PRE
        stmt_tags = set(pre_df[pre_df['stmt'] == stmt_type]['tag'].unique())

        # Try each candidate in order
        for tag in candidates:
            if tag in stmt_tags:
                # Check if it has values in NUM
                tag_values = num_df[num_df['tag'] == tag]
                tag_values = tag_values[tag_values['segments'].isna() & tag_values['coreg'].isna()]

                if len(tag_values) > 0:
                    return tag

        return None

    def _discover_bs_periods(self, tag_values: pd.DataFrame, tag_name: str) -> List[Dict]:
        """
        Discover Balance Sheet periods (instant dates)

        BS periods are defined by unique ddate values (qtrs should be 0)
        """
        periods = []

        # Get unique instant dates (qtrs=0)
        instant_values = tag_values[tag_values['qtrs'] == '0']
        unique_dates = sorted(instant_values['ddate'].unique(), reverse=True)

        for ddate in unique_dates:
            periods.append({
                'ddate': ddate,
                'qtrs': '0',
                'label': self._format_instant_label(ddate),
                'type': 'instant',
                'rep_tag': tag_name
            })

        return periods

    def _discover_duration_periods(self, tag_values: pd.DataFrame, tag_name: str,
                                   stmt_type: str) -> List[Dict]:
        """
        Discover Income Statement or Cash Flow periods (duration)

        IS/CF periods are defined by unique (ddate, qtrs) combinations
        """
        periods = []

        # Get duration values (qtrs != 0)
        duration_values = tag_values[tag_values['qtrs'] != '0']

        # Get unique (ddate, qtrs) combinations
        unique_periods = duration_values[['ddate', 'qtrs']].drop_duplicates()

        # Sort by date (descending) then qtrs (descending for same date)
        unique_periods = unique_periods.sort_values(['ddate', 'qtrs'], ascending=[False, False])

        for _, row in unique_periods.iterrows():
            ddate = row['ddate']
            qtrs = row['qtrs']

            periods.append({
                'ddate': ddate,
                'qtrs': qtrs,
                'label': self._format_duration_label(ddate, qtrs),
                'type': 'duration',
                'rep_tag': tag_name
            })

        return periods

    def _discover_from_all_tags(self, pre_df: pd.DataFrame, num_df: pd.DataFrame,
                                stmt_type: str) -> List[Dict]:
        """
        Fallback: discover periods using all tags from statement

        This is less efficient but more robust if no representative tag found
        """
        # Get all tags for this statement
        stmt_tags = pre_df[pre_df['stmt'] == stmt_type]['tag'].unique()

        # Get all values for these tags (consolidated only)
        stmt_values = num_df[num_df['tag'].isin(stmt_tags)]
        stmt_values = stmt_values[stmt_values['segments'].isna() & stmt_values['coreg'].isna()]

        # Discover based on type
        if stmt_type == 'BS':
            instant_values = stmt_values[stmt_values['qtrs'] == '0']
            unique_dates = sorted(instant_values['ddate'].unique(), reverse=True)

            return [{
                'ddate': ddate,
                'qtrs': '0',
                'label': self._format_instant_label(ddate),
                'type': 'instant',
                'rep_tag': 'all_tags'
            } for ddate in unique_dates]
        else:
            duration_values = stmt_values[stmt_values['qtrs'] != '0']
            unique_periods = duration_values[['ddate', 'qtrs']].drop_duplicates()
            unique_periods = unique_periods.sort_values(['ddate', 'qtrs'], ascending=[False, False])

            periods = []
            for _, row in unique_periods.iterrows():
                periods.append({
                    'ddate': row['ddate'],
                    'qtrs': row['qtrs'],
                    'label': self._format_duration_label(row['ddate'], row['qtrs']),
                    'type': 'duration',
                    'rep_tag': 'all_tags'
                })

            return periods

    def _format_instant_label(self, ddate: str) -> str:
        """
        Format instant date label

        Example: '20240630' → 'As of Jun 30, 2024'
        """
        try:
            date_obj = datetime.strptime(ddate, '%Y%m%d')
            return f"As of {date_obj.strftime('%b %d, %Y')}"
        except:
            return f"As of {ddate}"

    def _format_duration_label(self, ddate: str, qtrs: str) -> str:
        """
        Format duration period label

        Examples:
        - ('20240630', '1') → 'Three Months Ended Jun 30, 2024'
        - ('20240630', '2') → 'Six Months Ended Jun 30, 2024'
        - ('20240630', '4') → 'Year Ended Jun 30, 2024'
        """
        try:
            date_obj = datetime.strptime(ddate, '%Y%m%d')
            date_str = date_obj.strftime('%b %d, %Y')

            qtrs_int = int(qtrs)
            if qtrs_int == 1:
                period_desc = "Three Months Ended"
            elif qtrs_int == 2:
                period_desc = "Six Months Ended"
            elif qtrs_int == 3:
                period_desc = "Nine Months Ended"
            elif qtrs_int == 4:
                period_desc = "Year Ended"
            else:
                period_desc = f"{qtrs_int * 3} Months Ended"

            return f"{period_desc} {date_str}"
        except:
            return f"{qtrs} qtrs ended {ddate}"

    def infer_beginning_ddate(self, ending_ddate: str, qtrs: str,
                              available_instant_dates: List[str]) -> str:
        """
        Infer beginning cash balance date using duration calculation
        and closest match approach

        Validated 100% accuracy across test companies (Amazon, Home Depot, P&G)

        Args:
            ending_ddate: Period end date (e.g., '20240630')
            qtrs: Duration in quarters ('1', '2', '3', '4')
            available_instant_dates: List of available instant dates from NUM table

        Returns:
            Closest matching instant date representing beginning of period

        Example:
            ending_ddate='20240630', qtrs='2'
            → Calculates ~'20231231'
            → Finds closest in ['20231231', '20240331', '20240630']
            → Returns '20231231'
        """
        # Calculate approximate beginning date
        end_date = datetime.strptime(ending_ddate, '%Y%m%d')
        months = int(qtrs) * 3
        days = months * 30.5  # Approximation (validated to work well)

        approx_beginning = end_date - timedelta(days=days)
        approx_str = approx_beginning.strftime('%Y%m%d')

        # Find closest actual instant date before ending date
        past_dates = [d for d in available_instant_dates if d < ending_ddate]

        if not past_dates:
            # Fallback: use ending date (shouldn't happen in practice)
            return ending_ddate

        # Find closest match to approximation
        closest = min(past_dates, key=lambda x: abs(int(x) - int(approx_str)))

        return closest
