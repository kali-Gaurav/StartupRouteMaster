# Database Report for `railway_manager.db`

**Location:** `backend/railway_manager.db`

Generated automatically. Contains 64 tables.


## Table `stations_master`

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

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| query | TEXT | 0 |  | 1 |

| lat | TEXT | 0 |  | 0 |

| lon | TEXT | 0 |  | 0 |

| state | TEXT | 0 |  | 0 |


## Table `migration_history`

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

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 0 |  | 1 |

| metric_name | VARCHAR(100) | 1 |  | 0 |

| metric_value | REAL | 1 |  | 0 |

| labels | TEXT | 0 |  | 0 |

| timestamp | TIMESTAMP | 0 | CURRENT_TIMESTAMP | 0 |


## Table `saved_routes`

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


## Table `gtfs_routes`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 1 |  | 1 |

| route_id | VARCHAR(100) | 1 |  | 0 |

| agency_id | INTEGER | 1 |  | 0 |

| short_name | VARCHAR(50) | 0 |  | 0 |

| long_name | VARCHAR(255) | 1 |  | 0 |

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


## Table `segments`

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


## Table `fares`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 1 |  | 1 |

| segment_id | INTEGER | 0 |  | 0 |

| trip_id | INTEGER | 0 |  | 0 |

| class_type | VARCHAR(50) | 1 |  | 0 |

| amount | FLOAT | 1 |  | 0 |


## Table `station_departures_indexed`

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

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | INTEGER | 1 |  | 1 |

| entity_type | VARCHAR(50) | 1 |  | 0 |

| entity_id | VARCHAR(255) | 1 |  | 0 |


## Table `station_departures`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| station_id | VARCHAR(36) | 1 |  | 0 |

| bucket_start_minute | INTEGER | 1 |  | 0 |

| bitmap | BLOB | 1 |  | 0 |

| trips_count | INTEGER | 1 |  | 0 |

| created_at | DATETIME | 1 |  | 0 |


## Table `stop_departures`

| Column | Type | NotNull | Default | PK |

|---|---|---|---|---|

| id | VARCHAR(36) | 1 |  | 1 |

| stop_id | INTEGER | 1 |  | 0 |

| bucket_start_minute | INTEGER | 1 |  | 0 |

| bitmap | BLOB | 1 |  | 0 |

| trips_count | INTEGER | 1 |  | 0 |

| created_at | DATETIME | 1 |  | 0 |
