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
        # 1. Check if storage exists
        if storage_id not in self.storages:
            raise ValueError(f"Storage {storage_id} not found")
        
        # 2. Check if storage has enough capacity
        storage = self.storages[storage_id]
        if storage.current_load + item_data.count > storage.capacity:
            raise ValueError("Not enough capacity in storage")
        
        # 3. Create new item with unique ID
        new_item = Item(
            id=str(uuid4()),  # Generate unique ID
            name=item_data.name,
            count=item_data.count,
            storage_id=storage_id,
            # Add other fields from item_data as needed
        )
        
        # 4. Add to storage
        if storage_id not in self.items:
            self.items[storage_id] = []
        
        # Check if item already exists (optional - merge counts if exists)
        for existing_item in self.items[storage_id]:
            if existing_item.name == new_item.name:
                existing_item.count += new_item.count
                self._save()
                return existing_item
        
        # If not exists, add new item
        self.items[storage_id].append(new_item)
        storage.current_load += new_item.count
        self._save()
        
        return new_item

    def get_items(self, storage_id: Optional[str] = None) -> List[Item]:
        if storage_id:
            return self.items.get(storage_id, [])
        return [item for items in self.items.values() for item in items]

    def update_item(self, item_name: str,storage_id:str, update_data: ItemUpdate) -> Optional[Item]:

        for item_index in range(len(self.items[storage_id])):
            item = self.items[storage_id][item_index]
            if item.name == item_name:
                self.items[storage_id][item_index] = update_data


                self._save()
                break
                    
        
        return None

      

    def _move_item(
        self, 
        item_name: str, 
        from_storage_id: str, 
        to_storage_id: str, 
        count: int
    ) -> Item:
        # Проверяем существование целевого хранилища
        if to_storage_id not in self.storages:
            raise ValueError("Целевое хранилище не найдено")
        
        # Находим предмет в исходном хранилище
        item_to_move = None
        item_index = -1
        
        for i, item in enumerate(self.items.get(from_storage_id, [])):
            if item.name == item_name:
                item_to_move = item
                item_index = i
                break
        
        if item_to_move is None:
            raise ValueError("Предмет не найден в исходном хранилище")
        
        # Проверяем доступное количество
        if count <= 0:
            raise ValueError("Количество должно быть положительным")
        if count > item_to_move.count:
            raise ValueError(f"Недостаточно предметов (доступно: {item_to_move.count}, запрошено: {count})")
        
        # Обновляем исходный предмет (уменьшаем количество)
        remaining_count = item_to_move.count - count
        if remaining_count > 0:
            # Если остались предметы - обновляем количество
            self.items[from_storage_id][item_index].count = remaining_count
        else:
            # Если предметов не осталось - удаляем
            self.items[from_storage_id].pop(item_index)
        
        self.storages[from_storage_id].current_load -= count
        
        # Создаем новую версию предмета для целевого хранилища
        new_item = item_to_move.copy()
        new_item.storage_id = to_storage_id
        new_item.count = count
        
        # Добавляем предмет в целевое хранилище
        if to_storage_id not in self.items:
            self.items[to_storage_id] = []
        
        # Проверяем, есть ли уже такой предмет в целевом хранилище
        existing_item_index = next(
            (i for i, item in enumerate(self.items[to_storage_id]) 
            if item.name == item_name), 
            None
        )
        
        if existing_item_index is not None:
            # Если предмет уже есть - увеличиваем количество
            self.items[to_storage_id][existing_item_index].count += count
        else:
            # Если предмета нет - добавляем новый
            self.items[to_storage_id].append(new_item)
        
        self.storages[to_storage_id].current_load += count
        
        self._save()
        return new_item
    

    def delete_item(self, item_name: str, storage_id:str) -> bool:
        for item_index in range(len(self.items[storage_id])):
            item = self.items[storage_id][item_index]
            if item.name == item_name:
                self.items[storage_id].pop(item_index)
                self._save()
                return True
        
        return False

