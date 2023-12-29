from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Request
from proxyscrape import scrape_proxies
import sqlite3
import logging
import random
import string
import time


# Configure startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Setup ML model
        logger.info("Setting up ML model...")
        yield
    finally:
        # Teardown ML model
        logger.info("Tearing down ML model...")


app = FastAPI(lifespan=lifespan)

# Configure logging
logging.config.fileConfig("logging.conf", disable_existing_loggers=False)
logger = logging.getLogger(__name__)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    idem = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    logger.info(f"rid={idem} start request path={request.url.path}")
    start_time = time.time()

    response = await call_next(request)

    process_time = (time.time() - start_time) * 1000
    formatted_process_time = "{0:.2f}".format(process_time)
    logger.info(
        f"rid={idem} completed_in={formatted_process_time}ms status_code={response.status_code}"
    )

    return response


# Get DB helper funciton
def get_db():
    conn = sqlite3.connect("newsmead.sqlite")
    yield conn
    logger.info("Closing DB connection...")
    conn.close()


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/proxies")
def get_proxies():
    proxies = scrape_proxies()
    return {"proxies": proxies}
