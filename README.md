# GreyVie AI

A monorepo for a SaaS platform that helps users monitor carbohydrate and calorie intake, activity levels, and blood glucose (BG) data—leveraging machine learning to forecast BG and provide actionable meal and activity recommendations.

---

## 🚀 Repository Overview

```
/project-root
├── api-gateway/          # REST/GraphQL API (Node.js/Express)
├── services/
│   ├── bg-ingest/        # Dexcom CGM integration (Python)
│   ├── food-recognize/   # Food image recognition (Python)
│   └── activity-sync/    # Fitness-tracker stubs (Node.js)
├── web-ui/               # React application
├── ml-training/          # Jupyter notebooks & training scripts (TF/PyTorch)
├── infra/                # Docker Compose and local emulators
└── README.md
```

---

## 🔧 Prerequisites

- **Docker** (v20.10+) and **Docker Compose**
- **Node.js** (v14+)
- **Python** (v3.11+)
- Credentials for:
  - Dexcom Developer Sandbox
  - USDA FoodData Central or Edamam API (free tier)

---

## 🧑‍💻 Developer Notes

This project integrates with **aider**, a CLI-based developer assistant for scaffolding and code guidance. To start **aider** in the root of this repository, run:

```bash
aider --model o3 --architect
```

---

## 🏁 Getting Started

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/DiabetesAI.git
   cd DiabetesAI
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your sandbox API keys and dev settings
   ```

3. **Launch local dependencies & services**
   ```bash
   cd infra
   docker-compose up --build
   ```

4. **Run individual services (optional)**
   In separate terminals, you may start services with hot-reload:
   ```bash
   # API Gateway
   cd api-gateway && npm install && npm run dev

   # BG Ingest Service
   cd services/bg-ingest && pip install -r requirements.txt && uvicorn main:app --reload

   # Food Recognize Service
   cd services/food-recognize && npm install && npm run dev

   # Activity Sync Service
   cd services/activity-sync && npm install && npm run dev

   # Web UI
   cd web-ui && npm install && npm start
   ```

5. **Access the applications**
   - Web UI:       `http://localhost:3000`
   - API Gateway:  `http://localhost:4000` (REST/GraphQL playground at `/graphql` or `/docs`)
   - Postgres CLI: `psql -h localhost -U dev -d devdb`
   - MinIO Console: `http://localhost:9000` (user: `minioadmin` / pass: `minioadmin`)
   - RabbitMQ UI:   `http://localhost:15672` (guest/guest)

---

## 📁 Project Structure

- **api-gateway**: Entry point for all client traffic; aggregates microservice responses.
- **services**: Core backend microservices:
  - **bg-ingest**: Fetches CGM data from Dexcom Sandbox.
  - **food-recognize**: Runs CV model and nutrition lookup.
  - **activity-sync**: Simulates or ingests fitness-tracker data.
- **web-ui**: Frontend dashboard and entry forms.
- **ml-training**: Notebooks and scripts to train and evaluate BG forecasting models.
- **infra**: Local emulators (`docker-compose.yml`) for Postgres, DynamoDB Local, MinIO, RabbitMQ.

---

## 🛠️ Development Workflow

1. **Feature Branch**: Create a branch off `main` for each feature:
   ```bash
   git checkout -b feature/<short-description>
   ```
2. **Code & Tests**: Implement feature, add unit/integration tests.
3. **Commit & Push**:
   ```bash
   git add .
   git commit -m "feat(bg-ingest): add Dexcom token refresh"
   git push origin feature/<short-description>
   ```
4. **Pull Request**: Open a PR targeting `main`. Include reviewers and link relevant user stories.
5. **CI/CD**: On merge, GitHub Actions runs tests, builds Docker images, and (in production) deploys to EKS.

---

## 🔁 CI/CD

We use **GitHub Actions** to:
- Lint & unit-test each service.
- Build Docker images and push to ECR.
- Deploy to EKS (staging/production) on `main` branch.

Refer to `.github/workflows/` for workflow definitions.

