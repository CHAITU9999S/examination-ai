from fastapi import FastAPI

from app.routers import auth, questions, exams

app = FastAPI(
    title="ExamGuard AI",
    description="Intelligent Examination Platform",
    version="1.0.0"
)

app.include_router(auth.router)
app.include_router(questions.router)
app.include_router(exams.router)


@app.get("/")
def home():
    return {"message": "ExamGuard AI Backend Running"}


@app.get("/health")
def health():
    return {"status": "healthy"}
