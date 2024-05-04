from app.utils.scrapers.proxy import ProxyScraper
from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Depends
from fastapi.responses import FileResponse, RedirectResponse
import app.backend.config as config
import os
import datetime

router = APIRouter()


@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(os.path.join(config.get_project_root(), "favicon.ico"))


@router.get("/")
def read_root():
    return RedirectResponse(url="https://newsmead-docs.vercel.app")
    # return {"message": "Welcome to NewsMead API"}


@router.get("/status")
def get_status():
    return {"status": "OK", "time": datetime.datetime.now()}


@router.get("/proxies")
def get_proxies() -> dict[str, list[str]]:
    return {"proxies": ProxyScraper().get_proxies()}


def verify_key(key: str = Query(...)):
    if key != os.getenv("SECRET_KEY"):
        raise HTTPException(status_code=403, detail="Invalid keyphrase")
    return key


@router.get("/download-db", include_in_schema=False)
async def download_db(key: str = Depends(verify_key)):
    db_path = os.path.join(config.get_project_root(), os.getenv("DB_NAME"))
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Database not found")

    return FileResponse(
        db_path, media_type="application/octet-stream", filename=os.getenv("DB_NAME")
    )


@router.post("/upload-db", include_in_schema=False)
async def create_upload_db(
    file: UploadFile = File(...), key: str = Depends(verify_key)
):
    if file.filename == os.getenv("DB_NAME"):
        raise HTTPException(
            status_code=400, detail="Cannot upload database with same name"
        )
    filepath = os.path.join(config.get_project_root(), file.filename)
    with open(filepath, "wb") as f:
        f.write(file.file.read())
    return {"message": "Database uploaded successfully"}


@router.get("/download-logs", include_in_schema=False)
async def download_log(key: str = Depends(verify_key)):
    log_dir = config.get_log_dir()
    log_zip = os.path.join(config.get_project_root(), "logs.zip")
    config.create_zip(log_dir, log_zip)
    return FileResponse(
        log_zip, media_type="application/octet-stream", filename="logs.zip"
    )


@router.get("/download-sources", include_in_schema=False)
async def download_sources(key: str = Depends(verify_key)):
    sources_dir = config.get_sources_dir()
    sources_zip = os.path.join(config.get_project_root(), "sources.zip")
    config.create_zip(sources_dir, sources_zip)
    return FileResponse(
        sources_zip, media_type="application/octet-stream", filename="sources.zip"
    )
