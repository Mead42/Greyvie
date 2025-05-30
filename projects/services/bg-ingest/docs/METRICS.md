# Prometheus Metrics for BG Ingest Service

This service exposes the following Prometheus metrics at `/metrics` (HTTP Basic Auth required).

| Metric Name                        | Type      | Labels                        | Description                                               |
|-------------------------------------|-----------|-------------------------------|-----------------------------------------------------------|
| `dexcom_api_call_latency_seconds`   | Histogram | `method`, `endpoint`          | Latency of Dexcom API calls in seconds                    |
| `dexcom_api_call_total`             | Counter   | `method`, `endpoint`, `status`| Total Dexcom API calls, labeled by method and status      |
| `dexcom_api_rate_limit_events_total`| Counter   | `endpoint`                    | Total Dexcom API rate limit events                        |
| `dexcom_api_retries_total`          | Counter   | `method`, `endpoint`          | Total Dexcom API request retries                          |
| `dexcom_api_circuit_breaker_state`  | Gauge     | `endpoint`                    | Circuit breaker state (0=closed, 1=open, 2=half-open)     |

## Metric Details

- **dexcom_api_call_latency_seconds**: Measures the time taken for each API call, useful for performance monitoring.
- **dexcom_api_call_total**: Counts all API calls, with labels for HTTP method, endpoint, and status (`success` or `error`).
- **dexcom_api_rate_limit_events_total**: Increments when the Dexcom API returns a rate limit error (HTTP 429).
- **dexcom_api_retries_total**: Increments each time a retry is attempted for a Dexcom API call.
- **dexcom_api_circuit_breaker_state**: Shows the current state of the circuit breaker for each endpoint.

## Accessing Metrics

- Metrics are available at: `GET /metrics` (HTTP Basic Auth required)
- Example Prometheus scrape config:

```yaml
scrape_configs:
  - job_name: 'bg-ingest'
    metrics_path: /metrics
    scheme: http
    static_configs:
      - targets: ['your-service-host:5001']
    basic_auth:
      username: your_metrics_username
      password: your_metrics_password
```

---

For questions or to add new metrics, see `src/metrics.py` and update this file accordingly. 