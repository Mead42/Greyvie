from prometheus_client import Counter, Histogram, Gauge

# Histogram for API call latency (seconds)
dexcom_api_call_latency_seconds = Histogram(
    'dexcom_api_call_latency_seconds',
    'Latency of Dexcom API calls in seconds',
    ['method', 'endpoint']
)

# Counter for total API calls, labeled by method and status
# status: success, error
# method: GET, POST, etc.
dexcom_api_call_total = Counter(
    'dexcom_api_call_total',
    'Total Dexcom API calls',
    ['method', 'endpoint', 'status']
)

# Counter for rate limit events
dexcom_api_rate_limit_events_total = Counter(
    'dexcom_api_rate_limit_events_total',
    'Total Dexcom API rate limit events',
    ['endpoint']
)

# Counter for retries
dexcom_api_retries_total = Counter(
    'dexcom_api_retries_total',
    'Total Dexcom API request retries',
    ['method', 'endpoint']
)

# Gauge for circuit breaker state (0=closed, 1=open, 2=half-open)
dexcom_api_circuit_breaker_state = Gauge(
    'dexcom_api_circuit_breaker_state',
    'Dexcom API circuit breaker state',
    ['endpoint']
)

# === New Metrics ===
# Data volume processed (readings ingested)
readings_ingested_total = Counter(
    'readings_ingested_total',
    'Total number of blood glucose readings ingested',
    ['source']  # e.g., source could be 'dexcom', 'manual', etc.
)

# Webhook processing times and counts
webhook_processing_seconds = Histogram(
    'webhook_processing_seconds',
    'Time taken to process webhooks',
    ['webhook_type']
)
webhook_processed_total = Counter(
    'webhook_processed_total',
    'Total number of webhooks processed',
    ['webhook_type', 'status']  # status: success, error
)

# Sync job completion rates and durations
sync_job_completed_total = Counter(
    'sync_job_completed_total',
    'Total number of sync jobs completed',
    ['status']  # status: success, failed
)
sync_job_duration_seconds = Histogram(
    'sync_job_duration_seconds',
    'Duration of sync jobs in seconds',
    ['job_type']
)

__all__ = [
    'dexcom_api_call_latency_seconds',
    'dexcom_api_call_total',
    'dexcom_api_rate_limit_events_total',
    'dexcom_api_retries_total',
    'dexcom_api_circuit_breaker_state',
    'readings_ingested_total',
    'webhook_processing_seconds',
    'webhook_processed_total',
    'sync_job_completed_total',
    'sync_job_duration_seconds',
] 