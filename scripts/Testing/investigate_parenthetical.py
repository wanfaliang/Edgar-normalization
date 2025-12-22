"""
Investigate parenthetical statements in PRE table
"""
import sqlite3

# Connect to database
conn = sqlite3.connect('data/edgar_data.db')
cursor = conn.cursor()

print("=" * 80)
print("INVESTIGATING PARENTHETICAL STATEMENTS")
print("=" * 80)

# 1. Find all unique statement types in PRE table
print("\n1. All unique statement types in PRE table:")
print("-" * 80)
cursor.execute("""
    SELECT DISTINCT stmt, COUNT(*) as count
    FROM pre
    GROUP BY stmt
    ORDER BY stmt
""")
results = cursor.fetchall()
for stmt, count in results:
    print(f"  {stmt}: {count} rows")

# 2. Check for parenthetical statements specifically
print("\n2. Parenthetical statements:")
print("-" * 80)
cursor.execute("""
    SELECT DISTINCT adsh, stmt
    FROM pre
    WHERE stmt LIKE '%Parenthetical%'
    LIMIT 10
""")
results = cursor.fetchall()
if results:
    for adsh, stmt in results:
        print(f"  {adsh}: {stmt}")
else:
    print("  No parenthetical statements found")

# 3. Let's check Amazon specifically for all statement types
print("\n3. Amazon statement types:")
print("-" * 80)
# Amazon adsh from previous work
amazon_adsh = '0000018926-24-000044'
cursor.execute("""
    SELECT DISTINCT stmt, COUNT(*) as count
    FROM pre
    WHERE adsh = ?
    GROUP BY stmt
    ORDER BY stmt
""", (amazon_adsh,))
results = cursor.fetchall()
for stmt, count in results:
    print(f"  {stmt}: {count} rows")

# 4. Check if parenthetical statements have tags
print("\n4. Checking if parenthetical statements have tags (Amazon):")
print("-" * 80)
cursor.execute("""
    SELECT stmt, COUNT(DISTINCT tag) as tag_count, COUNT(*) as row_count
    FROM pre
    WHERE adsh = ? AND stmt LIKE '%Parenthetical%'
    GROUP BY stmt
""", (amazon_adsh,))
results = cursor.fetchall()
if results:
    for stmt, tag_count, row_count in results:
        print(f"  {stmt}:")
        print(f"    Unique tags: {tag_count}")
        print(f"    Total rows: {row_count}")

        # Show sample tags
        cursor.execute("""
            SELECT tag, plabel, line
            FROM pre
            WHERE adsh = ? AND stmt = ?
            ORDER BY line
            LIMIT 10
        """, (amazon_adsh, stmt))
        samples = cursor.fetchall()
        print(f"    Sample tags:")
        for tag, plabel, line in samples:
            print(f"      Line {line}: {tag} - '{plabel}'")
else:
    print("  No parenthetical statements found for Amazon")

# 5. Check Home Depot
print("\n5. Home Depot statement types:")
print("-" * 80)
# Need to find Home Depot adsh
cursor.execute("""
    SELECT adsh, name
    FROM sub
    WHERE name LIKE '%HOME DEPOT%'
    ORDER BY period DESC
    LIMIT 1
""")
result = cursor.fetchone()
if result:
    hd_adsh, hd_name = result
    print(f"  ADSH: {hd_adsh}")
    print(f"  Name: {hd_name}")

    cursor.execute("""
        SELECT DISTINCT stmt, COUNT(*) as count
        FROM pre
        WHERE adsh = ?
        GROUP BY stmt
        ORDER BY stmt
    """, (hd_adsh,))
    results = cursor.fetchall()
    print(f"\n  Statement types:")
    for stmt, count in results:
        print(f"    {stmt}: {count} rows")

    # Check for parenthetical
    cursor.execute("""
        SELECT stmt, COUNT(DISTINCT tag) as tag_count, COUNT(*) as row_count
        FROM pre
        WHERE adsh = ? AND stmt LIKE '%Parenthetical%'
        GROUP BY stmt
    """, (hd_adsh,))
    results = cursor.fetchall()
    if results:
        print(f"\n  Parenthetical statements:")
        for stmt, tag_count, row_count in results:
            print(f"    {stmt}: {tag_count} unique tags, {row_count} rows")

conn.close()
