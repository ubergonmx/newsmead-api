import os
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from app.core.recommender import Recommender
from app.database.asyncdb import AsyncDatabase, get_db
from app.models.article import Filter
from datetime import datetime
from pytz import timezone
import logging
import traceback

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/refresh-news")
async def refresh_news(request: Request, db: AsyncDatabase = Depends(get_db)):
    try:
        log.info("Refreshing news...")
        request.app.state.recommender = Recommender()
        await request.app.state.recommender.save_news(db)
        request.app.state.recommender.load_news()
        return {"message": "News refreshed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{user_id}")
async def recommended_articles(
    request: Request,
    user_id: str,
    page: int = Query(1),
    page_size: int = Query(35),
    language: Optional[str] = Query(None),
    db: AsyncDatabase = Depends(get_db),
):
    articles = []
    try:
        log.info(f"Getting recommended articles for user {user_id}...")
        history = await db.get_user_history(user_id)
        filter = Filter(language=language)
        articles = await db.get_articles(filter, page, page_size)
        # log filter if LOG_PREDICT from env is verbose
        if os.getenv("LOG_PREDICT") == "verbose":
            log.info(f"filter: {filter}")
        log.info(f"history: {history}")
        log.info(f"history count: {len(history)}")
        log.info(f"articles count: {len(articles)}")

        if len(history) == 0:
            preferred_categories = await db.get_user_preferences(user_id)
            log.info(f"preferred_categories: {preferred_categories}")

            if len(preferred_categories) > 0:
                # All articles with preferred categories will be on the top
                log.info("Sorting articles by preferred categories...")
                preferred_articles = []
                other_articles = []
                for article in articles:
                    if article.category in preferred_categories:
                        preferred_articles.append(article)
                    else:
                        other_articles.append(article)

                articles = preferred_articles + other_articles

            return {
                "status": "success",
                "totalResults": len(articles),
                "articles": articles,
            }

        # Limit history to last 50
        history = history[-50:]
        impression_news = " ".join(
            [
                f"{article.article_id}-{'1' if str(article.article_id) in history else '0'}"
                for article in articles
            ]
        )
        history = " ".join([h for h in history if h != "0"])
        log.info(f"impression_news: {impression_news}")
        time_now = datetime.now(timezone("Asia/Manila"))
        behavior = f"{user_id}\t{time_now}\t{history}\t{impression_news}"
        ranked_ids, score = request.app.state.recommender.predict(behavior)
        await db.insert_behavior(user_id, time_now, history, impression_news, score)
        log.info(f"ranked_ids: {ranked_ids}")
        articles = sorted(
            articles, key=lambda article: ranked_ids.index(str(article.article_id))
        )
    except Exception as e:
        log.error(f"Error predicting (L{e.__traceback__.tb_lineno}): {e}")
        log.error(traceback.format_exc())

    return {
        "status": "success",
        "totalResults": len(articles),
        "articles": articles,
    }
