import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.api.business_routes import business_router
from backend.api.auth_routes import auth_router
from backend.database.mongo import close_client, get_client

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        get_client()
        logger.info("MongoDB connection verified at startup.")
    except RuntimeError as exc:
        logger.critical(
            "MongoDB unavailable — server will not start. Detail: %s",
            exc,
        )
        raise

    yield

    close_client()


app = FastAPI(
    title="AI Digital Employee Platform",
    version="1.0.0",
    lifespan=lifespan,
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

app.include_router(
    business_router,
    prefix="/api",
    tags=["business-data"],
)

app.include_router(
    auth_router,
    prefix="/auth",
    tags=["authentication"]
)


@app.get("/health")
async def health():
    return {
        "status": "ok"
    }