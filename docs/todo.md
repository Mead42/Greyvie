# TODO Tasks

This document tracks tasks and features that are planned for future implementation but are not yet scheduled or in progress.

## How to Use
- Add new TODOs as checklist items below.
- Move completed items to the project changelog or mark as done.

## TODO Checklist

- [ ] Increment or observe these metrics in your ingestion, webhook, and sync job logic at the appropriate points
    - [ ] Increment `readings_ingested_total` in ingestion logic when a new reading is processed.
      ```python
      from src.metrics import readings_ingested_total
      readings_ingested_total.labels(source='dexcom').inc()
      ```
    - [ ] Observe `webhook_processing_seconds` and increment `webhook_processed_total` in webhook handler.
      ```python
      from src.metrics import webhook_processing_seconds, webhook_processed_total
      import time

      def handle_webhook(webhook_type, ...):
          start = time.perf_counter()
          try:
              # ... process webhook ...
              webhook_processed_total.labels(webhook_type=webhook_type, status='success').inc()
          except Exception:
              webhook_processed_total.labels(webhook_type=webhook_type, status='error').inc()
              raise
          finally:
              duration = time.perf_counter() - start
              webhook_processing_seconds.labels(webhook_type=webhook_type).observe(duration)
      ```
    - [ ] Increment `sync_job_completed_total` and observe `sync_job_duration_seconds` in sync job completion logic.
      ```python
      from src.metrics import sync_job_completed_total, sync_job_duration_seconds
      import time

      def run_sync_job(job_type, ...):
          start = time.perf_counter()
          status = 'success'
          try:
              # ... run sync job ...
              pass
          except Exception:
              status = 'failed'
              raise
          finally:
              duration = time.perf_counter() - start
              sync_job_completed_total.labels(status=status).inc()
              sync_job_duration_seconds.labels(job_type=job_type).observe(duration)
      ```

<!-- Add new TODOs below --> 