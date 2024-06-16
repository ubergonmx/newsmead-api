from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone
from app.utils.scrapers.proxy import ProxyScraper
from app.database.asyncdb import AsyncDatabase
from typing import TYPE_CHECKING
from fastapi import FastAPI
import app.utils.scrapers.news as news
import os
import logging.config

log = logging.getLogger(__name__)


# TODO: Make it check_and_fix_articles (this includes empty articles, duplicates, text cleaning (removal of newlines), etc.)
async def check_and_fix_empty_articles(app: FastAPI):
    from app.core.recommender import Recommender

    recommender = app.state.recommender
    log.info("Checking and fixing empty articles...")
    proxy = ProxyScraper()
    while proxy.get_proxies() == []:
        await proxy.scrape_proxies()
    async with AsyncDatabase() as db:
        for provider in news.Provider:
            scraper_strategy = news.get_scraper_strategy(provider)
            news_scraper = news.NewsScraper(scraper_strategy)
            empty_articles = await db.get_empty_articles(provider.value)
            if len(empty_articles) == 0:
                continue
            articles = await news_scraper.scrape_articles(empty_articles, proxy)
            await db.update_empty_articles(articles)
        await recommender.save_news(db)
    recommender.load_news()
    log.info("Empty articles checked and fixed.")


async def scrape_all_providers(app: FastAPI):
    from app.core.recommender import Recommender

    recommender = app.state.recommender
    log.info("Scraping all providers...")
    proxy = ProxyScraper()
    while proxy.get_proxies() == []:
        await proxy.scrape_proxies()
    async with AsyncDatabase() as db:
        for provider in news.Provider:
            scraper_strategy = news.get_scraper_strategy(provider)
            news_scraper = news.NewsScraper(scraper_strategy)
            articles = await news_scraper.scrape_all(proxy)
            await db.insert_articles(articles)
        await recommender.save_news(db)
    recommender.load_news()
    log.info("All providers scraped.")


# Scheduler jobs
jobs = [
    (  # every 6th hour of the day (12AM, 6AM, 12PM, 6PM)
        scrape_all_providers,
        "cron",
        {"hour": "*/6", "id": "scrape_all_providers"},
    ),
    # (  # every 6th hour and 30th minute of the day (12:30AM, 6:30AM, 12:30PM, 6:30PM)
    #     check_and_fix_empty_articles,
    #     "cron",
    #     {"hour": "*/6", "minute": 30, "id": "check_and_fix_empty_articles1"},
    # ),
]


# Schedule jobs
def schedule_jobs(app: FastAPI):
    scheduler = AsyncIOScheduler(timezone=timezone(os.getenv("TIMEZONE")))
    for job in jobs:
        func, trigger, kwargs = job
        scheduler.add_job(func, trigger, args=[app], **kwargs)
    scheduler.start()
    return scheduler
