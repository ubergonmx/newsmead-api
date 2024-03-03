from sqlite3 import IntegrityError
from typing import Callable, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks, Request
from app.database.asyncdb import AsyncDatabase, get_db
from app.models.article import Filter
import app.backend.event_scheduler as internals
import logging
import os
import translators as ts

router = APIRouter()
log = logging.getLogger(__name__)


@router.get("/")
async def get_articles(
    source: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    startDate: Optional[str] = Query(None),
    endDate: Optional[str] = Query(None),
    text: Optional[str] = Query(None),
    sortBy: Optional[str] = Query(None),
    page: int = Query(1),
    page_size: int = Query(30),
    db: AsyncDatabase = Depends(get_db),
):
    filter = Filter(
        source=source,
        category=category,
        startDate=startDate,
        endDate=endDate,
        text=text,
        sortBy=sortBy,
    )
    try:
        articles = await db.get_articles(filter, page, page_size)
        return {
            "status": "success",
            "totalResults": len(articles),
            "articles": articles,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def add_task(background_tasks: BackgroundTasks, func: Callable, *args, **kwargs):
    async def wrapper():
        await func(*args, **kwargs)

    background_tasks.add_task(wrapper)


@router.get("/cafea", include_in_schema=False)
async def check_and_fix_empty_articles(bg: BackgroundTasks, request: Request):
    await add_task(
        bg, internals.check_and_fix_empty_articles, request.app.state.recommender
    )
    return {"message": "Check and fix empty articles started"}


@router.get("/scrapeall", include_in_schema=False)
async def scrape_all_providers(
    bg: BackgroundTasks, request: Request, key: str = Query(None)
):
    if key != os.getenv("SECRET_KEY"):
        raise HTTPException(status_code=403, detail="Invalid keyphrase")
    await add_task(bg, internals.scrape_all_providers, request.app.state.recommender)
    return {"message": "Scrape all providers started"}


@router.get("/translate/{article_id}")
async def get_article(article_id: int, db: AsyncDatabase = Depends(get_db)):
    try:
        article = await db.get_article_by_id(article_id)
        translated_title = ts.translate_text(
            article.title, translator="google", to_language="tl"
        )
        translated_body = ts.translate_text(
            article.body, translator="google", to_language="tl"
        )
        return {
            "title": translated_title,
            "body": translated_body,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# @router.post("/new")
# async def create_article(article: Article, db: AsyncDatabase = Depends(get_db)):
#     try:
#         await db.insert_data([article])
#         return {"message": "Article created successfully"}
#     except IntegrityError as e:
#         raise HTTPException(
#             status_code=400, detail="Duplicate entry or integrity error"
#         )
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
