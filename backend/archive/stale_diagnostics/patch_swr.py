import sys
import re

with open('core/route_engine/engine.py', 'r') as f:
    content = f.read()

pattern = re.compile(r'    async def _get_current_graph\(.*?return self\.graph', re.DOTALL)

new_swr_code = """    async def _background_build_and_swap(self, date: datetime, force_rebuild: bool = False):
        \"\"\"[SWR Core] Background worker that builds the graph and performs an atomic swap.\"\"\"
        if getattr(self, '_is_building', False):
            return
        
        self._is_building = True
        try:
            logger.info(f"🔄 [SWR] Background graph rebuild started for {date.date()}")
            
            # Fetch or build graph
            snapshot = await self.snapshot_manager.load_snapshot(date) if not force_rebuild else None
            is_nexus_grade = snapshot and hasattr(snapshot, '_trip_reachability_bitset') and \
                 getattr(snapshot, 'cluster_reachability', None) is not None
                 
            if not snapshot or not is_nexus_grade:
                logger.info(f"🔄 [SWR] Building fresh Nexus-Grade graph...")
                new_graph = await self.graph_builder.build_graph(date)
                if new_graph.snapshot:
                    asyncio.create_task(self.snapshot_manager.save_snapshot(new_graph.snapshot))
                    
                # [Nexus:Cloud] Background R2 Sync
                async def _sync_to_cloud():
                    await asyncio.sleep(10)
                    await r2_sync.upload_transit_db()
                    await r2_sync.upload_latest_snapshot()
                asyncio.create_task(_sync_to_cloud())
            else:
                new_graph = TimeDependentGraph(snapshot, overlay=self.overlay)
                
            # Atomic Swap (GIL makes reference assignment atomic)
            new_graph.overlay = self.overlay
            self.graph = new_graph
            
            self.last_rebuild_status = "READY_FRESH"
            logger.info(f"✅ [SWR] Background rebuild complete. Atomic swap successful.")
            
            asyncio.create_task(self._predictive_hydration(self.graph))
        except Exception as e:
            logger.error(f"❌ [SWR] Background rebuild failed: {e}")
            self.last_rebuild_status = "FAILED"
        finally:
            self._is_building = False

    async def _get_current_graph(self, date: datetime, force_rebuild: bool=False) -> Optional[TimeDependentGraph]:
        # Path 1: Fresh Graph exists in memory
        if self.graph and self.graph.snapshot and self.graph.snapshot.date.date() == date.date() and not force_rebuild:
            self.graph.overlay = self.overlay
            self.last_rebuild_status = "READY_FRESH"
            return self.graph
            
        # Path 2: Stale Graph exists in memory (SWR Fallback)
        if self.graph and self.graph.snapshot:
            self.last_rebuild_status = "READY_STALE"
            if not getattr(self, '_is_building', False):
                asyncio.create_task(self._background_build_and_swap(date, force_rebuild))
            return self.graph
            
        # Path 3: Cold Start (Block only if absolutely nothing is available)
        async with self._lock:
            # Check if another request built it while we waited
            if self.graph: return self.graph
            
            # Try to load exactly what they want
            snapshot = await self.snapshot_manager.load_snapshot(date) if not force_rebuild else None
            
            # SWR Fallback: Try to load any available snapshot to avoid blocking
            if not snapshot:
                snapshot = await self.snapshot_manager.get_latest_snapshot_fallback()
                if snapshot:
                    self.graph = TimeDependentGraph(snapshot, overlay=self.overlay)
                    self.last_rebuild_status = "READY_STALE"
                    if not getattr(self, '_is_building', False):
                        asyncio.create_task(self._background_build_and_swap(date, force_rebuild))
                    return self.graph

            # Ultimate Slow Path: Block and build if no snapshots exist anywhere
            self.last_rebuild_status = "REBUILDING"
            await self._background_build_and_swap(date, force_rebuild)
            return self.graph"""

new_content, count = pattern.subn(new_swr_code, content)
if count > 0:
    with open('core/route_engine/engine.py', 'w') as f:
        f.write(new_content)
    print("Replaced successfully")
else:
    print("Could not find pattern")
