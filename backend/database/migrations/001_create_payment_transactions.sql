-- Migration: Create payment_transactions table
-- Task 1.1.4: Create payment_transactions table for payment reconciliation
-- Reference: REQ-011 (Payment Reconciliation)

-- Create payment_transactions table for storing all payment transactions
CREATE TABLE IF NOT EXISTS payment_transactions (
    payment_id VARCHAR(36) PRIMARY KEY,
    booking_id VARCHAR(36) REFERENCES bookings(id),
    amount DECIMAL(10, 2) NOT NULL,
    method VARCHAR(50) NOT NULL,  -- UPI, CARD, NET_BANKING, etc.
    status VARCHAR(50) NOT NULL DEFAULT 'pending',  -- pending, success, failed, refunded
    provider_reference VARCHAR(255),  -- Payment provider's transaction ID
    utr_number VARCHAR(50),  -- UPI Transaction Reference Number
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on payment_id for fast lookups
CREATE INDEX IF NOT EXISTS idx_payment_transactions_payment_id 
ON payment_transactions(payment_id);

-- Create index on booking_id for efficient reconciliation by booking
CREATE INDEX IF NOT EXISTS idx_payment_transactions_booking_id 
ON payment_transactions(booking_id);

-- Create index on utr_number for UPI reconciliation
CREATE INDEX IF NOT EXISTS idx_payment_transactions_utr_number 
ON payment_transactions(utr_number);

-- Create index on status for filtering transactions by status
CREATE INDEX IF NOT EXISTS idx_payment_transactions_status 
ON payment_transactions(status);

-- Create index on created_at for time-based queries
CREATE INDEX IF NOT EXISTS idx_payment_transactions_created_at 
ON payment_transactions(created_at);