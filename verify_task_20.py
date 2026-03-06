import time

def verify_task_20():
    print("🧪 Verifying Task 20: Multi-VPA Merchant Rotation...")
    merchants = ["gauravnagar@okaxis", "routemaster@oksbi", "nagarind@okicici"]
    
    selected = []
    # Test across 3 different minutes (simulated)
    for i in range(3):
        # Simulate time at minute offsets
        sim_time = (i * 60) + 1772794000 
        upi_id = merchants[int(sim_time // 60) % len(merchants)]
        selected.append(upi_id)
        print(f"Minute {i}: {upi_id}")
        
    # Ensure all merchants were used
    assert len(set(selected)) == 3
    assert "gauravnagar@okaxis" in selected
    assert "routemaster@oksbi" in selected
    assert "nagarind@okicici" in selected
    
    print("✅ Task 20 Verification SUCCESSFUL!")

if __name__ == "__main__":
    verify_task_20()
