"""
Validate EDGAR Data Integrity
=============================
Run validation tests on loaded edgar_pre, edgar_num, edgar_tag tables.

Author: Generated with Claude Code
Date: 2025-12
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from sqlalchemy import create_engine, text
from config import config

def get_engine():
    return create_engine(config.get_db_connection())


def test_row_counts(engine):
    """Test 1: Row counts by quarter for each table"""
    print("\n" + "="*70)
    print("TEST 1: ROW COUNTS BY QUARTER")
    print("="*70)

    tables = ['edgar_pre', 'edgar_num', 'edgar_tag']

    for table in tables:
        print(f"\n{table.upper()}:")
        print("-" * 50)

        with engine.connect() as conn:
            result = conn.execute(text(f"""
                SELECT source_year, source_quarter, COUNT(*) as cnt
                FROM {table}
                GROUP BY source_year, source_quarter
                ORDER BY source_year, source_quarter
            """))

            total = 0
            for row in result:
                print(f"  {row[0]}Q{row[1]}: {row[2]:,}")
                total += row[2]

            print(f"  {'TOTAL':>10}: {total:,}")


def test_null_tags(engine):
    """Test 2: Verify no NULL tags in edgar_pre and edgar_num"""
    print("\n" + "="*70)
    print("TEST 2: NULL TAG CHECK")
    print("="*70)

    with engine.connect() as conn:
        # Check edgar_pre
        result = conn.execute(text("SELECT COUNT(*) FROM edgar_pre WHERE tag IS NULL"))
        null_pre = result.scalar()

        # Check edgar_num
        result = conn.execute(text("SELECT COUNT(*) FROM edgar_num WHERE tag IS NULL"))
        null_num = result.scalar()

        # Check edgar_tag
        result = conn.execute(text("SELECT COUNT(*) FROM edgar_tag WHERE tag IS NULL"))
        null_tag = result.scalar()

    print(f"  edgar_pre NULL tags: {null_pre}")
    print(f"  edgar_num NULL tags: {null_num}")
    print(f"  edgar_tag NULL tags: {null_tag}")

    if null_pre == 0 and null_num == 0 and null_tag == 0:
        print("  ✅ PASS: No NULL tags found")
    else:
        print("  ❌ FAIL: NULL tags found!")


def test_value_ranges(engine):
    """Test 3: Check value ranges in edgar_num"""
    print("\n" + "="*70)
    print("TEST 3: VALUE RANGES IN EDGAR_NUM")
    print("="*70)

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT
                MIN(value) as min_val,
                MAX(value) as max_val,
                AVG(value) as avg_val,
                COUNT(*) as total,
                COUNT(value) as non_null,
                COUNT(*) - COUNT(value) as null_count
            FROM edgar_num
        """))
        row = result.fetchone()

        print(f"  Min value: {row[0]:,.4f}" if row[0] else "  Min value: NULL")
        print(f"  Max value: {row[1]:,.4f}" if row[1] else "  Max value: NULL")
        print(f"  Avg value: {row[2]:,.4f}" if row[2] else "  Avg value: NULL")
        print(f"  Total rows: {row[3]:,}")
        print(f"  Non-null values: {row[4]:,}")
        print(f"  Null values: {row[5]:,}")

        # Check for extreme values
        result = conn.execute(text("""
            SELECT COUNT(*) FROM edgar_num
            WHERE ABS(value) > 1000000000000000
        """))
        extreme = result.scalar()
        print(f"  Values > 1 quadrillion: {extreme:,}")


def test_sample_queries(engine):
    """Test 4: Run sample queries to verify data is queryable"""
    print("\n" + "="*70)
    print("TEST 4: SAMPLE QUERIES")
    print("="*70)

    with engine.connect() as conn:
        # Sample query 1: Top 10 most common tags in edgar_pre
        print("\n  Top 10 most common tags in edgar_pre:")
        result = conn.execute(text("""
            SELECT tag, COUNT(*) as cnt
            FROM edgar_pre
            GROUP BY tag
            ORDER BY cnt DESC
            LIMIT 10
        """))
        for row in result:
            print(f"    {row[0]}: {row[1]:,}")

        # Sample query 2: Distinct statement types
        print("\n  Statement types in edgar_pre:")
        result = conn.execute(text("""
            SELECT stmt, COUNT(*) as cnt
            FROM edgar_pre
            GROUP BY stmt
            ORDER BY cnt DESC
        """))
        for row in result:
            print(f"    {row[0]}: {row[1]:,}")

        # Sample query 3: Sample filing with values
        print("\n  Sample filing data (first 5 values):")
        result = conn.execute(text("""
            SELECT adsh, tag, value, ddate
            FROM edgar_num
            WHERE value IS NOT NULL
            LIMIT 5
        """))
        for row in result:
            print(f"    {row[0]}: {row[1]} = {row[2]:,.2f} (date: {row[3]})")


def test_cross_table_consistency(engine):
    """Test 5: Check cross-table consistency"""
    print("\n" + "="*70)
    print("TEST 5: CROSS-TABLE CONSISTENCY")
    print("="*70)

    with engine.connect() as conn:
        # Check quarters match across tables
        print("\n  Quarters present in each table:")

        for table in ['edgar_pre', 'edgar_num', 'edgar_tag']:
            result = conn.execute(text(f"""
                SELECT COUNT(DISTINCT (source_year, source_quarter))
                FROM {table}
            """))
            count = result.scalar()
            print(f"    {table}: {count} quarters")

        # Sample: Tags in pre that exist in tag
        print("\n  Tag coverage check (sample 2024Q3):")
        result = conn.execute(text("""
            SELECT
                (SELECT COUNT(DISTINCT tag) FROM edgar_pre
                 WHERE source_year = 2024 AND source_quarter = 3) as pre_tags,
                (SELECT COUNT(DISTINCT tag) FROM edgar_num
                 WHERE source_year = 2024 AND source_quarter = 3) as num_tags,
                (SELECT COUNT(DISTINCT tag) FROM edgar_tag
                 WHERE source_year = 2024 AND source_quarter = 3) as tag_defs
        """))
        row = result.fetchone()
        print(f"    edgar_pre distinct tags: {row[0]:,}")
        print(f"    edgar_num distinct tags: {row[1]:,}")
        print(f"    edgar_tag definitions: {row[2]:,}")


def main():
    print("\n" + "#"*70)
    print("EDGAR DATA VALIDATION")
    print("#"*70)

    engine = get_engine()

    test_row_counts(engine)
    test_null_tags(engine)
    test_value_ranges(engine)
    test_sample_queries(engine)
    test_cross_table_consistency(engine)

    print("\n" + "="*70)
    print("VALIDATION COMPLETE")
    print("="*70 + "\n")


if __name__ == '__main__':
    main()
