from fastapi import FastAPI

app = FastAPI(title="JobTracker API")


@app.get("/health")
def health():
    return {"status": "ok"}
@app.get("/get_jobs")
def get_jobs():
    return {"jobs": []}
