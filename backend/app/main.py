from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.body_limit import RequestBodyLimitMiddleware
from app.core.config import settings
from app.pdf.runner import check_engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    # Warns when the PDF converter is missing; the application runs without it.
    await check_engine()
    yield


app = FastAPI(title="Ifrit API", lifespan=lifespan)

app.add_middleware(RequestBodyLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
