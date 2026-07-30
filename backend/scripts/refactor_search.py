import re

fname = r"C:\Users\Gaurav Nagar\OneDrive\Desktop\startupV2\backend\services\search_service.py"
with open(fname, "r", encoding="utf-8") as f:
    code = f.read()

# Add RoutingRequest import
if "RoutingRequest" not in code:
    code = code.replace("from core.route_engine.orchestrator import UnifiedRoutingOrchestrator",
                        "from core.route_engine.orchestrator import UnifiedRoutingOrchestrator\nfrom core.route_engine.base import RoutingRequest")

# 1. First usage: discovery_task
rep1_old = """            discovery_task = asyncio.create_task(orchestrator.search_all_tiers(
                source_code=source,
                destination_code=destination,
                departure_date=dt,
                constraints=c,
                limit=max(100, limit * 3),
                db=self.transit_db,
                skip_heavy=skip_heavy,
                discovery_cache_key=discovery_key
            ))"""

rep1_new = """            req = RoutingRequest(
                source_code=source,
                destination_code=destination,
                departure_date=dt,
                constraints=c,
                limit=max(100, limit * 3),
                db_session=self.transit_db,
                src_cluster_ids=[],
                dst_cluster_ids=[]
            )
            discovery_task = asyncio.create_task(orchestrator.search_all_tiers(
                request=req,
                skip_heavy=skip_heavy,
                discovery_cache_key=discovery_key
            ))"""
code = code.replace(rep1_old, rep1_new)

# 2. res_plus
rep2_old = """res_plus = await orchestrator.search_all_tiers(source, destination, dt + timedelta(days=1), c, internal_limit, self.transit_db)"""
rep2_new = """req_plus = RoutingRequest(source_code=source, destination_code=destination, departure_date=dt + timedelta(days=1), constraints=c, limit=internal_limit, db_session=self.transit_db, src_cluster_ids=[], dst_cluster_ids=[])
                    res_plus = await orchestrator.search_all_tiers(req_plus)"""
code = code.replace(rep2_old, rep2_new)

# 3. res_minus
rep3_old = """res_minus = await orchestrator.search_all_tiers(source, destination, dt - timedelta(days=1), c, internal_limit, self.transit_db)"""
rep3_new = """req_minus = RoutingRequest(source_code=source, destination_code=destination, departure_date=dt - timedelta(days=1), constraints=c, limit=internal_limit, db_session=self.transit_db, src_cluster_ids=[], dst_cluster_ids=[])
                            res_minus = await orchestrator.search_all_tiers(req_minus)"""
code = code.replace(rep3_old, rep3_new)

# 4. hub_tasks
rep4_old = """                    hub_tasks.append(orchestrator.search_all_tiers(source, hub_code, dt, c, 50))
                    hub_tasks.append(orchestrator.search_all_tiers(hub_code, destination, dt, c, 50))"""

rep4_new = """                    req_h1 = RoutingRequest(source_code=source, destination_code=hub_code, departure_date=dt, constraints=c, limit=50, src_cluster_ids=[], dst_cluster_ids=[])
                    req_h2 = RoutingRequest(source_code=hub_code, destination_code=destination, departure_date=dt, constraints=c, limit=50, src_cluster_ids=[], dst_cluster_ids=[])
                    hub_tasks.append(orchestrator.search_all_tiers(req_h1))
                    hub_tasks.append(orchestrator.search_all_tiers(req_h2))"""
code = code.replace(rep4_old, rep4_new)

# 5. tatkal_results
rep5_old = """tatkal_results = await orchestrator.search_all_tiers(source, destination, dt, c, 10, self.transit_db)"""
rep5_new = """req_tatkal = RoutingRequest(source_code=source, destination_code=destination, departure_date=dt, constraints=c, limit=10, db_session=self.transit_db, src_cluster_ids=[], dst_cluster_ids=[])
                tatkal_results = await orchestrator.search_all_tiers(req_tatkal)"""
code = code.replace(rep5_old, rep5_new)


with open(fname, "w", encoding="utf-8") as f:
    f.write(code)
print("Updated search_service.py")
