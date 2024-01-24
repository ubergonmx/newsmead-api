from sqlite3 import IntegrityError
from fastapi import APIRouter, HTTPException, Depends
from app.database.asyncdb import AsyncDatabase, get_db
from app.models.article import Article

router = APIRouter()


@router.post("/articles/")
async def create_article(article: Article, db: AsyncDatabase = Depends(get_db)):
    try:
        await db.create_article_table()  # Ensure table exists
        await db.insert_data([article])  # Insert data
        return {"message": "Article created successfully"}
    except IntegrityError as e:
        raise HTTPException(
            status_code=400, detail="Duplicate entry or integrity error"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
