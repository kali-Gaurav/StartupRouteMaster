
import sqlite3
import os
import sys
import json

def inspect_db(db_path):
    if not os.path.exists(db_path):
        print(json.dumps({'error': f"DB file not found: {db_path}"}))
        sys.exit(2)
    
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    
    schema = {}
    for t in tables:
        cols = cur.execute(f"PRAGMA table_info('{t}')").fetchall()
        schema[t] = [{"cid": c[0], "name": c[1], "type": c[2], "notnull": bool(c[3]), "default": c[4], "pk": c[5]} for c in cols]
        
    con.close()
    return schema

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(json.dumps({'error': "Please provide the database path as a command-line argument."}))
        sys.exit(1)
        
    db_path = sys.argv[1]
    db_schema = inspect_db(db_path)
    print(json.dumps(db_schema, indent=2))
