
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    auth,
    users,
    admin,
    questions,
    exams,
    exam_sessions,
    answers,
    proctoring,
    grading,
)
from app.services.exam_scheduler import (
    start_exam_scheduler,
    stop_exam_scheduler,
)


# ==========================================
# APPLICATION CONFIGURATION
# ==========================================

APP_NAME = os.getenv("APP_NAME", "ExamGuard AI")
APP_ENV = os.getenv("APP_ENV", "development").lower()
DEBUG = APP_ENV == "development"

JWT_SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY",
    "development-only-secret-change-before-deployment"
)


# ==========================================
# APPLICATION LIFECYCLE
# ==========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""

    if APP_ENV == "production":
        if (
            JWT_SECRET_KEY
            == "development-only-secret-change-before-deployment"
            or len(JWT_SECRET_KEY) < 32
        ):
            raise RuntimeError(
                "Production requires a strong JWT_SECRET_KEY "
                "of at least 32 characters."
            )

    start_exam_scheduler()

    try:
        yield
    finally:
        stop_exam_scheduler()


# ==========================================
# CREATE FASTAPI APPLICATION
# ==========================================

app = FastAPI(
    title=APP_NAME,
    description=(
        "AI-Based Intelligent Examination Platform "
        "with Automated Proctoring and Candidate "
        "Performance Analysis."
    ),
    version="1.0.0",
    debug=DEBUG,
    lifespan=lifespan,
)


# ==========================================
# CORS CONFIGURATION
# ==========================================

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
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Admin-Bootstrap-Token",
    ],
)


# ==========================================
# REGISTER API ROUTERS
# ==========================================

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(admin.router)
app.include_router(questions.router)
app.include_router(exams.router)
app.include_router(exam_sessions.router)
app.include_router(answers.router)
app.include_router(answers.legacy_router)
app.include_router(proctoring.router)
app.include_router(grading.router)


# ==========================================
# ROOT ENDPOINT
# ==========================================

@app.get("/", tags=["General"])
def root():
    return {
        "message": "Welcome to ExamGuard AI",
        "application": APP_NAME,
        "environment": APP_ENV,
        "status": "running",
    }


# ==========================================
# HEALTH CHECK ENDPOINT
# ==========================================

@app.get("/health", tags=["General"])
def health_check():
    return {
        "status": "healthy",
        "application": APP_NAME,
    }
