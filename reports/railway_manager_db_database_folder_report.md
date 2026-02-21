# Database Report for `railway_manager.db`

**Location:** `backend/database/railway_manager.db`

Generated automatically. Contains 47 tables.


## Table `trains_master`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| train_number | VARCHAR | 1 |  | 1 |

| train_name | VARCHAR | 0 |  | 0 |

| source | VARCHAR | 0 |  | 0 |

| destination | VARCHAR | 0 |  | 0 |

| days_of_run | JSON | 0 |  | 0 |

| type | VARCHAR | 0 |  | 0 |

| updated_at | DATETIME | 0 |  | 0 |


## Table `train_live_status`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| train_number | VARCHAR | 1 |  | 1 |

| current_station | VARCHAR | 0 |  | 0 |

| status | VARCHAR | 0 |  | 0 |

| delay_minutes | INTEGER | 0 |  | 0 |

| next_station | VARCHAR | 0 |  | 0 |

| eta_next | VARCHAR | 0 |  | 0 |

| last_updated_ts | DATETIME | 0 |  | 0 |


## Table `seat_availability`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 1 |  | 1 |

| train_number | VARCHAR | 0 |  | 0 |

| class_code | VARCHAR | 0 |  | 0 |

| quota | VARCHAR | 0 |  | 0 |

| availability_status | VARCHAR | 0 |  | 0 |

| fare | FLOAT | 0 |  | 0 |

| check_date | DATETIME | 0 |  | 0 |


## Table `schedule_change_log`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 1 |  | 1 |

| train_number | VARCHAR | 0 |  | 0 |

| detected_at | DATETIME | 0 |  | 0 |

| diff | JSON | 0 |  | 0 |

| resolved | BOOLEAN | 0 |  | 0 |

| notes | VARCHAR | 0 |  | 0 |


## Table `rma_alerts`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 1 |  | 1 |

| source | VARCHAR | 0 |  | 0 |

| train_number | VARCHAR | 0 |  | 0 |

| level | VARCHAR | 0 |  | 0 |

| message | VARCHAR | 0 |  | 0 |

| meta | JSON | 0 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |

| resolved | BOOLEAN | 0 |  | 0 |

| resolved_at | DATETIME | 0 |  | 0 |

| acknowledged_by | VARCHAR | 0 |  | 0 |


## Table `train_reliability_index`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 1 |  | 1 |

| train_number | VARCHAR | 0 |  | 0 |

| reliability_score | FLOAT | 0 |  | 0 |

| avg_extraction_confidence | FLOAT | 0 |  | 0 |

| schedule_drift_score | FLOAT | 0 |  | 0 |

| delay_probability | FLOAT | 0 |  | 0 |

| computed_at | DATETIME | 0 |  | 0 |

| window_minutes | INTEGER | 0 |  | 0 |


## Table `train_stations`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 1 |  | 1 |

| train_number | VARCHAR | 0 |  | 0 |

| station_code | VARCHAR | 0 |  | 0 |

| station_name | VARCHAR | 0 |  | 0 |

| sequence | INTEGER | 0 |  | 0 |

| arrival | VARCHAR | 0 |  | 0 |

| departure | VARCHAR | 0 |  | 0 |

| halt_minutes | INTEGER | 0 |  | 0 |

| distance_km | FLOAT | 0 |  | 0 |

| day_count | INTEGER | 0 |  | 0 |


## Table `alembic_version`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| version_num | VARCHAR(32) | 1 |  | 1 |


## Table `users`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| email | VARCHAR(255) | 1 |  | 0 |

| password_hash | VARCHAR(255) | 1 |  | 0 |

| phone_number | VARCHAR(20) | 0 |  | 0 |

| role | VARCHAR(50) | 0 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |


## Table `agency`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 1 |  | 1 |

| agency_id | VARCHAR(100) | 1 |  | 0 |

| name | VARCHAR(255) | 1 |  | 0 |

| url | VARCHAR(255) | 1 |  | 0 |

| timezone | VARCHAR(50) | 1 |  | 0 |

| language | VARCHAR(10) | 0 |  | 0 |


## Table `stops`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 1 |  | 1 |

| stop_id | VARCHAR(100) | 1 |  | 0 |

| code | VARCHAR(100) | 0 |  | 0 |

| name | VARCHAR(255) | 1 |  | 0 |

| city | VARCHAR(255) | 0 |  | 0 |

| state | VARCHAR(255) | 0 |  | 0 |

| latitude | FLOAT | 1 |  | 0 |

| longitude | FLOAT | 1 |  | 0 |

| geom | VARCHAR | 0 |  | 0 |

| location_type | INTEGER | 0 |  | 0 |

| parent_station_id | INTEGER | 0 |  | 0 |

| safety_score | FLOAT | 1 |  | 0 |

| is_major_junction | BOOLEAN | 1 |  | 0 |

| facilities_json | JSON | 1 |  | 0 |

| wheelchair_accessible | BOOLEAN | 1 |  | 0 |

| platform_count | INTEGER | 0 |  | 0 |

| distance_to_city_center_km | FLOAT | 0 |  | 0 |


## Table `calendar`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 1 |  | 1 |

| service_id | VARCHAR(100) | 1 |  | 0 |

| monday | BOOLEAN | 1 |  | 0 |

| tuesday | BOOLEAN | 1 |  | 0 |

| wednesday | BOOLEAN | 1 |  | 0 |

| thursday | BOOLEAN | 1 |  | 0 |

| friday | BOOLEAN | 1 |  | 0 |

| saturday | BOOLEAN | 1 |  | 0 |

| sunday | BOOLEAN | 1 |  | 0 |

| start_date | DATE | 1 |  | 0 |

| end_date | DATE | 1 |  | 0 |


## Table `calendar_dates`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 1 |  | 1 |

| service_id | VARCHAR(100) | 1 |  | 0 |

| date | DATE | 1 |  | 0 |

| exception_type | INTEGER | 1 |  | 0 |


## Table `realtime_data`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| event_type | VARCHAR(50) | 1 |  | 0 |

| entity_type | VARCHAR(50) | 1 |  | 0 |

| entity_id | VARCHAR(100) | 1 |  | 0 |

| data | JSON | 1 |  | 0 |

| timestamp | DATETIME | 1 |  | 0 |

| source | VARCHAR(100) | 1 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |


## Table `precalculated_routes`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| source | VARCHAR(255) | 1 |  | 0 |

| destination | VARCHAR(255) | 1 |  | 0 |

| segments | JSON | 1 |  | 0 |

| total_duration | VARCHAR(50) | 1 |  | 0 |

| total_cost | FLOAT | 1 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |


## Table `vehicles`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| vehicle_number | VARCHAR(50) | 1 |  | 0 |

| type | VARCHAR(50) | 1 |  | 0 |

| operator | VARCHAR(255) | 1 |  | 0 |

| capacity | INTEGER | 0 |  | 0 |


**Sample rows:**

```
('04d7ead7-9461-4341-8b52-346e8b529883', '10103', 'train', 'Indian Railways', None)
```
```
('12c09bf2-0938-4cea-b2ec-1e7292e7d96a', '10104', 'train', 'Indian Railways', None)
```
```
('0655c711-1281-4688-9dc5-162b442fa3eb', '10111', 'train', 'Indian Railways', None)
```
```
('c4930e3b-820e-460e-80cf-452e549374d2', '10112', 'train', 'Indian Railways', None)
```
```
('97cb3a47-cd35-4cce-aef1-b1498446177f', '10215', 'train', 'Indian Railways', None)
```

## Table `stations`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| name | VARCHAR(255) | 1 |  | 0 |

| city | VARCHAR(255) | 1 |  | 0 |

| latitude | FLOAT | 1 |  | 0 |

| longitude | FLOAT | 1 |  | 0 |

| geom | VARCHAR | 0 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |


**Sample rows:**

```
('dfa20805-6c67-430c-a3b6-5770a4c58562', 'Ambika Bhawa', 'AMBIKA', 0.0, 0.0, None, '2026-02-19 17:25:51.693557')
```
```
('9949a612-9ca3-406e-a24f-a32726e1bade', 'Amb  Andaura', 'Madurai', 31.6703143, 76.1102063, 'POINT(76.1102063 31.6703143)', '2026-02-19 17:25:51.699608')
```
```
('f72e5a75-7409-4967-a36d-150208ffaee1', 'Angar', 'Hanumangarh', 17.9283836, 75.60829919999999, 'POINT(75.60829919999999 17.9283836)', '2026-02-19 17:25:51.704116')
```
```
('d07c1956-0d8c-4bad-a629-baa02537bfea', 'Itehar', 'Maihar', 26.5619396, 78.671942, 'POINT(78.671942 26.5619396)', '2026-02-19 17:25:51.709248')
```
```
('646d5135-1f10-45b4-9a21-f2cfc8e8f553', 'Amlai', 'Pali', 23.1727635, 81.5932123, 'POINT(81.5932123 23.1727635)', '2026-02-19 17:25:51.715763')
```

## Table `time_index_keys`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 1 |  | 1 |

| entity_type | VARCHAR(50) | 1 |  | 0 |

| entity_id | VARCHAR(255) | 1 |  | 0 |


**Sample rows:**

```
(1, 'vehicle', '04d7ead7-9461-4341-8b52-346e8b529883')
```
```
(2, 'vehicle', '12c09bf2-0938-4cea-b2ec-1e7292e7d96a')
```
```
(3, 'vehicle', '0655c711-1281-4688-9dc5-162b442fa3eb')
```
```
(4, 'vehicle', 'c4930e3b-820e-460e-80cf-452e549374d2')
```
```
(5, 'vehicle', '97cb3a47-cd35-4cce-aef1-b1498446177f')
```

## Table `stations_master`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| station_code | VARCHAR(10) | 1 |  | 1 |

| station_name | VARCHAR(255) | 1 |  | 0 |

| city | VARCHAR(255) | 0 |  | 0 |

| state | VARCHAR(255) | 0 |  | 0 |

| latitude | FLOAT | 0 |  | 0 |

| longitude | FLOAT | 0 |  | 0 |

| is_junction | BOOLEAN | 0 |  | 0 |


## Table `gtfs_routes`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 1 |  | 1 |

| route_id | VARCHAR(100) | 1 |  | 0 |

| agency_id | INTEGER | 1 |  | 0 |

| short_name | VARCHAR(50) | 0 |  | 0 |

| long_name | VARCHAR(255) | 1 |  | 0 |

| description | VARCHAR(512) | 0 |  | 0 |

| url | VARCHAR(255) | 0 |  | 0 |

| route_type | INTEGER | 1 |  | 0 |


## Table `commission_tracking`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| user_id | VARCHAR(36) | 1 |  | 0 |

| source | VARCHAR(255) | 1 |  | 0 |

| destination | VARCHAR(255) | 1 |  | 0 |

| travel_date | DATE | 0 |  | 0 |

| partner | VARCHAR(100) | 1 |  | 0 |

| commission_rate | FLOAT | 1 |  | 0 |

| tracking_id | VARCHAR(64) | 1 |  | 0 |

| redirect_url | TEXT | 1 |  | 0 |

| status | VARCHAR(50) | 0 |  | 0 |

| redirected_at | DATETIME | 0 |  | 0 |

| route_id | VARCHAR(36) | 0 |  | 0 |


## Table `rl_feedback_logs`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| user_id | VARCHAR(36) | 0 |  | 0 |

| session_id | VARCHAR(36) | 1 |  | 0 |

| action | VARCHAR(100) | 1 |  | 0 |

| context | JSON | 1 |  | 0 |

| reward | FLOAT | 1 |  | 0 |

| timestamp | DATETIME | 1 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |


## Table `station_facilities`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| stop_id | INTEGER | 1 |  | 0 |

| wifi_available | BOOLEAN | 0 |  | 0 |

| lounge_available | BOOLEAN | 0 |  | 0 |

| food_available | BOOLEAN | 0 |  | 0 |

| wheelchair_accessible | BOOLEAN | 0 |  | 0 |

| parking_available | BOOLEAN | 0 |  | 0 |

| baby_care | BOOLEAN | 0 |  | 0 |

| medical_clinic | BOOLEAN | 0 |  | 0 |

| lost_found | BOOLEAN | 0 |  | 0 |

| cloakroom | BOOLEAN | 0 |  | 0 |

| opening_time | TIME | 0 |  | 0 |

| closing_time | TIME | 0 |  | 0 |

| cctv_available | BOOLEAN | 0 |  | 0 |

| police_presence | BOOLEAN | 0 |  | 0 |

| women_waiting_room | BOOLEAN | 0 |  | 0 |

| emergency_contact | VARCHAR(20) | 0 |  | 0 |

| contact_email | VARCHAR(255) | 0 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |

| updated_at | DATETIME | 0 |  | 0 |


## Table `station_departures`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| station_id | VARCHAR(36) | 1 |  | 0 |

| bucket_start_minute | INTEGER | 1 |  | 0 |

| bitmap | BLOB | 1 |  | 0 |

| trips_count | INTEGER | 1 |  | 0 |

| created_at | DATETIME | 1 |  | 0 |


## Table `route_search_logs`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| user_id | VARCHAR(36) | 0 |  | 0 |

| src | VARCHAR(255) | 1 |  | 0 |

| dst | VARCHAR(255) | 1 |  | 0 |

| date | DATE | 1 |  | 0 |

| routes_shown | JSON | 1 |  | 0 |

| route_clicked | VARCHAR(36) | 0 |  | 0 |

| booking_success | BOOLEAN | 0 |  | 0 |

| latency_ms | FLOAT | 1 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |


## Table `train_states`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| trip_id | INTEGER | 1 |  | 0 |

| train_number | VARCHAR(50) | 1 |  | 0 |

| current_station_id | INTEGER | 0 |  | 0 |

| next_station_id | INTEGER | 0 |  | 0 |

| delay_minutes | INTEGER | 1 |  | 0 |

| status | VARCHAR(20) | 1 |  | 0 |

| platform_number | VARCHAR(10) | 0 |  | 0 |

| last_updated | DATETIME | 1 |  | 0 |

| estimated_arrival | DATETIME | 0 |  | 0 |

| estimated_departure | DATETIME | 0 |  | 0 |

| occupancy_rate | FLOAT | 1 |  | 0 |

| cancelled_stations | JSON | 1 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |

| updated_at | DATETIME | 0 |  | 0 |


## Table `pnr_records`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| pnr_number | VARCHAR(10) | 1 |  | 0 |

| user_id | VARCHAR(36) | 1 |  | 0 |

| travel_date | DATE | 1 |  | 0 |

| total_passengers | INTEGER | 1 |  | 0 |

| total_fare | NUMERIC(10, 2) | 1 |  | 0 |

| booking_status | VARCHAR(9) | 1 |  | 0 |

| payment_status | VARCHAR(20) | 1 |  | 0 |

| payment_id | VARCHAR(100) | 0 |  | 0 |

| segments_json | JSON | 1 |  | 0 |

| cancelled_at | DATETIME | 0 |  | 0 |

| refund_amount | NUMERIC(10, 2) | 0 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |

| updated_at | DATETIME | 0 |  | 0 |


## Table `booking_locks`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| lock_key | VARCHAR(200) | 1 |  | 0 |

| user_id | VARCHAR(36) | 1 |  | 0 |

| session_id | VARCHAR(100) | 1 |  | 0 |

| acquired_at | DATETIME | 1 |  | 0 |

| expires_at | DATETIME | 1 |  | 0 |

| ttl_seconds | INTEGER | 1 |  | 0 |

| lock_type | VARCHAR(20) | 1 |  | 0 |

| resource_id | VARCHAR(100) | 1 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |


## Table `trips`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 1 |  | 1 |

| trip_id | VARCHAR(255) | 1 |  | 0 |

| route_id | INTEGER | 1 |  | 0 |

| service_id | VARCHAR(100) | 1 |  | 0 |

| headsign | VARCHAR(255) | 0 |  | 0 |

| direction_id | INTEGER | 0 |  | 0 |

| bike_allowed | BOOLEAN | 1 |  | 0 |

| wheelchair_accessible | BOOLEAN | 1 |  | 0 |

| trip_headsign | VARCHAR(255) | 0 |  | 0 |


## Table `transfers`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 1 |  | 1 |

| from_stop_id | INTEGER | 1 |  | 0 |

| to_stop_id | INTEGER | 1 |  | 0 |

| route_id | INTEGER | 0 |  | 0 |

| transfer_type | INTEGER | 1 |  | 0 |

| min_transfer_time | INTEGER | 1 |  | 0 |


## Table `route_shapes`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| route_id | INTEGER | 1 |  | 0 |

| shape_id | VARCHAR(100) | 1 |  | 0 |

| geometry | VARCHAR | 0 |  | 0 |

| sequence | INTEGER | 1 |  | 0 |

| distance_traveled | FLOAT | 1 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |


## Table `cancellation_rules`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| route_id | INTEGER | 0 |  | 0 |

| hours_before_departure | INTEGER | 1 |  | 0 |

| refund_percentage | FLOAT | 1 |  | 0 |

| is_active | BOOLEAN | 0 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |


## Table `stop_times`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 1 |  | 1 |

| trip_id | INTEGER | 1 |  | 0 |

| stop_id | INTEGER | 1 |  | 0 |

| arrival_time | TIME | 1 |  | 0 |

| departure_time | TIME | 1 |  | 0 |

| stop_sequence | INTEGER | 1 |  | 0 |

| cost | FLOAT | 1 |  | 0 |

| pickup_type | INTEGER | 1 |  | 0 |

| drop_off_type | INTEGER | 1 |  | 0 |

| platform_number | VARCHAR(10) | 0 |  | 0 |


## Table `bookings`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| pnr_number | VARCHAR(10) | 1 |  | 0 |

| user_id | VARCHAR(36) | 1 |  | 0 |

| travel_date | DATE | 1 |  | 0 |

| booking_status | VARCHAR(50) | 1 |  | 0 |

| amount_paid | FLOAT | 1 |  | 0 |

| booking_details | JSON | 1 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |

| updated_at | DATETIME | 0 |  | 0 |

| route_id | VARCHAR(36) | 0 |  | 0 |

| trip_id | INTEGER | 0 |  | 0 |

| payment_status | VARCHAR(50) | 0 |  | 0 |


## Table `disruptions`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| disruption_type | VARCHAR(50) | 1 |  | 0 |

| description | TEXT | 0 |  | 0 |

| start_time | DATETIME | 0 |  | 0 |

| end_time | DATETIME | 0 |  | 0 |

| status | VARCHAR(50) | 0 |  | 0 |

| created_by_id | VARCHAR(36) | 0 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |

| gtfs_route_id | INTEGER | 0 |  | 0 |

| trip_id | INTEGER | 0 |  | 0 |

| stop_id | INTEGER | 0 |  | 0 |


## Table `frequencies`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| trip_id | INTEGER | 1 |  | 0 |

| start_time | TIME | 1 |  | 0 |

| end_time | TIME | 1 |  | 0 |

| headway_secs | INTEGER | 1 |  | 0 |

| exact_times | BOOLEAN | 0 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |


## Table `segments`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| source_station_id | VARCHAR(36) | 1 |  | 0 |

| dest_station_id | VARCHAR(36) | 1 |  | 0 |

| vehicle_id | VARCHAR(36) | 0 |  | 0 |

| trip_id | INTEGER | 0 |  | 0 |

| transport_mode | VARCHAR(50) | 1 |  | 0 |

| departure_time | TIME | 1 |  | 0 |

| arrival_time | TIME | 1 |  | 0 |

| arrival_day_offset | INTEGER | 0 |  | 0 |

| duration_minutes | INTEGER | 1 |  | 0 |

| distance_km | FLOAT | 0 |  | 0 |

| cost | FLOAT | 1 |  | 0 |

| operating_days | VARCHAR(7) | 1 |  | 0 |


**Sample rows:**

```
('b71a71ab-3560-4b5a-a72f-116ae4466b5a', 'b0ece6cd-ee1c-45c5-b83f-2d1cbe5a6080', 'a00bc90d-6c83-4d18-b8b4-71290f3e8fae', '04d7ead7-9461-4341-8b52-346e8b529883', None, 'train', '07:10:00.000000', '07:22:00.000000', 0, 12, 0.0, 150.0, '0001000')
```
```
('cbafdc10-df86-4d64-a109-dec699323f6b', 'a00bc90d-6c83-4d18-b8b4-71290f3e8fae', 'd88cdd83-ae60-4091-9858-350e13ee86ce', '04d7ead7-9461-4341-8b52-346e8b529883', None, 'train', '07:25:00.000000', '07:46:00.000000', 0, 21, 0.0, 150.0, '0001000')
```
```
('a0c45542-653f-41d3-a6f6-67f8ad7a8e62', 'd88cdd83-ae60-4091-9858-350e13ee86ce', 'f1371c32-0f3f-44ce-8a70-64316d506ebd', '04d7ead7-9461-4341-8b52-346e8b529883', None, 'train', '07:50:00.000000', '08:25:00.000000', 0, 35, 0.0, 150.0, '0001000')
```
```
('a0d34825-5b80-4923-8db0-5ab2532a097a', 'f1371c32-0f3f-44ce-8a70-64316d506ebd', '7709339a-58de-4594-a44d-971b08a4e7cf', '04d7ead7-9461-4341-8b52-346e8b529883', None, 'train', '08:30:00.000000', '10:34:00.000000', 0, 124, 107.0, 150.0, '0001000')
```
```
('18ab5fc8-96c3-4755-b0ce-c114ef6c3e57', '7709339a-58de-4594-a44d-971b08a4e7cf', 'd861b0be-ddf7-45b3-94c0-9263773bbade', '04d7ead7-9461-4341-8b52-346e8b529883', None, 'train', '10:35:00.000000', '11:26:00.000000', 0, 51, 68.0, 150.0, '0001000')
```

## Table `coaches`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| train_id | INTEGER | 1 |  | 0 |

| coach_number | VARCHAR(10) | 1 |  | 0 |

| coach_class | VARCHAR(3) | 1 |  | 0 |

| total_seats | INTEGER | 1 |  | 0 |

| base_fare_multiplier | FLOAT | 1 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |

| updated_at | DATETIME | 0 |  | 0 |


## Table `passenger_details`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| booking_id | VARCHAR(36) | 1 |  | 0 |

| full_name | VARCHAR(255) | 1 |  | 0 |

| age | INTEGER | 1 |  | 0 |

| gender | VARCHAR(10) | 1 |  | 0 |

| phone_number | VARCHAR(20) | 0 |  | 0 |

| email | VARCHAR(255) | 0 |  | 0 |

| document_type | VARCHAR(50) | 0 |  | 0 |

| document_number | VARCHAR(50) | 0 |  | 0 |

| coach_number | VARCHAR(10) | 0 |  | 0 |

| seat_number | VARCHAR(10) | 0 |  | 0 |

| berth_type | VARCHAR(20) | 0 |  | 0 |

| concession_type | VARCHAR(50) | 0 |  | 0 |

| concession_discount | FLOAT | 1 |  | 0 |

| meal_preference | VARCHAR(20) | 0 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |

| updated_at | DATETIME | 0 |  | 0 |

| pnr_id | VARCHAR(36) | 1 |  | 0 |

| name | VARCHAR(100) | 1 |  | 0 |

| berth_preference | VARCHAR(10) | 0 |  | 0 |

| seat_type | VARCHAR(10) | 0 |  | 0 |

| status | VARCHAR(9) | 1 |  | 0 |


## Table `seat_inventory`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| travel_date | DATE | 1 |  | 0 |

| seats_available | INTEGER | 1 |  | 0 |

| last_reconciled_at | DATETIME | 0 |  | 0 |

| stop_time_id | INTEGER | 1 |  | 0 |

| trip_id | INTEGER | 1 |  | 0 |

| segment_from_stop_id | INTEGER | 1 |  | 0 |

| segment_to_stop_id | INTEGER | 1 |  | 0 |

| date | DATE | 1 |  | 0 |

| quota_type | VARCHAR(15) | 1 |  | 0 |

| total_seats | INTEGER | 1 |  | 0 |

| available_seats | INTEGER | 1 |  | 0 |

| booked_seats | INTEGER | 1 |  | 0 |

| blocked_seats | INTEGER | 1 |  | 0 |

| current_waitlist_position | INTEGER | 1 |  | 0 |

| rac_count | INTEGER | 1 |  | 0 |

| last_updated | DATETIME | 0 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |


## Table `reviews`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| user_id | VARCHAR(36) | 1 |  | 0 |

| booking_id | VARCHAR(36) | 1 |  | 0 |

| rating | INTEGER | 1 |  | 0 |

| comment | TEXT | 0 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |


## Table `payments`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| booking_id | VARCHAR(36) | 0 |  | 0 |

| razorpay_order_id | VARCHAR(255) | 0 |  | 0 |

| razorpay_payment_id | VARCHAR(255) | 0 |  | 0 |

| status | VARCHAR(50) | 0 |  | 0 |

| amount | FLOAT | 1 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |

| updated_at | DATETIME | 0 |  | 0 |


## Table `waiting_list`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| booking_id | VARCHAR(36) | 1 |  | 0 |

| position | INTEGER | 1 |  | 0 |

| status | VARCHAR(50) | 1 |  | 0 |

| notification_sent | BOOLEAN | 0 |  | 0 |

| confirmed_at | DATETIME | 0 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |

| updated_at | DATETIME | 0 |  | 0 |


## Table `seats`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| coach_id | VARCHAR(36) | 1 |  | 0 |

| seat_number | VARCHAR(10) | 1 |  | 0 |

| seat_type | VARCHAR(10) | 1 |  | 0 |

| is_active | BOOLEAN | 1 |  | 0 |

| is_preferred | BOOLEAN | 1 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |


## Table `unlocked_routes`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| user_id | VARCHAR(36) | 1 |  | 0 |

| payment_id | VARCHAR(36) | 0 |  | 0 |

| unlocked_at | DATETIME | 0 |  | 0 |

| route_id | VARCHAR(36) | 0 |  | 0 |


## Table `quota_inventory`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| inventory_id | VARCHAR(36) | 1 |  | 0 |

| quota_type | VARCHAR(15) | 1 |  | 0 |

| allocated_seats | INTEGER | 1 |  | 0 |

| available_seats | INTEGER | 1 |  | 0 |

| max_allocation | INTEGER | 1 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |

| updated_at | DATETIME | 0 |  | 0 |


## Table `waitlist_queue`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| inventory_id | VARCHAR(36) | 1 |  | 0 |

| user_id | VARCHAR(36) | 1 |  | 0 |

| waitlist_position | INTEGER | 1 |  | 0 |

| booking_request_time | DATETIME | 1 |  | 0 |

| passengers_json | JSON | 1 |  | 0 |

| preferences_json | JSON | 0 |  | 0 |

| status | VARCHAR(9) | 1 |  | 0 |

| promoted_at | DATETIME | 0 |  | 0 |

| expired_at | DATETIME | 0 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |

| updated_at | DATETIME | 0 |  | 0 |
