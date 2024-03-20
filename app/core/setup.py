# Download model and unzip to recommender_utils
import math
import sys
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
    # This overwrite existing files if target_dir already exists
    with zipfile.ZipFile(filepath, "r") as zip_ref:
        zip_ref.extractall(target_dir)


def cleanup(filepath: str) -> None:
    os.remove(filepath)


def download_and_unzip(url: str, filepath: str, target_dir: str) -> None:
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    download(url, filepath)
    unzip(filepath, target_dir)
    cleanup(filepath)


if __name__ == "__main__":
    # Replace this with the direct download link of the model
    url = ""
    # or use the first argument as the url when running the script
    # python setup.py <url>
    if len(sys.argv) > 1:
        url = sys.argv[1]
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(script_dir, "recommender_utils", "pretrained.zip")
    target_dir = os.path.join(script_dir, "recommender_utils")
    print("Downloading and unzipping to:", filepath)
    download_and_unzip(url, filepath, target_dir)
