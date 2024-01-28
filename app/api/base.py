from app.utils.scrapers.proxy import ProxyScraper
from app.utils.scrapers.news import NewsScraper, Provider, get_scraper_strategy
from app.database.database_utils import get_articles
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import app.backend.config as config
import os
import datetime

router = APIRouter()


@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(os.join.path(config.get_project_root(), "favicon.ico"))


@router.get("/")
def read_root():
    return {"Hello": "World"}


@router.get("/status")
def get_status():
    return {"status": "OK", "time": datetime.datetime.now()}


@router.get("/proxies")
def get_proxies() -> dict[str, list[str]]:
    return {"proxies": ProxyScraper().get_proxies()}


# Refactor this endpoint
@router.get("/download-db")
async def download_db():
    db_path = "newsmead.sqlite"
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Database not found")

    return FileResponse(
        db_path, media_type="application/octet-stream", filename="newsmead.sqlite"
    )
