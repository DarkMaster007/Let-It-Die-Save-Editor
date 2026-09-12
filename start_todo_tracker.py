#!/usr/bin/env python3
"""
Let-It-Die TODO Tracker Launcher

A read-only progress tracker for monitoring grinding goals in Let-It-Die.

Usage:
    python start_todo_tracker.py [--save <path>]
    
Options:
    --save <path>    Path to save file to monitor (optional)
    
Examples:
    python start_todo_tracker.py
    python start_todo_tracker.py --save "C:\Games\LET IT DIE\Savedata\76561198140783693.sav"
"""

import sys
import os
from pathlib import Path

# Get the project root directory
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    application_path = os.path.dirname(sys.executable)
else:
    # Running as script
    application_path = os.path.dirname(os.path.abspath(__file__))

project_root = Path(__file__).parent.parent

# Add project root to sys.path
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Also add the todo_tracker directory
todo_tracker_dir = project_root / "todo_tracker"
if str(todo_tracker_dir) not in sys.path:
    sys.path.insert(0, str(todo_tracker_dir))


def main():
    """Main entry point."""
    # Parse command line arguments
    save_path = None
    
    if "--save" in sys.argv:
        idx = sys.argv.index("--save")
        if idx + 1 < len(sys.argv):
            save_path = sys.argv[idx + 1]
    
    # Try to find a default save file if none specified
    if not save_path:
        savedata_dir = project_root / "Savedata"
        if savedata_dir.exists():
            for f in savedata_dir.glob("*.sav"):
                if not f.name.endswith(".bak"):
                    save_path = str(f)
                    break
    
    print("""
╔══════════════════════════════════════════════════════════════════╗
║          LET IT DIE - TODO TRACKER                              ║
║          Read-only progress tracking for tower grinding         ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    # Import and run the GUI application
    try:
        from todo_tracker.gui import TodoTrackerApp
        
        from PySide6.QtWidgets import QApplication
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        
        window = TodoTrackerApp()
        
        # Set save file if provided
        if save_path:
            window.set_save_file(save_path)
        
        window.show()
        
        print(f"Application started successfully!")
        if save_path:
            print(f"Monitoring: {save_path}")
        else:
            print(f"Use Ctrl+O or click 'Select Save File' to choose a save file")
        
        sys.exit(app.exec())
        
    except ImportError as e:
        print(f"Error: Failed to import GUI module: {e}")
        print("\nPossible causes:")
        print("1. PySide6 is not installed: pip install PySide6")
        print("2. Running in a headless environment without display")
        print("\nTrying to run in CLI mode instead...")
        
        # Fall back to CLI test mode
        try:
            from todo_tracker.test_todo_tracker import main as cli_main
            sys.argv.append("--save")
            sys.argv.append(save_path or str(project_root / "Savedata" / "76561198140783693.sav"))
            cli_main()
        except Exception as cli_error:
            print(f"CLI mode also failed: {cli_error}")
            sys.exit(1)
    except Exception as e:
        print(f"Error starting application: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
