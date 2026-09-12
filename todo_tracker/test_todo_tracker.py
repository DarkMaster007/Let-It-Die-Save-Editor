#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test harness for the TODO Tracker module.

Usage:
    python test_todo_tracker.py [--save <path>]
    
Tests:
    1. Loading save file
    2. Analyzing storage
    3. Reading currencies
    4. Creating TODO items
    5. Updating progress
"""

import sys
import os
from pathlib import Path

# Add parent directory to sys.path for imports
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(script_dir))

from todo_tracker.read_save import (
    load_save_data,
    get_storage_analysis,
    get_currency_totals,
    get_save_metadata,
    validate_save_file
)
from todo_tracker.todo_types import TodoItem, TodoType
from todo_tracker.todo_manager import TodoManager, ItemDatabase


def print_banner():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║          LET IT DIE - TODO TRACKER TEST HARNESS                  ║
║          Read-only save file progress tracker                    ║
╚══════════════════════════════════════════════════════════════════╝
    """)


def test_save_loading(save_path: str):
    """Test loading and analyzing a save file."""
    print(f"\n{'='*60}")
    print(f"TEST: Loading save file")
    print(f"{'='*60}")
    
    # Validate
    valid, msg = validate_save_file(save_path)
    print(f"Validation: {msg}")
    if not valid:
        print("ERROR: Invalid save file")
        return None
    
    # Load
    print(f"\nLoading: {save_path}")
    try:
        data = load_save_data(save_path)
        print("✓ Save file loaded successfully")
    except Exception as e:
        print(f"✗ Error loading save: {e}")
        return None
    
    # Get metadata
    metadata = get_save_metadata(data)
    print(f"\nPlayer Info:")
    print(f"  Rank: {metadata.get('player_rank', 'N/A')}")
    print(f"  Rank Points: {metadata.get('rank_points', 0):,}")
    print(f"  Bank Level: {metadata.get('bank_level', 'N/A')}")
    print(f"  Tank Level: {metadata.get('tank_level', 'N/A')}")
    
    # Storage analysis
    storage = get_storage_analysis(data)
    print(f"\nStorage (Coin Locker):")
    print(f"  Total slots: {storage['total_slots']:,}")
    print(f"  Used slots: {storage['used_slots']:,}")
    print(f"  Free slots: {storage['free_slots']:,}")
    print(f"  Unique materials: {len(storage['items'])}")
    print(f"  Unique mushrooms: {len(storage['mushrooms'])}")
    print(f"  Unique beasts: {len(storage['beasts'])}")
    
    # Currencies
    currencies = get_currency_totals(data)
    print(f"\nCurrencies:")
    for name, amount in currencies.items():
        print(f"  {name}: {amount:,}")
    
    return data


def test_todo_manager(save_path: str):
    """Test the TODO manager functionality."""
    print(f"\n{'='*60}")
    print(f"TEST: TODO Manager")
    print(f"{'='*60}")
    
    # Create manager
    manager = TodoManager()
    print(f"✓ TODO Manager initialized")
    print(f"  TODO file: {manager.todo_file}")
    print(f"  Loaded {len(manager.todos)} existing TODO items")
    
    # Show existing items
    if manager.todos:
        print(f"\nExisting TODO items:")
        for todo in manager.todos:
            progress = todo.progress_percentage()
            status = "✓" if todo.is_complete else "○"
            print(f"  {status} [{todo.todo_type.value}] {todo.name}: {todo.current_amount:,}/{todo.target_amount:,} ({progress:.1f}%)")
    
    # Add some test items if empty
    if not manager.todos:
        print(f"\nAdding test TODO items...")
        
        # Add a currency goal
        dm_todo = manager.add_todo("DM", "Death Metals Goal", TodoType.CURRENCY, 5000)
        print(f"✓ Added: {dm_todo.name} ({dm_todo.target_amount:,} DM)")
        
        # Add a material goal
        copper_todo = manager.add_todo("ITMT_COPPER_1", "Copper Ore Goal", TodoType.MATERIAL, 1000)
        print(f"✓ Added: {copper_todo.name} ({copper_todo.target_amount:,} units)")
        
        # Add a mushroom goal
        mushroom_todo = manager.add_todo("MSR_001", "Life Shroom Goal", TodoType.MUSHROOM, 500)
        print(f"✓ Added: {mushroom_todo.name} ({mushroom_todo.target_amount:,} units)")
        
        # Add a beast goal
        beast_todo = manager.add_todo("BST_LION", "Lion Beast Goal", TodoType.BEAST, 100)
        print(f"✓ Added: {beast_todo.name} ({beast_todo.target_amount:,} units)")
    
    # Update progress from save
    print(f"\nUpdating progress from save file...")
    try:
        progress = manager.update_progress_from_save(save_path, refresh_data=True)
        print(f"✓ Updated {len(progress)} TODO items")
        
        # Show progress
        print(f"\nProgress Update:")
        for todo_id, prog in progress.items():
            todo = manager.get_todo_by_id(todo_id)
            if todo:
                status = "✓ COMPLETE" if prog.is_complete else "○ IN PROGRESS"
                print(f"  {status} [{prog.source_type}] {todo.name}")
                print(f"        {prog.current_amount:,} / {prog.target_amount:,} ({prog.progress_percentage:.1f}%)")
                print(f"        Source: {prog.source_info}")
    except Exception as e:
        print(f"✗ Error updating progress: {e}")
    
    # Summary
    summary = manager.get_progress_summary()
    print(f"\nProgress Summary:")
    print(f"  Total TODOs: {summary['total']}")
    print(f"  Active: {summary['active']}")
    print(f"  Completed: {summary['completed']}")
    print(f"  Pending: {summary['pending']}")
    print(f"  Overall Progress: {summary['overall_progress']:.1f}%")


def test_item_database():  # Skip GUI-related tests in CLI mode
    """Test the item database lookup."""
    print(f"\n{'='*60}")
    print(f"TEST: Item Database")
    print(f"{'='*60}")
    
    db = ItemDatabase()
    print(f"✓ Item Database loaded")
    print(f"  Total items: {len(db._items)}")
    
    # Search for some items
    searches = ["copper", "shroom", "lion", "DM"]
    for query in searches:
        results = db.search_items(query)
        print(f"\nSearch '{query}': {len(results)} results")
        for r in results[:3]:
            print(f"  {r['id']}: {r['name']} ({r['type']})")


def main():
    print_banner()
    
    # Find save file
    save_path = None
    
    if len(sys.argv) > 1:
        # Check command line arguments
        if "--save" in sys.argv:
            idx = sys.argv.index("--save")
            if idx + 1 < len(sys.argv):
                save_path = sys.argv[idx + 1]
    
    if not save_path:
        # Try to find a save file in common locations
        project_root = Path(__file__).parent.parent
        savedata_dir = project_root / "Savedata"
        
        if savedata_dir.exists():
            for f in savedata_dir.glob("*.sav"):
                if not f.name.endswith(".bak"):
                    save_path = str(f)
                    break
    
    if not save_path:
        # Try the default project save
        default_save = project_root / "Savedata" / "76561198140783693.sav"
        if default_save.exists():
            save_path = str(default_save)
    
    if not save_path:
        print("ERROR: No save file specified or found")
        print(f"\nUsage: python {Path(__file__).name} [--save <path>]")
        print("\nExample: python test_todo_tracker.py --save '/path/to/save.sav'")
        sys.exit(1)
    
    # Run tests
    print(f"Using save file: {save_path}\n")
    
    data = test_save_loading(save_path)
    if data:
        test_todo_manager(save_path)
    
    # test_item_database()  # Skip GUI-related tests in CLI mode
    
    print(f"\n{'='*60}")
    print("ALL TESTS COMPLETE")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
