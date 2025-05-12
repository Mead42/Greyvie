# Activity Sync Service

The **Activity Sync** microservice ingests and normalizes fitness-tracker data (steps, workouts, heart rate) from various providers (Fitbit, Google Fit, Apple HealthKit). It provides a unified API for downstream services (e.g., recommendation engine, ML pipeline) to query user activity data.

---

## 🚀 Overview

- **Language & Framework**: Node.js with Express
- **Key Responsibilities**:
  - Connect to third-party fitness APIs via OAuth or API keys
  - Poll or receive webhooks for activity data
  - Normalize data into a common schema and store in DynamoDB (time-series)
  - Expose RESTful endpoints for querying activity history

---

## 🔧 Prerequisites

- **Node.js** v14+
- **npm** or **yarn**
- **Local dependencies** (via Docker Compose):
  - DynamoDB Local
  - RabbitMQ (optional for event-driven ingestion)
- **Provider Developer Accounts** (for sandbox testing):
  - Fitbit (Client ID & Secret)
  - Google Cloud project with Fitness API enabled
  - Apple Developer account for HealthKit (if needed)

---

## ⚙️ Installation & Setup

1. **Clone the repo and install dependencies**
   ```bash
   cd services/activity-sync
   npm install
   ```

2. **Environment Variables**
   Copy `.env.example` to `.env` and configure:

   ```bash
   cp .env.example .env
   ```

   | Variable               | Description                                           |
   |------------------------|-------------------------------------------------------|
   | DYNAMODB_ENDPOINT      | DynamoDB Local URL (`http://dynamodb-local:8000`)     |
   | AWS_REGION             | AWS region (e.g., `us-east-1`)                        |
   | DYNAMODB_TABLE         | Table name for activity data                         |
   | RABBITMQ_URL           | AMQP URL for event broker (`amqp://guest:guest@...`) |
   | FITBIT_CLIENT_ID       | Fitbit OAuth Client ID                                |
   | FITBIT_CLIENT_SECRET   | Fitbit OAuth Client Secret                            |
   | GOOGLE_CLIENT_ID       | Google OAuth Client ID                                |
   | GOOGLE_CLIENT_SECRET   | Google OAuth Client Secret                            |
   | GOOGLE_REDIRECT_URI    | OAuth callback URI for Google Fit                     |
   | APPLE_TEAM_ID          | Apple Developer Team ID (for HealthKit)               |
   | APPLE_KEY_ID           | Apple API Key ID                                      |
   | APPLE_PRIVATE_KEY_PATH | Path to Apple private key file                        |

---

## 🏃‍♂️ Development

- **Start Service** (with hot-reload):
  ```bash
  npm run dev
  ```
  - Runs Express server on `localhost:5003` by default

- **Lint & Format**:
  ```bash
  npm run lint
  npm run format
  ```

- **Run Tests**:
  ```bash
  npm test
  ```

---

## 📦 Docker

1. **Build Image**:
   ```bash
   docker build -t diabetesai/activity-sync .
   ```

2. **Run Container**:
   ```bash
   docker run -p 5003:5003 \
     --env-file .env \
     diabetesai/activity-sync
   ```

3. **Compose**: This service is included in the monorepo’s `infra/docker-compose.yml`:
   ```yaml
   activity-sync:
     build:
       context: ../../services/activity-sync
     ports:
       - '5003:5003'
     env_file:
       - ../../.env
     depends_on:
       - dynamodb-local
   ```

---

## 📚 API Endpoints

- **GET /api/activity/:userId?from=&to=**
  - Returns activity records between `from` and `to` ISO timestamps.
  - Response:
    ```json
    [
      { "timestamp": "2025-04-25T12:00:00Z", "steps": 1200, "heartRate": 75 },
      ...
    ]
    ```

- **POST /api/activity/:userId/webhook**
  - Receives webhook events from providers (Fitbit, Google).
  - Validates signature, parses payload, and enqueues for normalization.

---

## 🧪 Testing

- **Unit Tests** (Jest + nock for HTTP mocks):
  ```bash
  npm test
  ```
- **Integration Tests** (with DynamoDB Local):
  ```bash
  npm run test:integration
  ```

---

## 🧑‍💻 Developer Notes

To harness **aider** for on-demand scaffolding, code hints, and architectural guidance within this service, run in the service directory:

```bash
aider --model o3 --architect
```
