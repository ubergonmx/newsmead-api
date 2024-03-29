from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.recommender import Recommender
from app.backend import event_scheduler
from app.database.asyncdb import AsyncDatabase
import logging.config
import dotenv
import os

# Configure logging
log = logging.getLogger(__name__)


def configure_logging():
    log_dir = get_log_dir()
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_file_path = os.path.join(get_project_root(), os.getenv("LOG_CONFIG_FILE_NAME"))
    logging.config.fileConfig(log_file_path, disable_existing_loggers=False)


def get_project_root():
    project_dir_name = os.getenv("PROJECT_DIR_NAME")
    current_file_path = os.path.abspath(__file__)
    path_components = current_file_path.split(os.sep)
    project_root_index = path_components.index(project_dir_name)
    project_root = os.sep.join(path_components[: project_root_index + 1])
    return project_root


def get_log_dir():
    return create_dir(os.path.join(get_project_root(), os.getenv("LOG_DIR_NAME")))


def get_sources_dir():
    return create_dir(os.path.join(get_project_root(), os.getenv("SOURCES_DIR_NAME")))


def get_rss_dir():
    return create_dir(os.path.join(get_sources_dir(), os.getenv("RSS_DIR_NAME")))


def get_webcrawler_dir():
    return create_dir(os.path.join(get_sources_dir(), os.getenv("WEBCRAWLER_DIR_NAME")))


def create_dir(dir_path) -> str:
    os.makedirs(dir_path, exist_ok=True)
    return dir_path


# Configure startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Load environment variables
        dotenv.load_dotenv()

        # Configure logging
        configure_logging()

        # Setup ML model
        log.info("Setting up ML model...")
        app.state.recommender = Recommender()
        async with AsyncDatabase() as db:
            await app.state.recommender.save_news(db)
        app.state.recommender.load_news()

        # Add scheduler jobs
        log.info("Adding scheduler jobs...")
        app.state.scheduler = event_scheduler.schedule_jobs(app)

        yield
    finally:
        # Shutdown scheduler
        log.info("Shutting down scheduler...")
        app.state.scheduler.shutdown()
