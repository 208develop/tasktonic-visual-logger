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
