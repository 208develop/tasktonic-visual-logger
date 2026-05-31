from TaskTonic import *
import random


class Dummy(ttTonic):
    def __init__(self):
        super().__init__()
        self.log(lane_color='yellow')

    def ttse__on_start(self):
        ttTimerSingleShot(seconds=.2, name='tm_delay')

    def ttse__on_tm_delay(self, _):
        self.finish()

class LoggerApp(ttFormula):
    def creating_formula(self):
        return (
            ('tasktonic/project/name', 'Dummy log generator'),
            ('tasktonic/log/to', 'ip'),
            ('tasktonic/log/to/target', 'localhost:1767'),
            ('tasktonic/log/default', ttLog.FULL),
        )

    def creating_starting_tonics(self):
        Dummy()


if __name__ == '__main__':
    app = LoggerApp()

    print(app.ledger.sdump())
    print('============ APP FINISHED ===========')