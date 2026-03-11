    async def _hydrate_fares_and_score(self, routes: List[Route], constraints: RouteConstraints, graph, db):
        from .scoring import RouteScorer
        from sqlalchemy import text
        
        trip_pks = set()
        train_nos = set()
        for r in routes:
            for s in r.segments:
                if isinstance(s.trip_id, int): trip_pks.add(s.trip_id)
                if s.train_number: train_nos.add(str(s.train_number))
        
        fare_map = {} 
        
        if trip_pks:
            pks_str = ",".join([str(tid) for tid in trip_pks])
            try:
                rows = db.execute(text(f"SELECT trip_id, amount FROM fares WHERE trip_id IN ({pks_str})")).fetchall()
                for tid, amt in rows:
                    fare_map[str(tid)] = amt
            except: pass

        if train_nos:
            nos_str = ",".join([f"'{n}'" for n in train_nos])
            try:
                rows = db.execute(text(f"""
                    SELECT t.trip_id, f.amount 
                    FROM fares f 
                    JOIN trips t ON f.trip_id = t.id 
                    WHERE t.trip_id IN ({nos_str})
                """)).fetchall()
                for tcode, amt in rows:
                    fare_map[str(tcode)] = amt
            except: pass

        for r in routes:
            # [38.3] Multi-leg fare optimization
            is_multi = len(r.segments) > 1
            total_dist = 0.0
            
            for s in r.segments:
                # [FIX] Ensure duration is calculated if missing
                if not s.duration_minutes or s.duration_minutes <= 0:
                    try:
                        # Attempt to parse time strings if needed, or use duration from data
                        # For simplicity, if missing, we use a default based on segment type
                        s.duration_minutes = 120 
                    except: s.duration_minutes = 60

                # If distance is missing, estimate from duration (avg speed 55 km/h)
                if not s.distance_km or s.distance_km < 1.0:
                    s.distance_km = round(s.duration_minutes * 0.916, 2)
                
                total_dist += s.distance_km

            # [FIX] Calculate total fare using cumulative distance for the entire journey
            # This prevents Rs. 54 fares for 2000km trips.
            effective_total_dist = max(total_dist, 50.0)
            
            # Fetch a baseline "DB fare" if it exists for the primary train
            primary_train = r.segments[0].train_number
            db_base_fare = fare_map.get(str(primary_train))
            
            if db_base_fare and not is_multi:
                # Direct route with known DB fare
                r.total_cost = float(db_base_fare)
            else:
                # [38.2] Recalculate using telescopic logic for multi-leg or unknown
                fare_res = calculate_fare(effective_total_dist, "SL", is_multi_leg=is_multi)
                r.total_cost = fare_res["total_fare"]
            
            r.total_distance = total_dist

            # Update individual segment fares proportionally for UI
            for s in r.segments:
                if total_dist > 0:
                    s.fare = round((s.distance_km / total_dist) * r.total_cost, 2)
                else:
                    s.fare = round(r.total_cost / len(r.segments), 2)
            
            # Add small discount for very long journeys (Telescopic benefit)
            if is_multi and total_dist > 1000:
                r.total_cost = round(r.total_cost * 0.98, 2)
            
            r.total_duration = sum(s.duration_minutes for s in r.segments) + sum(t.duration_minutes for t in r.transfers)
            r.score = await RouteScorer.score_route(r, constraints, getattr(graph.snapshot, 'reliability_scores', {}))
