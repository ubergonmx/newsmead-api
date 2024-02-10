from app.utils.scrapers.proxy import ProxyScraper
from fastapi import APIRouter, HTTPException, UploadFile, File, Header, Depends
from fastapi.responses import FileResponse
import app.backend.config as config
import os
import datetime

router = APIRouter()


@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(os.path.join(config.get_project_root(), "favicon.ico"))


@router.get("/")
def read_root():
    # return RedirectResponse(url="https://newsmead-docs.vercel.app")
    return {"message": "Welcome to NewsMead API"}


@router.get("/status")
def get_status():
    return {"status": "OK", "time": datetime.datetime.now()}


@router.get("/proxies")
def get_proxies() -> dict[str, list[str]]:
    return {"proxies": ProxyScraper().get_proxies()}


def verify_keyphrase(keyphrase: str = Header(...)):
    if keyphrase != os.getenv("SECRET_KEY"):
        raise HTTPException(status_code=403, detail="Invalid keyphrase")
    return keyphrase


@router.get("/download-db", include_in_schema=False)
async def download_db(keyphrase: str = Depends(verify_keyphrase)):
    db_path = os.path.join(config.get_project_root(), os.getenv("DB_NAME"))
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Database not found")

    return FileResponse(
        db_path, media_type="application/octet-stream", filename=os.getenv("DB_NAME")
    )


@router.post("/upload-db", include_in_schema=False)
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
