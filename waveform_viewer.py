import sys
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QTreeWidget, QTreeWidgetItem, 
    QSplitter, QHeaderView, QHBoxLayout
)
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QPolygon, QBrush, QMouseEvent
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal

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
        
        # Enable mouse tracking for interactive cursor
        self.setMouseTracking(True)
        
        self.setMinimumSize(self.max_time * self.time_scale + 100, len(self.signals) * self.row_height + 50)
        self.setStyleSheet("background-color: #000000;")
        
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
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
        painter.setPen(QPen(QColor("#333333"), 1, Qt.PenStyle.DashLine))
        for t in range(0, self.max_time + 1, max(1, self.max_time // 10)):
            x = self.margin_left + t * self.time_scale
            painter.drawLine(x, 0, x, self.height())
            painter.setPen(QColor("#ffffff"))
            painter.drawText(x + 2, 15, str(t))
            painter.setPen(QPen(QColor("#333333"), 1, Qt.PenStyle.DashLine))

        y_offset = self.margin_top
        
        for var_id, sig_data in self.signals.items():
            name = sig_data['name']
            size = sig_data['size']
            values = sig_data['values']
            
            # Draw row separator
            painter.setPen(QPen(QColor("#333333"), 1, Qt.PenStyle.SolidLine))
            painter.drawLine(0, y_offset + self.row_height, self.width(), y_offset + self.row_height)
            
            if size == 1:
                self.draw_scalar(painter, values, y_offset)
            else:
                self.draw_vector(painter, values, y_offset)
                
            y_offset += self.row_height
            
        # Draw Red Cursor
        cursor_x = self.margin_left + self.cursor_time * self.time_scale
        painter.setPen(QPen(QColor("#ff0000"), 2, Qt.PenStyle.SolidLine))
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
                painter.drawText(QRect(int(x_start + 5), int(high_y), int(x_end - x_start - 10), int(low_y - high_y)), Qt.AlignmentFlag.AlignCenter, hex_val)
            else:
                painter.drawLine(int(x_start), int(mid_y), int(x_end), int(mid_y))


class WaveformViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.layout.addWidget(self.splitter)
        
        # Left Panel for Signal Names and Values (Vivado style)
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Name", "Value"])
        self.tree_widget.setColumnWidth(0, 200)
        self.tree_widget.setStyleSheet("QTreeWidget { background-color: #1e1e1e; color: white; } QHeaderView::section { background-color: #2d2d30; color: white; }")
        
        # Right Panel for Waveform Canvas
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background-color: #000000;")
        
        self.splitter.addWidget(self.tree_widget)
        self.splitter.addWidget(self.scroll_area)
        self.splitter.setSizes([300, 800])
        
        self.signals = {}

    def load_vcd_data(self, filepath):
        from vcd_parser import VCDParser
        try:
            parser = VCDParser(filepath)
            signals, max_time = parser.parse()
            self.signals = signals
            
            # Populate Tree
            self.tree_widget.clear()
            for var_id, sig in signals.items():
                item = QTreeWidgetItem([sig['name'], ""])
                item.setData(0, Qt.ItemDataRole.UserRole, var_id)
                self.tree_widget.addTopLevelItem(item)
                
            self.canvas = WaveformCanvas(signals, max_time)
            self.canvas.cursor_moved.connect(self.update_values)
            self.scroll_area.setWidget(self.canvas)
            
            # Initial update
            self.update_values(0)
        except Exception as e:
            print(f"Failed to load VCD: {e}")

    def update_values(self, t):
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            var_id = item.data(0, Qt.ItemDataRole.UserRole)
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
