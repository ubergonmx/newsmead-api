import os
import time
import sys
import zipfile
import tensorflow as tf
import math
import requests
import argparse
from tqdm import tqdm
from datetime import timedelta

from recommenders.models.newsrec.newsrec_utils import prepare_hparams
from recommenders.models.newsrec.models.naml import NAMLModel
from recommenders.models.newsrec.io.mind_all_iterator import MINDAllIterator


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
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    download(url, filepath)
    unzip(filepath, target_dir)
    cleanup(filepath)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fit",
        action="store_true",
        help="Fit the model with the train, dev, & test set",
    )
    parser.add_argument(
        "--no-dl",
        action="store_true",
        help="Do not download the pretrained model",
    )
    parser.add_argument(
        "url",
        nargs="?",
        default="https://filebin.net/19aeuvg2jgix8iol/naml.zip",
        help="Direct download link for the pretrained model",
    )
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    target_dir = os.path.join(script_dir, "evaluate")

    if not args.no_dl:
        filepath = os.path.join(script_dir, "evaluate", "pretrained.zip")
        print("Downloading and unzipping to: ", filepath)
        download_and_unzip(args.url, filepath, target_dir)

    tf.get_logger().setLevel("ERROR")  # only show error messages

    start_overall_time = time.time()
    print("System version: {}".format(sys.version))
    print("Tensorflow version: {}".format(tf.__version__))

    # Prepare Parameters
    data_path = os.path.join(target_dir, "MIND_large")

    train_news_file = os.path.join(data_path, "train", r"news.tsv")
    train_behaviors_file = os.path.join(data_path, "train", r"behaviors.tsv")
    valid_news_file = os.path.join(data_path, "valid", r"news.tsv")
    valid_behaviors_file = os.path.join(data_path, "valid", r"behaviors.tsv")
    test_news_file = os.path.join(data_path, "test", r"news.tsv")
    test_behaviors_file = os.path.join(data_path, "test", r"behaviors.tsv")
    wordEmb_file = os.path.join(data_path, "utils", "embedding_all.npy")
    userDict_file = os.path.join(data_path, "utils", "uid2index.pkl")
    wordDict_file = os.path.join(data_path, "utils", "word_dict_all.pkl")
    vertDict_file = os.path.join(data_path, "utils", "vert_dict.pkl")
    subvertDict_file = os.path.join(data_path, "utils", "subvert_dict.pkl")
    yaml_file = os.path.join(data_path, "utils", r"naml.yaml")
    model_path = os.path.join(data_path, "model")

    # Setup the model
    start_time = time.time()
    hparams2 = prepare_hparams(
        yaml_file,
        wordEmb_file=wordEmb_file,
        wordDict_file=wordDict_file,
        userDict_file=userDict_file,
        vertDict_file=vertDict_file,
        subvertDict_file=subvertDict_file,
    )
    iterator2 = MINDAllIterator
    seed2 = 42
    model = NAMLModel(hparams2, iterator2, seed=seed2)

    if args.fit:
        # Save stdout to a file
        sys.stdout = open(os.path.join(data_path, "results-fit.txt"), "w")
        # Fit the model with the test set
        model.fit(
            train_news_file,
            train_behaviors_file,
            valid_news_file,
            valid_behaviors_file,
            test_news_file,
            test_behaviors_file,
        )
        # Return stdout to normal
        sys.stdout = sys.__stdout__
        print("fit time: ", timedelta(seconds=time.time() - start_time))
    else:
        # Load the weights saved from the model trained above
        model.model.load_weights(os.path.join(model_path, "naml_ckpt"))
        print("setup time: ", timedelta(seconds=time.time() - start_time))

        res = model.run_eval(test_news_file, test_behaviors_file)
        print("eval time: ", timedelta(seconds=time.time() - start_time))

        # Save the evaluation results to a file
        with open(os.path.join(data_path, "results-eval.txt"), "w") as file:
            file.write(str(res))

        print("saved results to ", os.path.join(data_path, "results.txt"))
        print("overall time: ", timedelta(seconds=time.time() - start_overall_time))
