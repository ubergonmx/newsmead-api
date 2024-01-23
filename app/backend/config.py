import logging.config
import dotenv
import os


dotenv.load_dotenv()


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
