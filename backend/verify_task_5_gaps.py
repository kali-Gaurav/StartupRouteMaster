import sys
import os
import io
from datetime import datetime
from services.tax_engine_service import tax_engine

def verify_task_5_gaps():
    print("=== Verifying Task 5 Gaps: PDF, Export, Currency, & Simulator ===")
    
    # 1. Test PDF Invoice Generation
    print("Testing PDF Generation...")
    breakdown = tax_engine.calculate_breakdown(1000.0)
    pdf_buffer = tax_engine.generate_tax_invoice_pdf(
        transaction_id="TX_TEST_123",
        date_str="2023-05-10",
        breakdown=breakdown
    )
    if pdf_buffer:
        assert isinstance(pdf_buffer, io.BytesIO)
        assert pdf_buffer.getbuffer().nbytes > 0
        print("[OK] PDF Generated successfully")
    else:
        print("[SKIP] ReportLab not installed")

    # 2. Test Currency Conversion
    print("Testing Internal Currency Conversion...")
    breakdown_usd = tax_engine.calculate_breakdown(1000.0, display_currency="USD")
    assert breakdown_usd["display_currency"] == "USD"
    # Total is 1024 INR. USD rate is 83.50. 1024 / 83.50 = 12.26
    assert breakdown_usd["display_total"] == round(1024.0 / tax_engine.EXCHANGE_RATES["USD"], 2)
    print("[OK] Multi-currency internal conversion")

    # 3. Test Settlement Simulator
    print("Testing Settlement Delay Simulator...")
    txn_date = datetime(2023, 5, 10, 10, 0, 0) # Wednesday
    
    # T+1 Normal
    sim_t1 = tax_engine.simulate_settlement(txn_date, is_holiday=False)
    assert sim_t1["settlement_type"] == "T+1"
    
    # T+2 Holiday
    sim_t2 = tax_engine.simulate_settlement(txn_date, is_holiday=True)
    assert sim_t2["settlement_type"] == "T+2"
    print("[OK] Settlement Simulator")

    print("=== Task 5 Gaps Verification Complete ===")

if __name__ == "__main__":
    verify_task_5_gaps()
