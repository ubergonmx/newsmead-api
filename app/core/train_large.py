import sys
import os
import numpy as np
import zipfile
from tqdm import tqdm
from tempfile import TemporaryDirectory
from datetime import timedelta
import tensorflow as tf
import shutil
import time

start_overall_time = time.time()
tf.get_logger().setLevel("ERROR")  # only show error messages

from recommenders.models.deeprec.deeprec_utils import download_deeprec_resources
from recommenders.models.newsrec.newsrec_utils import prepare_hparams
from recommenders.models.newsrec.models.naml import NAMLModel
from recommenders.models.newsrec.io.mind_all_iterator import MINDAllIterator
from recommenders.models.newsrec.newsrec_utils import get_mind_data_set

print("Setting up NAML model...")
# time benchmark
start_time = time.time()

epochs = 5
seed = 42
batch_size = 32

# Options: demo, small, large
MIND_type = "large"
tmp_dir = TemporaryDirectory()
data_path = tmp_dir.name
print(f"Temporary directory: {data_path}")
train_news_file = os.path.join(data_path, "train", r"news.tsv")
train_behaviors_file = os.path.join(data_path, "train", r"behaviors.tsv")
valid_news_file = os.path.join(data_path, "valid", r"news.tsv")
valid_behaviors_file = os.path.join(data_path, "valid", r"behaviors.tsv")
wordEmb_file = os.path.join(data_path, "utils", "embedding_all.npy")
userDict_file = os.path.join(data_path, "utils", "uid2index.pkl")
wordDict_file = os.path.join(data_path, "utils", "word_dict_all.pkl")
vertDict_file = os.path.join(data_path, "utils", "vert_dict.pkl")
subvertDict_file = os.path.join(data_path, "utils", "subvert_dict.pkl")
yaml_file = os.path.join(data_path, "utils", r"naml.yaml")

mind_url, mind_train_dataset, mind_dev_dataset, mind_utils = get_mind_data_set(
    MIND_type
)

if not os.path.exists(train_news_file):
    download_deeprec_resources(
        mind_url, os.path.join(data_path, "train"), mind_train_dataset
    )

if not os.path.exists(valid_news_file):
    download_deeprec_resources(
        mind_url, os.path.join(data_path, "valid"), mind_dev_dataset
    )
if not os.path.exists(yaml_file):
    download_deeprec_resources(
        r"https://recodatasets.z20.web.core.windows.net/newsrec/",
        os.path.join(data_path, "utils"),
        mind_utils,
    )

# Create hyper-parameters
hparams = prepare_hparams(
    yaml_file,
    wordEmb_file=wordEmb_file,
    wordDict_file=wordDict_file,
    userDict_file=userDict_file,
    vertDict_file=vertDict_file,
    subvertDict_file=subvertDict_file,
    batch_size=batch_size,
    epochs=epochs,
)
iterator = MINDAllIterator
model = NAMLModel(hparams, iterator, seed=seed)

print(f"Model setup time: {time.time() - start_time}")
print("Training NAML model...")
start_time = time.time()

# Train the model
model.fit(train_news_file, train_behaviors_file, valid_news_file, valid_behaviors_file)

print(f"Model training time: {timedelta(seconds=time.time() - start_time)}")
print(f"Evaluating NAML model...")
start_time = time.time()

res = model.run_eval(valid_news_file, valid_behaviors_file)

print(f"Model evaluation time: {timedelta(seconds=time.time() - start_time)}")
print(f"Saving results...")
start_time = time.time()

res_path = os.path.join(data_path, "utils", "evaluation_results.txt")
with open(res_path, "w") as f:
    f.write(f"group_auc: {res['group_auc']}\n")
    f.write(f"mean_mrr: {res['mean_mrr']}\n")
    f.write(f"ndcg@5: {res['ndcg@5']}\n")
    f.write(f"ndcg@10: {res['ndcg@10']}\n")

print(f"Results saving time: {time.time() - start_time}")
print("Saving model...")
start_time = time.time()

# Save the model
model_path = os.path.join(data_path, "pretrained")
os.makedirs(model_path, exist_ok=True)
model.model.save_weights(os.path.join(model_path, "naml_ckpt"))

print(f"Model saving time: {time.time() - start_time}")
print("Moving model to recommender_utils...")
start_time = time.time()

# Move pretrained and utils folder from tmp_dir to script_loc/recommender_utils
script_dir = os.path.dirname(os.path.abspath(__file__))
rec_path = os.path.join(script_dir, "recommender_utils")
os.makedirs(rec_path, exist_ok=True)
for folder in ["pretrained", "utils"]:
    shutil.move(os.path.join(data_path, folder), os.path.join(rec_path, folder))
print(f"Model moving time: {time.time() - start_time}")

print("Cleaning up...")
tmp_dir.cleanup()

print(f"Done! Runtime: {timedelta(seconds=time.time() - start_overall_time)}")
