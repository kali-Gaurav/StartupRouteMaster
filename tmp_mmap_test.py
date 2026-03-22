
import numpy as np
import os
import json

def test_memmap():
    path = "tmp_mmap.dat"
    shape = (8527, 2)
    dtype = 'float32'
    
    print(f"DEBUG: Saving to {path}")
    array = np.zeros(shape, dtype=dtype)
    fp = np.memmap(path, dtype=dtype, mode='w+', shape=shape)
    fp[:] = array[:]
    fp.flush()
    # If we don't delete fp, what happens?
    
    print(f"DEBUG: Loading from {path}")
    try:
        fp_read = np.memmap(path, dtype=dtype, mode='r', shape=shape)
        print("DEBUG: Success")
    except Exception as e:
        print(f"DEBUG: Error: {e}")
    finally:
        if os.path.exists(path):
            os.remove(path)

if __name__ == "__main__":
    test_memmap()
