-- Migration: Create Booking System Tables
-- Date: 2026-06-08
-- Purpose: Enable booking, payment, tickets, and refund tracking

-- Bookings table: Core booking records
CREATE TABLE IF NOT EXISTS bookings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    -- Journey details
    train_number VARCHAR(10) NOT NULL,
    journey_date DATE NOT NULL,
    source_station VARCHAR(10) NOT NULL,
    destination_station VARCHAR(10) NOT NULL,
    class_type VARCHAR(5) NOT NULL CHECK (class_type IN ('1A', '2A', '3A', 'SL')),

    -- Passenger details
    passenger_name VARCHAR(100) NOT NULL,
    passenger_email VARCHAR(100),
    passenger_phone VARCHAR(20),
    passenger_gender VARCHAR(10),
    passenger_dob DATE,

    -- Pricing breakdown
    base_fare DECIMAL(10, 2) NOT NULL,
    taxes DECIMAL(10, 2) DEFAULT 0,
    service_fee DECIMAL(10, 2) DEFAULT 50,
    total_fare DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'INR',

    -- Booking status
    status VARCHAR(30) NOT NULL DEFAULT 'PENDING_PAYMENT'
        CHECK (status IN ('PENDING_PAYMENT', 'PAYMENT_CONFIRMED', 'TICKET_CONFIRMED', 'COMPLETED', 'CANCELLED', 'REFUNDED')),

    -- IRCTC integration
    pnr VARCHAR(20),
    ticket_number VARCHAR(50),
    seat_number VARCHAR(10),
    coach_number VARCHAR(10),

    -- Cancellation tracking
    cancellation_requested_at TIMESTAMP,
    cancellation_reason VARCHAR(255),
    refund_amount DECIMAL(10, 2),

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    journey_completed_at TIMESTAMP,

    -- Metadata for extensibility
    metadata JSONB DEFAULT '{}',

    -- Constraints
    CONSTRAINT valid_dates CHECK (journey_date >= CURRENT_DATE),
    CONSTRAINT valid_stations CHECK (source_station != destination_station)
);

-- Payments table: Payment transaction tracking
CREATE TABLE IF NOT EXISTS payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id UUID NOT NULL UNIQUE REFERENCES bookings(id) ON DELETE CASCADE,

    -- Razorpay integration
    razorpay_order_id VARCHAR(50) UNIQUE,
    razorpay_payment_id VARCHAR(50) UNIQUE,
    razorpay_signature VARCHAR(255),

    -- Payment details
    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'INR',
    payment_method VARCHAR(50), -- card, upi, wallet, bank_transfer, netbanking
    status VARCHAR(30) NOT NULL DEFAULT 'INITIATED'
        CHECK (status IN ('INITIATED', 'PENDING', 'SUCCESS', 'FAILED', 'REFUNDED')),

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMP,
    failed_at TIMESTAMP,

    -- Error handling
    error_message VARCHAR(500),
    retry_count INT DEFAULT 0 CHECK (retry_count >= 0),
    last_retry_at TIMESTAMP,

    -- Metadata
    metadata JSONB DEFAULT '{}'
);

-- Tickets table: Issued tickets from IRCTC
CREATE TABLE IF NOT EXISTS tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id UUID NOT NULL UNIQUE REFERENCES bookings(id) ON DELETE CASCADE,

    -- Ticket details
    pnr VARCHAR(20) UNIQUE NOT NULL,
    ticket_number VARCHAR(50) UNIQUE NOT NULL,
    seat_number VARCHAR(10),
    coach_number VARCHAR(10),
    berth_type VARCHAR(20), -- Upper, Middle, Lower, Sitting

    -- IRCTC status
    irctc_status VARCHAR(30) DEFAULT 'PENDING'
        CHECK (irctc_status IN ('PENDING', 'CONFIRMED', 'CHART_NOT_PREPARED', 'CANCELLED', 'WAITLIST')),
    chart_status_updated_at TIMESTAMP,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Metadata
    metadata JSONB DEFAULT '{}'
);

-- Refunds table: Refund transactions
CREATE TABLE IF NOT EXISTS refunds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id UUID NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    payment_id UUID NOT NULL REFERENCES payments(id) ON DELETE CASCADE,

    -- Refund amount and status
    amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'INITIATED'
        CHECK (status IN ('INITIATED', 'PROCESSING', 'SUCCESS', 'FAILED')),

    -- Razorpay refund tracking
    razorpay_refund_id VARCHAR(50) UNIQUE,

    -- Reason for refund
    reason VARCHAR(255),

    -- Timestamps
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,

    -- Metadata
    metadata JSONB DEFAULT '{}'
);

-- Booking reviews table: Post-journey ratings and reviews
CREATE TABLE IF NOT EXISTS booking_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id UUID NOT NULL UNIQUE REFERENCES bookings(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    -- Overall rating
    overall_rating INT CHECK (overall_rating >= 1 AND overall_rating <= 5),
    review_text TEXT,

    -- Category ratings
    cleanliness_rating INT CHECK (cleanliness_rating >= 1 AND cleanliness_rating <= 5),
    comfort_rating INT CHECK (comfort_rating >= 1 AND comfort_rating <= 5),
    staff_rating INT CHECK (staff_rating >= 1 AND staff_rating <= 5),
    food_rating INT CHECK (food_rating >= 1 AND food_rating <= 5),

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Metadata
    metadata JSONB DEFAULT '{}'
);

-- Create indices for performance
CREATE INDEX idx_bookings_user_id ON bookings(user_id);
CREATE INDEX idx_bookings_status ON bookings(status);
CREATE INDEX idx_bookings_journey_date ON bookings(journey_date);
CREATE INDEX idx_bookings_train_number ON bookings(train_number);
CREATE INDEX idx_bookings_created_at ON bookings(created_at DESC);
CREATE INDEX idx_bookings_pnr ON bookings(pnr);

CREATE INDEX idx_payments_booking_id ON payments(booking_id);
CREATE INDEX idx_payments_status ON payments(status);
CREATE INDEX idx_payments_razorpay_order ON payments(razorpay_order_id);
CREATE INDEX idx_payments_razorpay_payment ON payments(razorpay_payment_id);
CREATE INDEX idx_payments_created_at ON payments(created_at DESC);

CREATE INDEX idx_tickets_booking_id ON tickets(booking_id);
CREATE INDEX idx_tickets_pnr ON tickets(pnr);
CREATE INDEX idx_tickets_irctc_status ON tickets(irctc_status);

CREATE INDEX idx_refunds_booking_id ON refunds(booking_id);
CREATE INDEX idx_refunds_status ON refunds(status);
CREATE INDEX idx_refunds_requested_at ON refunds(requested_at DESC);

CREATE INDEX idx_reviews_booking_id ON booking_reviews(booking_id);
CREATE INDEX idx_reviews_user_id ON booking_reviews(user_id);
CREATE INDEX idx_reviews_overall_rating ON booking_reviews(overall_rating);

-- Grant permissions (if using role-based access)
-- GRANT ALL ON bookings TO authenticated;
-- GRANT ALL ON payments TO authenticated;
-- GRANT ALL ON tickets TO authenticated;
-- GRANT ALL ON refunds TO authenticated;
-- GRANT ALL ON booking_reviews TO authenticated;
