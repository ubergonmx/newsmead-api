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


def add_label_to_news(old_behavior_file, new_behavior_file):
    # Open the old behavior file for reading
    with open(old_behavior_file, "r") as old_file:
        # Open a new behavior file for writing
        with open(new_behavior_file, "w") as new_file:
            # Iterate through each line in the old behavior file
            for line in old_file:
                # Split the line into its components
                (
                    impression_id,
                    user_id,
                    impression_time,
                    user_click_history,
                    impression_news,
                ) = line.strip().split("\t")
                # Split the impression news into individual news IDs
                news_ids_with_label = [
                    f"{news_id}-0" for news_id in impression_news.split()
                ]
                # Join the news IDs with labels back into a single string
                impression_news_with_labels = " ".join(news_ids_with_label)
                # Write the updated line to the new behavior file
                new_file.write(
                    f"{impression_id}\t{user_id}\t{impression_time}\t{user_click_history}\t{impression_news_with_labels}\n"
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-f",
        "--fit",
        action="store_true",
        help="fit the model with the train, dev, & test set",
    )
    parser.add_argument(
        "-n",
        "--no-dl",
        action="store_true",
        help="do not download the zip file",
    )
    parser.add_argument(
        "-u",
        "--url",
        default="https://filebin.net/19aeuvg2jgix8iol/naml.zip",
        help="direct download link for the zip file",
    )
    parser.add_argument(
        "-d",
        "--dir",
        default="",
        help="directory to download and extract the zip to (default: current directory)",
    )
    parser.add_argument(
        "-e",
        "--epoch",
        default=5,
        help="number of epochs to train the model",
    )

    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    target_dir = os.path.join(script_dir, args.dir)

    if not args.no_dl:
        filepath = os.path.join(target_dir, "MIND.zip")
        print("downloading and unzipping to: ", filepath)
        download_and_unzip(args.url, filepath, target_dir)

    tf.get_logger().setLevel("ERROR")  # only show error messages

    start_overall_time = time.time()
    print("system version: {}".format(sys.version))
    print("tensorflow version: {}".format(tf.__version__))

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

    # Add label 0 to test behaviors file and save the updated data to a new file
    new_test_behaviors_file = os.path.join(
        data_path, "test", r"behaviors_with_labels.tsv"
    )
    print("adding label 0 to test behaviors file...")
    add_label_to_news(test_behaviors_file, new_test_behaviors_file)
    print("added label 0 to test behaviors file")

    # Setup the model
    start_time = time.time()
    hparams = prepare_hparams(
        yaml_file,
        wordEmb_file=wordEmb_file,
        wordDict_file=wordDict_file,
        userDict_file=userDict_file,
        vertDict_file=vertDict_file,
        subvertDict_file=subvertDict_file,
    )
    iterator = MINDAllIterator
    seed = 42
    model = NAMLModel(hparams, iterator, seed=seed)

    try:
        print("model epochs: ", model.hparams.epochs)
        if args.epoch:
            model.hparams.epochs = args.epoch
    except:
        print("cannot print and set model epoch")

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
            new_test_behaviors_file,
        )
        # Return stdout to normal
        sys.stdout = sys.__stdout__
        print("fit time: ", timedelta(seconds=time.time() - start_time))
    else:
        # Load the weights saved from the model trained above
        model.model.load_weights(os.path.join(model_path, "naml_ckpt"))
        print("setup time: ", timedelta(seconds=time.time() - start_time))

        res = model.run_eval(test_news_file, new_test_behaviors_file)
        print("eval time: ", timedelta(seconds=time.time() - start_time))

        # Save the evaluation results to a file
        with open(os.path.join(data_path, "results-eval.txt"), "w") as file:
            file.write(str(res))

        print("saved results to ", os.path.join(data_path, "results.txt"))
        print("overall time: ", timedelta(seconds=time.time() - start_overall_time))
