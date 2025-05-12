# Food Recognize Service

The **Food Recognize** microservice ingests meal images, runs a computer-vision model to detect food items, and queries a nutrition API to estimate carbohydrate and calorie content. This service provides the meal-logging backbone for the SaaS application.

---

## 🚀 Overview

- **Language & Framework**: Python with FastAPI
- **Key Responsibilities**:
  - Receive image uploads of meals
  - Run a pretrained TensorFlow/PyTorch model to detect foods
  - Query a nutrition API (USDA FoodData Central, Edamam) for carb/calorie data
  - Publish detection events for logging and downstream processing

---

## 🔧 Prerequisites

- **Python** v3.11+
- **pip**
- Local dev dependencies (via Docker Compose):
  - MinIO (S3 emulator) or real S3
  - RabbitMQ (for event messages)
- **Nutrition API Key** (free tier):
  - USDA FoodData Central or Edamam credentials

---

## ⚙️ Installation & Setup

1. **Clone & Install**
   ```bash
   cd services/food-recognize
   pip install -r requirements.txt
   ```

2. **Environment Variables**
   Copy `.env.example` to `.env` and configure:
   ```bash
   cp .env.example .env
   ```

   | Variable               | Description                                         |
   |------------------------|-----------------------------------------------------|
   | S3_ENDPOINT            | MinIO or AWS S3 endpoint (`http://minio:9000`)      |
   | S3_ACCESS_KEY_ID       | AWS/MinIO access key                                |
   | S3_SECRET_ACCESS_KEY   | AWS/MinIO secret key                                |
   | NUTRITION_API_KEY      | USDA or Edamam API key                              |
   | NUTRITION_API_URL      | Base URL for nutrition lookup API                   |
   | RABBITMQ_URL           | AMQP URL for event broker (`amqp://guest:guest@...`)|

---

## 🏃‍♂️ Development

- **Run Locally** (with hot-reload):
  ```bash
  uvicorn main:app --reload --host 0.0.0.0 --port 5002
  ```

- **Lint & Format**:
  ```bash
  flake8 .
  black .
  ```

- **Unit Tests**:
  ```bash
  pytest
  ```

---

## 📦 Docker

1. **Build Image**:
   ```bash
   docker build -t diabetesai/food-recognize .
   ```

2. **Run Container**:
   ```bash
   docker run -p 5002:5002 \
     --env-file .env \
     diabetesai/food-recognize
   ```

3. **Compose**: Included in monorepo’s `infra/docker-compose.yml`:
   ```yaml
   food-recognize:
     build:
       context: ../../services/food-recognize
     ports:
       - '5002:5002'
     env_file:
       - ../../.env
     depends_on:
       - minio
   ```

---

## 📚 API Endpoints

- **POST /api/food/recognize**
  - Accepts `multipart/form-data` with field `photo`.
  - Returns detected items:
    ```json
    [
      { "name": "Grilled Chicken", "carbs_g": 0, "calories_kcal": 165, "confidence": 0.93 },
      { "name": "Steamed Broccoli", "carbs_g": 6, "calories_kcal": 55, "confidence": 0.87 }
    ]
    ```

- **GET /api/food/{userId}/meals**
  - Retrieves logged meals for a user.

---

## 🧪 Testing

- **Unit Tests** (pytest):
  ```bash
  pytest
  ```

- **Integration Tests** (with MinIO & RabbitMQ):
  ```bash
  pytest --integration
  ```

---

## 🧑‍💻 Developer Notes

To use **aider** for scaffolding and architecture guidance in this service directory, run:

```bash
aider --model o3 --architect
```
