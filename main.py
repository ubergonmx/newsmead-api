from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Request
from proxyscraper import ProxyScraper
from newsscraper import NewsScraper, Provider, get_scraper_strategy, GMANewsScraper
from database_utils import (
    insert_articles,
    get_articles,
    get_articles_by_provider,
    delete_empty_body_by_provider,
)
import sqlite3
import logging.config
import random
import string
import time
import os

# [ ] TODO: Add metadata tags & icon for /docs endpoint
# [ ] TODO: Add pydantic for validation

# Configure logging
if not os.path.exists("logs"):
    os.makedirs("logs")
logging.config.fileConfig("logging.conf", disable_existing_loggers=False)
log = logging.getLogger(__name__)


async def fix_empty_articles():
    for provider in Provider:
        # Get scraper strategy
        scraper_strategy = await get_scraper_strategy(provider)
        # Create news scraper
        news_scraper = NewsScraper(scraper_strategy)
        # Scrape all articles with empty body
        empty_articles = get_articles_by_provider(None, provider.value, True)
        log.info(f"Empty articles: {empty_articles}")
        if len(empty_articles) == 0:
            continue
        delete_empty_body_by_provider(None, provider.value)
        articles = await news_scraper.scrape_articles(empty_articles, app.proxy_scraper)
        insert_articles(None, articles)


async def scrape_all_providers():
    for provider in Provider:
        # Get scraper strategy
        scraper_strategy = await get_scraper_strategy(provider)
        # Create news scraper
        news_scraper = NewsScraper(scraper_strategy)
        # Scrape all categories
        articles = await news_scraper.scrape_all(app.proxy_scraper)
        insert_articles(None, articles)


# Configure startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Scraping
        log.info("Scraping all providers...")
        news_scraper = NewsScraper(GMANewsScraper())
        articles = await news_scraper.scrape_all(app.proxy_scraper)
        insert_articles(None, articles)

        # Setup ML model
        log.info("Setting up ML model...")
        yield
    finally:
        # Teardown ML model
        log.info("Tearing down ML model...")


app = FastAPI(lifespan=lifespan)

# Shared state
app.proxy_scraper = ProxyScraper()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    idem = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    log.info(f"rid={idem} start request path={request.url.path}")
    start_time = time.time()

    response = await call_next(request)

    process_time = (time.time() - start_time) * 1000
    formatted_process_time = "{0:.2f}".format(process_time)
    log.info(
        f"rid={idem} completed_in={formatted_process_time}ms status_code={response.status_code}"
    )

    return response


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/proxies")
def get_proxies():
    proxies = ProxyScraper().proxies
    return {"proxies": proxies}


# [ ] TODO: Add pagination
# Get articles
@app.get("/articles")
def get_articles():
    articles = get_articles(None)
    return {"total": len(articles), "articles": articles}


# [ ] TODO: Add status endpoint - return datetime.time (get current time of server)
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, reload=True)
