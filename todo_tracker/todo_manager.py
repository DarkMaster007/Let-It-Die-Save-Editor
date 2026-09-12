# -*- coding: utf-8 -*-
"""
TODO Manager - Manages user-defined grinding goals and tracks progress.

This module handles:
- Creating, editing, and deleting TODO items
- Saving/loading TODO lists to JSON files
- Tracking progress from save file data
- Filtering and sorting TODO items
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
import uuid

from todo_tracker.todo_types import TodoItem, TodoType
from todo_tracker.read_save import (
    load_save_data,
    get_storage_analysis,
    get_currency_totals,
    get_deathbag_analysis,
    get_dustin_sent_analysis,
    get_save_metadata,
)


DEFAULT_TODO_FILE = Path.home() / ".lid_todo_tracker" / "todo_list.json"


@dataclass
class TodoProgress:
    """Progress information for a TODO item."""
    todo_id: str
    current_amount: int = 0
    target_amount: int = 0
    is_complete: bool = False
    progress_percentage: float = 0.0
    last_updated: str = ""
    source_type: str = ""  # "storage" or "currency"
    source_info: str = ""  # Item ID or currency name
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TodoProgress':
        return cls(**data)


class TodoManager:
    """Manages TODO items and their progress tracking."""
    
    def __init__(self, todo_file: Optional[Path] = None):
        self.todo_file = todo_file or DEFAULT_TODO_FILE
        self.todos: List[TodoItem] = []
        self._progress_cache: Dict[str, TodoProgress] = {}
        self._last_save_data: Optional[Dict[str, Any]] = None
        self._last_save_path: Optional[str] = None
        
        # Ensure directory exists
        self.todo_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing TODO list
        self.load_todos()
    
    def load_todos(self) -> None:
        """Load TODO items from file."""
        if not self.todo_file.exists():
            self.todos = []
            return
        
        try:
            with open(self.todo_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self.todos = [
                TodoItem.from_dict(item) 
                for item in data.get("todos", [])
            ]
            
            # Also load progress cache if available
            if "progress_cache" in data:
                self._progress_cache = {
                    k: TodoProgress.from_dict(v)
                    for k, v in data["progress_cache"].items()
                }
                
            # Load metadata
            self.last_updated = data.get("last_updated", "")
            self.last_save_path = data.get("last_save_path", "")
            
        except Exception as e:
            print(f"Warning: Could not load TODO file: {e}")
            self.todos = []
    
    def save_todos(self) -> None:
        """Save TODO items to file."""
        data = {
            "last_updated": datetime.now().isoformat(),
            "last_save_path": self._last_save_path or "",
            "todos": [todo.to_dict() for todo in self.todos],
            "progress_cache": {k: v.to_dict() for k, v in self._progress_cache.items()}
        }
        
        # Write to temp file first, then rename (atomic operation)
        temp_file = self.todo_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        temp_file.replace(self.todo_file)
    
    def add_todo(
        self, 
        item_id: str, 
        name: str, 
        todo_type: TodoType, 
        target_amount: int,
        is_tracked: bool = True
    ) -> Optional[TodoItem]:
        """Add a new TODO item. Returns None if a TODO with the same item_id already exists."""
        # Check for duplicates by item_id
        for existing in self.todos:
            if existing.item_id == item_id:
                return None  # Duplicate, don't add
        
        todo = TodoItem(
            id=str(uuid.uuid4()),
            item_id=item_id,
            name=name,
            todo_type=todo_type,
            target_amount=target_amount,
            current_amount=0,
            is_complete=False,
            is_tracked=is_tracked
        )
        
        self.todos.append(todo)
        self.save_todos()
        return todo
    
    def remove_todo(self, todo_id: str) -> bool:
        """Remove a TODO item by ID."""
        for i, todo in enumerate(self.todos):
            if todo.id == todo_id:
                self.todos.pop(i)
                self._progress_cache.pop(todo_id, None)
                self.save_todos()
                return True
        return False
    
    def update_todo(
        self, 
        todo_id: str,
        name: Optional[str] = None,
        target_amount: Optional[int] = None,
        is_tracked: Optional[bool] = None
    ) -> bool:
        """Update a TODO item's properties."""
        for todo in self.todos:
            if todo.id == todo_id:
                if name is not None:
                    todo.name = name
                if target_amount is not None:
                    todo.target_amount = target_amount
                    todo.is_complete = False  # Reset completion status
                if is_tracked is not None:
                    todo.is_tracked = is_tracked
                self.save_todos()
                return True
        return False
    
    def get_todo_by_id(self, todo_id: str) -> Optional[TodoItem]:
        """Get a TODO item by ID."""
        for todo in self.todos:
            if todo.id == todo_id:
                return todo
        return None
    
    def get_todos_by_type(self, todo_type: TodoType) -> List[TodoItem]:
        """Get all TODO items of a specific type."""
        return [t for t in self.todos if t.todo_type == todo_type and t.is_tracked]
    
    def get_active_todos(self) -> List[TodoItem]:
        """Get all active (tracked) TODO items."""
        return [t for t in self.todos if t.is_tracked]
    
    def get_completed_todos(self) -> List[TodoItem]:
        """Get all completed TODO items."""
        return [t for t in self.todos if t.is_complete and t.is_tracked]
    
    def update_progress_from_save(
        self, 
        save_path: str, 
        refresh_data: bool = True
    ) -> Dict[str, TodoProgress]:
        """
        Update all TODO progress based on save file data.
        
        Args:
            save_path: Path to save file
            refresh_data: Whether to reload save data (True) or use cached
            
        Returns:
            Dictionary of todo_id -> TodoProgress
        """
        if refresh_data or self._last_save_data is None or self._last_save_path != save_path:
            try:
                self._last_save_data = load_save_data(save_path)
                self._last_save_path = save_path
            except Exception as e:
                print(f"Error loading save: {e}")
                return {}
        
        if self._last_save_data is None:
            return {}
        
        # Get analysis data
        storage = get_storage_analysis(self._last_save_data)
        currencies = get_currency_totals(self._last_save_data)
        deathbag = get_deathbag_analysis(self._last_save_data)
        dustin = get_dustin_sent_analysis(self._last_save_data)
        metadata = get_save_metadata(self._last_save_data)
        
        progress_updates: Dict[str, TodoProgress] = {}
        
        for todo in self.todos:
            if not todo.is_tracked:
                continue

            db_count = 0  # Initialize deathbag count

            progress = TodoProgress(
                todo_id=todo.id,
                current_amount=todo.current_amount,
                target_amount=todo.target_amount,
                is_complete=todo.is_complete,
                progress_percentage=todo.progress_percentage(),
                last_updated=datetime.now().isoformat(),
                source_type="",
                source_info=""
            )
            
# Determine current amount based on item type
            if todo.todo_type == TodoType.MATERIAL:
                storage_count = storage.get("items", {}).get(todo.item_id, 0)
                db_count = deathbag.get("items", {}).get(todo.item_id, 0)
                du_count = dustin.get(todo.item_id, 0)
                progress.source_type = "storage+deathbag+dustin"
                progress.source_info = f"Material: {todo.item_id}"
                current = storage_count

            elif todo.todo_type == TodoType.MUSHROOM:
                storage_count = storage.get("mushrooms", {}).get(todo.item_id, 0)
                db_count = deathbag.get("mushrooms", {}).get(todo.item_id, 0)
                du_count = 0
                progress.source_type = "storage+deathbag"
                progress.source_info = f"Mushroom: {todo.item_id}"
                current = storage_count

            elif todo.todo_type == TodoType.BEAST:
                storage_count = storage.get("beasts", {}).get(todo.item_id, 0)
                db_count = deathbag.get("beasts", {}).get(todo.item_id, 0)
                du_count = 0
                progress.source_type = "storage+deathbag"
                progress.source_info = f"Beast: {todo.item_id}"
                current = storage_count

            elif todo.todo_type == TodoType.CURRENCY:
                currency_map = {
                    "DM": "dm",
                    "KC": "kc",
                    "SPL": "spl",
                    "Bloodnium": "bloodnium",
                    "RE Points": "recycle_points"
                }
                currency_key = currency_map.get(todo.item_id, "")
                current = currencies.get(currency_key, 0) if currency_key else 0
                progress.source_type = "currency"
                progress.source_info = f"Currency: {todo.item_id}"
            
            else:
                current = 0
                db_count = 0
                du_count = 0

            progress.current_amount = current
            progress.progress_percentage = min(100.0, ((current + db_count + du_count) / todo.target_amount * 100) if todo.target_amount > 0 else 100.0)
            progress.is_complete = (current + db_count + du_count) >= todo.target_amount

            # Update the actual todo item
            todo.current_amount = current
            todo.deathbag_amount = db_count
            todo.dustin_amount = du_count
            todo.is_complete = progress.is_complete
            
            progress_updates[todo.id] = progress
            self._progress_cache[todo.id] = progress
        
        self.save_todos()
        return progress_updates
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """Get a summary of all TODO progress."""
        if not self.todos:
            return {
                "total": 0,
                "active": 0,
                "completed": 0,
                "pending": 0,
                "overall_progress": 0.0
            }
        
        total = len(self.todos)
        active = len([t for t in self.todos if t.is_tracked])
        completed = len([t for t in self.todos if t.is_complete and t.is_tracked])
        pending = active - completed
        
        if active > 0:
            total_progress = sum(t.progress_percentage() for t in self.todos if t.is_tracked)
            overall_progress = total_progress / active
        else:
            overall_progress = 0.0
        
        return {
            "total": total,
            "active": active,
            "completed": completed,
            "pending": pending,
            "overall_progress": overall_progress
        }
    
    def get_items_by_category(self) -> Dict[str, List[TodoItem]]:
        """Group TODO items by category."""
        categories = {
            "Materials": [],
            "Mushrooms": [],
            "Beasts": [],
            "Currencies": []
        }
        
        type_map = {
            TodoType.MATERIAL: "Materials",
            TodoType.MUSHROOM: "Mushrooms",
            TodoType.BEAST: "Beasts",
            TodoType.CURRENCY: "Currencies"
        }
        
        for todo in self.todos:
            if todo.is_tracked:
                cat = type_map.get(todo.todo_type, "Other")
                categories[cat].append(todo)
        
        return categories
    
    def clear_completed(self) -> int:
        """Remove all completed TODO items."""
        completed = [t for t in self.todos if t.is_complete]
        for todo in completed:
            self.todos.remove(todo)
            self._progress_cache.pop(todo.id, None)
        
        if completed:
            self.save_todos()
        
        return len(completed)
    
    def reset_all_progress(self) -> None:
        """Reset all TODO items to incomplete."""
        for todo in self.todos:
            todo.current_amount = 0
            todo.is_complete = False
        self._progress_cache.clear()
        self.save_todos()
    
    def export_to_dict(self) -> Dict[str, Any]:
        """Export manager state for serialization."""
        return {
            "todos": [t.to_dict() for t in self.todos],
            "progress_cache": {k: v.to_dict() for k, v in self._progress_cache.items()},
            "last_updated": datetime.now().isoformat(),
            "last_save_path": self._last_save_path or ""
        }
    
    def import_from_dict(self, data: Dict[str, Any]) -> None:
        """Import manager state from serialized data."""
        self.todos = [
            TodoItem.from_dict(item) 
            for item in data.get("todos", [])
        ]
        self._progress_cache = {
            k: TodoProgress.from_dict(v)
            for k, v in data.get("progress_cache", {}).items()
        }
        self.last_updated = data.get("last_updated", "")
        self._last_save_path = data.get("last_save_path", "")


class ItemDatabase:
    """Lookup database for item names and metadata."""
    
    def __init__(self):
        self._items: Dict[str, Dict[str, Any]] = {}
        self._load_default_database()
    
    def _load_default_database(self):
        """Load item names from default data files."""
        project_root = Path(__file__).parent.parent
        
        # Materials database - uses name_en field
        materials_file = project_root / "all_materials_db.json"
        if materials_file.exists():
            try:
                with open(materials_file, "r", encoding="utf-8") as f:
                    materials = json.load(f)
                    for item in materials:
                        if isinstance(item, dict) and "itemid" in item:
                            # Use name_en if available, fallback to itemid
                            name = item.get("name_en") or item.get("name") or item["itemid"]
                            self._items[item["itemid"]] = {
                                "name": name,
                                "type": "material",
                                "category": item.get("category", "Unknown")
                            }
            except Exception:
                pass
        
        # Shrooms and beasts database - uses name_en field
        beasts_file = project_root / "all_shrooms_beasts_db.json"
        if beasts_file.exists():
            try:
                with open(beasts_file, "r", encoding="utf-8") as f:
                    beasts_db = json.load(f)
                    for item_id, data in beasts_db.items():
                        if isinstance(data, dict):
                            # Use name_en if available, fallback to item_id
                            name = data.get("name_en") or data.get("name") or item_id
                            item_type = "mushroom" if item_id.startswith("MSR_") else "beast"
                            self._items[item_id] = {
                                "name": name,
                                "type": item_type,
                                "category": data.get("category_en", "Unknown")
                            }
            except Exception:
                pass
        
        # Add common currencies
        self._items["DM"] = {"name": "Death Metals", "type": "currency", "category": "Currency"}
        self._items["KC"] = {"name": "Kill Coins", "type": "currency", "category": "Currency"}
        self._items["SPL"] = {"name": "Splithium", "type": "currency", "category": "Currency"}
        self._items["Bloodnium"] = {"name": "Bloodnium", "type": "currency", "category": "Currency"}
        self._items["RE Points"] = {"name": "RE Points", "type": "currency", "category": "Currency"}
    
    def get_item_info(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get information about an item."""
        return self._items.get(item_id)
    
    def search_items(self, query: str) -> List[Dict[str, Any]]:
        """Search for items matching a query."""
        query = query.lower()
        results = []
        
        for item_id, info in self._items.items():
            if query in item_id.lower() or query in info.get("name", "").lower():
                results.append({
                    "id": item_id,
                    "name": info.get("name", item_id),
                    "type": info.get("type", "unknown"),
                    "category": info.get("category", "Unknown")
                })
        
        return results
    
    def get_all_items_by_type(self, type_name: str) -> List[Dict[str, Any]]:
        """Get all items of a specific type from the database.
        
        Args:
            type_name: Display name like "Material", "Mushroom", "Beast", "Currency"
            
        Returns:
            List of item dictionaries sorted by name
        """
        type_map = {
            "Material": TodoType.MATERIAL,
            "Mushroom": TodoType.MUSHROOM,
            "Beast": TodoType.BEAST,
            "Currency": TodoType.CURRENCY
        }
        target_type = type_map.get(type_name)
        if not target_type:
            return []
        
        results = []
        for item_id, info in self._items.items():
            if info.get("type") == target_type.value:
                results.append({
                    "id": item_id,
                    "name": info.get("name", item_id),
                    "type": info.get("type", "unknown"),
                    "category": info.get("category", "Unknown")
                })
        
        # Sort by name for better UX
        results.sort(key=lambda x: x['name'].lower())
        return results


if __name__ == "__main__":
    # Simple test
    manager = TodoManager()
    
    print("=== TODO Manager Test ===")
    print(f"Loaded {len(manager.todos)} TODO items")
    
    if manager.todos:
        for todo in manager.todos:
            print(f"  - [{todo.todo_type.value}] {todo.name}: {todo.current_amount}/{todo.target_amount}")
    
    print("\nItem search test:")
    db = ItemDatabase()
    results = db.search_items("copper")
    for r in results[:5]:
        print(f"  {r['id']}: {r['name']} ({r['type']})")
