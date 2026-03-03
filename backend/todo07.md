To eliminate "0 results" and make the system sub-millisecond, we must stop asking the database "What is possible?" and start asking "Which
  pre-calculated path is best?".

  ---

  🧠 Phase 3: 25 Ultra-Specific Database & Retrieval Upgrades


  🚄 I. The "Binary Backbone" (Compressing Knowledge)
   1. 365-bit Service Bitmaps: Instead of checking calendar + calendar_dates (JOINs), store a 46-byte BLOB per trip representing every day of the next
      year. (trip_mask & (1 << day_of_year)) is $O(1)$ and avoids all date-logic overhead.
   2. Quota Availability Bitmask: Map Tatkal, Ladies, and Senior Citizen availability into a 1-byte integer. Filter searches by quota without scanning
      inventory tables.
   3. Delta-Encoded Stop Times: Store arrival_time as minutes-from-departure-of-previous-stop instead of absolute time. This allows the index to fit in
      CPU L1/L2 cache due to smaller integer sizes.
   4. Protobuf/MessagePack for Blobs: SQLite's json_extract is convenient but CPU-heavy. Store the station_transit_index as binary MessagePack. Decoding
      is 10x faster than JSON parsing in hot loops.
   5. Stop-Sequence Bitmaps: A 100-bit mask for every train. If bit 5 is 1, the train stops at its 5th sequence. Allows RAPTOR to skip "Express" trains
      that don't stop at minor stations without reading stop_times.


  🗺️ II. The "Geospatial Intelligence" (Walking & Transfers)
   6. City-Cluster Adjacency: Group stations (e.g., NDLS, DLI, NZM, DEE) into a single Virtual_Delhi_Hub. Search "City to City" first, then resolve the
      "Station to Station" last mile.
   7. Transfer Penalty Heatmap: Pre-compute a (station_id, platform_count) time penalty. Walking from PF 1 to PF 16 at NDLS takes 15 mins; NZM takes 5
      mins. Inject this into RAPTOR cost functions.
   8. Hub-to-Hub Pre-computed Shortcuts: For the top 500 major_hubs, store a backbone_table. If a search is > 1000km, jump through this table first.
   9. Haversine Cache Table: A lookup table for the top 1 million station-to-station distances. Never calculate sqrt() or sin() during a search again.
   10. Walking Radius Bloom Filter: Before checking the neighbor index, use a Bloom Filter to see if a station even has neighbors within 5km. Saves 90% of
       empty neighbor lookups.


  ⚡ III. The "Algorithm-Specific" Hardening (RAPTOR/Turbo)
   11. Clustered Physical Ordering: Use VACUUM INTO to physically reorder stop_times on disk by (trip_id, stop_sequence). This ensures "Sequential Read"
       speeds (6GB/s) instead of "Random Seek" speeds.
   12. Targeted Cover Indexes: Create an index on stop_times that includes (stop_id, departure_time, trip_id). SQLite will answer the query entirely from
       the Index (B-Tree) without ever touching the actual Table (Heap).
   13. Hour-Bucket Partitioning: Split the station_schedule into 24 tables (one per hour). A search at 14:00 only scans the schedule_14 table. Reduces
       search space by 95%.
   14. Inverse Trip Index: A table mapping (station_A, station_B) -> List[TripIDs]. This is the ultimate "Direct Search" optimization.
   15. Route Fingerprint Hashes: Store a MurmurHash3 of a train's entire station sequence. If two trains have the same hash, they follow the same path;
       calculate reliability for one, apply to both.


  💎 IV. Data Integrity & Retrieval Quality
   16. Static Fare Matrix: Store base_fare per km per class in a small 50KB lookup table. Calculate "Estimated Fare" in $O(1)$ during search without
       querying the 100MB train_fares table.
   17. Inverse Calendar Lookup: A table keyed by Date returning a list of Active_Service_IDs. Allows the engine to immediately ignore 70% of trains that
       don't run on the search date.
   18. Station Popularity "Hot-Load": On startup, load the stop_times for the top 100 stations into Redis/RAM. 80% of searches involve these stations.
   19. Zstandard Dictionary Compression: Use a custom Zstd dictionary trained on railway JSONs to compress booking_details. Reduces DB size by 60% and IO
       power consumption.
   20. Search-Space Pruning Index: Store Min_Distance(Hub_A, Hub_B). If a user is searching NDLS -> SBC, the engine will instantly prune any paths going
       through HWH (Howrah) because the distance exceeds the threshold.


  🛡️ V. Performance & Power Management
   21. No-WAL for Transit Graph: Since transit_graph.db is read-only in production, disable WAL and use PRAGMA query_only = ON. This removes the overhead
       of write-locks and shared memory.
   22. Mmap Size Optimization: Set PRAGMA mmap_size = 2147483648 (2GB). This maps the entire database into the process's virtual memory address space.
       Lookups become memory-access speeds ($O(\text{nanoseconds})$).
   23. Bloom Filter for Availability: If a train is 100% full for the next 30 days, store its ID in a Redis Bloom Filter. The search engine skips these
       trains entirely before even checking the schedule.
   24. Incremental Transit Indexing: Only rebuild the station_transit_index for trains that changed in the last ETL run. Currently, we rebuild 8,000
       stations; we should only rebuild ~50.
   25. LRU for "Failed Resolution": Cache searches that return 0 results (e.g., obscure stations). If another user searches the same pair, return "No
       Route" in 0.01ms instead of burning CPU for 2 seconds.
