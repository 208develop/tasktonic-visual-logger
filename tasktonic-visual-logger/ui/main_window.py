import time
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QTabWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QAction

from TaskTonic.ttTonicStore import ttPysideWidget, ttPysideWindow
from ui.log_viewer import LogViewer
from ui.timeline_viewer import TimelineContainer
from ui.theme import Theme


class LoggerMainWindow(ttPysideWindow):
    def __init__(self, lc, **kwargs):
        self.lc = lc
        super().__init__(**kwargs)
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("TaskTonic Visual Logger")
        self.resize(1200, 800)
        self.setStyleSheet(f"background-color: {Theme.BG_MAIN}; color: {Theme.TEXT_MAIN};")

        # 1. Build the menu bar
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")

        # Create the exit action. TaskTonic will automatically route triggers to ttqt__exit_action__triggered
        self.exit_action = QAction("Exit", self)
        file_menu.addAction(self.exit_action)

        # 2. Setup the central workspace
        self.workspace = LogWorkspaceWidget(parent=self)
        self.setCentralWidget(self.workspace)

        self.show()

    def ttqt__exit_action__triggered(self):
        # Trigger the native close sequence (which fires closeEvent)
        self.close()
        self.finish()
        self.catalyst.finish()

    def ttse__on_start(self):
        self.lc.subscribe('newest_session_path', self.ttse__on_new_session_path)

        initial_path = self.lc.get('newest_session_path')
        if initial_path:
            # Simulate an update package to feed to our own callback
            dummy_update = [(None, initial_path, None, None)]
            self.ttse__on_new_session_path(dummy_update)

    def ttse__on_new_session_path(self, updates):
        for _, new_session_path, _, _ in updates:
            new_session = self.lc[new_session_path]
            new_session.set((
                ('ui/timeline/mode', 'waiting'),  # Initialized as waiting to prevent premature UI polling
                ('ui/timeline/cursor_ts', 0.0),
                ('ui/timeline/freeze_ts', 0.0),
                ('ui/timeline/zoom_sec', 30),
                ('ui/id', {}),
                ('ui/id_version', 0),
                ('ui/history', []),
            ))
            self.workspace.ttsc__create_new_session_widget(new_session)

class LogWorkspaceWidget(ttPysideWidget):
    def __init__(self, parent=None, **kwargs):
        super().__init__(parent=parent, **kwargs)
        self.views = []

    def setup_ui(self):
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(5, 5, 5, 5)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid {Theme.BG_PANEL}; background: {Theme.BG_MAIN}; }}
            QTabBar::tab {{ background: {Theme.BG_PANEL}; color: {Theme.TEXT_DIM}; padding: 8px 15px; 
                            border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; }}
            QTabBar::tab:selected {{ background: {Theme.BG_BLOCK}; color: {Theme.TEXT_MAIN}; 
                                     font-weight: bold; border-bottom: 2px solid #00FFFF; }}
        """)
        self.lay.addWidget(self.tabs)

    def _get_log_center(self):
        curr = getattr(self, 'base', None)
        while curr:
            if hasattr(curr, 'ttsc__start_new_session'):
                return curr
            curr = getattr(curr, 'base', None)
        return None

    def ttse__on_start(self):
        pass

    def ttsc__create_new_session_widget(self, new_session):
        SessionViewWidget(new_session, parent=self.tabs, name=None)

    def ttsc__register_view(self, view_widget):
        idx = self.tabs.addTab(view_widget, "Waiting...")
        self.tabs.setCurrentIndex(idx)

    def ttsc__unregister_view(self, view_widget):
        idx = self.tabs.indexOf(view_widget)
        if idx >= 0:
            self.tabs.removeTab(idx)


class SessionViewWidget(ttPysideWidget):
    def __init__(self, session_store, parent=None, **kwargs):
        self.session_store = session_store
        self._drag_pos = None

        super().__init__(parent=parent)

    def setup_ui(self):
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(2, 2, 2, 2)
        self.lay.setSpacing(2)

        self.setStyleSheet("background-color: #001E1E;")

        self.header_widget = QWidget()
        self.header_widget.setStyleSheet("background-color: #002b2b; border-radius: 4px;")
        self.header_lay = QHBoxLayout(self.header_widget)
        self.header_lay.setContentsMargins(5, 5, 5, 5)

        self.lbl_title = QLabel("Waiting for data...")
        self.lbl_title.setStyleSheet(
            "color: #00FFFF; font-family: Consolas; font-size: 14px; font-weight: bold; padding-left: 5px;"
        )

        self.btn_switch = QPushButton()
        self.btn_switch.setFixedSize(24, 24)
        self.btn_switch.setCursor(Qt.PointingHandCursor)
        self.btn_switch.setStyleSheet("background: transparent; border: none;")

        self.btn_close = QPushButton()
        self.btn_close.setFixedSize(24, 24)
        self.btn_close.setIcon(QIcon("ui/icons/close.svg"))
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setStyleSheet("background: transparent; border: none;")

        self.header_lay.addWidget(self.lbl_title)
        self.header_lay.addStretch()
        self.header_lay.addWidget(self.btn_switch)
        self.header_lay.addWidget(self.btn_close)

        self.lay.addWidget(self.header_widget)

        self.log_widget = LogViewer(self.session_store)
        self.timeline_widget = TimelineContainer(self.session_store)

        self.lay.addWidget(self.log_widget, 1)
        self.lay.addWidget(self.timeline_widget, 0)

    def ttse__on_start(self):

        self.session_store.subscribe('name', self.ttse__sync_title)
        self.session_store.subscribe('start@', self.ttse__sync_title)
        self.session_store.subscribe('status', self.ttse__on_status_changed1)
        self.ttse__sync_title()

        self.to_state('waiting')

    def ttse__sync_title(self, _=None):
        name = self.session_store.get('name', 'Unknown Session')
        start_ts = self.session_store.get('start@', 0)

        if start_ts > 0:
            time_str = time.strftime('%H:%M:%S', time.localtime(start_ts))
            title = f"[{time_str}] {name}"
        else:
            title = name

        self.lbl_title.setText(title)
        self.setWindowTitle(title)

        p_widget = self.parentWidget()
        while p_widget:
            if hasattr(p_widget, 'indexOf') and hasattr(p_widget, 'setTabText'):
                idx = p_widget.indexOf(self)
                if idx >= 0:
                    p_widget.setTabText(idx, title)
                break
            p_widget = p_widget.parentWidget()

    def ttse__on_status_changed1(self, _=None):
        self.log('Connected and not waiting')

    def ttqt__btn_close__clicked(self):
        self.session_store['status'] = 'closing'
        self.finish()

    def ttse_waiting__on_enter(self):
        pass

    def ttse_waiting__on_status_changed1(self, _=None):
        status = self.session_store.get('status')
        if status == 'connected':
            self.to_state('tab')

    def ttse_tab__on_enter(self):
        self.btn_switch.setIcon(QIcon("ui/icons/win.svg"))
        self.setWindowFlags(Qt.Widget)
        if hasattr(self.base, 'ttsc__register_view'):
            self.base.ttsc__register_view(self)
        self.show()

    def ttqt_tab__btn_switch__clicked(self):
            self.to_state('win')

    def ttse_tab__on_exit(self):
        if hasattr(self.base, 'ttsc__unregister_view'):
            self.base.ttsc__unregister_view(self)

    def ttse_win__on_enter(self):
        self.btn_switch.setIcon(QIcon("ui/icons/tab.svg"))
        self.setParent(None)
        self.setWindowFlags(Qt.Window)
        self.resize(800, 600)
        self.show()

    def ttqt_win__btn_switch__clicked(self):
        self.to_state('tab')

    def closeEvent(self, event):
        self.session_store['status'] = 'closing'
        event.ignore()