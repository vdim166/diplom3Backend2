import json
import os
from typing import Dict, Any, Optional

class FileDatabase:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.data: Dict[str, Any] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.file_path):
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        else:
            self.data = {"users": {}}
            self._save()

    def _save(self):
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def get_all_users(self):
        return {'users': list(self.data["users"].keys())}
    
    def get_all_managers(self):
        result = []
        for key, value in self.data["users"].items():
            if value["is_manager"] == True:
                result.append(key)

        return {'users': result}
    
    def get_all_workers(self):
        result = []
        for key, value in self.data["users"].items():
            if value["is_manager"] == False:
                result.append(key)

        return {'users': result}

    def get_user(self, username: str) -> Optional[Dict]:
        return self.data["users"].get(username)

    def create_user(self, user_data: Dict) -> Dict:
        username = user_data["username"]
        if username in self.data["users"]:
            raise ValueError("User already exists")
        
        self.data["users"][username] = user_data
        self._save()
        return user_data

    def update_user(self, username: str, update_data: Dict) -> Dict:
        if username not in self.data["users"]:
            raise ValueError("User not found")
        
        self.data["users"][username].update(update_data)
        self._save()
        return self.data["users"][username]

    def delete_user(self, username: str) -> bool:
        if username not in self.data["users"]:
            return False
        
        del self.data["users"][username]
        self._save()
        return True