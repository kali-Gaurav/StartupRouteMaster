import sqlite3
import pandas as pd
import json

def analyze_database(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r[0] for r in cursor.fetchall()]
    
    report = []
    
    for table in tables:
        # Get column details
        cursor.execute(f"PRAGMA table_info({table});")
        columns = cursor.fetchall()
        
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        total_rows = cursor.fetchone()[0]
        
        table_info = {
            "table": table,
            "total_rows": total_rows,
            "columns": []
        }
        
        if total_rows > 0:
            for col in columns:
                col_name = col[1]
                col_type = col[2]
                
                # Check for NULL or Empty
                cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {col_name} IS NULL OR {col_name} = ''")
                empty_count = cursor.fetchone()[0]
                
                # Check for Zeros in Numeric Columns
                zero_count = 0
                if 'INT' in col_type.upper() or 'FLOAT' in col_type.upper() or 'NUMERIC' in col_type.upper():
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {col_name} = 0 OR {col_name} = 0.0")
                        zero_count = cursor.fetchone()[0]
                    except:
                        pass
                
                table_info["columns"].append({
                    "column": col_name,
                    "type": col_type,
                    "empty_null_count": empty_count,
                    "empty_null_percentage": round((empty_count / total_rows) * 100, 2),
                    "zero_count": zero_count,
                    "zero_percentage": round((zero_count / total_rows) * 100, 2) if total_rows > 0 else 0
                })
                
        report.append(table_info)

    # Specific Logical Checks
    logical_errors = {}
    
    try:
        # Segments with 0 distance but > 0 duration
        cursor.execute("SELECT COUNT(*) FROM segments WHERE (distance_km IS NULL OR distance_km <= 0) AND duration_minutes > 0")
        logical_errors["segments_missing_distance"] = cursor.fetchone()[0]
        
        # Stops with 0,0 coordinates
        cursor.execute("SELECT COUNT(*) FROM stops WHERE latitude = 0.0 OR longitude = 0.0 OR latitude IS NULL OR longitude IS NULL")
        logical_errors["stops_missing_coordinates"] = cursor.fetchone()[0]
        
        # Fares with 0 amount
        cursor.execute("SELECT COUNT(*) FROM fares WHERE amount <= 0")
        logical_errors["fares_zero_amount"] = cursor.fetchone()[0]
    except Exception as e:
        logical_errors["error"] = str(e)

    conn.close()
    
    # Print the report
    print("="*60)
    print("DATABASE CORRUPTION & COMPLETENESS REPORT")
    print("="*60)
    
    for t in report:
        print(f"\nTable: {t['table'].upper()} | Total Rows: {t['total_rows']}")
        if t['total_rows'] == 0:
            print("  -> Table is EMPTY.")
            continue
            
        print(f"{'Column Name':<25} | {'Type':<10} | {'Empty/Null':<15} | {'Zero Value':<15}")
        print("-" * 75)
        for c in t['columns']:
            empty_str = f"{c['empty_null_count']} ({c['empty_null_percentage']}%)"
            zero_str = f"{c['zero_count']} ({c['zero_percentage']}%)" if c['zero_count'] > 0 else "-"
            
            # Highlight problematic columns
            flag = ""
            if c['empty_null_percentage'] > 50: flag = "⚠️ HIGH NULL"
            elif c['zero_percentage'] > 50 and c['column'] not in ['stop_sequence', 'transfer_type']: flag = "⚠️ HIGH ZERO"
            
            print(f"{c['column']:<25} | {c['type']:<10} | {empty_str:<15} | {zero_str:<15} {flag}")

    print("\n" + "="*60)
    print("CRITICAL LOGICAL ERRORS")
    print("="*60)
    for k, v in logical_errors.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    analyze_database("backend/database/transit_graph.db")
