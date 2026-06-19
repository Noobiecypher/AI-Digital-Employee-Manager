from fastapi import FastAPI

from backend.api.routes import router

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AI Digital Employee Platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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