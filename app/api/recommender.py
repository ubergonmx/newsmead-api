from sqlite3 import IntegrityError
from fastapi import APIRouter, File, Request, UploadFile, HTTPException, Depends, Header
from app.database.asyncdb import AsyncDatabase, get_db
from app.models.article import Article, Filter
from datetime import datetime
from pytz import timezone
import app.backend.config as config
import os
import logging

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/load-news/")
async def load_news(request: Request):
    try:
        await request.app.state.recommender.load_news()
        return {"message": "News loaded successfully"}
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
            history = " ".join(history)
            impression_news = " ".join(
                [
                    f"{article.article_id}-{'1' if article.article_id in history else '0'}"
                    for article in articles
                ]
            )
            log.info(f"impression_news: {impression_news}")
            time_now = datetime.now(timezone("Asia/Manila"))
            behavior = f"{user_id}\t{time_now}\t{history}\t{impression_news}"
            await db.insert_behavior(user_id, time_now, history, impression_news)
            ranked_ids = request.app.state.recommender.predict(behavior)
            articles = sorted(
                articles, key=lambda article: ranked_ids.index(str(article.article_id))
            )
    except Exception as e:
        log.error(f"Error predicting: {e}")

    return {
        "status": "success",
        "totalResults": len(articles),
        "articles": articles,
    }


def verify_keyphrase(keyphrase: str = Header(...)):
    if keyphrase != os.getenv("SECRET_KEY"):
        raise HTTPException(status_code=403, detail="Invalid keyphrase")
    return keyphrase


@router.post("/upload-db/")
async def create_upload_db(
    file: UploadFile = File(...), keyphrase: str = Depends(verify_keyphrase)
):
    if file.filename == os.getenv("DB_NAME"):
        raise HTTPException(
            status_code=400, detail="Cannot upload database with same name"
        )
    filepath = os.path.join(config.get_project_root, file.filename)
    with open(filepath, "wb") as f:
        f.write(file.file.read())
    return {"message": "Database uploaded successfully"}
