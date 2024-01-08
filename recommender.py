import logging
import os
import numpy as np

# Suppress C++ level warnings.
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
# Suppress TensorFlow logging
logging.getLogger("tensorflow").setLevel(logging.ERROR)
# Configure logging
log = logging.getLogger(__name__)

from recommenders.models.newsrec.newsrec_utils import prepare_hparams
from recommenders.models.newsrec.models.naml import NAMLModel
from recommenders.models.newsrec.io.mind_all_iterator import MINDAllIterator


data_path = "recommender"
wordEmb_file = os.path.join(data_path, "utils", "embedding_all.npy")
userDict_file = os.path.join(data_path, "utils", "uid2index.pkl")
wordDict_file = os.path.join(data_path, "utils", "word_dict_all.pkl")
vertDict_file = os.path.join(data_path, "utils", "vert_dict.pkl")
subvertDict_file = os.path.join(data_path, "utils", "subvert_dict.pkl")
yaml_file = os.path.join(data_path, "utils", "naml.yaml")
model_path = os.path.join(data_path, "model")

# Setup the model
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
model.model.load_weights(os.path.join(model_path, "naml_ckpt"))

# Setup inputs
news = os.path.join(data_path, r"news-smol.tsv")
impression = os.path.join(data_path, r"behaviors-smol.tsv")


def predict(news_file, impression_file):
    model.news_vecs = model.run_news(news_file)
    model.user_vecs = model.run_user(news_file, impression_file)

    group_impr_indexes = []
    group_labels = []
    group_preds = []

    print("start predicting...")

    import time

    start_time = time.time()
    for (
        impr_index,
        news_index,
        user_index,
        label,
    ) in model.test_iterator.load_impression_from_file(impression):
        pred = np.dot(
            np.stack([model.news_vecs[i] for i in news_index], axis=0),
            model.user_vecs[impr_index],
        )
        group_impr_indexes.append(impr_index)
        group_labels.append(label)
        group_preds.append(pred)

    print("predicting time: ", time.time() - start_time)

    predictions = []
    for impr_index, preds in zip(group_impr_indexes, group_preds):
        impr_index += 1
        pred_rank = (np.argsort(np.argsort(preds)[::-1]) + 1).tolist()

    impressions = []
    # Open impression file
    with open(impression_file, "r") as f:
        uid, time, history, impr = f.readline().strip("\n").split("\t")[-4:]
        impressions = [i.split("-")[0] for i in impr.split()]

    # Create a dictionary where the keys are the ranks and the values are the impressions
    articles = {rank: impression for rank, impression in zip(pred_rank, impressions)}

    # Sort the dictionary by rank
    articles = dict(sorted(articles.items()))

    # Create a list of impressions sorted by rank
    ranked = list(articles.values())

    print(ranked)


predict(news, impression)
