import sys
import os
import httpx
import asyncio

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def verify_task_2_csv():
    print("=== Verifying Task 2 Gap: CSV Failover Upload ===")
    
    # Create a mock CSV content matching expected structures
    csv_content = """Date,Description,Amount,Balance
10-05-2023,UPI/123456789012/Transfer,500.00,1000.00
10-05-2023,NEFT/111122223333/Salary,5000.00,6000.00
11-05-2023,IMPS/999988887777/Rent,100.00,5900.00
"""
    
    # Write temporary file
    with open("test_bank_statement.csv", "w") as f:
        f.write(csv_content)

    try:
        async with httpx.AsyncClient() as client:
            print("Uploading CSV to /api/bank_webhook/upload_csv...")
            with open("test_bank_statement.csv", "rb") as f:
                response = await client.post(
                    "http://localhost:8000/api/bank_webhook/upload_csv",
                    files={"file": ("test_bank_statement.csv", f, "text/csv")},
                    timeout=10
                )
            
        print(f"Response: {response.status_code} - {response.text}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["details"]["total"] == 3 # Should find 3 UTRs
        print("[OK] CSV Parsing & UTR Extraction")
    finally:
        if os.path.exists("test_bank_statement.csv"):
            os.remove("test_bank_statement.csv")

    print("=== Task 2 Gap Verification Complete ===")

if __name__ == "__main__":
    asyncio.run(verify_task_2_csv())
