import sys
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTabWidget, QLabel
from TaskTonic import ttFormula, ttLog
from TaskTonic.ttTonicStore import ttPyside6Ui, ttPysideWindow, ttPysideWidget


class ShowWidget(ttPysideWidget):
    """
    A dynamic widget that utilizes a state machine to act as an embedded tab or a standalone window.
    """

    def __init__(self, mode='tab', **kwargs):
        self.starting_mode = mode
        self.widget_id = id(self)

        super().__init__(**kwargs)

    def setup_ui(self):
        self.setWindowTitle(f"Floating Window {self.widget_id}")
        self.resize(300, 150)

        layout = QVBoxLayout(self)
        self.lbl_info = QLabel()
        layout.addWidget(self.lbl_info)

        self.btn_switch = QPushButton("Switch Mode")
        layout.addWidget(self.btn_switch)

    def ttse__on_start(self):
        if self.starting_mode == 'tab':
            self.to_state('tab')
        else:
            self.to_state('win')

    def ttse_tab__on_enter(self):
        # Reliably using self.base as guaranteed by the TaskTonic framework
        self.base.ttsc__add_to_tabs(self)
        self.lbl_info.setText(f"Widget ID: {self.widget_id}\nCurrent mode: tab")

    def ttqt_tab__btn_switch__clicked(self):
        self.to_state('win')

    def ttse_tab__on_exit(self):
        self.base.ttsc__remove_from_tabs(self)

    def ttse_win__on_enter(self):
        self.setParent(None)
        self.show()
        self.lbl_info.setText(f"Widget ID: {self.widget_id}\nCurrent mode: win")

    def ttqt_win__btn_switch__clicked(self):
        self.to_state('tab')

    def ttse_win__on_exit(self):
        pass


class DemoMainWindow(ttPysideWindow):
    """
    The main distributor window containing the workspace tabs and control buttons.
    """

    def __init__(self, **kwargs):
        # Declare variables before calling super()
        self.tabs = None
        self.btn_add_win = None
        self.btn_add_tab = None

        super().__init__(**kwargs)

        # Explicitly calling setup_ui as a workaround for the current ttPysideWindow bug
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("TaskTonic Window Manager Demo")
        self.resize(600, 400)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        btn_layout = QHBoxLayout()
        self.btn_add_tab = QPushButton("+ show tab")
        self.btn_add_win = QPushButton("+ show win")

        btn_layout.addWidget(self.btn_add_tab)
        btn_layout.addWidget(self.btn_add_win)
        layout.addLayout(btn_layout)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

    def ttse__on_start(self):
        self.show()

    def ttqt__btn_add_tab__clicked(self):
        ShowWidget(mode='tab')

    def ttqt__btn_add_win__clicked(self):
        ShowWidget(mode='win')

    def ttsc__add_to_tabs(self, widget):
        idx = self.tabs.addTab(widget, f"Tab {widget.widget_id}")
        self.tabs.setCurrentIndex(idx)

    def ttsc__remove_from_tabs(self, widget):
        idx = self.tabs.indexOf(widget)

        if idx >= 0:
            self.tabs.removeTab(idx)


class DemoApp(ttFormula):
    def creating_formula(self):
        return (
            ('tasktonic/project/name', 'UI Window Demo'),
            ('tasktonic/log/to', 'screen'),
            ('tasktonic/log/default', ttLog.FULL),
        )

    def creating_main_catalyst(self):
        ttPyside6Ui(name='tt_main_catalyst')

    def creating_starting_tonics(self):
        DemoMainWindow()


if __name__ == '__main__':
    DemoApp()