import sqlite3
conn = sqlite3.connect('backend/database/transit_graph.db')
cur = conn.cursor()
MAJOR_HUBS = [
    "NDLS", "HWH", "MAS", "CSMT", "BRC", "CNB", "PNBE", "KGP", "VGLJ", "BPL",
    "AGC", "JP", "ADI", "SC", "SBC", "BSB", "DDU", "ET", "NGP", "LKO", "MTJ"
]
placeholders = ','.join(['?'] * len(MAJOR_HUBS))
cur.execute(f"SELECT id, code FROM stops WHERE code IN ({placeholders})", MAJOR_HUBS)
res = cur.fetchall()
print(res)
conn.close()
