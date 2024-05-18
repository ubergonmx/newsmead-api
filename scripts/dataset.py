from ..app.core.recommender import Recommender
from ..app.utils.nlp.lang import Lang
import tensorflow as tf

recommender = Recommender(load_model=False)

with tf.io.gfile.GFile("news.tsv", "r") as rd, tf.io.gfile.GFile(
    "news_translated.tsv", "a"
) as wr:
    for line in rd:
        nid, vert, subvert, title, ab, url, entities_title, entities_ab = (
            line.strip().split("\t")
        )

        # Translate the title and abstract
        translated_title = Lang(detector=False).translate_text(title)
        translated_ab = Lang(detector=False).translate_text(ab)

        # Limit the number of words
        translated_title = recommender.limit_words(translated_title)
        translated_ab = recommender.limit_words(translated_ab)

        # Write to the new file
        wr.write(
            f"{nid}\t{vert}\t{subvert}\t{translated_title}\t{translated_ab}\t{url}\t{entities_title}\t{entities_ab}\n"
        )
