from core.data_utils.structures import Route, RouteSegment
from datetime import datetime

def verify_subtask_32_1():
    print(">>> Verifying Subtask 32.1: Highlights Schema")
    
    # 1. Create a route with highlights
    r = Route(
        is_featured=True,
        highlight_label="Best Value"
    )
    
    # 2. Check internal fields
    assert r.is_featured == True
    assert r.highlight_label == "Best Value"
    print("  Internal fields: OK")
    
    # 3. Check serialization
    d = r.to_dict()
    assert d["is_featured"] == True
    assert d["highlight_label"] == "Best Value"
    print("  Serialization: OK")
    
    print("✅ SUBTASK 32.1 VERIFIED")

if __name__ == "__main__":
    verify_subtask_32_1()
