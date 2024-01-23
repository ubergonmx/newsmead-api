from concurrent.futures import ThreadPoolExecutor
import asyncio
import logging
import os
import numpy as np
import time
import tempfile
import app.backend.config as config

# Suppress C++ level warnings.
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
# Suppress TensorFlow logging
logging.getLogger("tensorflow").setLevel(logging.ERROR)
# Configure logging
log = logging.getLogger(__name__)

from recommenders.models.newsrec.newsrec_utils import prepare_hparams
from recommenders.models.newsrec.models.naml import NAMLModel
from recommenders.models.newsrec.io.mind_all_iterator import MINDAllIterator


class Recommender:
    def __init__(self):
        start_time = time.time()

        self.data_path = os.path.join(
            config.get_project_root(), "app", "core", "recommender_utils"
        )
        wordEmb_file = os.path.join(self.data_path, "utils", "embedding_all.npy")
        userDict_file = os.path.join(self.data_path, "utils", "uid2index.pkl")
        wordDict_file = os.path.join(self.data_path, "utils", "word_dict_all.pkl")
        vertDict_file = os.path.join(self.data_path, "utils", "vert_dict.pkl")
        subvertDict_file = os.path.join(self.data_path, "utils", "subvert_dict.pkl")
        yaml_file = os.path.join(self.data_path, "utils", "naml.yaml")
        model_path = os.path.join(self.data_path, "pretrained")
        self.news_file = os.path.join(self.data_path, r"news.tsv")

        hparams = prepare_hparams(
            yaml_file,
            wordEmb_file=wordEmb_file,
            wordDict_file=wordDict_file,
            userDict_file=userDict_file,
            vertDict_file=vertDict_file,
            subvertDict_file=subvertDict_file,
        )

        self.model = NAMLModel(hparams, MINDAllIterator, seed=42)
        self.model.model.load_weights(os.path.join(model_path, "naml_ckpt"))
        log.info(f"Model setup time: {time.time() - start_time}")

    # def load_news(self, news_file: str = None):
    #     self.model.news_vecs = self.model.run_news(news_file or self.news_file)

    async def load_news(self, news_file: str = None):
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            await loop.run_in_executor(
                pool, self.model.run_news, news_file or self.news_file
            )

    async def predict(self, behavior: str) -> list[str]:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(pool, self._predict, behavior)

        return result

    def _predict(self, behavior: str) -> list[str]:
        behavior_file = None
        try:
            print("start predicting...")
            # Create a temporary file called behavior-{random string}.tsv
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=self.data_path,
                prefix="behavior-",
                suffix=".tsv",
                delete=False,
            ) as f:
                f.write(behavior)
                behavior_file = f.name
                log.info(f"Created temporary file: {behavior_file}")

            start_time = time.time()
            if hasattr(self.model.test_iterator, "impr_indexes"):
                print("has attr")
                del self.model.test_iterator.impr_indexes
            self.model.user_vecs = self.model.run_user(None, behavior_file)
            for (
                impr_index,
                news_index,
                _,
                _,
            ) in self.model.test_iterator.load_impression_from_file(behavior_file):
                pred = np.dot(
                    np.stack([self.model.news_vecs[i] for i in news_index], axis=0),
                    self.model.user_vecs[impr_index],
                )

            pred_rank = (np.argsort(np.argsort(pred)[::-1]) + 1).tolist()
            log.info(f"pred_rank: {pred_rank}")
            impressions = [i.split("-")[0] for i in behavior.split("\t")[-1].split()]
            merge = {r: i for r, i in zip(pred_rank, impressions)}
            ranked_articles = dict(sorted(merge.items()))
            articles = list(ranked_articles.values())
            log.info(f"predicting time: {time.time() - start_time}")
            return articles
        finally:
            # Delete the temporary file
            os.remove(behavior_file)


# Setup inputs
impression = "1\tU2000505\t11/15/2019 6:02:42 AM\tN22427 N15072 N16699 N22024 N22104 N15636\tN26508-0 N20150-1"
