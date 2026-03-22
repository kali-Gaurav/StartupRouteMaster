import re
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from services.station_search_service import station_search_engine
from utils.station_corrector import station_corrector

class EntityExtractor:
    """
    High-speed entity extraction for Railway intents.
    Extracts: Sources, Destinations, Dates, PNRs.
    """
    
    DATE_KEYWORDS = {
        'tomorrow': 1,
        'today': 0,
        'day after': 2,
    }

    WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

    @staticmethod
    def extract_all(message: str) -> Dict[str, Any]:
        entities = {}
        
        # 1. Extract PNR
        pnr_match = re.search(r'\b\d{10}\b', message)
        if pnr_match:
            entities['pnr'] = pnr_match.group(0)

        # 2. Extract Date
        date = EntityExtractor._parse_date(message)
        if date:
            entities['date'] = date

        # 3. Extract Stations (Source to Destination)
        stations = EntityExtractor._parse_stations(message)
        entities.update(stations)

        return entities

    @staticmethod
    def _parse_date(message: str) -> Optional[str]:
        msg = message.lower()
        
        # Relative dates
        for kw, days in EntityExtractor.DATE_KEYWORDS.items():
            if kw in msg:
                return (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
        
        # Weekdays
        for i, day in enumerate(EntityExtractor.WEEKDAYS):
            if day in msg:
                today_idx = datetime.now().weekday()
                days_ahead = (i - today_idx) % 7
                if days_ahead == 0 and 'next' in msg:
                    days_ahead = 7
                return (datetime.now() + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
        
        # Standard formats (DD-MM-YYYY, YYYY-MM-DD)
        match = re.search(r'(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})', msg)
        if match:
            d, m, y = match.groups()
            if len(y) == 2: y = "20" + y
            try:
                return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
            except ValueError: pass
            
        return None

    @staticmethod
    def _parse_stations(message: str) -> Dict[str, str]:
        msg = message.lower()
        
        # Patterns like "Delhi to Mumbai", "NDLS -> BCT", "from Kota to Pune"
        # Improved regex: more flexible word boundary and characters
        patterns = [
            r'(?:from\s+)?([\w\s]{2,})\s+(?:to|->|—)\s+([\w\s]{2,})',
            r'between\s+([\w\s]{2,})\s+and\s+([\w\s]{2,})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, msg)
            if match:
                src_raw = station_corrector.correct(match.group(1).strip())
                dst_raw = station_corrector.correct(match.group(2).strip())
                
                # Use fuzzy station search engine
                src_res = station_search_engine.resolve(src_raw)
                dst_res = station_search_engine.resolve(dst_raw)
                
                if src_res and dst_res:
                    return {
                        "source": src_res.name,
                        "source_code": src_res.code,
                        "destination": dst_res.name,
                        "destination_code": dst_res.code
                    }
        return {}
