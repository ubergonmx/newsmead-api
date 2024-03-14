from lingua import Language, LanguageDetectorBuilder
from azure.ai.translation.text import TextTranslationClient, TranslatorCredential
from azure.ai.translation.text.models import InputTextItem
from azure.core.exceptions import HttpResponseError
from google.cloud import translate_v2 as translate
import os
import logging

# Configure logging
log = logging.getLogger(__name__)


class Lang:
    def __init__(self, detector=True, all=False):
        if detector:
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

    def translate_text(
        self, text: str, source: str = "en", target: str = "fil", service: str = "bing"
    ) -> str:
        """
        Translates the text to the target language.
        By default, it translate from English to Filipino using the Bing Translator API.

        For Google, target must be an ISO 639-1 language code.
        See https://g.co/cloud/translate/v2/translate-reference#supported_languages
        """

        if service == "bing":
            api_key = os.getenv("AZURE_TRANSLATOR_API_KEY")
            region = os.getenv("AZURE_TRANSLATOR_REGION")

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
                log.error(f"Error Code: {exception.error.code}")
                log.error(f"Message: {exception.error.message}")

        elif service == "google":
            translate_client = translate.Client()
            if isinstance(text, bytes):
                text = text.decode("utf-8")
            result = translate_client.translate(text, target_language=target)
            return result["translatedText"]
