import math
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class SafetyBayesClassifier:
    """
    Task 30: Threat Categorization Bayes Classifier.
    Uses word-probability to categorize incidents.
    """
    def __init__(self):
        # Initial training data (In production, load from DB/JSON)
        self.categories = ["medical", "security", "fire"]
        self.word_counts = {cat: {} for cat in self.categories}
        self.cat_counts = {cat: 1 for cat in self.categories} # Laplace smoothing
        self.vocab = set()
        
        self._seed_training_data()

    def _seed_training_data(self):
        data = {
            "medical": ["heart", "pain", "doctor", "ambulance", "blood", "sick", "breathe", "chest", "pregnant"],
            "security": ["rob", "thief", "steal", "gun", "knife", "attack", "fight", "snatch", "harass", "threat"],
            "fire": ["fire", "smoke", "burning", "short", "circuit", "flame", "blast"]
        }
        for cat, words in data.items():
            for word in words:
                self.train(word, cat)

    def train(self, text: str, category: str):
        if category not in self.word_counts: return
        words = text.lower().split()
        for word in words:
            self.word_counts[category][word] = self.word_counts[category].get(word, 0) + 1
            self.vocab.add(word)
        self.cat_counts[category] += 1

    def classify(self, text: str) -> str:
        words = text.lower().split()
        best_cat = "unknown"
        max_prob = -float('inf')
        
        total_docs = sum(self.cat_counts.values())
        
        for cat in self.categories:
            # Prior: P(Category)
            prob = math.log(self.cat_counts[cat] / total_docs)
            
            # Likelihood: P(Word | Category)
            total_cat_words = sum(self.word_counts[cat].values())
            for word in words:
                # Laplace smoothing for unseen words
                count = self.word_counts[cat].get(word, 0) + 1
                prob += math.log(count / (total_cat_words + len(self.vocab)))
            
            if prob > max_prob:
                max_prob = prob
                best_cat = cat
                
        return best_cat

safety_bayes = SafetyBayesClassifier()
