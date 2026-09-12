#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Let-It-Die TODO Tracker - Main Application

A read-only progress tracker for monitoring grinding goals in Let-It-Die.
Monitors materials, mushrooms, beasts, and currencies from save files.

Features:
- Select save file to monitor
- Add/edit/delete grinding goals (TODO items)
- Track progress towards targets
- Monitor currencies (DM, KC, SPL, Bloodnium, RE Points)
- Auto-refresh when save changes
- Save/load TODO lists

IMPORTANT: This application is READ-ONLY and will NEVER modify save files.
"""

import sys
import os

# Ensure we can import from project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QListWidget,
    QListWidgetItem, QSplitter, QGroupBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
    QProgressBar, QFormLayout, QScrollArea, QFrame, QSizePolicy,
    QToolBar, QStatusBar, QMenuBar, QMenu, QTabWidget,
    QCheckBox, QSpinBox, QDoubleSpinBox, QStyle, QColorDialog,
    QDialog
)
from PySide6.QtCore import (
    Qt, QTimer, Signal, Slot, QThread, QObject, QSize
)
from PySide6.QtGui import QFont, QPalette, QColor, QIcon, QAction, QPainter
from PySide6.QtWidgets import QStyledItemDelegate, QTableWidget, QTableWidgetItem

from todo_tracker.todo_types import TodoItem, TodoType
from todo_tracker.todo_manager import TodoManager, ItemDatabase
from todo_tracker.read_save import (
    load_save_data,
    get_storage_analysis,
    get_currency_totals,
    get_deathbag_analysis,
    get_dustin_sent_analysis,
    validate_save_file,
    get_save_metadata,
)


# Color scheme constants
COLOR_BG = "#1a1a2e"
COLOR_PANEL = "#16213e"
COLOR_ACCENT = "#0f3460"
COLOR_HIGHLIGHT = "#e94560"
COLOR_TEXT = "#eaeaea"
COLOR_SUCCESS = "#4caf50"
COLOR_WARNING = "#ff9800"
COLOR_TEXT_SECONDARY = "#a0a0a0"


class WorkerThread(QThread):
    """Background thread for loading save data."""
    
    finished = Signal(object, str)  # data, error_message
    progress = Signal(str)
    
    def __init__(self, save_path: str):
        super().__init__()
        self.save_path = save_path
    
    def run(self):
        try:
            self.progress.emit("Loading save file...")
            data = load_save_data(self.save_path)
            self.finished.emit(data, "")
        except Exception as e:
            self.finished.emit(None, str(e))


class ProgressDelegate(QStyledItemDelegate):
    """Delegate that paints deathbag count in green prefix on progress column."""

    def paint(self, painter, option, index):
        db = index.data(Qt.ItemDataRole.UserRole)
        if isinstance(db, int) and db > 0:
            # Read the base text from DisplayRole
            text = index.data(Qt.ItemDataRole.DisplayRole)
            if isinstance(text, str) and "/" in text:
                storage_str, target_str = text.rsplit("/", 1)
                full_text = f"{db}+ {storage_str}/{target_str}"
            else:
                full_text = text

            opt = option
            painter.save()
            # Draw background
            if opt.state & QStyle.StateFlag.State_Selected:
                painter.setBrush(opt.palette.brush(QPalette.ColorRole.Highlight))
            else:
                painter.setBrush(opt.backgroundBrush)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(opt.rect.adjusted(0, 0, -1, -1))

            # Draw storage/target right-aligned in the item's text color
            text_color = opt.palette.color(QPalette.ColorRole.Text)
            if opt.state & QStyle.StateFlag.State_Selected:
                text_color = opt.palette.color(QPalette.ColorRole.HighlightedText)
            painter.setPen(text_color)

            # Draw "storage/target" right-aligned
            painter.drawText(opt.rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, text)

            # Draw "db+ " green prefix right-aligned, ending 1px before the storage/target text starts
            fm = painter.fontMetrics()
            text_w = fm.horizontalAdvance(text)
            prefix = f"{db}+ "
            prefix_w = fm.horizontalAdvance(prefix)
            # prefix_rect: right edge at (cell_right - 1 - text_w), left edge at (cell_right - 1 - text_w - prefix_w)
            prefix_rect = opt.rect.adjusted(-text_w - 1 - prefix_w, 0, -text_w - 1, 0)
            if opt.state & QStyle.StateFlag.State_Selected:
                painter.setPen(QColor("#a5d6a7"))
            else:
                painter.setPen(QColor("#4caf50"))
            painter.drawText(prefix_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, prefix)
            painter.restore()
        else:
            super().paint(painter, option, index)


class TodoTrackerApp(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        
        self.save_path: str = ""
        self.save_data = None
        self.storage_analysis = {}
        self.currency_totals = {}
        
        # Initialize managers
        self.todo_manager = TodoManager()
        self.item_db = ItemDatabase()
        
        # Setup UI
        self.setup_ui()
        self.setup_timer()
        
        # Load existing TODOs
        self.refresh_todo_list()
        
        # Set window title
        self.setWindowTitle("Let-It-Die TODO Tracker")
        self.resize(1000, 700)
    
    def setup_ui(self):
        """Setup the main user interface."""
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Set dark palette
        self.set_dark_theme()
        
        # ===== MENU BAR =====
        self.create_menu_bar()
        
        # ===== TOOL BAR =====
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)
        
        # File selection
        self.file_btn = QPushButton("Select Save File")
        self.file_btn.clicked.connect(self.select_save_file)
        toolbar.addWidget(self.file_btn)
        
        self.file_label = QLabel("No file selected")
        self.file_label.setStyleSheet("color: #a0a0a0;")
        toolbar.addWidget(self.file_label)
        
        toolbar.addSeparator()
        
        # Refresh button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_data)
        toolbar.addWidget(self.refresh_btn)
        
        toolbar.addSeparator()
        
        # Auto-refresh toggle
        self.auto_refresh_cb = QCheckBox("Auto-refresh (5s)")
        self.auto_refresh_cb.setChecked(True)
        self.auto_refresh_cb.toggled.connect(self.toggle_auto_refresh)
        toolbar.addWidget(self.auto_refresh_cb)
        
        # ===== MAIN CONTENT (TABS) =====
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(False)
        self.tabs.setDocumentMode(True)
        
        # Tab 1: TODO List
        self.todo_tab = self.create_todo_tab()
        self.tabs.addTab(self.todo_tab, "TODO List")
        
        # Tab 2: Currencies
        self.currency_tab = self.create_currency_tab()
        self.tabs.addTab(self.currency_tab, "Currencies")
        
        # Tab 3: Storage Summary
        self.storage_tab = self.create_storage_tab()
        self.tabs.addTab(self.storage_tab, "Storage")
        
        main_layout.addWidget(self.tabs)
        
        # ===== STATUS BAR =====
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready", 5000)
    
    def create_menu_bar(self):
        """Create the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        select_action = QAction("Select Save File...", self)
        select_action.setShortcut("Ctrl+O")
        select_action.triggered.connect(self.select_save_file)
        file_menu.addAction(select_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # TODO menu
        todo_menu = menubar.addMenu("&TODO")
        
        add_action = QAction("Add New TODO...", self)
        add_action.setShortcut("Ctrl+N")
        add_action.triggered.connect(self.show_add_todo_dialog)
        todo_menu.addAction(add_action)
        
        edit_action = QAction("Edit Selected TODO...", self)
        edit_action.setShortcut("Ctrl+E")
        edit_action.triggered.connect(self.show_edit_todo_dialog)
        todo_menu.addAction(edit_action)
        
        delete_action = QAction("Delete Selected TODO", self)
        delete_action.setShortcut("Delete")
        delete_action.triggered.connect(self.delete_selected_todo)
        todo_menu.addAction(delete_action)
        
        todo_menu.addSeparator()
        
        clear_action = QAction("Clear Completed TODOs", self)
        clear_action.triggered.connect(self.clear_completed_todos)
        todo_menu.addAction(clear_action)
        
        reset_action = QAction("Reset All Progress", self)
        reset_action.triggered.connect(self.reset_all_progress)
        todo_menu.addAction(reset_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        refresh_action = QAction("Refresh Now", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self.refresh_data)
        view_menu.addAction(refresh_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def create_todo_tab(self) -> QWidget:
        """Create the TODO list tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        
        # Controls
        controls = QHBoxLayout()
        
        self.add_todo_btn = QPushButton("Add TODO")
        self.add_todo_btn.clicked.connect(self.show_add_todo_dialog)
        controls.addWidget(self.add_todo_btn)
        
        self.edit_todo_btn = QPushButton("Edit")
        self.edit_todo_btn.clicked.connect(self.show_edit_todo_dialog)
        controls.addWidget(self.edit_todo_btn)
        
        self.delete_todo_btn = QPushButton("Delete")
        self.delete_todo_btn.clicked.connect(self.delete_selected_todo)
        controls.addWidget(self.delete_todo_btn)
        
        controls.addStretch()
        
        self.toggle_completed_cb = QCheckBox("Show completed")
        self.toggle_completed_cb.setChecked(True)
        self.toggle_completed_cb.toggled.connect(self.refresh_todo_list)
        controls.addWidget(self.toggle_completed_cb)
        
        layout.addLayout(controls)
        
        # Filter by category
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems([
            "All",
            "--- Materials ---",
            "Cloths (Cotton/Hemp/Leather/etc)",
            "Aluminum",
            "Copper",
            "Iron/Steel",
            "Oil",
            "Wood",
            "Faction Metals (DOD/War Ensemble/Candle Wolf/MILK)",
            "Tuber Metals (Scratch/Bullet/Hovering/Bone/Reversal)",
            "Skillshrooms (Death 'Roids)",
            "Sunflower Metals",
            "Jackal Resources",
            "--- Other ---",
            "Mushrooms",
            "Beasts",
            "Currencies"
        ])
        self.filter_combo.currentIndexChanged.connect(self.refresh_todo_list)
        filter_layout.addWidget(self.filter_combo)
        
        layout.addLayout(filter_layout)
        
        # TODO list using QTableWidget for better formatting
        self.todo_table = QTableWidget()
        self.todo_table.setColumnCount(5)
        self.todo_table.setHorizontalHeaderLabels(["", "Name", "Type", "Progress", "Status"])
        self.todo_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.todo_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.todo_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        # Column 3 (Progress): delegate paints green db+ prefix separately via UserRole,
        # so ResizeToContents can't measure it. Use a fixed width that fits the widest
        # content: "99+ 9,999/9,999" = 15 chars plus padding.
        self.todo_table.setColumnWidth(3, 170)
        self.todo_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.todo_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.todo_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.todo_table.setAlternatingRowColors(True)
        self.todo_table.setItemDelegate(ProgressDelegate())

        self.todo_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.todo_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLOR_PANEL};
                border: 1px solid #3a3a5c;
                border-radius: 5px;
                color: {COLOR_TEXT};
            }}
        """)
        self.todo_table.itemSelectionChanged.connect(self.on_todo_selected)
        self.todo_table.cellDoubleClicked.connect(self.on_todo_double_clicked)
        layout.addWidget(self.todo_table, 1)
        
        # Progress bar
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(QLabel("Overall Progress:"))
        
        self.overall_progress = QProgressBar()
        self.overall_progress.setTextVisible(True)
        self.overall_progress.setFormat("%p%")
        progress_layout.addWidget(self.overall_progress)
        
        progress_layout.addStretch()
        self.progress_label = QLabel("0% (0/0)")
        progress_layout.addWidget(self.progress_label)
        
        layout.addLayout(progress_layout)
        
        return tab
    
    def create_currency_tab(self) -> QWidget:
        """Create the currencies display tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        
        # Currency cards
        self.currency_cards = QScrollArea()
        self.currency_cards.setWidgetResizable(True)
        self.currency_cards.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.currency_widget = QWidget()
        self.currency_layout = QVBoxLayout(self.currency_widget)
        self.currency_layout.setSpacing(10)
        
        self.currency_cards.setWidget(self.currency_widget)
        layout.addWidget(self.currency_cards, 1)
        
        # Update currencies
        self.update_currency_display()
        
        return tab
    
    def create_storage_tab(self) -> QWidget:
        """Create the storage summary tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        
        # Storage info group
        storage_group = QGroupBox("Coin Locker Summary")
        storage_layout = QFormLayout(storage_group)
        storage_layout.setSpacing(10)
        
        self.total_slots_label = QLabel("0")
        self.used_slots_label = QLabel("0")
        self.free_slots_label = QLabel("0")
        self.unique_items_label = QLabel("0")
        self.unique_mushrooms_label = QLabel("0")
        self.unique_beasts_label = QLabel("0")
        
        storage_layout.addRow("Total Slots:", self.total_slots_label)
        storage_layout.addRow("Used Slots:", self.used_slots_label)
        storage_layout.addRow("Free Slots:", self.free_slots_label)
        storage_layout.addRow("Unique Materials:", self.unique_items_label)
        storage_layout.addRow("Unique Mushrooms:", self.unique_mushrooms_label)
        storage_layout.addRow("Unique Beasts:", self.unique_beasts_label)
        
        layout.addWidget(storage_group)
        
        # Top items table
        top_group = QGroupBox("Top Stored Items")
        top_layout = QVBoxLayout(top_group)
        
        self.top_table = QTableWidget()
        self.top_table.setColumnCount(4)
        self.top_table.setHorizontalHeaderLabels(["Type", "ID", "Name", "Count"])
        self.top_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.top_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.top_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.top_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.top_table.setAlternatingRowColors(True)
        
        top_layout.addWidget(self.top_table)
        layout.addWidget(top_group, 1)
        
        return tab
    
    def setup_timer(self):
        """Setup auto-refresh timer."""
        self.refresh_timer = QTimer()
        self.refresh_timer.setInterval(5000)  # 5 seconds
        self.refresh_timer.timeout.connect(self.refresh_data)
        
        # Start timer if auto-refresh is checked (default)
        if self.auto_refresh_cb.isChecked():
            self.refresh_timer.start()
    
    def set_dark_theme(self):
        """Apply dark theme to the application."""
        palette = QPalette()
        
        palette.setColor(QPalette.Window, QColor(COLOR_BG))
        palette.setColor(QPalette.WindowText, QColor(COLOR_TEXT))
        palette.setColor(QPalette.Base, QColor(COLOR_PANEL))
        palette.setColor(QPalette.AlternateBase, QColor(COLOR_ACCENT))
        palette.setColor(QPalette.Text, QColor(COLOR_TEXT))
        palette.setColor(QPalette.Button, QColor(COLOR_ACCENT))
        palette.setColor(QPalette.ButtonText, QColor(COLOR_TEXT))
        palette.setColor(QPalette.Link, QColor(COLOR_HIGHLIGHT))
        palette.setColor(QPalette.Highlight, QColor(COLOR_HIGHLIGHT))
        palette.setColor(QPalette.HighlightedText, QColor(COLOR_BG))
        
        self.setPalette(palette)
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {COLOR_BG};
            }}
            QWidget {{
                background-color: {COLOR_BG};
                color: {COLOR_TEXT};
            }}
            QGroupBox {{
                border: 1px solid #3a3a5c;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
                color: {COLOR_TEXT};
                font-weight: bold;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: {COLOR_HIGHLIGHT};
            }}
            QTabWidget::pane {{
                border: 1px solid #3a3a5c;
                border-radius: 5px;
                background-color: {COLOR_PANEL};
            }}
            QTabBar::tab {{
                background-color: {COLOR_PANEL};
                color: {COLOR_TEXT_SECONDARY};
                padding: 8px 15px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background-color: {COLOR_HIGHLIGHT};
                color: white;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: #2a2a4e;
            }}
            QPushButton {{
                background-color: {COLOR_ACCENT};
                color: {COLOR_TEXT};
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {COLOR_HIGHLIGHT};
            }}
            QPushButton:pressed {{
                background-color: #c0354c;
            }}
            QComboBox {{
                background-color: {COLOR_PANEL};
                color: {COLOR_TEXT};
                border: 1px solid #3a3a5c;
                border-radius: 5px;
                padding: 5px 10px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QCheckBox {{
                color: {COLOR_TEXT};
                spacing: 5px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                background-color: {COLOR_PANEL};
                border: 1px solid #3a3a5c;
                border-radius: 3px;
            }}
            QCheckBox::indicator:checked {{
                background-color: {COLOR_HIGHLIGHT};
            }}
            QProgressBar {{
                background-color: {COLOR_PANEL};
                border: 1px solid #3a3a5c;
                border-radius: 5px;
                text-align: center;
                color: {COLOR_TEXT};
            }}
            QProgressBar::chunk {{
                background-color: {COLOR_SUCCESS};
                border-radius: 5px;
            }}
            QTableWidget {{
                background-color: {COLOR_PANEL};
                border: 1px solid #3a3a5c;
                border-radius: 5px;
                color: {COLOR_TEXT};
                gridline-color: #2a2a4e;
            }}
            QTableWidget::item:selected {{
                background-color: {COLOR_HIGHLIGHT};
                color: white;
            }}
            QHeaderView::section {{
                background-color: {COLOR_ACCENT};
                color: {COLOR_TEXT};
                border: none;
                padding: 5px;
                font-weight: bold;
            }}
            QMenuBar {{
                background-color: {COLOR_ACCENT};
                color: {COLOR_TEXT};
                border-bottom: 1px solid #3a3a5c;
            }}
            QMenuBar::item {{
                padding: 5px 10px;
            }}
            QMenuBar::item:selected {{
                background-color: {COLOR_HIGHLIGHT};
            }}
            QMenu {{
                background-color: {COLOR_PANEL};
                border: 1px solid #3a3a5c;
                color: {COLOR_TEXT};
            }}
            QMenu::item:selected {{
                background-color: {COLOR_HIGHLIGHT};
                color: white;
            }}
            QToolBar {{
                background-color: {COLOR_ACCENT};
                border-bottom: 1px solid #3a3a5c;
                spacing: 5px;
            }}
            QStatusBar {{
                background-color: {COLOR_ACCENT};
                color: {COLOR_TEXT_SECONDARY};
            }}
            QScrollArea {{
                border: none;
            }}
            QLineEdit {{
                background-color: {COLOR_PANEL};
                color: {COLOR_TEXT};
                border: 1px solid #3a3a5c;
                border-radius: 5px;
                padding: 5px 10px;
            }}
        """)
    
    def select_save_file(self):
        """Open file dialog to select save file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Let-It-Die Save File",
            "",
            "Save Files (*.sav);;All Files (*)"
        )
        
        if file_path:
            self.set_save_file(file_path)
    
    def set_save_file(self, path: str):
        """Set and validate the save file."""
        valid, msg = validate_save_file(path)
        
        if not valid:
            QMessageBox.warning(
                self,
                "Invalid Save File",
                f"The selected file is not a valid Let-It-Die save file.\n\n{msg}"
            )
            return
        
        self.save_path = path
        self.file_label.setText(os.path.basename(path))
        self.status_bar.showMessage(f"Monitoring: {os.path.basename(path)}")
        
        # Load save data
        self.refresh_data()
    
    def refresh_data(self):
        """Refresh all data from save file."""
        if not self.save_path:
            self.status_bar.showMessage("No save file selected", 3000)
            return
        
        self.status_bar.showMessage("Loading save data...", 5000)
        
        try:
            self.save_data = load_save_data(self.save_path)
            self.storage_analysis = get_storage_analysis(self.save_data)
            self.currency_totals = get_currency_totals(self.save_data)
            
            # Update UI
            self.update_todo_progress()
            self.update_currency_display()
            self.update_storage_display()
            
            self.status_bar.showMessage(
                f"Loaded - Rank: {self.get_player_rank()}", 5000
            )
            
            # Restart timer for next refresh (single-shot pattern for reliability)
            if self.auto_refresh_cb.isChecked():
                self.refresh_timer.start()
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Loading Save",
                f"Failed to load save file:\n{str(e)}"
            )
            self.status_bar.showMessage("Error loading save file", 5000)
    
    def toggle_auto_refresh(self, enabled: bool):
        """Toggle auto-refresh on/off."""
        if enabled:
            # Start timer - will fire after interval, then restart in refresh_data
            self.refresh_timer.start()
        else:
            self.refresh_timer.stop()
    
    def get_player_rank(self) -> str:
        """Get player rank string."""
        if self.save_data:
            metadata = get_save_metadata(self.save_data)
            rank = metadata.get("player_rank", 0)
            points = metadata.get("rank_points", 0)
            return f"Rank {rank} ({points:,} pts)"
        return "N/A"
    
    def get_material_category(self, item_id: str) -> str:
        """Get the category code for a material based on its item ID."""
        if not item_id.startswith("ITMT_"):
            return "other"
        
        parts = item_id.split("_")
        if len(parts) >= 2:
            prefix = parts[1]
            
            # Map to display categories
            category_map = {
                "COTTON": "cloth", "HEMP": "cloth", "LEATHER": "cloth", "WOOL": "cloth",
                "SILK": "cloth", "CARBON": "cloth", "ARAMID": "cloth", "POLYARYLATE": "cloth",
                "FIBER": "cloth",
                
                "ALUMI": "aluminum",
                "COPPER": "copper",
                "IRON": "iron",
                "OIL": "oil",
                "WOOD": "wood",
                "STEROID": "steroid",
                
                "STONE": "stone",
                "DIY": "faction_dod",
                "FAN": "faction_cw",
                "MIL": "faction_mil",
                "SPO": "faction_milk",
                "TBR": "tuber",
                "JAC": "sunflower",
            }
            
            return category_map.get(prefix, "other")
        return "other"
    
    def get_material_color(self, item_id: str, item_name: str = None) -> QColor:
        """Get the display color for a material based on its category and rarity.
        
        Args:
            item_id: The item ID (e.g., "ITMT_STONE_DIY_8")
            item_name: Optional item name for color detection (e.g., "D.O.D. ARMS Platinum Metal")
        """
        # Default color
        default_color = QColor(COLOR_TEXT_SECONDARY)
        
        if not item_id.startswith("ITMT_"):
            return default_color
        
        parts = item_id.split("_")
        if len(parts) < 2:
            return default_color
        
        prefix = parts[1]
        
        # Define color palettes for each category
        # Format: base_color with intensity based on rarity
        
        def lerp_color(base_r, base_g, base_b, factor):
            """Linear interpolation between white and base color.
            
            factor: 0.0 = pure white, 1.0 = full base color
            Returns a color that's "base color mixed into white paint"
            """
            r = int(255 + (base_r - 255) * factor)
            g = int(255 + (base_g - 255) * factor)
            b = int(255 + (base_b - 255) * factor)
            return QColor(r, g, b)
        
        def color_from_rgb(r: int, g: int, b: int, white_factor: float = 0.0) -> QColor:
            wf = max(0.0, min(1.0, white_factor))
            return QColor(
                int(r + (255 - r) * wf),
                int(g + (255 - g) * wf),
                int(b + (255 - b) * wf),
            )
        # Cloths - shades of pink
        if prefix in ["COTTON", "HEMP", "LEATHER", "WOOL", "SILK", "CARBON", "ARAMID", "POLYARYLATE", "FIBER"]:
            rarity = int(parts[-1]) if parts[-1].isdigit() else 1
            base_pink = (255, 105, 180)  # Hot pink
            factor = 0.15 + (rarity * 0.1)  # 0.25 to 0.95
            return lerp_color(*base_pink, factor)
        
        # Aluminum - shades of green
        if prefix == "ALUMI":
            rarity = int(parts[-1]) if parts[-1].isdigit() else 1
            base_green = (0, 128, 0)  # Green
            factor = 0.15 + (rarity * 0.1)
            return lerp_color(*base_green, factor)
        
        # Copper - shades of brown
        if prefix == "COPPER":
            rarity = int(parts[-1]) if parts[-1].isdigit() else 1
            base_brown = (139, 69, 19)  # Saddle brown
            factor = 0.15 + (rarity * 0.1)
            return lerp_color(*base_brown, factor)
        
        # Iron - shades of gray
        if prefix == "IRON":
            rarity = int(parts[-1]) if parts[-1].isdigit() else 1
            gray = 25 + (rarity * 15)  # 40 to 160
            return lerp_color(gray, gray, gray, 1.0)
        
        # Oil - shades of blue
        if prefix == "OIL":
            rarity = int(parts[-1]) if parts[-1].isdigit() else 1
            base_blue = (30, 144, 255)  # Dodger blue
            factor = 0.15 + (rarity * 0.1)
            return lerp_color(*base_blue, factor)
        
        # Wood - earthy brown
        if prefix == "WOOD":
            rarity = int(parts[-1]) if parts[-1].isdigit() else 1
            base_earth = (139, 90, 43)  # Peru brown
            factor = 0.15 + (rarity * 0.1)
            return lerp_color(*base_earth, factor)
        
        # Steroids (Death 'Roids)
        if prefix == "STEROID":
            steroid_type = int(parts[-1]) if parts[-1].isdigit() else 1
            steroid_colors = {
                1: (100, 149, 237),
                2: (50, 205, 50),
                3: (25, 25, 112),
                4: (220, 20, 60),
                5: (128, 0, 128),
                6: (255, 140, 0),
            }
            return QColor(*steroid_colors.get(steroid_type, (128, 128, 128)))
        
        # Stone items - faction metals and tubers
        if prefix == "STONE":
            sub = parts[2] if len(parts) > 2 else ""
            rarity = int(parts[-1]) if parts[-1].isdigit() else 1
            
            # Check name for color indicators if available
            name_upper = item_name.upper() if item_name else ""
            is_platinum = "PLATINUM" in name_upper
            is_44ce = "44CE" in name_upper or "H" in name_upper and rarity >= 8
            
            # Faction metals - use color in name
            if sub in ["DIY", "MIL", "FAN", "SPO"]:
                if is_platinum:
                    return QColor(255, 255, 255)  # Pure white for platinum
                if is_44ce:
                    return color_from_rgb(255, 228, 196, 0.85)  # Pale yellowish/skin
                
                # Blue, Green, Black, Red - standard faction colors
                color_map = {
                    1: (135, 206, 250),  # Blue
                    2: (144, 238, 144),  # Green
                    3: (128, 128, 128),  # Black/gray
                    4: (255, 105, 180),  # Red/pink
                    5: (128, 0, 128),    # Purple
                }
                return QColor(*color_map.get(rarity, (200, 200, 200)))
            
            # Tuber metals
            if sub == "TBR":
                # Check item_id AND name for specific tuber type
                item_upper = item_id.upper()
                name_upper = item_name.upper() if item_name else ""
                
                if "SCRATCH" in item_upper or "SCRATCH" in name_upper:
                    return color_from_rgb(173, 216, 230, 0.8)
                if "BULLET" in item_upper or "BULLET" in name_upper:
                    return color_from_rgb(152, 251, 152, 0.8)
                if "HOVERING" in item_upper or "HOVERING" in name_upper:
                    return color_from_rgb(255, 182, 193, 0.8)
                if "BONE" in item_upper or "BONE" in name_upper:
                    return QColor(220, 220, 220)
                if "REVERSAL" in item_upper or "REVERSAL" in name_upper:
                    return color_from_rgb(255, 228, 196, 0.8)
                return QColor(200, 200, 200)
            
            # Sunflower and Jackal resources
            if sub == "JAC":
                if "JAC_X" in item_id:
                    return color_from_rgb(135, 206, 250, 0.85)
                if "JAC_Y" in item_id:
                    return color_from_rgb(255, 228, 196, 0.85)
                if "JAC_Z" in item_id:
                    return QColor(200, 180, 255)
                if "JAC_5" in item_id:
                    return color_from_rgb(255, 182, 193, 0.85)
                if "JAC_2" in item_id:
                    return color_from_rgb(135, 206, 250, 0.85)
                if "JAC_3" in item_id:
                    return color_from_rgb(255, 228, 196, 0.85)
                if "JAC_4" in item_id:
                    return QColor(200, 180, 255)
                return QColor(135, 206, 250)
        
        return default_color
    
    # ===== TODO LIST FUNCTIONS =====
    
    def refresh_todo_list(self):
        """Refresh the TODO list display."""
        self.todo_table.setRowCount(0)
        
        # Filter
        filter_text = self.filter_combo.currentText()
        show_completed = self.toggle_completed_cb.isChecked()
        
        todos = self.todo_manager.todos
        
        # Apply category filter
        if filter_text != "All" and not filter_text.startswith("---"):
            # Determine if this is a material subcategory or other type
            material_subcats = {
                "Cloths (Cotton/Hemp/Leather/etc)": "FIBER",
                "Aluminum": "ALUMI",
                "Copper": "COPPER",
                "Iron/Steel": "IRON",
                "Oil": "OIL",
                "Wood": "WOOD",
                "Faction Metals (DOD/War Ensemble/Candle Wolf/MILK)": "STONE",
                "Tuber Metals (Scratch/Bullet/Hovering/Bone/Reversal)": "STONE",
                "Skillshrooms (Death 'Roids)": "STEROID",
                "Sunflower Metals": "STONE",
                "Jackal Resources": "STONE"
            }
            
            is_material_subcat = filter_text in material_subcats
            is_general_type = filter_text in ["Mushrooms", "Beasts", "Currencies"]
            
            if is_material_subcat or is_general_type:
                filtered_todos = []
                for todo in todos:
                    if todo.todo_type != TodoType.MATERIAL:
                        if is_general_type:
                            type_map = {"Mushrooms": TodoType.MUSHROOM, "Beasts": TodoType.BEAST, "Currencies": TodoType.CURRENCY}
                            if todo.todo_type == type_map.get(filter_text):
                                filtered_todos.append(todo)
                        continue
                    
                    # For material subcategories, check the item_id prefix
                    item_id = todo.item_id
                    if is_material_subcat:
                        cat_code = material_subcats[filter_text]
                        if cat_code == "STONE":
                            # Handle special subcategories for STONE
                            if filter_text == "Faction Metals (DOD/War Ensemble/Candle Wolf/MILK)":
                                if any(x in item_id for x in ["STONE_DIY", "STONE_FAN", "STONE_MIL", "STONE_SPO"]):
                                    filtered_todos.append(todo)
                            elif filter_text == "Tuber Metals (Scratch/Bullet/Hovering/Bone/Reversal)":
                                if "STONE_TBR" in item_id:
                                    filtered_todos.append(todo)
                            elif filter_text == "Sunflower Metals":
                                if "STONE_JAC" in item_id and "_1" not in item_id and "_2" not in item_id:
                                    # Sunflower metals are JAC_2, JAC_3, JAC_4, JAC_5
                                    if any(f"STONE_JAC_{i}_" in item_id for i in [2, 3, 4, 5]):
                                        filtered_todos.append(todo)
                            elif filter_text == "Jackal Resources":
                                if "STONE_JAC_X" in item_id or "STONE_JAC_Y" in item_id or "STONE_JAC_Z" in item_id:
                                    filtered_todos.append(todo)
                            else:
                                # Generic STONE - include all stone items (for initial list)
                                if item_id.startswith("ITMT_STONE_"):
                                    filtered_todos.append(todo)
                        elif item_id.startswith(f"ITMT_{cat_code}_"):
                            filtered_todos.append(todo)
                
                todos = filtered_todos
        
        # Apply completion filter
        if not show_completed:
            todos = [t for t in todos if not t.is_complete]
        
        # Sort: incomplete first, then by category order, then by rarity, then by name
        def todo_sort_key(todo):
            # Default rarity for sorting
            rarity = 9999
            
            # Category order for materials
            if todo.todo_type == TodoType.MATERIAL:
                item_id = todo.item_id
                if item_id.startswith("ITMT_FIBER_") or item_id.startswith("ITMT_COTTON_") or item_id.startswith("ITMT_HEMP_") or item_id.startswith("ITMT_LEATHER_") or item_id.startswith("ITMT_WOOL_") or item_id.startswith("ITMT_SILK_"):
                    cat_order = 1  # Cloths
                elif item_id.startswith("ITMT_ALUMI_"):
                    cat_order = 2  # Aluminum
                elif item_id.startswith("ITMT_COPPER_"):
                    cat_order = 3  # Copper
                elif item_id.startswith("ITMT_IRON_"):
                    cat_order = 4  # Iron
                elif item_id.startswith("ITMT_OIL_"):
                    cat_order = 5  # Oil
                elif item_id.startswith("ITMT_WOOD_"):
                    cat_order = 6  # Wood
                elif item_id.startswith("ITMT_STONE_DIY_") or item_id.startswith("ITMT_STONE_FAN_") or item_id.startswith("ITMT_STONE_MIL_") or item_id.startswith("ITMT_STONE_SPO_"):
                    cat_order = 7  # Faction metals
                elif item_id.startswith("ITMT_STONE_TBR_"):
                    cat_order = 8  # Tuber metals
                elif item_id.startswith("ITMT_STEROID_"):
                    cat_order = 9  # Skillshrooms
                elif item_id.startswith("ITMT_STONE_JAC_") and "_1" not in item_id:
                    # Sunflower metals (JAC_2, JAC_3, JAC_4, JAC_5)
                    if "_2" in item_id:
                        cat_order = 10
                    elif "_3" in item_id:
                        cat_order = 11
                    elif "_4" in item_id:
                        cat_order = 12
                    elif "_5" in item_id:
                        cat_order = 13
                    else:
                        cat_order = 10
                elif item_id.startswith("ITMT_STONE_JAC_X_") or item_id.startswith("ITMT_STONE_JAC_Y_") or item_id.startswith("ITMT_STONE_JAC_Z_"):
                    cat_order = 14  # Jackal resources
                else:
                    cat_order = 99  # Other materials
                
                # Extract rarity number from item_id
                if item_id:
                    parts = item_id.split('_')
                    if len(parts) >= 3 and parts[-1].isdigit():
                        rarity = int(parts[-1])
            elif todo.todo_type == TodoType.MUSHROOM:
                cat_order = 100
            elif todo.todo_type == TodoType.BEAST:
                cat_order = 200
            elif todo.todo_type == TodoType.CURRENCY:
                cat_order = 300
            else:
                cat_order = 999
            
            # Sort by name within category
            name_order = todo.name.lower()
            complete_order = 0 if todo.is_complete else 1
            
            return (complete_order, cat_order, rarity, name_order)
        
        todos.sort(key=todo_sort_key)
        
        # Add items to table
        for row, todo in enumerate(todos):
            self.todo_table.insertRow(row)
            
            # Status icon
            status_item = QTableWidgetItem()
            if todo.is_complete:
                status_item.setText("✓")
                status_item.setForeground(QColor(COLOR_SUCCESS))
            else:
                progress = todo.progress_percentage()
                if progress >= 75:
                    color = "#8bc34a"
                elif progress >= 50:
                    color = COLOR_WARNING
                elif progress > 0:
                    color = "#ff5722"
                else:
                    color = COLOR_TEXT_SECONDARY
                status_item.setText("○")
                status_item.setForeground(QColor(color))
            status_item.setTextAlignment(Qt.AlignCenter)
            self.todo_table.setItem(row, 0, status_item)
            
            # Name
            name_item = QTableWidgetItem(todo.name)
            name_item.setFont(QFont("", 11, QFont.Bold))
            name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            # Apply color as background for materials (easier to see)
            if todo.todo_type == TodoType.MATERIAL:
                # Get item name from database for color detection
                info = self.item_db.get_item_info(todo.item_id)
                item_name = info.get('name') if info else todo.name
                bg_color = self.get_material_color(todo.item_id, item_name or "")
                name_item.setBackground(bg_color)
                name_item.setForeground(QColor(20, 20, 20))  # Dark text for contrast
            elif todo.todo_type == TodoType.MUSHROOM:
                bg_color = QColor(230, 255, 230)  # Very light green background
                name_item.setBackground(bg_color)
                name_item.setForeground(QColor(0, 100, 0))
            elif todo.todo_type == TodoType.BEAST:
                bg_color = QColor(220, 240, 255)  # Very light blue background
                name_item.setBackground(bg_color)
                name_item.setForeground(QColor(0, 50, 100))
            else:
                name_item.setForeground(QColor(COLOR_TEXT))
            self.todo_table.setItem(row, 1, name_item)
            
            # Type
            type_item = QTableWidgetItem(todo.todo_type.value.capitalize())
            type_item.setForeground(QColor(COLOR_HIGHLIGHT))
            self.todo_table.setItem(row, 2, type_item)
            
            # Progress (storage + deathbag/dustin format)
            db = todo.deathbag_amount
            du = todo.dustin_amount
            storage = todo.current_amount
            target = todo.target_amount

            # Combined non-storage count: deathbag + dustin, shown as green "+n" prefix
            non_storage = db + du
            if non_storage > 0:
                # Store combined count in UserRole; delegate paints green prefix
                display_text = f"{storage:,}/{target:,}"
                progress_item = QTableWidgetItem(display_text)
                progress_item.setData(Qt.ItemDataRole.UserRole, non_storage)
            else:
                progress_text = f"{storage:,}/{target:,}"
                progress_item = QTableWidgetItem(progress_text)
            progress_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.todo_table.setItem(row, 3, progress_item)

            # Status
            if todo.is_complete:
                status_text = "COMPLETE"
                status_color = COLOR_SUCCESS
            else:
                remaining = todo.remaining()
                status_text = f"{remaining:,} remaining"
                status_color = COLOR_TEXT_SECONDARY
            status_item2 = QTableWidgetItem(status_text)
            status_item2.setForeground(QColor(status_color))
            self.todo_table.setItem(row, 4, status_item2)

            # Store todo reference
            self.todo_table.setItem(row, 0, status_item)
            status_item.setData(Qt.UserRole, todo)
        
        # Update progress summary
        self.update_progress_summary()
    
    def on_todo_selected(self):
        """Handle TODO selection."""
        selected = self.todo_table.selectedItems()
        if selected:
            for item in selected:
                todo = item.data(Qt.UserRole)
                if todo:
                    db = todo.deathbag_amount
                    if db > 0:
                        msg = f"Selected: {todo.name} - {db}+ {todo.current_amount:,}/{todo.target_amount:,}"
                    else:
                        msg = f"Selected: {todo.name} - {todo.current_amount:,}/{todo.target_amount:,}"
                    self.status_bar.showMessage(msg)
                    break

    def update_todo_progress(self):
        """Update TODO progress from current save data."""
        if not self.save_path or not self.save_data:
            return

        # Load fresh data and update all TODO items directly
        try:
            fresh_data = load_save_data(self.save_path)
            storage = get_storage_analysis(fresh_data)
            currencies = get_currency_totals(fresh_data)
            deathbag = get_deathbag_analysis(fresh_data)
            dustin = get_dustin_sent_analysis(fresh_data)

            # Update all TODO items directly from fresh data
            for todo in self.todo_manager.todos:
                if not todo.is_tracked:
                    continue

                # Determine current amount based on item type
                if todo.todo_type == TodoType.MATERIAL:
                    current = storage.get("items", {}).get(todo.item_id, 0)
                    db_count = deathbag.get("items", {}).get(todo.item_id, 0)
                    du_count = dustin.get(todo.item_id, 0)
                elif todo.todo_type == TodoType.MUSHROOM:
                    current = storage.get("mushrooms", {}).get(todo.item_id, 0)
                    db_count = deathbag.get("mushrooms", {}).get(todo.item_id, 0)
                    du_count = 0
                elif todo.todo_type == TodoType.BEAST:
                    current = storage.get("beasts", {}).get(todo.item_id, 0)
                    db_count = deathbag.get("beasts", {}).get(todo.item_id, 0)
                    du_count = 0
                elif todo.todo_type == TodoType.CURRENCY:
                    currency_map = {
                        "DM": "dm",
                        "KC": "kc",
                        "SPL": "spl",
                        "Bloodnium": "bloodnium",
                        "RE Points": "recycle_points"
                    }
                    current = currencies.get(currency_map.get(todo.item_id, ""), 0)
                    db_count = 0
                    du_count = 0
                else:
                    current = 0
                    db_count = 0
                    du_count = 0

                # Update the todo
                todo.current_amount = current
                todo.deathbag_amount = db_count
                todo.dustin_amount = du_count
                todo.is_complete = (current + db_count + du_count) >= todo.target_amount

            self.refresh_todo_list()
        except Exception as e:
            print(f"Error updating TODO progress: {e}")
    
    def update_progress_summary(self):
        """Update the overall progress summary."""
        summary = self.todo_manager.get_progress_summary()
        
        self.overall_progress.setValue(summary['overall_progress'])
        self.progress_label.setText(
            f"{summary['overall_progress']:.1f}% ({summary['completed']}/{summary['active']} completed)"
        )
    
    # ===== TODO DIALOGS =====
    
    def show_add_todo_dialog(self):
        """Show dialog to add a new TODO."""
        dialog = AddTodoDialog(self.item_db, self)
        
        if dialog.exec() == QDialog.Accepted:
            item_id = dialog.get_item_id()
            name = dialog.get_name()
            todo_type = dialog.get_type()
            target = dialog.get_target()
            
            if item_id and name and target > 0:
                result = self.todo_manager.add_todo(item_id, name, todo_type, target)
                if result:
                    self.refresh_todo_list()
                    # Refresh data to show current amount for new item
                    if self.save_path and self.save_data:
                        self.update_todo_progress()
                    self.status_bar.showMessage(f"Added TODO: {name}", 3000)
                else:
                    QMessageBox.warning(
                        self,
                        "Duplicate Item",
                        f"'{name}' (ID: {item_id}) is already in the TODO list.\n"
                        f"You cannot add the same item twice."
                    )
                    self.status_bar.showMessage(f"Duplicate: {name} already tracked", 3000)
    
    def show_edit_todo_dialog(self):
        """Show dialog to edit selected TODO."""
        selected = self.todo_table.selectedItems()
        if not selected:
            QMessageBox.information(
                self,
                "No Selection",
                "Please select a TODO item to edit."
            )
            return
        
        # Get the todo from the first selected item
        todo = None
        for item in selected:
            todo = item.data(Qt.UserRole)
            if todo:
                break
        
        if not todo:
            QMessageBox.information(
                self,
                "No Selection",
                "Please select a TODO item to edit."
            )
            return
        
        dialog = EditTodoDialog(todo, self.item_db, self)
        
        if dialog.exec() == QDialog.Accepted:
            name = dialog.get_name()
            target = dialog.get_target()
            is_tracked = dialog.get_tracked()
            
            self.todo_manager.update_todo(
                todo.id,
                name=name,
                target_amount=target,
                is_tracked=is_tracked
            )
            self.refresh_todo_list()
            self.status_bar.showMessage(f"Updated TODO: {name}", 3000)
    
    def delete_selected_todo(self):
        """Delete the selected TODO item."""
        selected = self.todo_table.selectedItems()
        if not selected:
            QMessageBox.information(
                self,
                "No Selection",
                "Please select a TODO item to delete."
            )
            return
        
        todo = None
        for item in selected:
            todo = item.data(Qt.UserRole)
            if todo:
                break
        
        if not todo:
            return
        
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete TODO '{todo.name}'?\n\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.todo_manager.remove_todo(todo.id)
            self.refresh_todo_list()
            self.status_bar.showMessage(f"Deleted TODO: {todo.name}", 3000)
    
    def on_todo_double_clicked(self, row: int, column: int):
        """Handle double-click on TODO item to edit it."""
        # Get the todo from the row
        item = self.todo_table.item(row, 0)
        if item:
            todo = item.data(Qt.UserRole)
            if todo:
                self.show_edit_todo_dialog_by_todo(todo)

    def show_edit_todo_dialog_by_todo(self, todo):
        """Show edit dialog for a specific todo."""
        dialog = EditTodoDialog(todo, self.item_db, self)
        
        if dialog.exec() == QDialog.Accepted:
            name = dialog.get_name()
            target = dialog.get_target()
            is_tracked = dialog.get_tracked()
            
            self.todo_manager.update_todo(
                todo.id,
                name=name,
                target_amount=target,
                is_tracked=is_tracked
            )
            self.refresh_todo_list()
            self.status_bar.showMessage(f"Updated TODO: {name}", 3000)

    def clear_completed_todos(self):
        """Remove all completed TODOs."""
        count = self.todo_manager.clear_completed()
        if count > 0:
            self.refresh_todo_list()
            self.status_bar.showMessage(f"Cleared {count} completed TODOs", 3000)
        else:
            QMessageBox.information(self, "No Completed", "No completed TODOs to clear.")
    
    def reset_all_progress(self):
        """Reset all progress to 0."""
        reply = QMessageBox.question(
            self,
            "Confirm Reset",
            "Reset all TODO progress to 0?\n\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.todo_manager.reset_all_progress()
            self.refresh_todo_list()
            self.status_bar.showMessage("Reset all progress", 3000)
    
    # ===== CURRENCY DISPLAY =====
    
    def update_currency_display(self):
        """Update the currency display cards."""
        while self.currency_layout.count():
            item = self.currency_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        currencies = [
            ("Death Metals", "dm", "Free + Paid Medals"),
            ("Kill Coins", "kc", "KC for shops"),
            ("Splithium", "spl", "SPL for upgrades"),
            ("Bloodnium", "bloodnium", "Blood currency"),
            ("RE Points", "recycle_points", "Recycling points"),
        ]
        
        icons = ["DM", "KC", "SPL", "Bloodnium", "RE"]
        
        for i, (name, key, desc) in enumerate(currencies):
            card = self.create_currency_card(icons[i], name, key, desc)
            self.currency_layout.addWidget(card)
        
        self.currency_layout.addStretch()
    
    def create_currency_card(self, icon: str, name: str, key: str, desc: str) -> QFrame:
        """Create a currency display card."""
        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setFrameShadow(QFrame.Sunken)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_PANEL};
                border: 1px solid #3a3a5c;
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        
        layout = QHBoxLayout(card)
        layout.setSpacing(15)
        
        info_layout = QVBoxLayout()
        
        name_label = QLabel(f"{icon} - {name}")
        name_label.setFont(QFont("", 12, QFont.Bold))
        
        desc_label = QLabel(desc)
        desc_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 10px;")
        
        info_layout.addWidget(name_label)
        info_layout.addWidget(desc_label)
        
        layout.addLayout(info_layout)
        layout.addStretch()
        
        amount = self.currency_totals.get(key, 0)
        amount_label = QLabel(f"{amount:,}")
        amount_label.setFont(QFont("", 16, QFont.Bold))
        
        if amount >= 1000000:
            color = "#ff5722"
        elif amount >= 10000:
            color = COLOR_WARNING
        else:
            color = COLOR_TEXT
        
        amount_label.setStyleSheet(f"color: {color};")
        amount_label.setMinimumWidth(100)
        amount_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        layout.addWidget(amount_label)
        
        return card
    
    # ===== STORAGE DISPLAY =====
    
    def update_storage_display(self):
        """Update storage summary display."""
        storage = self.storage_analysis
        
        self.total_slots_label.setText(f"{storage.get('total_slots', 0):,}")
        self.used_slots_label.setText(f"{storage.get('used_slots', 0):,}")
        self.free_slots_label.setText(f"{storage.get('free_slots', 0):,}")
        self.unique_items_label.setText(f"{len(storage.get('items', {})):,}")
        self.unique_mushrooms_label.setText(f"{len(storage.get('mushrooms', {})):,}")
        self.unique_beasts_label.setText(f"{len(storage.get('beasts', {})):,}")
        
        self.top_table.setRowCount(0)
        
        all_items = []
        
        for item_id, count in storage.get('items', {}).items():
            name = self.item_db.get_item_info(item_id)
            all_items.append(("Material", item_id, name['name'] if name else item_id, count))
        
        for msr_id, count in storage.get('mushrooms', {}).items():
            name = self.item_db.get_item_info(msr_id)
            all_items.append(("Mushroom", msr_id, name['name'] if name else msr_id, count))
        
        for bst_id, count in storage.get('beasts', {}).items():
            name = self.item_db.get_item_info(bst_id)
            all_items.append(("Beast", bst_id, name['name'] if name else bst_id, count))
        
        all_items.sort(key=lambda x: -x[3])
        top_items = all_items[:50]
        
        self.top_table.setRowCount(len(top_items))
        
        for row, (item_type, item_id, name, count) in enumerate(top_items):
            self.top_table.setItem(row, 0, QTableWidgetItem(item_type))
            self.top_table.setItem(row, 1, QTableWidgetItem(item_id))
            self.top_table.setItem(row, 2, QTableWidgetItem(name))
            self.top_table.setItem(row, 3, QTableWidgetItem(f"{count:,}"))
    
    # ===== ABOUT =====
    
    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About TODO Tracker",
            """<h2>Let-It-Die TODO Tracker</h2>
            <p>Version 1.0.0</p>
            <p>A read-only progress tracker for monitoring grinding goals in Let-It-Die.</p>
            <h3>Features:</h3>
            <ul>
                <li>Track materials, mushrooms, beasts, and currencies</li>
                <li>Set target amounts and monitor progress</li>
                <li>Auto-refresh when save file changes</li>
                <li>Save/load TODO lists</li>
            </ul>
            <h3>Important:</h3>
            <p>This application is <b>READ-ONLY</b> and will never modify your save files.
            It only reads data to track your progress towards grinding goals.</p>
            <p style="color: #a0a0a0;">Built with Python + PySide6</p>
            """
        )


# ===== ADD TODO DIALOG =====

class AddTodoDialog(QDialog):
    """Dialog for adding a new TODO item."""
    
    def __init__(self, item_db: ItemDatabase, parent=None):
        super().__init__(parent)
        self.item_db = item_db
        self.setWindowTitle("Add TODO")
        self.setMinimumWidth(400)
        
        self.setup_ui()
        self.populate_items()
    
    def setup_ui(self):
        """Setup dialog UI."""
        layout = QFormLayout(self)
        layout.setSpacing(10)
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Material", "Mushroom", "Beast", "Currency"])
        self.type_combo.currentTextChanged.connect(self.on_type_changed)
        layout.addRow("Type:", self.type_combo)
        
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search items...")
        self.search_box.textChanged.connect(self.on_search_changed)
        layout.addRow("Item:", self.search_box)
        
        self.items_list = QListWidget()
        self.items_list.setMinimumHeight(100)
        self.items_list.currentItemChanged.connect(self.on_item_selected)
        layout.addRow("Select Item:", self.items_list)
        
        self.custom_id_check = QCheckBox("Enter custom item ID")
        self.custom_id_check.toggled.connect(self.on_custom_toggled)
        layout.addRow(self.custom_id_check)
        
        self.custom_id_box = QLineEdit()
        self.custom_id_box.setPlaceholderText("Enter item ID (e.g., ITMT_COPPER_1)")
        self.custom_id_box.setEnabled(False)
        layout.addRow("Item ID:", self.custom_id_box)
        
        self.name_box = QLineEdit()
        self.name_box.setPlaceholderText("Display name")
        layout.addRow("Name:", self.name_box)
        
        self.target_spin = QSpinBox()
        self.target_spin.setMinimum(1)
        self.target_spin.setMaximum(999999999)
        self.target_spin.setValue(1000)
        layout.addRow("Target Amount:", self.target_spin)
        
        self.currency_prefix = QLabel("")
        layout.addRow(self.currency_prefix)
        
        btn_layout = QHBoxLayout()
        
        self.ok_btn = QPushButton("Add TODO")
        self.ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.ok_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addRow(btn_layout)
    
    def populate_items(self):
        """Populate the items list based on search or type selection."""
        self.items_list.clear()
        
        query = self.search_box.text().strip()
        selected_type_text = self.type_combo.currentText()
        
        # Case 1: Search box has text - search all items
        if query:
            results = self.item_db.search_items(query)
            
            # If search returns items of only one type, auto-select that type
            if results:
                types_found = set(r['type'] for r in results)
                if len(types_found) == 1:
                    # Auto-select the matching type
                    type_to_select = types_found.pop()
                    type_map_reverse = {
                        "material": "Material",
                        "mushroom": "Mushroom",
                        "beast": "Beast",
                        "currency": "Currency"
                    }
                    type_name = type_map_reverse.get(type_to_select, "Material")
                    if self.type_combo.currentText() != type_name:
                        self.type_combo.setCurrentText(type_name)
                        self.update_currency_prefix()
            
            # Filter by selected type if one is selected
            type_map = {
                "Material": TodoType.MATERIAL,
                "Mushroom": TodoType.MUSHROOM,
                "Beast": TodoType.BEAST,
                "Currency": TodoType.CURRENCY
            }
            current_type = type_map.get(selected_type_text)
            
            filtered = []
            if current_type:
                for r in results:
                    if r['type'] == current_type.value:
                        filtered.append(r)
                
                # If filtering removed all results, show unfiltered results
                if not filtered:
                    filtered = results[:50]
            else:
                filtered = results[:50]
            
            for r in filtered:
                item = QListWidgetItem(f"{r['id']} - {r['name']}")
                item.setData(Qt.UserRole, r)
                self.items_list.addItem(item)
        
        # Case 2: No search, but type is selected - show all items of that type
        elif selected_type_text and selected_type_text != "Type:":
            # Load all items of the selected type from database
            all_items = self.item_db.get_all_items_by_type(selected_type_text)
            for r in all_items:
                item = QListWidgetItem(f"{r['id']} - {r['name']}")
                item.setData(Qt.UserRole, r)
                self.items_list.addItem(item)
    
    def on_type_changed(self, text: str):
        """Handle type combo change."""
        self.populate_items()
        self.update_currency_prefix()
    
    def on_search_changed(self, text: str):
        """Handle search box changes."""
        self.populate_items()
    
    def on_item_selected(self, current, previous):
        """Handle item selection."""
        if current:
            data = current.data(Qt.UserRole)
            if data:
                self.name_box.setText(data['name'])
                self.custom_id_box.setText(data['id'])
                self.update_currency_prefix()
    
    def on_custom_toggled(self, checked: bool):
        """Handle custom ID toggle."""
        self.custom_id_box.setEnabled(checked)
        if checked:
            self.search_box.setEnabled(False)
            self.items_list.setEnabled(False)
            self.name_box.clear()
        else:
            self.search_box.setEnabled(True)
            self.items_list.setEnabled(True)
    
    def update_currency_prefix(self):
        """Update currency prefix for target amount."""
        if self.type_combo.currentText() == "Currency":
            self.currency_prefix.setText("(e.g., 5000 for 5000 DM)")
        else:
            self.currency_prefix.setText("")
    
    def get_item_id(self) -> str:
        """Get selected item ID."""
        if self.custom_id_check.isChecked():
            return self.custom_id_box.text().strip()
        
        selected = self.items_list.selectedItems()
        if selected:
            data = selected[0].data(Qt.UserRole)
            if data:
                return data['id']
        
        return ""
    
    def get_name(self) -> str:
        """Get display name."""
        name = self.name_box.text().strip()
        if not name:
            item_id = self.get_item_id()
            info = self.item_db.get_item_info(item_id)
            name = info['name'] if info else item_id
        return name
    
    def get_type(self) -> TodoType:
        """Get item type.
        
        Determines type from selected item if available, otherwise uses combo selection.
        """
        # Try to get type from selected item first
        selected = self.items_list.selectedItems()
        if selected:
            data = selected[0].data(Qt.UserRole)
            if data and 'type' in data:
                type_map = {
                    "material": TodoType.MATERIAL,
                    "mushroom": TodoType.MUSHROOM,
                    "beast": TodoType.BEAST,
                    "currency": TodoType.CURRENCY
                }
                return type_map.get(data['type'], TodoType.MATERIAL)
        
        # Fallback to combo selection
        type_map = {
            "Material": TodoType.MATERIAL,
            "Mushroom": TodoType.MUSHROOM,
            "Beast": TodoType.BEAST,
            "Currency": TodoType.CURRENCY
        }
        return type_map.get(self.type_combo.currentText(), TodoType.MATERIAL)
    
    def get_target(self) -> int:
        """Get target amount."""
        return self.target_spin.value()


# ===== EDIT TODO DIALOG =====

class EditTodoDialog(QDialog):
    """Dialog for editing a TODO item."""
    
    def __init__(self, todo: TodoItem, item_db: ItemDatabase, parent=None):
        super().__init__(parent)
        self.todo = todo
        self.item_db = item_db
        self.setWindowTitle("Edit TODO")
        self.setMinimumWidth(400)
        
        self.setup_ui()
        self.populate_fields()
    
    def setup_ui(self):
        """Setup dialog UI."""
        layout = QFormLayout(self)
        layout.setSpacing(10)
        
        self.name_box = QLineEdit()
        layout.addRow("Name:", self.name_box)
        
        self.target_spin = QSpinBox()
        self.target_spin.setMinimum(1)
        self.target_spin.setMaximum(999999999)
        layout.addRow("Target Amount:", self.target_spin)
        
        self.track_cb = QCheckBox("Track this TODO")
        self.track_cb.setChecked(True)
        layout.addRow(self.track_cb)
        
        self.progress_label = QLabel("")
        layout.addRow("Current Progress:", self.progress_label)
        
        btn_layout = QHBoxLayout()
        
        self.ok_btn = QPushButton("Save")
        self.ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.ok_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addRow(btn_layout)
    
    def populate_fields(self):
        """Populate fields from existing TODO."""
        self.name_box.setText(self.todo.name)
        self.target_spin.setValue(self.todo.target_amount)
        self.track_cb.setChecked(self.todo.is_tracked)
        
        progress = self.todo.progress_percentage()
        remaining = self.todo.remaining()
        self.progress_label.setText(
            f"{self.todo.current_amount:,} / {self.todo.target_amount:,} "
            f"({progress:.1f}%) - {remaining:,} remaining"
        )
    
    def get_name(self) -> str:
        """Get name."""
        return self.name_box.text().strip()
    
    def get_target(self) -> int:
        """Get target amount."""
        return self.target_spin.value()
    
    def get_tracked(self) -> bool:
        """Get tracked status."""
        return self.track_cb.isChecked()


# ===== MAIN =====

def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = TodoTrackerApp()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
