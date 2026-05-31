import time
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QPushButton, QWidget, QLabel
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QCursor, QIcon
from TaskTonic.ttTonicStore import ttPysideWidget
from TaskTonic.ttTimer import ttTimerRepeat
from ui.theme import Theme


def get_timeline_head(session_store):
    """Calculates the absolute end of the timeline based on session status."""
    status = session_store.get("status", "new")
    if status == "disconnected":
        logs = session_store.get("logs", [])
        if logs:
            return logs[-1].get("start@", time.time())
    return time.time()


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
                align = Qt.AlignLeft
                tx = 0
            elif i == 8:
                align = Qt.AlignRight
                tx = x - 100
            else:
                align = Qt.AlignCenter
                tx = x - 50

            text_rect = QRect(tx, 6 if not self.is_top else 0, 100, 18)
            painter.drawText(text_rect, align, text)

        if not self.is_top and 0.0 <= self.cursor_ratio <= 1.0 and self.cursor_text:
            cx = int(self.cursor_ratio * (w - 1))

            painter.setFont(QFont("Consolas", 9, QFont.Bold))
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(self.cursor_text) + 12

            box_rect = QRect(int(cx - (tw / 2)), 0, tw, 18)

            if box_rect.left() < 0:
                box_rect.moveLeft(0)
            if box_rect.right() > w:
                box_rect.moveRight(w)

            painter.setBrush(QColor("#FFCC00"))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(box_rect, 4, 4)
            painter.setPen(QColor("black"))
            painter.drawText(box_rect, Qt.AlignCenter, self.cursor_text)


class TotalTimelineWidget(ttPysideWidget):
    def __init__(self, session_store, parent=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.session_store = session_store
        self.id_info = {}
        self.lane_info = {}
        self._is_dragging = False
        self.setCursor(QCursor(Qt.PointingHandCursor))

    # ----------------------------------------------------------------------------------------------------------------
    # The widget
    # ----------------------------------------------------------------------------------------------------------------
    def setup_ui(self):
        self.setFixedHeight(45)

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
        now = get_timeline_head(self.session_store)
        base_ts = self.session_store.get('start@', now)
        total_duration = max(now - base_ts, 1.0)

        ratio = max(0.0, min(1.0, x_pos / self.width()))
        target_ts = base_ts + (ratio * total_duration)

        self.session_store.set([
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

            metrics = self.session_store.get("metrics_100ms", [])
            now = get_timeline_head(self.session_store)
            base_ts = self.session_store.get('start@', now)
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
                        id_info = self.id_info[t_int]

                        is_active = id_info.get("active", True)
                        if is_active and val > 0:
                            c_idx = id_info.get("color_idx", 0)
                            h = max(2, int((val / mv) * (rect.height() - 10)))
                            painter.fillRect(QRect(x, y_off - h, max(1, int(bw + 1)), h),
                                             Theme.get_color(c_idx))
                            y_off -= h
                    except (ValueError, TypeError, KeyError):
                        pass

            painter.setRenderHint(QPainter.Antialiasing, True)
            zoom = self.session_store.get("ui/timeline/zoom_sec", 30)
            mode = self.session_store.get("ui/timeline/mode", "waiting")

            if mode in ["tailing", "waiting"]:
                center_ts = now - (zoom / 2)
            else:
                center_ts = self.session_store.get("ui/timeline/freeze_ts", now)

            hw = (zoom / total_duration) * rect.width()
            hx = ((center_ts - (zoom / 2) - base_ts) / total_duration) * rect.width()
            hx = max(0, min(rect.width() - hw, hx))

            painter.setBrush(QColor(0, 255, 255, 50))
            painter.setPen(QPen(QColor(0, 255, 255, 200), 2))
            painter.drawRoundedRect(QRect(int(rect.left() + hx), rect.top(), int(hw), rect.height()), 4, 4)

            cursor_ts = self.session_store.get("ui/timeline/cursor_ts", 0)
            if cursor_ts > 0:
                cx = rect.left() + (((cursor_ts - base_ts) / total_duration) * rect.width())
                painter.setPen(QPen(QColor("#FFCC00"), 1))
                painter.drawLine(int(cx), rect.top(), int(cx), rect.bottom())

        finally:
            painter.end()

    #----------------------------------------------------------------------------------------------------------------
    # The Tonic
    #----------------------------------------------------------------------------------------------------------------
    def ttse__on_start(self):
        self.session_store.subscribe("ui/id_lanes", self.ttse__on_ui_id_change, recursive=True, trigger_now=True)
        self.id_info = self.session_store["ui/fast_access/id"].v.copy()
        self.lane_info = self.session_store["ui/fast_access/lane"].v.copy()

    def ttse__on_ui_id_change(self, updates):
        self.id_info = self.session_store["ui/fast_access/id"].v.copy()
        self.lane_info = self.session_store["ui/fast_access/lane"].v.copy()
        self.update()



class MicroTimelineWidget(ttPysideWidget):
    def __init__(self, session_store, parent=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.session_store = session_store
        self.metrics = []
        self.id_info = {}
        self.lane_info = {}
        self._is_dragging = False
        self.setCursor(QCursor(Qt.CrossCursor))

    def setup_ui(self):
        self.setFixedHeight(95)

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
        now = get_timeline_head(self.session_store)
        zoom = self.session_store.get("ui/timeline/zoom_sec", 30)
        mode = self.session_store.get("ui/timeline/mode", "waiting")
        base_ts = self.session_store.get('start@', now)

        if mode in ["tailing", "waiting"]:
            start_ts = now - zoom
        else:
            center_ts = self.session_store.get("ui/timeline/freeze_ts", now)
            center_ts = max(base_ts, min(now, center_ts))
            start_ts = center_ts - (zoom / 2)

        ratio = max(0.0, min(1.0, x_pos / self.width()))
        target_ts = start_ts + (ratio * zoom)

        self.session_store.set([
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

            now = get_timeline_head(self.session_store)
            base_ts = self.session_store.get('start@', now)
            zoom = self.session_store.get("ui/timeline/zoom_sec", 30)
            mode = self.session_store.get("ui/timeline/mode", "waiting")

            if mode in ["tailing", "waiting"]:
                center_ts = now - (zoom / 2)
            else:
                center_ts = self.session_store.get("ui/timeline/freeze_ts", now)
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

                    for tid_s, val in bucket.items():
                        try:
                            id_info = self.id_info[int(tid_s)]
                            if id_info.get('active', True) and val > 0:
                                c_idx = id_info.get('color_idx', 0)
                                h = max(2, int((val / mv) * (baseline_y - rect.top() - 5)))
                                painter.fillRect(QRect(x, y_off - h, max(1, int(bw + 1)), h),
                                                 Theme.get_color(c_idx))
                                y_off -= h
                        except (ValueError, TypeError, KeyError):
                            pass

            cursor_ts = self.session_store.get("ui/timeline/cursor_ts", 0)
            if start_ts <= cursor_ts <= (start_ts + zoom):
                cx = rect.left() + (((cursor_ts - start_ts) / zoom) * rect.width())
                painter.setRenderHint(QPainter.Antialiasing, True)
                painter.setPen(QPen(QColor("#FFCC00"), 2))
                painter.drawLine(int(cx), rect.top(), int(cx), rect.bottom())

        finally:
            painter.end()

    # ----------------------------------------------------------------------------------------------------------------
    # The Tonic
    # ----------------------------------------------------------------------------------------------------------------
    def ttse__on_start(self):
        self.session_store.subscribe("ui/id_lanes", self.ttse__on_ui_id_change, recursive=True, trigger_now=True)
        self.id_info = self.session_store["ui/fast_access/id"].v.copy()
        self.lane_info = self.session_store["ui/fast_access/lane"].v.copy()
        self.metrics = self.session_store.at("metrics_100ms").v

    def ttse__on_ui_id_change(self, updates):
        self.id_info = self.session_store["ui/fast_access/id"].v.copy()
        self.lane_info = self.session_store["ui/fast_access/lane"].v.copy()
        self.update()


class TimelineContainer(ttPysideWidget):
    ZOOM_STEPS = [30, 60, 120, 300, 600, 1800, 3600, 14400]

    def __init__(self, session_store, parent=None, **kwargs):
        self.session_store = session_store
        self._last_freeze_ts = -1.0
        self._tm_running = False
        super().__init__(parent=parent, name='timeline', **kwargs)

    def setup_ui(self):
        self.setFixedHeight(235)
        self.main_lay = QVBoxLayout(self)
        self.main_lay.setContentsMargins(10, 5, 10, 5)
        self.main_lay.setSpacing(6)

        CTRL_W = 40

        r1 = QHBoxLayout()
        r1.setSpacing(6)
        s1 = QWidget()
        s1.setFixedWidth(CTRL_W)
        r1.addWidget(s1)
        self.top_labels = TimelineLabelsWidget(is_top=True)
        r1.addWidget(self.top_labels)
        self.main_lay.addLayout(r1)

        r2 = QHBoxLayout()
        r2.setSpacing(6)
        self.btn_play = QPushButton()
        self.btn_play.setIcon(QIcon("ui/icons/play.svg"))
        self.btn_play.setIconSize(QSize(20, 20))
        self.btn_play.setFixedSize(CTRL_W, 45)
        self.btn_play.setStyleSheet("background:#222; border:1px solid #444; border-radius:6px;")
        self.btn_play.setCursor(Qt.PointingHandCursor)
        r2.addWidget(self.btn_play)

        self.total_view = TotalTimelineWidget(self.session_store)
        r2.addWidget(self.total_view)
        self.main_lay.addLayout(r2)

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

        self.micro_view = MicroTimelineWidget(self.session_store)
        r3.addWidget(self.micro_view)
        self.main_lay.addLayout(r3)

        r4 = QHBoxLayout()
        r4.setSpacing(6)
        s4 = QWidget()
        s4.setFixedWidth(CTRL_W)
        r4.addWidget(s4)
        self.bot_labels = TimelineLabelsWidget(is_top=False)
        r4.addWidget(self.bot_labels)
        self.main_lay.addLayout(r4)

    def ttse__on_start(self):
        self.tm_master = ttTimerRepeat(seconds=0.1, name="tm_master")
        self.tm_master.stop()
        self._tm_running = False

        self.session_store.subscribe("ui/timeline/freeze_ts", self.ttse__on_ui_changed)
        self.session_store.subscribe("ui/timeline/cursor_ts", self.ttse__on_ui_changed)
        self.session_store.subscribe("ui/timeline/zoom_sec", self.ttse__on_ui_changed)
        self.session_store.subscribe("ui/timeline/mode", self.ttse__on_mode_changed)
        self.session_store.subscribe("status", self.ttse__on_status_changed)

    def ttse__on_status_changed(self, _):
        self._evaluate_timer_state()
        self.ttsc__sync_ui_state()

    def ttse__on_mode_changed(self, _):
        self._evaluate_timer_state()
        self.ttsc__sync_ui_state()

    def ttse__on_ui_changed(self, _):
        if hasattr(self, 'tm_master') and not self._tm_running:
            self.ttsc__sync_ui_state()

    def _evaluate_timer_state(self):
        if not hasattr(self, 'tm_master'):
            return

        mode = self.session_store.get("ui/timeline/mode", "waiting")
        status = self.session_store.get("status", "new")

        if mode == "tailing" and status == "connected":
            if not self._tm_running:
                self.tm_master.restart()
                self._tm_running = True
        else:
            if self._tm_running:
                self.tm_master.stop()
                self._tm_running = False

    def ttse__on_tm_master(self, _):
        self.ttsc__sync_ui_state()

    def ttsc__sync_ui_state(self):
        if not self.session_store.get('logs', []):
            return

        now = get_timeline_head(self.session_store)
        mode = self.session_store.get("ui/timeline/mode", "waiting")
        status = self.session_store.get("status", "new")

        if mode == "tailing" and status == "connected":
            self.btn_play.setIcon(QIcon("ui/icons/pause.svg"))
        else:
            self.btn_play.setIcon(QIcon("ui/icons/play.svg"))

        self.total_view.update()
        self.micro_view.update()

        base_ts = self.session_store.get('start@', now)
        total_duration = max(now - base_ts, 0.1)

        top_ts = [
            f"{time.strftime('%H%M%S', time.localtime(base_ts + (i * total_duration / 8)))}."
            f"{int(((base_ts + (i * total_duration / 8)) % 1) * 1000):03d}"
            for i in range(9)
        ]
        self.top_labels.update_data(top_ts)

        zoom = self.session_store.get("ui/timeline/zoom_sec", 30)

        if mode in ["tailing", "waiting"]:
            center_ts = now - (zoom / 2)
        else:
            center_ts = self.session_store.get("ui/timeline/freeze_ts", now)
            center_ts = max(base_ts, min(now, center_ts))

        start_ts = center_ts - (zoom / 2)
        bot_ts = [
            f"{time.strftime('%H%M%S', time.localtime(start_ts + (i * zoom / 8)))}."
            f"{int(((start_ts + (i * zoom / 8)) % 1) * 1000):03d}"
            for i in range(9)
        ]

        cursor_ts = self.session_store.get("ui/timeline/cursor_ts", 0)
        c_ratio = -1.0
        c_text = ""
        if cursor_ts > 0 and start_ts <= cursor_ts <= (start_ts + zoom):
            c_ratio = (cursor_ts - start_ts) / zoom
            struct = time.localtime(cursor_ts)
            c_text = f"{time.strftime('%H:%M:%S', struct)}.{int((cursor_ts % 1) * 1000):03d}"

        self.bot_labels.update_data(bot_ts, cursor_ratio=c_ratio, cursor_text=c_text)

    def ttqt__btn_play__clicked(self):
        mode = self.session_store.get("ui/timeline/mode", "waiting")
        now = get_timeline_head(self.session_store)
        zoom = self.session_store.get("ui/timeline/zoom_sec", 30)

        if mode == "tailing":
            self.session_store.set([
                ("ui/timeline/mode", "history"),
                ("ui/timeline/freeze_ts", now - (zoom / 2)),
                ("ui/timeline/cursor_ts", now)
            ])
        else:
            self.session_store.set([
                ("ui/timeline/mode", "tailing"),
                ("ui/timeline/cursor_ts", 0.0)
            ])

    def ttqt__b_in__clicked(self):
        self._adj(-1)

    def ttqt__b_out__clicked(self):
        self._adj(1)

    def _adj(self, d):
        cur = self.session_store.get("ui/timeline/zoom_sec", 30)
        idx = self.ZOOM_STEPS.index(cur)
        val = self.ZOOM_STEPS[max(0, min(len(self.ZOOM_STEPS) - 1, idx + d))]
        self.session_store["ui/timeline/zoom_sec"] = val
        if val < 60:
            self.z_lbl.setText(f"{val}s")
        else:
            self.z_lbl.setText(f"{val // 60}m")
