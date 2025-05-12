# BG Ingest Service

The **BG Ingest** microservice connects to Continuous Glucose Monitoring (CGM) providers (e.g., Dexcom) to fetch blood-glucose readings and persist them in a time-series datastore. This service powers the dashboard and ML pipelines with up-to-date BG data.

---

## 🚀 Overview

- **Language & Framework**: Python with FastAPI
- **Key Responsibilities**:
  - Perform OAuth2 flow against Dexcom (or other CGM) sandbox/production APIs
  - Poll or subscribe to webhook events for new BG readings
  - Normalize and store BG readings in DynamoDB (time-series)
  - Expose REST endpoints for downstream consumers (API gateway, ML training)

---

## 🔧 Prerequisites

- **Python** v3.11+
- **pip**
- **Local dependencies** (via Docker Compose):
  - DynamoDB Local
  - RabbitMQ (for event publishing)
- **Dexcom Developer Account** (sandbox or production)
  - Client ID & Secret

---

## ⚙️ Installation & Setup

1. **Clone & Install**
   ```bash
   cd services/bg-ingest
   pip install -r requirements.txt
   ```

2. **Environment Variables**
   Copy `.env.example` to `.env` and configure:
   ```bash
   cp .env.example .env
   ```

   | Variable                 | Description                                         |
   |--------------------------|-----------------------------------------------------|
   | DYNAMODB_ENDPOINT        | DynamoDB Local URL (`http://dynamodb-local:8000`)   |
   | AWS_REGION               | AWS region (e.g., `us-east-1`)                      |
   | DYNAMODB_TABLE           | Table name for BG readings                          |
   | RABBITMQ_URL             | AMQP URL for event broker (`amqp://guest:guest@...`)|
   | DEXCOM_CLIENT_ID         | Dexcom OAuth Client ID                              |
   | DEXCOM_CLIENT_SECRET     | Dexcom OAuth Client Secret                          |
   | DEXCOM_REDIRECT_URI      | OAuth callback URI for Dexcom                       |
   | DEXCOM_API_BASE_URL      | Dexcom API Base URL (sandbox or production)         |
   | POLL_INTERVAL_SECONDS    | How often to poll for new readings (default: 900)   |

---

## 🏃‍♂️ Development

- **Start in Dev Mode** (with auto-reload):
  ```bash
  uvicorn main:app --reload --host 0.0.0.0 --port 5001
  ```
  - Service listens on `localhost:5001` by default.

- **Lint & Format**:
  ```bash
  flake8 .
  black .
  ```

- **Run Tests**:
  ```bash
  pytest
  ```

---

## 📦 Docker

1. **Build Image**:
   ```bash
   docker build -t diabetesai/bg-ingest .
   ```

2. **Run Container**:
   ```bash
   docker run -p 5001:5001 \
     --env-file .env \
     diabetesai/bg-ingest
   ```

3. **Compose**: Included in monorepo’s `infra/docker-compose.yml`:
   ```yaml
   bg-ingest:
     build:
       context: ../../services/bg-ingest
     ports:
       - '5001:5001'
     env_file:
       - ../../.env.dev
     depends_on:
       - dynamodb-local
   ```

---

## 📚 API Endpoints

- **GET /api/bg/:userId/latest**
  - Returns the most recent BG reading:
    ```json
    { "timestamp": "2025-04-26T14:30:00Z", "glucose_mg_dl": 110 }
    ```

- **GET /api/bg/:userId?from=&to=**
  - Returns all readings in the specified range:
    ```json
    [
      { "timestamp": "2025-04-26T14:30:00Z", "glucose_mg_dl": 110 },
      { "timestamp": "2025-04-26T15:00:00Z", "glucose_mg_dl": 115 }
    ]
    ```

- **POST /api/bg/:userId/webhook**
  - Receive webhook notifications from Dexcom.
  - Validates signature, enqueues event, and stores the reading.

---

## 🧪 Testing

- **Unit Tests** (pytest + moto for AWS mocks):
  ```bash
  pytest
  ```
- **Integration Tests** (with DynamoDB Local):
  ```bash
  pytest --integration
  ```

---

## 🧑‍💻 Developer Notes

To leverage **aider** for scaffolding, code hints, and architectural guidance within this service, run in the service directory:

```bash
aider --model o3 --architect
```
