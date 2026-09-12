# -*- coding: utf-8 -*-
"""TODO item types and configuration for the tracker."""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class TodoType(Enum):
    """Types of items that can be tracked."""
    MATERIAL = "material"      # Raw materials (ITMT_*)
    MUSHROOM = "mushroom"      # Shrooms (MSR_*)
    BEAST = "beast"           # Beasts (BST_*)
    CURRENCY = "currency"     # In-game currencies


@dataclass
class TodoItem:
    """A single TODO item representing a grinding goal."""
    id: str                    # Unique identifier for this TODO entry
    item_id: str              # Item identifier (e.g., "ITMT_COPPER_1", "BST_ELEPHANT")
    name: str                  # Human-readable name
    todo_type: TodoType        # Type of item
    target_amount: int         # Target quantity to grind
    current_amount: int = 0    # Current quantity in save (storage only)
    deathbag_amount: int = 0   # Current quantity in deathbag (fighter inventory)
    dustin_amount: int = 0     # Dustin-sent items (Reward Box / soul.present pending)
    is_complete: bool = False  # Whether target reached
    is_tracked: bool = True    # Whether actively tracked
    
    def progress_percentage(self) -> float:
        """Return progress as percentage (0-100), counting storage + deathbag + dustin."""
        total = self.current_amount + self.deathbag_amount + self.dustin_amount
        if self.target_amount <= 0:
            return 100.0 if total >= self.target_amount else 0.0
        return min(100.0, (total / self.target_amount) * 100.0)
    
    def remaining(self) -> int:
        """Return amount still needed, subtracting storage + deathbag + dustin."""
        if self.is_complete:
            return 0
        total = self.current_amount + self.deathbag_amount + self.dustin_amount
        return max(0, self.target_amount - total)
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            'id': self.id,
            'item_id': self.item_id,
            'name': self.name,
            'todo_type': self.todo_type.value,
            'target_amount': self.target_amount,
            'current_amount': self.current_amount,
            'deathbag_amount': self.deathbag_amount,
            'dustin_amount': self.dustin_amount,
            'is_complete': self.is_complete,
            'is_tracked': self.is_tracked
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TodoItem':
        """Deserialize from dictionary."""
        return cls(
            id=data['id'],
            item_id=data.get('item_id', data['id']),
            name=data['name'],
            todo_type=TodoType(data['todo_type']),
            target_amount=data['target_amount'],
            current_amount=data.get('current_amount', 0),
            deathbag_amount=data.get('deathbag_amount', 0),
            dustin_amount=data.get('dustin_amount', 0),
            is_complete=data.get('is_complete', False),
            is_tracked=data.get('is_tracked', True)
        )
