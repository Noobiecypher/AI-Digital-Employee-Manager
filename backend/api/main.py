from fastapi import FastAPI

from backend.api.routes import router

app = FastAPI(
    title="AI Digital Employee Platform",
    version="1.0.0",
)

app.include_router(
    router,
    prefix="/workflows",
    tags=["workflows"],
)


@app.get("/health")
async def health():
    return {
        "status": "ok"
    }