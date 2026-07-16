from fastapi import FastAPI
from contextlib import asynccontextmanager
from api.database import get_pool, close_pool
from api.routers import metrics  

@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()
    yield
    await close_pool()

app = FastAPI(
    title="SaaS Metrics API",
    description="HTTP endpoints for SaaS subscription analytics",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(metrics.router)       

@app.get("/")
async def root():
    return {
        "name": "SaaS Metrics API",
        "version": "1.0.0",
        "endpoints": [
            "/metrics/mrr",
            "/metrics/churn",
            "/metrics/ltv",
            "/metrics/arpu",
            "/metrics/nrr",
            "/metrics/mrr-movement",
            "/customers",
        ]
    }