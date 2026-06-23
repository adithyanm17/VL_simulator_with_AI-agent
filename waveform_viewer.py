import sys
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QTreeWidget, QTreeWidgetItem, 
    QSplitter, QHeaderView, QHBoxLayout, QAbstractItemView
)
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QPolygon, QBrush, QMouseEvent
from PyQt5.QtCore import Qt, QRect, QPoint, pyqtSignal, QSize

class WaveformCanvas(QWidget):
    # Signal emitted when cursor moves: emits current time
    cursor_moved = pyqtSignal(int)

    def __init__(self, signals, max_time):
        super().__init__()
        self.signals = signals
        self.max_time = max_time if max_time > 0 else 100
        self.time_scale = 10 # Pixels per time unit
        self.row_height = 40
        self.margin_top = 30
        self.margin_left = 10
        self.cursor_time = 0
        self.visible_items = []
        
        # Enable mouse tracking for interactive cursor
        self.setMouseTracking(True)
        self.setStyleSheet("background-color: #000000;")
        self.update_geometry()
        
    def set_visible_items(self, items):
        self.visible_items = items
        self.update_geometry()
        self.update()
        
    def update_geometry(self):
        h = len(self.visible_items) * self.row_height + self.margin_top + 20
        w = self.max_time * self.time_scale + 100
        self.setMinimumSize(w, h)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            x = event.pos().x() - self.margin_left
            t = max(0, min(self.max_time, int(x / self.time_scale)))
            self.cursor_time = t
            self.cursor_moved.emit(t)
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor("#000000")) # Black background
        
        if not self.signals:
            return

        # Draw Grid and Time Axis
        painter.setPen(QPen(QColor("#333333"), 1, Qt.DashLine))
        for t in range(0, self.max_time + 1, max(1, self.max_time // 10)):
            x = self.margin_left + t * self.time_scale
            painter.drawLine(x, 0, x, self.height())
            painter.setPen(QColor("#ffffff"))
            painter.drawText(x + 2, 15, str(t))
            painter.setPen(QPen(QColor("#333333"), 1, Qt.DashLine))

        y_offset = self.margin_top
        
        for item in self.visible_items:
            var_id = item.data(0, Qt.UserRole)
            
            # Draw row separator
            painter.setPen(QPen(QColor("#333333"), 1, Qt.SolidLine))
            painter.drawLine(0, y_offset + self.row_height, self.width(), y_offset + self.row_height)
            
            if var_id == "SCOPE":
                # Draw a subtle background for scopes
                painter.fillRect(0, y_offset + 1, self.width(), self.row_height - 1, QColor("#1e1e1e"))
            else:
                sig_data = self.signals.get(var_id)
                if sig_data:
                    size = sig_data['size']
                    values = sig_data['values']
                    
                    if size == 1:
                        self.draw_scalar(painter, values, y_offset)
                    else:
                        self.draw_vector(painter, values, y_offset)
                
            y_offset += self.row_height
            
        # Draw Red Cursor
        cursor_x = self.margin_left + self.cursor_time * self.time_scale
        painter.setPen(QPen(QColor("#ff0000"), 2, Qt.SolidLine))
        painter.drawLine(cursor_x, 0, cursor_x, self.height())
        # Draw "T" box for cursor
        painter.fillRect(cursor_x - 6, 18, 12, 12, QColor("#ff0000"))
        painter.setPen(QColor("#ffffff"))
        painter.drawText(cursor_x - 4, 28, "T")

    def draw_scalar(self, painter, values, y_offset):
        if not values: return
        
        high_y = y_offset + 5
        low_y = y_offset + self.row_height - 5
        
        path_points = []
        
        for i, (t, val) in enumerate(values):
            x = self.margin_left + t * self.time_scale
            y = high_y if val == '1' else low_y
            
            if i == 0:
                # Extend from start to first transition
                path_points.append((self.margin_left, y))
            else:
                # Draw horizontal line to transition point
                prev_x = self.margin_left + t * self.time_scale
                path_points.append((prev_x, path_points[-1][1]))
                
            path_points.append((x, y))
            
        # Draw to end
        end_x = self.margin_left + self.max_time * self.time_scale
        path_points.append((end_x, path_points[-1][1]))
        
        painter.setPen(QPen(QColor("#00ff00"), 2))
        for i in range(len(path_points) - 1):
            painter.drawLine(path_points[i][0], path_points[i][1], path_points[i+1][0], path_points[i+1][1])

    def draw_vector(self, painter, values, y_offset):
        if not values: return
        
        high_y = y_offset + 5
        low_y = y_offset + self.row_height - 5
        mid_y = (high_y + low_y) // 2
        
        painter.setBrush(QColor("#004400"))
        
        for i, (t, val) in enumerate(values):
            x_start = self.margin_left + t * self.time_scale
            x_end = self.margin_left + values[i+1][0] * self.time_scale if i < len(values) - 1 else self.margin_left + self.max_time * self.time_scale
            
            if val == 'x' or 'x' in val:
                painter.setPen(QPen(QColor("#ff0000"), 2))
                painter.drawLine(int(x_start), int(mid_y), int(x_end), int(mid_y))
                continue
            
            painter.setPen(QPen(QColor("#00ff00"), 2))
            
            if x_end - x_start > 10:
                poly = QPolygon([
                    QPoint(int(x_start), int(mid_y)),
                    QPoint(int(x_start + 5), int(high_y)),
                    QPoint(int(x_end - 5), int(high_y)),
                    QPoint(int(x_end), int(mid_y)),
                    QPoint(int(x_end - 5), int(low_y)),
                    QPoint(int(x_start + 5), int(low_y))
                ])
                painter.drawPolygon(poly)
                
                # Draw hex value
                try:
                    hex_val = hex(int(val, 2))[2:]
                except:
                    hex_val = val
                painter.setPen(QColor("#ffffff"))
                painter.drawText(QRect(int(x_start + 5), int(high_y), int(x_end - x_start - 10), int(low_y - high_y)), Qt.AlignCenter, hex_val)
            else:
                painter.drawLine(int(x_start), int(mid_y), int(x_end), int(mid_y))


class WaveformViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        
        self.splitter = QSplitter(Qt.Horizontal)
        self.layout.addWidget(self.splitter)
        
        # Left Panel for Signal Names and Values (Vivado style)
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Name", "Value"])
        self.tree_widget.setColumnWidth(0, 200)
        self.tree_widget.setStyleSheet("QTreeWidget { background-color: #1e1e1e; color: white; } QHeaderView::section { background-color: #2d2d30; color: white; border: none; padding-left: 5px; }")
        self.tree_widget.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.tree_widget.header().setFixedHeight(30)
        self.tree_widget.setUniformRowHeights(True)
        
        # Right Panel for Waveform Canvas
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background-color: #000000; border: none;")
        
        # Sync scrolling
        self.tree_widget.verticalScrollBar().valueChanged.connect(self.scroll_area.verticalScrollBar().setValue)
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.tree_widget.verticalScrollBar().setValue)
        
        # Update canvas visibility when items expand or collapse
        self.tree_widget.itemExpanded.connect(self.update_canvas_visible_items)
        self.tree_widget.itemCollapsed.connect(self.update_canvas_visible_items)
        
        self.splitter.addWidget(self.tree_widget)
        self.splitter.addWidget(self.scroll_area)
        self.splitter.setSizes([300, 800])
        
        self.signals = {}
        self.canvas = None

    def load_vcd_data(self, filepath):
        from vcd_parser import VCDParser
        try:
            parser = VCDParser(filepath)
            signals, max_time = parser.parse()
            self.signals = signals
            
            # Populate Tree
            self.tree_widget.clear()
            scope_items = {}
            
            root = self.tree_widget.invisibleRootItem()
            
            for var_id, sig in signals.items():
                path = sig.get('path', [])
                current_parent = root
                current_path_str = ""
                
                # Build hierarchy
                for p in path:
                    current_path_str += "/" + p
                    if current_path_str not in scope_items:
                        scope_item = QTreeWidgetItem([p, ""])
                        scope_item.setData(0, Qt.UserRole, "SCOPE")
                        scope_item.setSizeHint(0, QSize(100, 40))
                        # Optional: style the scope name
                        scope_item.setFont(0, QFont("Consolas", 10, QFont.Bold))
                        current_parent.addChild(scope_item)
                        scope_items[current_path_str] = scope_item
                    current_parent = scope_items[current_path_str]
                
                # Add signal
                item = QTreeWidgetItem([sig['name'], ""])
                item.setData(0, Qt.UserRole, var_id)
                item.setSizeHint(0, QSize(100, 40))
                current_parent.addChild(item)
                
            self.tree_widget.collapseAll()
            
            self.canvas = WaveformCanvas(signals, max_time)
            self.canvas.cursor_moved.connect(self.update_values)
            self.scroll_area.setWidget(self.canvas)
            
            self.update_canvas_visible_items()
            
            # Initial update
            self.update_values(0)
        except Exception as e:
            print(f"Failed to load VCD: {e}")

    def update_canvas_visible_items(self):
        if not self.canvas: return
        
        visible_items = []
        def traverse(item):
            visible_items.append(item)
            if item.isExpanded():
                for i in range(item.childCount()):
                    traverse(item.child(i))
                    
        for i in range(self.tree_widget.topLevelItemCount()):
            traverse(self.tree_widget.topLevelItem(i))
            
        self.canvas.set_visible_items(visible_items)

    def update_values(self, t):
        if not self.canvas: return
        for item in self.canvas.visible_items:
            var_id = item.data(0, Qt.UserRole)
            if var_id and var_id != "SCOPE":
                sig = self.signals.get(var_id)
                if sig:
                    val = self.get_value_at_time(sig['values'], t)
                    if sig['size'] > 1 and val not in ('x', 'z'):
                        try:
                            val = hex(int(val, 2))[2:]
                        except:
                            pass
                    item.setText(1, val)

    def get_value_at_time(self, values, t):
        current_val = 'x'
        for time_pt, val in values:
            if time_pt <= t:
                current_val = val
            else:
                break
        return current_val
