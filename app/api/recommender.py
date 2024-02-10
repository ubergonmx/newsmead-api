from fastapi import APIRouter, Request, HTTPException, Depends
from app.database.asyncdb import AsyncDatabase, get_db
from app.models.article import Filter
from datetime import datetime
from pytz import timezone
import logging

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/refresh-news")
async def refresh_news(request: Request, db: AsyncDatabase = Depends(get_db)):
    try:
        await request.app.state.recommender.save_news(db)
        request.app.state.recommender.load_news()
        return {"message": "News refreshed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{user_id}/{page}")
async def recommended_articles(
    user_id: str, page: int, request: Request, db: AsyncDatabase = Depends(get_db)
):
    history = await db.get_user_history(user_id)
    articles = await db.get_articles(Filter(), page, 10)
    log.info(f"history: {history}")
    log.info(f"articles count: {len(articles)}")

    try:
        if history:
            impression_news = " ".join(
                [
                    f"{article.article_id}-{'1' if str(article.article_id) in history else '0'}"
                    for article in articles
                ]
            )
            history = " ".join(history)
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

    return {
        "status": "success",
        "totalResults": len(articles),
        "articles": articles,
    }
