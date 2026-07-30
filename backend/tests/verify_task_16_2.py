import sys
import os
import numpy as np
import time

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.geo_utils import haversine_distance, haversine_vectorized

def verify_task_16_2():
    print("\n>>> Verifying Task 16.2: Vectorized Haversine")
    
    # 1. Scalar Test
    lat1, lon1 = 28.6139, 77.2090 # Delhi
    lat2, lon2 = 19.0760, 72.8777 # Mumbai
    
    d_scalar = haversine_distance(lat1, lon1, lat2, lon2)
    d_vec = haversine_vectorized(lat1, lon1, lat2, lon2)
    
    print(f"  Delhi to Mumbai: Scalar={d_scalar:.2f}km, Vectorized={d_vec:.2f}km")
    
    if abs(d_scalar - d_vec) > 0.01:
        print("❌ FAILURE: Scalar and Vectorized distance mismatch.")
        return False
        
    # 2. Array Test
    num_points = 10000
    lats1 = np.random.uniform(8, 35, num_points)
    lons1 = np.random.uniform(68, 97, num_points)
    lats2 = np.random.uniform(8, 35, num_points)
    lons2 = np.random.uniform(68, 97, num_points)
    
    start = time.perf_counter()
    res_vec = haversine_vectorized(lats1, lons1, lats2, lons2)
    vec_time = (time.perf_counter() - start) * 1000
    
    start = time.perf_counter()
    res_scalar = []
    for i in range(num_points):
        res_scalar.append(haversine_distance(lats1[i], lons1[i], lats2[i], lons2[i]))
    scalar_time = (time.perf_counter() - start) * 1000
    
    print(f"  Benchmark (10k points): Scalar={scalar_time:.2f}ms, Vectorized={vec_time:.2f}ms")
    print(f"  Speedup: {scalar_time / vec_time:.1f}x")
    
    if vec_time > scalar_time:
        print("❌ FAILURE: Vectorized version is slower than loop (unexpected).")
        return False

    print("\n✅ TASK 16.2 VERIFIED: haversine_vectorized is accurate and fast.")
    return True

if __name__ == "__main__":
    verify_task_16_2()
