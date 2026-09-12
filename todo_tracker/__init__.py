# -*- coding: utf-8 -*-
"""Let-It-Die Save TODO Tracker - A read-only progress tracker for tower grinding goals.

This program monitors save files for material, beast, and currency progress
towards user-defined targets. NO save editing capability - purely read-only
to prevent save corruption.
"""

__version__ = "1.0.0"
__author__ = "Upstage AI"

from todo_tracker.read_save import load_save_data, get_storage_analysis, get_currency_totals, get_deathbag_analysis, get_dustin_sent_analysis
from todo_tracker.todo_manager import TodoManager, TodoItem, TodoType
from todo_tracker.gui import TodoTrackerApp

__all__ = [
    'load_save_data',
    'get_storage_analysis',
    'get_currency_totals',
    'TodoManager',
    'TodoItem',
    'TodoType',
    'TodoTrackerApp',
]
