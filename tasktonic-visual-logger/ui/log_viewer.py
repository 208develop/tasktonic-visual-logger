import time
import pprint
from PySide6.QtWidgets import QWidget, QToolTip, QMenu, QVBoxLayout, QHBoxLayout, QScrollBar
from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtGui import QPainter, QColor, QFont, QPen

# Pas deze import aan naar jouw specifieke locatie
from TaskTonic.ttTonicStore import ttPysideWidget
from ui.theme import Theme


# ==========================================
# Helpers
# ==========================================
def get_dynamic_lanes(seen_ids):
    try:
        known_ids = sorted([int(x) for x in seen_ids])
        return {tid: col for col, tid in enumerate(known_ids)}
    except (ValueError, TypeError, AttributeError):
        return {}


def get_contrast_color(bg_color):
    lum = 0.299 * bg_color.red() + 0.587 * bg_color.green() + 0.114 * bg_color.blue()
    return QColor("black") if lum > 130 else QColor("white")


# ==========================================
# 1. De ID Header Tonic
# ==========================================
class IDHeaderWidget(ttPysideWidget):
    def __init__(self, session_store, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_store = session_store
        self.id_info = {}
        self.lane_info = {}

    #----------------------------------------------------------------------------------------------------------------
    # The widget
    #----------------------------------------------------------------------------------------------------------------
    def setup_ui(self):
        self.setFixedHeight(30)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            painter.fillRect(self.rect(), QColor(Theme.BG_PANEL))

            x = Theme.LANE_START_X

            for i_id in self.id_info.values():
                l_id = i_id['id'].v
                is_active = i_id['active'].v
                color_idx = i_id['color_idx'].v

                target_color = Theme.get_color(color_idx)
                if not is_active:
                    target_color = QColor(getattr(Theme, 'LANE_INACTIVE', "#444444"))

                painter.setPen(Qt.NoPen)
                painter.setBrush(target_color)
                rect = QRect(x - 12, 5, 24, 20)
                painter.drawRoundedRect(rect, 6, 6)

                text_color = get_contrast_color(target_color) if is_active else QColor(Theme.TEXT_DIM)
                painter.setPen(text_color)
                painter.setFont(QFont("Consolas", 9, QFont.Bold))
                painter.drawText(rect, Qt.AlignCenter, f"{l_id}")

                x += Theme.LANE_SPACING
        finally:
            painter.end()

    def mouseMoveEvent(self, event):
        col = (event.pos().x() - Theme.LANE_START_X) / Theme.LANE_SPACING + .5
        if 10 <= int(col*100)%100 <= 90:
            pointed = self.lane_info.get(int(col))
            if pointed is not None:
                QToolTip.showText(
                    event.globalPosition().toPoint(),
                    f"{pointed['id'].v}:{pointed['name'].v}",
                    self
                )
                return

        QToolTip.hideText()

    def mousePressEvent(self, event):
        col = (event.pos().x() - Theme.LANE_START_X) / Theme.LANE_SPACING + .5
        if 10 <= int(col*100)%100 <= 90:
            pointed = self.lane_info[int(col)]
            if pointed['id'].v is not None:
                self.ttsc__show_context_menu(pointed, event.globalPosition().toPoint())

    #----------------------------------------------------------------------------------------------------------------
    # The Tonic
    #----------------------------------------------------------------------------------------------------------------
    def ttse__on_start(self):
        self.session_store.subscribe("ui/id_lanes", self.ttse__on_ui_id_updated, recursive=True, trigger_now=True)
        self.id_info = self.session_store["ui/fast_access/id"].v.copy()
        self.lane_info = self.session_store["ui/fast_access/lane"].v.copy()

    def ttse__on_ui_id_updated(self, updates):
        self.id_info = self.session_store["ui/fast_access/id"].v.copy()
        self.lane_info = self.session_store["ui/fast_access/lane"].v.copy()
        self.repaint()

    def ttsc__show_context_menu(self, pointed, pos):
        menu = QMenu(self)
        style = f"background: {Theme.BG_BLOCK}; color: {Theme.TEXT_MAIN}; border: 1px solid {Theme.BG_PANEL};"
        menu.setStyleSheet(style)

        title_act = menu.addAction(f"Settings for {pointed.v}:{pointed['name'].v}")
        title_act.setEnabled(False)

        menu.addSeparator()

        is_active = pointed.get('active', False)
        toggle_text = "Hide Lane" if is_active else "Show Lane"
        toggle_act = menu.addAction(toggle_text)
        toggle_act.triggered.connect(lambda _, item=pointed, toggle=not is_active: item.set('active', toggle))

        menu.addSeparator()

        for idx, (_, color_name) in enumerate(Theme.ID_COLORS):
            act = menu.addAction(color_name)
            act.triggered.connect(lambda _, item=pointed, ci=idx: item.set('color_idx', ci))

        menu.popup(pos)



# ==========================================
# 2. De Virtual Log View Tonic
# ==========================================
class VirtualLogView(ttPysideWidget):
    """
    Zelfstandige Tonic voor het tekenen van logs.
    Zendt een PySide signaal uit zodat domme UI-elementen (zoals een scrollbar) kunnen meeliften.
    """
    # PySide Signaal om de scrollbar van de parent up-to-date te houden
    sync_scrollbar = Signal(int, int)  # (scroll_index, total_logs)

    def __init__(self, session_store, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_store = session_store

        # Lokale State & Cache
        self._is_scrubbing = False
        self.logs = []
        self.scroll_index = 0

        self.id_info = {}
        self.lane_info = {}

    def setup_ui(self):
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)

    #----------------------------------------------------------------------------------------------------------------
    # The widget
    #----------------------------------------------------------------------------------------------------------------
    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        shift = 3 if delta > 0 else -3
        self.ttse_on_mouse_scroll_wheel(new_index=self.scroll_index + shift)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            log_dict = self._get_log_at_y(event.position().y())
            if log_dict and log_dict.get('start@', 0) > 0:
                self.ttse_on_log_clicked(cursor_ts=log_dict['start@'])

        elif event.button() == Qt.RightButton:
            self._is_scrubbing = True
            self._scrub_start_y = event.position().y()
            self._scrub_start_idx = self.scroll_index
            self.setCursor(Qt.SizeVerCursor)

    def mouseMoveEvent(self, event):
        if self._is_scrubbing:
            dy = event.position().y() - self._scrub_start_y
            idx_shift = int(dy / 5)
            self.ttse_on_mouse_scroll_wheel(new_index=self._scrub_start_idx - idx_shift)
            msg = f"Scrubbing: {self.scroll_index} / {len(self.logs)}"
            QToolTip.showText(event.globalPosition().toPoint(), msg, self)
        else:
            log_dict = self._get_log_at_y(event.position().y())
            if log_dict:
                clean_dict = {k: v for k, v in log_dict.items() if k != 'enriched'}
                pretty_str = pprint.pformat(clean_dict, indent=2, width=60)
                QToolTip.showText(event.globalPosition().toPoint(), f"<pre>{pretty_str}</pre>", self)
            else:
                QToolTip.hideText()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton:
            self._is_scrubbing = False
            self.setCursor(Qt.PointingHandCursor)
            QToolTip.hideText()

    # --- PYSIDE RENDERING ---

    def _get_log_at_y(self, target_y):
        if not self.logs: return None

        rect = self.rect()
        idx = (len(self.logs) - 1) - self.scroll_index
        current_y = rect.bottom()

        while idx >= 0 and current_y > -200:
            log_dict = self.logs[idx]
            t_id = int(log_dict.get('id', -1))

            if t_id >= 0 or self.id_info[t_id].get('active', True):
                h = self.calculate_height(log_dict)
                if current_y - h <= target_y <= current_y:
                    return log_dict
                current_y -= h
            idx -= 1
        return None

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            rect = self.rect()
            painter.fillRect(rect, QColor(Theme.BG_MAIN))

            x = Theme.LANE_START_X
            for i_id in self.id_info.values():
                color_idx = i_id['color_idx'].v

                lane_color = QColor(Theme.get_color(color_idx))
                lane_color.setAlpha(70)
                painter.setPen(QPen(lane_color, 3))
                painter.drawLine(x, 0, x, rect.height())

                x += Theme.LANE_SPACING

            total_count = len(self.logs)
            if total_count == 0: return

            idx = (total_count - 1) - self.scroll_index
            current_y = rect.bottom()

            painter.setRenderHint(QPainter.Antialiasing, True)
            while idx >= 0 and current_y > -200:
                log_dict = self.logs[idx]
                t_id = int(log_dict.get('id', -1))
                if t_id >= 0:
                    id_info = self.id_info.get(t_id)
                    if id_info is None or id_info.get('active', True):
                        h = self.calculate_height(log_dict)
                        self._draw_log(painter, current_y - h, h, rect.width(), log_dict, id_info)
                        current_y -= h
                idx -= 1
        finally:
            painter.end()

    def calculate_height(self, log):
        enr = log.get('enriched', {})
        lines = enr.get('ui_log_lines', [])
        probe = enr.get('probe')

        total_h = Theme.GAP_HEIGHT + 25 + 10
        if lines: total_h += len(lines) * 16
        if probe and isinstance(probe, dict):
            total_h += 10 + (len(probe) * 16) + 10
        return total_h

    def _draw_log(self, painter, y, h, w, log, id_info):
        t_id = int(log.get('id', -1))
        enr = log.get('enriched', {})
        ts = log.get('start@', 0)

        is_system = enr.get('is_system', False)
        bg_color = QColor(0, 30, 30) if is_system else QColor(0, 50, 50)
        border_color = QColor(0, 100, 100, 150) if is_system else QColor(0, 255, 255, 100)

        if enr.get('color_override') == 'white':
            bg_color = QColor(200, 200, 200)
            border_color = QColor(255, 255, 255)

        if t_id < 0:
            bg_color = QColor(30, 0, 30)
            border_color = QColor(200, 50, 150, 200)

        id_info = self.id_info.get(t_id)
        if not id_info: return

        c_idx = id_info['color_idx'].v
        base_color = Theme.get_color(c_idx) if t_id >= 0 else QColor("#FF00FF")

        bx, by = Theme.BLOCK_MARGIN, y + Theme.GAP_HEIGHT
        bw, bh = w - (Theme.BLOCK_MARGIN * 2), h - Theme.GAP_HEIGHT - 2
        painter.setBrush(bg_color)
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(bx, by, bw, bh, 6, 6)

        painter.setBrush(base_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(bx, by, 6, bh, 3, 3)

        if t_id >= 0:
            id_info = self.id_info[t_id]
            lane_x = Theme.LANE_START_X + (id_info.get('lane_nr', 0) * Theme.LANE_SPACING)
            painter.setBrush(base_color)
            painter.drawEllipse(lane_x - 4, by - 4, 8, 8)

            source_id = enr.get('source_id', -1)
            src_info = self.id_info.get(source_id, None)
            if src_info and src_info.get('active', True):
                painter.setPen(QPen(QColor(150, 150, 150, 150), 2, Qt.DashLine))
                if t_id == source_id:
                    painter.drawLine(lane_x, by - 10, lane_x+10, by-5)
                    painter.drawLine(lane_x+10, by - 5, lane_x, by-0)
                else:
                    src_x = Theme.LANE_START_X + (src_info.get('lane_nr', 0) * Theme.LANE_SPACING)
                    painter.drawLine(src_x, by - 10, lane_x, by)

        tx, ty = bx + 16, by + 18
        milli = int((ts % 1) * 1000)
        ts_str = f"[{time.strftime('%H:%M:%S', time.localtime(ts))}.{milli:03d}]" if ts > 0 else "[--:--:--.---]"
        painter.setFont(QFont("Consolas", 9))
        painter.setPen(QColor("#AAAAAA"))
        painter.drawText(tx, ty, ts_str)

        content_x = tx + 105

        phase = enr.get('lifecycle_phase')
        if phase:
            badge_map = {
                'creation': ('C', QColor(0, 180, 80)),
                'new_state': ('S', QColor(0, 120, 255)),
                'finishing': ('f', QColor(255, 140, 0)),
                'finished': ('F', QColor(255, 50, 50))
            }
            if phase in badge_map:
                char, b_color = badge_map[phase]
                painter.setBrush(b_color)
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(content_x, ty - 12, 15, 15, 4, 4)
                painter.setPen(QColor("white"))
                painter.setFont(QFont("Consolas", 9, QFont.Bold))
                painter.drawText(content_x + 3, ty, char)
                content_x += 22

        markers = enr.get('marker', [])
        if markers:
            painter.setFont(QFont("Consolas", 9, QFont.Bold))
            for m in markers:
                painter.setPen(QColor("#FFAA00"))
                painter.drawText(content_x, ty, f"[{m}]")
                content_x += painter.fontMetrics().horizontalAdvance(f"[{m}] ")

        painter.setFont(QFont("Consolas", 10, QFont.Bold))
        painter.setPen(QColor("black") if enr.get('color_override') == 'white' else QColor(Theme.TEXT_MAIN))

        if t_id < 0:
            main_text = f"-- SESSION --  {log.get('project', 'Unknown')} (v{log.get('logger_version', 0)})"
        else:
            state_str = f"[{enr.get('current_state')}]" if enr.get('current_state') else ""
            sparkle = enr.get('display_sparkle', '')
            main_text = f"{t_id:02d} : {enr.get('tonic_name', '')}{state_str}"
            if sparkle: main_text += f".{sparkle}"

            caller = enr.get('caller', '')
            if caller and caller != '.':
                main_text += f"  <--  {caller}"

            if enr.get('is_finishing') and phase != 'finished':
                main_text += " [FINISHING]"

        painter.drawText(content_x, ty, main_text)

        content_x = tx + 105
        painter.setFont(QFont("Consolas", 9))

        for line_item in enr.get('ui_log_lines', []):
            ty += 16
            if isinstance(line_item, tuple) and len(line_item) == 2:
                line_color_str, text = line_item
                if line_color_str and hasattr(Theme, line_color_str.upper()):
                    painter.setPen(QColor(getattr(Theme, line_color_str.upper())))
                else:
                    painter.setPen(QColor(line_color_str) if line_color_str else QColor(Theme.TEXT_DIM))
            else:
                painter.setPen(QColor(Theme.TEXT_DIM))
                text = str(line_item)

            painter.drawText(content_x + 15, ty, text)

        probe_data = enr.get('probe')
        if probe_data and isinstance(probe_data, dict):
            ty += 10
            probe_h = len(probe_data) * 16 + 10
            painter.setPen(QPen(QColor("#444444"), 1))
            painter.setBrush(QColor(0, 0, 0, 50))
            painter.drawRoundedRect(content_x + 15, ty, 300, probe_h, 4, 4)

            ty += 14
            for pk, pv in probe_data.items():
                painter.setPen(QColor("#00FFFF"))
                painter.drawText(content_x + 25, ty, f"{pk}:")
                painter.setPen(QColor("#FFFFFF"))
                painter.drawText(content_x + 120, ty, str(pv))
                ty += 16

    #----------------------------------------------------------------------------------------------------------------
    # The Tonic
    #----------------------------------------------------------------------------------------------------------------

    def ttse__on_start(self):
        # Abonneer op de data die deze view nodig heeft
        self.session_store.subscribe("last_append", self.ttse__on_logs_updated, trigger_now=True)
        self.session_store.subscribe("ui/timeline/cursor_ts", self.ttse__on_cursor_updated)
        self.session_store.subscribe("ui/id_lanes", self.ttse__on_id_store_updated, recursive=True, trigger_now=True)

        self.id_info = self.session_store["ui/fast_access/id"].v.copy()
        self.lane_info = self.session_store["ui/fast_access/lane"].v.copy()
        self.logs = self.session_store["logs"].v

        self.to_state('tailing')

    def ttse__on_id_store_updated(self, *args, **kwargs):
        self.id_info = self.session_store["ui/fast_access/id"].v.copy()
        self.lane_info = self.session_store["ui/fast_access/lane"].v.copy()
        self.update()

    def ttse_tailing__on_logs_updated(self, *args, **kwargs):
        self.scroll_index = 0
        self.sync_scrollbar.emit(self.scroll_index, len(self.logs))
        self.update()

    def ttse_frozen__on_logs_updated(self, *args, **kwargs):
        self.sync_scrollbar.emit(self.scroll_index, len(self.logs))
        self.update()

    def ttse_tailing__on_cursor_updated(self, *args, **kwargs):
        cursor_ts = self.session_store.get("ui/timeline/cursor_ts", 0)
        if not self.logs or cursor_ts <= 0: return
        last_ts = self.logs[-1].get('start@', 0)
        if abs(last_ts - cursor_ts) > 0.5:
            self.to_state('frozen')
            self.session_store.set([("ui/timeline/mode", "frozen")])
        self._get_nearest_index(cursor_ts)

    def ttse__on_cursor_updated(self, *args, **kwargs):
        cursor_ts = self.session_store.get("ui/timeline/cursor_ts", 0)
        if not self.logs or cursor_ts <= 0: return
        self._get_nearest_index(cursor_ts)

    def _get_nearest_index(self, cursor_ts):
        closest_idx = 0
        min_diff = float('inf')
        for i in range(len(self.logs) - 1, -1, -1):
            log_ts = self.logs[i].get('start@', 0)
            if log_ts <= 0: continue
            diff = abs(log_ts - cursor_ts)
            if diff < min_diff:
                min_diff = diff
                closest_idx = (len(self.logs) - 1) - i
            elif diff > min_diff:
                break

        if self.scroll_index != closest_idx:
            self.scroll_index = closest_idx
            self.sync_scrollbar.emit(self.scroll_index, len(self.logs))
            self.update()

    def ttse_on_mouse_scroll_wheel(self, new_index):
        if not self.logs: return
        safe_idx = max(0, min(len(self.logs) - 1, new_index))

        if self.scroll_index != safe_idx:
            self.scroll_index = safe_idx
            self.to_state('frozen')

            # Update store, dit triggert andere widgets (zoals de tijdlijn)
            log_dict = self.logs[(len(self.logs) - 1) - self.scroll_index]
            ts = log_dict.get('start@', 0)

            self.session_store.set([
                ("ui/timeline/cursor_ts", ts),
                ("ui/timeline/freeze_ts", ts),
                ("ui/timeline/mode", "frozen")
            ])

            self.sync_scrollbar.emit(self.scroll_index, len(self.logs))
            self.update()

    def ttse_on_log_clicked(self, cursor_ts):
        self.to_state('frozen')
        self.session_store.set([
            ("ui/timeline/cursor_ts", cursor_ts),
            ("ui/timeline/freeze_ts", cursor_ts),
            ("ui/timeline/mode", "frozen")
        ])



# ==========================================
# 3. De Layout Container (Geen Tonic meer!)
# ==========================================
class LogViewer(QWidget):
    """
    De domme PySide wrapper.
    Deze klasse voegt simpelweg de twee slimme Tonics en een ScrollBar samen in één layout.
    """

    def __init__(self, session_store, parent=None):
        super().__init__(parent)
        self.session_store = session_store

        # 1. Installeer de twee onafhankelijke Tonics
        self.header_widget = IDHeaderWidget(self.session_store, parent=self)
        self.log_view = VirtualLogView(self.session_store, parent=self)

        # 2. Installeer de domme scrollbar
        self.scrollbar = QScrollBar(Qt.Vertical, self)

        # 3. Koppel de scrollbar aan de VirtualLogView signalen en vice versa
        self.log_view.sync_scrollbar.connect(self._sync_scrollbar_bounds)
        self.scrollbar.valueChanged.connect(self._on_scrollbar_dragged)

        # 4. Bouw de layout op
        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)
        h_layout.addWidget(self.log_view)
        h_layout.addWidget(self.scrollbar)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header_widget)
        layout.addLayout(h_layout)

    def _sync_scrollbar_bounds(self, scroll_index, total_logs):
        """Wordt aangeroepen als VirtualLogView intern nieuwe data of index heeft."""
        if total_logs == 0:
            self.scrollbar.setRange(0, 0)
            return

        self.scrollbar.blockSignals(True)
        self.scrollbar.setRange(0, total_logs - 1)
        val = (total_logs - 1) - scroll_index
        self.scrollbar.setValue(val)
        self.scrollbar.blockSignals(False)

    def _on_scrollbar_dragged(self, value):
        """Wordt aangeroepen als de gebruiker fysiek aan de scrollbar trekt."""
        total = len(self.log_view.logs)
        if total > 0:
            new_idx = (total - 1) - value
            # Geef de actie door aan de Tonic zodat die een Sparkle kan genereren
            self.log_view.ttse_on_mouse_scroll_wheel(new_index=new_idx)