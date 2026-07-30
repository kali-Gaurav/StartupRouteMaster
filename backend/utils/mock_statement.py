import random
from datetime import datetime, timedelta
from typing import List, Dict, Any

def generate_mock_bank_statement(count: int = 10) -> List[Dict[str, Any]]:
    """
    Task 7.2: Mock Bank Statement Generator.
    Simulates a list of recent transactions from a bank portal.
    """
    transactions = []
    banks = ["HDFC", "SBI", "ICICI", "AXIS"]
    
    for i in range(count):
        utr = str(random.randint(100000000000, 999999999999))
        amount = round(random.uniform(500, 5000), 2)
        # Randomly add cent-matching paisa
        if random.choice([True, False]):
            amount = round(float(random.randint(500, 5000)) + (random.randint(1, 99) / 100.0), 2)
            
        bank = random.choice(banks)
        date = datetime.now() - timedelta(minutes=random.randint(1, 60))
        
        transactions.append({
            "utr": utr,
            "amount": amount,
            "bank": bank,
            "description": f"UPI/PAY/{utr}/RM_{random.randint(1000,9999)}",
            "timestamp": date.isoformat()
        })
        
    return transactions

if __name__ == "__main__":
    import json
    print(json.dumps(generate_mock_bank_statement(5), indent=2))
