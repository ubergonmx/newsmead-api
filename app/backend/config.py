from contextlib import asynccontextmanager
from fastapi import FastAPI
from event_scheduler import schedule_jobs
from app.utils.scrapers.proxyscraper import ProxyScraper
from app.core.recommender import Recommender
import logging.config
import dotenv
import os

# Load environment variables
dotenv.load_dotenv()

# Configure logging
log = logging.getLogger(__name__)


def configure_logging():
    log_dir = get_log_dir()
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_file_path = os.join(log_dir, os.getenv("LOG_FILE_NAME"))
    logging.config.fileConfig(log_file_path, disable_existing_loggers=False)


def get_project_root():
    project_dir_name = os.getenv("PROJECT_DIR_NAME")
    current_file_path = os.path.abspath(__file__)
    path_components = current_file_path.split(os.sep)
    project_root_index = path_components.index(project_dir_name)
    project_root = os.sep.join(path_components[: project_root_index + 1])
    return project_root


def get_log_dir():
    return os.join(get_project_root(), os.getenv("LOG_DIR_NAME"))


def get_sources_dir():
    return os.join(get_project_root(), os.getenv("SOURCES_DIR_NAME"))


def get_rss_dir():
    return os.join(get_sources_dir(), os.getenv("RSS_DIR_NAME"))


def get_webcrawler_dir():
    return os.join(get_sources_dir(), os.getenv("WEBCRAWLER_DIR_NAME"))


# Configure startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Configure logging
        configure_logging()

        # Setup ML model
        log.info("Setting up ML model...")
        app.recommender = Recommender()

        # Add scheduler jobs
        log.info("Adding scheduler jobs...")
        app.scheduler = schedule_jobs()

        yield
    finally:
        # Tear down ML model
        log.info("Tearing down ML model...")

        # Shutdown scheduler
        log.info("Shutting down scheduler...")
        app.scheduler.shutdown()
