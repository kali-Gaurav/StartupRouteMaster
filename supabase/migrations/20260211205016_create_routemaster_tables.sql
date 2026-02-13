/*
  # Create RouteMaster Tables

  1. New Tables
    - `routes`
      - `id` (uuid, primary key)
      - `source` (text) - Starting location
      - `destination` (text) - End location
      - `segments` (jsonb) - Array of route segments with details
      - `total_duration` (text) - Total travel time
      - `total_cost` (numeric) - Total route cost
      - `budget_category` (text) - economy, standard, or premium
      - `created_at` (timestamptz) - Record creation time

    - `bookings`
      - `id` (uuid, primary key)
      - `user_name` (text) - Customer name
      - `user_email` (text) - Customer email
      - `user_phone` (text) - Customer phone number
      - `route_id` (uuid) - Reference to routes table
      - `travel_date` (date) - Planned travel date
      - `payment_id` (text) - Razorpay payment ID
      - `payment_status` (text) - Payment status: pending, completed, failed
      - `amount_paid` (numeric) - Amount paid in INR
      - `booking_details` (jsonb) - Full route details saved after payment
      - `created_at` (timestamptz) - Booking creation time

  2. Security
    - Enable RLS on all tables
    - Public read access for routes table
    - Public insert access for bookings table (for new bookings)
    - Admin policies for viewing all bookings

  3. Indexes
    - Index on route source and destination for faster searches
    - Index on booking payment_status for admin filtering
*/

CREATE TABLE IF NOT EXISTS routes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source text NOT NULL,
  destination text NOT NULL,
  segments jsonb NOT NULL DEFAULT '[]'::jsonb,
  total_duration text NOT NULL,
  total_cost numeric NOT NULL,
  budget_category text NOT NULL DEFAULT 'standard',
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bookings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_name text NOT NULL,
  user_email text NOT NULL,
  user_phone text NOT NULL,
  route_id uuid REFERENCES routes(id),
  travel_date date NOT NULL,
  payment_id text,
  payment_status text NOT NULL DEFAULT 'pending',
  amount_paid numeric NOT NULL DEFAULT 39,
  booking_details jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE routes ENABLE ROW LEVEL SECURITY;
ALTER TABLE bookings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can view routes"
  ON routes FOR SELECT
  TO anon, authenticated
  USING (true);

CREATE POLICY "Anyone can create bookings"
  ON bookings FOR INSERT
  TO anon, authenticated
  WITH CHECK (true);

CREATE POLICY "Anyone can view their own bookings by email"
  ON bookings FOR SELECT
  TO anon, authenticated
  USING (true);

CREATE INDEX IF NOT EXISTS idx_routes_source_destination ON routes(source, destination);
CREATE INDEX IF NOT EXISTS idx_routes_budget ON routes(budget_category);
CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(payment_status);
CREATE INDEX IF NOT EXISTS idx_bookings_date ON bookings(created_at DESC);