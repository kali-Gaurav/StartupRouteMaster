-- Migration: Create notification_logs table
-- Task 1.1.5: Create notification_logs table for notification retry logic
-- Reference: REQ-015 (Notification Retry Logic)

-- Create notification_logs table for tracking notification delivery
CREATE TABLE IF NOT EXISTS notification_logs (
    notification_id VARCHAR(36) PRIMARY KEY,
    booking_id VARCHAR(36) REFERENCES bookings(id),
    channel VARCHAR(20) NOT NULL,  -- SMS, EMAIL, PUSH
    status VARCHAR(50) NOT NULL DEFAULT 'pending',  -- pending, sent, delivered, failed
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on booking_id for efficient querying by booking
CREATE INDEX IF NOT EXISTS idx_notification_logs_booking_id 
ON notification_logs(booking_id);

-- Create index on status for efficient retry processing
CREATE INDEX IF NOT EXISTS idx_notification_logs_status 
ON notification_logs(status);

-- Create index on created_at for time-based queries and monitoring
CREATE INDEX IF NOT EXISTS idx_notification_logs_created_at 
ON notification_logs(created_at);

-- Create index on channel for filtering by notification channel
CREATE INDEX IF NOT EXISTS idx_notification_logs_channel 
ON notification_logs(channel);