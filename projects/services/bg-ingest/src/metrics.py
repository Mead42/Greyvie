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

# Optionally, add a function to expose all metrics for import
__all__ = [
    'dexcom_api_call_latency_seconds',
    'dexcom_api_call_total',
    'dexcom_api_rate_limit_events_total',
    'dexcom_api_retries_total',
    'dexcom_api_circuit_breaker_state',
] 