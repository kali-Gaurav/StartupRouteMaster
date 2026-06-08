Group 1: API Entry Point & Application Lifecycle
   * Responsibility: Initializes FastAPI, sets up middleware, manages startup/shutdown events, and acts as the 
     main entry point.
   * Key Files: backend/app.py, backend/dependencies.py, backend/config.py, backend/gunicorn_conf.py,
     backend/start.sh, backend/Procfile.

  Group 2: Core Routing Algorithms (RAPTOR/Turbo)
   * Responsibility: The "brains" of the pathfinding—calculating the fastest/most efficient rail routes.       
   * Key Files: backend/core/route_engine/raptor.py, backend/core/route_engine/turbo_router.py,
     backend/core/route_engine/ultra_turbo.py, backend/core/route_engine/csa_kernel.py.

  Group 3: Route Orchestration & Search Service
   * Responsibility: Orchestrates multiple search engines, handles multi-modal stitching, and provides the     
     high-level search API.
   * Key Files: backend/core/route_engine/orchestrator.py, backend/core/route_engine/engine.py,
     backend/core/route_engine/hybrid_engine.py, backend/services/search_service.py,
     backend/services/unified_search.py.

  Group 4: Routing Data & Graph Infrastructure
   * Responsibility: Manages the graph structures, timetable data providers, and transfer link builders        
     required for routing.
   * Key Files: backend/core/route_engine/graph.py, backend/core/route_engine/data_provider.py,
     backend/core/route_engine/transfer_graph_builder.py, backend/core/route_engine/zonal_loader.py,
     backend/core/routing/.

  Group 5: Authentication & User Security
   * Responsibility: Manages user login, registration, JWT token handling, and Supabase auth integration.      
   * Key Files: backend/core/auth/, backend/api/auth.py, backend/services/user_service.py,
     backend/core/middleware/auth.py.

  Group 6: Booking & Ticket Management
   * Responsibility: Handles the lifecycle of a ticket booking, from reservation to issuance and PNR
     management.
   * Key Files: backend/api/bookings.py, backend/services/booking_service.py,
     backend/services/agent_booking_service.py, backend/schemas/booking.py, backend/services/pnr_service.py.   

  Group 7: Payment Processing & Reconciliation
   * Responsibility: Integrates with payment gateways, handles UPI/VPA services, refunds, and bank
     reconciliation.
   * Key Files: backend/api/payments.py, backend/services/payment_service.py,
     backend/services/refund_service.py, backend/services/reconciliation_service.py,
     backend/api/bank_webhooks.py.

  Group 8: Dynamic Pricing & Yield Management
   * Responsibility: Calculates real-time fares based on demand, dynamic pricing strategies, and yield
     optimization.
   * Key Files: backend/core/pricing/, backend/services/enhanced_pricing_service.py,
     backend/services/fare_calculator.py, backend/services/yield_management_engine.py,
     backend/core/route_engine/scoring.py.

  Group 9: Seat Inventory & Availability
   * Responsibility: Tracks real-time seat availability, manages quotas (like Tatkal), and performs seat       
     allocation.
   * Key Files: backend/services/inventory_service.py, backend/services/seat_availability.py,
     backend/services/advanced_seat_allocation_engine.py, backend/services/seat_verification.py.

  Group 10: AI Chatbot & Natural Language Processing (NLP)
   * Responsibility: Powers the intelligent chat interface, parses user intent, and dispatches chat actions.   
   * Key Files: backend/api/chat.py, backend/services/nlp_parser.py,
     backend/services/chat_action_dispatcher.py, backend/api/telegram_bot.py.

  Group 11: Machine Learning Models & Predictors
   * Responsibility: Hosts trained models for delay prediction, cancellation probability, and route ranking.   
   * Key Files: backend/core/ml_models/, backend/models/*.pkl, backend/services/delay_predictor.py,
     backend/services/cancellation_predictor.py, backend/services/route_ranking_predictor.py.

  Group 12: Real-time Data Ingestion & Live Status
   * Responsibility: Processes incoming real-time events (train delays, status updates) and provides live      
     status APIs.
   * Key Files: backend/core/realtime_event_processor.py, backend/services/live_status_service.py,
     backend/api/realtime.py, backend/workers/realtime_ingest_worker.py.

  Group 13: Station & Hub Intelligence
   * Responsibility: Manages station metadata, quality scoring, hub detection, and station-specific searches.  
   * Key Files: backend/core/hubs.py, backend/core/route_engine/hub_scoring.py,
     backend/services/station_service.py, backend/services/station_search_service.py, backend/api/stations.py. 

  Group 14: SOS & Emergency Safety System
   * Responsibility: Mission-critical safety features including voice triage, SOS triggers, and emergency      
     coordination.
   * Key Files: backend/api/sos.py, backend/api/voice_triage.py, backend/services/emergency/,
     backend/workers/udp_safety_listener.py.

  Group 15: ETL Pipelines & Data Synchronization
   * Responsibility: Syncs data from external sources, imports GTFS feeds, and rebuilds the transit graph.     
   * Key Files: backend/etl/gtfs_master_importer.py, backend/etl/turbo_etl.py,
     backend/etl/sqlite_to_postgres.py, backend/etl/rebuild_transit_graph.py.

  Group 16: Scraper System (Data Acquisition)
   * Responsibility: Scrapy-based system for gathering live data from railway websites and external APIs.      
   * Key Files: backend/scraper/, backend/scraper/app.py, backend/scraper/scrapy.cfg.

  Group 17: Database Models & Migrations
   * Responsibility: Defines the relational database schema and manages versioned migrations with Alembic.     
   * Key Files: backend/database/, backend/alembic/, backend/alembic.ini, backend/schemas/base.py.

  Group 18: Multi-Layer Caching (Redis)
   * Responsibility: Manages the high-performance caching strategy, warming services, and Redis connection     
     logic.
   * Key Files: backend/core/redis.py, backend/services/multi_layer_cache.py,
     backend/services/cache_warming_service.py, backend/workers/warmup_worker.py.

  Group 19: Background Task Management (Celery)
   * Responsibility: Handles asynchronous tasks like email notifications, cleanup, and background data
     processing.
   * Key Files: backend/core/celery_app.py, backend/tasks/, backend/workers/worker_pool.py.

  Group 20: System Monitoring & Observability
   * Responsibility: Collects performance metrics, monitors resources, and provides health/status checks.      
   * Key Files: backend/core/metrics.py, backend/core/monitoring.py, backend/core/resource_monitor.py,
     backend/services/performance_monitor.py, backend/api/status.py.

  Group 21: Middleware & Request Interceptors
   * Responsibility: Custom logic for request rate limiting, performance tracking, and cross-cutting concerns. 
   * Key Files: backend/core/middleware/, backend/core/rate_limit.py.

  Group 22: Microservices & External Adapters
   * Responsibility: Interfaces for communicating with internal microservices and external partner APIs.       
   * Key Files: backend/microservices/, backend/adapters/, backend/services/routemaster_client.py.

  Group 23: Data Validation & Integrity
   * Responsibility: Ensures the correctness of routing results, fare data, and system-wide data integrity.    
   * Key Files: backend/core/validator/, backend/services/verification_engine.py,
     backend/services/fare_verification.py, backend/core/performance_validators.py.

  Group 24: Utilities & Core Data Structures
   * Responsibility: Shared helper functions, custom data types, and fundamental building blocks used across   
     the backend.
   * Key Files: backend/utils/, backend/core/data_structures.py, backend/core/utils.py,
     backend/core/base_engine.py.

  Group 25: Verification & Integration Testing
   * Responsibility: The suite of tests and scripts used to verify features in isolation and across the whole  
     system.
   * Key Files: backend/tests/, backend/verify_*.py, backend/test_*.py, backend/conftest.py.

  ---

  How to use this:
  Every time you want to work on a specific feature, pick a Group Number. All the logic related to that feature
  will be contained within those specific folders and files, allowing you to focus your thinking entirely on   
  that responsibility.