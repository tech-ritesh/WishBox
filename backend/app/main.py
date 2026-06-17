"""WishBox API — application factory and router wiring."""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.core.config import settings
from app.core.database import Base, engine
from app.api.routers import (
    admin, auth, cart, categories, engagement, hampers, orders, payments, products,
    storefront, wallet,
)
from app.services.worker import start_worker

# Local-dev convenience: ensure tables exist. Production uses Alembic (see alembic/).
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Background worker runs only for a real server (the test client doesn't
    # enter the lifespan context), so tests stay deterministic.
    if start_worker():
        print(f"[worker] started (interval={settings.WORKER_INTERVAL_SECONDS}s)")
    yield


app = FastAPI(
    title="WishBox API",
    description="Local-first gifting & hamper platform — successor to Celebration Box.",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")

API = "/api/v1"
for r in (auth, products, categories, cart, orders, payments, engagement, hampers, storefront, wallet, admin):
    app.include_router(r.router, prefix=API)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Consistent error envelope; avoid leaking internals.
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/api/health")
def health():
    return {"status": "ok", "version": __version__}


@app.get("/")
def root():
    return {"app": "WishBox API", "docs": "/docs", "health": "/api/health"}
