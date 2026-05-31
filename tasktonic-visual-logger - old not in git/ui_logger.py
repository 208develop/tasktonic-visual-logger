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
