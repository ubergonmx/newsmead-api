from app.utils.scrapers.proxy import ProxyScraper
from app.utils.scrapers.news import NewsScraper, Provider, get_scraper_strategy
from app.database.database_utils import get_articles
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os
import time

router = APIRouter()


@router.get("/")
def read_root():
    return {"Hello": "World"}


@router.get("/status")
def get_status():
    # return datetime.time (get current time of server)
    return {"status": "OK", "time": time.time()}


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
        db_path, media_type="routerlication/octet-stream", filename="newsmead.sqlite"
    )


# Get articles
@router.get("/articles")
def get_articles():
    # [ ] TODO: Add pagination
    articles = get_articles(None)
    return {"total": len(articles), "articles": articles}
