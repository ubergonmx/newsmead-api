import logging
import os
import numpy as np
import io
import time
import tempfile

# Suppress C++ level warnings.
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
# Suppress TensorFlow logging
logging.getLogger("tensorflow").setLevel(logging.ERROR)
# Configure logging
log = logging.getLogger(__name__)

from recommenders.models.newsrec.newsrec_utils import prepare_hparams
from recommenders.models.newsrec.models.naml import NAMLModel
from recommenders.models.newsrec.io.mind_all_iterator import MINDAllIterator

start_time = time.time()
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
news = os.path.join(data_path, r"news.tsv")
impression = "1\tU2000505\t11/15/2019 6:02:42 AM\tN22427 N15072 N16699 N22024 N22104 N15636\tN26508-0 N20150-1"
model.news_vecs = model.run_news(news)
print("setup time: ", time.time() - start_time)


def predict(behavior: str, news_file=None):
    behavior_file = None
    try:
        print("start predicting...")
        # Create a temporary file called behavior-{random string}.tsv
        with tempfile.NamedTemporaryFile(
            mode="w", dir=data_path, prefix="behavior-", suffix=".tsv", delete=False
        ) as f:
            f.write(behavior)
            behavior_file = f.name
            print(behavior_file)

        start_time = time.time()
        if hasattr(model.test_iterator, "impr_indexes"):
            print("has attr")
            del model.test_iterator.impr_indexes
        model.user_vecs = model.run_user(news_file, behavior_file)
        for (
            impr_index,
            news_index,
            _,
            _,
        ) in model.test_iterator.load_impression_from_file(behavior_file):
            pred = np.dot(
                np.stack([model.news_vecs[i] for i in news_index], axis=0),
                model.user_vecs[impr_index],
            )

        pred_rank = (np.argsort(np.argsort(pred)[::-1]) + 1).tolist()
        print("pred_rank: ", pred_rank)
        impressions = [i.split("-")[0] for i in behavior.split("\t")[-1].split()]
        merge = {r: i for r, i in zip(pred_rank, impressions)}
        ranked_articles = dict(sorted(merge.items()))
        articles = list(ranked_articles.values())
        print("predicting time: ", time.time() - start_time)
        return articles
    finally:
        # Delete the temporary file
        os.remove(behavior_file)


print(predict(impression))
