"""
Logic Gate Diagram Viewer
Parses Verilog assign/gate instantiation statements and renders a
visual schematic of AND, OR, NOT, XOR, NAND, NOR, XNOR gates with wires.
No external hardware or ports needed — purely code-to-diagram.
"""
import re
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy, QApplication, QComboBox
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QFont, QBrush, QPainterPath,
    QLinearGradient, QFontMetrics
)
from PyQt6.QtCore import Qt, QRect, QRectF, QPointF, QSize, QTimer


# ─────────────────────────────────────────────────────────────────────────────
#  Gate data model
# ─────────────────────────────────────────────────────────────────────────────
GATE_COLORS_DARK = {
    "AND":  ("#1a3a6a", "#4a9eff", "#a0cfff"),
    "NAND": ("#3a1a1a", "#ff6a6a", "#ffaaaa"),
    "OR":   ("#1a3a1a", "#4aff6a", "#a0ffb0"),
    "NOR":  ("#2a1a3a", "#aa6aff", "#ccaaff"),
    "XOR":  ("#3a2a00", "#ffbb00", "#ffe080"),
    "XNOR": ("#1a2a3a", "#00ccff", "#80eeff"),
    "NOT":  ("#2a1a00", "#ff8800", "#ffcc80"),
    "BUF":  ("#1a1a1a", "#aaaaaa", "#dddddd"),
    "WIRE": ("#0a1a0a", "#44aa44", "#88dd88"),
}

GATE_COLORS_LIGHT = {
    "AND":  ("#ddeeff", "#1565c0", "#003580"),
    "NAND": ("#ffeaea", "#c62828", "#7a0000"),
    "OR":   ("#eaffea", "#2e7d32", "#005005"),
    "NOR":  ("#f3eaff", "#6a1b9a", "#38006b"),
    "XOR":  ("#fffde7", "#f57f17", "#bc5100"),
    "XNOR": ("#e0f7fa", "#00838f", "#005662"),
    "NOT":  ("#fff3e0", "#e65100", "#8d1c00"),
    "BUF":  ("#f5f5f5", "#616161", "#212121"),
    "WIRE": ("#e8f5e9", "#388e3c", "#1b5e20"),
}

# Default to dark
GATE_COLORS = GATE_COLORS_DARK

class GateNode:
    """Represents one logic gate extracted from Verilog."""
    def __init__(self, gate_type, output, inputs, expr=""):
        self.gate_type = gate_type.upper()
        self.output = output          # signal name string
        self.inputs = inputs          # list of signal name strings
        self.expr = expr              # original expression for tooltip
        # Layout position (set by layout engine)
        self.col = 0
        self.row = 0
        self.x = 0
        self.y = 0
        self.w = 120
        self.h = 70


# ─────────────────────────────────────────────────────────────────────────────
#  Verilog → Gate parser
# ─────────────────────────────────────────────────────────────────────────────
class VerilogGateParser:
    """
    Extracts logical gate operations from Verilog source.
    Handles:
      - assign  out = a & b;        → AND
      - assign  out = a | b;        → OR
      - assign  out = a ^ b;        → XOR
      - assign  out = ~a;           → NOT
      - assign  out = ~(a & b);     → NAND  (simple cases)
      - Gate-level instantiation: and g1(out, a, b);
    """

    PRIMITIVES = ["and", "nand", "or", "nor", "xor", "xnor", "not", "buf"]

    def parse(self, code: str):
        """Returns list of GateNode."""
        gates = []
        # Strip comments
        code = re.sub(r'//[^\n]*', '', code)
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)

        gates += self._parse_primitives(code)
        gates += self._parse_assigns(code)
        return gates

    # ── Gate primitive instantiation ──────────────────────────────────────
    def _parse_primitives(self, code):
        gates = []
        prim_pat = re.compile(
            r'\b(' + '|'.join(self.PRIMITIVES) + r')\s+'
            r'(?:\w+\s+)?\(([^;]+)\)\s*;',
            re.IGNORECASE
        )
        for m in prim_pat.finditer(code):
            gtype = m.group(1).upper()
            ports_raw = [p.strip() for p in m.group(2).split(',')]
            if len(ports_raw) >= 2:
                out = ports_raw[0]
                ins = ports_raw[1:]
                gates.append(GateNode(gtype, out, ins, m.group(0).strip()))
        return gates

    # ── Assign statement decomposition ───────────────────────────────────
    def _parse_assigns(self, code):
        gates = []
        assign_pat = re.compile(
            r'\bassign\s+(\w+)\s*=\s*([^;]+);',
            re.IGNORECASE
        )
        for m in assign_pat.finditer(code):
            out = m.group(1).strip()
            expr = m.group(2).strip()
            node = self._classify_expr(out, expr)
            if node:
                gates.append(node)
        return gates

    def _classify_expr(self, out, expr):
        """Map a simple RHS expression to a gate type."""
        e = expr.strip()

        # NAND: ~(a & b)
        nm = re.match(r'^~\(\s*([^&|^~)(]+)\s*&\s*([^&|^~)(]+)\s*\)$', e)
        if nm:
            return GateNode("NAND", out, [nm.group(1).strip(), nm.group(2).strip()], expr)

        # NOR: ~(a | b)
        nm = re.match(r'^~\(\s*([^&|^~)(]+)\s*\|\s*([^&|^~)(]+)\s*\)$', e)
        if nm:
            return GateNode("NOR", out, [nm.group(1).strip(), nm.group(2).strip()], expr)

        # XNOR: ~(a ^ b)
        nm = re.match(r'^~\(\s*([^&|^~)(]+)\s*\^\s*([^&|^~)(]+)\s*\)$', e)
        if nm:
            return GateNode("XNOR", out, [nm.group(1).strip(), nm.group(2).strip()], expr)

        # NOT: ~a or !a
        nm = re.match(r'^[~!]\(?(\w+)\)?$', e)
        if nm:
            return GateNode("NOT", out, [nm.group(1).strip()], expr)

        # AND: a & b (& c ...)
        if '&' in e and '|' not in e and '^' not in e:
            parts = [p.strip() for p in re.split(r'&', e) if p.strip()]
            parts = [re.sub(r'[()~!]', '', p).strip() for p in parts]
            parts = [p for p in parts if p]
            if parts:
                return GateNode("AND", out, parts, expr)

        # OR: a | b
        if '|' in e and '&' not in e and '^' not in e:
            parts = [p.strip() for p in re.split(r'\|', e) if p.strip()]
            parts = [re.sub(r'[()~!]', '', p).strip() for p in parts]
            parts = [p for p in parts if p]
            if parts:
                return GateNode("OR", out, parts, expr)

        # XOR: a ^ b
        if '^' in e and '&' not in e and '|' not in e:
            parts = [p.strip() for p in re.split(r'\^', e) if p.strip()]
            parts = [re.sub(r'[()~!]', '', p).strip() for p in parts]
            parts = [p for p in parts if p]
            if parts:
                return GateNode("XOR", out, parts, expr)

        # Wire / buffer assignment (plain signal copy)
        if re.match(r'^\w+$', e):
            return GateNode("BUF", out, [e], expr)

        return None  # complex expression – skip


# ─────────────────────────────────────────────────────────────────────────────
#  Gate Canvas (QPainter schematic renderer)
# ─────────────────────────────────────────────────────────────────────────────
GATE_W = 110
GATE_H = 68
H_GAP  = 90   # horizontal gap between columns
V_GAP  = 28   # vertical gap between rows
MARGIN = 60


class GateCanvas(QWidget):
    """Renders a list of GateNode as a schematic."""

    BG_DARK  = "#0b0f14"
    BG_LIGHT = "#f8fafc"

    def __init__(self, gates, parent=None, theme="dark"):
        super().__init__(parent)
        self.gates = gates
        self._theme = theme
        self._bg = self.BG_LIGHT if theme == "light" else self.BG_DARK
        self.setStyleSheet(f"background: {self._bg};")
        self._layout_gates()
        self._compute_size()
        self.setMinimumSize(self._total_w, self._total_h)

    # ── layout: assign col/row to each gate ──────────────────────────────
    def _layout_gates(self):
        if not self.gates:
            return

        # Build signal→gate map
        sig_to_gate = {g.output: g for g in self.gates}

        # Assign column by topological depth
        def get_depth(gate, memo={}):
            if gate.output in memo:
                return memo[gate.output]
            max_d = 0
            for inp in gate.inputs:
                if inp in sig_to_gate:
                    max_d = max(max_d, get_depth(sig_to_gate[inp], memo) + 1)
            memo[gate.output] = max_d
            return max_d

        memo = {}
        for g in self.gates:
            g.col = get_depth(g, memo)

        # Group by column, assign rows
        col_groups = {}
        for g in self.gates:
            col_groups.setdefault(g.col, []).append(g)

        for col, grp in col_groups.items():
            for row, g in enumerate(grp):
                g.row = row
                g.x = MARGIN + col * (GATE_W + H_GAP)
                g.y = MARGIN + row * (GATE_H + V_GAP)
                g.w = GATE_W
                g.h = GATE_H

    def _compute_size(self):
        if not self.gates:
            self._total_w = 600
            self._total_h = 300
            return
        max_x = max(g.x + g.w for g in self.gates) + MARGIN
        max_y = max(g.y + g.h for g in self.gates) + MARGIN
        self._total_w = max(600, max_x)
        self._total_h = max(300, max_y)

    # ── Paint ─────────────────────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(self._bg))

        if not self.gates:
            no_gate_color = "#334455" if self._theme == "dark" else "#607d8b"
            p.setPen(QColor(no_gate_color))
            p.setFont(QFont("Segoe UI", 13))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "No logic gates detected in the Verilog code.\n\n"
                       "Make sure your file contains assign statements\n"
                       "or gate-level primitives (and, or, not, xor…)")
            return

        # Draw grid dots
        dot_color = "#151c24" if self._theme == "dark" else "#dde4ec"
        p.setPen(QPen(QColor(dot_color), 1))
        for gx in range(0, self._total_w, 30):
            for gy in range(0, self._total_h, 30):
                p.drawPoint(gx, gy)

        # Build signal→gate map for wire routing
        sig_to_gate = {g.output: g for g in self.gates}

        # Draw wires first (behind gates)
        self._draw_wires(p, sig_to_gate)

        # Draw gates
        for g in self.gates:
            self._draw_gate(p, g)

    def _draw_wires(self, p, sig_to_gate):
        """Draw wires from gate outputs to connected inputs."""
        for dst_gate in self.gates:
            for i, inp_name in enumerate(dst_gate.inputs):
                # Input pin position on destination gate
                dst_x, dst_y = self._input_pin_pos(dst_gate, i)

                if inp_name in sig_to_gate:
                    src_gate = sig_to_gate[inp_name]
                    src_x, src_y = self._output_pin_pos(src_gate)
                else:
                    # External input: draw a short stub from the left
                    # Label the stub
                    stub_x = dst_x - 40
                    stub_y = dst_y
                    pen = QPen(QColor("#667799"), 1.5, Qt.PenStyle.DashLine)
                    p.setPen(pen)
                    p.drawLine(int(stub_x), int(stub_y), int(dst_x), int(dst_y))
                    # Input label
                    p.setPen(QColor("#8899bb"))
                    p.setFont(QFont("Consolas", 8))
                    p.drawText(int(stub_x) - 55, int(stub_y) - 7, 52, 16,
                               Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                               inp_name)
                    continue

                # Bezier wire from src output to dst input
                pen = QPen(QColor("#2a6a44"), 2)
                p.setPen(pen)
                path = QPainterPath()
                path.moveTo(src_x, src_y)
                mid_x = (src_x + dst_x) / 2
                path.cubicTo(mid_x, src_y, mid_x, dst_y, dst_x, dst_y)
                p.drawPath(path)

                # Arrow tip at destination
                p.setBrush(QColor("#2a6a44"))
                p.setPen(Qt.PenStyle.NoPen)
                aw = 6
                tri = QPainterPath()
                tri.moveTo(dst_x, dst_y)
                tri.lineTo(dst_x - aw, dst_y - aw // 2)
                tri.lineTo(dst_x - aw, dst_y + aw // 2)
                tri.closeSubpath()
                p.drawPath(tri)
                p.setBrush(Qt.BrushStyle.NoBrush)

    def _draw_gate(self, p: QPainter, g: GateNode):
        gtype = g.gate_type
        palette = GATE_COLORS_LIGHT if self._theme == "light" else GATE_COLORS_DARK
        bg_dark, accent, label_color = palette.get(gtype, ("#1a1a2a", "#6688cc", "#aabbdd"))

        x, y, w, h = g.x, g.y, g.w, g.h

        # ── Body gradient ──────────────────────────────────────────────
        grad = QLinearGradient(x, y, x, y + h)
        grad.setColorAt(0, QColor(bg_dark).lighter(160))
        grad.setColorAt(1, QColor(bg_dark))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(QColor(accent), 2))

        shape_path = self._gate_shape_path(gtype, x, y, w, h)
        p.drawPath(shape_path)

        # ── Gate type label ────────────────────────────────────────────
        p.setPen(QColor(label_color))
        p.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        p.drawText(int(x), int(y), int(w), int(h),
                   Qt.AlignmentFlag.AlignCenter, gtype)

        # ── Output signal name (right side) ───────────────────────────
        out_x, out_y = self._output_pin_pos(g)
        p.setPen(QColor("#00cc88"))
        p.setFont(QFont("Consolas", 8))
        p.drawText(int(out_x + 6), int(out_y) - 7, 80, 14,
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   g.output)

        # ── Output pin dot ─────────────────────────────────────────────
        p.setBrush(QColor("#00cc88"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(int(out_x) - 4, int(out_y) - 4, 8, 8)
        p.setBrush(Qt.BrushStyle.NoBrush)

        # ── Input pin dots ─────────────────────────────────────────────
        for i in range(len(g.inputs)):
            px, py = self._input_pin_pos(g, i)
            p.setBrush(QColor("#4499cc"))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(int(px) - 3, int(py) - 3, 6, 6)
            p.setBrush(Qt.BrushStyle.NoBrush)

        # ── Bubble for inverting gates ─────────────────────────────────
        if gtype in ("NOT", "NAND", "NOR", "XNOR", "BUF"):
            bx, by = self._output_pin_pos(g)
            p.setBrush(QColor(self._bg))
            p.setPen(QPen(QColor(accent), 2))
            p.drawEllipse(int(bx) - 7, int(by) - 5, 10, 10)

    def _gate_shape_path(self, gtype, x, y, w, h) -> QPainterPath:
        """Return the iconic gate shape as a QPainterPath."""
        path = QPainterPath()
        rx, ry = float(x), float(y)
        rw, rh = float(w), float(h)

        if gtype in ("AND", "NAND"):
            # D-shape: flat left, rounded right
            path.moveTo(rx + rw * 0.35, ry)
            path.lineTo(rx + rw * 0.35, ry + rh)
            path.lineTo(rx, ry + rh)
            path.lineTo(rx, ry)
            path.closeSubpath()
            # Arc on right
            arc_rect = QRectF(rx + rw * 0.1, ry, rw * 0.9, rh)
            path2 = QPainterPath()
            path2.moveTo(rx + rw * 0.35, ry)
            path2.arcTo(arc_rect, 90, -180)
            path2.lineTo(rx + rw * 0.35, ry + rh)
            path2.closeSubpath()
            return path2

        elif gtype in ("OR", "NOR"):
            path.moveTo(rx, ry)
            path.quadTo(rx + rw * 0.5, ry, rx + rw, ry + rh * 0.5)
            path.quadTo(rx + rw * 0.5, ry + rh, rx, ry + rh)
            path.quadTo(rx + rw * 0.25, ry + rh * 0.5, rx, ry)
            path.closeSubpath()
            return path

        elif gtype in ("XOR", "XNOR"):
            path.moveTo(rx + rw * 0.12, ry)
            path.quadTo(rx + rw * 0.5, ry, rx + rw, ry + rh * 0.5)
            path.quadTo(rx + rw * 0.5, ry + rh, rx + rw * 0.12, ry + rh)
            path.quadTo(rx + rw * 0.37, ry + rh * 0.5, rx + rw * 0.12, ry)
            path.closeSubpath()
            return path

        elif gtype == "NOT":
            path.moveTo(rx, ry)
            path.lineTo(rx + rw * 0.85, ry + rh * 0.5)
            path.lineTo(rx, ry + rh)
            path.closeSubpath()
            return path

        else:  # BUF, WIRE, default rectangle
            path.addRoundedRect(QRectF(rx, ry, rw, rh), 8, 8)
            return path

    def _output_pin_pos(self, g):
        """Right-center of gate."""
        return g.x + g.w, g.y + g.h / 2

    def _input_pin_pos(self, g, index):
        """Evenly spaced pins on left side."""
        n = max(1, len(g.inputs))
        step = g.h / (n + 1)
        py = g.y + step * (index + 1)
        return g.x, py


# ─────────────────────────────────────────────────────────────────────────────
#  Main VIO Dashboard widget
# ─────────────────────────────────────────────────────────────────────────────
class VIODashboard(QWidget):
    """
    Logic Gate Diagram viewer panel.
    Call load_module(verilog_code, module_name) to parse and display.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._gates = []
        self._theme = "dark"
        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        self._header = QFrame()
        self._header.setFixedHeight(44)
        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(12, 0, 12, 0)

        self._icon_lbl = QLabel("⬡")
        self._icon_lbl.setFont(QFont("Segoe UI Emoji", 18))
        hl.addWidget(self._icon_lbl)

        self._title_lbl = QLabel("Logic Gate Diagram Viewer")
        self._title_lbl.setStyleSheet(
            "font-family: 'Segoe UI'; font-size: 13px; font-weight: bold; padding-left: 6px;"
        )
        hl.addWidget(self._title_lbl)
        hl.addStretch()

        self.gate_count_lbl = QLabel("")
        hl.addWidget(self.gate_count_lbl)

        root.addWidget(self._header)

        # Toolbar
        self._toolbar = QFrame()
        self._toolbar.setFixedHeight(38)
        tb = QHBoxLayout(self._toolbar)
        tb.setContentsMargins(8, 4, 8, 4)
        tb.setSpacing(8)

        self.parse_btn = QPushButton("⟳  Parse & Draw")
        self.parse_btn.setToolTip("Parse the active Verilog file and draw gate diagram")
        tb.addWidget(self.parse_btn)

        # Zoom controls
        tb.addWidget(QLabel(" "))
        self._zoom_lbl = QLabel("Zoom:")
        self._zoom_lbl.setStyleSheet("font-family: 'Segoe UI'; font-size: 10px;")
        tb.addWidget(self._zoom_lbl)

        self.zoom_combo = QComboBox()
        self.zoom_combo.addItems(["50%", "75%", "100%", "125%", "150%", "200%"])
        self.zoom_combo.setCurrentText("100%")
        self.zoom_combo.setFixedWidth(70)
        self.zoom_combo.currentTextChanged.connect(self._on_zoom_changed)
        tb.addWidget(self.zoom_combo)

        tb.addStretch()

        # Legend dots (stored so we can recolor on theme change)
        self._legend_dots  = []
        self._legend_lbls  = []
        for gtype, (_, accent_d, _) in list(GATE_COLORS_DARK.items())[:6]:
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {accent_d}; font-size: 10px;")
            lbl = QLabel(gtype)
            lbl.setStyleSheet("font-family: Consolas; font-size: 9px; margin-right: 6px;")
            tb.addWidget(dot)
            tb.addWidget(lbl)
            self._legend_dots.append((gtype, dot))
            self._legend_lbls.append(lbl)

        root.addWidget(self._toolbar)

        # Scroll canvas area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(False)

        # Initial placeholder
        self._canvas = self._make_placeholder()
        self.scroll.setWidget(self._canvas)
        root.addWidget(self.scroll)

        self._zoom = 1.0

        # Apply the default (dark) theme styling now that all widgets exist
        self._apply_vio_palette()

    # ── placeholder canvas ────────────────────────────────────────────────
    def _make_placeholder(self):
        bg  = "#f8fafc" if self._theme == "light" else "#0b0f14"
        fg  = "#607d8b" if self._theme == "light" else "#263545"
        w = QWidget()
        w.setStyleSheet(f"background: {bg};")
        w.setMinimumSize(600, 300)
        lyt = QVBoxLayout(w)
        lbl = QLabel(
            "📐  Open a Verilog file in the editor,\n"
            "then click  ⟳ Parse & Draw\n\n"
            "Supported: assign statements, and/or/not/xor/nand/nor primitives"
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            f"color: {fg}; font-family: 'Segoe UI'; font-size: 13px; padding: 60px;"
        )
        lyt.addWidget(lbl)
        return w

    # ── public API ─────────────────────────────────────────────────────────
    def apply_theme(self, theme_name: str):
        """Called by the IDE when the user switches themes."""
        self._theme = "light" if theme_name == "light" else "dark"
        self._apply_vio_palette()
        # Redraw the canvas with the new theme
        if self._gates:
            self._redraw()
        else:
            try:
                old = self._canvas
                self._canvas = self._make_placeholder()
                self.scroll.setWidget(self._canvas)
                if old is not None and old is not self._canvas:
                    old.hide()
                    old.setParent(None)
            except RuntimeError:
                self._canvas = self._make_placeholder()
                self.scroll.setWidget(self._canvas)

    def _apply_vio_palette(self):
        """Apply header / toolbar / scroll stylesheet for current theme."""
        is_light = self._theme == "light"

        # Header
        if is_light:
            hdr_ss = (
                "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                "stop:0 #e3f0ff, stop:1 #dbeeff);"
                "border-bottom: 2px solid #1565c0;"
            )
            icon_color  = "#1565c0"
            title_color = "#0d47a1"
            count_color = "#546e7a"
        else:
            hdr_ss = (
                "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                "stop:0 #0d1b2a, stop:1 #12294a);"
                "border-bottom: 2px solid #1e88e5;"
            )
            icon_color  = "#4fc3f7"
            title_color = "#4fc3f7"
            count_color = "#546e7a"

        self._header.setStyleSheet(hdr_ss)
        self._icon_lbl.setStyleSheet(f"color: {icon_color};")
        self._title_lbl.setStyleSheet(
            f"color: {title_color}; font-family: 'Segoe UI'; "
            f"font-size: 13px; font-weight: bold; padding-left: 6px;"
        )
        self.gate_count_lbl.setStyleSheet(
            f"color: {count_color}; font-family: Consolas; font-size: 10px;"
        )

        # Toolbar
        if is_light:
            tb_ss = "background: #f0f4f8; border-bottom: 1px solid #d1d9e6;"
            btn_bg, btn_hov = "#1565c0", "#1976d2"
            zoom_ss = (
                "QComboBox { background: #ffffff; color: #1565c0; border: 1px solid #90caf9; "
                "border-radius: 4px; font-family: Consolas; font-size: 10px; padding: 2px 4px; }"
                "QComboBox::drop-down { border: none; }"
                "QComboBox QAbstractItemView { background: #ffffff; color: #1565c0; }"
            )
            legend_label_color = "#455a64"
        else:
            tb_ss = "background: #0a131d; border-bottom: 1px solid #162030;"
            btn_bg, btn_hov = "#1565c0", "#1976d2"
            zoom_ss = (
                "QComboBox { background: #0d1f33; color: #90caf9; border: 1px solid #1e4a8a; "
                "border-radius: 4px; font-family: Consolas; font-size: 10px; padding: 2px 4px; }"
                "QComboBox::drop-down { border: none; }"
                "QComboBox QAbstractItemView { background: #0d1f33; color: #90caf9; }"
            )
            legend_label_color = "#546e7a"

        self._toolbar.setStyleSheet(tb_ss)
        self.parse_btn.setStyleSheet(self._btn(btn_bg, btn_hov))
        self.zoom_combo.setStyleSheet(zoom_ss)
        self._zoom_lbl.setStyleSheet(f"color: {legend_label_color}; font-family: 'Segoe UI'; font-size: 10px;")

        # Legend dot colors
        palette = GATE_COLORS_LIGHT if is_light else GATE_COLORS_DARK
        for gtype, dot in self._legend_dots:
            _, accent, _ = palette.get(gtype, ("#000", "#666", "#aaa"))
            dot.setStyleSheet(f"color: {accent}; font-size: 10px;")
        for lbl in self._legend_lbls:
            lbl.setStyleSheet(f"color: {legend_label_color}; font-family: Consolas; font-size: 9px; margin-right: 6px;")

        # Scroll area
        if is_light:
            scroll_bg = "#f8fafc"
            scroll_handle = "#b0bec5"
        else:
            scroll_bg = "#0b0f14"
            scroll_handle = "#1e3a5c"
        self.scroll.setStyleSheet(
            f"QScrollArea {{ background: {scroll_bg}; border: none; }}"
            f"QScrollBar:vertical   {{ background: {scroll_bg}; width: 10px; }}"
            f"QScrollBar::handle:vertical {{ background: {scroll_handle}; border-radius: 5px; }}"
            f"QScrollBar:horizontal {{ background: {scroll_bg}; height: 10px; }}"
            f"QScrollBar::handle:horizontal {{ background: {scroll_handle}; border-radius: 5px; }}"
        )

    def load_module(self, verilog_code: str, module_name: str = ""):
        parser = VerilogGateParser()
        gates = parser.parse(verilog_code)
        self._gates = gates
        self._redraw(module_name)

    def _redraw(self, module_name=""):
        if self._gates:
            canvas = GateCanvas(self._gates, theme=self._theme)
            self._apply_zoom(canvas)
        else:
            canvas = GateCanvas([], theme=self._theme)   # shows "no gates" message

        self._canvas = canvas
        self.scroll.setWidget(canvas)

        n = len(self._gates)
        types = {}
        for g in self._gates:
            types[g.gate_type] = types.get(g.gate_type, 0) + 1
        summary = "  ".join(f"{k}:{v}" for k, v in types.items())
        self.gate_count_lbl.setText(
            f"{module_name}  │  {n} gate{'s' if n!=1 else ''}  {summary}"
        )

    def _apply_zoom(self, canvas: GateCanvas):
        z = self._zoom
        canvas.setFixedSize(
            int(canvas._total_w * z),
            int(canvas._total_h * z)
        )
        canvas.setTransform = lambda *a, **kw: None   # no-op (we scale via size)
        if z != 1.0:
            # Re-scale gate positions
            for g in canvas.gates:
                g.x = int(g.x * z)
                g.y = int(g.y * z)
                g.w = int(g.w * z)
                g.h = int(g.h * z)

    def _on_zoom_changed(self, text):
        try:
            self._zoom = int(text.replace('%', '')) / 100.0
        except Exception:
            self._zoom = 1.0
        if self._gates:
            self._redraw()

    # ── helpers ────────────────────────────────────────────────────────────
    @staticmethod
    def _btn(bg, hover):
        return (
            f"QPushButton {{ background: {bg}; color: #bbdefb; "
            f"border: 1px solid {hover}; border-radius: 4px; "
            f"padding: 3px 12px; font-family: 'Segoe UI'; font-size: 11px; }}"
            f"QPushButton:hover {{ background: {hover}; }}"
        )

    # ── Stubs kept for compatibility with main.py calls ───────────────────
    def get_input_values(self):
        return {}

    def update_simulation_result(self, port_values):
        pass

    def set_status(self, text, color="#aaaaaa"):
        pass

    def set_idle(self):
        pass
