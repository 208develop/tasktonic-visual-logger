import enum
from TaskTonic import ttTonic, ttTimerRepeat
from TaskTonic.internals import Store


class LogStreamMode(enum.IntEnum):
    OFF = 0
    DIRECT = 1
    GROUPED = 2


# Meervoudige overerving: ttTonic (State Machine) + ttStore (Data Store)
class LogCenter(ttTonic, Store):
    """
    Central Log Service and State Store.
    Manages session settings and distributes incoming log streams via a burst-optimized State Machine.
    """
    _tt_is_service = "log_center"
    _tt_base_essence = True
    _tt_force_stealth_logging = True
    
    def __init__(self, *args, log_sparkle=None, log_stream_mod=LogStreamMode.OFF, **kwargs):
        ttTonic.__init__(self, *args, **kwargs)
        Store.__init__(self)
        
        # Geoptimaliseerde opsplitsing per type abonnee
        self.subs_direct = {}
        self.subs_grouped = {}
        self.log_buffer = []
        self.tm_burst = None

    def _init_post_action(self):
        super()._init_post_action()
        
        if not self.exists("session"):
            with self.group(notify=False):
                self.set([("session/name", "test")])
                for lane_id in range(1, 9):
                    self.set((
                        (f"session/ui/id/{lane_id:02d}", {}),
                        (f"session/ui/id/{lane_id:02d}/active", True),
                        (f"session/ui/id/{lane_id:02d}/color_idx", 0),
                    ))

        # Start de state machine in rust
        self.to_state('no_subscribers')
        self.log(f"Log Center initialized\n{self.dumps()}")

    def _tt_init_service_base(self, base, log_sparkle=None, log_stream_mod=LogStreamMode.OFF, **kwargs):
        if base is None or log_sparkle is None: return
        self.ttsc__update_subscription(base, log_sparkle, log_stream_mod)
        
    def ttsc__update_subscription(self, base, log_sparkle, log_stream_mod):
        # Verwijder veilig uit beide takken
        self.subs_direct.pop(base.id, None)
        self.subs_grouped.pop(base.id, None)
        
        # Uitschrijven
        if log_stream_mod == LogStreamMode.OFF:
            if not self.subs_direct and not self.subs_grouped:
                if self.tm_burst:
                    self.tm_burst.stop()
                self.to_state('no_subscribers')
            return
            
        # Inschrijven in de juiste tak
        if isinstance(log_sparkle, str):
            log_sparkle = getattr(base, log_sparkle)

        if log_stream_mod == LogStreamMode.DIRECT:
            self.subs_direct[base.id] = {'base': base, 'sparkle': log_sparkle}
        elif log_stream_mod == LogStreamMode.GROUPED:
            self.subs_grouped[base.id] = {'base': base, 'sparkle': log_sparkle}
            
        # Wek de state machine als deze sliep
        if self.state == 'no_subscribers':
            self.to_state('wait_for_log')
            
        self.log(f"Tonic '{base.name}' subscribed. Mode: {log_stream_mod.name}")

    # --- Dispatch Helpers ---
    def _dispatch_direct(self, log_dict):
        """Stuur direct door naar de snelle tak."""
        for sub in self.subs_direct.values():
            sub['sparkle']([log_dict])

    def _dispatch_grouped(self, batch_list):
        """Stuur de buffer door naar de gegroepeerde tak."""
        if not batch_list: return
            
        for sub in self.subs_grouped.values():
            sub['sparkle'](batch_list)

    # =====================================================================
    # STATE: no_subscribers (Idle)
    # =====================================================================
    def ttsc_no_subscribers__process_incoming_log(self, log_dict):
        pass 

    # =====================================================================
    # STATE: wait_for_log (Ready for a new burst)
    # =====================================================================
    def ttsc_wait_for_log__process_incoming_log(self, log_dict):
        self._dispatch_direct(log_dict)
        self._dispatch_grouped([log_dict])
        
        self.tm_burst = ttTimerRepeat(seconds=0.100, name='tm_burst')
        self.to_state('check_for_burst')

    # =====================================================================
    # STATE: check_for_burst (Timer is ticking)
    # =====================================================================
    def ttsc_check_for_burst__process_incoming_log(self, log_dict):
        self._dispatch_direct(log_dict)
        self.log_buffer.append(log_dict)
        self.to_state('group_burst')

    def ttse_check_for_burst__on_tm_burst(self, tinfo):
        if self.tm_burst:
            self.tm_burst.stop()
            
        self.to_state('wait_for_log')

    # =====================================================================
    # STATE: group_burst (Active burst)
    # =====================================================================
    def ttsc_group_burst__process_incoming_log(self, log_dict):
        self._dispatch_direct(log_dict)
        self.log_buffer.append(log_dict)

    def ttse_group_burst__on_tm_burst(self, tinfo):
        if self.log_buffer:
            # We gebruiken jouw kopie-loze optimalisatie
            self._dispatch_grouped(self.log_buffer)
            self.log_buffer.clear()
            
        self.to_state('check_for_burst')
