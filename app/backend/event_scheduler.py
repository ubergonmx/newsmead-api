from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone
from app.utils.scrapers.proxy import ProxyScraper
from app.database.asyncdb import AsyncDatabase
import app.utils.scrapers.news as news
import os
import logging.config

log = logging.getLogger(__name__)


async def check_and_fix_empty_articles():
    log.info("Checking and fixing empty articles...")
    proxy = ProxyScraper()
    async with AsyncDatabase() as db:
        for provider in news.Provider:
            scraper_strategy = news.get_scraper_strategy(provider)
            news_scraper = news.NewsScraper(scraper_strategy)
            empty_articles = await db.get_empty_articles(provider.value)
            log.info(f"Empty articles ({provider.value}): {len(empty_articles)}")
            if len(empty_articles) == 0:
                continue
            articles = await news_scraper.scrape_articles(empty_articles, proxy)
            await db.update_empty_articles(articles)


async def scrape_all_providers():
    log.info("Scraping all providers...")
    proxy = ProxyScraper()
    async with AsyncDatabase() as db:
        for provider in news.Provider:
            scraper_strategy = news.get_scraper_strategy(provider)
            news_scraper = news.NewsScraper(scraper_strategy)
            articles = await news_scraper.scrape_all(proxy)
            await db.insert_articles(articles)


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
