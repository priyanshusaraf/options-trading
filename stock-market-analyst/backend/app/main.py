"""
Stock Market Intelligence Platform — FastAPI Application Entry Point
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.core.config import get_settings
from backend.app.core.logging import configure_logging, logger
from backend.app.core.scheduler import get_scheduler
from backend.app.data.models.database import init_db
from backend.app.api.routes import (
    watchlist_router, analysis_router, data_router,
    intelligence_router, portfolio_router, options_router, commodities_router,
    alerts_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info("Starting Stock Market Intelligence Platform...")
    settings = get_settings()
    settings.ensure_dirs()
    init_db()
    logger.info(f"Database initialized at {settings.sqlite_path}")

    # Start background scheduler
    scheduler = get_scheduler()
    scheduler.start()
    logger.info("Background scheduler started — jobs: " +
                ", ".join(j.name for j in scheduler.get_jobs()))

    logger.info("System ready.")
    yield

    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped.")
    logger.info("Shutting down...")


app = FastAPI(
    title="Stock Market Intelligence Platform",
    description="""
    A research-grade, modular stock market intelligence system.
    
    Combines quantitative finance, technical analysis, macro data, 
    NLP-driven news analysis, and graph-based supply chain modeling.
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(watchlist_router, prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")
app.include_router(data_router, prefix="/api/v1")
app.include_router(intelligence_router, prefix="/api/v1")
app.include_router(portfolio_router, prefix="/api/v1")
app.include_router(options_router, prefix="/api/v1")
app.include_router(commodities_router, prefix="/api/v1")
app.include_router(alerts_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
def root():
    return {"status": "ok", "service": "Stock Market Intelligence Platform", "version": "1.0.0"}


@app.get("/health", tags=["System"])
def health():
    settings = get_settings()
    return {
        "status": "healthy",
        "benchmark": settings.benchmark_symbol,
        "data_dir": str(settings.data_dir),
        "api_keys": {
            "alpha_vantage": bool(settings.alpha_vantage_key),
            "finnhub": bool(settings.finnhub_key),
            "fmp": bool(settings.fmp_key),
            "fred": bool(settings.fred_key),
            "kite": bool(settings.kite_api_key),
        },
    }


@app.get("/scheduler/jobs", tags=["System"])
def scheduler_jobs():
    """List all scheduled background jobs and their next run times."""
    scheduler = get_scheduler()
    return {
        "running": scheduler.running,
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            }
            for job in scheduler.get_jobs()
        ],
    }


@app.post("/scheduler/run/{job_id}", tags=["System"])
async def run_job_now(job_id: str):
    """Manually trigger a scheduled job immediately."""
    import asyncio
    job_map = {
        "ohlcv_refresh": "backend.app.core.scheduler.job_refresh_ohlcv",
        "score_computation": "backend.app.core.scheduler.job_compute_scores",
        "news_refresh": "backend.app.core.scheduler.job_refresh_news",
        "macro_refresh": "backend.app.core.scheduler.job_refresh_macro",
        "calendar_refresh": "backend.app.core.scheduler.job_refresh_calendar",
        "alert_checker": "backend.app.core.scheduler.job_check_alerts",
    }
    from fastapi import HTTPException
    if job_id not in job_map:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    from importlib import import_module
    module_path, func_name = job_map[job_id].rsplit(".", 1)
    mod = import_module(module_path)
    func = getattr(mod, func_name)
    asyncio.create_task(func())
    return {"message": f"Job '{job_id}' triggered", "job_id": job_id}
