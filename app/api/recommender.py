from sqlite3 import IntegrityError
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Header
from app.database.asyncdb import AsyncDatabase, get_db
from app.models.article import Article
import app.backend.config as config
import os

router = APIRouter()

secret_keyphrase = "n3w5me@d-s3cret"


def verify_keyphrase(keyphrase: str = Header(...)):
    if keyphrase != secret_keyphrase:
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
