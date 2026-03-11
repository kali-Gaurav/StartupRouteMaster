import sqlite3
conn = sqlite3.connect('backend/database/transit_graph.db')
c = conn.cursor()
code = 'NDLS'
pattern = f'%"{(code.upper())}"%'
query = """
WITH cluster_codes AS (
    SELECT value FROM json_each(
        COALESCE(
            (SELECT station_codes_json FROM city_clusters WHERE station_codes_json LIKE ? LIMIT 1),
            json_array(?)
        )
    )
)
SELECT id FROM stops WHERE code IN (SELECT value FROM cluster_codes);
"""
c.execute(query, (pattern, code.upper()))
print(c.fetchall())
conn.close()
