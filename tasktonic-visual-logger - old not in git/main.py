from TaskTonic import ttCatalyst, ttTonic, ttFormula, ttLog, ttTimerRepeat
from TaskTonic.ttTonicStore import ttPyside6Ui

from ui_logger import UiLogger
from log_center import LogCenter
from ui.main_window import LoggerMainWindow

import random

class Dummy(ttCatalyst):
    def __init__(self):
        super().__init__()

    def ttse__on_start(self):
        DummyLogGenerator()
        DummyStateGenerator()
        DummyRandomGenerator()

class DummyLogGenerator(ttTonic):
    """Generates a high-speed dummy log stream to test the LogCenter."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.msg_count = 0

    def ttse__on_start(self):
        self.tm_burst = ttTimerRepeat(seconds=2.0, name="tm_burst")
        self.to_state('running')

    def ttse_running__on_tm_burst(self, tinfo):
        b = 15
        self.log(f"Start burst of  {b} sparkles")
        self.ttsc__burst(b)

    def ttsc__burst(self, cnt):
        self.msg_count += 1
        self.log(f"Generating log {self.msg_count}...")
        cnt -= 1
        if cnt > 0:
            self.ttsc__burst(cnt)


class DummyStateGenerator(ttTonic):
    def ttse__on_start(self):
        ttTimerRepeat(seconds=1.023, name="tm_next")
        ttTimerRepeat(seconds=0.333, name="tm_make_noice")
        self.to_state('silent')

    def ttse_silent__on_tm_next(self, _):
        self.to_state('be_quiet')
    def ttse_silent__on_tm_make_noice(self, _):
        pass

    def ttse_be_quiet__on_tm_next(self, _):
        self.to_state('noise')
    def ttse_be_quiet__on_tm_make_noice(self, _):
        self.log(f"Hé, pssst {random.randint(3, 8) * '.'}")

    def ttse_noise__on_tm_next(self, _):
        self.to_state('silent')
    def ttse_noise__on_tm_make_noice(self, _):
        self.log(f"GET LOUD{random.randint(8,20)*'!'}")

class DummyRandomGenerator(ttTonic):
    def __init__(self, name=None, log_mode=None, catalyst=None):
        super().__init__(name, ttLog.FULL, catalyst)
        self.tm_adjust = None
        self.tm_event = None

    def ttse__on_start(self):
        self.tm_adjust = ttTimerRepeat(seconds=3.0, name="tm_adjust")
        self.tm_event = ttTimerRepeat(seconds=1.45, name="tm_event")

    def ttse__on_tm_adjust(self, _):
        if __name__ == '__main__':
            new_adjust = random.uniform(1.0, 5.0)
            new_event = random.uniform(0.431, 1.999)
            self.log(f"New adjust timer set to {new_adjust}sec/ event timer to {new_event}sec")
            self.tm_adjust.change_timer(seconds=new_adjust)
            self.tm_event.change_timer(seconds=new_event)

    def ttse__on_tm_event(self, _):
        pass



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
        Dummy()


if __name__ == '__main__':
    LoggerApp()
