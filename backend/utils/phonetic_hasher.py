import re
import logging

logger = logging.getLogger(__name__)

class PhoneticHasher:
    """
    Task 23: Language-Agnostic Phonetic Keyword Hashing.
    Converts words into a consonant-based signature to allow fuzzy/misspelled matching.
    """
    @staticmethod
    def get_signature(text: str) -> str:
        if not text: return ""
        
        # 1. Lowercase and strip non-alpha
        text = text.lower()
        text = re.sub(r'[^a-z\s]', '', text)
        
        signatures = []
        for word in text.split():
            if not word: continue
            
            # 2. Phonetic Normalization (Simplified Metaphone-like)
            # Remove vowels (except maybe the first one if we wanted more accuracy, but consonants are key)
            # Remove repeated characters (Heeelp -> Help)
            
            # Remove repeats
            word = re.sub(r'(.)\1+', r'\1', word)
            
            # Strip vowels
            word = re.sub(r'[aeiouy]', '', word)
            
            if word:
                signatures.append(word.upper())
                
        return " ".join(signatures)

    @staticmethod
    def match(source_text: str, target_keywords: list) -> bool:
        """Checks if any target keyword phonetically matches words in source_text."""
        source_sig = PhoneticHasher.get_signature(source_text)
        
        for kw in target_keywords:
            kw_sig = PhoneticHasher.get_signature(kw)
            if kw_sig in source_sig:
                return True
        return False

# Global instance
safety_hasher = PhoneticHasher()
