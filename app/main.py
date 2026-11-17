
from fastapi import FastAPI

from app.routers import (
    auth,
    questions,
    exams,
    exam_sessions,
    admin
)


app = FastAPI(
    title="ExamGuard AI",
    description="Intelligent Examination Platform",
    version="1.0.0"
)


# Authentication
app.include_router(auth.router)

# Question Bank
app.include_router(questions.router)

# Exam Configuration
app.include_router(exams.router)

# Exam Sessions
app.include_router(exam_sessions.router)

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
    
