"""
Schedule Optimizer — Backend API (FastAPI)

Web app đề xuất thời khóa biểu dựa trên file Excel + ràng buộc tín chỉ.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.api.routes import router as api_router
from app.services.prereq_graph import build_prereq_graph
from app.services.ranker import load_ranker


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Warm immutable graph/model singletons before serving requests."""
    build_prereq_graph()
    load_ranker()
    yield

# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Schedule Optimizer API",
    description="Hệ thống đề xuất thời khóa biểu dựa trên file Excel và ràng buộc tín chỉ.",
    version="0.1.0",
    lifespan=lifespan,
)

# ── Templates & Static ─────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BASE_DIR.parent / "frontend" / "templates"
STATIC_DIR = BASE_DIR.parent / "frontend" / "static"

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ── Routes ─────────────────────────────────────────────────────────────────────

app.include_router(api_router)
