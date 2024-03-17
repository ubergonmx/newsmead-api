from concurrent.futures import ThreadPoolExecutor
from app.database.asyncdb import AsyncDatabase
from aiocsv import AsyncWriter
import asyncio
import logging
import os
import numpy as np
import time
import tempfile
import app.backend.config as config
import aiofiles

# Suppress C++ level warnings.
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
# Suppress TensorFlow logging
logging.getLogger("tensorflow").setLevel(logging.ERROR)
# Configure logging
log = logging.getLogger(__name__)

from recommenders.models.newsrec.newsrec_utils import prepare_hparams
from recommenders.models.newsrec.models.naml import NAMLModel
from recommenders.models.newsrec.io.mind_all_iterator import MINDAllIterator
from recommenders.models.deeprec.deeprec_utils import cal_metric


class Recommender:
    def __init__(self):
        start_time = time.time()
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_path = os.path.join(current_dir, "recommender_utils")
        wordEmb_file = os.path.join(self.data_path, "utils", "embedding_all.npy")
        userDict_file = os.path.join(self.data_path, "utils", "uid2index.pkl")
        wordDict_file = os.path.join(self.data_path, "utils", "word_dict_all.pkl")
        vertDict_file = os.path.join(self.data_path, "utils", "vert_dict.pkl")
        subvertDict_file = os.path.join(self.data_path, "utils", "subvert_dict.pkl")
        yaml_file = os.path.join(self.data_path, "utils", "naml.yaml")
        model_path = os.path.join(self.data_path, "pretrained")
        self.news_file = os.path.join(self.data_path, r"news.tsv")
        self.impression_file = os.path.join(self.data_path, r"behaviors.tsv")

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

    def limit_words(self, text: str, limit: int = None) -> str:
        limit = limit or self.model.hparams.body_size
        clean_text = (
            text.replace("\n", " ")
            .replace("/", "")
            .replace("\\", "")
            .replace(r"\u2014", "")
            .strip()
        )
        words = clean_text.split()
        return " ".join(words[:limit])

    async def write_article_to_tsv(self, writer, article):
        # article_id:0, category:2, title:4, body:7, url:6
        await writer.writerow(
            [
                article[0],
                article[2],
                article[2],
                article[4],
                self.limit_words(article[7]),
                article[6],
                "[skip]",
                "[skip]",
            ]
        )

    async def write_impression_to_tsv(self, writer, impression):
        # user_id:0, time:1, history:2, impression_news:3
        await writer.writerow(impression)

    async def write_chunk_to_tsv(self, chunk, filename, write_func):
        async with aiofiles.open(filename, "a", encoding="utf-8", newline="") as f:
            writer = AsyncWriter(f, delimiter="\t")
            for item in chunk:
                await write_func(writer, item)

    async def save_news(
        self, db: AsyncDatabase, chunk_size: int = 1000, news_file: str = None
    ):
        log.info(f"Saving news...")
        news_file = news_file or self.news_file
        if os.path.exists(news_file):
            os.remove(news_file)
        cursor = await db.get_all_articles_cursor()
        last_row_in_chunk = None
        while True:
            chunk = await cursor.fetchmany(chunk_size)
            if not chunk:
                break
            last_row_in_chunk = chunk[-1]
            await self.write_chunk_to_tsv(chunk, news_file, self.write_article_to_tsv)

        # Print the last row to be written
        print(f"Last row to be written: {last_row_in_chunk[0]}")

        log.info(f"Saved news to {news_file}")

    async def save_impressions(
        self, db: AsyncDatabase, chunk_size: int = 1000, impression_file: str = None
    ):
        impression_file = impression_file or self.impression_file
        if os.path.exists(impression_file):
            os.remove(impression_file)
        cursor = await db.get_all_impressions_cursor()
        while True:
            chunk = await cursor.fetchmany(chunk_size)
            if not chunk:
                break

            await self.write_chunk_to_tsv(
                chunk, impression_file, self.write_impression_to_tsv
            )

        log.info(f"Saved impressions to {impression_file}")

    def load_news(self, news_file: str = None):
        log.info(f"Loading news...")
        self.model.news_vecs = self.model.run_news(news_file or self.news_file)
        log.info(f"Loaded news")

    def predict(self, behavior: str) -> tuple[list[str], dict]:
        behavior_file = None
        try:
            log.info(f"Start predicting...")
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
            score = {}
            for (
                impr_index,
                news_index,
                _,
                label,
            ) in self.model.test_iterator.load_impression_from_file(behavior_file):
                pred = np.dot(
                    np.stack([self.model.news_vecs[i] for i in news_index], axis=0),
                    self.model.user_vecs[impr_index],
                )
                try:
                    score = cal_metric([label], [pred], self.model.hparams.metrics)
                except Exception as e:
                    pass

            pred_rank = (np.argsort(np.argsort(pred)[::-1]) + 1).tolist()
            log.info(f"pred_rank: {pred_rank}")
            log.info(f"score: {score}")
            impression_news = [
                i.split("-")[0] for i in behavior.split("\t")[-1].split()
            ]
            merge = {r: i for r, i in zip(pred_rank, impression_news)}
            ranked_articles = dict(sorted(merge.items()))
            articles = list(ranked_articles.values())
            log.info(f"Prediction runtime: {time.time() - start_time}")
            return articles, score
        finally:
            # Delete the temporary file
            os.remove(behavior_file)
