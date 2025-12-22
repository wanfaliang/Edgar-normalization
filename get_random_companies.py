import psycopg2
import sys
sys.path.insert(0, 'src')
from config import config

conn = psycopg2.connect(config.get_db_connection())
cur = conn.cursor()

# Get 100 random companies that have filings
cur.execute("""
    SELECT cik FROM (
        SELECT DISTINCT c.cik
        FROM companies c
        JOIN filings f ON c.cik = f.cik
        WHERE c.ticker IS NOT NULL
        AND c.ticker != ''
    ) AS unique_companies
    ORDER BY RANDOM()
    LIMIT 100
""")

results = cur.fetchall()
ciks = [row[0] for row in results]
print(", ".join(ciks))

cur.close()
conn.close()
