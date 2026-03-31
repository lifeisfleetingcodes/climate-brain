"""ClimateBrain — AI-powered multi-person comfort controller.

Run with:
    python -m climate_brain.main
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from climate_brain.config import settings
from climate_brain.db.database import init_db
from climate_brain.scheduler import start_scheduler, stop_scheduler
from climate_brain.api.routes_rooms import router as rooms_router
from climate_brain.api.routes_people import router as people_router
from climate_brain.api.routes_status import router as status_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[ClimateBrain] Initializing database...")
    await init_db()
    print("[ClimateBrain] Starting scheduler...")
    start_scheduler()
    print(f"[ClimateBrain] Ready! Web UI at http://{settings.host}:{settings.port}")
    yield
    stop_scheduler()
    print("[ClimateBrain] Shut down.")


app = FastAPI(
    title="ClimateBrain",
    description="AI-powered multi-person comfort controller for air conditioners",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(rooms_router)
app.include_router(people_router)
app.include_router(status_router)

WEB_DIR = Path(__file__).parent.parent / "web_ui"
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/")
async def serve_ui():
    index = WEB_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"message": "ClimateBrain API running. See /docs for API documentation."}


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("climate_brain.main:app", host=settings.host, port=settings.port, reload=settings.debug)
