from lingua import Language, LanguageDetectorBuilder


class Language:
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
