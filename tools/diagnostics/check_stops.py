import sqlite3

def check_stops(codes):
    conn = sqlite3.connect('backend/database/transit_graph.db')
    placeholders = ','.join(['?'] * len(codes))
    query = f"SELECT id, code, name FROM stops WHERE code IN ({placeholders})"
    res = conn.execute(query, codes).fetchall()
    print(f"Stops found: {res}")
    conn.close()

if __name__ == "__main__":
    check_stops(['NDLS', 'CSMT'])
