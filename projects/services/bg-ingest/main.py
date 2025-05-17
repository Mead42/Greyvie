from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    print("Starting BG Ingest Service...")
    # Initialize DynamoDB connection
    # Initialize RabbitMQ connection
    yield
    # Shutdown logic
    print("Shutting down BG Ingest Service...")

app = FastAPI(
    title="BG Ingest Service",
    description="Service for ingesting blood glucose readings from CGM providers",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "bg-ingest"}

@app.get("/api/bg/{user_id}/latest")
async def get_latest_reading(user_id: str):
    # TODO: Implement fetching latest reading from DynamoDB
    return {"message": "Not implemented yet"}

@app.get("/api/bg/{user_id}")
async def get_readings(user_id: str, from_date: str = None, to_date: str = None):
    # TODO: Implement fetching readings with date range
    return {"message": "Not implemented yet"}

@app.post("/api/bg/{user_id}/webhook")
async def dexcom_webhook(user_id: str):
    # TODO: Implement webhook handler for Dexcom notifications
    return {"message": "Webhook received"}