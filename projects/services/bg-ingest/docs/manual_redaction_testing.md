# Manual Testing: Redaction of Sensitive Data

This guide explains how to manually verify that sensitive data (e.g., passwords, API keys, tokens) are properly redacted from error responses and logs in the BG Ingest Service.

---

## 1. Start the FastAPI App

Run the app locally (from the project root):

```sh
uvicorn src.main:app --reload --port 5001
```

---

## 2. Test Error Responses for Redaction

### Example: Trigger a 404 Error with Sensitive Data

```sh
curl -X POST http://localhost:5001/api/bg/nonexistent \
  -H "Content-Type: application/json" \
  -d '{"password": "supersecret", "user": "bob"}'
```

**Expected:**
- The response should NOT include the actual password value.
- The field may be replaced with `"***REDACTED***"` or omitted, depending on error handler config.
- The username ("bob") may appear if not considered sensitive.

### Example: Trigger a 401/422 Error (if endpoint requires auth or invalid input)

```sh
curl -X POST http://localhost:5001/api/bg/test-ok \
  -H "Content-Type: application/json" \
  -d '{"password": "supersecret"}'
```

**Expected:**
- If the endpoint is protected, you may get a 401 Unauthorized.
- If the endpoint is public but input is invalid, you may get a 422 Unprocessable Entity.
- In all cases, sensitive fields should NOT appear in the error response.

---

## 3. Test Non-Error Responses (Should Not Be Redacted)

If you have a public endpoint that echoes data (for testing only):

```sh
curl -X POST http://localhost:5001/api/bg/test-ok \
  -H "Content-Type: application/json" \
  -d '{"password": "supersecret", "user": "bob"}'
```

**Expected:**
- The response should echo back the original data (no redaction for successful responses).

---

## 4. Check Logs (If Logging Request/Response Bodies)

- If you have enabled logging of request/response bodies, check your logs for redacted output.
- Sensitive fields should appear as `***REDACTED***` in logs.
- If not logging bodies, skip this step.

---

## 5. Security Notes
- Never log or expose real secrets in production.
- Always verify that error responses and logs are free of sensitive data before deploying.
- Use automated tests and CI/CD checks in addition to manual testing.

---

## 6. Troubleshooting
- If you see sensitive data in error responses or logs, check:
  - That the redaction utility is used in all error handlers and middleware.
  - That your logging configuration does not bypass redaction.
  - That you are not running an outdated version of the app.
- For protected endpoints, you may need to provide a valid JWT or adjust your test to use public endpoints.

---

For more details, see the implementation in [`src/utils/logging_utils.py`](../../src/utils/logging_utils.py) and the middleware in [`src/main.py`](../../src/main.py). 