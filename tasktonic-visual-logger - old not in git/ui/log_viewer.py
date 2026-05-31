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

