from langdetect import detect, DetectorFactory
from deep_translator import GoogleTranslator
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# Ensure consistent results
DetectorFactory.seed = 0

class MultiLingualBridge:
    """
    Seamlessly handles non-English inputs by translating to English for the AI 
    and translating the AI's response back to the user's native language.
    """
    
    @staticmethod
    def detect_and_translate(text: str) -> Tuple[str, str]:
        """
        Detects language and translates to English if necessary.
        Returns: (translated_text, detected_lang_code)
        """
        if not text or len(text.strip()) < 3:
            return text, "en"
            
        try:
            lang = detect(text)
            if lang == "en":
                return text, "en"
            
            logger.info(f"Detected non-English language: {lang}")
            translated = GoogleTranslator(source='auto', target='en').translate(text)
            return translated, lang
        except Exception as e:
            logger.warning(f"Translation detection/process failed: {e}")
            return text, "en"

    @staticmethod
    def translate_to(text: str, target_lang: str) -> str:
        """
        Translates English text to the target language.
        """
        if target_lang == "en" or not text:
            return text
            
        try:
            return GoogleTranslator(source='en', target=target_lang).translate(text)
        except Exception as e:
            logger.warning(f"Translation back to {target_lang} failed: {e}")
            return text
