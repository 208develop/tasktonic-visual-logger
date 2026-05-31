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

## `File: tasktonic-visual-logger\main.py`

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

## `File: tasktonic-visual-logger\ui\log_viewer.py`

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

## `File: tasktonic-visual-logger\ui\main_window.py`

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

## `File: tasktonic-visual-logger\ui\__init__.py`

```python

```

## `File: tasktonic-visual-logger\ui\timeline_viewer.py`

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

