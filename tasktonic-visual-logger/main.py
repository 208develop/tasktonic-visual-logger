from TaskTonic import ttCatalyst, ttTonic, ttFormula, ttLog, ttTimerSingleShot
from TaskTonic.ttTonicStore import ttPyside6Ui

from ui_logger import UiLogger

from log_center import LogCenter
from ui.main_window import LoggerMainWindow

class LaunchDUT(ttTonic):

    def __init__(self, dut):
        super().__init__()
        self.dut = dut if isinstance(dut, list) else [dut]

    def ttse__on_start(self):
        ttTimerSingleShot(1, name='tm_start_dummy')

    def ttse__on_tm_start_dummy(self, _=None):
        import sys, subprocess
        try:
            run_dut = [sys.executable] + self.dut
            # Check if we are on Windows to use the CREATE_NEW_CONSOLE flag
            if sys.platform == "win32":
                subprocess.Popen(run_dut, creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                # Mac/Linux fallback
                subprocess.Popen(run_dut)

            self.log(f"Started DUT '{' '.join(self.dut)}' in the background.")
        except Exception as e:
            self.log(f"Failed to launch DUT '{' '.join(self.dut)}': {e}")

        self.finish()



class LoggerApp(ttFormula):

    def __init__(self, app_args):
        self.app_args = app_args
        super().__init__()

    def creating_formula(self):
        formula = (
            ('tasktonic/project/name', 'TaskTonic Visual Logger'),
            ('tasktonic/log/default', ttLog.FULL),
        )

        log_to = self.app_args.debug
        if log_to == 'off':
            formula += ('tasktonic/log/to', 'off'),
        elif log_to == 'screen':
            formula += ('tasktonic/log/to', 'screen'),
        else:
            formula += ('tasktonic/log/to', 'ip'),
            formula += ('tasktonic/log/to/target', log_to),

        for key, val in vars(self.app_args).items():
            formula += (f'app_data/startup_args/{key}', val),

        return formula


    def creating_main_catalyst(self):
        ttPyside6Ui(name='tt_main_catalyst')

    def creating_starting_tonics(self):
        lc = LogCenter()
        LoggerMainWindow(lc, name=None)

        dut = self.ledger.formula.get('app_data/startup_args/dut', [])
        if dut:
            LaunchDUT(dut)




if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="TaskTonic Visual Logger")

    parser.add_argument(
        "-p", "--port",
        type=int,
        default=1767,
        help="Debug port for server. Default: 1767, the year Joseph Priestley created the first sparkle"
    )

    parser.add_argument(
        "--debug",
        type=str,
        default='off',
        help="Debugging the logger. off, screen, <target>"
    )

    parser.add_argument(
        "-d", "--dut",
        default=[],
        nargs=argparse.REMAINDER,
        help="Script to run followed by its arguments. (NOTE: use --dut always as last parameter!!)"
    )

    args = parser.parse_args()
    LoggerApp(args)
