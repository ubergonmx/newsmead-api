from azure.ai.translation.text import TextTranslationClient, TranslatorCredential
from azure.ai.translation.text.models import InputTextItem
from azure.core.exceptions import HttpResponseError
import tensorflow as tf
import time


def translate_text(text: str, source: str = "en", target: str = "fil") -> str:
    api_key = "api_key"  # os.getenv("AZURE_TRANSLATOR_API_KEY")
    region = "southeastasia"  # os.getenv("AZURE_TRANSLATOR_REGION")

    text_translator = TextTranslationClient(
        credential=TranslatorCredential(api_key, region)
    )

    try:
        input_text_elements = [InputTextItem(text=text)]

        response = text_translator.translate(
            content=input_text_elements, to=[target], from_parameter=source
        )
        translation = response[0] if response else None

        if translation:
            for translated_text in translation.translations:
                return translated_text.text
        else:
            raise ValueError(
                "Translation failed, no result returned from Azure Translator."
            )

    except HttpResponseError as exception:
        print(f"Error Code: {exception.error.code}")
        print(f"Message: {exception.error.message}")


if __name__ == "__main__":
    # Open the news.tsv file for reading and news_translated.tsv file for writing
    i = 0

    # Count the lines in the news_translated_ta.tsv file
    with tf.io.gfile.GFile("news_translated_ta.tsv", "r") as wr:
        line_start = sum(1 for _ in wr) + 1

    with tf.io.gfile.GFile("news.tsv", "r") as rd, tf.io.gfile.GFile(
        "news_translated_ta.tsv", "a"
    ) as wr:
        for line in rd:
            i += 1
            if i < line_start:
                continue

            print(f"Processing line {i}...")
            nid, vert, subvert, title, ab, url, entities_title, entities_ab = (
                line.strip().split("\t")
            )

            # Translate the title and abstract
            translated_title = translate_text(title)

            if translated_title is None:
                print("Translating title failed. Sleeping for 60 seconds...")
                time.sleep(60)
                translated_title = translate_text(title)

            translated_ab = translate_text(ab)

            if translated_ab is None:
                print("Translating abstract failed. Sleeping for 60 seconds...")
                time.sleep(60)
                translated_ab = translate_text(ab)

            if translated_title is None or translated_ab is None:
                raise RuntimeError("Translation failed.")

            # Print the translated text
            print(f"\t Translated text: {translated_title} -> {translated_ab}")

            # Write to the new file
            wr.write(
                f"{nid}\t{vert}\t{subvert}\t{translated_title}\t{translated_ab}\t{url}\t{entities_title}\t{entities_ab}\n"
            )
