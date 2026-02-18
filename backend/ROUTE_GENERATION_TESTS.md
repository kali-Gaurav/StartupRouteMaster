# Route Generation — Feature Test Checklist (220 cases)

Purpose: exhaustive, actionable feature-test list for backend route-generation (search + route-engine + integrated search). Use each item as a manual test or convert to automated pytest stubs.

How to use:
- Each test has an ID (RT-###). Copy into test files or use as tickets.
- Mark priority (P0/P1/P2) when converting to automation.

---

## Quick metadata
- Area: route search / route generation / journey reconstruction
- Primary modules: `backend/route_engine.py`, `backend/core/multi_modal_route_engine.py`, `backend/api/search.py`, `backend/api/integrated_search.py`, `backend/services/*` (cache, ml, station)

---

## Tests (RT-001 — RT-220)

### Core correctness (RT-001 — RT-015)
1. RT-001 — Direct single-leg route exists: return at least one direct route when direct trip scheduled. (expect: direct segment, correct times)
2. RT-002 — No route available: return empty results with helpful message for impossible source/destination/date.
3. RT-003 — Route arrival/departure sanity: arrival >= departure and duration matches sum of segment durations.
4. RT-004 — Journey time calculation: total travel_time equals computed segment durations + transfers.
5. RT-005 — Unique route IDs: each returned route contains a stable unique identifier (`journey_id`).
6. RT-006 — Max results respected: `max_results` constraint enforced by API and engine.
7. RT-007 — Deterministic results (stable graph): repeated identical queries return identical ordered results (when no realtime changes).
8. RT-008 — Response schema validation: API response matches documented schema (types/required fields).
9. RT-009 — Pagination & limits: large result sets paginate correctly if supported; `limit`/`offset` respected.
10. RT-010 — Source/destination swap: searching reversed origin/destination returns plausible reversed routes or empty when one-way.
11. RT-011 — Station alias handling: station synonyms/codes map to same station (e.g., `NDLS` and `New Delhi`).
12. RT-012 — Route contains station sequence: each route segment lists correct ordered station stop IDs.
13. RT-013 — Route timestamps timezone-aware: timestamps are ISO strings and consistent for local timezone handling.
14. RT-014 — Max journey duration constraint: queries exceeding `max_journey_time` are filtered out.
15. RT-015 — `max_transfers` enforced: returned routes do not exceed max allowed transfers.

### Transfer rules & layovers (RT-016 — RT-035)
16. RT-016 — Minimum transfer time respected: transfers with insufficient layover are rejected.
17. RT-017 — Maximum layover time respected: routes with layovers > allowed max are excluded.
18. RT-018 — Transfer feasibility by platform: transfers requiring unrealistic platform jumps flagged or penalized.
19. RT-019 — Night-layover avoidance: when `avoid_night_layovers=true`, night transfers avoided.
20. RT-020 — Transfer continuity: arrival station of previous segment equals departure station of next segment.
21. RT-021 — Transfer quality scoring: transfers include `facilities_score` and `safety_score` metadata.
22. RT-022 — Transfer time distribution presented: `get_transfer_durations()` matches transfer metadata.
23. RT-023 — Transfers count accuracy: number of transfers reported equals segments-1.
24. RT-024 — Cross-platform transfer edge case: transfers with minimal walking time still valid if >= min_transfer_time.
25. RT-025 — Transfer feasibility with delays: transfer remains feasible when incoming train delayed within tolerance.
26. RT-026 — Minimum-connection-time variable per station: station-specific min transfer honored.
27. RT-027 — Transfer removed when transfer station is closed (disruption): route updated accordingly.
28. RT-028 — Transfer prioritization by comfort/safety weight: routes can prioritize safer transfers when weights set.
29. RT-029 — Transfers for diverted trains: transitional transfer connections used when trains diverted.
30. RT-030 — Multi-transfer path validity: routes with multiple transfers validated end-to-end.
31. RT-031 — Transfer duration rounding: reported minutes are integer-rounded and consistent.
32. RT-032 — Transfer across agencies: multi-agency transfers allowed when supported.
33. RT-033 — Transfer between different modes (train→bus): included in multi-modal engine results.
34. RT-034 — Transfer time tolerances under daylight-saving switches: transfer validity across DST boundary.
35. RT-035 — Transfer suggestions include walking time estimate where data available.

### Time-dependent behavior & scheduling (RT-036 — RT-053)
36. RT-036 — Respect `departure_time` constraint: searches for earliest-after-departure return correct options.
37. RT-037 — Respect `arrival_by` constraint (if supported): routes arriving before requested time.
38. RT-038 — Overnight trains handling: overnight spans calculate correct date rollover for arrival time.
39. RT-039 — Calendar/date exceptions: services with calendar date exceptions honored (CalendarDate entries).
40. RT-040 — Weekend/weekday schedule variations: search uses weekday-specific timetables.
41. RT-041 — Seasonal schedules (festival/peak months): peak-season service changes reflected in results.
42. RT-042 — Frequency/headway model: high-frequency services produce more departure options.
43. RT-043 — Time-window queries: search within a departure time window returns expected options.
44. RT-044 — Late-night boundary cutoffs: services past midnight handled as next-day departures.
45. RT-045 — Minimum days-to-travel validation: prevent bookings for past dates.
46. RT-046 — Multi-day itineraries: long journeys crossing midnight/day boundaries compute durations correctly.
47. RT-047 — Time-precision: seconds-level schedule differences handled consistently.
48. RT-048 — Scheduled vs cached schedules: updates to timetable propagate after reload-graph.
49. RT-049 — Start-of-service / end-of-service edge cases: searches on service start/end dates handled.
50. RT-050 — Early-morning transient service changes handled (temporary timetable overrides).
51. RT-051 — Search across DST transition yields consistent absolute times.
52. RT-052 — Respect user `date` vs `return_date` in circular/multi-city searches.
53. RT-053 — Handling of `days_to_travel` feature when building ML features.

### Real-time updates & graph mutation (RT-054 — RT-071)
54. RT-054 — Delay application updates routes: after applying a delay, affected routes reflect increased arrival/departure times.
55. RT-055 — Cancellation removes affected segments: canceled trains do not appear in route options.
56. RT-056 — Partial cancellation handled: canceled stations removed but unaffected segments preserved.
57. RT-057 — Occupancy update influences ranking: high occupancy penalizes route ranking when enabled.
58. RT-058 — Platform change events do not break route validity if transfer time still feasible.
59. RT-059 — Graph refresh endpoint (`/api/admin/reload-graph`) reloads engine and changes are visible.
60. RT-060 — Bulk updates (bulk-update) apply atomically where possible and trigger cache invalidation.
61. RT-061 — External NTES/GPS updates processed by poller and reflected in route search results.
62. RT-062 — Real-time simulated delays for search previews are deterministic for same seed.
63. RT-063 — Realtime updates preserve route-id stability where possible (unless route structure changes).
64. RT-064 — In-flight search requests during graph mutation either return old results or fail gracefully.
65. RT-065 — Invalidation of cached routes when a train affected: cached entries for impacted origin/destination removed.
66. RT-066 — Eventual consistency: after update, caches and graph converge within acceptable window.
67. RT-067 — Re-route suggestion: when a booked train cancelled, alternative route suggestions provided.
68. RT-068 — Apply delay to multi-segment trip updates all segments consistently.
69. RT-069 — Real-time delta update logs emitted for observability.
70. RT-070 — Rate of polling external sources controlled; safety against thrashing the graph.
71. RT-071 — Applying contradictory updates (delay+cancel) resolved deterministically.

### Caching, TTL & consistency (RT-072 — RT-085)
72. RT-072 — Cache hit returns same structure as computed result.
73. RT-073 — Cache miss triggers engine computation and subsequent cache set.
74. RT-074 — Cache key includes relevant query params (date, class, max_transfers).
75. RT-075 — Cache TTL respected: expired cache forces recompute.
76. RT-076 — Manual cache invalidation via admin endpoints clears cached results.
77. RT-077 — LRU/eviction behavior under memory pressure (multi-layer cache).
78. RT-078 — Cache doesn't return stale routes after cancellations/delays (invalidation test).
79. RT-079 — Cache consistency across multi-layer (in-memory + Redis) layers.
80. RT-080 — Cached fare details updated when fare engine changes (cache-busting).
81. RT-081 — Cache warm-up behavior: pre-warmed popular station pairs return faster.
82. RT-082 — Partial cache keys (different class/quotas) do not collide.
83. RT-083 — Cache TTL override via config respected (Config values applied).
84. RT-084 — High-concurrency cache stampede protection (single-flight style) under load.
85. RT-085 — Cache serialization/deserialization retains numeric precision for times/fare.

### Scoring, ranking & ML integration (RT-086 — RT-101)
86. RT-086 — Multi-objective scoring uses configured weights (time/cost/comfort/safety).
87. RT-087 — Changing weight priorities immediately affects route order.
88. RT-088 — ML re-ranking applied when model is active (`route_ranking_predictor`).
89. RT-089 — Personalization (past bookings) modifies ranking when user context provided.
90. RT-090 — Score tie-breakers deterministic and stable.
91. RT-091 — Score normalization across routes with different lengths works correctly.
92. RT-092 — ML model metadata (feature importances) logged with predictions.
93. RT-093 — Scoring includes transfer penalties and comfort adjustments.
94. RT-094 — Price-sensitive ranking favors cheaper options when requested by user preference.
95. RT-095 — Safety-prioritized search returns routes with higher safety_score.
96. RT-096 — Score outliers filtered or presented with explanation (if enabled).
97. RT-097 — When ML service unavailable, fallback to heuristic ranking used.
98. RT-098 — Model A/B experiment toggles affect returned routes (split testing validation).
99. RT-099 — Ranking reproducibility: same inputs + model version -> same ordered results.
100. RT-100 — ML features derived from search events present in `route_features` DB for training.
101. RT-101 — ML-based confirmation probability (for waitlist) approximates observed promotion rates.

### Personalization, user context & preferences (RT-102 — RT-115)
102. RT-102 — `preferred_class` filters/boosts routes matching user preference.
103. RT-103 — Loyalty tier influences ranking and fare display where applicable.
104. RT-104 — Accessibility preference (avoid stairs) filters transfer stations accordingly.
105. RT-105 — Women's safety priority surfaces safer transfer options.
106. RT-106 — Recent user history biases route ranking (frequent routes first).
107. RT-107 — Preferred departure windows honored (morning/evening preferences).
108. RT-108 — Passenger-type concessions applied in fare calculations (senior, child).
109. RT-109 — Multi-passenger group preference (adjacent berths) affects seat suggestion metadata.
110. RT-110 — User-specific blackout dates (travel restrictions) respected in results.
111. RT-111 — Preference to minimize transfers returns 0- or 1-transfer routes when available.
112. RT-112 — Push personalized notifications for better options when available (analytics flow).
113. RT-113 — Saved favorite stations are used as `source` suggestion shortcuts.
114. RT-114 — Geo-location preference yields nearby-station routing and increased relevance.
115. RT-115 — Opt-out of ML personalization returns neutral ranking.

### Fare, classes & pricing (RT-116 — RT-127)
116. RT-116 — Fare breakdown presence: base fare, GST, discounts, cancellation charges present.
117. RT-117 — Concession discounts applied correctly for specified passenger types.
118. RT-118 — Tatkal pricing/availability indicated for routes supporting tatkal.
119. RT-119 — Class preference (AC/SL/etc.) filters route seat availability metadata.
120. RT-120 — Price range calculation (min/max/avg) accurate across segments.
121. RT-121 — Promo/coupon integration (if present) reflected in final price preview.
122. RT-122 — Fare rounding rules respected (currency precision).
123. RT-123 — Price-per-km calculation (used by ML features) consistent with distance.
124. RT-124 — Fare changes (dynamic pricing) reflected after price engine reload.
125. RT-125 — Booking unlock payment vs full booking price differentiation correct.
126. RT-126 — Refund/cancellation charges surfaced in route detail where applicable.
127. RT-127 — Commission/partner-affiliate breakdown returned for partner routes.

### Seat availability, inventory & waitlist (RT-128 — RT-139)
128. RT-128 — Availability flag included in each route; `available_seats` accurate.
129. RT-129 — Segment overlap allocation logic prevents double-allocation of seats.
130. RT-130 — Waitlist position returned when seats insufficient.
131. RT-131 — Confirmation probability estimate included and within [0,1].
132. RT-132 — Seat quota-type filtering returns correct allocations per quota.
133. RT-133 — Release/hold seat TTL behavior respected for held-but-unpaid bookings.
134. RT-134 — Waitlist promotion triggers notify alternative route availability.
135. RT-135 — Inventory cache invalidation after booking updates availability for subsequent searches.
136. RT-136 — Overbooked scenarios handled gracefully (no negative available seats).
137. RT-137 — Coach-class seat maps (if provided) align with allocation results.
138. RT-138 — Bulk seat allocation tested for multi-passenger group seating.
139. RT-139 — Seat-lock race conditions: concurrent holds do not oversell seats.

### Multi-modal & journey reconstruction (RT-140 — RT-151)
140. RT-140 — Multi-modal routes include valid bus/train/flight legs where available.
141. RT-141 — Integrated journey reconstruction returns complete `segments` and `fare_details`.
142. RT-142 — Circular journey requires `return_date` and returns outward+return legs.
143. RT-143 — Multi-city itinerary supports sequential legs and date mapping.
144. RT-144 — Mode-change transfer allowances and minimum transfer times applied.
145. RT-145 — Walk-time connectors considered in multimodal transfer feasibility.
146. RT-146 — Inter-modal price aggregation correct across legs.
147. RT-147 — Journey reconstruction tolerates small gaps in schedule data (best-effort).
148. RT-148 — Reconstruction uses GTFS-like stop-times accurately per trip segment.
149. RT-149 — Multi-modal ranking includes commission-bias where configured.
150. RT-150 — Suggested interchanges include platform & minimum connection time metadata.
151. RT-151 — Journey-level amenities (overnight, meal) surfaced in reconstructed result.

### Edge cases, validation & input hygiene (RT-152 — RT-166)
152. RT-152 — Same source and destination returns validation error.
153. RT-153 — Invalid station names return suggestions (fuzzy matching).
154. RT-154 — Short codes vs full names both accepted as station identifiers.
155. RT-155 — Missing required fields => HTTP 400 with descriptive message.
156. RT-156 — Excessively long query strings rejected or truncated safely.
157. RT-157 — Non-ASCII / Unicode station names handled correctly.
158. RT-158 — Searches for discontinued routes return useful message or alternatives.
159. RT-159 — Requests outside service date range handled gracefully.
160. RT-160 — Negative numeric parameter validation (passengers, radius) rejected.
161. RT-161 — Floating point coordinates validated for `nearby` station queries.
162. RT-162 — Partial station matches return prioritized suggestions.
163. RT-163 — Ambiguous station pairs require disambiguation (error/suggestions).
164. RT-164 — Input with timezone offset normalized correctly for date/time.
165. RT-165 — Parameter injection attempts sanitized (no SQL injection in station search)
166. RT-166 — Extremely large `max_transfers` requests sanitized/limited.

### Performance, scale & load (RT-167 — RT-178)
167. RT-167 — Single-query latency meets target (e.g., < 50ms for simple single-leg) under baseline.
168. RT-168 — Complex multi-transfer P95 latency under target (e.g., < 50ms P95 for typical queries).
169. RT-169 — Throughput: engine sustains 10k req/sec in stress benchmark (or documented throughput test).
170. RT-170 — Concurrent bookings/searches do not deadlock the route engine.
171. RT-171 — Memory usage under heavy load remains within configured limits.
172. RT-172 — Threadpool/async executor saturation handled gracefully (queueing/backpressure).
173. RT-173 — Cache warming reduces cold-start latency for popular origin/destination pairs.
174. RT-174 — Large-area `nearby` station queries scale (limit enforcement applies).
175. RT-175 — Long-running route computations timeout and return partial/failure safely.
176. RT-176 — High fan-out notifications (route change events) do not overwhelm worker.
177. RT-177 — Rate limiting under extreme burst prevents service collapse.
178. RT-178 — Load tests validate side-effects (DB, cache) remain consistent.

### API contract, schema & backward compatibility (RT-179 — RT-188)
179. RT-179 — OpenAPI paths documented and match actual responses.
180. RT-180 — Backwards-compatible stations endpoint (`/api/stations/search`) remains functional.
181. RT-181 — Adding optional fields is non-breaking for existing clients.
182. RT-182 — Deprecation headers provided for endpoints scheduled for removal.
183. RT-183 — Error codes standardized across endpoints (400/404/500 consistency).
184. RT-184 — Rate-limit response includes Retry-After header when applicable.
185. RT-185 — WebSocket messages follow expected JSON schema for SOS/updates.
186. RT-186 — API versioning for integrated-search `/api/v2` maintained.
187. RT-187 — Response field renaming triggers clear migration guidance in docs.
188. RT-188 — Contract tests validate sample payloads in `tests/` match real outputs.

### Security, rate limiting & abuse protection (RT-189 — RT-196)
189. RT-189 — Rate limiter blocks abusive IPs after threshold; returns 429.
190. RT-190 — Auth-required endpoints reject missing/invalid tokens (401).
191. RT-191 — Sensitive fields (payment data) never returned in search responses.
192. RT-192 — Input validation prevents mass enumeration via station autocomplete (rate-limited).
193. RT-193 — Circuit breaker protects external AI provider calls (OpenRouter) from cascading failures.
194. RT-194 — Sensitive logs redaction: PII not present in route logs.
195. RT-195 — CORS policy allows only configured origins for dev/prod.
196. RT-196 — API throttling per API key/user enforces fair usage.

### Localization, internationalization & data quality (RT-197 — RT-202)
197. RT-197 — Station names with diacritics/Unicode return and match search queries.
198. RT-198 — Distances and fare units returned with locale-appropriate formatting where required.
199. RT-199 — Missing data fields in source DB gracefully handled (fallback values).
200. RT-200 — Data-quality metrics updated when route_features ingestion runs.
201. RT-201 — Station coordinates geospatial queries return correct nearest station.
202. RT-202 — Multilingual station aliases used in autocomplete suggestions.

### Fault tolerance, chaos & resilience (RT-203 — RT-210)
203. RT-203 — DB connection drop handled: readiness probe reports not-ready while maintaining safe failures.
204. RT-204 — Redis cache outage falls back to in-memory cache without returning incorrect results.
205. RT-205 — Partial graph load: engine rejects requests requiring unloaded partitions with 503.
206. RT-206 — Worker restart preserves idempotent operations (reconciliation worker resumes safely).
207. RT-207 — Graceful shutdown drains running queries and persists cache/metrics.
208. RT-208 — Simulate malformed external update payloads are rejected and logged.
209. RT-209 — Retry/backoff behavior for transient failures (external APIs) implemented and tested.
210. RT-210 — Transactional sagas rollback cleanly on step failure (booking orchestration integration tests).

### Integration & end-to-end scenarios (RT-211 — RT-216)
211. RT-211 — End-to-end search → hold-seat → payment flow success scenario (happy path).
212. RT-212 — End-to-end search → delayed train re-route suggestion + user notification.
213. RT-213 — Search results include disruption alerts when `Disruption` entries active.
214. RT-214 — Webhook-triggered reconciliation updates search availability after payment captured.
215. RT-215 — Chat assistant tool-call triggers `RouteSearchTool` and returns matching route(s).
216. RT-216 — Admin ETL sync updates routes/stations and new data surfaces in searches.

### Metrics, logging & observability (RT-217 — RT-220)
217. RT-217 — `SEARCH_LATENCY_SECONDS` metric updated per search call with correct labels.
218. RT-218 — `SEARCH_REQUESTS_TOTAL` increments with success/failure labels.
219. RT-219 — Route-engine errors logged with correlation/request_id for debugging.
220. RT-220 — Prometheus `/metrics` endpoint exposes route-engine and ML pipeline metrics.

---

## Suggested priorities (recommended starter set)
- P0 (critical): RT-001, RT-002, RT-036, RT-054, RT-072, RT-086, RT-128, RT-167, RT-179, RT-189
- P1 (important): RT-015, RT-016, RT-041, RT-055, RT-074, RT-090, RT-103, RT-116, RT-171
- P2 (nice-to-have): remaining items

---

If you want, I can:
- Generate pytest skeletons for selected RT-IDs, or
- Create a prioritized JIRA/ZenHub-style task list, or
- Auto-convert these into Postman/Newman collection checks.

Reply with which option to do next ("pytest stubs", "task list", "postman checks", or "none").
