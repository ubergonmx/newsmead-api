from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Request
from proxyscraper import ProxyScraper
import sqlite3
import logging
import random
import string
import time
from newsscraper import NewsScraper, Provider, get_scraper_strategy, GMANewsScraper
from database_utils import insert_articles, get_articles

# [ ] TODO: Add pydantic for validation


# Configure logging
logging.config.fileConfig("logging.conf", disable_existing_loggers=False)
logger = logging.getLogger(__name__)


# Configure startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Scraping
        logger.info("Scraping...")
        # Loop each provider and perform scraping
        # for provider in Provider:
        #     # Get scraper strategy
        #     scraper_strategy = await get_scraper_strategy(provider)
        #     # Create news scraper
        #     news_scraper = NewsScraper(scraper_strategy)
        #     # Scrape all categories
        #     await news_scraper.scrape_all()
        proxy_scraper = ProxyScraper()
        news_scraper = NewsScraper(GMANewsScraper())
        articles = await news_scraper.scrape_all(proxy_scraper)
        insert_articles(None, articles)

        # Setup ML model
        logger.info("Setting up ML model...")
        yield
    finally:
        # Teardown ML model
        logger.info("Tearing down ML model...")


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    idem = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    logger.info(f"rid={idem} start request path={request.url.path}")
    start_time = time.time()

    response = await call_next(request)

    process_time = (time.time() - start_time) * 1000
    formatted_process_time = "{0:.2f}".format(process_time)
    logger.info(
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
