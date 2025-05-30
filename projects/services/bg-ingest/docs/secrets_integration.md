# Integrating Secure Secrets Management in Your Service

This guide explains how to use the `get_secret` abstraction from [`src/utils/secrets.py`](../../src/utils/secrets.py) to securely access API keys and sensitive credentials in your FastAPI services and endpoints.

---

## Why Use `get_secret`?
- **Security:** Avoids hardcoding secrets in code or config files.
- **Flexibility:** Uses environment variables for local/dev, AWS Secrets Manager in production.
- **Performance:** Caches secrets in memory to minimize API calls.

---

## When to Use
- Whenever you need to access an API key, database password, or any sensitive credential in your application code.
- Recommended for all new and existing services/endpoints that require secrets.

---

## Example: Using `get_secret` in a Service

```python
from src.utils.secrets import get_secret

def get_external_api_client():
    api_key = get_secret("EXTERNAL_API_KEY")
    # Use api_key to initialize your client
    client = ExternalApiClient(api_key=api_key)
    return client
```

---

## Example: Using `get_secret` in a FastAPI Endpoint

```python
from fastapi import APIRouter, HTTPException
from src.utils.secrets import get_secret

router = APIRouter()

@router.get("/secure-data")
def get_secure_data():
    try:
        secret_token = get_secret("MY_SECRET_TOKEN")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    # Use secret_token to access a protected resource
    return {"message": "Accessed secure data!"}
```

---

## Security Best Practices
- **Never log or print secrets.**
- **Restrict IAM permissions** for the app in production to only the secrets it needs.
- **Do not commit `.env` files** or any file containing secrets to version control.
- **Rotate secrets regularly** and update them in the secrets manager and environment.

---

## Troubleshooting
- If you see `RuntimeError: Secret 'KEY' not found...`, check:
  - The environment variable is set (for local/dev)
  - The secret exists in AWS Secrets Manager (for production)
  - The app has correct IAM permissions
  - The `secret_name` and `aws_region` are set in your config
- For local development, add secrets to your `.env` file:
  ```env
  MY_SECRET_TOKEN=dev-token-123
  ```

---

## Reference
- Implementation: [`src/utils/secrets.py`](../../src/utils/secrets.py)
- Configuration: [`src/utils/config.py`](../../src/utils/config.py) 