
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers import (
    auth,
    questions,
    exams,
    exam_sessions,
    answers,
    admin
)

from app.services.exam_scheduler import (
    start_exam_scheduler,
    stop_exam_scheduler
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start automatic exam submission scheduler.
    start_exam_scheduler()

    yield

    # Stop scheduler during application shutdown.
    stop_exam_scheduler()


app = FastAPI(
    title="ExamGuard AI",
    description="Intelligent Examination Platform",
    version="1.0.0",
    lifespan=lifespan
)


# Authentication
app.include_router(auth.router)

# Question Bank
app.include_router(questions.router)

# Exam Configuration
app.include_router(exams.router)

# Exam Sessions
app.include_router(exam_sessions.router)

# Student Answers
app.include_router(answers.router)

# Admin Management
app.include_router(admin.router)


@app.get("/")
def home():
    return {
        "message": "ExamGuard AI Backend Running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
}
    
