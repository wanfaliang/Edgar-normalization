"""
Excel Exporter for Financial Statements
========================================
Exports reconstructed financial statements to formatted Excel files

Features:
- Formatted statement sheets (BS, IS, CF) with indentation and styling
- Metadata sheet with all fields for analysis
- Human-readable presentation matching EDGAR display

Author: Generated with Claude Code
Date: 2025-11-12
"""

import xlsxwriter
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd


class ExcelExporter:
    """
    Export reconstructed financial statements to Excel format

    Usage:
        exporter = ExcelExporter()
        exporter.add_statement('BS', bs_result)
        exporter.add_statement('IS', is_result)
        exporter.add_statement('CF', cf_result)
        exporter.export('output.xlsx', company_name='Amazon', period='Q2 2024')
    """

    def __init__(self):
        """Initialize exporter"""
        self.statements = {}  # stmt_type -> reconstruction result

    def add_statement(self, stmt_type: str, result: Dict):
        """
        Add a statement reconstruction result

        Args:
            stmt_type: Statement type ('BS', 'IS', 'CF')
            result: Result dict from StatementReconstructor.reconstruct_statement()
        """
        if 'line_items' not in result:
            raise ValueError(f"Result missing 'line_items' - is this from updated reconstructor?")

        self.statements[stmt_type] = result

    def export(self, filepath: str, company_name: str = None, period: str = None):
        """
        Export all statements to Excel file

        Args:
            filepath: Output Excel file path
            company_name: Company name for title (optional)
            period: Period description for title (optional, e.g., "Q2 2024")
        """
        print(f"\nExporting financial statements to Excel...")
        print(f"  Output: {filepath}")

        # Create workbook with nan_inf_to_errors option
        workbook = xlsxwriter.Workbook(filepath, {'nan_inf_to_errors': True})

        # Define formats
        formats = self._create_formats(workbook)

        # Export each statement type
        if 'BS' in self.statements:
            self._export_formatted_statement(
                workbook, 'Balance Sheet', self.statements['BS'],
                company_name, period, formats
            )

        if 'IS' in self.statements:
            self._export_formatted_statement(
                workbook, 'Income Statement', self.statements['IS'],
                company_name, period, formats
            )

        if 'CF' in self.statements:
            self._export_formatted_statement(
                workbook, 'Cash Flow', self.statements['CF'],
                company_name, period, formats
            )

        if 'CI' in self.statements:
            self._export_formatted_statement(
                workbook, 'Comprehensive Income', self.statements['CI'],
                company_name, period, formats
            )

        if 'EQ' in self.statements:
            self._export_formatted_statement(
                workbook, 'Stockholders Equity', self.statements['EQ'],
                company_name, period, formats
            )

        # Export metadata sheet with all details
        self._export_metadata_sheet(workbook, formats)

        # Close workbook
        workbook.close()

        print(f"✅ Export complete!")
        print(f"  Sheets created: {len(self.statements)} formatted + 1 metadata")

    def _create_formats(self, workbook):
        """Create cell formats for styling"""
        return {
            'title': workbook.add_format({
                'bold': True,
                'font_size': 14,
                'align': 'center'
            }),
            'header': workbook.add_format({
                'bold': True,
                'bg_color': '#D3D3D3',
                'border': 1
            }),
            'total': workbook.add_format({
                'bold': True,
                'num_format': '#,##0'
            }),
            'number': workbook.add_format({
                'num_format': '#,##0'
            }),
            'negative': workbook.add_format({
                'num_format': '#,##0',
                'font_color': 'red'
            }),
            'indent_1': workbook.add_format({
                'indent': 1,
                'num_format': '#,##0'
            }),
            'indent_2': workbook.add_format({
                'indent': 2,
                'num_format': '#,##0'
            }),
            'indent_3': workbook.add_format({
                'indent': 3,
                'num_format': '#,##0'
            }),
            'text': workbook.add_format({}),
            'metadata_header': workbook.add_format({
                'bold': True,
                'bg_color': '#4472C4',
                'font_color': 'white',
                'border': 1
            })
        }

    def _export_formatted_statement(self, workbook, sheet_name: str, result: Dict,
                                    company_name: str, period: str, formats: Dict):
        """
        Export a single statement as formatted sheet

        Supports both single-period and multi-period results.
        For multi-period, creates columns for each period.

        Args:
            workbook: xlsxwriter Workbook
            sheet_name: Name for worksheet
            result: Reconstruction result
            company_name: Company name
            period: Period description
            formats: Format dict
        """
        worksheet = workbook.add_worksheet(sheet_name)

        # Check if this is multi-period result
        is_multi_period = 'periods' in result and len(result.get('periods', [])) > 0

        if is_multi_period:
            # Multi-period layout
            periods = result['periods']
            num_periods = len(periods)

            # Set column widths
            worksheet.set_column('A:A', 50)  # Label column
            for i in range(num_periods):
                worksheet.set_column(i + 1, i + 1, 18)  # Period columns

            row = 0

            # Title
            if company_name:
                title = f"{company_name} - {sheet_name}"
                worksheet.write(row, 0, title, formats['title'])
                row += 2
            else:
                worksheet.write(row, 0, sheet_name, formats['title'])
                row += 2

            # Column headers
            worksheet.write(row, 0, 'Line Item', formats['header'])
            for col_idx, period_info in enumerate(periods):
                # Use short version of label for column header
                header = period_info['label']
                # Shorten if too long
                if len(header) > 30:
                    # Extract key parts: "Three Months Ended Jun 30, 2024" -> "Q2 2024"
                    if 'Three Months' in header:
                        parts = header.split()
                        date_part = parts[-3] + ' ' + parts[-1]  # "Jun 2024"
                        header = f"Q {date_part}"
                    elif 'Six Months' in header:
                        parts = header.split()
                        date_part = parts[-3] + ' ' + parts[-1]
                        header = f"6M {date_part}"
                    elif 'Year Ended' in header or 'Twelve Months' in header:
                        parts = header.split()
                        date_part = parts[-3] + ' ' + parts[-1]
                        header = f"FY {date_part}"

                worksheet.write(row, col_idx + 1, header, formats['header'])
            row += 1

            # Line items
            line_items = result['line_items']

            for item in line_items:
                label = item['plabel']
                level = item.get('inpth', 0)
                values_dict = item.get('values', {})  # {period_label: value}

                # Add indentation to label
                indented_label = ('  ' * level) + label
                worksheet.write(row, 0, indented_label, formats['text'])

                # Write value for each period
                for col_idx, period_info in enumerate(periods):
                    period_label = period_info['label']
                    value = values_dict.get(period_label)

                    # Determine format
                    if level == 0 or 'total' in label.lower() or 'Total' in label:
                        if value and value < 0:
                            value_format = formats['negative']
                        else:
                            value_format = formats['total']
                    else:
                        if level >= 3:
                            value_format = formats['indent_3']
                        elif level == 2:
                            value_format = formats['indent_2']
                        elif level == 1:
                            value_format = formats['indent_1']
                        else:
                            value_format = formats['number']

                        if value and value < 0:
                            value_format = formats['negative']

                    # Write value
                    if value is None or pd.isna(value):
                        worksheet.write(row, col_idx + 1, '', value_format)
                    else:
                        worksheet.write(row, col_idx + 1, value, value_format)

                row += 1

            # Add metadata footer
            row += 1
            worksheet.write(row, 0, f"Periods: {len(periods)}", formats['text'])
            row += 1
            worksheet.write(row, 0, f"EDGAR URL: {result['metadata'].get('edgar_url', 'N/A')}", formats['text'])

        else:
            # Single-period layout (backward compatibility)
            # Set column widths
            worksheet.set_column('A:A', 50)  # Label column
            worksheet.set_column('B:B', 20)  # Value column

            row = 0

            # Title
            if company_name and period:
                title = f"{company_name} - {sheet_name}"
                worksheet.write(row, 0, title, formats['title'])
                row += 1
                worksheet.write(row, 0, f"Period: {period}", formats['text'])
                row += 2
            elif company_name:
                worksheet.write(row, 0, f"{company_name} - {sheet_name}", formats['title'])
                row += 2
            else:
                worksheet.write(row, 0, sheet_name, formats['title'])
                row += 2

            # Column headers
            worksheet.write(row, 0, 'Line Item', formats['header'])
            worksheet.write(row, 1, 'Value', formats['header'])
            row += 1

            # Line items
            line_items = result['line_items']

            for item in line_items:
                label = item['plabel']
                value = item['value']
                level = item.get('inpth', 0)

                # Determine format based on level and value
                if level == 0 or 'total' in label.lower() or 'Total' in label:
                    # Top-level items or totals - bold
                    label_format = formats['text']
                    if value < 0:
                        value_format = formats['negative']
                    else:
                        value_format = formats['total']
                else:
                    # Indented items
                    label_format = formats['text']
                    if level >= 3:
                        value_format = formats['indent_3']
                    elif level == 2:
                        value_format = formats['indent_2']
                    elif level == 1:
                        value_format = formats['indent_1']
                    else:
                        value_format = formats['number']

                    if value < 0:
                        value_format = formats['negative']

                # Add indentation to label
                indented_label = ('  ' * level) + label

                worksheet.write(row, 0, indented_label, label_format)

                # Check for NaN before writing
                if pd.isna(value):
                    worksheet.write(row, 1, '', value_format)
                else:
                    worksheet.write(row, 1, value, value_format)
                row += 1

            # Add metadata footer
            row += 1
            worksheet.write(row, 0, f"Date: {line_items[0].get('ddate', 'N/A')}", formats['text'])
            row += 1
            worksheet.write(row, 0, f"EDGAR URL: {result['metadata'].get('edgar_url', 'N/A')}", formats['text'])

    def _export_metadata_sheet(self, workbook, formats: Dict):
        """
        Export metadata sheet with all fields in table format

        Args:
            workbook: xlsxwriter Workbook
            formats: Format dict
        """
        worksheet = workbook.add_worksheet('Metadata')

        # Collect all line items from all statements
        all_items = []
        for stmt_type, result in self.statements.items():
            for item in result['line_items']:
                # Add statement type to each item
                item_copy = item.copy()
                all_items.append(item_copy)

        if not all_items:
            return

        # Define columns to export
        columns = [
            'stmt', 'line', 'inpth', 'plabel', 'value', 'tag',
            'ddate', 'qtrs', 'uom', 'report', 'negating',
            'custom', 'tlabel', 'datatype', 'iord', 'crdr',
            'segments', 'coreg'
        ]

        # Column widths
        col_widths = {
            'stmt': 8,
            'line': 6,
            'inpth': 6,
            'plabel': 40,
            'value': 15,
            'tag': 50,
            'ddate': 10,
            'qtrs': 6,
            'uom': 8,
            'report': 8,
            'negating': 10,
            'custom': 8,
            'tlabel': 50,
            'datatype': 12,
            'iord': 6,
            'crdr': 6,
            'segments': 10,
            'coreg': 10
        }

        # Set column widths
        for col_idx, col_name in enumerate(columns):
            worksheet.set_column(col_idx, col_idx, col_widths.get(col_name, 15))

        # Header row
        row = 0
        for col_idx, col_name in enumerate(columns):
            worksheet.write(row, col_idx, col_name.upper(), formats['metadata_header'])
        row += 1

        # Data rows
        for item in all_items:
            for col_idx, col_name in enumerate(columns):
                value = item.get(col_name)

                # Format value
                if col_name == 'value' and value is not None:
                    worksheet.write(row, col_idx, value, formats['number'])
                elif col_name == 'negating':
                    worksheet.write(row, col_idx, str(value))
                elif value is None or (isinstance(value, float) and pd.isna(value)):
                    worksheet.write(row, col_idx, '')
                else:
                    worksheet.write(row, col_idx, str(value))

            row += 1

        # Freeze header row
        worksheet.freeze_panes(1, 0)

        # Add filter
        worksheet.autofilter(0, 0, row - 1, len(columns) - 1)


def export_company_to_excel(reconstructor, cik: int, adsh: str,
                            output_path: str, company_name: str = None):
    """
    Convenience function: Export all statements for a company to Excel

    Args:
        reconstructor: StatementReconstructor instance
        cik: Company CIK
        adsh: Accession number
        output_path: Output Excel file path
        company_name: Company name (optional)
    """
    exporter = ExcelExporter()

    # Get filing metadata for period
    filing_data = reconstructor.load_filing_data(adsh)
    sub = filing_data['sub']
    period = f"{sub['form']} {sub['fy']} {sub['fp']}"

    # Reconstruct all statement types
    for stmt_type in ['BS', 'IS', 'CF']:
        print(f"\nReconstructing {stmt_type}...")
        result = reconstructor.reconstruct_statement(cik, adsh, stmt_type)

        if result.get('line_items'):
            exporter.add_statement(stmt_type, result)
        else:
            print(f"  Warning: No line items found for {stmt_type}")

    # Export to Excel
    if not company_name:
        company_name = sub.get('name', f'CIK {cik}')

    exporter.export(output_path, company_name=company_name, period=period)

    return output_path


if __name__ == '__main__':
    """Test with Amazon"""
    from statement_reconstructor import StatementReconstructor

    print("Testing Excel Export with Amazon")
    print("=" * 60)

    reconstructor = StatementReconstructor(2024, 3)

    output_file = export_company_to_excel(
        reconstructor=reconstructor,
        cik=1018724,
        adsh='0001018724-24-000130',
        output_path='amazon_q2_2024.xlsx',
        company_name='Amazon.com Inc'
    )

    print(f"\n✅ Excel file created: {output_file}")
