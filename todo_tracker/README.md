# Let-It-Die TODO Tracker

A read-only progress tracking application for Let-It-Die. Monitor your grinding progress for materials, mushrooms, beasts, and currencies without ever modifying your save files.

## Features

- **Read-Only Operation**: NEVER modifies save files - only reads data to track progress
- **Multiple Item Types**: Track materials (ITMT_*), mushrooms (MSR_*), beasts (BST_*), and currencies
- **Target Setting**: Set target amounts for each item and monitor progress
- **Auto-Refresh**: Automatically updates progress every 5 seconds while game is running
- **Save/Load TODOs**: Your TODO list persists between sessions
- **Item Database**: Built-in lookup for item names and metadata

## Quick Start

### Requirements
- Python 3.8+
- PySide6 (for GUI): `pip install PySide6`
- Project dependencies: `pip install -r requirements.txt`

### Running the Application

From the project root directory:

```bash
# With a specific save file
python start_todo_tracker.py --save "/path/to/your/save.sav"

# Without arguments (will try to find save automatically)
python start_todo_tracker.py
```

Or run directly from the todo_tracker directory:

```bash
cd todo_tracker
python gui.py
```

### Using the Application

1. **Select Save File**: Click "Select Save File" button or press Ctrl+O
2. **Add TODOs**: Click "Add TODO" or press Ctrl+N
3. **Set Target**: Enter the item ID (e.g., "ITMT_COPPER_1") and target amount
4. **Track Progress**: The application automatically reads your save file and updates progress
5. **Monitor**: Watch progress bars fill as you grind in-game

## Supported Item Types

### Materials (Type: material)
Raw materials stored in the Coin Locker.
Examples: `ITMT_COPPER_1`, `ITMT_IRON_5`, `ITMT_STONE_SPO_1`

### Mushrooms (Type: mushroom)
Mushroom monsters stored in the Coin Locker.
Examples: `MSR_001` (Life Shroom), `MSR_043`

### Beasts (Type: beast)
Beast monsters stored in the Coin Locker.
Examples: `BST_LION`, `BST_ELEPHANT`, `BST_SNAIL`

### Currencies (Type: currency)
In-game currencies (always tracked, not storage-dependent):
- **DM**: Death Metals
- **KC**: Kill Coins
- **SPL**: Splithium
- **Bloodnium**: Bloodnium points
- **RE Points**: Recycling points

## Project Structure

```
todo_tracker/
├── __init__.py           # Package initialization
├── todo_types.py         # Data classes (TodoItem, TodoType)
├── todo_manager.py       # TODO list management and persistence
├── read_save.py          # Save file reading (read-only!)
└── gui.py                # PySide6 GUI application
```

## How It Works

1. **Loading Save**: Uses the same decompression logic as the main save editor (read-only)
2. **Analyzing Storage**: Scans `soul.cl` (Coin Locker) to count stored items
3. **Reading Currencies**: Extracts currency values from `user.*` and `soul.*` fields
4. **Tracking Progress**: Compares current amounts against user-set targets
5. **Persistence**: TODO list saved to `~/.lid_todo_tracker/todo_list.json`

## Safety Guarantees

This application:
- ❌ NEVER writes to save files
- ❌ NEVER modifies save data
- ✅ Only reads decompressed JSON data
- ✅ Uses atomic read operations
- ✅ Validates save file format before reading

## Configuration

TODO list is stored in: `~/.lid_todo_tracker/todo_list.json`

You can backup this file to preserve your TODO list across systems.

## Troubleshooting

### "Invalid save file"
- Ensure you're selecting a `.sav` file, not a `.bak` backup
- The file must be from the same Steam account

### "No items found"
- Make sure items are stored in the Coin Locker (not equipped or in use)
- Items must have an owner of "COIN_LOCKER"

### Items not updating
- The game must save progress for changes to be detected
- Auto-refresh runs every 5 seconds - toggle off/on if needed
- Click "Refresh" to force an immediate update

## License

Same as the parent project (see LICENSE file in project root).

## Credits

Built on top of the Let-It-Die Save Editor by Upstage AI.
Uses PySide6 for the GUI framework.

## Disclaimer

This tool is for personal progress tracking only. 
It does NOT modify save files in any way.
Use at your own discretion - always backup your saves before using any save-related tool.
