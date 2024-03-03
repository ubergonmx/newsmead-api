# Download model and unzip to recommender_utils
import math
import requests
import zipfile
import os
from tqdm import tqdm


def download(url: str, filepath: str) -> None:
    r = requests.get(url, stream=True, allow_redirects=True)
    if r.status_code == 200:
        print(f"Downloading {url}")
        total_size = int(r.headers.get("content-length", 0))
        block_size = 1024
        num_iterables = math.ceil(total_size / block_size)
        with open(filepath, "wb") as file:
            for data in tqdm(
                r.iter_content(block_size),
                total=num_iterables,
                unit="KB",
                unit_scale=True,
            ):
                file.write(data)
    else:
        print(f"Problem downloading {url}")
        r.raise_for_status()


def unzip(filepath: str, target_dir: str) -> None:
    # This will create target_dir if it does not exist
    # This overwrite existing files if target_dir already exists
    with zipfile.ZipFile(filepath, "r") as zip_ref:
        zip_ref.extractall(target_dir)


def cleanup(filepath: str) -> None:
    os.remove(filepath)


def download_and_unzip(url: str, filepath: str, target_dir: str) -> None:
    download(url, filepath)
    unzip(filepath, target_dir)


if __name__ == "__main__":
    # Replace this URL with any direct download link
    url = "https://bit.ly/4bTqqgd"
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(script_dir, "recommender_utils", "pretrained.zip")
    target_dir = os.path.join(script_dir, "recommender_utils")
    print(filepath)
    download_and_unzip(url, filepath, target_dir)
    cleanup(filepath)
