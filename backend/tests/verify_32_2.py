from core.route_engine.scoring import RouteScorer
from core.route_engine.constraints import RouteConstraints
from core.data_utils.structures import Route, RouteSegment, Persona
from datetime import datetime, timedelta

async def verify_subtask_32_2():
    print(">>> Verifying Subtask 32.2: Persona Scoring Audit")
    
    # 1. Create two routes
    # Fast but expensive
    r_fast = Route(total_duration=100, total_cost=2000)
    # Slow but cheap
    r_cheap = Route(total_duration=500, total_cost=500)
    
    # 2. Test BUDGET Persona
    c_budget = RouteConstraints(persona=Persona.BUDGET)
    s_fast_budget = await RouteScorer.score_route(r_fast, c_budget)
    s_cheap_budget = await RouteScorer.score_route(r_cheap, c_budget)
    
    print(f"  BUDGET - Fast: {s_fast_budget:.1f}, Cheap: {s_cheap_budget:.1f}")
    assert s_cheap_budget < s_fast_budget # Lower score is better
    
    # 3. Test EMERGENCY Persona (Time is critical)
    c_emergency = RouteConstraints(persona=Persona.EMERGENCY)
    s_fast_em = await RouteScorer.score_route(r_fast, c_emergency)
    s_cheap_em = await RouteScorer.score_route(r_cheap, c_emergency)
    
    print(f"  EMERGENCY - Fast: {s_fast_em:.1f}, Cheap: {s_cheap_em:.1f}")
    assert s_fast_em < s_cheap_em
    
    print("✅ SUBTASK 32.2 VERIFIED")

if __name__ == "__main__":
    import asyncio
    asyncio.run(verify_subtask_32_2())
