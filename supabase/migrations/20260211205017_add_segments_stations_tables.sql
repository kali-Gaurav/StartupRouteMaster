/*
  # Add Segments and Stations Tables

  Adds the missing `segments` and `stations` tables that are required
  for the route search functionality and ETL pipeline.

  These tables store the core transportation network data.
*/

-- Create stations table
CREATE TABLE IF NOT EXISTS stations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  city text NOT NULL,
  latitude numeric NOT NULL,
  longitude numeric NOT NULL,
  created_at timestamptz DEFAULT now()
);

-- Create segments table
CREATE TABLE IF NOT EXISTS segments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_station_id uuid NOT NULL REFERENCES stations(id),
  dest_station_id uuid NOT NULL REFERENCES stations(id),
  transport_mode text NOT NULL,
  departure_time text NOT NULL, -- HH:MM format
  arrival_time text NOT NULL,   -- HH:MM format
  duration_minutes integer NOT NULL,
  cost numeric NOT NULL,
  operator text NOT NULL,
  operating_days text NOT NULL DEFAULT '1111111', -- 7-char bitmask for days
  created_at timestamptz DEFAULT now()
);

-- Enable RLS
ALTER TABLE stations ENABLE ROW LEVEL SECURITY;
ALTER TABLE segments ENABLE ROW LEVEL SECURITY;

-- RLS Policies (public read for route search)
CREATE POLICY "Anyone can view stations"
  ON stations FOR SELECT
  TO anon, authenticated
  USING (true);

CREATE POLICY "Anyone can view segments"
  ON segments FOR SELECT
  TO anon, authenticated
  USING (true);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_segments_source ON segments(source_station_id);
CREATE INDEX IF NOT EXISTS idx_segments_dest ON segments(dest_station_id);
CREATE INDEX IF NOT EXISTS idx_segments_departure ON segments(departure_time);
CREATE INDEX IF NOT EXISTS idx_segments_mode ON segments(transport_mode);
CREATE INDEX IF NOT EXISTS idx_stations_name ON stations(name);
CREATE INDEX IF NOT EXISTS idx_stations_city ON stations(city);

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_segments_route_time ON segments(source_station_id, dest_station_id, departure_time);
CREATE INDEX IF NOT EXISTS idx_segments_cost ON segments(cost);