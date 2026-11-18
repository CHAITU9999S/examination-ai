import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


# -----------------------------------------
# APPLICATION CONFIGURATION
# -----------------------------------------

APP_NAME = os.getenv(
    "APP_NAME",
    "ExamGuard AI"
)

APP_ENV = os.getenv(
    "APP_ENV",
    "development"
)

DEBUG = APP_ENV == "development"


# -----------------------------------------
# CREATE FASTAPI APPLICATION
# -----------------------------------------

app = FastAPI(
    title=APP_NAME,
    description=(
        "AI-Based Intelligent Examination Platform "
        "with Automated Proctoring and Candidate "
        "Performance Analysis."
    ),
    version="1.0.0",
    debug=DEBUG
)


# -----------------------------------------
# CORS CONFIGURATION
# -----------------------------------------

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000"
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


# -----------------------------------------
# ROOT ENDPOINT
# -----------------------------------------

@app.get("/", tags=["General"])
def root():
    return {
        "message": "Welcome to ExamGuard AI",
        "application": APP_NAME,
        "environment": APP_ENV,
        "status": "running"
    }


# -----------------------------------------
# HEALTH CHECK ENDPOINT
# -----------------------------------------

@app.get("/health", tags=["General"])
def health_check():
    return {
        "status": "healthy",
        "application": APP_NAME
}
