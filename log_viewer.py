from PySide6.QtWidgets import QVBoxLayout, QLineEdit, QStyledItemDelegate, QListView, QLabel, QMenu, QWidget
from PySide6.QtCore import Qt, QRect, QPoint, QSize, QAbstractListModel, QModelIndex, QSortFilterProxyModel
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush

from TaskTonic.ttTonicStore import ttPysideWidget
from log_center import LogCenter, LogStreamMode


LANE_START_X = 25
LANE_SPACING = 30  
MAX_LANES = 8
GAP_HEIGHT = 16    
BLOCK_MARGIN = 5

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


class LogItemDelegate(QStyledItemDelegate):
    def __init__(self, log_center_ref, parent=None):
        super().__init__(parent)
        self.ls = log_center_ref
        self.font_header = QFont("Consolas", 10, QFont.Bold)
        self.font_symbol = QFont("Consolas", 10, QFont.Bold)
        self.font_body = QFont("Consolas", 9)

    def paint(self, painter, option, index):
        log_dict = index.data(Qt.UserRole)
        if not log_dict:
            return

        painter.save()
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            rect = option.rect
            t_id = log_dict.get('id', 0)
            
            source = log_dict.get('source', (None, ""))
            caller_id = source[0].id if (source and isinstance(source, tuple) and source[0]) else -1
            
            for i in range(1, MAX_LANES + 1):
                lane_x = rect.left() + LANE_START_X + ((i-1) * LANE_SPACING)
                color_idx = self.ls.get(f"session/ui/id/{i:02d}/color_idx", 0) or 0
                lane_color = QColor(ID_COLORS[color_idx][0])
                painter.setPen(QPen(lane_color, 2, Qt.SolidLine))
                painter.drawLine(lane_x, rect.top(), lane_x, rect.bottom())

            block_top = rect.top() + GAP_HEIGHT
            my_lane_x = rect.left() + LANE_START_X + ((t_id-1) % MAX_LANES * LANE_SPACING)
            
            if caller_id > 0:
                c_color_idx = self.ls.get(f"session/ui/id/{caller_id:02d}/color_idx", 0) or 0
                caller_color = QColor(ID_COLORS[c_color_idx][0])
                painter.setPen(QPen(caller_color, 2))
                
                route_y = rect.top() + 4
                dy = block_top - route_y
                
                if caller_id != t_id:
                    caller_lane_x = rect.left() + LANE_START_X + ((caller_id-1) * LANE_SPACING)
                    direction = 1 if caller_id < t_id else -1
                    turn_x = my_lane_x - (dy * direction)
                    painter.drawLine(caller_lane_x, route_y, turn_x, route_y)
                    painter.drawLine(turn_x, route_y, my_lane_x, block_top)
                else:
                    turn_x = my_lane_x + dy
                    painter.drawLine(my_lane_x, route_y, turn_x, route_y)
                    painter.drawLine(turn_x, route_y, my_lane_x, block_top)

            my_color_idx = self.ls.get(f"session/ui/id/{t_id:02d}/color_idx", 0) or 0
            target_color = QColor(ID_COLORS[my_color_idx][0])
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(target_color))
            painter.drawEllipse(my_lane_x - 4, block_top - 4, 8, 8)

            block_rect = QRect(rect.left() + BLOCK_MARGIN, block_top, 
                               rect.width() - (BLOCK_MARGIN * 2), rect.height() - GAP_HEIGHT - 2)
            painter.setBrush(QBrush(QColor("#2b2b2b")))
            painter.drawRoundedRect(block_rect, 6, 6)

            if my_color_idx > 0:
                border_rect = QRect(block_rect.left(), block_rect.top(), 4, block_rect.height())
                painter.setBrush(QBrush(target_color))
                painter.drawRect(border_rect)

            content_y = block_top + 16
            sym_x = block_rect.left() + 12
            painter.setFont(self.font_symbol)
            
            sys_info = log_dict.get('sys', {})
            if sys_info.get('created'):
                painter.setPen(QColor("#4CAF50"))
                painter.drawText(sym_x, content_y, "+")
            elif log_dict.get('finishing'):
                painter.setPen(QColor("#F44336"))
                painter.drawText(sym_x, content_y, "-")
                
            sym_x += 16
            sparkle_name = log_dict.get('sparkle', '')
            if sparkle_name.startswith('ttsc'):
                painter.setPen(QColor("#2196F3"))
                painter.drawText(sym_x, content_y, "C")
            elif sparkle_name.startswith('ttse'):
                painter.setPen(QColor("#FF9800"))
                painter.drawText(sym_x, content_y, "E")
            elif sparkle_name.startswith('_tts'):
                painter.setPen(QColor("#9C27B0"))
                painter.drawText(sym_x, content_y, "S")

            text_x = sym_x + 18
            painter.setFont(self.font_header)
            painter.setPen(QColor("#ffffff"))
            t_name = sys_info.get('name', 'Tonic')
            header_text = f"{t_id:02d}:{t_name}[{log_dict.get('state_name', 'idle')}].{sparkle_name}"
            
            if source and isinstance(source, tuple) and source[0] is not None and source[0].id > 0:
                header_text += f"  <--  calling {source[0].id:02d}:{getattr(source[0], 'name', 'Tonic')}.{source[1]}"
            painter.drawText(text_x, content_y, header_text)
            
            log_lines = log_dict.get('log', [])
            if log_lines:
                painter.setFont(self.font_body)
                painter.setPen(QColor("#aaaaaa"))
                y_off = content_y + 18
                for line in log_lines:
                    painter.drawText(text_x + 10, y_off, str(line))
                    y_off += 15
        finally:
            painter.restore()

    def sizeHint(self, option, index):
        log_dict = index.data(Qt.UserRole)
        if not log_dict:
            return QSize(option.rect.width(), 40)
            
        base_h = GAP_HEIGHT + 24 
        log_lines = log_dict.get('log', [])
        if log_lines:
            base_h += len(log_lines) * 15 + 6 
            
        return QSize(option.rect.width(), base_h)


class IDHeaderWidget(QWidget):
    def __init__(self, log_center_ref, on_change_callback, parent=None):
        super().__init__(parent)
        self.ls = log_center_ref
        self.on_change = on_change_callback
        self.setFixedHeight(30)
        self.setMouseTracking(True)

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            painter.fillRect(self.rect(), QColor("#121212"))
            painter.setPen(QColor("#888"))
            painter.drawText(2, 20, "ID")
            
            for i in range(1, MAX_LANES + 1):
                x = LANE_START_X + ((i-1) * LANE_SPACING)
                
                is_active = self.ls.get(f"session/ui/id/{i:02d}/active", True)
                color_idx = self.ls.get(f"session/ui/id/{i:02d}/color_idx", 0) or 0
                
                if not is_active:
                    painter.setPen(QColor("#444"))
                    painter.drawText(x - 7, 20, "XX")
                    continue

                color = QColor(ID_COLORS[color_idx][0])
                painter.setPen(color)
                
                if color_idx > 0:
                    painter.drawEllipse(x - 9, 7, 18, 18)
                    
                painter.drawText(x - 7, 20, f"{i:02d}")
        finally:
            painter.end()

    def mousePressEvent(self, event):
        for i in range(1, MAX_LANES + 1):
            x = LANE_START_X + ((i-1) * LANE_SPACING)
            if abs(event.position().x() - x) < 15:
                self.show_context_menu(i, event.globalPosition().toPoint())
                break

    def show_context_menu(self, t_id, pos):
        menu = QMenu(self)
        menu.setStyleSheet("background: #2b2b2b; color: white;")
        
        for idx, (color_hex, color_name) in enumerate(ID_COLORS):
            act = menu.addAction(color_name)
            act.triggered.connect(lambda _, tid=t_id, ci=idx: self.update_settings(tid, ci))
        
        menu.addSeparator()
        is_active = self.ls.get(f"session/ui/id/{t_id:02d}/active", True)
        v_act = menu.addAction("Hide ID" if is_active else "Show ID")
        v_act.triggered.connect(lambda _, tid=t_id: self.toggle_visibility(tid))
        
        menu.exec(pos)

    def update_settings(self, t_id, color_idx):
        self.ls[f"session/ui/id/{t_id:02d}/color_idx"] = color_idx
        self.on_change()
        self.update()

    def toggle_visibility(self, t_id):
        active_item = self.ls.at(f"session/ui/id/{t_id:02d}/active")
        active_item.v = not active_item.v
        self.on_change()
        self.update()


class LogModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logs = []
        
    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self.logs)
        
    def data(self, index, role=Qt.UserRole):
        if role == Qt.UserRole:
            return self.logs[index.row()]
        return None
        
    def add_logs(self, log_dicts):
        if not log_dicts:
            return
            
        row = len(self.logs)
        self.beginInsertRows(QModelIndex(), row, row + len(log_dicts) - 1)
        self.logs.extend(log_dicts)
        self.endInsertRows()


class LogFilterProxy(QSortFilterProxyModel):
    def __init__(self, log_center_ref, parent=None):
        super().__init__(parent)
        self.ls = log_center_ref

    def filterAcceptsRow(self, source_row, source_parent):
        index = self.sourceModel().index(source_row, 0, source_parent)
        log_dict = self.sourceModel().data(index, Qt.UserRole)
        
        if not log_dict:
            return False 
        
        t_id = log_dict.get('id', 0)
        return self.ls.get(f"session/ui/id/{t_id:02d}/active", True)


class ScreenLoggerWidget(ttPysideWidget):
    _tt_force_stealth_logging = True
    def setup_ui(self):
        self.ls = LogCenter(log_sparkle=self.ttsc__receive_batch, log_stream_mod=LogStreamMode.GROUPED)
        
        self.lay = self.layout() or QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(0)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter logs...")
        
        style = "padding: 8px; background: #1e1e1e; color: #fff; border: none; border-bottom: 1px solid #333;"
        self.search_input.setStyleSheet(style)
        self.lay.addWidget(self.search_input)

        self.id_header = IDHeaderWidget(self.ls, self.refresh_view)
        self.lay.addWidget(self.id_header)

        self.log_model = LogModel(self)
        self.proxy_model = LogFilterProxy(self.ls, self)
        self.proxy_model.setSourceModel(self.log_model)

        self.log_view = QListView()
        self.log_view.setStyleSheet("QListView { background-color: #000; border: none; }")
        self.log_view.setModel(self.proxy_model)
        
        self.delegate = LogItemDelegate(self.ls, self.log_view)
        self.log_view.setItemDelegate(self.delegate)
        
        self.log_view.setUniformItemSizes(False)
        self.lay.addWidget(self.log_view)

    def refresh_view(self):
        self.proxy_model.invalidateFilter()
        self.log_view.viewport().update()

    def ttse__on_start(self):
        self.ls.ttsc__update_subscription(
            base=self, 
            log_sparkle='ttsc__receive_batch', 
            log_stream_mod=LogStreamMode.GROUPED
        )
        print("ScreenLoggerWidget successfully subscribed to LogCenter.")

    def ttsc__receive_batch(self, log_batch):
        self.log_model.add_logs(log_batch)
        count = self.proxy_model.rowCount()
        
        if count > 0:
            self.log_view.scrollTo(self.proxy_model.index(count - 1, 0), QListView.PositionAtBottom)
