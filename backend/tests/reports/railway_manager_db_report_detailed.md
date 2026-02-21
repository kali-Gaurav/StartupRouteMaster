# Database Report for `railway_manager.db`

**Location:** `backend/railway_manager.db`

Generated automatically. Contains 64 tables.


## Table `stations_master`

**Purpose:** This table stores records about `stations_master`. Each row represents a single stations master entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `station_code` (TEXT) – primary key.
- `station_name` (TEXT) (not null).
- `city` (TEXT) (not null).
- `state` (TEXT) (not null).
- `latitude` (REAL).
- `longitude` (REAL).
- `is_junction` (INTEGER) (not null); default `0`.
- `created_at` (TIMESTAMP); default `CURRENT_TIMESTAMP`.
- `geo_hash` (TEXT).

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| station_code | TEXT | 0 |  | 1 |

| station_name | TEXT | 1 |  | 0 |

| city | TEXT | 1 |  | 0 |

| state | TEXT | 1 |  | 0 |

| latitude | REAL | 0 |  | 0 |

| longitude | REAL | 0 |  | 0 |

| is_junction | INTEGER | 1 | 0 | 0 |

| created_at | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |

| geo_hash | TEXT | 0 |  | 0 |


**Sample rows:**

```
('SWV', 'Sawantwadi R', 'SAWANTWADI', 'Maharashtra', 15.9052627, 73.8213213, 0, '2026-01-27 18:30:00', 'tdu6rz')
```
```
('THVM', 'Thivim', 'THIVIM', 'Goa', 15.6299661, 73.8768379, 0, '2026-01-27 18:30:00', 'tdu8cj')
```
```
('KRMI', 'Karmali', 'Karauli', 'Goa', 15.490463, 73.9245664, 0, '2026-01-27 18:30:00', 'tdu845')
```
```
('MAO', 'Madgoan Jn.', 'Mohan', 'Goa', 15.2676769, 73.9707938, 1, '2026-01-27 18:30:00', 'tdswg5')
```
```
('KUDL', 'Kudal', 'KUDAL', 'Maharashtra', 16.0172218, 73.6779683, 0, '2026-01-27 18:30:00', 'tdu7he')
```

## Table `trains_master`

**Purpose:** This table stores records about `trains_master`. Each row represents a single trains master entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `train_no` (INTEGER) – primary key.
- `train_name` (TEXT) (not null).
- `train_type` (TEXT) (not null).
- `source_station` (TEXT).
- `destination_station` (TEXT).
- `created_at` (TIMESTAMP); default `CURRENT_TIMESTAMP`.
- `total_stops` (INTEGER).
- `total_distance` (INTEGER).
- `start_lat` (REAL).
- `start_lon` (REAL).
- `end_lat` (REAL).
- `end_lon` (REAL).

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| train_no | INTEGER | 0 |  | 1 |

| train_name | TEXT | 1 |  | 0 |

| train_type | TEXT | 1 |  | 0 |

| source_station | TEXT | 0 |  | 0 |

| destination_station | TEXT | 0 |  | 0 |

| created_at | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |

| total_stops | INTEGER | 0 |  | 0 |

| total_distance | INTEGER | 0 |  | 0 |

| start_lat | REAL | 0 |  | 0 |

| start_lon | REAL | 0 |  | 0 |

| end_lat | REAL | 0 |  | 0 |

| end_lon | REAL | 0 |  | 0 |


**Sample rows:**

```
(10103, 'MANDOVI EXPR', 'EXPRESS', 'CSMT', 'MAO', '2026-01-27 18:30:00', None, None, 18.9398446, 72.8354475, 15.2676769, 73.9707938)
```
```
(10104, 'MANDOVI EXPR', 'EXPRESS', 'MAO', 'CSMT', '2026-01-27 18:30:00', None, None, 15.2676769, 73.9707938, 18.9398446, 72.8354475)
```
```
(10111, 'KONKAN KANYA', 'GENERAL', 'CSMT', 'MAO', '2026-01-27 18:30:00', None, None, 18.9398446, 72.8354475, 15.2676769, 73.9707938)
```
```
(10112, 'KONKAN KANYA', 'GENERAL', 'MAO', 'CSMT', '2026-01-27 18:30:00', None, None, 15.2676769, 73.9707938, 18.9398446, 72.8354475)
```
```
(10215, 'MAO-ERS', 'GENERAL', 'MAO', 'ERS', '2026-01-27 18:30:00', 11, 726, 15.2676769, 73.9707938, 9.9695719, 76.2911687)
```

## Table `train_running_days`

**Purpose:** This table stores records about `train_running_days`. Each row represents a single train running days entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `train_no` (INTEGER) – primary key.
- `mon` (INTEGER) (not null); default `0`.
- `tue` (INTEGER) (not null); default `0`.
- `wed` (INTEGER) (not null); default `0`.
- `thu` (INTEGER) (not null); default `0`.
- `fri` (INTEGER) (not null); default `0`.
- `sat` (INTEGER) (not null); default `0`.
- `sun` (INTEGER) (not null); default `0`.
- `created_at` (TIMESTAMP); default `CURRENT_TIMESTAMP`.

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| train_no | INTEGER | 0 |  | 1 |

| mon | INTEGER | 1 | 0 | 0 |

| tue | INTEGER | 1 | 0 | 0 |

| wed | INTEGER | 1 | 0 | 0 |

| thu | INTEGER | 1 | 0 | 0 |

| fri | INTEGER | 1 | 0 | 0 |

| sat | INTEGER | 1 | 0 | 0 |

| sun | INTEGER | 1 | 0 | 0 |

| created_at | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |


**Sample rows:**

```
(10103, 0, 0, 0, 1, 0, 0, 0, '2026-01-27 18:30:00')
```
```
(10104, 1, 0, 0, 0, 0, 0, 0, '2026-01-27 18:30:00')
```
```
(10111, 0, 0, 0, 0, 1, 0, 0, '2026-01-27 18:30:00')
```
```
(10112, 0, 0, 0, 0, 0, 1, 0, '2026-01-27 18:30:00')
```
```
(10215, 0, 1, 0, 0, 0, 0, 0, '2026-01-27 18:30:00')
```

## Table `train_routes`

**Purpose:** This table stores records about `train_routes`. Each row represents a single train routes entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `train_no` (INTEGER) – primary key (not null).
- `seq_no` (INTEGER) (not null).
- `station_code` (TEXT) (not null).
- `arrival_time` (TEXT).
- `departure_time` (TEXT).
- `distance_from_source` (INTEGER) (not null); default `0`.
- `created_at` (TIMESTAMP); default `CURRENT_TIMESTAMP`.
- `cumulative_travel_minutes` (INTEGER) (not null); default `0`.
- `day_offset` (INTEGER) (not null); default `0`.

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| train_no | INTEGER | 1 |  | 1 |

| seq_no | INTEGER | 1 |  | 2 |

| station_code | TEXT | 1 |  | 0 |

| arrival_time | TEXT | 0 |  | 0 |

| departure_time | TEXT | 0 |  | 0 |

| distance_from_source | INTEGER | 1 | 0 | 0 |

| created_at | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |

| cumulative_travel_minutes | INTEGER | 1 | 0 | 0 |

| day_offset | INTEGER | 1 | 0 | 0 |


**Sample rows:**

```
(10103, 1, 'CSMT', '07:10:00', '07:10:00', 0, '2026-01-27 18:30:00', 0, 0)
```
```
(10103, 4, 'PNVL', '08:25:00', '08:30:00', 70, '2026-01-27 18:30:00', 75, 0)
```
```
(10103, 5, 'MNI', '10:34:00', '10:35:00', 177, '2026-01-27 18:30:00', 204, 0)
```
```
(10103, 6, 'KHED', '11:26:00', '11:27:00', 245, '2026-01-27 18:30:00', 256, 0)
```
```
(10103, 7, 'CHI', '11:58:00', '11:59:00', 275, '2026-01-27 18:30:00', 288, 0)
```

## Table `train_schedule`

**Purpose:** This table stores records about `train_schedule`. Each row represents a single train schedule entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `train_no` (INTEGER) – primary key (not null).
- `seq_no` (INTEGER) (not null).
- `station_code` (TEXT) (not null).
- `arrival_time` (TEXT).
- `departure_time` (TEXT).
- `day_offset` (INTEGER) (not null); default `0`.
- `created_at` (TIMESTAMP); default `CURRENT_TIMESTAMP`.

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| train_no | INTEGER | 1 |  | 1 |

| seq_no | INTEGER | 1 |  | 2 |

| station_code | TEXT | 1 |  | 0 |

| arrival_time | TEXT | 0 |  | 0 |

| departure_time | TEXT | 0 |  | 0 |

| day_offset | INTEGER | 1 | 0 | 0 |

| created_at | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |


**Sample rows:**

```
(10103, 1, 'CSMT', '07:10:00', '07:10:00', 0, '2026-01-27 18:30:05')
```
```
(10103, 2, 'DR', '07:22:00', '07:25:00', 0, '2026-01-27 18:30:05')
```
```
(10103, 3, 'TNA', '07:46:00', '07:50:00', 0, '2026-01-27 18:30:05')
```
```
(10103, 4, 'PNVL', '08:25:00', '08:30:00', 0, '2026-01-27 18:30:05')
```
```
(10103, 5, 'MNI', '10:34:00', '10:35:00', 0, '2026-01-27 18:30:05')
```

## Table `train_fares`

**Purpose:** This table stores records about `train_fares`. Each row represents a single train fares entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `train_no` (INTEGER) – primary key (not null).
- `source_station` (TEXT) (not null).
- `destination_station` (TEXT) (not null).
- `class_code` (TEXT) (not null).
- `base_fare` (REAL).
- `total_fare` (REAL).
- `dynamic_fare` (REAL).
- `distance` (INTEGER).
- `duration` (REAL).
- `availability` (TEXT).
- `fare_timestamp` (TEXT).
- `created_at` (TIMESTAMP); default `CURRENT_TIMESTAMP`.

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| train_no | INTEGER | 1 |  | 1 |

| source_station | TEXT | 1 |  | 2 |

| destination_station | TEXT | 1 |  | 3 |

| class_code | TEXT | 1 |  | 4 |

| base_fare | REAL | 0 |  | 0 |

| total_fare | REAL | 0 |  | 0 |

| dynamic_fare | REAL | 0 |  | 0 |

| distance | INTEGER | 0 |  | 0 |

| duration | REAL | 0 |  | 0 |

| availability | TEXT | 0 |  | 0 |

| fare_timestamp | TEXT | 0 |  | 0 |

| created_at | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |


**Sample rows:**

```
(11464, 'JBP', 'SRID', '1A', 1059.0, 1175.0, 0.0, 54, 33.0, "[{'date': '2-12-2023', 'status': 'AVAILABLE-0008'}, {'date': '3-12-2023', 'status': 'AVAILABLE-0014'}, {'date': '5-12-2023', 'status': 'AVAILABLE-0011'}, {'date': '6-12-2023', 'status': 'AVAILABLE-0004'}, {'date': '7-12-2023', 'status': 'AVAILABLE-0014'}, {'date': '9-12-2023', 'status': 'AVAILABLE-0012'}]", '2023-10-03 22:13:07.781307', '2026-01-27 18:30:07')
```
```
(11464, 'JBP', 'SRID', '2A', 626.0, 710.0, 0.0, 54, 33.0, "[{'date': '2-12-2023', 'status': 'AVAILABLE-0020'}, {'date': '3-12-2023', 'status': 'AVAILABLE-0026'}, {'date': '5-12-2023', 'status': 'AVAILABLE-0029'}, {'date': '6-12-2023', 'status': 'AVAILABLE-0018'}, {'date': '7-12-2023', 'status': 'AVAILABLE-0026'}, {'date': '9-12-2023', 'status': 'AVAILABLE-0022'}]", '2023-10-03 22:13:07.781307', '2026-01-27 18:30:07')
```
```
(11464, 'JBP', 'SRID', '3A', 441.0, 505.0, 0.0, 54, 33.0, "[{'date': '2-12-2023', 'status': 'AVAILABLE-0136'}, {'date': '3-12-2023', 'status': 'AVAILABLE-0192'}, {'date': '5-12-2023', 'status': 'AVAILABLE-0185'}, {'date': '6-12-2023', 'status': 'AVAILABLE-0139'}, {'date': '7-12-2023', 'status': 'AVAILABLE-0154'}, {'date': '9-12-2023', 'status': 'AVAILABLE-0140'}]", '2023-10-03 22:13:07.781307', '2026-01-27 18:30:07')
```
```
(11464, 'JBP', 'SRID', 'SL', 125.0, 145.0, 0.0, 54, 33.0, "[{'date': '2-12-2023', 'status': 'AVAILABLE-0090'}, {'date': '3-12-2023', 'status': 'AVAILABLE-0101'}, {'date': '5-12-2023', 'status': 'AVAILABLE-0100'}, {'date': '6-12-2023', 'status': 'AVAILABLE-0067'}, {'date': '7-12-2023', 'status': 'AVAILABLE-0118'}, {'date': '9-12-2023', 'status': 'AVAILABLE-0125'}]", '2023-10-03 22:13:07.781307', '2026-01-27 18:30:07')
```
```
(11464, 'JBP', 'KKB', '1A', 1059.0, 1175.0, 0.0, 69, 49.0, "[{'date': '2-12-2023', 'status': 'AVAILABLE-0008'}, {'date': '3-12-2023', 'status': 'AVAILABLE-0014'}, {'date': '5-12-2023', 'status': 'AVAILABLE-0011'}, {'date': '6-12-2023', 'status': 'AVAILABLE-0004'}, {'date': '7-12-2023', 'status': 'AVAILABLE-0014'}, {'date': '9-12-2023', 'status': 'AVAILABLE-0012'}]", '2023-10-03 22:13:07.781307', '2026-01-27 18:30:07')
```

## Table `trains_active`

**Purpose:** This table stores records about `trains_active`. Each row represents a single trains active entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `train_no` (INTEGER) – primary key.
- `is_running` (INTEGER) (not null); default `0`.
- `last_verified_date` (TEXT).
- `created_at` (TIMESTAMP); default `CURRENT_TIMESTAMP`.

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| train_no | INTEGER | 0 |  | 1 |

| is_running | INTEGER | 1 | 0 | 0 |

| last_verified_date | TEXT | 0 |  | 0 |

| created_at | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |


**Sample rows:**

```
(10103, 1, '2026-01-25T16:56:50.035761', '2026-01-27 18:30:21')
```
```
(10104, 1, '2026-01-25T16:56:50.787345', '2026-01-27 18:30:21')
```
```
(10111, 1, '2026-01-25T16:56:52.206477', '2026-01-27 18:30:21')
```
```
(10112, 1, '2026-01-25T16:56:53.016629', '2026-01-27 18:30:21')
```
```
(10215, 1, '2026-01-25T16:56:53.744130', '2026-01-27 18:30:21')
```

## Table `geocode_cache`

**Purpose:** This table stores records about `geocode_cache`. Each row represents a single geocode cache entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `query` (TEXT) – primary key.
- `lat` (TEXT).
- `lon` (TEXT).
- `state` (TEXT).

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| query | TEXT | 0 |  | 1 |

| lat | TEXT | 0 |  | 0 |

| lon | TEXT | 0 |  | 0 |

| state | TEXT | 0 |  | 0 |


## Table `migration_history`

**Purpose:** This table stores records about `migration_history`. Each row represents a single migration history entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (INTEGER) – primary key.
- `migration_name` (TEXT) (not null).
- `applied_at` (DATETIME); default `CURRENT_TIMESTAMP`.

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 0 |  | 1 |

| migration_name | TEXT | 1 |  | 0 |

| applied_at | DATETIME | 0 | CURRENT_TIMESTAMP | 0 |


**Sample rows:**

```
(1, '001_add_journey_and_sos_tables.sql', '2026-02-01 13:44:35')
```
```
(2, '003_mvp_sqlite_bootstrap.sqlite.sql', '2026-02-10 13:50:29')
```

## Table `sqlite_sequence`

**Purpose:** This table stores records about `sqlite_sequence`. Each row represents a single sqlite sequence entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `name` ().
- `seq` ().

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| name |  | 0 |  | 0 |

| seq |  | 0 |  | 0 |


**Sample rows:**

```
('migration_history', 2)
```
```
('journey_history', 2)
```
```
('notifications', 2)
```
```
('notification_preferences', 1)
```

## Table `journey_history`

**Purpose:** This table stores records about `journey_history`. Each row represents a single journey history entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (INTEGER) – primary key.
- `passenger_id` (TEXT) (not null).
- `departure_station` (TEXT) (not null).
- `arrival_station` (TEXT) (not null).
- `train_id` (TEXT).
- `selected_date` (DATE).
- `selected_time` (TIME).
- `search_timestamp` (TIMESTAMP); default `CURRENT_TIMESTAMP`.
- `selection_timestamp` (TIMESTAMP).
- `source` (TEXT) (not null).
- `route_details` (TEXT).
- `status` (TEXT); default `'searching'`.
- `notes` (TEXT).
- `created_at` (TIMESTAMP); default `CURRENT_TIMESTAMP`.
- `updated_at` (TIMESTAMP); default `CURRENT_TIMESTAMP`.

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 0 |  | 1 |

| passenger_id | TEXT | 1 |  | 0 |

| departure_station | TEXT | 1 |  | 0 |

| arrival_station | TEXT | 1 |  | 0 |

| train_id | TEXT | 0 |  | 0 |

| selected_date | DATE | 0 |  | 0 |

| selected_time | TIME | 0 |  | 0 |

| search_timestamp | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |

| selection_timestamp | TIMESTAMP | 0 |  | 0 |

| source | TEXT | 1 |  | 0 |

| route_details | TEXT | 0 |  | 0 |

| status | TEXT | 0 | 'searching' | 0 |

| notes | TEXT | 0 |  | 0 |

| created_at | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |

| updated_at | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |


**Sample rows:**

```
(1, 'test001', 'NDLS', 'BOM', '12345', '2026-02-15', '10:30', '2026-02-01 13:45:47', '2026-02-01 13:45:47', 'website', None, 'completed', None, '2026-02-01 13:45:47', '2026-02-01 13:46:21')
```
```
(2, 'test_user_001', 'NDLS', 'BOM', '12345', '2026-02-20', '14:30', '2026-02-01 13:46:21', '2026-02-01 13:46:21', 'website', None, 'selected', None, '2026-02-01 13:46:21', '2026-02-01 13:46:21')
```

## Table `passenger_locations`

**Purpose:** This table stores records about `passenger_locations`. Each row represents a single passenger locations entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (INTEGER) – primary key.
- `passenger_id` (TEXT) (not null).
- `journey_id` (INTEGER) (not null).
- `starting_location_lat` (REAL).
- `starting_location_lng` (REAL).
- `current_location_lat` (REAL).
- `current_location_lng` (REAL).
- `location_shared_at` (TIMESTAMP).
- `journey_started_at` (TIMESTAMP).
- `journey_ended_at` (TIMESTAMP).
- `is_journey_active` (BOOLEAN); default `0`.
- `last_update` (TIMESTAMP); default `CURRENT_TIMESTAMP`.
- `auto_delete_at` (TIMESTAMP).
- `created_at` (TIMESTAMP); default `CURRENT_TIMESTAMP`.

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 0 |  | 1 |

| passenger_id | TEXT | 1 |  | 0 |

| journey_id | INTEGER | 1 |  | 0 |

| starting_location_lat | REAL | 0 |  | 0 |

| starting_location_lng | REAL | 0 |  | 0 |

| current_location_lat | REAL | 0 |  | 0 |

| current_location_lng | REAL | 0 |  | 0 |

| location_shared_at | TIMESTAMP | 0 |  | 0 |

| journey_started_at | TIMESTAMP | 0 |  | 0 |

| journey_ended_at | TIMESTAMP | 0 |  | 0 |

| is_journey_active | BOOLEAN | 0 | 0 | 0 |

| last_update | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |

| auto_delete_at | TIMESTAMP | 0 |  | 0 |

| created_at | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |


## Table `sos_requests`

**Purpose:** This table stores records about `sos_requests`. Each row represents a single sos requests entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (INTEGER) – primary key.
- `sos_id` (TEXT) (not null).
- `passenger_id` (TEXT) (not null).
- `journey_id` (INTEGER).
- `emergency_type` (TEXT) (not null).
- `current_location_lat` (REAL).
- `current_location_lng` (REAL).
- `description` (TEXT).
- `timestamp` (TIMESTAMP); default `CURRENT_TIMESTAMP`.
- `status` (TEXT); default `'ACTIVE'`.
- `priority` (TEXT); default `'HIGH'`.
- `assigned_responder` (TEXT).
- `response_eta_minutes` (INTEGER).
- `resolved_at` (TIMESTAMP).
- `feedback_rating` (INTEGER).
- `feedback_text` (TEXT).
- `resolved_by` (TEXT).
- `created_at` (TIMESTAMP); default `CURRENT_TIMESTAMP`.
- `updated_at` (TIMESTAMP); default `CURRENT_TIMESTAMP`.

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 0 |  | 1 |

| sos_id | TEXT | 1 |  | 0 |

| passenger_id | TEXT | 1 |  | 0 |

| journey_id | INTEGER | 0 |  | 0 |

| emergency_type | TEXT | 1 |  | 0 |

| current_location_lat | REAL | 0 |  | 0 |

| current_location_lng | REAL | 0 |  | 0 |

| description | TEXT | 0 |  | 0 |

| timestamp | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |

| status | TEXT | 0 | 'ACTIVE' | 0 |

| priority | TEXT | 0 | 'HIGH' | 0 |

| assigned_responder | TEXT | 0 |  | 0 |

| response_eta_minutes | INTEGER | 0 |  | 0 |

| resolved_at | TIMESTAMP | 0 |  | 0 |

| feedback_rating | INTEGER | 0 |  | 0 |

| feedback_text | TEXT | 0 |  | 0 |

| resolved_by | TEXT | 0 |  | 0 |

| created_at | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |

| updated_at | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |


## Table `sos_chat_history`

**Purpose:** This table stores records about `sos_chat_history`. Each row represents a single sos chat history entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (INTEGER) – primary key.
- `sos_id` (TEXT) (not null).
- `sender_type` (TEXT) (not null).
- `sender_id` (TEXT).
- `sender_name` (TEXT).
- `message` (TEXT) (not null).
- `message_type` (TEXT); default `'text'`.
- `attachment_url` (TEXT).
- `is_read` (BOOLEAN); default `0`.
- `created_at` (TIMESTAMP); default `CURRENT_TIMESTAMP`.

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 0 |  | 1 |

| sos_id | TEXT | 1 |  | 0 |

| sender_type | TEXT | 1 |  | 0 |

| sender_id | TEXT | 0 |  | 0 |

| sender_name | TEXT | 0 |  | 0 |

| message | TEXT | 1 |  | 0 |

| message_type | TEXT | 0 | 'text' | 0 |

| attachment_url | TEXT | 0 |  | 0 |

| is_read | BOOLEAN | 0 | 0 | 0 |

| created_at | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |


## Table `notifications`

**Purpose:** This table stores records about `notifications`. Each row represents a single notifications entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (INTEGER) – primary key.
- `passenger_id` (TEXT) (not null).
- `journey_id` (INTEGER).
- `sos_id` (TEXT).
- `notification_type` (TEXT) (not null).
- `channels` (TEXT).
- `email_sent` (BOOLEAN); default `0`.
- `sms_sent` (BOOLEAN); default `0`.
- `telegram_sent` (BOOLEAN); default `0`.
- `inapp_sent` (BOOLEAN); default `0`.
- `subject` (TEXT).
- `message` (TEXT) (not null).
- `template_name` (TEXT).
- `priority` (TEXT); default `'NORMAL'`.
- `created_at` (TIMESTAMP); default `CURRENT_TIMESTAMP`.
- `sent_at` (TIMESTAMP).
- `read_at` (TIMESTAMP).

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 0 |  | 1 |

| passenger_id | TEXT | 1 |  | 0 |

| journey_id | INTEGER | 0 |  | 0 |

| sos_id | TEXT | 0 |  | 0 |

| notification_type | TEXT | 1 |  | 0 |

| channels | TEXT | 0 |  | 0 |

| email_sent | BOOLEAN | 0 | 0 | 0 |

| sms_sent | BOOLEAN | 0 | 0 | 0 |

| telegram_sent | BOOLEAN | 0 | 0 | 0 |

| inapp_sent | BOOLEAN | 0 | 0 | 0 |

| subject | TEXT | 0 |  | 0 |

| message | TEXT | 1 |  | 0 |

| template_name | TEXT | 0 |  | 0 |

| priority | TEXT | 0 | 'NORMAL' | 0 |

| created_at | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |

| sent_at | TIMESTAMP | 0 |  | 0 |

| read_at | TIMESTAMP | 0 |  | 0 |


**Sample rows:**

```
(1, 'test001', 1, None, 'confirmation', '{"email": true, "sms": false, "telegram": false, "inapp": true}', 1, 0, 0, 1, 'Journey Confirmation', '\n✅ Journey Confirmed!\n\nFrom: NDLS\nTo: BOM\nTrain: 12345\nDate: 2026-02-15\nTime: 10:30\n\nHave a safe journey!\n', 'journey_confirmation', 'NORMAL', '2026-02-01 13:45:47', '2026-02-01 13:45:47', '2026-02-01 13:46:21')
```
```
(2, 'test_user_001', 2, None, 'confirmation', '{"email": true, "sms": false, "telegram": false, "inapp": true}', 1, 0, 0, 1, 'Journey Confirmation', '\n✅ Journey Confirmed!\n\nFrom: NDLS\nTo: BOM\nTrain: 12345\nDate: 2026-02-20\nTime: 14:30\n\nHave a safe journey!\n', 'journey_confirmation', 'NORMAL', '2026-02-01 13:46:21', '2026-02-01 13:46:21', None)
```

## Table `notification_preferences`

**Purpose:** This table stores records about `notification_preferences`. Each row represents a single notification preferences entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (INTEGER) – primary key.
- `passenger_id` (TEXT) (not null).
- `email_enabled` (BOOLEAN); default `1`.
- `sms_enabled` (BOOLEAN); default `0`.
- `telegram_enabled` (BOOLEAN); default `1`.
- `inapp_enabled` (BOOLEAN); default `1`.
- `journey_updates` (BOOLEAN); default `1`.
- `emergency_alerts` (BOOLEAN); default `1`.
- `promotional_emails` (BOOLEAN); default `0`.
- `email_address` (TEXT).
- `phone_number` (TEXT).
- `telegram_chat_id` (TEXT).
- `created_at` (TIMESTAMP); default `CURRENT_TIMESTAMP`.
- `updated_at` (TIMESTAMP); default `CURRENT_TIMESTAMP`.

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 0 |  | 1 |

| passenger_id | TEXT | 1 |  | 0 |

| email_enabled | BOOLEAN | 0 | 1 | 0 |

| sms_enabled | BOOLEAN | 0 | 0 | 0 |

| telegram_enabled | BOOLEAN | 0 | 1 | 0 |

| inapp_enabled | BOOLEAN | 0 | 1 | 0 |

| journey_updates | BOOLEAN | 0 | 1 | 0 |

| emergency_alerts | BOOLEAN | 0 | 1 | 0 |

| promotional_emails | BOOLEAN | 0 | 0 | 0 |

| email_address | TEXT | 0 |  | 0 |

| phone_number | TEXT | 0 |  | 0 |

| telegram_chat_id | TEXT | 0 |  | 0 |

| created_at | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |

| updated_at | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |


**Sample rows:**

```
(1, 'test_user_001', 1, 0, 1, 1, 1, 1, 0, None, None, None, '2026-02-01 13:46:21', '2026-02-01 13:46:22')
```

## Table `user_sessions`

**Purpose:** This table stores records about `user_sessions`. Each row represents a single user sessions entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (INTEGER) – primary key.
- `chat_id` (BIGINT) (not null).
- `state` (VARCHAR(50)); default `'HOME'`.
- `session_data` (TEXT).
- `created_at` (TIMESTAMP); default `CURRENT_TIMESTAMP`.
- `last_activity` (TIMESTAMP); default `CURRENT_TIMESTAMP`.
- `expires_at` (TIMESTAMP).
- `is_active` (BOOLEAN); default `TRUE`.

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 0 |  | 1 |

| chat_id | BIGINT | 1 |  | 0 |

| state | VARCHAR(50) | 0 | 'HOME' | 0 |

| session_data | TEXT | 0 |  | 0 |

| created_at | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |

| last_activity | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |

| expires_at | TIMESTAMP | 0 |  | 0 |

| is_active | BOOLEAN | 0 | TRUE | 0 |


## Table `user_preferences`

**Purpose:** This table stores records about `user_preferences`. Each row represents a single user preferences entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (INTEGER) – primary key.
- `chat_id` (BIGINT) (not null).
- `username` (VARCHAR(100)).
- `language` (VARCHAR(10)); default `'en'`.
- `home_station_code` (VARCHAR(10)).
- `home_station_name` (VARCHAR(100)).
- `default_travel_class` (VARCHAR(20)); default `'SL'`.
- `notify_journey_updates` (BOOLEAN); default `TRUE`.
- `notify_emergency_alerts` (BOOLEAN); default `TRUE`.
- `notify_promotions` (BOOLEAN); default `FALSE`.
- `preferred_notification_channel` (VARCHAR(20)); default `'telegram'`.
- `created_at` (TIMESTAMP); default `CURRENT_TIMESTAMP`.
- `updated_at` (TIMESTAMP); default `CURRENT_TIMESTAMP`.

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 0 |  | 1 |

| chat_id | BIGINT | 1 |  | 0 |

| username | VARCHAR(100) | 0 |  | 0 |

| language | VARCHAR(10) | 0 | 'en' | 0 |

| home_station_code | VARCHAR(10) | 0 |  | 0 |

| home_station_name | VARCHAR(100) | 0 |  | 0 |

| default_travel_class | VARCHAR(20) | 0 | 'SL' | 0 |

| notify_journey_updates | BOOLEAN | 0 | TRUE | 0 |

| notify_emergency_alerts | BOOLEAN | 0 | TRUE | 0 |

| notify_promotions | BOOLEAN | 0 | FALSE | 0 |

| preferred_notification_channel | VARCHAR(20) | 0 | 'telegram' | 0 |

| created_at | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |

| updated_at | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |


## Table `webhook_logs`

**Purpose:** This table stores records about `webhook_logs`. Each row represents a single webhook logs entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (INTEGER) – primary key.
- `update_id` (BIGINT).
- `chat_id` (BIGINT).
- `message_type` (VARCHAR(50)).
- `callback_data` (VARCHAR(100)).
- `raw_payload` (TEXT).
- `processed` (BOOLEAN); default `FALSE`.
- `processing_time_ms` (INTEGER).
- `error_message` (TEXT).
- `created_at` (TIMESTAMP); default `CURRENT_TIMESTAMP`.

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 0 |  | 1 |

| update_id | BIGINT | 0 |  | 0 |

| chat_id | BIGINT | 0 |  | 0 |

| message_type | VARCHAR(50) | 0 |  | 0 |

| callback_data | VARCHAR(100) | 0 |  | 0 |

| raw_payload | TEXT | 0 |  | 0 |

| processed | BOOLEAN | 0 | FALSE | 0 |

| processing_time_ms | INTEGER | 0 |  | 0 |

| error_message | TEXT | 0 |  | 0 |

| created_at | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |


## Table `error_logs`

**Purpose:** This table stores records about `error_logs`. Each row represents a single error logs entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (INTEGER) – primary key.
- `module` (VARCHAR(100)) (not null).
- `function_name` (VARCHAR(100)).
- `error_type` (VARCHAR(100)).
- `error_message` (TEXT) (not null).
- `stack_trace` (TEXT).
- `chat_id` (BIGINT).
- `session_state` (VARCHAR(50)).
- `additional_context` (TEXT).
- `severity` (VARCHAR(20)); default `'ERROR'`.
- `resolved` (BOOLEAN); default `FALSE`.
- `created_at` (TIMESTAMP); default `CURRENT_TIMESTAMP`.

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 0 |  | 1 |

| module | VARCHAR(100) | 1 |  | 0 |

| function_name | VARCHAR(100) | 0 |  | 0 |

| error_type | VARCHAR(100) | 0 |  | 0 |

| error_message | TEXT | 1 |  | 0 |

| stack_trace | TEXT | 0 |  | 0 |

| chat_id | BIGINT | 0 |  | 0 |

| session_state | VARCHAR(50) | 0 |  | 0 |

| additional_context | TEXT | 0 |  | 0 |

| severity | VARCHAR(20) | 0 | 'ERROR' | 0 |

| resolved | BOOLEAN | 0 | FALSE | 0 |

| created_at | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |


## Table `audit_logs`

**Purpose:** This table stores records about `audit_logs`. Each row represents a single audit logs entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (INTEGER) – primary key.
- `chat_id` (BIGINT).
- `action` (VARCHAR(100)) (not null).
- `resource_type` (VARCHAR(50)).
- `resource_id` (VARCHAR(50)).
- `old_value` (TEXT).
- `new_value` (TEXT).
- `ip_address` (VARCHAR(50)).
- `user_agent` (TEXT).
- `created_at` (TIMESTAMP); default `CURRENT_TIMESTAMP`.

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 0 |  | 1 |

| chat_id | BIGINT | 0 |  | 0 |

| action | VARCHAR(100) | 1 |  | 0 |

| resource_type | VARCHAR(50) | 0 |  | 0 |

| resource_id | VARCHAR(50) | 0 |  | 0 |

| old_value | TEXT | 0 |  | 0 |

| new_value | TEXT | 0 |  | 0 |

| ip_address | VARCHAR(50) | 0 |  | 0 |

| user_agent | TEXT | 0 |  | 0 |

| created_at | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |


## Table `bot_metrics`

**Purpose:** This table stores records about `bot_metrics`. Each row represents a single bot metrics entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (INTEGER) – primary key.
- `metric_name` (VARCHAR(100)) (not null).
- `metric_value` (REAL) (not null).
- `labels` (TEXT).
- `timestamp` (TIMESTAMP); default `CURRENT_TIMESTAMP`.

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 0 |  | 1 |

| metric_name | VARCHAR(100) | 1 |  | 0 |

| metric_value | REAL | 1 |  | 0 |

| labels | TEXT | 0 |  | 0 |

| timestamp | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |


## Table `saved_routes`

**Purpose:** This table stores records about `saved_routes`. Each row represents a single saved routes entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (INTEGER) – primary key.
- `chat_id` (BIGINT) (not null).
- `route_name` (VARCHAR(100)).
- `origin_code` (VARCHAR(10)) (not null).
- `origin_name` (VARCHAR(100)).
- `destination_code` (VARCHAR(10)) (not null).
- `destination_name` (VARCHAR(100)).
- `preferred_train_no` (VARCHAR(20)).
- `travel_class` (VARCHAR(20)).
- `notes` (TEXT).
- `use_count` (INTEGER); default `0`.
- `created_at` (TIMESTAMP); default `CURRENT_TIMESTAMP`.
- `last_used_at` (TIMESTAMP).

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 0 |  | 1 |

| chat_id | BIGINT | 1 |  | 0 |

| route_name | VARCHAR(100) | 0 |  | 0 |

| origin_code | VARCHAR(10) | 1 |  | 0 |

| origin_name | VARCHAR(100) | 0 |  | 0 |

| destination_code | VARCHAR(10) | 1 |  | 0 |

| destination_name | VARCHAR(100) | 0 |  | 0 |

| preferred_train_no | VARCHAR(20) | 0 |  | 0 |

| travel_class | VARCHAR(20) | 0 |  | 0 |

| notes | TEXT | 0 |  | 0 |

| use_count | INTEGER | 0 | 0 | 0 |

| created_at | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |

| last_used_at | TIMESTAMP | 0 |  | 0 |


## Table `users`

**Purpose:** This table stores records about `users`. Each row represents a single users entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `email` (VARCHAR(255)) (not null).
- `password_hash` (VARCHAR(255)) (not null).
- `phone_number` (VARCHAR(20)).
- `role` (VARCHAR(50)).
- `created_at` (DATETIME).

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| email | VARCHAR(255) | 1 |  | 0 |

| password_hash | VARCHAR(255) | 1 |  | 0 |

| phone_number | VARCHAR(20) | 0 |  | 0 |

| role | VARCHAR(50) | 0 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |


## Table `agency`

**Purpose:** This table stores records about `agency`. Each row represents a single agency entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (INTEGER) – primary key (not null).
- `agency_id` (VARCHAR(100)) (not null).
- `name` (VARCHAR(255)) (not null).
- `url` (VARCHAR(255)) (not null).
- `timezone` (VARCHAR(50)) (not null).

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 1 |  | 1 |

| agency_id | VARCHAR(100) | 1 |  | 0 |

| name | VARCHAR(255) | 1 |  | 0 |

| url | VARCHAR(255) | 1 |  | 0 |

| timezone | VARCHAR(50) | 1 |  | 0 |


## Table `stops`

**Purpose:** This table stores records about `stops`. Each row represents a single stops entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (INTEGER) – primary key (not null).
- `stop_id` (VARCHAR(100)) (not null).
- `code` (VARCHAR(100)).
- `name` (VARCHAR(255)) (not null).
- `city` (VARCHAR(255)).
- `state` (VARCHAR(255)).
- `latitude` (FLOAT) (not null).
- `longitude` (FLOAT) (not null).
- `geom` (VARCHAR).
- `location_type` (INTEGER).
- `parent_station_id` (INTEGER).
- `safety_score` (FLOAT) (not null).
- `is_major_junction` (BOOLEAN) (not null).
- `facilities_json` (JSON) (not null).
- `wheelchair_accessible` (BOOLEAN) (not null).
- `platform_count` (INTEGER).
- `distance_to_city_center_km` (FLOAT).

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

**Purpose:** This table stores records about `calendar`. Each row represents a single calendar entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (INTEGER) – primary key (not null).
- `service_id` (VARCHAR(100)) (not null).
- `monday` (BOOLEAN) (not null).
- `tuesday` (BOOLEAN) (not null).
- `wednesday` (BOOLEAN) (not null).
- `thursday` (BOOLEAN) (not null).
- `friday` (BOOLEAN) (not null).
- `saturday` (BOOLEAN) (not null).
- `sunday` (BOOLEAN) (not null).
- `start_date` (DATE) (not null).
- `end_date` (DATE) (not null).

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

**Purpose:** This table stores records about `calendar_dates`. Each row represents a single calendar dates entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (INTEGER) – primary key (not null).
- `service_id` (VARCHAR(100)) (not null).
- `date` (DATE) (not null).
- `exception_type` (INTEGER) (not null).

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 1 |  | 1 |

| service_id | VARCHAR(100) | 1 |  | 0 |

| date | DATE | 1 |  | 0 |

| exception_type | INTEGER | 1 |  | 0 |


## Table `realtime_data`

**Purpose:** This table stores records about `realtime_data`. Each row represents a single realtime data entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `event_type` (VARCHAR(50)) (not null).
- `entity_type` (VARCHAR(50)) (not null).
- `entity_id` (VARCHAR(100)) (not null).
- `data` (JSON) (not null).
- `timestamp` (DATETIME) (not null).
- `source` (VARCHAR(100)) (not null).
- `created_at` (DATETIME).

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

**Purpose:** This table stores records about `precalculated_routes`. Each row represents a single precalculated routes entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `source` (VARCHAR(255)) (not null).
- `destination` (VARCHAR(255)) (not null).
- `segments` (JSON) (not null).
- `total_duration` (VARCHAR(50)) (not null).
- `total_cost` (FLOAT) (not null).
- `created_at` (DATETIME).

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

**Purpose:** This table stores records about `vehicles`. Each row represents a single vehicles entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `vehicle_number` (VARCHAR(50)) (not null).
- `type` (VARCHAR(50)) (not null).
- `operator` (VARCHAR(255)) (not null).
- `capacity` (INTEGER).

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| vehicle_number | VARCHAR(50) | 1 |  | 0 |

| type | VARCHAR(50) | 1 |  | 0 |

| operator | VARCHAR(255) | 1 |  | 0 |

| capacity | INTEGER | 0 |  | 0 |


## Table `stations`

**Purpose:** This table stores records about `stations`. Each row represents a single stations entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `name` (VARCHAR(255)) (not null).
- `city` (VARCHAR(255)) (not null).
- `latitude` (FLOAT) (not null).
- `longitude` (FLOAT) (not null).
- `geom` (VARCHAR).
- `created_at` (DATETIME).

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| name | VARCHAR(255) | 1 |  | 0 |

| city | VARCHAR(255) | 1 |  | 0 |

| latitude | FLOAT | 1 |  | 0 |

| longitude | FLOAT | 1 |  | 0 |

| geom | VARCHAR | 0 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |


## Table `gtfs_routes`

**Purpose:** This table stores records about `gtfs_routes`. Each row represents a single gtfs routes entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (INTEGER) – primary key (not null).
- `route_id` (VARCHAR(100)) (not null).
- `agency_id` (INTEGER) (not null).
- `short_name` (VARCHAR(50)).
- `long_name` (VARCHAR(255)) (not null).
- `route_type` (INTEGER) (not null).

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 1 |  | 1 |

| route_id | VARCHAR(100) | 1 |  | 0 |

| agency_id | INTEGER | 1 |  | 0 |

| short_name | VARCHAR(50) | 0 |  | 0 |

| long_name | VARCHAR(255) | 1 |  | 0 |

| route_type | INTEGER | 1 |  | 0 |


## Table `commission_tracking`

**Purpose:** This table stores records about `commission_tracking`. Each row represents a single commission tracking entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `user_id` (VARCHAR(36)) (not null).
- `source` (VARCHAR(255)) (not null).
- `destination` (VARCHAR(255)) (not null).
- `travel_date` (DATE).
- `partner` (VARCHAR(100)) (not null).
- `commission_rate` (FLOAT) (not null).
- `tracking_id` (VARCHAR(64)) (not null).
- `redirect_url` (TEXT) (not null).
- `status` (VARCHAR(50)).
- `redirected_at` (DATETIME).
- `route_id` (VARCHAR(36)).

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

**Purpose:** This table stores records about `rl_feedback_logs`. Each row represents a single rl feedback logs entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `user_id` (VARCHAR(36)).
- `session_id` (VARCHAR(36)) (not null).
- `action` (VARCHAR(100)) (not null).
- `context` (JSON) (not null).
- `reward` (FLOAT) (not null).
- `timestamp` (DATETIME) (not null).
- `created_at` (DATETIME).

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

**Purpose:** This table stores records about `station_facilities`. Each row represents a single station facilities entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `stop_id` (INTEGER) (not null).
- `wifi_available` (BOOLEAN).
- `lounge_available` (BOOLEAN).
- `food_available` (BOOLEAN).
- `wheelchair_accessible` (BOOLEAN).
- `parking_available` (BOOLEAN).
- `baby_care` (BOOLEAN).
- `medical_clinic` (BOOLEAN).
- `lost_found` (BOOLEAN).
- `cloakroom` (BOOLEAN).
- `opening_time` (TIME).
- `closing_time` (TIME).
- `cctv_available` (BOOLEAN).
- `police_presence` (BOOLEAN).
- `women_waiting_room` (BOOLEAN).
- `emergency_contact` (VARCHAR(20)).
- `contact_email` (VARCHAR(255)).
- `created_at` (DATETIME).
- `updated_at` (DATETIME).

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


## Table `segments`

**Purpose:** This table stores records about `segments`. Each row represents a single segments entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `source_station_id` (VARCHAR(36)) (not null).
- `dest_station_id` (VARCHAR(36)) (not null).
- `vehicle_id` (VARCHAR(36)).
- `transport_mode` (VARCHAR(50)) (not null).
- `departure_time` (VARCHAR(8)) (not null).
- `arrival_time` (VARCHAR(8)) (not null).
- `duration_minutes` (INTEGER) (not null).
- `cost` (FLOAT) (not null).
- `operating_days` (VARCHAR(7)) (not null).

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| source_station_id | VARCHAR(36) | 1 |  | 0 |

| dest_station_id | VARCHAR(36) | 1 |  | 0 |

| vehicle_id | VARCHAR(36) | 0 |  | 0 |

| transport_mode | VARCHAR(50) | 1 |  | 0 |

| departure_time | VARCHAR(8) | 1 |  | 0 |

| arrival_time | VARCHAR(8) | 1 |  | 0 |

| duration_minutes | INTEGER | 1 |  | 0 |

| cost | FLOAT | 1 |  | 0 |

| operating_days | VARCHAR(7) | 1 |  | 0 |


## Table `route_search_logs`

**Purpose:** This table stores records about `route_search_logs`. Each row represents a single route search logs entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `user_id` (VARCHAR(36)).
- `src` (VARCHAR(255)) (not null).
- `dst` (VARCHAR(255)) (not null).
- `date` (DATE) (not null).
- `routes_shown` (JSON) (not null).
- `route_clicked` (VARCHAR(36)).
- `booking_success` (BOOLEAN).
- `latency_ms` (FLOAT) (not null).
- `created_at` (DATETIME).

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

**Purpose:** This table stores records about `train_states`. Each row represents a single train states entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `trip_id` (INTEGER) (not null).
- `train_number` (VARCHAR(50)) (not null).
- `current_station_id` (INTEGER).
- `next_station_id` (INTEGER).
- `delay_minutes` (INTEGER) (not null).
- `status` (VARCHAR(20)) (not null).
- `platform_number` (VARCHAR(10)).
- `last_updated` (DATETIME) (not null).
- `estimated_arrival` (DATETIME).
- `estimated_departure` (DATETIME).
- `occupancy_rate` (FLOAT) (not null).
- `cancelled_stations` (JSON) (not null).
- `created_at` (DATETIME).
- `updated_at` (DATETIME).

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

**Purpose:** This table stores records about `pnr_records`. Each row represents a single pnr records entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `pnr_number` (VARCHAR(10)) (not null).
- `user_id` (VARCHAR(36)) (not null).
- `travel_date` (DATE) (not null).
- `total_passengers` (INTEGER) (not null).
- `total_fare` (NUMERIC(10, 2)) (not null).
- `booking_status` (VARCHAR(9)) (not null).
- `payment_status` (VARCHAR(20)) (not null).
- `payment_id` (VARCHAR(100)).
- `segments_json` (JSON) (not null).
- `cancelled_at` (DATETIME).
- `refund_amount` (NUMERIC(10, 2)).
- `created_at` (DATETIME).
- `updated_at` (DATETIME).

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

**Purpose:** This table stores records about `booking_locks`. Each row represents a single booking locks entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `lock_key` (VARCHAR(200)) (not null).
- `user_id` (VARCHAR(36)) (not null).
- `session_id` (VARCHAR(100)) (not null).
- `acquired_at` (DATETIME) (not null).
- `expires_at` (DATETIME) (not null).
- `ttl_seconds` (INTEGER) (not null).
- `lock_type` (VARCHAR(20)) (not null).
- `resource_id` (VARCHAR(100)) (not null).
- `created_at` (DATETIME).

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

**Purpose:** This table stores records about `trips`. Each row represents a single trips entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (INTEGER) – primary key (not null).
- `trip_id` (VARCHAR(255)) (not null).
- `route_id` (INTEGER) (not null).
- `service_id` (VARCHAR(100)) (not null).
- `headsign` (VARCHAR(255)).
- `direction_id` (INTEGER).
- `bike_allowed` (BOOLEAN) (not null).
- `wheelchair_accessible` (BOOLEAN) (not null).
- `trip_headsign` (VARCHAR(255)).

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

**Purpose:** This table stores records about `transfers`. Each row represents a single transfers entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (INTEGER) – primary key (not null).
- `from_stop_id` (INTEGER) (not null).
- `to_stop_id` (INTEGER) (not null).
- `route_id` (INTEGER).
- `transfer_type` (INTEGER) (not null).
- `min_transfer_time` (INTEGER) (not null).

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 1 |  | 1 |

| from_stop_id | INTEGER | 1 |  | 0 |

| to_stop_id | INTEGER | 1 |  | 0 |

| route_id | INTEGER | 0 |  | 0 |

| transfer_type | INTEGER | 1 |  | 0 |

| min_transfer_time | INTEGER | 1 |  | 0 |


## Table `route_shapes`

**Purpose:** This table stores records about `route_shapes`. Each row represents a single route shapes entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `route_id` (INTEGER) (not null).
- `shape_id` (VARCHAR(100)) (not null).
- `geometry` (VARCHAR).
- `sequence` (INTEGER) (not null).
- `distance_traveled` (FLOAT) (not null).
- `created_at` (DATETIME).

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

**Purpose:** This table stores records about `cancellation_rules`. Each row represents a single cancellation rules entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `route_id` (INTEGER).
- `hours_before_departure` (INTEGER) (not null).
- `refund_percentage` (FLOAT) (not null).
- `is_active` (BOOLEAN).
- `created_at` (DATETIME).

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| route_id | INTEGER | 0 |  | 0 |

| hours_before_departure | INTEGER | 1 |  | 0 |

| refund_percentage | FLOAT | 1 |  | 0 |

| is_active | BOOLEAN | 0 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |


## Table `stop_times`

**Purpose:** This table stores records about `stop_times`. Each row represents a single stop times entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (INTEGER) – primary key (not null).
- `trip_id` (INTEGER) (not null).
- `stop_id` (INTEGER) (not null).
- `arrival_time` (TIME) (not null).
- `departure_time` (TIME) (not null).
- `stop_sequence` (INTEGER) (not null).
- `cost` (FLOAT) (not null).
- `pickup_type` (INTEGER) (not null).
- `drop_off_type` (INTEGER) (not null).
- `platform_number` (VARCHAR(10)).

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

**Purpose:** This table stores records about `bookings`. Each row represents a single bookings entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `pnr_number` (VARCHAR(10)) (not null).
- `user_id` (VARCHAR(36)) (not null).
- `travel_date` (DATE) (not null).
- `booking_status` (VARCHAR(50)) (not null).
- `amount_paid` (FLOAT) (not null).
- `booking_details` (JSON) (not null).
- `created_at` (DATETIME).
- `updated_at` (DATETIME).
- `route_id` (VARCHAR(36)).
- `trip_id` (INTEGER).
- `payment_status` (VARCHAR(50)).

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

**Purpose:** This table stores records about `disruptions`. Each row represents a single disruptions entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `disruption_type` (VARCHAR(50)) (not null).
- `description` (TEXT).
- `start_time` (DATETIME).
- `end_time` (DATETIME).
- `status` (VARCHAR(50)).
- `created_by_id` (VARCHAR(36)).
- `created_at` (DATETIME).
- `gtfs_route_id` (INTEGER).
- `trip_id` (INTEGER).
- `stop_id` (INTEGER).

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

**Purpose:** This table stores records about `frequencies`. Each row represents a single frequencies entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `trip_id` (INTEGER) (not null).
- `start_time` (TIME) (not null).
- `end_time` (TIME) (not null).
- `headway_secs` (INTEGER) (not null).
- `exact_times` (BOOLEAN).
- `created_at` (DATETIME).

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| trip_id | INTEGER | 1 |  | 0 |

| start_time | TIME | 1 |  | 0 |

| end_time | TIME | 1 |  | 0 |

| headway_secs | INTEGER | 1 |  | 0 |

| exact_times | BOOLEAN | 0 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |


## Table `coaches`

**Purpose:** This table stores records about `coaches`. Each row represents a single coaches entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `train_id` (INTEGER) (not null).
- `coach_number` (VARCHAR(10)) (not null).
- `coach_class` (VARCHAR(3)) (not null).
- `total_seats` (INTEGER) (not null).
- `base_fare_multiplier` (FLOAT) (not null).
- `created_at` (DATETIME).
- `updated_at` (DATETIME).

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

**Purpose:** This table stores records about `passenger_details`. Each row represents a single passenger details entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `booking_id` (VARCHAR(36)) (not null).
- `full_name` (VARCHAR(255)) (not null).
- `age` (INTEGER) (not null).
- `gender` (VARCHAR(10)) (not null).
- `phone_number` (VARCHAR(20)).
- `email` (VARCHAR(255)).
- `document_type` (VARCHAR(50)).
- `document_number` (VARCHAR(50)).
- `coach_number` (VARCHAR(10)).
- `seat_number` (VARCHAR(10)).
- `berth_type` (VARCHAR(20)).
- `concession_type` (VARCHAR(50)).
- `concession_discount` (FLOAT) (not null).
- `meal_preference` (VARCHAR(20)).
- `created_at` (DATETIME).
- `updated_at` (DATETIME).
- `pnr_id` (VARCHAR(36)) (not null).
- `name` (VARCHAR(100)) (not null).
- `berth_preference` (VARCHAR(10)).
- `seat_type` (VARCHAR(10)).
- `status` (VARCHAR(9)) (not null).

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

**Purpose:** This table stores records about `seat_inventory`. Each row represents a single seat inventory entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `travel_date` (DATE) (not null).
- `seats_available` (INTEGER) (not null).
- `last_reconciled_at` (DATETIME).
- `stop_time_id` (INTEGER) (not null).
- `trip_id` (INTEGER) (not null).
- `segment_from_stop_id` (INTEGER) (not null).
- `segment_to_stop_id` (INTEGER) (not null).
- `date` (DATE) (not null).
- `quota_type` (VARCHAR(15)) (not null).
- `total_seats` (INTEGER) (not null).
- `available_seats` (INTEGER) (not null).
- `booked_seats` (INTEGER) (not null).
- `blocked_seats` (INTEGER) (not null).
- `current_waitlist_position` (INTEGER) (not null).
- `rac_count` (INTEGER) (not null).
- `last_updated` (DATETIME).
- `created_at` (DATETIME).

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

**Purpose:** This table stores records about `reviews`. Each row represents a single reviews entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `user_id` (VARCHAR(36)) (not null).
- `booking_id` (VARCHAR(36)) (not null).
- `rating` (INTEGER) (not null).
- `comment` (TEXT).
- `created_at` (DATETIME).

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| user_id | VARCHAR(36) | 1 |  | 0 |

| booking_id | VARCHAR(36) | 1 |  | 0 |

| rating | INTEGER | 1 |  | 0 |

| comment | TEXT | 0 |  | 0 |

| created_at | DATETIME | 0 |  | 0 |


## Table `payments`

**Purpose:** This table stores records about `payments`. Each row represents a single payments entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `booking_id` (VARCHAR(36)).
- `razorpay_order_id` (VARCHAR(255)).
- `razorpay_payment_id` (VARCHAR(255)).
- `status` (VARCHAR(50)).
- `amount` (FLOAT) (not null).
- `created_at` (DATETIME).
- `updated_at` (DATETIME).

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

**Purpose:** This table stores records about `waiting_list`. Each row represents a single waiting list entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `booking_id` (VARCHAR(36)) (not null).
- `position` (INTEGER) (not null).
- `status` (VARCHAR(50)) (not null).
- `notification_sent` (BOOLEAN).
- `confirmed_at` (DATETIME).
- `created_at` (DATETIME).
- `updated_at` (DATETIME).

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

**Purpose:** This table stores records about `seats`. Each row represents a single seats entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `coach_id` (VARCHAR(36)) (not null).
- `seat_number` (VARCHAR(10)) (not null).
- `seat_type` (VARCHAR(10)) (not null).
- `is_active` (BOOLEAN) (not null).
- `is_preferred` (BOOLEAN) (not null).
- `created_at` (DATETIME).

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

**Purpose:** This table stores records about `unlocked_routes`. Each row represents a single unlocked routes entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `user_id` (VARCHAR(36)) (not null).
- `payment_id` (VARCHAR(36)).
- `unlocked_at` (DATETIME).
- `route_id` (VARCHAR(36)).

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| user_id | VARCHAR(36) | 1 |  | 0 |

| payment_id | VARCHAR(36) | 0 |  | 0 |

| unlocked_at | DATETIME | 0 |  | 0 |

| route_id | VARCHAR(36) | 0 |  | 0 |


## Table `quota_inventory`

**Purpose:** This table stores records about `quota_inventory`. Each row represents a single quota inventory entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `inventory_id` (VARCHAR(36)) (not null).
- `quota_type` (VARCHAR(15)) (not null).
- `allocated_seats` (INTEGER) (not null).
- `available_seats` (INTEGER) (not null).
- `max_allocation` (INTEGER) (not null).
- `created_at` (DATETIME).
- `updated_at` (DATETIME).

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

**Purpose:** This table stores records about `waitlist_queue`. Each row represents a single waitlist queue entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `inventory_id` (VARCHAR(36)) (not null).
- `user_id` (VARCHAR(36)) (not null).
- `waitlist_position` (INTEGER) (not null).
- `booking_request_time` (DATETIME) (not null).
- `passengers_json` (JSON) (not null).
- `preferences_json` (JSON).
- `status` (VARCHAR(9)) (not null).
- `promoted_at` (DATETIME).
- `expired_at` (DATETIME).
- `created_at` (DATETIME).
- `updated_at` (DATETIME).

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


## Table `fares`

**Purpose:** This table stores records about `fares`. Each row represents a single fares entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (INTEGER) – primary key (not null).
- `segment_id` (INTEGER).
- `trip_id` (INTEGER).
- `class_type` (VARCHAR(50)) (not null).
- `amount` (FLOAT) (not null).

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 1 |  | 1 |

| segment_id | INTEGER | 0 |  | 0 |

| trip_id | INTEGER | 0 |  | 0 |

| class_type | VARCHAR(50) | 1 |  | 0 |

| amount | FLOAT | 1 |  | 0 |


## Table `station_departures_indexed`

**Purpose:** This table stores records about `station_departures_indexed`. Each row represents a single station departures indexed entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `station_id` (INTEGER) (not null).
- `trip_id` (INTEGER) (not null).
- `departure_time` (TIME) (not null).
- `arrival_time_at_next` (TIME).
- `next_station_id` (INTEGER).
- `operating_days` (VARCHAR(7)) (not null).
- `train_number` (VARCHAR(50)).
- `distance_to_next` (FLOAT).

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| station_id | INTEGER | 1 |  | 0 |

| trip_id | INTEGER | 1 |  | 0 |

| departure_time | TIME | 1 |  | 0 |

| arrival_time_at_next | TIME | 0 |  | 0 |

| next_station_id | INTEGER | 0 |  | 0 |

| operating_days | VARCHAR(7) | 1 |  | 0 |

| train_number | VARCHAR(50) | 0 |  | 0 |

| distance_to_next | FLOAT | 0 |  | 0 |


## Table `time_index_keys`

**Purpose:** This table stores records about `time_index_keys`. Each row represents a single time index keys entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (INTEGER) – primary key (not null).
- `entity_type` (VARCHAR(50)) (not null).
- `entity_id` (VARCHAR(255)) (not null).

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 1 |  | 1 |

| entity_type | VARCHAR(50) | 1 |  | 0 |

| entity_id | VARCHAR(255) | 1 |  | 0 |


## Table `station_departures`

**Purpose:** This table stores records about `station_departures`. Each row represents a single station departures entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `station_id` (VARCHAR(36)) (not null).
- `bucket_start_minute` (INTEGER) (not null).
- `bitmap` (BLOB) (not null).
- `trips_count` (INTEGER) (not null).
- `created_at` (DATETIME) (not null).

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| station_id | VARCHAR(36) | 1 |  | 0 |

| bucket_start_minute | INTEGER | 1 |  | 0 |

| bitmap | BLOB | 1 |  | 0 |

| trips_count | INTEGER | 1 |  | 0 |

| created_at | DATETIME | 1 |  | 0 |


## Table `stop_departures`

**Purpose:** This table stores records about `stop_departures`. Each row represents a single stop departures entry used by the application. Columns below explain the stored attributes.

**Column details:**

- `id` (VARCHAR(36)) – primary key (not null).
- `stop_id` (INTEGER) (not null).
- `bucket_start_minute` (INTEGER) (not null).
- `bitmap` (BLOB) (not null).
- `trips_count` (INTEGER) (not null).
- `created_at` (DATETIME) (not null).

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| stop_id | INTEGER | 1 |  | 0 |

| bucket_start_minute | INTEGER | 1 |  | 0 |

| bitmap | BLOB | 1 |  | 0 |

| trips_count | INTEGER | 1 |  | 0 |

| created_at | DATETIME | 1 |  | 0 |
