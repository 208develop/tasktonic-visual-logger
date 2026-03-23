import random
from TaskTonic import ttTonic, ttFormula, ttLog, ttTimerRepeat
from TaskTonic.ttTonicStore import ttPyside6Ui

from ui_logger import UiLogger
from log_center import LogCenter
from main_window import LoggerMainWindow


class DummyLogGenerator(ttTonic):
    """Generates a high-speed dummy log stream to test the LogCenter."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.msg_count = 0

    def ttse__on_start(self):
        self.tm_burst = ttTimerRepeat(seconds=2.0, name="tm_burst")
        self.to_state('running')

    def ttse_running__on_tm_burst(self, tinfo):
        self.msg_count += 1
        self.log(f"Generating log {self.msg_count}...")
        


class LoggerApp(ttFormula):
    def creating_formula(self):
        return (
            ('tasktonic/log/service#', 'my_ui'),
            ('tasktonic/log/service./service', UiLogger),
            ('tasktonic/log/service./arguments', {}),

            ('tasktonic/project/name', 'TaskTonic Visual Logger'),
            ('tasktonic/log/to', 'my_ui'), 
            ('tasktonic/log/default', ttLog.QUIET),
        )
        
    def creating_main_catalyst(self):
        ttPyside6Ui(name='tt_main_catalyst')
        
    def creating_starting_tonics(self):
        LogCenter()
        LoggerMainWindow()
        DummyLogGenerator()


if __name__ == '__main__':
    LoggerApp()
