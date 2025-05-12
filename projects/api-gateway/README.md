# API Gateway Service

The **API Gateway** acts as the single entry point for all client traffic (web, mobile, third‑party) and orchestrates calls to underlying microservices (BG ingest, food recognition, activity sync, recommendation engine).

---

## 🚀 Overview

- **Language & Framework**: Node.js with Express (REST) and Apollo Server (GraphQL)
- **Responsibilities**:
  - Authentication & authorization (JWT, AWS Cognito)
  - Routing & aggregation of microservice calls
  - Input validation, rate limiting, error handling
  - Exposing OpenAPI (REST) and GraphQL schemas

---

## 🔧 Prerequisites

- **Node.js** v14+
- **npm** or **yarn**
- Running dependencies (via `docker-compose` or local instances):
  - PostgreSQL
  - DynamoDB Local (or real endpoint)
  - MinIO (S3 emulator) or AWS S3
  - RabbitMQ (or Kafka)

---

## ⚙️ Installation

1. **Clone & Install**
   ```bash
   cd api-gateway
   npm install
   ```

2. **Environment Variables**
   Copy `.env.example` to `.env` and fill in values:

   ```bash
   cp .env.example .env
   ```

   | Variable                     | Description                                      |
   |------------------------------|--------------------------------------------------|
   | DB_HOST                      | PostgreSQL host (e.g. `postgres`)                |
   | DB_PORT                      | PostgreSQL port (e.g. `5432`)                    |
   | DB_USER                      | PostgreSQL username (`dev`)                      |
   | DB_PASS                      | PostgreSQL password (`devpass`)                  |
   | DB_NAME                      | Database name (`devdb`)                          |
   | DYNAMODB_ENDPOINT            | DynamoDB endpoint URL (local or AWS)             |
   | S3_ENDPOINT                  | S3-compatible endpoint (MinIO or AWS S3)         |
   | S3_ACCESS_KEY_ID             | AWS or MinIO access key                          |
   | S3_SECRET_ACCESS_KEY         | AWS or MinIO secret key                          |
   | RABBITMQ_URL                 | AMQP connection string (`amqp://guest:guest@...`)|
   | COGNITO_USER_POOL_ID         | AWS Cognito User Pool Id                         |
   | COGNITO_CLIENT_ID            | AWS Cognito App Client Id                        |
   | COGNITO_REGION               | AWS region for Cognito                           |
   | DEXCOM_CLIENT_ID             | Dexcom API Client ID                             |
   | DEXCOM_CLIENT_SECRET         | Dexcom API Client Secret                         |
   | DEXCOM_REDIRECT_URI          | OAuth callback URI for Dexcom                    |

---

## 🏃‍♂️ Development

- **Start in Dev Mode** (with hot reload):
  ```bash
  npm run dev
  ```
  - Express & Apollo live‑reload on file changes

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

## 📦 Production

- **Build**:
  ```bash
  npm run build
  ```
- **Start**:
  ```bash
  npm start
  ```

- **Docker**:
  ```bash
  docker build -t diabetesai/api-gateway .
  docker run -p 4000:4000 \
    --env-file .env \
    diabetesai/api-gateway
  ```

---

## 📚 API Documentation

- **GraphQL Playground**: `http://localhost:4000/graphql`
- **REST Swagger UI**: `http://localhost:4000/docs`

Schemas and endpoint definitions are kept in `src/graphql/schema/` and `src/routes/` respectively.

---

## 🧪 Testing

- **Unit Tests** (Jest):
  ```bash
  npm test
  ```
- **Integration Tests** (Supertest + local Docker compose):
  ```bash
  npm run test:integration
  ```

---

## 🧑‍💻 Developer Notes

To leverage **aider** for scaffolding, code suggestions, and architecture guidance within this service, run from the service root:

```bash
aider --model o3 --architect
```
