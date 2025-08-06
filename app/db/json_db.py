import json
import os
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime, time

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, time):
            return obj.strftime("%H:%M:%S")
        return super().default(obj)

class JsonDB:
    def __init__(self, db_path: str = "app/db/data"):
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
    
    def _get_file_path(self, collection: str) -> Path:
        return self.db_path / f"{collection}.json"
    
    def _read_collection(self, collection: str) -> List[Dict[str, Any]]:
        file_path = self._get_file_path(collection)
        if not file_path.exists():
            return []
        with open(file_path, 'r') as f:
            return json.load(f)
    
    def _write_collection(self, collection: str, data: List[Dict[str, Any]]) -> None:
        file_path = self._get_file_path(collection)
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, cls=DateTimeEncoder)
    
    def find_all(self, collection: str) -> List[Dict[str, Any]]:
        return self._read_collection(collection)
    
    def find_one(self, collection: str, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        items = self._read_collection(collection)
        for item in items:
            if all(item.get(k) == v for k, v in query.items()):
                return item
        return None
    
    def insert_one(self, collection: str, document: Dict[str, Any]) -> Dict[str, Any]:
        items = self._read_collection(collection)
        items.append(document)
        self._write_collection(collection, items)
        return document
    
    def insert_many(self, collection: str, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        items = self._read_collection(collection)
        items.extend(documents)
        self._write_collection(collection, items)
        return documents
    
    def update_one(self, collection: str, query: Dict[str, Any], update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        items = self._read_collection(collection)
        for i, item in enumerate(items):
            if all(item.get(k) == v for k, v in query.items()):
                items[i].update(update)
                self._write_collection(collection, items)
                return items[i]
        return None
    
    def delete_one(self, collection: str, query: Dict[str, Any]) -> bool:
        items = self._read_collection(collection)
        for i, item in enumerate(items):
            if all(item.get(k) == v for k, v in query.items()):
                items.pop(i)
                self._write_collection(collection, items)
                return True
        return False
