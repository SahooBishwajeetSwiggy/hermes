import os
import json
import threading
from datetime import datetime

CACHE_FILE = os.path.join(os.path.dirname(__file__), "distance_cache.json")

def _ts():
    """Timestamp for logs"""
    return datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")

def _truncate_coord(value, digits=8):
    return f"{float(value):.{digits}f}"

def make_key(loc, lat, lon):
    """Create a persistent key for location with truncated lat/lon"""
    return f"{loc}_{_truncate_coord(lat)}_{_truncate_coord(lon)}"

class DistanceCache:
    def __init__(self, cache_file=CACHE_FILE):
        self.cache_file = cache_file
        self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.cache_file):
            with open(self.cache_file, "r") as f:
                self.cache = json.load(f)
            print(_ts(), f"Cache loaded with {len(self.cache)} locations from {self.cache_file}")
        else:
            self.cache = {}
            print(_ts(), "No existing cache found, starting fresh")

    def _save_cache(self):
        with open(self.cache_file, "w") as f:
            json.dump(self.cache, f)
        print(_ts(), f"Cache saved → {self.cache_file}")

    def get_distance(self, key1, key2):
        """Get distance from cache if available"""
        dist = self.cache.get(key1, {}).get(key2)
        # if dist is not None:
        #     print(_ts(), f"CACHE HIT: {key1} ↔ {key2} = {dist}m")
        # else:
        #     print(_ts(), f"CACHE MISS: {key1} ↔ {key2}")
        return dist

    def set_distance(self, key1, key2, dist):
        """Store distance symmetrically"""
        if key1 not in self.cache:
            self.cache[key1] = {}
        if key2 not in self.cache:
            self.cache[key2] = {}
        self.cache[key1][key2] = dist
        self.cache[key2][key1] = dist
        # print(_ts(), f"DISTANCE SAVED: {key1} ↔ {key2} = {dist}m")
        self._save_cache()

    def background_fill(self, new_key, distances_dict):
        """In background, store missing distances for a location with all other locations
        
        Args:
            new_key: The key of the new location
            distances_dict: Dictionary of {location_key: distance_in_meters}
        """
        def _fill():
            for loc_key, distance in distances_dict.items():
                if self.get_distance(new_key, loc_key) is None:
                    self.set_distance(new_key, loc_key, distance)
            
        threading.Thread(target=_fill, daemon=True).start()
