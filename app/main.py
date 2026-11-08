from fastapi import FastAPI

app = FastAPI(
    title="ExamGuard AI",
    description="Intelligent Examination Platform",
    version="1.0.0"
)

@app.get("/")
def home():
    return {"message": "ExamGuard AI Backend Running"}

@app.get("/health")
def health():
    return {"status": "healthy"}
