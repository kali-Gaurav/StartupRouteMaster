"""
Copy tables and data from backend/railway_manager01.db into workspace railway_manager.db.
Behavior:
 - For each non-system table in source, if table doesn't exist in target, create it using the source CREATE TABLE SQL.
 - If table exists, insert rows from source into target.
 - If table has a primary key, use INSERT OR REPLACE so rows with the same PK are updated; otherwise do a plain INSERT.
 - Prints a short summary per table: rows read, rows inserted/updated.
"""
import sqlite3
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
SRC = os.path.normpath(os.path.join(ROOT, 'backend', 'railway_manager01.db'))
DST = os.path.normpath(os.path.join(ROOT, 'railway_manager.db'))

if not os.path.exists(SRC):
    print(f"Source DB not found: {SRC}")
    sys.exit(2)

if not os.path.exists(DST):
    print(f"Target DB not found: {DST} — creating new DB at that path.")
    open(DST, 'a').close()

src_con = sqlite3.connect(SRC)
src_con.row_factory = sqlite3.Row
s_cur = src_con.cursor()

dst_con = sqlite3.connect(DST)
dst_con.row_factory = sqlite3.Row
d_cur = dst_con.cursor()

# gather tables from source (exclude sqlite_ internal)
s_cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
tables = s_cur.fetchall()

summary = []

for t_row in tables:
    tname = t_row['name']
    create_sql = t_row['sql']
    print(f"\nProcessing table: {tname}")

    # if table missing in destination, create it
    d_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tname,))
    if d_cur.fetchone() is None:
        if create_sql:
            try:
                d_cur.execute(create_sql)
                dst_con.commit()
                print(f"  Created table {tname} in target DB")
            except Exception as e:
                print(f"  Failed to create table {tname}: {e}")
                continue
        else:
            print(f"  No CREATE SQL available for {tname}; skipping")
            continue

    # get column info and pk info
    s_cur.execute(f"PRAGMA table_info('{tname}')")
    cols = s_cur.fetchall()
    col_names = [c[1] for c in cols]
    pk_cols = [c[1] for c in cols if c[5] and c[5] > 0]

    # read rows from source
    s_cur.execute(f"SELECT * FROM '{tname}'")
    rows = s_cur.fetchall()
    total_rows = len(rows)
    if total_rows == 0:
        print("  No rows to copy")
        summary.append((tname, 0, 0))
        continue

    placeholders = ','.join(['?'] * len(col_names))
    cols_sql = ','.join([f'"{c}"' for c in col_names])

    # choose insert mode
    if pk_cols:
        insert_sql = f"INSERT OR REPLACE INTO '{tname}' ({cols_sql}) VALUES ({placeholders})"
    else:
        insert_sql = f"INSERT INTO '{tname}' ({cols_sql}) VALUES ({placeholders})"

    # prepare data tuples
    data = [tuple(row[c] for c in col_names) for row in rows]

    inserted = 0
    try:
        d_cur.executemany(insert_sql, data)
        dst_con.commit()
        inserted = d_cur.rowcount if d_cur.rowcount is not None else total_rows
        # rowcount for executemany may be -1 in sqlite; use total_rows as fallback
        if inserted < 0:
            inserted = total_rows
        print(f"  Read {total_rows} rows from source, attempted insert (or replace) into target")
    except Exception as e:
        print(f"  Error inserting rows into {tname}: {e}")
        # attempt row-by-row to get partial progress
        inserted = 0
        for r in data:
            try:
                d_cur.execute(insert_sql, r)
                inserted += 1
            except Exception as e2:
                # skip problematic row
                print(f"    skipping row due to error: {e2}")
        dst_con.commit()
    summary.append((tname, total_rows, inserted))

src_con.close()
dst_con.close()

print("\nCopy summary:")
for tn, rcount, icount in summary:
    print(f" - {tn}: source_rows={rcount}, target_rows_written={icount}")

print('\nDone.')
