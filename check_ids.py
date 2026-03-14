import sqlite3
conn = sqlite3.connect('backend/database/transit_graph.db')
cur = conn.cursor()
codes = ['NDLS', 'BCT', 'CSMT', 'HWH', 'MAS', 'BZA', 'PNBE', 'PUNE']
placeholders = ','.join(['?'] * len(codes))
cur.execute(f"SELECT id, code FROM stops WHERE code IN ({placeholders})", codes)
print("IDs:", cur.fetchall())
conn.close()
