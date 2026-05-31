from PySide6.QtWidgets import QVBoxLayout, QSplitter, QWidget, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction

from TaskTonic.ttTonicStore import ttPysideWindow
from log_viewer import ScreenLoggerWidget
from timeline_viewer import TimelineContainer


class LoggerMainWindow(ttPysideWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("TaskTonic Studio - IP Logger")
        self.resize(1100, 800)
        self.setStyleSheet("QMainWindow { background-color: #000; } QSplitter::handle { background: #444; }")

        menubar = self.menuBar()
        menubar.setStyleSheet("background: #1e1e1e; color: white;")
        file_menu = menubar.addMenu("File")

        self.exit_action = QAction("Exit", self)
        file_menu.addAction(self.exit_action)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(2, 2, 2, 2)

        splitter = QSplitter(Qt.Vertical)
        top_splitter = QSplitter(Qt.Horizontal)

        # 1. Jouw log list widget
        self.logger_panel = ScreenLoggerWidget(parent=self)

        # 2. Jouw glass label
        glass_label = QLabel("Tonic Glass Visualizer")
        glass_label.setAlignment(Qt.AlignCenter)
        glass_label.setStyleSheet("background: #050505; color: #00aaff; border: 1px solid #333; border-radius: 4px;")

        # 3. DE ECHTE TIJDLIJN WIDGET (vervangt timeline_label)
        self.timeline_view = TimelineContainer(parent=self)

        # Indeling top: Loglijst links, glass_label rechts
        top_splitter.addWidget(self.logger_panel)
        top_splitter.addWidget(glass_label)
        top_splitter.setStretchFactor(0, 4)

        # Indeling main: Top gedeelte boven, Tijdlijn onder
        splitter.addWidget(top_splitter)
        splitter.addWidget(self.timeline_view)
        splitter.setStretchFactor(0, 5)

        layout.addWidget(splitter)

    def ttse__on_start(self):
        self.show()

    def ttqt__exit_action__triggered(self):
        self.catalyst.finish()