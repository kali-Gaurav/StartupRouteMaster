import json
import os
import difflib
from typing import Optional

class StationCorrector:
    """
    Auto-corrects common station typos and fuzzy matches inputs to known codes.
    """
    
    def __init__(self):
        self.typo_map = {}
        self._load_map()
        
    def _load_map(self):
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            map_path = os.path.join(base_dir, 'data', 'station_typo_map.json')
            if os.path.exists(map_path):
                with open(map_path, 'r') as f:
                    self.typo_map = json.load(f)
        except Exception:
            self.typo_map = {}

    def correct(self, input_text: str) -> str:
        """
        Takes raw user input and returns a corrected station name or code.
        """
        if not input_text:
            return input_text
            
        cleaned = input_text.strip().lower()
        
        # 1. Exact Typo Map Match
        if cleaned in self.typo_map:
            return self.typo_map[cleaned]
            
        # 2. Fuzzy Match against typo map keys
        matches = difflib.get_close_matches(cleaned, self.typo_map.keys(), n=1, cutoff=0.8)
        if matches:
            return self.typo_map[matches[0]]
            
        return input_text

# Singleton instance
station_corrector = StationCorrector()
