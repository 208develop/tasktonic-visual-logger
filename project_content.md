# Introduction
This file contains all source code and documentation for the project.
       All markdown documents are add, all other files are wrapped in formatting blocks.
    

---

# Project Structure

```text
tasktonic-visual-logger/
    README.md
    collect_for_nlm.py
    project_content.md
    .devcontainer/
        devcontainer.json
    tasktonic-visual-logger/
        log_center.py
        main.py
        ttUiLogger.py
        ui_logger.py
        __init__.py
        log_session.py
        main_dummy_gen.py
        network_handlers.py
        ui/
            log_viewer.py
            main_window.py
            __init__.py
            timeline_viewer.py
            theme.py
            demo_show_widget.py
            icons/
        testing/
            test_log_center.py
    tasktonic-visual-logger - old not in git/  # <-- old code after first development run with working visualisation code
        log_center.py
        main.py
        ttUiLogger.py
        ui_logger.py
        __init__.py
        ui/
            log_viewer.py
            main_window.py
            __init__.py
            timeline_viewer.py
            theme.py
            icons/
        testing/
            test_log_center.py
```

---

# File Contents

## `File: README.md`
# tasktonic-visual-logger
Visual logger for testing TaskTonic applications. View the concurrency.
## `File: .devcontainer\devcontainer.json`
```json
{
    "name": "PySide6 Virtual Desktop",
    "build": {
        "dockerfile": "Dockerfile"
    },
    "features": {
        "ghcr.io/devcontainers/features/desktop-lite:1": {
            "password": "admin"
        }
    },
    "postCreateCommand": "bash .devcontainer/setup.sh",
    "customizations": {
        "vscode": {
            "extensions": [
                "ms-python.python"
            ]
        }
    }
}

```

## `File: tasktonic-visual-logger\log_center.py`
```python
from TaskTonic import ttTonic, ttCatalyst
from TaskTonic.internals import Store, Item

from log_session import LogSession

# -- Patch to add subscribe tot the Item class------------
def _patch_item_subscribe(self, subpath: str, callback, ignore_source: str = None, recursive: bool = True,
                          exclude: list = None):
    target = f"{self._path}/{subpath}".strip("/") if subpath else self._path
    self._store.subscribe(target, callback, ignore_source, recursive, exclude)

Item.subscribe = _patch_item_subscribe
# ---------------------------------------------------------

class LogCenter(ttCatalyst, Store):
    _tt_is_service = "log_center"

    def __init__(self,*args, **kwargs):
        ttCatalyst.__init__(self, *args, **kwargs)
        Store.__init__(self)
        self._sessions = self.at('sessions')

        # init store
        self.set((
            ('newest_session_path', ''),
        ), notify=False)

    def _ttss__on_start(self):
        self.ttsc__start_new_session()

    def ttsc__start_new_session(self):
        store_session = self._sessions.append()
        store_session['status'] = 'new'
        store_session.v = LogSession(store_session, name=store_session.path)
        self['newest_session_path'] = store_session.path

        self.log(store_session.dumps())

    def ttse__on_session_connected(self):
        self.ttsc__start_new_session()

    def ttsc__remove_session(self, session):
        if isinstance(session, str):
            session = self._sessions[session]
        elif not isinstance(session, Item):
            raise TypeError('session must be str or Item')

        session.v.finish()
        session['status'] = 'deleted'
        session.list_root.pop()





```

## `File: tasktonic-visual-logger\main.py`
```python
from TaskTonic import ttCatalyst, ttTonic, ttFormula, ttLog, ttTimerRepeat
from TaskTonic.ttTonicStore import ttPyside6Ui

from ui_logger import UiLogger

from log_center import LogCenter
from ui.main_window import LoggerMainWindow


class LoggerApp(ttFormula):
    def creating_formula(self):
        return (
            ('tasktonic/log/service#', 'my_ui'),
            ('tasktonic/log/service./service', UiLogger),
            ('tasktonic/log/service./arguments', {}),

            ('tasktonic/project/name', 'TaskTonic Visual Logger'),
            ('tasktonic/log/to', 'screen'),
            ('tasktonic/log/default', ttLog.FULL),
        )

    def creating_main_catalyst(self):
        ttPyside6Ui(name='tt_main_catalyst')

    def creating_starting_tonics(self):
        lc = LogCenter()
        LoggerMainWindow(lc)


if __name__ == '__main__':
    # import sys, subprocess
    #
    # try:
    #     # Check if we are on Windows to use the CREATE_NEW_CONSOLE flag
    #     if sys.platform == "win32":
    #         subprocess.Popen([sys.executable, "main_dummy_gen.py"], creationflags=subprocess.CREATE_NEW_CONSOLE)
    #     else:
    #         # Mac/Linux fallback
    #         subprocess.Popen([sys.executable, "main_dummy_gen.py"])
    #
    #     print("Started dummy generator in the background.")
    # except Exception as e:
    #     print(f"Failed to launch dummy generator: {e}")

    LoggerApp()

```

## `File: tasktonic-visual-logger\ttUiLogger.py`
```python
from .. import ttTimerRepeat
from ..ttLogger import ttLogService
import time

class ttUiLogService(ttLogService):

    def __init__(self, name=None):
        super().__init__(name)
        self.log_records = []
        prj = self.ledger.formula.at('tasktonic/project')
        ts = prj['started@'].v
        lt = time.localtime(ts)
        l_time_start = f'{time.strftime("%H%M%S", lt)}.{int((ts - int(ts)) * 1000):03d}'

        print(f"[{l_time_start}] TaskTonic log for {prj['name'].v}, started at {time.strftime('%H:%M:%S', lt)}")
        print(41 * '-=')
    def _tt_init_service_base(self, base, *args, **kwargs):
        self.log(close_log=True)

    def put_log(self, log):
        self.ttsc__add_log(log)

    def ttse__on_start(self):
        pass

    def ttse__on_finished(self):
        print(41*'-=')
        print('Logging finished')
        print(self.ledger.sdump())

    def ttsc__add_log(self, log):
        """
        Formats and prints the collected log entry for an event, then resets it.
        """
        l_id = log.get('id', -1)
        if l_id < 0:
            raise RuntimeError(f'Error in log entry {log}')

        if log.get('sys',{}).get('created', False):

            while len(self.log_records) <= l_id:
                self.log_records.append(None)
            self.log_records[l_id] = log.copy()

        sparkle_name = log.get('sparkle', '')
        sparkle_state_idx = log.get('state', -1)

        if sparkle_name == '_ttinternal_state_change_to':
            sparkle_name = f" TO STATE [{self.log_records[l_id]['sys']['states'][log['sys']['new_state']]}]"

        ts = log['start@']
        lt = time.localtime(ts)
        l_time_start = f'{time.strftime("%H%M%S", lt)}.{int((ts - int(ts)) * 1000):03d}'

        header = f"{self.log_records[l_id]['sys']['name']}"
        if sparkle_state_idx >= 0:
            header += f"[{self.log_records[l_id]['sys']['states'][sparkle_state_idx]}]"
        header += f".{sparkle_name}"

        dont_print_flags = ['id', 'start@', 'log', 'sparkle', 'state', 'sparkles', 'states', 'duration']
        flags_to_print = {k: v for k, v in log.items() if k not in dont_print_flags}

        du = log.get('duration',0.0)
        l_du = '' if du <= .15 else f'DURATION: {du:1.3f} sec !!! '

        print(f"[{l_time_start}] {l_id:02d} - {header:.<65} {l_du}{flags_to_print}")
        if l_states := log.get('states'):
            print(f"{16 * ' '}== STATES: |", end='')
            for state in l_states: print(f" {state} |", end='')
            print()
        if l_sparkles := log.get('sparkles'):
            print(f"{16 * ' '}== SPARKLES: |", end='')
            for sparkle in l_sparkles:
                if not sparkle.startswith('_ttss'): print(f" {sparkle} |", end='')
            print()

        if log.get('log'):
            for line in log['log']:
                line = str(line).replace('\n', f"\n{18*' '}")
                print(f"{16 * ' '}- {line}")
```

## `File: tasktonic-visual-logger\ui_logger.py`
```python
import time
from TaskTonic.ttLogger import ttLogService
from log_center import LogCenter

class UiLogger(ttLogService):
    """
    Intercepts the real TaskTonic log stream, formats the data, 
    and forwards it to the visual LogCenter instead of the terminal.
    """
    
    def __init__(self, name=None):
        super().__init__(name)
        self.log_records = []
        prj = self.ledger.formula.at('tasktonic/project')
        ts = prj['started@'].v
        lt = time.localtime(ts)
        self.l_time_start = f'{time.strftime("%H%M%S", lt)}.{int((ts - int(ts)) * 1000):03d}'

        print(f"[{self.l_time_start}] Visual UiLogger engaged for {prj['name'].v}")
        print(41 * '-=')

        startup = {
            'start_new_session': True,
            'project': prj['name'].v,
            'start@': prj['started@'].v,
            'connection': "<ip>:<port>",
            'logger_version': 0,
        }

        print(startup)

        self.ttsc__add_log(startup)

    def _tt_init_service_base(self, base, *args, **kwargs):
        self.log(close_log=True)

    def put_log(self, log):
        self.ttsc__add_log(log)

    def ttse__on_start(self):
        self.log_center = LogCenter()

    def ttse__on_finished(self):
        print(41 * '-=')
        print('Visual Logging finished')
        print(self.ledger.sdump())

    def ttsc__add_log(self, log):
        print(log)

        l_id = log.get('id', -1)
        if l_id < 0:
            return

        # 1. Maintain metadata cache for tonic names and states
        if log.get('sys', {}).get('created', False):
            while len(self.log_records) <= l_id:
                self.log_records.append(None)
            self.log_records[l_id] = log.copy()  # Hier wel een copy voor in de cache!

        meta = self.log_records[l_id] if l_id < len(self.log_records) and self.log_records[l_id] else None
        if not meta:
            meta = {'sys': {'name': f'Unknown_{l_id}', 'states': []}}

        sparkle_name = log.get('sparkle', '')
        sparkle_state_idx = log.get('state', -1)

        state_list = meta['sys'].get('states', [])
        state_name = state_list[sparkle_state_idx] if state_list and sparkle_state_idx >= 0 else 'idle'

        if sparkle_name == '_ttinternal_state_change_to':
            new_state_idx = log.get('sys', {}).get('new_state', -1)
            if new_state_idx >= 0 and state_list:
                sparkle_name = f"TO STATE [{state_list[new_state_idx]}]"

        # 2. Format extra information to display in the UI body
        extra_log_lines = list(log.get('log', []))

        dont_print = ['id', 'start@', 'log', 'sparkle', 'state', 'sparkles', 'states', 'duration', 'sys', 'source',
                      'catalyst']
        flags_to_print = {k: v for k, v in log.items() if k not in dont_print}
        if flags_to_print:
            extra_log_lines.append(f"Flags: {flags_to_print}")

        du = log.get('duration', 0.0)
        if du > 0.15:
            extra_log_lines.append(f"DURATION: {du:1.3f} sec !!!")

        if l_states := log.get('states'):
            extra_log_lines.append(f"STATES: {l_states}")

        if l_sparkles := log.get('sparkles'):
            filtered_sparkles = [s for s in l_sparkles if not s.startswith('_ttss')]
            if filtered_sparkles:
                extra_log_lines.append(f"SPARKLES: {filtered_sparkles}")

        # 3. DE ENRICHED NAMESPACE
        # We voegen onze berekende UI-data netjes toe in een eigen "mapje"
        log['enriched'] = {
            'display_sparkle': sparkle_name,
            'state_name': state_name,
            'ui_log_lines': extra_log_lines,
            'finishing': '_ttss__remove_tonic_from_catalyst' in sparkle_name,
            'tonic_name': meta['sys']['name'],
            'system_sparkle': sparkle_name.startswith('ttss') or sparkle_name.startswith('_ttss')
        }

        # 4. Inject into the visual LogCenter pipeline
        if hasattr(self, 'log_center'):
            self.log_center.ttse__new_log(log)

```

## `File: tasktonic-visual-logger\__init__.py`
```python
from .log_center import LogCenter

```

## `File: tasktonic-visual-logger\log_session.py`
```python
from TaskTonic import ttTonic
from network_handlers import DictSocketHandler


class LogSession(ttTonic):

    def __init__(self, store, **kwargs):
        super().__init__(**kwargs)
        self.log_records = []
        self._store = store
        self._net = None

    def ttse__on_start(self):
        # Initialize the baseline arrays and dictionaries for this session
        self._store['logs'] = []
        self._logs = self._store.at('logs').v
        # Setup the UI configuration specifically for this session's timeline
        ui_store = self._store.at('ui/timeline')
        ui_store['mode'] = 'tailing'
        ui_store['cursor_ts'] = 0.0
        ui_store['freeze_ts'] = 0.0
        ui_store['zoom_sec'] = 30
        self._net = DictSocketHandler(as_server=True, host='localhost', port=9999)
        self.log("New LogSession initialized and waiting for log connection.")

    def ttse__on_socket_connected(self, addr):
        self._store['session address'] = addr
        if hasattr(self.base, 'ttse__on_session_connected'):
            self.base.ttse__on_session_connected()
        self.log(f"Connected to: {addr}")

    def ttse__on_socket_status(self, status):
        self._store['status'] = status
        self.log(f"Status: {status}")

    def ttse__on_socket_data(self, log):
        self.log(f'{log}')

        l_id = log.get('id', -1)
        if l_id < 0:
            if  log.get('start_new_session', False):
                self._store.set((
                    ('name', log['project']),
                    ('start@', log['start@']),
                    ('logger_version', log['logger_version']),
                ))
            return

        # 1. Maintain metadata cache for tonic names and states
        if log.get('sys', {}).get('created', False):
            while len(self.log_records) <= l_id:
                self.log_records.append(None)
            self.log_records[l_id] = log.copy()

        meta = self.log_records[l_id] if l_id < len(self.log_records) and self.log_records[l_id] else None
        if not meta:
            meta = {'sys': {'name': f'Unknown_{l_id}', 'states': []}}

        sparkle_name = log.get('sparkle', '')
        sparkle_state_idx = log.get('state', -1)
        state_list = meta['sys'].get('states', [])

        state_name = state_list[sparkle_state_idx] if state_list and sparkle_state_idx >= 0 else 'idle'

        if sparkle_name == '_ttinternal_state_change_to':
            new_state_idx = log.get('sys', {}).get('new_state', -1)
            if new_state_idx >= 0 and state_list:
                sparkle_name = f"TO STATE [{state_list[new_state_idx]}]"

        # 2. Format extra information to display in the UI body
        extra_log_lines = list(log.get('log', []))
        dont_print = ['id', 'start@', 'log', 'sparkle', 'state', 'sparkles', 'states', 'duration', 'sys', 'source',
                      'catalyst']

        flags_to_print = {k: v for k, v in log.items() if k not in dont_print}
        if flags_to_print:
            extra_log_lines.append(f"Flags: {flags_to_print}")

        if log.get('duration', 0.0) > 0.15:
            extra_log_lines.append(f"DURATION: {log.get('duration'):1.3f} sec !!!")

        l_states = log.get('states')
        if l_states:
            extra_log_lines.append(f"STATES: {l_states}")

        l_sparkles = log.get('sparkles')
        if l_sparkles:
            filtered_sparkles = [s for s in l_sparkles if not s.startswith('_ttss')]
            if filtered_sparkles:
                extra_log_lines.append(f"SPARKLES: {filtered_sparkles}")

        # 3. Add the ENRICHED NAMESPACE for the UI
        log['enriched'] = {
            'display_sparkle': sparkle_name,
            'state_name': state_name,
            'ui_log_lines': extra_log_lines,
            'finishing': '_ttss__remove_tonic_from_catalyst' in sparkle_name,
            'tonic_name': meta['sys']['name'],
            'system_sparkle': sparkle_name.startswith('ttss') or sparkle_name.startswith('_ttss')
        }

        self._logs.append(log)


    def ttsc__on_disconnect(self, payload):
        # Update the status to disconnected
        self._store['status'] = 'disconnected'

        # Freeze the UI by setting the timeline mode to history
        ui_store = self._store.at('ui/timeline')
        ui_store['mode'] = 'history'

        self.log("LogSession IP connection lost. UI switched to history mode.")


    class LogSessionLedger:
        def __init__(self):
            self.session_name = "Unknown Session"
            self.entities = {}

        def process_and_enrich(self, log_data):
            # 1. Extract session name from the first log block
            if "start_new_session" in log_data:
                if "project" in log_data:
                    self.session_name = log_data["project"]

            log_id = log_data.get("id")
            if log_id is None:
                return log_data

            # 2. Build and update the session ledger
            if "sys" in log_data:
                sys_data = log_data["sys"]

                if sys_data.get("created"):
                    self.entities[log_id] = {
                        "name": sys_data.get("name", f"Unknown_{log_id}"),
                        "type": sys_data.get("type", "Unknown"),
                        "states": sys_data.get("states", []),
                        "sparkles": sys_data.get("sparkles", []),
                        "current_state": -1,
                        "state_history": []
                    }

                if "new_state" in sys_data:
                    new_state_idx = sys_data["new_state"]
                    timestamp = log_data.get("start@")

                    if log_id in self.entities:
                        self.entities[log_id]["current_state"] = new_state_idx
                        self.entities[log_id]["state_history"].append((timestamp, new_state_idx))

            # 3. Enrich the log data for downstream use
            if log_id in self.entities:
                entity_info = self.entities[log_id]
                log_data["_enriched_name"] = entity_info["name"]

                # Enrich the active state if present in the root of the log
                if "state" in log_data:
                    state_idx = log_data["state"]
                    states_list = entity_info["states"]

                    if states_list and 0 <= state_idx < len(states_list):
                        log_data["_enriched_state_name"] = states_list[state_idx]

                # Enrich the state change if present in the sys dict
                if "sys" in log_data:
                    if "new_state" in log_data["sys"]:
                        new_state_idx = log_data["sys"]["new_state"]
                        states_list = entity_info["states"]

                        if new_state_idx is not None and states_list:
                            if 0 <= new_state_idx < len(states_list):
                                log_data["sys"]["_enriched_new_state_name"] = states_list[new_state_idx]

            return log_data
```

## `File: tasktonic-visual-logger\main_dummy_gen.py`
```python
from TaskTonic import *
import random


class Dummy(ttTonic):
    def __init__(self):
        super().__init__()

    def ttse__on_start(self):
        DummyLogGenerator()
        DummyStateGenerator()
        DummyRandomGenerator()
        ttTimerSingleShot(seconds=10, name='timeout')

    def ttse__on_timeout(self, _):
        self.finish()


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
        self.log(f"GET LOUD{random.randint(8, 20) * '!'}")


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


# create ui logger =======================================================================
import time
from TaskTonic.ttLoggers import ttLogService
from network_handlers import *

class UiLogger(ttLogService):
    """
    Intercepts the real TaskTonic log stream, formats the data,
    and forwards it to the visual LogCenter instead of the terminal.
    """
    _tt_force_stealth_logging = False

    def __init__(self, name=None):
        super().__init__(name=name, log_mode=ttLog.QUIET)
        self.net = None
        self.counter = None

        prj = self.ledger.formula.at('tasktonic/project')
        self.log_bucket = [{
            'start_new_session': True,
            'project': prj['name'].v,
            'start@': prj['started@'].v,
            'connection': "<ip>:<port>",
            'logger_version': 0,
        }]


    def put_log(self, log):
        self.ttsc__add_log(log)

    def ttse__on_start(self):
        self.counter = 0

        # Start the IP client connecting to our Visual Logger
        self.net = DictSocketHandler(as_client=True, host='127.0.0.1', port=9999)
        self.to_state('wait_for_connection')

    def ttse__on_socket_status(self, status, info=None):
        self.log(f"Network status changed: {status}")

    def ttse__on_socket_connected(self, addr):
        self.to_state('connected')
        self.log(f"Connected to visual logger at {addr}")
        print(f"Connected to visual logger at {addr}")

    def ttsc_wait_for_connection__add_log(self, log):
        print(f"BUFF > {log}")
        self.log_bucket.append(log)

    def ttse_connected__on_enter(self):
        for log in self.log_bucket:
            print(log)
            self.net.ttsc__send_data(log)
        self.log_bucket = []

    def ttsc_connected__add_log(self, log):
        print(log)
        self.net.ttsc__send_data(log)

class LoggerApp(ttFormula):
    def creating_formula(self):
        return (
            ('tasktonic/log/service#', 'my_ui'),
            ('tasktonic/log/service./service', UiLogger),
            ('tasktonic/log/service./arguments', {}),

            ('tasktonic/project/name', 'Dummy log generator'),
            ('tasktonic/log/to', 'my_ui'),
            ('tasktonic/log/default', ttLog.QUIET),
        )

    def creating_starting_tonics(self):
        Dummy()


if __name__ == '__main__':
    LoggerApp()

```

## `File: tasktonic-visual-logger\network_handlers.py`
```python
import struct

from TaskTonic import ttCatalyst, ttTonic, ttLog, ttSparkleStack
import socket, selectors, errno
import threading, queue, time

'''
Designer Notes: 
The SelectorHandler is designed as a catalyst for both itself and the socket handlers. This ensures 
that all 'sparkles' are executed from the same thread, which is required because Python's selectors 
are not thread-safe by design.

In the sparkling loop, we need to monitor both the catalyst queue and selector events. Since we 
want to avoid polling (busy waiting), a adapted queue is created: MyNotifyingQueue. Putting data now 
also signals a notification channel to trigger a selector event. This wakes up the loop, allowing 
it to process the queue and execute the sparkles.
'''


class SelectorHandler(ttCatalyst):
    _tt_is_service = 'selector_handling_service'
    _tt_root_context = True

    # _tt_force_stealth_logging = True

    def __init__(self, *args, name=None, log_mode=None, **kwargs):
        super().__init__(name, log_mode, dont_start_yet=True)

        self.register_data = {}
        self._queue_filled_notify_channel = None
        self._queue_filled_notify_channel_read = None

        # startup notifier
        self.selector = selectors.DefaultSelector()
        self._queue_filled_notify_channel, self._queue_filled_notify_channel_read = socket.socketpair()
        self._queue_filled_notify_channel.setblocking(False)
        self._queue_filled_notify_channel_read.setblocking(False)
        self.selector.register(self._queue_filled_notify_channel_read, selectors.EVENT_READ,
                               (1, self._handle_queue_filled_notify_channel, None))
        self.start_sparkling()

    def _init_service(self, *args, context=None, **kwargs):
        pass

    def new_catalyst_queue(self):
        class MyNotifyingQueue(queue.SimpleQueue):
            def __init__(self, catalyst, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.catalyst = catalyst

            def put(self, item):
                super().put(item)
                try:
                    self.catalyst._queue_filled_notify_channel.send(b'1')  # notify: queue filled
                except:
                    pass

        return MyNotifyingQueue(self)

    def sparkle(self):
        """
        The main execution loop of the Catalyst.

        This method continuously pulls work orders (instance, sparkle, args, kwargs)
        from the queue and executes them. It runs until the `self.sparkling` flag
        is set to False.
        """
        self.thread_id = threading.get_ident()
        sp_stck = ttSparkleStack()
        sp_stck.catalyst = self
        self.sparkling = True
        sparkles_in_queue = True

        # The loop continues as long as the Catalyst is in a sparkling state.
        while self.sparkling:
            reference = time.time()
            next_timer_expire = 0.0
            while next_timer_expire == 0.0:
                next_timer_expire = self.timers[0].check_on_expiration(reference) if self.timers else 60.0
            if sparkles_in_queue: next_timer_expire = 0.0
            try:
                events = self.selector.select(timeout=next_timer_expire)
                for key, mask in events:
                    sock = key.fileobj
                    mode, rd_sparkle, wr_sparkle = key.data  # data contains the callback function
                    if mode == 1:  # connection rd/wr
                        if mask & selectors.EVENT_READ:
                            try:
                                data = sock.recv(65536)
                            except OSError:
                                data = b''
                            if not data: self.unregister(sock=sock)
                            rd_sparkle(data)
                        if mask & selectors.EVENT_WRITE:
                            wr_sparkle()
                    elif mode == 2:  # server accept
                        conn, addr = sock.accept()
                        conn.setblocking(False)
                        rd_sparkle(conn, addr)
            except TimeoutError:
                pass
            except OSError as e:
                # Op Windows: Check op 'bad file descriptor'
                if getattr(e, 'winerror', 0) == 10038:
                    # Logica om dode sockets op te ruimen
                    pass
                else:
                    raise e
            except Exception:
                raise

            # handle sparkles if any
            try:
                instance, sparkle, args, kwargs, sp_stck.source = self.catalyst_queue.get_nowait()
                sp_name = sparkle.__name__
                sp_stck.push(instance, sp_name)
                instance._execute_sparkle(sparkle, *args, **kwargs)
                sp_stck.pop()

                sp_stck.source = (instance, sp_name)
                while self.extra_sparkles:
                    instance, sparkle, args, kwargs = self.extra_sparkles.pop(0)
                    sp_stck.push(instance, sparkle.__name__)
                    instance._execute_sparkle(sparkle, *args, **kwargs)
                    sp_stck.pop()
                sparkles_in_queue = True
            except queue.Empty:
                sparkles_in_queue = False

        # clean up notifier channel
        self.selector.unregister(self._queue_filled_notify_channel_read)
        self._queue_filled_notify_channel.close()
        self._queue_filled_notify_channel_read.close()

    def _handle_queue_filled_notify_channel(self, data):
        # data read, but has no meaning.
        pass

    def register(self, sock, context, mode=1, mask=None, rd=None, wr=None, rd_sparkle=None, wr_sparkle=None):
        if sock is None: sock = context.comm_socket
        if mask is None:
            mask = 0
            if rd is not None and rd: mask |= selectors.EVENT_READ
            if wr is not None and wr: mask |= selectors.EVENT_WRITE
            if mask == 0: mask = selectors.EVENT_READ
        if rd_sparkle is None: rd_sparkle = context.ttse__on_socket_rd
        if wr_sparkle is None: wr_sparkle = context.ttse__on_socket_wr
        self.register_data[sock] = {'mask': mask, 'data': (mode, rd_sparkle, wr_sparkle)}
        self.selector.register(sock, mask, (mode, rd_sparkle, wr_sparkle))

    def unregister(self, sock=None):
        try:
            self.selector.unregister(sock)
        except:
            pass
        try:
            self.register_data.pop(sock)
        except:
            pass

    def modify(self, sock, mask=None, rd=None, wr=None):
        if mask is None:
            mask = self.register_data[sock]['mask']
            if rd is not None: mask = mask & ~selectors.EVENT_READ | (selectors.EVENT_READ if rd else 0)
            if wr is not None: mask = mask & ~selectors.EVENT_WRITE | (selectors.EVENT_WRITE if wr else 0)
        if mask == 0:
            if self.register_data[sock]['mask'] != 0:
                self.selector.unregister(sock)
        else:
            if self.register_data[sock]['mask'] == 0:
                self.selector.register(sock, mask, self.register_data[sock]['data'])
            else:
                self.selector.modify(sock, mask, self.register_data[sock]['data'])
        self.register_data[sock]['mask'] = mask


class SocketHandler(ttTonic):
    _tt_force_stealth_logging = True

    def __init__(self, as_server=None, as_client=None, host=None, port=None, **kwargs):
        # Look for service before calling super init and create if not active

        from TaskTonic import ttLedger
        l = ttLedger()
        srv = l.get_service_essence('selector_handling_service')
        if not srv:
            srv = SelectorHandler(log=ttLog.QUIET)

        super().__init__(catalyst=srv.catalyst, **kwargs)

        if as_server is not None and as_client is not None:
            raise ValueError('Make up your mind error: cannot specify both as_server and as_client')
        self.as_server = as_server if as_server is not None else not as_client
        self.server_host = host if host is not None else 'localhost'
        self.server_port = port if port is not None else '5555'
        self.server_addr = f'{host}:{port}'

        self.selector_handler = SelectorHandler()
        self.server_socket = None
        self.comm_socket = None
        self.comm_addr = None
        self.retry = 0
        self.rcv_buf = b''
        self.send_buf = b''
        self.buffering_send = False

    def ttse__on_start(self):
        st_init = 'init_server' if self.as_server else 'init_client'
        self.log(st_init)
        self.to_state(st_init)
        self.ttsc__start_init()

    def ttse__on_enter(self):
        if hasattr(self.base, 'ttse__on_socket_status'):
            self.base.ttse__on_socket_status(self.get_active_state())

    def ttsc_init_server__start_init(self):
        self.log(f'Init server: {self.server_addr}')
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow reuse of address
        self.server_socket.bind((self.server_host, self.server_port))
        self.server_socket.listen(1)  # Accept 1 connection at a time
        self.server_socket.setblocking(False)
        self.to_state('server_wait_for_connection')
        self.selector_handler.register(self.server_socket, self, rd=1, mode=2, rd_sparkle=self.ttse__on_server_rd)

    def ttse_server_wait_for_connection__on_server_rd(self, conn, addr):
        self.selector_handler.unregister(sock=self.server_socket)
        self.server_socket.close()
        self.server_socket = None

        self.comm_socket = conn  # Store the client socket
        self.comm_addr = addr
        self.to_state('connected')
        self.selector_handler.register(self.comm_socket, self, rd=1)

    def ttsc_init_client__start_init(self):
        self.log(f'Init client: connect to {self.server_addr}')
        self.comm_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.comm_socket.setblocking(False)

        try:
            self.selector_handler.register(self.comm_socket, self, wr=1)
            self.comm_socket.connect((self.server_host, self.server_port))
        except BlockingIOError as e:
            if e.errno == errno.EINPROGRESS or e.errno == errno.WSAEWOULDBLOCK:
                self.to_state('client_wait_for_connection')
                return
            else:
                raise e

        self.comm_addr = f'{self.server_host}:{self.server_port}'
        self.to_state('connected')
        self.selector_handler.modify(self.comm_socket, rd=1, wr=0)

    def ttse_client_wait_for_connection__on_socket_wr(self):
        err = self.comm_socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        if err:
            import os
            self.log(f"Connection failed: {os.strerror(err)}")
            self.selector_handler.unregister(self.comm_socket)
            self.comm_socket.close()
            self.comm_socket = None

            if self.retry > 3:
                self.finish()
            else:
                self.retry += 1
                self.to_state('wait_for_retry')
            return

        self.comm_addr = f'{self.server_host}:{self.server_port}'
        self.to_state('connected')
        self.selector_handler.modify(self.comm_socket, rd=1, wr=0)

    def ttse_wait_for_retry__on_enter(self):
        self.log("Scheduling connection retry in 2 seconds...")
        ttTimerSingleShot(seconds=2, name='tm_retry')

    def ttse_wait_for_retry__on_tm_retry(self, _):
        self.log("Attempting to reconnect to the server...")
        self.to_state('init_client')
        self.ttsc__start_init()


    def ttse_connected__on_enter(self):
        if hasattr(self.base, 'ttse__on_socket_status'):
            self.base.ttse__on_socket_status('connected')
        if hasattr(self.base, 'ttse__on_socket_connected'):
            self.base.ttse__on_socket_connected(self.comm_addr)

    def ttse_connected__on_socket_rd(self, data):
        if data:
            for data in self.rcv_data_conversion(data):
                self.base.ttse__on_socket_data(data)
        else:
            self.comm_socket = None
            self.finish()

    def ttse_connected__on_socket_wr(self):
        # pick up writing if send blocked
        self._send(self.send_buf)

    def ttsc_connected__send_data(self, data):
        bdata = self.send_data_conversion(data)
        if self.buffering_send:
            self.send_buf += bdata
        else:
            self._send(bdata)

    def _send(self, bdata):
        try:
            sent = self.comm_socket.send(bdata)
        except BlockingIOError:
            sent = 0

        if sent == len(bdata):
            self.send_buf = b''
            self.buffering_send = False
            self.selector_handler.modify(self.comm_socket, wr=0)
        else:
            self.send_buf = bdata[sent:]
            self.buffering_send = True
            self.selector_handler.modify(self.comm_socket, wr=1)

    def ttse_connected__on_exit(self):
        self.log(f'Disconnected from {self.comm_addr}')

    def send_data_conversion(self, bdata):
        return bdata

    def rcv_data_conversion(self, bdata):
        return [bdata]

    def ttse__on_finished(self):
        if hasattr(self.base, 'ttse__on_socket_finished'):
            self.base.ttse__on_socket_finished()
            if hasattr(self.base, 'ttse__on_socket_status'):
                self.base.ttse__on_socket_status('finished')
        if self.comm_socket:
            self.selector_handler.unregister(sock=self.comm_socket)
            self.comm_socket.close()
        if self.server_socket:
            self.selector_handler.unregister(sock=self.server_socket)
            self.server_socket.close()


class StrSocketHandler(SocketHandler):
    def send_data_conversion(self, str_data):
        if not isinstance(str_data, str): raise TypeError('Data must be a string')
        return str_data.encode('utf-8')

    def rcv_data_conversion(self, bdata):
        return [bdata.decode('utf-8', errors='replace')]


import pickle


class DictSocketHandler(SocketHandler):
    def send_data_conversion(self, dict_data):
        if not isinstance(dict_data, dict):
            raise TypeError('Data must be a dict')
        pdict = pickle.dumps(dict_data)
        return b'' + struct.pack('!I', len(pdict)) + pdict

    def rcv_data_conversion(self, bdata):
        dicts = []
        self.rcv_buf += bdata
        while len(self.rcv_buf) > 4:  # start check if rcv_buf at least hast length (4 bytes) and dict data
            plen = struct.unpack('!I', self.rcv_buf[:4])[0]
            if len(self.rcv_buf) < plen + 4: break  # not enough data, wait for it
            dicts.append(pickle.loads(self.rcv_buf[4:plen+4]))
            self.rcv_buf = self.rcv_buf[plen + 4:]
        return dicts


# --- Usage Example ---
from TaskTonic import ttTonic, ttFormula, ttTimerRepeat, ttTimerSingleShot


class ChatClient(ttTonic):
    def __init__(self, name=None):
        super().__init__(name=name)
        self.cnt = None
        self.net = None
        self.bulk_cnt = 0

    def ttse__on_start(self):
        self.log("Client starting delay...")
        ttTimerSingleShot(1, sparkle_back=self.ttse__on_delayed_start)

    def ttse__on_delayed_start(self, info):
        self.log("Starting Client...")
        # Bind Service: IpService is now a Catalyst running in its own thread
        self.net = StrSocketHandler(as_client=True, host='localhost', port=9999)
        self.cnt = 0

    def ttse__on_socket_status(self, status, info=None):
        self.log(f"Client Status: {status} - {info}")

    def ttse__on_socket_connected(self, addr):
        self.tmr = ttTimerRepeat(1, name='client_ping_tmr', sparkle_back=self.ttsc__ping)
        self.to_state('ping')

    def ttsc_ping__ping(self, info):
        self.cnt += 1
        self.net.ttsc__send_data(f"Ping {self.cnt}")
        self.log(f"Ping {self.cnt}")

    def ttse_ping__on_socket_data(self, data):
        # This method is called safely by the IpService thread!
        self.log(f"Client received: {data}")
        if 'STOPPED' in data:
            self.to_state('bulk')
            self.tmr.finish()

    def ttse_bulk__on_socket_data(self, data):
        if not hasattr(self, 'start_bulk'): self.start_bulk = time.time()
        self.bulk_cnt += len(data)
        self.log(f"Received: {self.bulk_cnt} bytes total in {(time.time() - self.start_bulk):2.3f} seconds")

    def ttse__on_socket_finished(self):
        self.finish()


class ChatServer(ttTonic):
    def ttse__on_start(self):
        self.log("Starting Server...")
        self.net = DictSocketHandler(as_server=True, host='localhost', port=9999)

    def ttse__on_socket_connected(self, addr):
        self.log(f"Connected event: {addr}")

    def ttse__on_socket_status(self, status, info=None):
        self.log(f"Server Status: {status} - {info}")

    def ttse__on_socket_data(self, data):
        self.log(f"Server got: {data}")
        # Simple echo (broadcasts to all connections of this tonic inInfusion completed this simple impl)
        self.net.ttsc__send_data(f"Echo: {data}")

        if data == 'Ping 4':
            self.net.ttsc__send_data(f" / STOPPED")
            ttTimerSingleShot(1, name='server_wait_for_sending_bulk', sparkle_back=self.ttsc__start_sending_bulk)

    def ttsc__start_sending_bulk(self, info):
        self.ttsc__send_bulk(100)

    def ttsc__send_bulk(self, cnt):
        if cnt == 0:
            ttTimerSingleShot(5, name='tmr_pause_before_finishing', sparkle_back=self.ttse__on_pause_over)
            return

        self.net.ttsc__send_data('1' * 1_000_000)
        self.ttsc__send_bulk(cnt - 1)

    def ttse__on_pause_over(self, info):
        self.finish()

    def ttse__on_socket_finished(self):
        self.finish()


class NetworkApp(ttFormula):
    def creating_formula(self):
        return (
            ('tasktonic/log/to', 'screen'),
            ('tasktonic/log/default', 'full'),
        )

    def creating_starting_tonics(self):
        ChatServer(name="Server")
        # Give server time to bind (conceptually, though select handles async connect fine)
        # ChatClient(name="Client")


if __name__ == "__main__":
    NetworkApp()

```

## `File: tasktonic-visual-logger\ui\log_viewer.py`
```python
from PySide6.QtWidgets import QVBoxLayout, QListWidget, QListWidgetItem
from PySide6.QtCore import Qt

from TaskTonic.ttTonicStore import ttPysideWidget


class LoggerWidget(ttPysideWidget):
    """
    Displays the textual representation of the log stream.
    """

    def __init__(self, session_store, parent=None, **kwargs):
        super().__init__(name=None, parent=parent, **kwargs)
        self.session_store = session_store

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.log_list = QListWidget(self)
        self.log_list.setStyleSheet("background-color: #121212; color: #cccccc; font-family: monospace;")
        self.layout.addWidget(self.log_list)

        # Bind the store update to the Qt thread sparkle
        self.session_store.subscribe('logs', self.ttse__on_logs_updated)

    def ttse__on_logs_updated(self, item):
        logs = item.v

        if not logs:
            return

        latest_log = logs[-1]

        enriched = latest_log.get('enriched', {})
        display_sparkle = enriched.get('display_sparkle', 'Unknown')
        state_name = enriched.get('state_name', 'idle')
        ui_lines = enriched.get('ui_log_lines', [])

        main_line = f"[{state_name.upper()}] {display_sparkle}"
        list_item = QListWidgetItem(main_line)
        self.log_list.addItem(list_item)

        for line in ui_lines:
            sub_item = QListWidgetItem(f"    - {line}")
            sub_item.setForeground(Qt.darkGray)
            self.log_list.addItem(sub_item)

        self.log_list.scrollToBottom()

```

## `File: tasktonic-visual-logger\ui\main_window.py`
```python
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QPushButton, QTabWidget, QSplitter, QLabel, QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction

from TaskTonic.ttTonicStore import ttPysideWindow, ttPysideWidget

from log_viewer import LoggerWidget
from timeline_viewer import TimelineContainer


class SessionViewWidget(ttPysideWidget):
    """
    Encapsulates the UI for a single isolated log session.
    Utilizes a state machine to manage waiting, embedded tab, and floating window modes.
    """

    def __init__(self, session_store, mode='tab', **kwargs):
        self.session_store = session_store
        self.target_mode = mode
        self.session_title = "Waiting..."

        super().__init__(name=None, **kwargs)

        self.session_store.subscribe('status', self.ttse__on_status_changed)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Control bar for title and dynamic mode switching
        ctrl_layout = QHBoxLayout()
        self.lbl_title = QLabel(self.session_title)
        self.lbl_title.setStyleSheet("color: #00aaff; font-weight: bold; padding: 4px;")

        self.btn_switch = QPushButton("Switch Mode")

        ctrl_layout.addWidget(self.lbl_title)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(self.btn_switch)
        layout.addLayout(ctrl_layout)

        splitter = QSplitter(Qt.Vertical)
        top_splitter = QSplitter(Qt.Horizontal)

        self.logger_panel = LoggerWidget(session_store=self.session_store, parent=self)

        self.glass_label = QLabel("Tonic Glass Visualizer")
        self.glass_label.setAlignment(Qt.AlignCenter)
        self.glass_label.setStyleSheet(
            "background: #050505; color: #00aaff; border: 1px solid #333; border-radius: 4px;"
        )

        self.timeline_view = TimelineContainer(session_store=self.session_store, parent=self)

        top_splitter.addWidget(self.logger_panel)
        top_splitter.addWidget(self.glass_label)
        top_splitter.setStretchFactor(0, 4)

        splitter.addWidget(top_splitter)
        splitter.addWidget(self.timeline_view)
        splitter.setStretchFactor(0, 5)

        layout.addWidget(splitter)

    def ttse__on_start(self):
        # Start in the hidden/waiting state
        self.to_state('waiting')

    # state fallback routines
    def ttse__on_status_changed(self, updates):
        for _, status, _, _ in updates:
            if status == 'connected':
                addr = self.session_store.get('remote_address', self.session_store.path)
                self.session_title = f"Connected: {addr}"
                self.lbl_title.setText(self.session_title)

                # Only transition if we are currently waiting for the first connection
                if self.state == 'waiting':
                    self.to_state(self.target_mode)

    # --- WAITING STATE ---
    def ttse_waiting__on_status_changed(self, updates):
        for _, status, _, _ in updates:
            if status == 'connected':
                addr = self.session_store.get('remote_address', self.session_store.path)
                self.session_title = f"Connected: {addr}"
                self.lbl_title.setText(self.session_title)

                self.to_state(self.target_mode)

    # --- TAB STATE ---
    def ttse_tab__on_enter(self):
        self.base.ttsc__register_view(self, self.session_title)

    def ttqt_tab__btn_switch__clicked(self):
        self.to_state('win')

    def ttse_tab__on_exit(self):
        self.base.ttsc__unregister_view(self)

    # --- WINDOW STATE ---
    def ttse_win__on_enter(self):
        self.setParent(None)
        self.setWindowTitle(self.session_title)
        self.resize(1000, 700)
        self.show()

    def ttqt_win__btn_switch__clicked(self):
        self.to_state('tab')

    def ttse_win__on_exit(self):
        pass


class LogWorkspaceWidget(ttPysideWidget):
    """
    Manages all embedded session views using a QTabWidget.
    """

    def __init__(self, **kwargs):
        self.container = None
        super().__init__(**kwargs)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.container = QTabWidget(self)
        self.container.setStyleSheet("QTabWidget::pane { border: 1px solid #444; }")
        layout.addWidget(self.container)

    def add_session_tab(self, view_widget, title):
        idx = self.container.addTab(view_widget, title)
        self.container.setCurrentIndex(idx)

    def remove_session_tab(self, view_widget):
        idx = self.container.indexOf(view_widget)
        if idx >= 0:
            self.container.removeTab(idx)


class LoggerMainWindow(ttPysideWindow):
    """
    The main distributor window containing the workspace tabs.
    """

    def __init__(self, lc_store, **kwargs):
        self.lc_store = lc_store
        self.workspace = None
        self.exit_action = None

        super().__init__(**kwargs)

        # Workaround for ttPysideWindow framework bug
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("TaskTonic Studio - Workspace Manager")
        self.resize(1200, 800)
        self.setStyleSheet("QMainWindow { background-color: #000; } QSplitter::handle { background: #444; }")

        menubar = self.menuBar()
        menubar.setStyleSheet("background: #1e1e1e; color: white;")

        file_menu = menubar.addMenu("File")
        self.exit_action = QAction("Exit", self)
        file_menu.addAction(self.exit_action)
        self.exit_action.triggered.connect(self.ttqt__exit_action__triggered)

        self.workspace = LogWorkspaceWidget(parent=self)
        self.setCentralWidget(self.workspace)

    def ttse__on_start(self):
        self.lc_store.subscribe('newest_session_path', self.ttse__on_new_session)

        # Catch up on the current state (LogCenter might have been faster)
        current_path = self.lc_store.get('newest_session_path', '')
        if current_path:
            session_store = self.lc_store.at(current_path)
            # Create the initial view manually
            SessionViewWidget(session_store, mode='tab')

        self.show()

    def ttse__on_new_session(self, updates):
        for _, session_path, _, _ in updates:
            if session_path:
                session_store = self.lc_store.at(session_path)

                # Create the view; base is automatically set to self (LoggerMainWindow)
                SessionViewWidget(session_store, mode='tab')

    def ttsc__register_view(self, view_widget, title):
        self.workspace.add_session_tab(view_widget, title)

    def ttsc__unregister_view(self, view_widget):
        self.workspace.remove_session_tab(view_widget)

    def ttqt__exit_action__triggered(self):
        self.catalyst.finish()

```

## `File: tasktonic-visual-logger\ui\__init__.py`
```python

```

## `File: tasktonic-visual-logger\ui\timeline_viewer.py`
```python
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtGui import QPainter, QColor
from PySide6.QtCore import Qt

from TaskTonic.ttTonicStore import ttPysideWidget


class TimelineContainer(ttPysideWidget):
    """
    Wrapper for the timeline to handle structural layout.
    """

    def __init__(self, session_store, parent=None, **kwargs):
        super().__init__(parent=parent, **kwargs)
        self.session_store = session_store

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.canvas = TimelineView(self.session_store, parent=self)
        self.layout.addWidget(self.canvas)


class TimelineView(ttPysideWidget):
    """
    The canvas where log states are drawn as colored bars over time.
    """

    def __init__(self, session_store, parent=None, **kwargs):
        super().__init__(parent=parent, **kwargs)
        self.session_store = session_store
        self.setMinimumHeight(150)

        # Subscribe to logs and trigger repaint on the Qt thread
        self.session_store.subscribe('logs', self.ttse__trigger_repaint)

    def ttse__trigger_repaint(self, item):
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#1e1e1e"))

        logs = self.session_store.get('logs', [])

        if not logs:
            return

        color_map = {
            0: QColor("#2b5b84"),
            1: QColor("#845b2b"),
            2: QColor("#842b2b")
        }

        x_offset = 10
        block_width = 8

        for log_entry in logs[-100:]:
            state_idx = log_entry.get('state', 0)
            color = color_map.get(state_idx, QColor("#555555"))

            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawRect(x_offset, 30, block_width, 80)

            x_offset += (block_width + 2)

            if x_offset > self.width():
                break

```

## `File: tasktonic-visual-logger\ui\theme.py`
```python
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

```

## `File: tasktonic-visual-logger\ui\demo_show_widget.py`
```python
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
```

## `File: tasktonic-visual-logger\testing\test_log_center.py`
```python
import time
from TaskTonic import ttFormula
from TaskTonic.ttTonicStore import ttDistiller
from log_center import LogCenter


class LogCenterTestFormula(ttFormula):
    def creating_formula(self):
        return {
            'tasktonic/log/to': 'off',  # No output from the framework itself
            'tasktonic/log/default': 'stealth',
        }

    def creating_main_catalyst(self):
        self.distiller = ttDistiller(name='tt_main_catalyst')

    def creating_starting_tonics(self):
        self.lc = LogCenter()


def test_log_center_flow():
    app = LogCenterTestFormula()
    distiller = app.distiller
    lc = app.lc

    print("\n--- Starting LogCenter Test ---")

    try:
        # 1. Startup phase
        status = distiller.sparkle(timeout=.1, till_sparkle_in=['_ttinternal_state_change_to'])
        print(distiller.stat_print(status))

        assert lc.get_current_state_name() == 'listening', "LogCenter must start in 'listening' state"
        print("✅ Starts cleanly in [listening] state\n")

        # 2. Fire 3 dummy logs: Simulate a FULL lifecycle of Tonic ID 99
        t0 = time.time()

        # Log 1: Birth (sys.created = True)
        dummy_log_1 = {
            'id': 99,
            'start@': t0,
            'sys': {'created': True},
            'enriched': {'tonic_name': 'LifecycleTest', 'finishing': False}
        }
        # Log 2: Normal activity
        dummy_log_2 = {
            'id': 99,
            'start@': t0 + 0.05,
            'sys': {},
            'enriched': {'tonic_name': 'LifecycleTest', 'finishing': False}
        }
        # Log 3: Death (enriched.finishing = True)
        dummy_log_3 = {
            'id': 99,
            'start@': t0 + 0.1,
            'sys': {},
            'enriched': {'tonic_name': 'LifecycleTest', 'finishing': True}
        }

        lc.ttse__new_log(dummy_log_1)
        lc.ttse__new_log(dummy_log_2)
        lc.ttse__new_log(dummy_log_3)

        # 3. Process queue until 'buffering'
        status = distiller.sparkle(timeout=1, till_state_in=['buffering'])
        assert lc.get_current_state_name() == 'buffering', "Must be in 'buffering' state now"
        print("✅ Switches directly to [buffering] after the first log")

        # 4. Wait for the 100ms timer batch
        status = distiller.sparkle(timeout=1.5, till_state_in=['listening'])

        duration = status.get("end@", 0) - status.get("start@", 0)
        assert 0.19 < duration < 0.21, f"Buffering took {duration}s, expected ~0.20s"
        print(f"✅ Buffering took exactly 2 periods of 100ms")

        assert len(lc.store_logs) == 3, "There must be 3 logs in RAM"
        print("✅ 3 logs successfully recorded in RAM")

        last_append = lc.session.get("last_append")
        assert last_append == (1, 2), f"Expected (1, 2) but got {last_append}"
        print("✅ Timer fired and Store correctly triggered the batch (1, 2)!\n")

        # ==========================================================
        # 5. THE NEW HISTORY INDEX TEST
        # ==========================================================
        history = lc.session.at("ui/history").v

        print(history)

        assert len(history) == 1, f"History should contain exactly 1 finished run, found {len(history)}"

        run_info = history[0]
        assert run_info['tonic_id'] == 99, "Tonic ID was not stored correctly"
        assert run_info['name'] == 'LifecycleTest', "Tonic name was not stored correctly"
        assert 'run_id' in run_info, "Run ID is missing in history!"
        assert run_info['start_log_idx'] == 0, "The start index must be 0 (first log in RAM)"
        assert run_info['end_log_idx'] == 2, "The end index must be 2 (third log in RAM)"

        print("✅ History Index successfully updated after Tonic death!")
        print(
            f"   -> Stored run: {run_info['run_id']} (Duration: {(run_info['end_ts'] - run_info['start_ts']) * 1000:.1f}ms)\n")

    finally:
        # 6. Clean up
        lc.finish()
        distiller.finish_distiller()
        print("🎉 Test execution finished and cleaned up.")
```

## `File: tasktonic-visual-logger - old not in git\log_center.py`
```python
import time
from TaskTonic import ttTonic, ttTimerSingleShot, ttTimerRepeat
from TaskTonic.internals import Store




# --- MONKEY PATCH VOOR TASKTONIC STORE ---
from TaskTonic.internals.Store import Item

def _patch_item_subscribe(self, subpath: str, callback, ignore_source: str = None, recursive: bool = True,
                          exclude: list = None):
    """Dynamische patch: voegt subscribe toe aan de Item class."""
    target = f"{self._path}/{subpath}".strip("/") if subpath else self._path
    self._store.subscribe(target, callback, ignore_source, recursive, exclude)

Item.subscribe = _patch_item_subscribe
# -----------------------------------------

class LogCenter(ttTonic, Store):
    """
    Centralized Log Manager. Handles ingestion of single logs,
    metrics calculation, and Store-based batch notifications for the UI.
    """
    _tt_is_service = "log_center"
    _tt_force_stealth_logging = True

    def __init__(self, *args, **kwargs):
        # Break the multiple inheritance chain properly
        ttTonic.__init__(self, *args, **kwargs)
        Store.__init__(self)

        self.buffering_start_idx = 0
        self.base_ts = None
        self.seen_ids = set()
        self.active_runs = {}

        # Define the root path for this session
        session_name = time.strftime("%Y%m%d_%H%M_Session")
        self.session_root = f"sessions/{session_name}"

        # 1. Fetch settings from the global project formula (default to 5000)
        settings_path = self.ledger.formula.at('tasktonic/project/settings/log')
        self.max_ram_history = settings_path.get("max_ram_history", 5000)

        # 2. Initialize the session structure in the Store
        self.session = self.at(self.session_root)

        with self.group(notify=False):
            self.session.set((
                ("logs", []),
                ("metrics_100ms", []),
                ("live_count", 0),
                ("last_append", (0, 0)),  # <-- TUPLE: (start_idx, count)
                ("ui/timeline/mode", "tailing"),
                ("ui/timeline/zoom_sec", 30),
                ("ui/timeline/focus_ts", 0.0),
                ("ui/id", {}),
                ("ui/id_version", 0),
                ("ui/history", []),
            ))

        # 3. Create elegant, direct references to the Store list values (for speed)
        self.store_logs = self.session.at("logs").v
        self.store_metrics = self.session.at("metrics_100ms").v


    def _init_post_action(self):
        super()._init_post_action()

    def ttse__on_start(self):
        self.to_state('listening')

    # =====================================================================
    # STATE: listening
    # =====================================================================
    def ttse_listening__new_log(self, log_data):
        self._append_single_log(log_data)
        self.session["last_append"] = (len(self.store_logs) - 1, 1)
        self.to_state('buffering')

    # =====================================================================
    # STATE: buffering
    # =====================================================================
    def ttse_buffering__on_enter(self):
        # Group incoming logs for 100ms before notifying the UI
        self.tm_batch = ttTimerRepeat(seconds=0.1, name="tm_batch")
        self.buffering_start_idx = len(self.store_logs)

    def ttse_buffering__new_log(self, log_data):
        self._append_single_log(log_data)

    def ttse_buffering__on_tm_batch(self, tinfo):
        count = len(self.store_logs) - self.buffering_start_idx

        if count <= 0:
            # no new logs buffered, goto listening
            self.to_state('listening')
            return

        self.session["last_append"] = (self.buffering_start_idx, count)
        self.buffering_start_idx = len(self.store_logs)

    def ttse_buffering__on_exit(self):
        self.tm_batch.finish()

    # =====================================================================
    # HELPER METHODS
    # =====================================================================
    def _append_single_log(self, log):
        # Appends directly into the Store's list memory (ultra fast)
        self.store_logs.append(log)

        # Optional: trigger direct subscribers (creates high UI load if many logs)
        self.session["live_count"] = len(self.store_logs)

        # calculate metrics
        t_id = log.get('id', 0)
        ts = log.get('start@', time.time())

        # Haal verrijkte info op uit de log (die UiLogger erin heeft gestopt)
        enriched = log.get('enriched', {})
        is_created = log.get('sys', {}).get('created', False)
        is_finishing = enriched.get('finishing', False)

        if self.base_ts is None:
            self.base_ts = ts

        # --- LEVENSCYCLUS TRACKING ---
        # 1. Start een nieuwe generatie als hij gecreëerd wordt (of als we hem nog niet kenden)
        if is_created or t_id not in self.active_runs:
            run_id = f"{t_id:02d}_{ts:.3f}"  # Bijv: "04_170521.123"
            self.active_runs[t_id] = {
                "run_id": run_id,
                "tonic_id": t_id,
                "name": enriched.get('tonic_name', f'Unknown_{t_id}'),
                "start_ts": ts,
                "start_log_idx": len(self.store_logs) - 1  # Weet precies op welke regel hij begon!
            }

        # Stempel de log met zijn huidige unieke generatie-ID
        current_run = self.active_runs[t_id]
        enriched['run_id'] = current_run['run_id']

        # 2. Sluit de generatie netjes af als de tonic sterft
        if is_finishing and t_id in self.active_runs:
            finished_run = self.active_runs.pop(t_id)
            finished_run['end_ts'] = ts
            finished_run['end_log_idx'] = len(self.store_logs) - 1

            # Sla hem permanent op in de history index van de Store
            with self.group(notify=False):
                history_list = self.session.at("ui/history").v
                history_list.append(finished_run)

        # --- BESTAANDE METRICS & ID REGISTRATIE ---
        if t_id not in self.seen_ids:
            self.seen_ids.add(t_id)
            ui_id_version = self.session["ui/id_version"].v
            with self.group(notify=False):
                self.session.set([
                    (f"ui/id/{t_id:02d}/active", True),
                    (f"ui/id/{t_id:02d}/color_idx", 0),
                    ("ui/id_version", ui_id_version+1),
                ])

        bin_idx = int((ts - self.base_ts) * 10)
        if bin_idx < 0: return

        if bin_idx >= len(self.store_metrics):
            extension_needed = (bin_idx - len(self.store_metrics)) + 1
            self.store_metrics.extend([{} for _ in range(extension_needed)])

        bucket = self.store_metrics[bin_idx]
        bucket[t_id] = bucket.get(t_id, 0) + 1
```

## `File: tasktonic-visual-logger - old not in git\main.py`
```python
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

```

## `File: tasktonic-visual-logger - old not in git\ttUiLogger.py`
```python
from .. import ttTimerRepeat
from ..ttLogger import ttLogService
import time

class ttUiLogService(ttLogService):

    def __init__(self, name=None):
        super().__init__(name)
        self.log_records = []
        prj = self.ledger.formula.at('tasktonic/project')
        ts = prj['started@'].v
        lt = time.localtime(ts)
        l_time_start = f'{time.strftime("%H%M%S", lt)}.{int((ts - int(ts)) * 1000):03d}'

        print(f"[{l_time_start}] TaskTonic log for {prj['name'].v}, started at {time.strftime('%H:%M:%S', lt)}")
        print(41 * '-=')
    def _tt_init_service_base(self, base, *args, **kwargs):
        self.log(close_log=True)

    def put_log(self, log):
        self.ttsc__add_log(log)

    def ttse__on_start(self):
        pass

    def ttse__on_finished(self):
        print(41*'-=')
        print('Logging finished')
        print(self.ledger.sdump())

    def ttsc__add_log(self, log):
        """
        Formats and prints the collected log entry for an event, then resets it.
        """
        l_id = log.get('id', -1)
        if l_id < 0:
            raise RuntimeError(f'Error in log entry {log}')

        if log.get('sys',{}).get('created', False):

            while len(self.log_records) <= l_id:
                self.log_records.append(None)
            self.log_records[l_id] = log.copy()

        sparkle_name = log.get('sparkle', '')
        sparkle_state_idx = log.get('state', -1)

        if sparkle_name == '_ttinternal_state_change_to':
            sparkle_name = f" TO STATE [{self.log_records[l_id]['sys']['states'][log['sys']['new_state']]}]"

        ts = log['start@']
        lt = time.localtime(ts)
        l_time_start = f'{time.strftime("%H%M%S", lt)}.{int((ts - int(ts)) * 1000):03d}'

        header = f"{self.log_records[l_id]['sys']['name']}"
        if sparkle_state_idx >= 0:
            header += f"[{self.log_records[l_id]['sys']['states'][sparkle_state_idx]}]"
        header += f".{sparkle_name}"

        dont_print_flags = ['id', 'start@', 'log', 'sparkle', 'state', 'sparkles', 'states', 'duration']
        flags_to_print = {k: v for k, v in log.items() if k not in dont_print_flags}

        du = log.get('duration',0.0)
        l_du = '' if du <= .15 else f'DURATION: {du:1.3f} sec !!! '

        print(f"[{l_time_start}] {l_id:02d} - {header:.<65} {l_du}{flags_to_print}")
        if l_states := log.get('states'):
            print(f"{16 * ' '}== STATES: |", end='')
            for state in l_states: print(f" {state} |", end='')
            print()
        if l_sparkles := log.get('sparkles'):
            print(f"{16 * ' '}== SPARKLES: |", end='')
            for sparkle in l_sparkles:
                if not sparkle.startswith('_ttss'): print(f" {sparkle} |", end='')
            print()

        if log.get('log'):
            for line in log['log']:
                line = str(line).replace('\n', f"\n{18*' '}")
                print(f"{16 * ' '}- {line}")
```

## `File: tasktonic-visual-logger - old not in git\ui_logger.py`
```python
import time
from TaskTonic.ttLogger import ttLogService
from log_center import LogCenter


class UiLogger(ttLogService):
    """
    Intercepts the real TaskTonic log stream, formats the data, 
    and forwards it to the visual LogCenter instead of the terminal.
    """
    
    def __init__(self, name=None):
        super().__init__(name)
        self.log_records = []
        prj = self.ledger.formula.at('tasktonic/project')
        ts = prj['started@'].v
        lt = time.localtime(ts)
        self.l_time_start = f'{time.strftime("%H%M%S", lt)}.{int((ts - int(ts)) * 1000):03d}'

        print(f"[{self.l_time_start}] Visual UiLogger engaged for {prj['name'].v}")
        print(41 * '-=')

        startup = {
            'project': prj['name'].v,
            'start@': prj['started@'].v,
            'connection': "<ip>:<port>",
            'logger_version': 0,
        }

        print(startup)

        self.ttsc__add_log(startup)

    def _tt_init_service_base(self, base, *args, **kwargs):
        self.log(close_log=True)

    def put_log(self, log):
        self.ttsc__add_log(log)

    def ttse__on_start(self):
        self.log_center = LogCenter()

    def ttse__on_finished(self):
        print(41 * '-=')
        print('Visual Logging finished')
        print(self.ledger.sdump())

    def ttsc__add_log(self, log):
        print(log)

        l_id = log.get('id', -1)
        if l_id < 0:
            return

        # 1. Maintain metadata cache for tonic names and states
        if log.get('sys', {}).get('created', False):
            while len(self.log_records) <= l_id:
                self.log_records.append(None)
            self.log_records[l_id] = log.copy()  # Hier wel een copy voor in de cache!

        meta = self.log_records[l_id] if l_id < len(self.log_records) and self.log_records[l_id] else None
        if not meta:
            meta = {'sys': {'name': f'Unknown_{l_id}', 'states': []}}

        sparkle_name = log.get('sparkle', '')
        sparkle_state_idx = log.get('state', -1)

        state_list = meta['sys'].get('states', [])
        state_name = state_list[sparkle_state_idx] if state_list and sparkle_state_idx >= 0 else 'idle'

        if sparkle_name == '_ttinternal_state_change_to':
            new_state_idx = log.get('sys', {}).get('new_state', -1)
            if new_state_idx >= 0 and state_list:
                sparkle_name = f"TO STATE [{state_list[new_state_idx]}]"

        # 2. Format extra information to display in the UI body
        extra_log_lines = list(log.get('log', []))

        dont_print = ['id', 'start@', 'log', 'sparkle', 'state', 'sparkles', 'states', 'duration', 'sys', 'source',
                      'catalyst']
        flags_to_print = {k: v for k, v in log.items() if k not in dont_print}
        if flags_to_print:
            extra_log_lines.append(f"Flags: {flags_to_print}")

        du = log.get('duration', 0.0)
        if du > 0.15:
            extra_log_lines.append(f"DURATION: {du:1.3f} sec !!!")

        if l_states := log.get('states'):
            extra_log_lines.append(f"STATES: {l_states}")

        if l_sparkles := log.get('sparkles'):
            filtered_sparkles = [s for s in l_sparkles if not s.startswith('_ttss')]
            if filtered_sparkles:
                extra_log_lines.append(f"SPARKLES: {filtered_sparkles}")

        # 3. DE ENRICHED NAMESPACE
        # We voegen onze berekende UI-data netjes toe in een eigen "mapje"
        log['enriched'] = {
            'display_sparkle': sparkle_name,
            'state_name': state_name,
            'ui_log_lines': extra_log_lines,
            'finishing': '_ttss__remove_tonic_from_catalyst' in sparkle_name,
            'tonic_name': meta['sys']['name'],
            'system_sparkle': sparkle_name.startswith('ttss') or sparkle_name.startswith('_ttss')
        }

        # 4. Inject into the visual LogCenter pipeline
        if hasattr(self, 'log_center'):
            self.log_center.ttse__new_log(log)

```

## `File: tasktonic-visual-logger - old not in git\__init__.py`
```python
from .log_center import LogCenter

```

## `File: tasktonic-visual-logger - old not in git\ui\log_viewer.py`
```python
import time
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QMenu, QWidget, QToolTip, QScrollBar
from PySide6.QtCore import Qt, QRect, QTimer
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush

from TaskTonic.ttTonicStore import ttPysideWidget
from log_center import LogCenter
from theme import Theme


def get_dynamic_lanes(lc):
    """Haalt dynamisch de ID's op en dwingt ze naar integers voor veilige mapping."""
    if hasattr(lc, 'seen_ids'):
        try:
            known_ids = sorted(list(set(int(x) for x in lc.seen_ids)))
            return {tid: col for col, tid in enumerate(known_ids)}
        except (ValueError, TypeError):
            pass
    return {}


def get_contrast_color(bg_color):
    """Berekent of de tekstkleur zwart of wit moet zijn o.b.v. luminantie."""
    lum = 0.299 * bg_color.red() + 0.587 * bg_color.green() + 0.114 * bg_color.blue()
    return QColor("black") if lum > 130 else QColor("white")


# =====================================================================
# 1. ID HEADER WIDGET
# =====================================================================
class IDHeaderWidget(QWidget):
    def __init__(self, log_center_ref, parent=None):
        super().__init__(parent)
        self.lc = log_center_ref
        self.setFixedHeight(30)
        self.setMouseTracking(True)
        # ⚡ Luister direct naar kleur-updates, dwars door de anti-flicker heen!
        self.lc.session.subscribe("ui/id_version", lambda _: self.update())

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            painter.fillRect(self.rect(), QColor(Theme.BG_PANEL))

            lane_map = get_dynamic_lanes(self.lc)
            for t_id, col_idx in lane_map.items():
                x = Theme.LANE_START_X + (col_idx * Theme.LANE_SPACING)
                is_active = self.lc.session.get(f"ui/id/{t_id:02d}/active", True)
                color_idx = self.lc.session.get(f"ui/id/{t_id:02d}/color_idx", 0) or 0

                target_color = Theme.get_color(color_idx)
                if not is_active:
                    target_color = QColor(Theme.LANE_INACTIVE)

                painter.setPen(Qt.NoPen)
                painter.setBrush(target_color)
                rect = QRect(x - 12, 5, 24, 20)
                painter.drawRoundedRect(rect, 6, 6)

                text_color = get_contrast_color(target_color) if is_active else QColor(Theme.TEXT_DIM)
                painter.setPen(text_color)
                painter.setFont(QFont("Consolas", 9, QFont.Bold))
                painter.drawText(rect, Qt.AlignCenter, f"{t_id:02d}")
        finally:
            painter.end()

    def mouseMoveEvent(self, event):
        lane_map = get_dynamic_lanes(self.lc)
        for t_id, col_idx in lane_map.items():
            x = Theme.LANE_START_X + (col_idx * Theme.LANE_SPACING)
            rect = QRect(x - 12, 5, 24, 20)
            if rect.contains(event.position().toPoint()):
                name = self.lc.session.get(f"ui/id/{t_id:02d}/name", f"ID {t_id}")
                QToolTip.showText(event.globalPosition().toPoint(), name, self)
                return
        QToolTip.hideText()

    def mousePressEvent(self, event):
        lane_map = get_dynamic_lanes(self.lc)
        for t_id, col_idx in lane_map.items():
            x = Theme.LANE_START_X + (col_idx * Theme.LANE_SPACING)
            if abs(event.position().x() - x) < 15:
                self.show_context_menu(t_id, event.globalPosition().toPoint())
                break

    def show_context_menu(self, t_id, pos):
        menu = QMenu(self)
        menu.setStyleSheet(f"background: {Theme.BG_BLOCK}; color: {Theme.TEXT_MAIN};")
        for idx, (_, color_name) in enumerate(Theme.ID_COLORS):
            act = menu.addAction(color_name)
            act.triggered.connect(lambda _, tid=t_id, ci=idx: self.update_settings(tid, ci))
        menu.exec(pos)

    def update_settings(self, t_id, color_idx):
        self.lc.session.set([
            (f"ui/id/{t_id:02d}/color_idx", color_idx),
            ("ui/id_version", self.lc.session.get("ui/id_version", 0) + 1)
        ])
        # ⚡ Forceer een directe visuele update voor dit specifieke widget
        self.update()


# =====================================================================
# 2. VIRTUAL VIEWPORT
# =====================================================================
class VirtualLogView(QWidget):
    _tt_force_stealth_logging = True

    def __init__(self, log_center_ref, parent=None):
        super().__init__(parent)
        self.lc = log_center_ref
        self.logs = []
        self.scroll_index = 0
        self.is_tailing = True
        self._cached_lanes = {}
        self._cached_colors = {}
        self._active_ids = {}

        self._last_log_count = 0
        self._ignore_cursor = False
        self._is_scrubbing = False

        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setCursor(Qt.PointingHandCursor)
        self.system_prefixes = ("__init__", "ttss", "_ttss", "state_change")

    def setup_on_start(self):
        self.logs = self.lc.session["logs"].v
        self.lc.session.subscribe("ui/timeline/mode", lambda _: self._on_mode_changed())
        self.lc.session.subscribe("ui/id_version", lambda _: self.rebuild_render_cache())
        self.lc.session.subscribe("ui/timeline/cursor_ts", self._sync_from_timeline)

        self.rebuild_render_cache()

    def _on_mode_changed(self):
        self.is_tailing = self.lc.session.get("ui/timeline/mode") == "tailing"
        if self.is_tailing: self.scroll_index = 0
        self.update()

    def rebuild_render_cache(self):
        self._cached_lanes = get_dynamic_lanes(self.lc)
        self._active_ids = {}
        self._cached_colors = {}
        for tid in self._cached_lanes.keys():
            self._active_ids[tid] = self.lc.session.get(f"ui/id/{tid:02d}/active", True)
            self._cached_colors[tid] = self.lc.session.get(f"ui/id/{tid:02d}/color_idx", 0)
        self.update()

    def maintain_scroll_position(self):
        current_count = len(self.logs)
        if not self.is_tailing and self._last_log_count > 0:
            diff = current_count - self._last_log_count
            if diff > 0:
                self.scroll_index += diff
        self._last_log_count = current_count

    def _get_log_ts(self, log):
        ts = log.get('start@') or log.get('sys', {}).get('timestamp') or log.get('timestamp')
        try:
            val = float(ts)
            if val > 0: return val
        except (ValueError, TypeError):
            pass
        return 0.0

    def _update_timeline_cursor_from_index(self):
        if not self.logs: return
        idx = (len(self.logs) - 1) - self.scroll_index
        if 0 <= idx < len(self.logs):
            target_ts = self._get_log_ts(self.logs[idx])
            if target_ts > 0:
                self._ignore_cursor = True
                self.lc.session.set([
                    ("ui/timeline/cursor_ts", target_ts),
                    ("ui/timeline/freeze_ts", target_ts)
                ])
                self._ignore_cursor = False

    def _sync_from_timeline(self, updates=None):
        if self._ignore_cursor or self.is_tailing or not self.logs: return
        cursor_ts = self.lc.session.get("ui/timeline/cursor_ts", 0)
        if cursor_ts <= 0: return

        closest_idx = 0
        min_diff = float('inf')

        for i in range(len(self.logs) - 1, -1, -1):
            log_ts = self._get_log_ts(self.logs[i])
            if log_ts <= 0: continue

            diff = abs(log_ts - cursor_ts)
            if diff < min_diff:
                min_diff = diff
                closest_idx = (len(self.logs) - 1) - i
            elif diff > min_diff:
                break

        self.scroll_index = closest_idx
        if self.parent(): self.parent().sync_scrollbar_to_view()
        self.update()

    def wheelEvent(self, event):
        if not self.logs: return
        delta = event.angleDelta().y()
        if delta > 0:
            self.scroll_index = min(len(self.logs) - 1, self.scroll_index + 3)
        elif delta < 0:
            self.scroll_index = max(0, self.scroll_index - 3)

        if self.lc.session.get("ui/timeline/mode") != "history":
            self.lc.session["ui/timeline/mode"] = "history"

        self._update_timeline_cursor_from_index()
        if self.parent(): self.parent().sync_scrollbar_to_view()
        self.update()

    def mousePressEvent(self, event):
        total_count = len(self.logs)
        if total_count == 0: return

        if event.button() == Qt.LeftButton:
            click_y = event.position().y()
            rect = self.rect()
            idx = (total_count - 1) - self.scroll_index
            current_y = rect.bottom()

            while idx >= 0 and current_y > -200:
                log_dict = self.logs[idx]
                t_id = int(log_dict.get('id', 0))
                if self._active_ids.get(t_id, True):
                    h = self.calculate_height(log_dict)
                    top_y = current_y - h

                    if top_y <= click_y <= current_y:
                        target_ts = self._get_log_ts(log_dict)
                        if target_ts > 0:
                            self._ignore_cursor = True
                            self.lc.session.set([
                                ("ui/timeline/mode", "history"),
                                ("ui/timeline/cursor_ts", target_ts),
                                ("ui/timeline/freeze_ts", target_ts)
                            ])
                            self._ignore_cursor = False
                        return
                    current_y -= h
                idx -= 1

        elif event.button() == Qt.RightButton:
            self._is_scrubbing = True
            self._scrub_start_y = event.position().y()
            self._scrub_start_idx = self.scroll_index
            self.setCursor(Qt.SizeVerCursor)

    def mouseMoveEvent(self, event):
        if getattr(self, '_is_scrubbing', False):
            dy = event.position().y() - self._scrub_start_y
            idx_shift = int(dy / 5)
            new_idx = max(0, min(len(self.logs) - 1, self._scrub_start_idx - idx_shift))

            if new_idx != self.scroll_index:
                self.scroll_index = new_idx
                self.lc.session["ui/timeline/mode"] = "history"
                self._update_timeline_cursor_from_index()
                if self.parent(): self.parent().sync_scrollbar_to_view()
                self.update()

            QToolTip.showText(event.globalPosition().toPoint(), f"Fine-Tune Scroll: {new_idx} / {len(self.logs)}", self)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton:
            self._is_scrubbing = False
            self.setCursor(Qt.PointingHandCursor)
            QToolTip.hideText()

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            rect = self.rect()
            painter.fillRect(rect, QColor(Theme.BG_MAIN))

            painter.setRenderHint(QPainter.Antialiasing, False)
            for lane_tid, col_idx in self._cached_lanes.items():
                lane_x = Theme.LANE_START_X + (col_idx * Theme.LANE_SPACING)
                c_idx = self._cached_colors.get(lane_tid, 0)

                lane_color = QColor(Theme.get_color(c_idx))
                lane_color.setAlpha(70)
                painter.setPen(QPen(lane_color, 3))
                painter.drawLine(lane_x, 0, lane_x, rect.height())

            total_count = len(self.logs)
            if total_count == 0: return
            idx = (total_count - 1) - self.scroll_index
            current_y = rect.bottom()

            painter.setRenderHint(QPainter.Antialiasing, True)
            while idx >= 0 and current_y > -200:
                log_dict = self.logs[idx]
                t_id = int(log_dict.get('id', 0))
                if self._active_ids.get(t_id, True):
                    h = self.calculate_height(log_dict)
                    self._draw_log(painter, current_y - h, h, rect.width(), log_dict)
                    current_y -= h
                idx -= 1
        finally:
            painter.end()

    def calculate_height(self, log):
        enr = log.get('enriched', {})
        lines = log.get('log') or enr.get('ui_log_lines', [])
        caller = log.get('caller') or enr.get('calling_sparkle', '')
        header_h = 45 if caller else 30
        return Theme.GAP_HEIGHT + header_h + (len(lines) * 15)

    def _draw_log(self, painter, y, h, w, log):
        t_id = int(log.get('id', 0))
        c_idx = self._cached_colors.get(t_id, 0)
        base_color = Theme.get_color(c_idx)

        enr = log.get('enriched', {})
        sparkle = log.get('sparkle') or enr.get('display_sparkle', 'unknown_sparkle')
        tonic = log.get('source') or enr.get('tonic_name', 'UnknownTonic')
        caller = log.get('caller') or enr.get('calling_sparkle', '')
        lines = log.get('log') or enr.get('ui_log_lines', [])
        ts = self._get_log_ts(log)

        is_system = sparkle.startswith(self.system_prefixes)
        if is_system:
            bg_color = QColor(0, 30, 30)
            border_color = QColor(0, 100, 100, 150)
        else:
            bg_color = QColor(0, 50, 50)
            border_color = QColor(0, 255, 255, 100)

        bx = Theme.BLOCK_MARGIN
        by = y + Theme.GAP_HEIGHT
        bw = w - (Theme.BLOCK_MARGIN * 2)
        bh = h - Theme.GAP_HEIGHT - 2

        painter.setBrush(bg_color)
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(bx, by, bw, bh, 6, 6)

        painter.setBrush(base_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(bx, by, 6, bh, 3, 3)

        lane_x = Theme.LANE_START_X + (self._cached_lanes.get(t_id, 0) * Theme.LANE_SPACING)
        painter.setBrush(base_color)
        painter.drawEllipse(lane_x - 4, by - 4, 8, 8)

        tx = bx + 16
        ty = by + 16

        if ts > 0:
            milli = int((ts % 1) * 1000)
            ts_str = f"[{time.strftime('%H:%M:%S', time.localtime(ts))}.{milli:03d}]"
        else:
            ts_str = "[--:--:--.---]"

        painter.setFont(QFont("Consolas", 9))
        painter.setPen(QColor("#AAAAAA"))
        painter.drawText(tx, ty, ts_str)

        title_x = tx + 105
        painter.setFont(QFont("Consolas", 10, QFont.Bold))
        painter.setPen(QColor(Theme.TEXT_MAIN))
        painter.drawText(title_x, ty, f"{t_id:02d} : {tonic}.{sparkle}")

        if caller:
            ty += 15
            painter.setFont(QFont("Consolas", 8, QFont.StyleItalic))
            painter.setPen(QColor("#888888"))
            painter.drawText(title_x, ty, f"<- called by: {caller}")

        ty += 5
        painter.setFont(QFont("Consolas", 9))
        painter.setPen(QColor(Theme.TEXT_DIM))
        for line in lines:
            ty += 15
            painter.drawText(title_x, ty, str(line))


# =====================================================================
# 3. SCREEN LOGGER WIDGET
# =====================================================================
class ScreenLoggerWidget(ttPysideWidget):
    def __init__(self, parent=None, **kwargs):
        self.lc = LogCenter()
        self._is_syncing = False
        super().__init__(parent, **kwargs)

    def setup_ui(self):
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(0)
        self.id_header = IDHeaderWidget(self.lc, self)
        self.log_view = VirtualLogView(self.lc, self)

        self.scrollbar = QScrollBar(Qt.Vertical)
        self.scrollbar.setInvertedAppearance(True)
        self.scrollbar.valueChanged.connect(self.on_user_scroll)

        body = QHBoxLayout()
        body.addWidget(self.log_view, 1)
        body.addWidget(self.scrollbar)
        self.lay.addWidget(self.id_header)
        self.lay.addLayout(body)

    def ttse__on_start(self):
        self.log_view.setup_on_start()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.sync_heartbeat)
        self.timer.start(50)

    def on_user_scroll(self, val):
        if self._is_syncing: return

        if self.lc.session.get("ui/timeline/mode") != "history":
            self.lc.session["ui/timeline/mode"] = "history"

        self.log_view.scroll_index = val
        self.log_view.update()

        logs = self.log_view.logs
        if logs:
            real_idx = (len(logs) - 1) - val
            if 0 <= real_idx < len(logs):
                target_ts = self.log_view._get_log_ts(logs[real_idx])
                if target_ts > 0:
                    self.log_view._ignore_cursor = True
                    self.lc.session.set([
                        ("ui/timeline/cursor_ts", target_ts),
                        ("ui/timeline/freeze_ts", target_ts)
                    ])
                    self.log_view._ignore_cursor = False

    def sync_scrollbar_to_view(self):
        self._is_syncing = True
        total = len(self.log_view.logs)
        if self.scrollbar.maximum() != max(0, total - 1):
            self.scrollbar.setRange(0, max(0, total - 1))
        self.scrollbar.setValue(self.log_view.scroll_index)
        self._is_syncing = False

    def sync_heartbeat(self):
        total = len(self.log_view.logs)
        has_new_logs = (total != self.log_view._last_log_count)

        if not has_new_logs and not self.log_view.is_tailing:
            return

        self._is_syncing = True

        if self.scrollbar.maximum() != max(0, total - 1):
            self.scrollbar.setRange(0, max(0, total - 1))

        needs_update = False

        if self.log_view.is_tailing:
            if self.scrollbar.value() != 0:
                self.scrollbar.setValue(0)
            if self.log_view.scroll_index != 0:
                self.log_view.scroll_index = 0
            needs_update = has_new_logs
        else:
            self.log_view.maintain_scroll_position()
            if self.scrollbar.value() != self.log_view.scroll_index:
                self.scrollbar.setValue(self.log_view.scroll_index)
            needs_update = False

        self._is_syncing = False

        if needs_update:
            self.log_view.update()
            self.id_header.update()


```

## `File: tasktonic-visual-logger - old not in git\ui\main_window.py`
```python
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
```

## `File: tasktonic-visual-logger - old not in git\ui\__init__.py`
```python

```

## `File: tasktonic-visual-logger - old not in git\ui\timeline_viewer.py`
```python
import time
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QPushButton, QWidget, QLabel
from PySide6.QtCore import Qt, QRect, QPoint, QSize
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QCursor, QIcon
from TaskTonic.ttTonicStore import ttPysideWidget
from TaskTonic.ttTimer import ttTimerRepeat
from theme import Theme
from log_center import LogCenter


# =====================================================================
# 1. PIXEL-PERFECT LABELS (With Floating Cursor)
# =====================================================================
class TimelineLabelsWidget(QWidget):
    """Draws ticks, timestamps, and the floating cursor label."""

    def __init__(self, is_top=False, parent=None):
        super().__init__(parent)
        self.is_top = is_top
        self.timestamps = [""] * 9
        self.cursor_ratio = -1.0
        self.cursor_text = ""
        self.setFixedHeight(25)
        self.font = QFont("Consolas", 10)

    def update_data(self, timestamps, cursor_ratio=-1.0, cursor_text=""):
        self.timestamps = timestamps
        self.cursor_ratio = cursor_ratio
        self.cursor_text = cursor_text
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.TextAntialiasing)
        w = self.width()

        for i in range(9):
            x = int((i / 8) * (w - 1))

            painter.setPen(QPen(QColor("#777"), 1))
            tick_y = self.height() - 6 if self.is_top else 0
            painter.drawLine(x, tick_y, x, tick_y + 5)

            painter.setPen(QPen(QColor(Theme.TEXT_DIM), 1))
            painter.setFont(self.font)
            text = self.timestamps[i]

            if i == 0:
                align = Qt.AlignLeft;
                tx = 0
            elif i == 8:
                align = Qt.AlignRight;
                tx = x - 100
            else:
                align = Qt.AlignCenter;
                tx = x - 50

            text_rect = QRect(tx, 6 if not self.is_top else 0, 100, 18)
            painter.drawText(text_rect, align, text)

        if not self.is_top and 0.0 <= self.cursor_ratio <= 1.0 and self.cursor_text:
            cx = int(self.cursor_ratio * (w - 1))

            painter.setFont(QFont("Consolas", 9, QFont.Bold))
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(self.cursor_text) + 12

            box_rect = QRect(int(cx - (tw / 2)), 0, tw, 18)

            if box_rect.left() < 0: box_rect.moveLeft(0)
            if box_rect.right() > w: box_rect.moveRight(w)

            painter.setBrush(QColor("#FFCC00"))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(box_rect, 4, 4)
            painter.setPen(QColor("black"))
            painter.drawText(box_rect, Qt.AlignCenter, self.cursor_text)


# =====================================================================
# 2. TOTAL TIMELINE (Interactive Map)
# =====================================================================
class TotalTimelineWidget(ttPysideWidget):
    _tt_force_stealth_logging = True

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lc = None
        self._cached_colors = {}
        self._active_ids = {}
        self._is_dragging = False
        self.setCursor(QCursor(Qt.PointingHandCursor))

    def setup_ui(self):
        self.setFixedHeight(45)

    def ttse__on_start(self):
        self.lc = LogCenter()
        self.lc.session.subscribe("ui/id_version", self.ttse__sync_cache)
        self.ttse__sync_cache()

    def ttse__sync_cache(self, _=None):
        self._active_ids = {}
        self._cached_colors = {}

        if hasattr(self.lc, 'seen_ids'):
            for tid in self.lc.seen_ids:
                try:
                    t_int = int(tid)
                    self._active_ids[t_int] = self.lc.session.get(f"ui/id/{t_int:02d}/active", True)
                    self._cached_colors[t_int] = self.lc.session.get(f"ui/id/{t_int:02d}/color_idx", 0)
                except (ValueError, TypeError):
                    pass
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_dragging = True
            self._handle_seek(event.position().x())

    def mouseMoveEvent(self, event):
        if self._is_dragging:
            self._handle_seek(event.position().x())

    def mouseReleaseEvent(self, event):
        self._is_dragging = False

    def _handle_seek(self, x_pos):
        now = time.time()
        base_ts = getattr(self.lc, 'base_ts', now)
        total_duration = max(now - base_ts, 1.0)

        ratio = max(0.0, min(1.0, x_pos / self.width()))
        target_ts = base_ts + (ratio * total_duration)

        self.lc.session.set([
            ("ui/timeline/mode", "history"),
            ("ui/timeline/freeze_ts", target_ts)
        ])

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            rect = self.rect().adjusted(0, 0, -1, -1)
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setBrush(QColor(Theme.BG_BLOCK))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect, 6, 6)

            metrics = self.lc.session["metrics_100ms"].v
            now = time.time()
            base_ts = getattr(self.lc, 'base_ts', now)
            total_duration = max(now - base_ts, 0.1)
            total_buckets = int(total_duration * 10)

            bw = rect.width() / max(total_buckets, 1)
            mv = max([sum(b.values()) for b in metrics[-1000:]] + [1])

            painter.setRenderHint(QPainter.Antialiasing, False)
            painter.setPen(QPen(QColor(0, 255, 255, 80), 1))
            painter.drawLine(rect.left(), rect.bottom() - 4, rect.right(), rect.bottom() - 4)

            for i, bucket in enumerate(metrics):
                x = rect.left() + int(i * bw)
                y_off = rect.bottom() - 4
                for tid_s, val in bucket.items():
                    try:
                        t_int = int(tid_s)
                        is_active = self.lc.session.get(f"ui/id/{t_int:02d}/active", True)
                        if is_active and val > 0:
                            c_idx = self.lc.session.get(f"ui/id/{t_int:02d}/color_idx", 0)
                            # ⚡ Forceer minimaal 2 pixels zichtbaarheid als er sparkles zijn
                            h = max(2, int((val / mv) * (rect.height() - 10)))
                            painter.fillRect(QRect(x, y_off - h, max(1, int(bw + 1)), h),
                                             Theme.get_color(c_idx))
                            y_off -= h
                    except (ValueError, TypeError):
                        pass

            painter.setRenderHint(QPainter.Antialiasing, True)
            zoom = self.lc.session.get("ui/timeline/zoom_sec", 30)
            mode = self.lc.session.get("ui/timeline/mode", "tailing")

            if mode == "tailing":
                center_ts = now - (zoom / 2)
            else:
                center_ts = self.lc.session.get("ui/timeline/freeze_ts", now)

            hw = (zoom / total_duration) * rect.width()
            hx = ((center_ts - (zoom / 2) - base_ts) / total_duration) * rect.width()
            hx = max(0, min(rect.width() - hw, hx))

            painter.setBrush(QColor(0, 255, 255, 50))
            painter.setPen(QPen(QColor(0, 255, 255, 200), 2))
            painter.drawRoundedRect(QRect(int(rect.left() + hx), rect.top(), int(hw), rect.height()), 4, 4)

            cursor_ts = self.lc.session.get("ui/timeline/cursor_ts", 0)
            if cursor_ts > 0:
                cx = rect.left() + (((cursor_ts - base_ts) / total_duration) * rect.width())
                painter.setPen(QPen(QColor("#FFCC00"), 1))
                painter.drawLine(int(cx), rect.top(), int(cx), rect.bottom())

        finally:
            painter.end()


# =====================================================================
# 3. MICRO TIMELINE (Zoom View)
# =====================================================================
class MicroTimelineWidget(ttPysideWidget):
    _tt_force_stealth_logging = True

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lc = None
        self.metrics = []
        self._colors = {}
        self._active = {}
        self._is_dragging = False
        self.setCursor(QCursor(Qt.CrossCursor))

    def setup_ui(self):
        self.setFixedHeight(95)

    def ttse__on_start(self):
        self.lc = LogCenter()
        self.metrics = self.lc.session["metrics_100ms"].v
        self.lc.session.subscribe("ui/id_version", self.ttse__sync)
        self.ttse__sync()

    def ttse__sync(self, _=None):
        self._active = {}
        self._colors = {}

        if hasattr(self.lc, 'seen_ids'):
            for tid in self.lc.seen_ids:
                try:
                    t_int = int(tid)
                    self._active[t_int] = self.lc.session.get(f"ui/id/{t_int:02d}/active", True)
                    self._colors[t_int] = self.lc.session.get(f"ui/id/{t_int:02d}/color_idx", 0)
                except (ValueError, TypeError):
                    pass
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_dragging = True
            self._update_cursor(event.position().x())

    def mouseMoveEvent(self, event):
        if self._is_dragging:
            self._update_cursor(event.position().x())

    def mouseReleaseEvent(self, event):
        self._is_dragging = False

    def _update_cursor(self, x_pos):
        now = time.time()
        zoom = self.lc.session.get("ui/timeline/zoom_sec", 30)
        mode = self.lc.session.get("ui/timeline/mode", "tailing")
        base_ts = getattr(self.lc, 'base_ts', now)

        if mode == "tailing":
            start_ts = now - zoom
        else:
            center_ts = self.lc.session.get("ui/timeline/freeze_ts", now)
            center_ts = max(base_ts, min(now, center_ts))
            start_ts = center_ts - (zoom / 2)

        ratio = max(0.0, min(1.0, x_pos / self.width()))
        target_ts = start_ts + (ratio * zoom)

        self.lc.session.set([
            ("ui/timeline/cursor_ts", target_ts),
            ("ui/timeline/mode", "history"),
            ("ui/timeline/freeze_ts", start_ts + (zoom / 2))
        ])

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            rect = self.rect().adjusted(0, 0, -1, -1)
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setBrush(QColor(0, 30, 30))
            painter.setPen(QPen(QColor(0, 255, 255, 120), 1))
            painter.drawRoundedRect(rect, 6, 6)

            now = time.time()
            base_ts = getattr(self.lc, 'base_ts', now)
            zoom = self.lc.session.get("ui/timeline/zoom_sec", 30)
            mode = self.lc.session.get("ui/timeline/mode", "tailing")

            if mode == "tailing":
                center_ts = now - (zoom / 2)
            else:
                center_ts = self.lc.session.get("ui/timeline/freeze_ts", now)
                center_ts = max(base_ts, min(now, center_ts))

            start_ts = center_ts - (zoom / 2)
            start_idx = int((start_ts - base_ts) * 10)
            nb = int(zoom * 10)
            bw = rect.width() / nb

            baseline_y = rect.bottom() - 2

            mv = 1
            for i in range(nb):
                idx = start_idx + i
                if 0 <= idx < len(self.metrics):
                    mv = max(mv, sum(self.metrics[idx].values()))

            painter.setRenderHint(QPainter.Antialiasing, False)
            painter.setPen(QPen(QColor(0, 255, 255, 120), 1))
            painter.drawLine(rect.left(), baseline_y, rect.right(), baseline_y)

            for i in range(nb):
                x = rect.left() + int(i * bw)
                d_idx = start_idx + i

                if 0 <= d_idx < len(self.metrics):
                    bucket = self.metrics[d_idx]
                    y_off = baseline_y
                    active_sum = sum(bucket.values())

                    if active_sum > 0:
                        # ⚡ Forceer minimaal 2 pixels zichtbaarheid voor de oranje peak
                        ph = max(2, int((active_sum / mv) * (baseline_y - rect.top() - 5)))
                        painter.fillRect(QRect(x, baseline_y - ph, max(1, int(bw + 1)), 3), QColor("#FFA500"))

                    for tid_s, val in bucket.items():
                        try:
                            t_int = int(tid_s)
                            is_active = self.lc.session.get(f"ui/id/{t_int:02d}/active", True)
                            if is_active and val > 0:
                                c_idx = self.lc.session.get(f"ui/id/{t_int:02d}/color_idx", 0)
                                # ⚡ Forceer minimaal 2 pixels zichtbaarheid per ID kleur
                                h = max(2, int((val / mv) * (baseline_y - rect.top() - 5)))
                                painter.fillRect(QRect(x, y_off - h, max(1, int(bw + 1)), h),
                                                 Theme.get_color(c_idx))
                                y_off -= h
                        except (ValueError, TypeError):
                            pass

            cursor_ts = self.lc.session.get("ui/timeline/cursor_ts", 0)
            if start_ts <= cursor_ts <= (start_ts + zoom):
                cx = rect.left() + (((cursor_ts - start_ts) / zoom) * rect.width())
                painter.setRenderHint(QPainter.Antialiasing, True)
                painter.setPen(QPen(QColor("#FFCC00"), 2))
                painter.drawLine(int(cx), rect.top(), int(cx), rect.bottom())

        finally:
            painter.end()


# =====================================================================
# 4. MAIN CONTAINER
# =====================================================================
class TimelineContainer(ttPysideWidget):
    _tt_force_stealth_logging = True
    ZOOM_STEPS = [30, 60, 120, 300, 600, 1800, 3600, 14400]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lc = LogCenter()

    def setup_ui(self):
        self.setFixedHeight(235)
        self.main_lay = QVBoxLayout(self)
        self.main_lay.setContentsMargins(10, 5, 10, 5)
        self.main_lay.setSpacing(6)

        CTRL_W = 40

        # 1. Top Labels
        r1 = QHBoxLayout()
        r1.setSpacing(6)
        s1 = QWidget()
        s1.setFixedWidth(CTRL_W)
        r1.addWidget(s1)
        self.top_labels = TimelineLabelsWidget(is_top=True)
        r1.addWidget(self.top_labels)
        self.main_lay.addLayout(r1)

        # 2. Total Bar + Play/Pause SVG Button
        r2 = QHBoxLayout()
        r2.setSpacing(6)
        self.btn_play = QPushButton()
        self.btn_play.setIcon(QIcon("ui/icons/play.svg"))
        self.btn_play.setIconSize(QSize(20, 20))
        self.btn_play.setFixedSize(CTRL_W, 45)
        self.btn_play.setStyleSheet("background:#222; border:1px solid #444; border-radius:6px;")
        self.btn_play.setCursor(Qt.PointingHandCursor)
        r2.addWidget(self.btn_play)

        self.total_view = TotalTimelineWidget()
        r2.addWidget(self.total_view)
        self.main_lay.addLayout(r2)

        # 3. Micro Bar + SVG Zoom Controls
        r3 = QHBoxLayout()
        r3.setSpacing(6)
        ctrl = QVBoxLayout()
        ctrl.setSpacing(2)
        ctrl.setContentsMargins(0, 0, 0, 0)

        self.b_in = QPushButton()
        self.b_in.setIcon(QIcon("ui/icons/zoom_in.svg"))
        self.b_in.setIconSize(QSize(20, 20))

        self.b_out = QPushButton()
        self.b_out.setIcon(QIcon("ui/icons/zoom_out.svg"))
        self.b_out.setIconSize(QSize(20, 20))

        self.z_lbl = QLabel("30s")
        self.z_lbl.setStyleSheet("color: white; font-family: Consolas; font-size: 11px; font-weight: bold;")
        self.z_lbl.setFixedSize(CTRL_W, 20)
        self.z_lbl.setAlignment(Qt.AlignCenter)

        style = "background: #222; border: 1px solid #444; border-radius: 6px;"
        for w in [self.b_in, self.b_out]:
            w.setStyleSheet(style)
            w.setFixedSize(CTRL_W, 26)
            w.setCursor(Qt.PointingHandCursor)

        ctrl.addWidget(self.b_in)
        ctrl.addWidget(self.z_lbl)
        ctrl.addWidget(self.b_out)
        r3.addLayout(ctrl)

        self.micro_view = MicroTimelineWidget()
        r3.addWidget(self.micro_view)
        self.main_lay.addLayout(r3)

        # 4. Bottom Labels (with Floating Yellow Box)
        r4 = QHBoxLayout()
        r4.setSpacing(6)
        s4 = QWidget()
        s4.setFixedWidth(CTRL_W)
        r4.addWidget(s4)
        self.bot_labels = TimelineLabelsWidget(is_top=False)
        r4.addWidget(self.bot_labels)
        self.main_lay.addLayout(r4)

    def ttse__on_start(self):
        self.lc.session["ui/timeline/mode"] = "tailing"
        self.lc.session["ui/timeline/cursor_ts"] = 0.0
        self.tm_master = ttTimerRepeat(seconds=0.1, name="tm_master")

    def ttse__on_tm_master(self, _):
        now = time.time()

        mode = self.lc.session.get("ui/timeline/mode", "tailing")
        if mode == "tailing":
            self.btn_play.setIcon(QIcon("ui/icons/play.svg"))
        else:
            self.btn_play.setIcon(QIcon("ui/icons/pause.svg"))

        self.total_view.update()
        self.micro_view.update()

        base_ts = getattr(self.lc, 'base_ts', now)
        total_duration = max(now - base_ts, 0.1)

        top_ts = [
            f"{time.strftime('%H%M%S', time.localtime(base_ts + (i * total_duration / 8)))}.{int(((base_ts + (i * total_duration / 8)) % 1) * 1000):03d}"
            for i in range(9)]
        self.top_labels.update_data(top_ts)

        zoom = self.lc.session.get("ui/timeline/zoom_sec", 30)

        if mode == "tailing":
            center_ts = now - (zoom / 2)
        else:
            center_ts = self.lc.session.get("ui/timeline/freeze_ts", now)
            center_ts = max(base_ts, min(now, center_ts))

        start_ts = center_ts - (zoom / 2)
        bot_ts = [
            f"{time.strftime('%H%M%S', time.localtime(start_ts + (i * zoom / 8)))}.{int(((start_ts + (i * zoom / 8)) % 1) * 1000):03d}"
            for i in range(9)]

        cursor_ts = self.lc.session.get("ui/timeline/cursor_ts", 0)
        c_ratio = -1.0
        c_text = ""
        if cursor_ts > 0 and start_ts <= cursor_ts <= (start_ts + zoom):
            c_ratio = (cursor_ts - start_ts) / zoom
            struct = time.localtime(cursor_ts)
            c_text = f"{time.strftime('%H:%M:%S', struct)}.{int((cursor_ts % 1) * 1000):03d}"

        self.bot_labels.update_data(bot_ts, cursor_ratio=c_ratio, cursor_text=c_text)

    def ttqt__btn_play__clicked(self):
        mode = self.lc.session.get("ui/timeline/mode", "tailing")
        now = time.time()
        zoom = self.lc.session.get("ui/timeline/zoom_sec", 30)

        if mode == "tailing":
            self.lc.session.set([
                ("ui/timeline/mode", "history"),
                ("ui/timeline/freeze_ts", now - (zoom / 2)),
                ("ui/timeline/cursor_ts", now)
            ])
        else:
            self.lc.session.set([
                ("ui/timeline/mode", "tailing"),
                ("ui/timeline/cursor_ts", 0.0)
            ])

    def ttqt__b_in__clicked(self):
        self._adj(-1)

    def ttqt__b_out__clicked(self):
        self._adj(1)

    def _adj(self, d):
        cur = self.lc.session.get("ui/timeline/zoom_sec", 30)
        idx = self.ZOOM_STEPS.index(cur)
        val = self.ZOOM_STEPS[max(0, min(len(self.ZOOM_STEPS) - 1, idx + d))]
        self.lc.session["ui/timeline/zoom_sec"] = val
        self.z_lbl.setText(f"{val}s" if val < 60 else f"{val // 60}m")

```

## `File: tasktonic-visual-logger - old not in git\ui\theme.py`
```python
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

```

## `File: tasktonic-visual-logger - old not in git\testing\test_log_center.py`
```python
import time
from TaskTonic import ttFormula
from TaskTonic.ttTonicStore import ttDistiller
from log_center import LogCenter


class LogCenterTestFormula(ttFormula):
    def creating_formula(self):
        return {
            'tasktonic/log/to': 'off',  # No output from the framework itself
            'tasktonic/log/default': 'stealth',
        }

    def creating_main_catalyst(self):
        self.distiller = ttDistiller(name='tt_main_catalyst')

    def creating_starting_tonics(self):
        self.lc = LogCenter()


def test_log_center_flow():
    app = LogCenterTestFormula()
    distiller = app.distiller
    lc = app.lc

    print("\n--- Starting LogCenter Test ---")

    try:
        # 1. Startup phase
        status = distiller.sparkle(timeout=.1, till_sparkle_in=['_ttinternal_state_change_to'])
        print(distiller.stat_print(status))

        assert lc.get_current_state_name() == 'listening', "LogCenter must start in 'listening' state"
        print("✅ Starts cleanly in [listening] state\n")

        # 2. Fire 3 dummy logs: Simulate a FULL lifecycle of Tonic ID 99
        t0 = time.time()

        # Log 1: Birth (sys.created = True)
        dummy_log_1 = {
            'id': 99,
            'start@': t0,
            'sys': {'created': True},
            'enriched': {'tonic_name': 'LifecycleTest', 'finishing': False}
        }
        # Log 2: Normal activity
        dummy_log_2 = {
            'id': 99,
            'start@': t0 + 0.05,
            'sys': {},
            'enriched': {'tonic_name': 'LifecycleTest', 'finishing': False}
        }
        # Log 3: Death (enriched.finishing = True)
        dummy_log_3 = {
            'id': 99,
            'start@': t0 + 0.1,
            'sys': {},
            'enriched': {'tonic_name': 'LifecycleTest', 'finishing': True}
        }

        lc.ttse__new_log(dummy_log_1)
        lc.ttse__new_log(dummy_log_2)
        lc.ttse__new_log(dummy_log_3)

        # 3. Process queue until 'buffering'
        status = distiller.sparkle(timeout=1, till_state_in=['buffering'])
        assert lc.get_current_state_name() == 'buffering', "Must be in 'buffering' state now"
        print("✅ Switches directly to [buffering] after the first log")

        # 4. Wait for the 100ms timer batch
        status = distiller.sparkle(timeout=1.5, till_state_in=['listening'])

        duration = status.get("end@", 0) - status.get("start@", 0)
        assert 0.19 < duration < 0.21, f"Buffering took {duration}s, expected ~0.20s"
        print(f"✅ Buffering took exactly 2 periods of 100ms")

        assert len(lc.store_logs) == 3, "There must be 3 logs in RAM"
        print("✅ 3 logs successfully recorded in RAM")

        last_append = lc.session.get("last_append")
        assert last_append == (1, 2), f"Expected (1, 2) but got {last_append}"
        print("✅ Timer fired and Store correctly triggered the batch (1, 2)!\n")

        # ==========================================================
        # 5. THE NEW HISTORY INDEX TEST
        # ==========================================================
        history = lc.session.at("ui/history").v

        print(history)

        assert len(history) == 1, f"History should contain exactly 1 finished run, found {len(history)}"

        run_info = history[0]
        assert run_info['tonic_id'] == 99, "Tonic ID was not stored correctly"
        assert run_info['name'] == 'LifecycleTest', "Tonic name was not stored correctly"
        assert 'run_id' in run_info, "Run ID is missing in history!"
        assert run_info['start_log_idx'] == 0, "The start index must be 0 (first log in RAM)"
        assert run_info['end_log_idx'] == 2, "The end index must be 2 (third log in RAM)"

        print("✅ History Index successfully updated after Tonic death!")
        print(
            f"   -> Stored run: {run_info['run_id']} (Duration: {(run_info['end_ts'] - run_info['start_ts']) * 1000:.1f}ms)\n")

    finally:
        # 6. Clean up
        lc.finish()
        distiller.finish_distiller()
        print("🎉 Test execution finished and cleaned up.")
```

