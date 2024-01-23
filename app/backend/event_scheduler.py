from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone
from app.utils.scrapers.newsscraper import NewsScraper, Provider, get_scraper_strategy
from app.utils.scrapers.proxyscraper import ProxyScraper
from app.database.database import (
    get_articles_by_provider,
    insert_articles,
    delete_empty_body_by_provider,
)
import os
import logging.config

log = logging.getLogger(__name__)


async def check_and_fix_empty_articles():
    log.info("Checking and fixing empty articles...")
    for provider in Provider:
        scraper_strategy = await get_scraper_strategy(provider)
        news_scraper = NewsScraper(scraper_strategy)
        empty_articles = await get_articles_by_provider(None, provider.value, True)
        log.info(f"Empty articles: {empty_articles}")
        if len(empty_articles) == 0:
            continue
        await delete_empty_body_by_provider(None, provider.value)
        articles = await news_scraper.scrape_articles(empty_articles, ProxyScraper())
        await insert_articles(None, articles)


async def scrape_all_providers():
    log.info("Scraping all providers...")
    for provider in Provider:
        scraper_strategy = await get_scraper_strategy(provider)
        news_scraper = NewsScraper(scraper_strategy)
        articles = await news_scraper.scrape_all(ProxyScraper())
        await insert_articles(None, articles)


# Scheduler jobs
jobs = [
    (  # every 6th hour of the day (12AM, 6AM, 12PM, 6PM)
        scrape_all_providers,
        "cron",
        {"hour": "*/6", "id": "scrape_all_providers"},
    ),
    (  # every 6th hour and 30th minute of the day (12:30AM, 6:30AM, 12:30PM, 6:30PM)
        check_and_fix_empty_articles,
        "cron",
        {"hour": "*/6", "minute": 30, "id": "check_and_fix_empty_articles1"},
    ),
    (  # every 5th hour and 30th minute of the day (11:30PM, 5:30AM, 11:30AM, 5:30PM)
        check_and_fix_empty_articles,
        "cron",
        {"hour": "*/5", "minute": 30, "id": "check_and_fix_empty_articles2"},
    ),
]


# Schedule jobs
def schedule_jobs():
    scheduler = AsyncIOScheduler(timezone=timezone(os.getenv("TIMEZONE")))
    for job in jobs:
        func, trigger, kwargs = job
        scheduler.add_job(func, trigger, **kwargs)
    scheduler.start()
    return scheduler
