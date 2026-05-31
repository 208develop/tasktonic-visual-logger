# theme.py
from PySide6.QtGui import QColor, QFont


class Theme:
    # --- Achtergronden & Panelen ---
    BG_MAIN = "#000000"
    BG_PANEL = "#121212"
    BG_BLOCK = "#2b2b2b"
    BG_INPUT = "#1e1e1e"
    BG_TIMELINE = "#0a0a0a"

    # --- Lijnen & Randen ---
    BORDER_DIM = "#333333"
    BORDER_HIGHLIGHT = "#888888"
    LANE_INACTIVE = "#444444"

    # --- Tekst ---
    TEXT_MAIN = "#ffffff"
    TEXT_DIM = "#aaaaaa"

    # --- Status Symbolen (+, -, C, E, S) ---
    STAT_CREATED = "#4CAF50"
    STAT_FINISHED = "#F44336"
    STAT_CALL = "#2196F3"
    STAT_EVENT = "#FF9800"
    STAT_STATE = "#9C27B0"

    # --- Swimlane Layout ---
    LANE_START_X = 25
    LANE_SPACING = 30
    GAP_HEIGHT = 16
    BLOCK_MARGIN = 5

    # --- ID Kleuren Palet ---
    ID_COLORS = [
        ("#ffffff", "White (Default)"),
        ("#4CAF50", "Green"),
        ("#2196F3", "Blue"),
        ("#FF9800", "Orange"),
        ("#E91E63", "Pink"),
        ("#9C27B0", "Purple"),
        ("#00BCD4", "Cyan"),
        ("#FFEB3B", "Yellow")
    ]

    @classmethod
    def get_color(cls, index):
        """Helper to safely get a QColor from the palette index"""
        hex_code = cls.ID_COLORS[index % len(cls.ID_COLORS)][0]
        return QColor(hex_code)
