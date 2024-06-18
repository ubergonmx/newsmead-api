from typing import Callable
from app.core.recommender import Recommender
from app.database.asyncdb import AsyncDatabase, get_db
from app.utils.scrapers import news
from app.utils.scrapers.proxy import ProxyScraper
from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    Request,
    UploadFile,
    File,
    Query,
    Depends,
)
from fastapi.responses import FileResponse, RedirectResponse
import app.backend.config as config
import os
import logging
import datetime
import aiofiles
import httpx

router = APIRouter()
log = logging.getLogger(__name__)


@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(os.path.join(config.get_project_root(), "favicon.ico"))


@router.get("/")
def read_root():
    return RedirectResponse(url="https://newsmead-docs.vercel.app")


@router.get("/status")
def get_status():
    return {"status": "OK", "time": datetime.datetime.now()}


@router.get("/proxies")
def get_proxies() -> dict[str, list[str]]:
    return {"proxies": ProxyScraper().get_proxies()}


def verify_key(key: str = Query(...)):
    if key != os.getenv("SECRET_KEY"):
        raise HTTPException(status_code=403, detail="Invalid keyphrase")
    return key


async def add_task(background_tasks: BackgroundTasks, func: Callable, *args, **kwargs):
    async def wrapper():
        await func(*args, **kwargs)

    background_tasks.add_task(wrapper)


@router.get("/download-db", include_in_schema=False)
async def download_db(key: str = Depends(verify_key)):
    db_path = os.path.join(config.get_project_root(), os.getenv("DB_NAME"))
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Database not found")

    return FileResponse(
        db_path, media_type="application/octet-stream", filename=os.getenv("DB_NAME")
    )


@router.post("/upload-db", include_in_schema=False)
async def create_upload_db(
    file: UploadFile = File(...), key: str = Depends(verify_key)
):
    if file.filename == os.getenv("DB_NAME"):
        raise HTTPException(
            status_code=400, detail="Cannot upload database with same name"
        )
    filepath = os.path.join(config.get_project_root(), file.filename)
    with open(filepath, "wb") as f:
        f.write(file.file.read())
    return {"message": "Database uploaded successfully"}


async def sync(recommender: Recommender, db: AsyncDatabase):
    try:
        if os.getenv("MODEL_LANG") == "en":
            log.info("Skipping sync")
        log.info("Syncing news...")
        db_name = os.getenv("DB_NAME")
        # if os.path.exists(os.path.join(config.get_project_root(), db_name)):
        #     db_name = "newsmead-en.sqlite"

        second_db = os.path.join(config.get_project_root(), db_name)
        async with httpx.AsyncClient() as client:
            orig_db = await client.get(
                "https://newsmead.southeastasia.cloudapp.azure.com/download-db",
                params={"key": os.getenv("SECRET_KEY")},
            )
            async with aiofiles.open(second_db, "wb") as f:
                await f.write(orig_db.content)

        # await db.merge_articles(second_db)
        await recommender.save_news(db)
        recommender.load_news()
        log.info("News synced successfully")
    except Exception as e:
        log.error(f"Error syncing news: {e}")
        log.error(f"Traceback: {e.__traceback__.tb_lasti}")


@router.get("/sync-news")
async def sync_news(
    bg: BackgroundTasks,
    request: Request,
    db: AsyncDatabase = Depends(get_db),
    key: str = Depends(verify_key),
):
    await add_task(bg, sync, request.app.state.recommender, db)
    return {"message": "Syncing news started"}


@router.get("/download-news", include_in_schema=False)
async def download_news(key: str = Depends(verify_key)):
    news_path = os.path.join(
        config.get_project_root(), "app", "core", "recommender_utils", "news.tsv"
    )
    return FileResponse(
        news_path, media_type="application/octet-stream", filename="news.tsv"
    )


@router.get("/download-logs", include_in_schema=False)
async def download_log(key: str = Depends(verify_key)):
    log_dir = config.get_log_dir()
    log_zip = os.path.join(config.get_project_root(), "logs.zip")
    config.create_zip(log_dir, log_zip)
    return FileResponse(
        log_zip, media_type="application/octet-stream", filename="logs.zip"
    )


@router.get("/download-sources", include_in_schema=False)
async def download_sources(key: str = Depends(verify_key)):
    sources_dir = config.get_sources_dir()
    sources_zip = os.path.join(config.get_project_root(), "sources.zip")
    config.create_zip(sources_dir, sources_zip)
    return FileResponse(
        sources_zip, media_type="application/octet-stream", filename="sources.zip"
    )


# TO BE REMOVED
async def ts(recommender: Recommender, db: AsyncDatabase):
    log.info("Scraping Abante News...")
    proxy = ProxyScraper()
    while proxy.get_proxies() == []:
        await proxy.scrape_proxies()
    async with AsyncDatabase() as db:
        provider = news.Provider.AbanteNews
        scraper_strategy = news.get_scraper_strategy(provider)
        news_scraper = news.NewsScraper(scraper_strategy)
        for category in news.Category:
            articles = await news_scraper.scrape_category(category, proxy)
            await db.insert_articles(articles)
        await recommender.save_news(db)
    recommender.load_news()
    async with httpx.AsyncClient() as client:
        await client.get(
            "https://newsmead-fil.southeastasia.cloudapp.azure.com/sync-news",
            params={"key": os.getenv("SECRET_KEY")},
        )
    log.info("Abante News scraped. TS complete.")


@router.get("/ts", include_in_schema=False)
async def test_scrape(
    bg: BackgroundTasks, request: Request, db: AsyncDatabase = Depends(get_db)
):
    await add_task(bg, ts, request.app.state.recommender, db)
    return {"message": "Scraping started"}
