"""
Batch Export Financial Statements to Excel
==========================================
Export multiple companies' financial statements to Excel format for validation
"""
from src.statement_reconstructor import StatementReconstructor
from src.excel_exporter import export_company_to_excel
from pathlib import Path

# Define companies to export
COMPANIES = [
    {
        'name': 'Amazon.com Inc',
        'cik': 1018724,
        'adsh': '0001018724-24-000130',
        'filename': 'amazon_q2_2024.xlsx'
    },
    {
        'name': 'The Home Depot Inc',
        'cik': 354950,
        'adsh': '0000354950-24-000201',
        'filename': 'home_depot_q2_2024.xlsx'
    },
    {
        'name': 'Procter & Gamble Co',
        'cik': 80424,
        'adsh': '0000080424-24-000083',  # FY2024 10-K
        'filename': 'procter_gamble_fy2024.xlsx'
    },
    {
        'name': 'M&T Bank Corp',
        'cik': 36270,
        'adsh': '0001628280-24-034695',  # FY2024 Q2
        'filename': 'mt_bank_q2_2024.xlsx'
    }
]

def main():
    """Export all companies to Excel"""
    print("=" * 80)
    print("BATCH EXPORT TO EXCEL")
    print("=" * 80)
    print(f"\nExporting {len(COMPANIES)} companies...")

    # Create output directory
    output_dir = Path('output')
    output_dir.mkdir(exist_ok=True)

    # Initialize reconstructor
    reconstructor = StatementReconstructor(2024, 3)

    successful = []
    failed = []

    for i, company in enumerate(COMPANIES, 1):
        print(f"\n{'=' * 80}")
        print(f"[{i}/{len(COMPANIES)}] {company['name']}")
        print(f"{'=' * 80}")

        try:
            output_path = output_dir / company['filename']

            export_company_to_excel(
                reconstructor=reconstructor,
                cik=company['cik'],
                adsh=company['adsh'],
                output_path=str(output_path),
                company_name=company['name']
            )

            successful.append({
                'name': company['name'],
                'file': str(output_path)
            })
            print(f"✅ Success: {output_path}")

        except Exception as e:
            failed.append({
                'name': company['name'],
                'error': str(e)
            })
            print(f"❌ Failed: {e}")

    # Summary
    print("\n" + "=" * 80)
    print("EXPORT SUMMARY")
    print("=" * 80)

    print(f"\n✅ Successful: {len(successful)}/{len(COMPANIES)}")
    for item in successful:
        print(f"   - {item['name']}")
        print(f"     {item['file']}")

    if failed:
        print(f"\n❌ Failed: {len(failed)}/{len(COMPANIES)}")
        for item in failed:
            print(f"   - {item['name']}: {item['error']}")

    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print("\n1. Open Excel files in output/ directory")
    print("2. Compare values to EDGAR viewer side-by-side:")
    print("\n   Amazon:")
    print("   https://www.sec.gov/cgi-bin/viewer?action=view&cik=0001018724&accession_number=0001018724-24-000130&xbrl_type=v")
    print("\n   Home Depot:")
    print("   https://www.sec.gov/cgi-bin/viewer?action=view&cik=0000354950&accession_number=0000354950-24-000201&xbrl_type=v")
    print("\n   Procter & Gamble:")
    print("   https://www.sec.gov/cgi-bin/viewer?action=view&cik=0000080424&accession_number=0000080424-24-000083&xbrl_type=v")
    print("\n   M&T Bank:")
    print("   https://www.sec.gov/cgi-bin/viewer?action=view&cik=0000036270&accession_number=0001628280-24-034695&xbrl_type=v")
    print("\n3. Review Metadata sheet to see all captured fields")
    print("\n" + "=" * 80)

if __name__ == '__main__':
    main()
