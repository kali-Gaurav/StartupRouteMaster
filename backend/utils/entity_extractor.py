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
        now = datetime.now()
        
        # 1. Relative dates
        for kw, days in EntityExtractor.DATE_KEYWORDS.items():
            if kw in msg:
                return (now + timedelta(days=days)).strftime('%Y-%m-%d')
        
        # 2. Weekdays & "Next" Weekday
        for i, day in enumerate(EntityExtractor.WEEKDAYS):
            if day in msg:
                today_idx = now.weekday()
                days_ahead = (i - today_idx) % 7
                # If today is Monday and user says "Monday", it means today (days_ahead=0)
                # If user says "Next Monday", add 7 days
                if 'next' in msg:
                    days_ahead += 7
                elif days_ahead == 0 and 'today' not in msg:
                    # If I say "Monday" on Monday, usually means next Monday unless "today" is specified
                    days_ahead = 7
                return (now + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
        
        # 3. Standard formats (DD-MM-YYYY, YYYY-MM-DD, DD/MM)
        # Matches 15/03, 15-03-2026, 2026-03-15
        date_patterns = [
            r'(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})',
            r'(\d{1,2})[-/](\d{1,2})' # Just Day/Month
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, msg)
            if match:
                parts = match.groups()
                if len(parts) == 3:
                    d, m, y = parts
                    if len(y) == 2: y = "20" + y
                    try: return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
                    except ValueError: continue
                elif len(parts) == 2:
                    d, m = parts
                    y = now.year
                    # If date has passed this year, assume next year
                    try:
                        target = datetime(y, int(m), int(d))
                        if target < now - timedelta(days=1): target = target.replace(year=y+1)
                        return target.strftime('%Y-%m-%d')
                    except ValueError: continue
            
        return None

    @staticmethod
    def _parse_stations(message: str) -> Dict[str, str]:
        msg = message.lower()
        
        # Task 2.6: Expanded Patterns (Capture structure first)
        patterns = [
            (r'(?:from\s+)?([\w\s]{2,})\s+(?:to|->|—)\s+([\w\s]{2,})', False), # Delhi to Mumbai
            (r'between\s+([\w\s]{2,})\s+and\s+([\w\s]{2,})', False),          # between Delhi and Mumbai
            (r'train\s+for\s+([\w\s]{2,})\s+from\s+([\w\s]{2,})', True),      # train for Mumbai from Delhi
            (r'to\s+([\w\s]{2,})\s+from\s+([\w\s]{2,})', True),               # to Mumbai from Delhi
            (r'([\w\s]{3,})\s+bound\s+from\s+([\w\s]{3,})', True)             # Mumbai bound from Delhi
        ]
        
        # Helper to clean station fragments of noise
        def clean_fragment(text: str) -> str:
            # 1. Remove common noise words
            noise = r'\b(please|show|me|trains|train|for|from|to|between|and|on|at|next|today|tomorrow|pnr|status|details|is|are|a|an|the|of|bound|morning|evening|night|in|into)\b'
            text = re.sub(noise, ' ', text)
            # 2. Remove weekdays and months
            temporal = r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|january|february|march|april|may|june|july|august|september|october|november|december)\b'
            text = re.sub(temporal, ' ', text)
            # 3. Remove date numbers (e.g. 25th, 15/03)
            text = re.sub(r'\d+(st|nd|rd|th)?', ' ', text)
            text = re.sub(r'[-/]', ' ', text)
            return " ".join(text.split()).strip()

        # 1. Try directional patterns
        for pattern, is_reversed in patterns:
            match = re.search(pattern, msg)
            if match:
                p1, p2 = match.group(1).strip(), match.group(2).strip()
                src_raw, dst_raw = (p2, p1) if is_reversed else (p1, p2)
                
                src_clean = clean_fragment(src_raw)
                dst_clean = clean_fragment(dst_raw)

                if len(src_clean) < 2 or len(dst_clean) < 2: continue

                src_res = station_search_engine.resolve(src_clean)
                dst_res = station_search_engine.resolve(dst_clean)
                
                if src_res and dst_res:
                    return {
                        "source": src_res.code,
                        "source_name": src_res.name,
                        "destination": dst_res.code,
                        "destination_name": dst_res.name
                    }

        # 2. Heuristic Fallback
        clean_msg = clean_fragment(msg)
        words = clean_msg.split()
        potential_stations = []
        for i in range(len(words)):
            chunk1 = words[i]
            if len(chunk1) < 3: continue # Heuristic needs more signal
            res1 = station_search_engine.resolve(chunk1)
            if res1 and res1.popularity > 50: 
                potential_stations.append(res1)
            
            if i < len(words) - 1:
                chunk2 = f"{words[i]} {words[i+1]}"
                res2 = station_search_engine.resolve(chunk2)
                if res2 and res2.popularity > 70:
                    potential_stations.append(res2)

        unique_stations = []
        seen = set()
        for s in potential_stations:
            if s.code not in seen:
                unique_stations.append(s)
                seen.add(s.code)

        if len(unique_stations) >= 2:
            return {
                "source": unique_stations[0].code,
                "source_name": unique_stations[0].name,
                "destination": unique_stations[1].code,
                "destination_name": unique_stations[1].name
            }

        return {}
