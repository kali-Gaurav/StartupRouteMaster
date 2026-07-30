-- Database audit logging schema
-- Creates immutable audit_log table for tracking all mutations

CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,

    -- What changed
    table_name VARCHAR(255) NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    record_id VARCHAR(255),

    -- Who changed it
    user_id VARCHAR(255),
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45),
    session_id VARCHAR(255),

    -- What the values were
    before_values JSONB,
    after_values JSONB,

    -- Retention policy (days until auto-delete)
    retention_days INTEGER NOT NULL DEFAULT 30,

    -- Indexes for queryability
    CONSTRAINT audit_log_pkey PRIMARY KEY (id)
);

-- Create indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_audit_table_timestamp ON audit_log(table_name, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_user_timestamp ON audit_log(user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_operation ON audit_log(operation);
CREATE INDEX IF NOT EXISTS idx_audit_record_id ON audit_log(record_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp DESC);

-- Comment on table
COMMENT ON TABLE audit_log IS 'Immutable audit trail of all database mutations (INSERT, UPDATE, DELETE)';
COMMENT ON COLUMN audit_log.table_name IS 'Name of the table that was modified';
COMMENT ON COLUMN audit_log.operation IS 'Type of operation: INSERT, UPDATE, or DELETE';
COMMENT ON COLUMN audit_log.record_id IS 'Primary key of the modified record';
COMMENT ON COLUMN audit_log.user_id IS 'ID of user who made the change';
COMMENT ON COLUMN audit_log.timestamp IS 'When the change was made';
COMMENT ON COLUMN audit_log.ip_address IS 'IP address of the client';
COMMENT ON COLUMN audit_log.session_id IS 'Session ID if available';
COMMENT ON COLUMN audit_log.before_values IS 'Previous values (for UPDATE/DELETE)';
COMMENT ON COLUMN audit_log.after_values IS 'New values (for INSERT/UPDATE)';
COMMENT ON COLUMN audit_log.retention_days IS 'Days before this record is eligible for deletion';
