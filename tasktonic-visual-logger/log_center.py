from TaskTonic import ttTonic, ttCatalyst
from TaskTonic.internals import Store, Item

from log_session import LogSession

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
        store_session.v = LogSession(store_session, name=store_session.path)
        store_session['status'] = 'new'
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




