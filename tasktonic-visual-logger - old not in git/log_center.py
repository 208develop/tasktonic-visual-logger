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