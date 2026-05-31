import time
from TaskTonic import ttTonic, ttTimerRepeat, ttLog
from TaskTonic.ttTonicStore import DictSocketHandler


class LogSession(ttTonic):

    def __init__(self, store, **kwargs):
        super().__init__(**kwargs, log_mode=ttLog.STEALTH)
        self.log_records = []
        self._store = store
        self._net = None

        # Buffering and metrics variables for timeline generation
        self.buffering_start_idx = 0
        self.base_ts = None
        self.seen_ids = set()
        self.active_runs = {}
        self.store_metrics = None
        self.tm_batch = None

    def ttse__on_start(self):
        # Initialize the baseline arrays and dictionaries for this session
        self._store.set((
            ('logs', []),
            ('metrics_100ms', []),
            ('live_count', 0),
            ('last_append', (0, 0)),
            ('ui/fast_access/id', {}),   # 2x reference to ui/id/# store for fast access by id and lane
            ('ui/fast_access/lane', {}), #  !! exclude from disk storage !!
        ))

        self._logs = self._store.at('logs').v
        self.store_metrics = self._store.at('metrics_100ms').v

        port = self.ledger.formula['app_data/startup_args/port'].v
        self._net = DictSocketHandler(as_server=True, host='localhost', port=port)
        self.log("New LogSession initialized and waiting for log connection.")

        self._store.subscribe('status', self.ttse__on_status_changed)

        # create batch timer and stop it running
        self.tm_batch = ttTimerRepeat(seconds=0.1, name="tm_batch")
        self.tm_batch.stop()

        # Start in listening state to await incoming bursts
        self.to_state('listening')

    def ttse__on_status_changed(self, _):
        status = self._store.get('status')

        if status == 'closing':
            self.log("Received 'closing' intent from UI via store. Shutting down backend.")
            self.base.ttsc__remove_session(self._store)

    def ttse__on_socket_connected(self, addr):
        self._store['status'] = 'connected'
        self._store['session address'] = addr
        self._store['ui/timeline/mode'] = self._store.get('ui/timeline/default_mode', 'tailing')

        if hasattr(self.base, 'ttse__on_session_connected'):
            self.base.ttse__on_session_connected()
        self.log(f"Connected to: {addr}")
        self.log(f"Store {self._store.dumps()}")

    def ttse__on_disconnected(self):
        self._store['status'] = 'disconnected'
        self.to_state('disconnected')

        # Freeze the UI by setting the timeline mode to history
        ui_store = self._store.at('ui/timeline')
        ui_store['mode'] = 'history'

        self.log("LogSession IP connection lost. UI switched to history mode.")


    def ttse_listening__on_socket_data(self, log):
        self._process_and_enrich_log(log)
        self._store['last_append'] = (len(self._logs) - 1, 1)
        self.to_state('buffering')

    def ttse_buffering__on_enter(self):
        # Group incoming logs for 100ms before notifying the UI
        self.tm_batch.restart()
        self.buffering_start_idx = len(self._logs)

    def ttse_buffering__on_socket_data(self, log):
        self._process_and_enrich_log(log)

    def ttse_buffering__on_tm_batch(self, tinfo):
        count = len(self._logs) - self.buffering_start_idx
        if count <= 0:
            self.to_state('listening')
            return

        self._store['last_append'] = (self.buffering_start_idx, count)
        self.buffering_start_idx = len(self._logs)

    def ttse_buffering__on_exit(self):
        self.tm_batch.stop()

    def ttse_disconnected__on_enter(self):
        pass # disconnected state created


    # helper
    def _process_and_enrich_log(self, log_dict):
        # ==========================================
        # 1. Session Log Check
        # ==========================================
        if 'id' not in log_dict:
            if log_dict.get('start_new_session'):
                self._store.set((
                    ('name', log_dict.get('project', 'Unknown Project')),
                    ('start@', log_dict.get('start@', time.time())),
                    ('logger_version', log_dict.get('logger_version', 0)),
                ))
            return

        # ==========================================
        # 2. Base Container Setup
        # ==========================================
        l_id = log_dict['id']
        ts = log_dict.get('start@', time.time())

        enriched = {
            'ui_log_lines': [],
            'marker': [],
            'probe': None,
            'color_override': None,
            'is_system': False,
            'is_finishing': False,
            'tonic_name': f"ID_{l_id:02d}",
            'display_sparkle': '',
            'source_id': log_dict.get('source_id'),
            'caller': log_dict.get('source', ''),
            'current_state': '',
            'lifecycle_phase': None,
        }

        # ==========================================
        # 3. Parse Meta & Backward Compat Flags
        # ==========================================
        meta = log_dict.get('meta', {})
        if meta:
            enriched['color_override'] = meta.get('lane_color')
            enriched['marker'] = meta.get('marker', [])
            enriched['probe'] = meta.get('probe')

        # Vang oude flags op (zoals in jouw log voor ID 2: 'log_color_green')
        for flag in log_dict.get('flags', []):
            if isinstance(flag, str) and flag.startswith('log_color_'):
                enriched['color_override'] = flag.replace('log_color_', '')

        # ==========================================
        # 4. Parse Lifecycle (Nieuwe Structuur)
        # ==========================================
        lc = log_dict.get('lifecycle', {})
        if lc:
            phase = lc.get('phase')

            enriched['lifecycle_phase'] = phase

            if phase == 'creation':
                while len(self.log_records) <= l_id:
                    self.log_records.append(None)
                self.log_records[l_id] = {
                    'name': lc.get('name', enriched['tonic_name']),
                    'type': lc.get('type', 'Unknown'),
                    'states': lc.get('states', []),
                    'current_state_idx': -1
                }

            elif phase == 'new_state':
                if l_id < len(self.log_records) and self.log_records[l_id]:
                    new_idx = lc.get('new_state')
                    if new_idx is not None:
                        self.log_records[l_id]['current_state_idx'] = new_idx
                        states_list = self.log_records[l_id]['states']
                        if 0 <= new_idx < len(states_list):
                            enriched['display_sparkle'] = f"TO STATE [{states_list[new_idx]}]"

            elif phase in ['finishing', 'finished']:
                enriched['is_finishing'] = True

        # Haal de echte naam op uit de lookup table
        blueprint = self.log_records[l_id] if l_id < len(self.log_records) and self.log_records[l_id] else None
        if blueprint:
            enriched['tonic_name'] = blueprint['name']

        # ==========================================
        # 5. Parse Sparkle / Exec Context
        # ==========================================
        sparkle = log_dict.get('sparkle')
        if sparkle:
            enriched['is_system'] = sparkle.startswith('_ttss') or sparkle.startswith('ttss')
            if not enriched['display_sparkle'] and sparkle != '_ttinternal_state_change_to':
                enriched['display_sparkle'] = sparkle

            st = log_dict.get('state',
                              self.log_records[l_id]['current_state_idx']
                              if sparkle in ['ttse__on_enter', 'ttse__on_exit'] else None)
            
            if st is not None:
                states_list = self.log_records[l_id]['states']
                enriched['current_state'] = states_list[st] if 0 <= st < len(states_list) else f'{st}'

        # ==========================================
        # 6. Parse Inline Colors (##red)
        # ==========================================
        import re
        color_pattern = re.compile(r"^##([a-zA-Z]+)(.*)")

        for raw_line in log_dict.get('log', []):
            line_str = str(raw_line)
            match = color_pattern.match(line_str)
            if match:
                enriched['ui_log_lines'].append((match.group(1).lower(), match.group(2).strip()))
            else:
                enriched['ui_log_lines'].append((None, line_str))

        # ==========================================
        # 7. Opslaan & ID Updates
        # ==========================================
        log_dict['enriched'] = enriched
        self._logs.append(log_dict)

        if self.base_ts is None:
            self.base_ts = ts

        # Zorg dat de UI weet dat er een nieuw ID is
        if l_id not in self.seen_ids:
            self.seen_ids.add(l_id)

            b_type = blueprint['type'] if blueprint and 'type' in blueprint else "Unknown"

            # Vertaal de flag naar een start-kleur
            start_color_idx = 0
            if enriched.get('color_override'):
                c_str = enriched['color_override'].lower()
                c_map = {'white': 0, 'green': 1, 'blue': 2, 'orange': 3, 'pink': 4, 'purple': 5, 'cyan': 6, 'yellow': 7}
                start_color_idx = c_map.get(c_str, 0)

            with self._store.group():
                new_id_lane = self._store.at('ui/id_lanes').append()
                lane_nr = int(new_id_lane.key[1:])
                new_id_lane.set([
                    ("id", f'{l_id:02d}'),
                    ("lane_nr", lane_nr),
                    ("active", True),
                    ("color_idx", start_color_idx),
                    ("name", enriched['tonic_name']),
                    ("type", b_type),
                ])
                # self._store[f'ui/id_ref/{l_id}'] = new_id_lane.path
                self._store['ui/fast_access/id'].v[int(l_id)] = new_id_lane
                self._store['ui/fast_access/lane'].v[int(lane_nr)] = new_id_lane


        # ==========================================
        # 8. Timeline Binning (Voor de grafiekjes)
        # ==========================================
        bin_idx = int((ts - self.base_ts) * 10)
        if bin_idx >= 0:
            while bin_idx >= len(self.store_metrics):
                self.store_metrics.append({})

            bucket = self.store_metrics[bin_idx]
            bucket[l_id] = bucket.get(l_id, 0) + 1
