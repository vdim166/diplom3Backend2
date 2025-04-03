from pydantic import BaseModel
from typing import Dict, List, Optional
import json
import os
from uuid import uuid4

import chardet

class Item(BaseModel):
    id: str
    name: str
    count: int
    storage_id: str
    category: Optional[str] = None

class ItemCreate(BaseModel):
    name: str
    count: int
    category: Optional[str] = None

class ItemUpdate(BaseModel):
    name: Optional[str] = None
    count: Optional[int] = None
    category: Optional[str] = None
    storage_id: Optional[str] = None

class Storage(BaseModel):
    id: str
    name: str
    location: str
    capacity: int
    current_load: int

class StorageDB:
    def __init__(self, file_path: str = "storage_db.json"):
        self.file_path = file_path
        self.storages: Dict[str, Storage] = {}
        self.items: Dict[str, List[Item]] = {}  # storage_id -> items
        self._load()

    def _load(self):
        if os.path.exists(self.file_path):
            with open("storage_db.json", "rb") as f:
                raw_data = f.read()
                detected = chardet.detect(raw_data)
                encoding = detected["encoding"]
                with open(self.file_path, 'r', encoding=encoding) as f:
                    data = json.load(f)
                
                    self.storages = {
                        s["id"]: Storage(**s) 
                        for s in data.get("storages", [])
                    }
                    self.items = {
                        storage_id: [Item(**item) for item in items]
                        for storage_id, items in data.get("items", {}).items()
                    }

    def _save(self):
        with open(self.file_path, 'w') as f:
            data = {
                "storages": [s.dict() for s in self.storages.values()],
                "items": {
                    storage_id: [i.dict() for i in items]
                    for storage_id, items in self.items.items()
                }
            }
            json.dump(data, f, indent=2)

    def init_storages(self):
        """Инициализация 24 хранилищ"""
        if not self.storages:
            for i in range(1, 25):
                storage_id = f"storage_{i}"
                self.storages[storage_id] = Storage(
                    id=storage_id,
                    name=f"Склад {i}",
                    location=f"Локация {i}",
                    capacity=1000,
                    current_load=0
                )
            self._save()

    def add_item(self, storage_id: str, item_data: ItemCreate) -> Item:
        if storage_id not in self.storages:
            raise ValueError("Хранилище не найдено")
        
        new_item = Item(
            id=str(uuid4()),
            **item_data.dict(),
            storage_id=storage_id
        )
        
        if storage_id not in self.items:
            self.items[storage_id] = []
        self.items[storage_id].append(new_item)
        
        storage = self.storages[storage_id]
        storage.current_load += item_data.count
        self._save()
        return new_item

    def get_items(self, storage_id: Optional[str] = None) -> List[Item]:
        if storage_id:
            return self.items.get(storage_id, [])
        return [item for items in self.items.values() for item in items]

    def update_item(self, item_id: str, update_data: ItemUpdate) -> Optional[Item]:
        for storage_id, items in self.items.items():
            for i, item in enumerate(items):
                if item.id == item_id:
                    if update_data.storage_id and update_data.storage_id != storage_id:
                        return self._move_item(item, update_data)
                    
                    old_count = item.count
                    updated_item = item.copy(update=update_data.dict(exclude_unset=True))
                    items[i] = updated_item
                    
                    if update_data.count:
                        storage = self.storages[storage_id]
                        storage.current_load += (update_data.count - old_count)
                    
                    self._save()
                    return updated_item
        return None

    def _move_item(self, item: Item, update_data: ItemUpdate) -> Item:
        new_storage_id = update_data.storage_id
        if new_storage_id not in self.storages:
            raise ValueError("Новое хранилище не найдено")
        
        old_storage = self.storages[item.storage_id]
        old_storage.current_load -= item.count
        self.items[item.storage_id] = [i for i in self.items[item.storage_id] if i.id != item.id]
        
        new_item = item.copy(update=update_data.dict(exclude_unset=True))
        new_item.storage_id = new_storage_id
        
        if new_storage_id not in self.items:
            self.items[new_storage_id] = []
        self.items[new_storage_id].append(new_item)
        
        new_storage = self.storages[new_storage_id]
        new_storage.current_load += new_item.count
        
        self._save()
        return new_item

    def delete_item(self, item_id: str) -> bool:
        for storage_id, items in self.items.items():
            for i, item in enumerate(items):
                if item.id == item_id:
                    storage = self.storages[storage_id]
                    storage.current_load -= item.count
                    
                    self.items[storage_id].pop(i)
                    self._save()
                    return True
        return False