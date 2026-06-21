-- execution_sessions (added in V2) was meant as a durable observability record for Deferred
-- Eager sessions, but nothing in the application reads it — the actual session->container
-- registry lives in the Execution Service's in-memory registry, not here. Dropping rather
-- than building unused infrastructure ahead of an actual consumer (analytics/activity history).
DROP TABLE IF EXISTS execution_sessions;
