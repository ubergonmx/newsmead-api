from lingua import Language, LanguageDetectorBuilder
from azure.ai.translation.text import TextTranslationClient, TranslatorCredential
from azure.ai.translation.text.models import InputTextItem
from azure.core.exceptions import HttpResponseError
from google.cloud import translate_v2 as translate
import os


class Lang:
    def __init__(self, all=False):
        self.detector = (
            LanguageDetectorBuilder.from_all_languages()
            if all
            else LanguageDetectorBuilder.from_languages(
                Language.ENGLISH, Language.TAGALOG
            ).build()
        )

    def detect(self, text) -> str:
        """
        Returns the top language of the text.

        Example:
        ```
        "TAGALOG"
        ```
        """
        return self.detector.detect_language_of(text).name

    def detect_with_score(self, text) -> dict[str, float]:
        """
        Returns a dict with the top language and the confidence score.

        Example:
        ```
        {
            "lang": "TAGALOG",
            "score": 0.9585779901734812
        }
        ```
        """
        result = self.detector.compute_language_confidence_values(text)
        return {"lang": result[0].language.name, "score": result[0].value}

    def is_english(self, text) -> bool:
        """
        Returns True if the text is in English.
        """
        return self.detect(text) == "ENGLISH"

    def translate_to_filipino(self, text: str, service: str = "bing") -> str:
        """
        Translates the text to Filipino.
        """
        api_key = os.getenv("AZURE_TRANSLATOR_API_KEY")
        region = os.getenv("AZURE_TRANSLATOR_REGION")

        text_translator = TextTranslationClient(
            credential=TranslatorCredential(api_key, region)
        )

        try:
            source_language = "en"
            target_languages = ["fil"]
            input_text_elements = [InputTextItem(text=text)]

            response = text_translator.translate(
                content=input_text_elements,
                to=target_languages,
                from_parameter=source_language,
            )
            translation = response[0] if response else None

            if translation:
                for translated_text in translation.translations:
                    print(
                        f"Text was translated to: '{translated_text.to}' and the result is: '{translated_text.text}'."
                    )
                    return translated_text.text
            else:
                raise ValueError(
                    "Translation failed, no result returned from Azure Translator."
                )

        except HttpResponseError as exception:
            print(f"Error Code: {exception.error.code}")
            print(f"Message: {exception.error.message}")

    def translate_text(target: str, text: str) -> dict:
        """Translates text into the target language.

        Target must be an ISO 639-1 language code.
        See https://g.co/cloud/translate/v2/translate-reference#supported_languages
        """
        translate_client = translate.Client()

        if isinstance(text, bytes):
            text = text.decode("utf-8")

        # Text can also be a sequence of strings, in which case this method
        # will return a sequence of results for each text.
        result = translate_client.translate(text, target_language=target)

        print("Text: {}".format(result["input"]))
        print("Translation: {}".format(result["translatedText"]))
        print("Detected source language: {}".format(result["detectedSourceLanguage"]))

        return result
