import sys
import os
import json
import subprocess
import urllib.request
import urllib.error
import re
import shutil
from example_codes import EXAMPLES
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QPlainTextEdit, QFileDialog, QDockWidget, QListWidget,
    QTreeView, QMenu, QMenuBar, QToolBar, QTextEdit,
    QPushButton, QLabel, QSplitter, QComboBox, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QGroupBox, QDialog, QFormLayout,
    QDialogButtonBox, QLineEdit, QInputDialog, QScrollArea, QFrame, QSizePolicy
)
import html
from PyQt6.QtGui import QAction, QKeySequence, QFont, QIcon, QColor, QPainter, QPen, QFileSystemModel, QTextFormat
from PyQt6.QtCore import Qt, QDir, QSize, QRect, QThread, pyqtSignal, QProcess, QByteArray

OLLAMA_CLOUD_API_KEY = "949a3f58fcfb475ebd95be644b8aa7b1.Wex8pxkLXUrUGqQKBPWDSEyD"
OLLAMA_CLOUD_BASE_URL = "https://ollama.com"

class OllamaWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, model, messages, api_key=None, base_url=None, max_tokens=4096):
        super().__init__()
        self.model = model
        self.messages = messages
        self.api_key = api_key or OLLAMA_CLOUD_API_KEY
        self.base_url = (base_url or OLLAMA_CLOUD_BASE_URL).rstrip('/')
        self.max_tokens = max_tokens

    def stop(self):
        self.terminate()

    def run(self):
        url = f"{self.base_url}/api/chat"
        data = {
            "model": self.model,
            "messages": self.messages,
            "stream": False,
            "options": {"num_predict": self.max_tokens}
        }
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }

        try:
            req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode('utf-8'))
                self.finished.emit(result.get("message", {}).get("content", ""))
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='replace')
            self.error.emit(f"HTTP {e.code} Error: {body}")
        except urllib.error.URLError as e:
            self.error.emit(f"Connection failed: {str(e)}")
        except Exception as e:
            self.error.emit(f"An error occurred: {str(e)}")

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor

    def sizeHint(self):
        return QSize(self.codeEditor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.codeEditor.lineNumberAreaPaintEvent(event)

class CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = QFont("Consolas", 12)
        self.setFont(font)
        
        self.lineNumberArea = LineNumberArea(self)
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.updateLineNumberAreaWidth(0)

    def lineNumberAreaWidth(self):
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num //= 10
            digits += 1
        return 5 + self.fontMetrics().horizontalAdvance('9') * digits

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QColor("#333333")) # Dark background for line numbers
        
        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                painter.setPen(QColor("#aaaaaa"))
                painter.drawText(0, top, self.lineNumberArea.width() - 2, self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            blockNumber += 1
            
    def focusInEvent(self, event):
        super().focusInEvent(event)
        main_win = self.window()
        if hasattr(main_win, 'last_focused_tabs'):
            if main_win.editor_tabs.indexOf(self) != -1:
                main_win.last_focused_tabs = main_win.editor_tabs
            elif main_win.editor_tabs_right.indexOf(self) != -1:
                main_win.last_focused_tabs = main_win.editor_tabs_right

class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Project")
        self.resize(500, 150)
        self.layout = QFormLayout(self)
        
        self.name_input = QLineEdit()
        self.loc_input = QLineEdit()
        self.loc_input.setText(os.getcwd())
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse)
        
        loc_layout = QHBoxLayout()
        loc_layout.addWidget(self.loc_input)
        loc_layout.addWidget(browse_btn)
        
        self.vc_checkbox = QCheckBox("Enable Version Control (Track Changes)")
        self.vc_checkbox.setChecked(True)
        
        self.layout.addRow("Project Name:", self.name_input)
        self.layout.addRow("Location:", loc_layout)
        self.layout.addRow("", self.vc_checkbox)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addRow(self.buttons)
        
    def browse(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Location")
        if dir_path:
            self.loc_input.setText(dir_path)

class VersionHistoryDialog(QDialog):
    def __init__(self, proj_dir, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Change Tracker History")
        self.resize(900, 600)
        self.proj_dir = proj_dir
        
        layout = QHBoxLayout(self)
        left_layout = QVBoxLayout()
        self.list_widget = QListWidget()
        self.list_widget.setFixedWidth(250)
        self.list_widget.currentRowChanged.connect(self.on_select)
        
        self.revert_btn = QPushButton("Revert Project to Selected Change")
        self.revert_btn.clicked.connect(self.revert_change)
        
        left_layout.addWidget(self.list_widget)
        left_layout.addWidget(self.revert_btn)
        
        self.diff_view = QTextEdit()
        self.diff_view.setReadOnly(True)
        font = QFont("Consolas", 11)
        self.diff_view.setFont(font)
        self.diff_view.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        
        layout.addLayout(left_layout)
        layout.addWidget(self.diff_view)
        
        self.commits = []
        self.load_history()
        
    def load_history(self):
        res = subprocess.run(["git", "log", "--oneline"], cwd=self.proj_dir, capture_output=True, text=True)
        if res.returncode == 0:
            for line in res.stdout.strip().split('\n'):
                if line:
                    parts = line.split(' ', 1)
                    if len(parts) == 2:
                        self.commits.append((parts[0], parts[1]))
                        self.list_widget.addItem(parts[1])
                        
    def on_select(self, row):
        if row < 0 or row >= len(self.commits): return
        commit_hash = self.commits[row][0]
        res = subprocess.run(["git", "show", commit_hash], cwd=self.proj_dir, capture_output=True, text=True)
        if res.returncode == 0:
            diff_text = res.stdout
            html_content = "<pre style='font-family: Consolas;'>"
            for line in diff_text.split('\n'):
                escaped = html.escape(line)
                if line.startswith('+') and not line.startswith('+++'):
                    html_content += f"<span style='color: #4CAF50;'>{escaped}</span><br>"
                elif line.startswith('-') and not line.startswith('---'):
                    html_content += f"<span style='color: #F44336;'>{escaped}</span><br>"
                elif line.startswith('@@'):
                    html_content += f"<span style='color: #2196F3;'>{escaped}</span><br>"
                else:
                    html_content += f"{escaped}<br>"
            html_content += "</pre>"
            self.diff_view.setHtml(html_content)
            
    def revert_change(self):
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.commits): return
        commit_hash = self.commits[row][0]
        
        reply = QMessageBox.question(self, "Revert Project", f"Are you sure you want to revert the entire project to {commit_hash}? Uncommitted changes will be lost.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                subprocess.run(["git", "reset", "--hard", commit_hash], cwd=self.proj_dir, capture_output=True)
                QMessageBox.information(self, "Reverted", "Project successfully reverted.\nPlease close and reopen your files to see the changes.")
                self.accept()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to revert: {e}")

from waveform_viewer import WaveformViewer
from vio_dashboard import VIODashboard


class TerminalWidget(QWidget):
    """A VS Code-style integrated terminal.
    
    Each command is run as a fresh subprocess (cmd /c or powershell -Command)
    so output is always captured and displayed reliably on Windows.
    The current working directory is tracked locally and updated by `cd` commands.
    """

    # Theme palette (can be overridden by apply_theme)
    DARK = {
        "bar_bg": "#252526",
        "bar_border": "#333333",
        "output_bg": "#1e1e1e",
        "output_fg": "#d4d4d4",
        "input_bg": "#252526",
        "input_fg": "#d4d4d4",
        "input_border": "#3a3a3a",
        "input_focus": "#4EC9B0",
        "prompt_color": "#4EC9B0",
        "btn_bg": "#3a3a3a",
        "btn_fg": "#cccccc",
        "btn_border": "#555555",
        "btn_hover": "#505050",
        "label_fg": "#9CDCFE",
        "cwd_fg": "#888888",
        "prompt_text_color": "#4EC9B0",
        "error_color": "#F44747",
    }
    LIGHT = {
        "bar_bg": "#f3f3f3",
        "bar_border": "#d1d9e6",
        "output_bg": "#ffffff",
        "output_fg": "#1e1e1e",
        "input_bg": "#f8f8f8",
        "input_fg": "#1e1e1e",
        "input_border": "#c8c8c8",
        "input_focus": "#007acc",
        "prompt_color": "#007acc",
        "btn_bg": "#e8e8e8",
        "btn_fg": "#333333",
        "btn_border": "#c0c0c0",
        "btn_hover": "#d0d0d0",
        "label_fg": "#005a9e",
        "cwd_fg": "#555555",
        "prompt_text_color": "#007acc",
        "error_color": "#cc0000",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: list[str] = []
        self._hist_idx: int = -1
        self._running_proc: QProcess | None = None   # currently executing command
        self._cwd: str = os.getcwd()
        self._colors = dict(self.DARK)
        self._setup_ui()
        self._print_banner()

    # ── UI ──────────────────────────────────────────────────────────
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top toolbar ─────────────────────────────────────────────
        bar = QHBoxLayout()
        bar.setContentsMargins(6, 4, 6, 4)

        self._shell_label = QLabel()

        self._cwd_label = QLabel()
        self._cwd_label.setWordWrap(False)
        self._cwd_label.setText(self._cwd)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFixedWidth(60)
        self._clear_btn.clicked.connect(self._clear_output)

        self._kill_btn = QPushButton("⏹ Kill")
        self._kill_btn.setFixedWidth(64)
        self._kill_btn.setToolTip("Kill the running command")
        self._kill_btn.setEnabled(False)
        self._kill_btn.clicked.connect(self._kill_process)

        bar.addWidget(self._shell_label)
        bar.addSpacing(10)
        bar.addWidget(self._cwd_label)
        bar.addStretch()
        bar.addWidget(self._kill_btn)
        bar.addWidget(self._clear_btn)

        self._bar_widget = QWidget()
        self._bar_widget.setLayout(bar)
        root.addWidget(self._bar_widget)

        # ── Output display ──────────────────────────────────────────
        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self._output.setFont(QFont("Consolas", 11))
        self._output.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        root.addWidget(self._output, stretch=1)

        # ── Input row ───────────────────────────────────────────────
        input_row = QHBoxLayout()
        input_row.setContentsMargins(4, 2, 4, 4)
        input_row.setSpacing(4)

        self._prompt_label = QLabel("❯")
        self._prompt_label.setFont(QFont("Consolas", 13))
        input_row.addWidget(self._prompt_label)

        self._input = QLineEdit()
        self._input.setFont(QFont("Consolas", 11))
        self._input.setPlaceholderText("Type a command and press Enter…")
        self._input.returnPressed.connect(self._send_command)
        self._input.installEventFilter(self)
        input_row.addWidget(self._input)

        self._input_widget = QWidget()
        self._input_widget.setLayout(input_row)
        root.addWidget(self._input_widget)

        self._apply_palette()  # set colors for the first time

    def _print_banner(self):
        exe = self._shell_executable()
        shell_name = "PowerShell" if "powershell" in exe.lower() else "CMD"
        self._shell_label.setText(f"⚡ {shell_name}")
        self._append_text(
            f"[Terminal] {shell_name} — each command runs as a subprocess.\n"
            f"  Working dir: {self._cwd}\n"
            f"  Use 'cd <path>' to change directory.\n",
            color="info"
        )

    # ── Theme ────────────────────────────────────────────────────────
    def apply_theme(self, theme_name: str):
        """Switch between 'light' and 'dark' terminal colour palette."""
        self._colors = dict(self.LIGHT if theme_name == "light" else self.DARK)
        self._apply_palette()

    def _apply_palette(self):
        c = self._colors
        self._bar_widget.setStyleSheet(
            f"background:{c['bar_bg']}; border-bottom:1px solid {c['bar_border']};"
        )
        self._shell_label.setStyleSheet(
            f"color:{c['label_fg']}; font-weight:bold; font-family:Consolas;"
        )
        self._cwd_label.setStyleSheet(
            f"color:{c['cwd_fg']}; font-family:Consolas; font-size:10px;"
        )
        btn_ss = (
            f"QPushButton{{background:{c['btn_bg']};color:{c['btn_fg']};"
            f"border:1px solid {c['btn_border']};border-radius:3px;padding:2px 6px;}}"
            f"QPushButton:hover{{background:{c['btn_hover']};}}"
        )
        self._clear_btn.setStyleSheet(btn_ss)
        self._kill_btn.setStyleSheet(btn_ss)
        self._output.setStyleSheet(
            f"QPlainTextEdit{{background:{c['output_bg']};color:{c['output_fg']};border:none;}}"
        )
        self._prompt_label.setStyleSheet(
            f"color:{c['prompt_color']}; font-weight:bold;"
        )
        self._input.setStyleSheet(
            f"QLineEdit{{background:{c['input_bg']};color:{c['input_fg']};"
            f"border:1px solid {c['input_border']};border-radius:3px;padding:3px 6px;}}"
            f"QLineEdit:focus{{border:1px solid {c['input_focus']};}}"
        )
        self._input_widget.setStyleSheet(f"background:{c['output_bg']};")

    # ── Shell helpers ────────────────────────────────────────────────
    def _shell_executable(self) -> str:
        ps = shutil.which("powershell.exe") or shutil.which("powershell")
        return ps if ps else "cmd.exe"

    def _build_args(self, cmd: str) -> tuple[str, list[str]]:
        """Return (exe, args) to run `cmd` as a one-shot subprocess.
        
        Uses cmd.exe /c by default – most reliable on Windows for all
        path forms (spaces, drive letters, UNC, etc.).
        If the user explicitly wants PowerShell, they can prefix with 'ps:'.
        """
        # Allow ps: prefix to explicitly use PowerShell
        if cmd.lower().startswith("ps:"):
            ps_cmd = cmd[3:].strip()
            exe = self._shell_executable()
            # PowerShell: use escaped double-quotes and cd via push
            full = f'Push-Location "{self._cwd}"; {ps_cmd}; Pop-Location'
            return exe, ["-NoLogo", "-NonInteractive", "-Command", full]
        # Default: cmd.exe /c — handles spaces and all drive paths fine
        return "cmd.exe", ["/c", f'cd /d "{self._cwd}" && {cmd}']

    # ── Commands ────────────────────────────────────────────────────
    def _send_command(self):
        cmd = self._input.text().strip()
        if not cmd:
            return

        # Echo the typed command
        self._append_text(f"❯ {cmd}\n", color="prompt")

        # History
        if not self._history or self._history[-1] != cmd:
            self._history.append(cmd)
        self._hist_idx = -1
        self._input.clear()
        self._input.setEnabled(False)

        # Handle built-in `cd` so the cwd persists for next commands
        cd_match = re.match(r'^cd\s+(.+)$', cmd, re.IGNORECASE)
        if cd_match:
            target = cd_match.group(1).strip().strip('"').strip("'")
            new_path = target if os.path.isabs(target) else os.path.join(self._cwd, target)
            new_path = os.path.normpath(new_path)
            if os.path.isdir(new_path):
                self._cwd = new_path
                self._cwd_label.setText(new_path)
                self._append_text(f"Changed directory to: {new_path}\n", color="info")
            else:
                self._append_text(f"cd: No such directory: {new_path}\n", color="error")
            self._input.setEnabled(True)
            self._input.setFocus()
            return

        exe, args = self._build_args(cmd)
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.readyReadStandardOutput.connect(lambda: self._on_proc_output(proc))
        proc.finished.connect(lambda code, status: self._on_proc_finished(proc, code))
        proc.setWorkingDirectory(self._cwd)
        proc.start(exe, args)

        if proc.waitForStarted(3000):
            self._running_proc = proc
            self._kill_btn.setEnabled(True)
        else:
            self._append_text(f"[Terminal] Failed to start: {exe}\n", color="error")
            self._input.setEnabled(True)
            self._input.setFocus()

    def _kill_process(self):
        if self._running_proc and self._running_proc.state() != QProcess.ProcessState.NotRunning:
            self._running_proc.kill()
            self._append_text("[Terminal] Process killed.\n", color="error")

    def _clear_output(self):
        self._output.clear()

    # ── CWD control (called by IDE when project opens) ───────────────
    def set_cwd(self, path: str):
        self._cwd = path
        self._cwd_label.setText(path)
        self._append_text(f"[Terminal] Working directory set to: {path}\n", color="info")

    # ── Output handling ─────────────────────────────────────────────
    def _on_proc_output(self, proc: QProcess):
        raw: QByteArray = proc.readAllStandardOutput()
        try:
            text = raw.data().decode("utf-8", errors="replace")
        except Exception:
            text = str(raw.data())
        # Strip ANSI escape codes
        text = re.sub(r'\x1b\[[0-9;]*[mGKHFJK]', '', text)
        # Also strip PowerShell's \r
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        self._append_text(text)

    def _on_proc_finished(self, proc: QProcess, exit_code: int):
        # Flush remaining output
        self._on_proc_output(proc)
        if exit_code != 0:
            self._append_text(f"[Exit code: {exit_code}]\n", color="error")
        self._running_proc = None
        self._kill_btn.setEnabled(False)
        self._input.setEnabled(True)
        self._input.setFocus()

    def _append_text(self, text: str, color: str = "normal"):
        """color: 'normal' | 'prompt' | 'error' | 'info'"""
        cursor = self._output.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        fmt = self._output.currentCharFormat()
        c = self._colors
        if color == "prompt":
            fmt.setForeground(QColor(c["prompt_text_color"]))
        elif color == "error":
            fmt.setForeground(QColor(c["error_color"]))
        elif color == "info":
            fg = QColor(c["output_fg"])
            fg.setAlpha(160)
            fmt.setForeground(fg)
        else:
            fmt.setForeground(QColor(c["output_fg"]))
        cursor.setCharFormat(fmt)
        cursor.insertText(text)
        self._output.setTextCursor(cursor)
        self._output.ensureCursorVisible()

    # ── Arrow-key history navigation ────────────────────────────────
    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Up:
                if self._history:
                    if self._hist_idx == -1:
                        self._hist_idx = len(self._history) - 1
                    elif self._hist_idx > 0:
                        self._hist_idx -= 1
                    self._input.setText(self._history[self._hist_idx])
                return True
            elif key == Qt.Key.Key_Down:
                if self._hist_idx != -1:
                    self._hist_idx += 1
                    if self._hist_idx >= len(self._history):
                        self._hist_idx = -1
                        self._input.clear()
                    else:
                        self._input.setText(self._history[self._hist_idx])
                return True
        return super().eventFilter(obj, event)


# ── Provider URL presets ─────────────────────────────────────────────────────
PROVIDER_URLS = {
    "Ollama":         "https://ollama.com",
    "Google Gemini":  "https://generativelanguage.googleapis.com/v1beta",
    "OpenAI":         "https://api.openai.com/v1",
    "Anthropic":      "https://api.anthropic.com/v1",
    "Custom":         "",
}

API_KEYS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_keys.json")


class APIKeyManagerDialog(QDialog):
    """Manage named API key profiles. Keys are stored in api_keys.json."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("API Key Manager")
        self.resize(780, 460)
        self.setMinimumSize(640, 380)
        self._profiles = []        # list of dicts
        self._current_row = -1
        self._load_profiles()
        self._build_ui()
        self._refresh_list()
        if self._profiles:
            self._list.setCurrentRow(0)

    # ── Data I/O ──────────────────────────────────────────────────────────────
    def _load_profiles(self):
        if os.path.exists(API_KEYS_FILE):
            try:
                with open(API_KEYS_FILE, "r") as f:
                    data = json.load(f)
                self._profiles = data.get("keys", [])
            except Exception:
                self._profiles = []
        if not self._profiles:
            # seed with the built-in default
            self._profiles = [{
                "name": "Ollama Cloud (default)",
                "provider": "Ollama",
                "base_url": OLLAMA_CLOUD_BASE_URL,
                "key": OLLAMA_CLOUD_API_KEY,
                "model": "llama3.2",
            }]

    def _save_profiles(self):
        try:
            existing = {}
            if os.path.exists(API_KEYS_FILE):
                with open(API_KEYS_FILE, "r") as f:
                    existing = json.load(f)
            existing["keys"] = self._profiles
            with open(API_KEYS_FILE, "w") as f:
                json.dump(existing, f, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "Save Error", f"Could not save keys: {e}")

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── Left panel: list ──────────────────────────────────────────────────
        left = QWidget()
        left.setFixedWidth(220)
        left.setStyleSheet("background:#1e1e1e;")
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(8, 8, 8, 8)
        left_lay.setSpacing(6)

        lbl = QLabel("Saved Keys")
        lbl.setStyleSheet("color:#9CDCFE; font-weight:bold; font-size:12px;")
        left_lay.addWidget(lbl)

        self._list = QListWidget()
        self._list.setStyleSheet(
            "QListWidget{background:#252526; color:#d4d4d4; border:1px solid #3a3a3a; border-radius:4px;}"
            "QListWidget::item{padding:6px 8px;}"
            "QListWidget::item:selected{background:#094771; color:#ffffff;}"
        )
        self._list.currentRowChanged.connect(self._on_select)
        left_lay.addWidget(self._list)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("＋ New")
        add_btn.setStyleSheet(self._btn_style("#0e639c"))
        add_btn.clicked.connect(self._add_new)
        self._del_btn = QPushButton("🗑 Delete")
        self._del_btn.setStyleSheet(self._btn_style("#6e1c1c"))
        self._del_btn.clicked.connect(self._delete_current)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(self._del_btn)
        left_lay.addLayout(btn_row)
        root.addWidget(left)

        # ── Divider ───────────────────────────────────────────────────────────
        div = QFrame()
        div.setFrameShape(QFrame.Shape.VLine)
        div.setStyleSheet("color:#3a3a3a;")
        root.addWidget(div)

        # ── Right panel: form ─────────────────────────────────────────────────
        right = QWidget()
        right.setStyleSheet("background:#252526;")
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(16, 16, 16, 16)
        right_lay.setSpacing(10)

        form_lbl = QLabel("Key Profile")
        form_lbl.setStyleSheet("color:#9CDCFE; font-weight:bold; font-size:13px;")
        right_lay.addWidget(form_lbl)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(8)

        label_style = "color:#cccccc; font-size:11px;"

        # Name
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. Gemini Pro")
        self._style_input(self._name_edit)
        name_lbl = QLabel("Name:")
        name_lbl.setStyleSheet(label_style)
        form.addRow(name_lbl, self._name_edit)

        # Provider
        self._provider_combo = QComboBox()
        self._provider_combo.addItems(list(PROVIDER_URLS.keys()))
        self._provider_combo.setStyleSheet(
            "QComboBox{background:#3c3c3c;color:#d4d4d4;border:1px solid #555;border-radius:3px;padding:4px;}"
            "QComboBox::drop-down{border:none;} QComboBox QAbstractItemView{background:#2d2d2d;color:#d4d4d4;}"
        )
        self._provider_combo.currentTextChanged.connect(self._on_provider_changed)
        prov_lbl = QLabel("Provider:")
        prov_lbl.setStyleSheet(label_style)
        form.addRow(prov_lbl, self._provider_combo)

        # Base URL
        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("https://...")
        self._style_input(self._url_edit)
        url_lbl = QLabel("Base URL:")
        url_lbl.setStyleSheet(label_style)
        form.addRow(url_lbl, self._url_edit)

        # API Key
        key_row = QHBoxLayout()
        self._key_edit = QLineEdit()
        self._key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_edit.setPlaceholderText("Paste API key here...")
        self._style_input(self._key_edit)
        show_btn = QPushButton("👁")
        show_btn.setFixedWidth(34)
        show_btn.setCheckable(True)
        show_btn.setStyleSheet("QPushButton{background:#3c3c3c;color:#ccc;border:1px solid #555;border-radius:3px;}"
                               "QPushButton:checked{background:#094771;}")
        show_btn.toggled.connect(lambda c: self._key_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if c else QLineEdit.EchoMode.Password))
        key_row.addWidget(self._key_edit)
        key_row.addWidget(show_btn)
        key_lbl = QLabel("API Key:")
        key_lbl.setStyleSheet(label_style)
        form.addRow(key_lbl, key_row)

        # Default Model
        self._model_edit = QLineEdit()
        self._model_edit.setPlaceholderText("e.g. llama3.2 / gemini-1.5-pro")
        self._style_input(self._model_edit)
        mod_lbl = QLabel("Default Model:")
        mod_lbl.setStyleSheet(label_style)
        form.addRow(mod_lbl, self._model_edit)

        right_lay.addLayout(form)
        right_lay.addStretch()

        # Save button
        save_btn = QPushButton("💾  Save Profile")
        save_btn.setStyleSheet(self._btn_style("#0e639c", pad="8px 20px"))
        save_btn.clicked.connect(self._save_current)
        right_lay.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignRight)

        # Close
        close_btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_btn.rejected.connect(self.reject)
        right_lay.addWidget(close_btn)

        root.addWidget(right)

    # ── Helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def _btn_style(bg, pad="4px 10px"):
        return (f"QPushButton{{background:{bg};color:#fff;border:none;border-radius:4px;"
                f"padding:{pad};font-size:11px;}}"
                f"QPushButton:hover{{background:{bg}cc;}}")

    @staticmethod
    def _style_input(w):
        w.setStyleSheet(
            "QLineEdit{background:#3c3c3c;color:#d4d4d4;border:1px solid #555;"
            "border-radius:3px;padding:5px 8px;font-family:Consolas;}"
            "QLineEdit:focus{border:1px solid #4EC9B0;}"
        )

    def _refresh_list(self):
        self._list.clear()
        for p in self._profiles:
            self._list.addItem(f"🔑  {p.get('name', 'Unnamed')}")

    def _on_select(self, row):
        self._current_row = row
        if 0 <= row < len(self._profiles):
            p = self._profiles[row]
            self._name_edit.setText(p.get("name", ""))
            # Set provider combo
            prov = p.get("provider", "Ollama")
            idx = self._provider_combo.findText(prov)
            self._provider_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self._url_edit.setText(p.get("base_url", ""))
            self._key_edit.setText(p.get("key", ""))
            self._model_edit.setText(p.get("model", ""))

    def _on_provider_changed(self, prov):
        preset = PROVIDER_URLS.get(prov, "")
        if preset:                 # only auto-fill for non-Custom
            self._url_edit.setText(preset)
            self._url_edit.setReadOnly(prov != "Custom")
        else:
            self._url_edit.setReadOnly(False)

    def _add_new(self):
        new_profile = {
            "name": "New Key",
            "provider": "Ollama",
            "base_url": OLLAMA_CLOUD_BASE_URL,
            "key": "",
            "model": "",
        }
        self._profiles.append(new_profile)
        self._refresh_list()
        self._list.setCurrentRow(len(self._profiles) - 1)

    def _save_current(self):
        row = self._list.currentRow()
        if row < 0:
            return
        name = self._name_edit.text().strip() or "Unnamed"
        self._profiles[row] = {
            "name": name,
            "provider": self._provider_combo.currentText(),
            "base_url": self._url_edit.text().strip(),
            "key": self._key_edit.text(),
            "model": self._model_edit.text().strip(),
        }
        self._save_profiles()
        self._refresh_list()
        self._list.setCurrentRow(row)
        QMessageBox.information(self, "Saved", f"Profile '{name}' saved.")

    def _delete_current(self):
        row = self._list.currentRow()
        if row < 0:
            return
        name = self._profiles[row].get("name", "?")
        reply = QMessageBox.question(self, "Delete", f"Delete profile '{name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self._profiles.pop(row)
            self._save_profiles()
            self._refresh_list()
            if self._profiles:
                self._list.setCurrentRow(min(row, len(self._profiles) - 1))


class VerilogIDE(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Verilog Studio IDE (Vivado Style)")
        self.resize(1280, 800)
        self.setCorner(Qt.Corner.BottomRightCorner, Qt.DockWidgetArea.RightDockWidgetArea)
        self.setCorner(Qt.Corner.TopRightCorner, Qt.DockWidgetArea.RightDockWidgetArea)
        self.current_project_dir = None
        self.chat_history = []
        
        self.load_themes()
        self.setup_ui()
        self.apply_theme("light")
        self.load_config()
        
    def load_config(self):
        self.config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ide_config.json")
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    config = json.load(f)
                    last_proj = config.get("last_project")
                    if last_proj and os.path.exists(last_proj):
                        self.set_project_dir(last_proj)
            except: pass

    def save_config(self, key, value):
        config = {}
        if hasattr(self, 'config_path') and os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    config = json.load(f)
            except: pass
        config[key] = value
        try:
            with open(getattr(self, 'config_path', os.path.join(os.path.dirname(os.path.abspath(__file__)), "ide_config.json")), "w") as f:
                json.dump(config, f)
        except: pass
        
    def load_themes(self):
        self.themes = {}
        try:
            with open("theme.json", "r") as f:
                self.themes = json.load(f)
        except Exception as e:
            print(f"Error loading theme: {e}")
            
    def apply_theme(self, theme_name):
        if theme_name in self.themes:
            stylesheet = self.themes[theme_name].get("stylesheet", "")
            self.setStyleSheet(stylesheet)
        # Propagate theme to terminal, VIO board, and AI panel
        if hasattr(self, 'terminal_widget'):
            self.terminal_widget.apply_theme(theme_name)
        if hasattr(self, 'vio_dashboard'):
            self.vio_dashboard.apply_theme(theme_name)
        if hasattr(self, '_ai_theme_name'):
            self._ai_theme_name = theme_name
            self._apply_ai_palette()

    def _apply_ai_palette(self):
        """Apply light or dark colors to all AI Coding Assistant panel widgets."""
        t = getattr(self, '_ai_theme_name', 'light')
        is_light = (t == 'light')

        if is_light:
            panel_bg       = "#f5f7fa"
            header_bg      = "#e8edf5"
            header_border  = "#c8d4e8"
            chat_bg        = "#f0f4fb"
            input_bar_bg   = "#e8edf5"
            input_bar_bdr  = "#c8d4e8"
            combo_bg       = "#ffffff"
            combo_fg       = "#1a1a2e"
            combo_border   = "#b0bec5"
            combo_dd_bg    = "#f0f4fb"
            input_bg       = "#ffffff"
            input_fg       = "#1a1a2e"
            input_border   = "#b0bec5"
            input_focus    = "#1565c0"
            lbl_fg         = "#0d47a1"
            ctx_fg         = "#546e7a"
            scroll_bg      = "#f0f4fb"
            scroll_handle  = "#90a4ae"
            send_bg        = "#1565c0"
            send_hover     = "#1976d2"
            send_disabled  = "#b0bec5"
            send_dis_fg    = "#78909c"
            stop_bg        = "#c62828"
            stop_hover     = "#d32f2f"
            btn_bg         = "#e3eaf5"
            btn_fg         = "#1a3a6a"
            btn_border     = "#90a4ae"
            btn_hover      = "#ccd8ee"
        else:
            panel_bg       = "#1e1e1e"
            header_bg      = "#252526"
            header_border  = "#3a3a3a"
            chat_bg        = "#1e1e1e"
            input_bar_bg   = "#252526"
            input_bar_bdr  = "#3a3a3a"
            combo_bg       = "#3c3c3c"
            combo_fg       = "#d4d4d4"
            combo_border   = "#555555"
            combo_dd_bg    = "#2d2d2d"
            input_bg       = "#3c3c3c"
            input_fg       = "#d4d4d4"
            input_border   = "#555555"
            input_focus    = "#4EC9B0"
            lbl_fg         = "#9CDCFE"
            ctx_fg         = "#888888"
            scroll_bg      = "#252526"
            scroll_handle  = "#555555"
            send_bg        = "#0e639c"
            send_hover     = "#1177bb"
            send_disabled  = "#3c3c3c"
            send_dis_fg    = "#666666"
            stop_bg        = "#5c2020"
            stop_hover     = "#7a2a2a"
            btn_bg         = "#3c3c3c"
            btn_fg         = "#d4d4d4"
            btn_border     = "#555555"
            btn_hover      = "#505050"

        combo_ss = (
            f"QComboBox{{background:{combo_bg};color:{combo_fg};border:1px solid {combo_border};"
            f"border-radius:3px;padding:3px 6px;font-size:11px;}}"
            f"QComboBox::drop-down{{border:none;}}"
            f"QComboBox QAbstractItemView{{background:{combo_dd_bg};color:{combo_fg};}}"
        )
        btn_ss = (
            f"QPushButton{{background:{btn_bg};color:{btn_fg};border:1px solid {btn_border};"
            f"border-radius:4px;padding:3px 8px;}}"
            f"QPushButton:hover{{background:{btn_hover};}}"
        )

        if hasattr(self, '_ai_widget'):
            self._ai_widget.setStyleSheet(f"background:{panel_bg};")
        if hasattr(self, '_ai_header'):
            self._ai_header.setStyleSheet(
                f"background:{header_bg}; border-bottom:1px solid {header_border};"
            )
        if hasattr(self, '_ai_key_icon'):
            self._ai_key_icon.setStyleSheet(f"color:{lbl_fg};font-size:11px;font-weight:bold;")
        if hasattr(self, '_ai_model_lbl'):
            self._ai_model_lbl.setStyleSheet(f"color:{lbl_fg};font-size:11px;font-weight:bold;")
        if hasattr(self, '_ai_ctx_lbl'):
            self._ai_ctx_lbl.setStyleSheet(f"color:{ctx_fg};font-size:10px;")
        if hasattr(self, '_ai_ctx_lbl2'):
            self._ai_ctx_lbl2.setStyleSheet(f"color:{ctx_fg};font-size:10px;")
        if hasattr(self, 'ai_key_combo'):
            self.ai_key_combo.setStyleSheet(combo_ss)
        if hasattr(self, 'ai_model_combo'):
            self.ai_model_combo.setStyleSheet(combo_ss)
        if hasattr(self, 'ai_ctx_combo'):
            self.ai_ctx_combo.setStyleSheet(combo_ss)
        if hasattr(self, '_ai_manage_btn'):
            self._ai_manage_btn.setStyleSheet(btn_ss)
        if hasattr(self, 'ai_refresh_btn'):
            self.ai_refresh_btn.setStyleSheet(btn_ss)
        if hasattr(self, 'ai_scroll'):
            self.ai_scroll.setStyleSheet(
                f"QScrollArea{{border:none; background:{scroll_bg};}}"
                f"QScrollBar:vertical{{background:{scroll_bg};width:8px;border-radius:4px;}}"
                f"QScrollBar::handle:vertical{{background:{scroll_handle};border-radius:4px;min-height:20px;}}"
            )
        if hasattr(self, 'ai_chat_container'):
            self.ai_chat_container.setStyleSheet(f"background:{chat_bg};")
        if hasattr(self, '_ai_input_bar'):
            self._ai_input_bar.setStyleSheet(
                f"background:{input_bar_bg}; border-top:1px solid {input_bar_bdr};"
            )
        if hasattr(self, 'ai_input'):
            self.ai_input.setStyleSheet(
                f"QTextEdit{{background:{input_bg};color:{input_fg};border:1px solid {input_border};"
                f"border-radius:4px;padding:4px 8px;font-family:Consolas;}}"
                f"QTextEdit:focus{{border:1px solid {input_focus};}}"
            )
        if hasattr(self, 'ai_send_btn'):
            self.ai_send_btn.setStyleSheet(
                f"QPushButton{{background:{send_bg};color:#fff;border:none;border-radius:4px;font-weight:bold;}}"
                f"QPushButton:hover{{background:{send_hover};}}"
                f"QPushButton:disabled{{background:{send_disabled};color:{send_dis_fg};}}"
            )
        if hasattr(self, 'ai_stop_btn'):
            self.ai_stop_btn.setStyleSheet(
                f"QPushButton{{background:{stop_bg};color:#fff;border:none;border-radius:4px;font-weight:bold;}}"
                f"QPushButton:hover{{background:{stop_hover};}}"
                f"QPushButton:disabled{{background:{send_disabled};color:{send_dis_fg};}}"
            )
        # Console toolbar buttons
        console_btn_ss = (
            f"QPushButton{{background:{btn_bg};color:{btn_fg};border:1px solid {btn_border};"
            f"border-radius:4px;padding:2px 10px;font-size:9pt;}}"
            f"QPushButton:hover{{background:{btn_hover};}}"
        )
        if hasattr(self, '_console_send_ai_btn'):
            self._console_send_ai_btn.setStyleSheet(console_btn_ss)
        if hasattr(self, '_console_clear_btn'):
            self._console_clear_btn.setStyleSheet(console_btn_ss)


    def setup_ui(self):
        # Menu Bar
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        edit_menu = menubar.addMenu("Edit")
        view_menu = menubar.addMenu("View")
        run_menu = menubar.addMenu("Run")
        
        # File Actions
        new_proj_act = QAction("New Project", self)
        new_proj_act.triggered.connect(self.new_project)
        file_menu.addAction(new_proj_act)
        
        open_proj_act = QAction("Open Project", self)
        open_proj_act.triggered.connect(self.open_project)
        file_menu.addAction(open_proj_act)
        
        new_file_act = QAction("New File", self)
        new_file_act.setShortcut("Ctrl+N")
        new_file_act.triggered.connect(self.new_file)
        file_menu.addAction(new_file_act)

        save_file_act = QAction("Save", self)
        save_file_act.setShortcut("Ctrl+S")
        save_file_act.triggered.connect(self.save_file)
        file_menu.addAction(save_file_act)
        
        # Edit Actions
        undo_act = QAction("Undo", self)
        undo_act.setShortcut(QKeySequence.StandardKey.Undo)
        undo_act.triggered.connect(self.undo_edit)
        edit_menu.addAction(undo_act)

        redo_act = QAction("Redo", self)
        redo_act.setShortcut(QKeySequence.StandardKey.Redo)
        redo_act.triggered.connect(self.redo_edit)
        edit_menu.addAction(redo_act)

        edit_menu.addSeparator()
        manage_keys_act = QAction("🔑  Manage API Keys…", self)
        manage_keys_act.setShortcut("Ctrl+Shift+K")
        manage_keys_act.triggered.connect(self.show_api_key_manager)
        edit_menu.addAction(manage_keys_act)
        
        # View Actions (Themes)
        # View Actions
        split_act = QAction("Toggle Split Editor", self)
        split_act.setShortcut("Ctrl+\\")
        split_act.triggered.connect(self.toggle_split_editor)
        view_menu.addAction(split_act)
        
        self.windows_menu = view_menu.addMenu("Windows")
        
        theme_menu = view_menu.addMenu("Theme")
        for t in ["light", "dark", "gray"]:
            act = QAction(t.capitalize(), self)
            act.triggered.connect(lambda checked, name=t: self.apply_theme(name))
            theme_menu.addAction(act)
            
        # Examples Menu
        examples_menu = menubar.addMenu("Examples")
        for ex_folder in ["full_adder", "half_adder", "logic_gates", "blinking_led"]:
            act = QAction(ex_folder.replace("_", " ").title(), self)
            act.triggered.connect(lambda checked, name=ex_folder: self.load_example(name))
            examples_menu.addAction(act)
            
        # Run Actions
        compile_act = QAction("Run Synthesis/Simulation", self)
        compile_act.setShortcut("F5")
        compile_act.triggered.connect(self.run_simulation)
        run_menu.addAction(compile_act)

        # Help Menu
        help_menu = menubar.addMenu("Help")
        doc_act = QAction("Documentation (How to Code)", self)
        doc_act.triggered.connect(self.show_documentation)
        help_menu.addAction(doc_act)
        
        history_act = QAction("View Change History", self)
        history_act.triggered.connect(self.show_history)
        view_menu.addAction(history_act)
        
        vc_menu = menubar.addMenu("Version Control")
        commit_all_act = QAction("Commit All", self)
        commit_all_act.triggered.connect(lambda: self.commit_changes("All"))
        vc_menu.addAction(commit_all_act)
        
        commit_cur_act = QAction("Commit Current File", self)
        commit_cur_act.triggered.connect(lambda: self.commit_changes("Current"))
        vc_menu.addAction(commit_cur_act)

        # Tool Bar
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        
        toolbar.addAction(save_file_act)
        toolbar.addSeparator()
        toolbar.addAction(undo_act)
        toolbar.addAction(redo_act)
        toolbar.addSeparator()
        toolbar.addAction(compile_act)
        toolbar.addSeparator()
        toolbar.addAction(commit_all_act)
        toolbar.addAction(commit_cur_act)

        # Central Widget (Multi-tab Editor with Splitter)
        self.editor_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        self.editor_tabs = QTabWidget()
        self.editor_tabs.setTabsClosable(True)
        self.editor_tabs.tabCloseRequested.connect(self.close_tab)
        
        self.editor_tabs_right = QTabWidget()
        self.editor_tabs_right.setTabsClosable(True)
        self.editor_tabs_right.tabCloseRequested.connect(self.close_tab_right)
        self.editor_tabs_right.hide() # Hidden by default
        
        self.editor_splitter.addWidget(self.editor_tabs)
        self.editor_splitter.addWidget(self.editor_tabs_right)
        self.setCentralWidget(self.editor_splitter)
        
        self.last_focused_tabs = self.editor_tabs
        
        # Dock: Project Explorer
        self.proj_dock = QDockWidget("Project Explorer", self)
        self.file_system_model = QFileSystemModel()
        self.file_system_model.setRootPath("")
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.file_system_model)
        self.tree_view.doubleClicked.connect(self.on_tree_double_clicked)
        # Hide columns other than name
        for i in range(1, 4):
            self.tree_view.hideColumn(i)
        self.proj_dock.setWidget(self.tree_view)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.proj_dock)
        
        # Dock: VIO / Logic Gate Diagram
        self.vio_dock = QDockWidget("Logic Gate Diagram", self)
        self.vio_dock.setMinimumWidth(420)
        self.vio_dashboard = VIODashboard()
        self.vio_dashboard.parse_btn.clicked.connect(self.vio_parse_module)
        self.vio_dock.setWidget(self.vio_dashboard)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.vio_dock)
        
        # Dock: ILA / Waveform
        self.ila_dock = QDockWidget("Integrated Logic Analyzer (ILA)", self)
        self.waveform_viewer = WaveformViewer()
        self.ila_dock.setWidget(self.waveform_viewer)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.ila_dock)

        # Dock: Output Console
        self.console_dock = QDockWidget("Debug Console / Terminal", self)

        # Wrap console in a container with a toolbar
        console_container = QWidget()
        console_vlay = QVBoxLayout(console_container)
        console_vlay.setContentsMargins(0, 0, 0, 0)
        console_vlay.setSpacing(0)

        # ── Console toolbar ──────────────────────────────────────────
        console_toolbar = QWidget()
        console_toolbar.setFixedHeight(34)
        ctb_lay = QHBoxLayout(console_toolbar)
        ctb_lay.setContentsMargins(6, 3, 6, 3)
        ctb_lay.setSpacing(6)

        ctb_lay.addStretch()

        self._console_send_ai_btn = QPushButton("📋 Insert in AI Chat")
        self._console_send_ai_btn.setToolTip(
            "Insert the full Debug Console output into the AI chat input box.\n"
            "You can then edit/add context and send it manually."
        )
        self._console_send_ai_btn.setFont(QFont("Segoe UI", 9))
        self._console_send_ai_btn.clicked.connect(self._insert_console_to_ai)
        ctb_lay.addWidget(self._console_send_ai_btn)

        clear_console_btn = QPushButton("🗑 Clear")
        clear_console_btn.setToolTip("Clear the debug console")
        clear_console_btn.setFont(QFont("Segoe UI", 9))
        clear_console_btn.clicked.connect(self.console_output.clear if hasattr(self, 'console_output') else lambda: None)
        ctb_lay.addWidget(clear_console_btn)
        self._console_clear_btn = clear_console_btn

        console_toolbar.setLayout(ctb_lay)
        console_vlay.addWidget(console_toolbar)

        # ── Console output ───────────────────────────────────────────
        self.console_output = QPlainTextEdit()
        self.console_output.setReadOnly(True)
        font = QFont("Consolas", 11)
        self.console_output.setFont(font)
        console_vlay.addWidget(self.console_output)

        # Wire the clear button now that console_output exists
        clear_console_btn.clicked.disconnect()
        clear_console_btn.clicked.connect(self.console_output.clear)

        self.console_dock.setWidget(console_container)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.console_dock)
        
        self.tabifyDockWidget(self.ila_dock, self.console_dock)


        # Dock: Integrated Terminal
        self.terminal_dock = QDockWidget("Terminal", self)
        self.terminal_widget = TerminalWidget()
        self.terminal_dock.setWidget(self.terminal_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.terminal_dock)
        self.tabifyDockWidget(self.console_dock, self.terminal_dock)
        
        # Dock: AI Coding Assistant (redesigned)
        self.ai_dock = QDockWidget("AI Coding Assistant", self)
        self.ai_dock.setMinimumWidth(420)
        # ── AI widget (theme-aware refs stored as self._ai_*) ──────────────────
        self._ai_theme_name = "light"  # will be set properly by apply_theme
        ai_widget = QWidget()
        self._ai_widget = ai_widget
        ai_layout = QVBoxLayout(ai_widget)
        ai_layout.setContentsMargins(0, 0, 0, 0)
        ai_layout.setSpacing(0)

        # ── Header bar ────────────────────────────────────────────────────────
        self._ai_header = QWidget()
        header_lay = QVBoxLayout(self._ai_header)
        header_lay.setContentsMargins(8, 6, 8, 6)
        header_lay.setSpacing(4)

        # Row 1: Key selector + Model + Refresh
        row1 = QHBoxLayout()
        row1.setSpacing(6)

        self._ai_key_icon = QLabel("🔑 API Key")
        self._ai_key_icon.setStyleSheet("font-size:11px;font-weight:bold;")
        row1.addWidget(self._ai_key_icon)

        self.ai_key_combo = QComboBox()
        self.ai_key_combo.setToolTip("Select saved API key profile")
        self.ai_key_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row1.addWidget(self.ai_key_combo)

        self._ai_manage_btn = QPushButton("⚙ Keys")
        self._ai_manage_btn.setFixedWidth(60)
        self._ai_manage_btn.setFont(QFont("Segoe UI", 9))
        self._ai_manage_btn.setToolTip("Manage API Keys")
        self._ai_manage_btn.clicked.connect(self.show_api_key_manager)
        row1.addWidget(self._ai_manage_btn)

        self._ai_model_lbl = QLabel("🤖 Model:")
        self._ai_model_lbl.setStyleSheet("font-size:11px;font-weight:bold;")
        row1.addWidget(self._ai_model_lbl)

        self.ai_model_combo = QComboBox()
        self.ai_model_combo.addItems(["llama3.2", "llama3", "llama3.1", "gemma3:4b",
                                      "qwen2.5-coder:7b", "deepseek-coder-v2", "mistral", "codellama"])
        row1.addWidget(self.ai_model_combo)

        self.ai_refresh_btn = QPushButton("🔄")
        self.ai_refresh_btn.setFixedWidth(32)
        self.ai_refresh_btn.setFont(QFont("Segoe UI", 11))
        self.ai_refresh_btn.setToolTip("Refresh available models")
        self.ai_refresh_btn.clicked.connect(self.refresh_ollama_models)
        row1.addWidget(self.ai_refresh_btn)
        header_lay.addLayout(row1)

        # Row 2: Context window
        row2 = QHBoxLayout()
        row2.setSpacing(6)
        self._ai_ctx_lbl = QLabel("📏 Context:")
        self._ai_ctx_lbl.setStyleSheet("font-size:10px;")
        row2.addWidget(self._ai_ctx_lbl)
        self.ai_ctx_combo = QComboBox()
        self.ai_ctx_combo.addItems(["1024", "2048", "4096", "8192", "16384", "32768"])
        self.ai_ctx_combo.setCurrentText("4096")
        self.ai_ctx_combo.setFixedWidth(90)
        row2.addWidget(self.ai_ctx_combo)
        self._ai_ctx_lbl2 = QLabel("tokens")
        self._ai_ctx_lbl2.setStyleSheet("font-size:10px;")
        row2.addWidget(self._ai_ctx_lbl2)
        row2.addStretch()
        header_lay.addLayout(row2)
        ai_layout.addWidget(self._ai_header)

        # ── Chat scroll area ──────────────────────────────────────────────────
        self.ai_scroll = QScrollArea()
        self.ai_scroll.setWidgetResizable(True)
        self.ai_chat_container = QWidget()
        self.ai_chat_layout = QVBoxLayout(self.ai_chat_container)
        self.ai_chat_layout.setContentsMargins(8, 8, 8, 8)
        self.ai_chat_layout.setSpacing(10)
        self.ai_chat_layout.addStretch()   # pushes messages to bottom
        self.ai_scroll.setWidget(self.ai_chat_container)
        ai_layout.addWidget(self.ai_scroll, stretch=1)

        # Keep a QTextEdit alias for backward compat
        self.ai_output = QTextEdit()
        self.ai_output.setVisible(False)

        # ── Input bar ─────────────────────────────────────────────────────────
        self._ai_input_bar = QWidget()
        input_bar_lay = QHBoxLayout(self._ai_input_bar)
        input_bar_lay.setContentsMargins(8, 6, 8, 6)
        input_bar_lay.setSpacing(6)

        self.ai_input = QTextEdit()
        self.ai_input.setMaximumHeight(80)
        self.ai_input.setMinimumHeight(44)
        self.ai_input.setFont(QFont("Consolas", 10))
        self.ai_input.setPlaceholderText("Message AI…  (Ctrl+Enter to send)")
        self.ai_input.installEventFilter(self)
        input_bar_lay.addWidget(self.ai_input)

        btn_col = QVBoxLayout()
        btn_col.setSpacing(4)
        self.ai_send_btn = QPushButton("📨 Send")
        self.ai_send_btn.setFixedSize(70, 34)
        self.ai_send_btn.setFont(QFont("Segoe UI", 9))
        self.ai_send_btn.setToolTip("Send message (Ctrl+Enter)")
        self.ai_send_btn.clicked.connect(self.ask_ai)

        self.ai_stop_btn = QPushButton("⏹ Stop")
        self.ai_stop_btn.setFixedSize(70, 34)
        self.ai_stop_btn.setFont(QFont("Segoe UI", 9))
        self.ai_stop_btn.setToolTip("Stop AI generation")
        self.ai_stop_btn.clicked.connect(self.stop_ai)
        self.ai_stop_btn.setEnabled(False)

        btn_col.addWidget(self.ai_send_btn)
        btn_col.addWidget(self.ai_stop_btn)
        input_bar_lay.addLayout(btn_col)
        ai_layout.addWidget(self._ai_input_bar)

        self.ai_dock.setWidget(ai_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.ai_dock)

        # Populate key selector
        self._reload_key_combo()
        
        # Tabify VIO dock under AI dock (right side)
        self.tabifyDockWidget(self.ai_dock, self.vio_dock)
        self.ai_dock.raise_()
        
        # Add dock widgets to Windows menu
        self.windows_menu.addAction(self.proj_dock.toggleViewAction())
        self.windows_menu.addAction(self.vio_dock.toggleViewAction())
        self.windows_menu.addAction(self.ila_dock.toggleViewAction())
        self.windows_menu.addAction(self.console_dock.toggleViewAction())
        self.windows_menu.addAction(self.ai_dock.toggleViewAction())
        self.windows_menu.addAction(self.terminal_dock.toggleViewAction())

        self.new_file() # Start with an empty file
        
        # Try to load available models
        self.refresh_ollama_models()

    # ── API Key Manager helpers ───────────────────────────────────────────────
    def load_api_keys(self) -> list:
        """Return the list of key profiles from api_keys.json."""
        if os.path.exists(API_KEYS_FILE):
            try:
                with open(API_KEYS_FILE, "r") as f:
                    return json.load(f).get("keys", [])
            except Exception:
                pass
        return []

    def get_active_key(self) -> dict:
        """Return the currently selected key profile dict (or a default)."""
        profiles = self.load_api_keys()
        if not profiles:
            return {"name": "default", "key": OLLAMA_CLOUD_API_KEY,
                    "base_url": OLLAMA_CLOUD_BASE_URL, "model": ""}
        idx = self.ai_key_combo.currentIndex()
        idx = max(0, min(idx, len(profiles) - 1))
        return profiles[idx]

    def _reload_key_combo(self):
        """Refresh the key-selector combo from disk."""
        profiles = self.load_api_keys()
        if not profiles:
            # seed default
            profiles = [{"name": "Ollama Cloud (default)",
                         "provider": "Ollama",
                         "base_url": OLLAMA_CLOUD_BASE_URL,
                         "key": OLLAMA_CLOUD_API_KEY,
                         "model": "llama3.2"}]
        prev = self.ai_key_combo.currentText()
        self.ai_key_combo.clear()
        for p in profiles:
            self.ai_key_combo.addItem(f"🔑 {p.get('name', 'Unnamed')}")
        # restore selection
        idx = self.ai_key_combo.findText(prev)
        if idx >= 0:
            self.ai_key_combo.setCurrentIndex(idx)
        # pre-fill model from profile
        active = self.get_active_key()
        if active.get("model"):
            idx_m = self.ai_model_combo.findText(active["model"])
            if idx_m >= 0:
                self.ai_model_combo.setCurrentIndex(idx_m)

    def show_api_key_manager(self):
        dlg = APIKeyManagerDialog(self)
        dlg.exec()
        self._reload_key_combo()   # refresh after edits

    def refresh_ollama_models(self):
        profile = self.get_active_key() if hasattr(self, 'ai_key_combo') else {}
        api_key = profile.get("key", OLLAMA_CLOUD_API_KEY)
        base_url = profile.get("base_url", OLLAMA_CLOUD_BASE_URL).rstrip('/')
        if not api_key:
            return
        try:
            headers = {'Authorization': f'Bearer {api_key}'}
            req = urllib.request.Request(f"{base_url}/api/tags", headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                result = json.loads(response.read().decode('utf-8'))
                models = [m["name"] for m in result.get("models", [])]
                if models:
                    current = self.ai_model_combo.currentText()
                    self.ai_model_combo.clear()
                    self.ai_model_combo.addItems(models)
                    if current in models:
                        self.ai_model_combo.setCurrentText(current)
        except Exception:
            pass  # Fail silently – keep the default list

    # ── Chat bubble helpers ───────────────────────────────────────────────────
    def _add_chat_bubble(self, text: str, role: str):
        """Append a styled bubble to the chat scroll area.
        role: 'user' | 'assistant' | 'system' | 'error'
        """
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M")
        is_light = getattr(self, '_ai_theme_name', 'light') == 'light'

        bubble = QWidget()
        b_lay = QVBoxLayout(bubble)
        b_lay.setContentsMargins(0, 0, 0, 0)
        b_lay.setSpacing(2)

        if role == "user":
            bubble_color = "#dbeafe" if is_light else "#1a3a5c"
            border_color = "#1565c0" if is_light else "#0e639c"
            text_color   = "#0d2a5e" if is_light else "#d4d4d4"
            label_text   = "You"
            label_color  = "#0d47a1" if is_light else "#4EC9B0"
            align = Qt.AlignmentFlag.AlignRight
        elif role == "assistant":
            bubble_color = "#f0f4fb" if is_light else "#252526"
            border_color = "#b0c4de" if is_light else "#3a3a3a"
            text_color   = "#1a1a2e" if is_light else "#d4d4d4"
            label_text   = f"AI ({self.ai_model_combo.currentText()})"
            label_color  = "#1565c0" if is_light else "#9CDCFE"
            align = Qt.AlignmentFlag.AlignLeft
        elif role == "error":
            bubble_color = "#fdecea" if is_light else "#3a1010"
            border_color = "#e53935" if is_light else "#F44747"
            text_color   = "#8b0000" if is_light else "#d4d4d4"
            label_text   = "Error"
            label_color  = "#c62828" if is_light else "#F44747"
            align = Qt.AlignmentFlag.AlignLeft
        else:  # system
            bubble_color = "#fffde7" if is_light else "#2d2d00"
            border_color = "#f9a825" if is_light else "#888800"
            text_color   = "#4e3a00" if is_light else "#d4d4d4"
            label_text   = "System"
            label_color  = "#e65100" if is_light else "#DCDCAA"
            align = Qt.AlignmentFlag.AlignLeft

        # Header row: role label + timestamp
        ts_color = "#546e7a" if is_light else "#666666"
        hdr = QLabel(f"<b>{label_text}</b>  <span style='color:{ts_color};font-size:9px;'>{ts}</span>")
        hdr.setStyleSheet(f"color:{label_color}; font-size:10px; padding:0;")
        b_lay.addWidget(hdr, alignment=align)

        # Content label (selectable)
        msg_lbl = QTextEdit()
        msg_lbl.setReadOnly(True)
        msg_lbl.setFont(QFont("Consolas", 10))
        msg_lbl.setStyleSheet(
            f"QTextEdit{{background:{bubble_color}; color:{text_color};"
            f"border:1px solid {border_color}; border-radius:6px;"
            f"padding:8px 10px; font-family:Consolas;}}"
        )
        # Format code blocks
        formatted = self._format_bubble_text(text, is_light=is_light)
        msg_lbl.setHtml(formatted)
        # Auto-height
        msg_lbl.document().setTextWidth(msg_lbl.viewport().width())
        doc_h = int(msg_lbl.document().size().height()) + 20
        msg_lbl.setFixedHeight(min(max(doc_h, 60), 600))
        msg_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        b_lay.addWidget(msg_lbl)

        # Insert before the trailing stretch
        count = self.ai_chat_layout.count()
        self.ai_chat_layout.insertWidget(count - 1, bubble)

        # Scroll to bottom
        QApplication.processEvents()
        vsb = self.ai_scroll.verticalScrollBar()
        vsb.setValue(vsb.maximum())

    @staticmethod
    def _format_bubble_text(text: str, is_light: bool = False) -> str:
        """Convert markdown-ish code fences to colored HTML for the bubble."""
        import re as _re
        escaped = html.escape(text)
        # Code block colors
        code_bg  = "#f4f4f4" if is_light else "#1e1e1e"
        code_fg  = "#8b4513" if is_light else "#CE9178"
        code_bdr = "#c0c0c0" if is_light else "#555555"
        ic_bg    = "#ebebeb" if is_light else "#3c3c3c"
        ic_fg    = "#8b4513" if is_light else "#CE9178"

        def replace_fence(m):
            code = m.group(2) or m.group(1) or ""
            return (f"<pre style='background:{code_bg};color:{code_fg};"
                    f"border:1px solid {code_bdr};border-radius:4px;"
                    f"padding:8px;margin:4px 0;white-space:pre-wrap;'>"
                    f"{code}</pre>")
        result = _re.sub(r'```[a-zA-Z]*\n(.*?)```|```(.*?)```',
                         replace_fence, escaped, flags=_re.DOTALL)
        result = _re.sub(r'`([^`]+)`',
                         rf"<code style='background:{ic_bg};color:{ic_fg};"
                         r"border-radius:3px;padding:1px 4px;'>\1</code>",
                         result)
        result = _re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', result)
        result = result.replace('\n', '<br>')
        return result

    def stop_ai(self):
        if hasattr(self, 'ai_worker') and self.ai_worker.isRunning():
            self.ai_worker.stop()
            self.ai_send_btn.setEnabled(True)
            self.ai_stop_btn.setEnabled(False)
            self._add_chat_bubble("Generation stopped.", "system")

    def ask_ai(self):
        prompt = self.ai_input.toPlainText().strip()
        if not prompt:
            return

        model = self.ai_model_combo.currentText() or "llama3.2"
        profile = self.get_active_key()
        api_key = profile.get("key", "") or OLLAMA_CLOUD_API_KEY
        base_url = profile.get("base_url", OLLAMA_CLOUD_BASE_URL)
        max_tokens = int(self.ai_ctx_combo.currentText())

        if not api_key:
            self._add_chat_bubble("No API key configured. Go to Edit → Manage API Keys to add one.", "error")
            return

        self.ai_send_btn.setEnabled(False)
        self.ai_stop_btn.setEnabled(True)
        self.ai_input.clear()

        # Show user bubble
        self._add_chat_bubble(prompt, "user")
        # Placeholder thinking bubble
        self._add_chat_bubble("Generating…", "system")

        context = ""
        active_file_name = "Untitled"
        target_tabs = self.last_focused_tabs if not self.editor_tabs_right.isHidden() else self.editor_tabs
        current_editor = target_tabs.currentWidget()
        if current_editor:
            context = current_editor.toPlainText()
            idx = target_tabs.indexOf(current_editor)
            if idx >= 0:
                active_file_name = target_tabs.tabText(idx)

        system_prompt = (
            "You are an advanced AI coding assistant integrated into a Verilog IDE.\n"
            "You can create or edit files directly. To create a new file, your response MUST contain exactly:\n"
            "[CREATE_FILE: filename.v]\n```verilog\n// complete code here\n```\n\n"
            "To completely replace/edit the currently active file, use exactly:\n"
            "[EDIT_ACTIVE_FILE]\n```verilog\n// complete new code here\n```\n\n"
            "Always output the full file content without placeholders when using these tags."
        )
        if context:
            system_prompt += f"\n\nCURRENT ACTIVE FILE ({active_file_name}):\n```verilog\n{context}\n```"

        messages = ([{"role": "system", "content": system_prompt}]
                    + self.chat_history
                    + [{"role": "user", "content": prompt}])

        self.ai_worker = OllamaWorker(model, messages,
                                      api_key=api_key,
                                      base_url=base_url,
                                      max_tokens=max_tokens)
        self.ai_worker.finished.connect(self.on_ai_finished)
        self.ai_worker.error.connect(self.on_ai_error)
        self.ai_worker.start()

    def on_ai_finished(self, response):
        self.ai_send_btn.setEnabled(True)
        self.ai_stop_btn.setEnabled(False)

        # Remove the "Generating…" system bubble (last widget before stretch)
        count = self.ai_chat_layout.count()
        if count > 1:
            item = self.ai_chat_layout.itemAt(count - 2)
            if item and item.widget():
                item.widget().deleteLater()

        # Add to chat history
        prompt = self.ai_worker.messages[-1]["content"]
        self.chat_history.append({"role": "user", "content": prompt})
        self.chat_history.append({"role": "assistant", "content": response})
        self.save_ai_memory()

        # Show AI bubble
        self._add_chat_bubble(response, "assistant")

        # Parse for file actions and show notifications
        create_matches = re.finditer(
            r'\[CREATE_FILE:\s*([^\]\s]+)\]\s*```(?:verilog|v)?\n(.*?)\n?```',
            response, re.DOTALL | re.IGNORECASE)
        for match in create_matches:
            filename = match.group(1).strip()
            code = match.group(2)
            proj_dir = self.current_project_dir or os.getcwd()
            filepath = os.path.join(proj_dir, filename)
            try:
                with open(filepath, 'w') as f:
                    f.write(code)
                self.open_file(filepath)
                self._add_chat_bubble(f"✅ Created and opened: **{filename}**", "system")
            except Exception as e:
                self._add_chat_bubble(f"❌ Failed to create {filename}: {e}", "error")

        edit_matches = re.finditer(
            r'\[EDIT_ACTIVE_FILE\]\s*```(?:verilog|v)?\n(.*?)```',
            response, re.DOTALL | re.IGNORECASE)
        for match in edit_matches:
            code = match.group(1)
            target_tabs = self.last_focused_tabs if not self.editor_tabs_right.isHidden() else self.editor_tabs
            current_editor = target_tabs.currentWidget()
            if current_editor:
                current_editor.setPlainText(code)
                self._add_chat_bubble("✅ Active file updated.", "system")
            else:
                self._add_chat_bubble("❌ No active file to edit.", "error")

    def on_ai_error(self, error):
        self.ai_send_btn.setEnabled(True)
        self.ai_stop_btn.setEnabled(False)
        # Remove "Generating…" placeholder
        count = self.ai_chat_layout.count()
        if count > 1:
            item = self.ai_chat_layout.itemAt(count - 2)
            if item and item.widget():
                item.widget().deleteLater()
        self._add_chat_bubble(error, "error")

    def new_project(self):
        dlg = NewProjectDialog(self)
        if dlg.exec():
            name = dlg.name_input.text().strip()
            loc = dlg.loc_input.text().strip()
            vc_enabled = dlg.vc_checkbox.isChecked()
            
            if not name or not loc:
                return
                
            proj_dir = os.path.join(loc, name)
            os.makedirs(proj_dir, exist_ok=True)
            
            proj_data = {"name": name, "vc_enabled": vc_enabled}
            with open(os.path.join(proj_dir, "project.json"), "w") as f:
                json.dump(proj_data, f)
                
            if vc_enabled:
                with open(os.path.join(proj_dir, ".gitignore"), "w") as f:
                    f.write("*.vcd\n*.vvp\n__pycache__/\n")
                subprocess.run(["git", "init"], cwd=proj_dir, capture_output=True)
                subprocess.run(["git", "add", "."], cwd=proj_dir, capture_output=True)
                subprocess.run(["git", "commit", "-m", "Initial project creation"], cwd=proj_dir, capture_output=True)
                
            self.set_project_dir(proj_dir)
            self.console_output.appendPlainText(f"Created new project: {name} (VC: {vc_enabled})")
            
    def open_project(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Open Project Directory")
        if dir_path:
            self.set_project_dir(dir_path)
            
    def set_project_dir(self, dir_path):
        self.current_project_dir = dir_path
        self.tree_view.setRootIndex(self.file_system_model.index(dir_path))
        self.console_output.appendPlainText(f"Opened project: {dir_path}")
        self.save_config("last_project", dir_path)
        self.load_ai_memory()
        if hasattr(self, 'terminal_widget'):
            self.terminal_widget.set_cwd(dir_path)
        
    def load_ai_memory(self):
        self.chat_history = []
        # Clear chat bubbles (keep trailing stretch)
        while self.ai_chat_layout.count() > 1:
            item = self.ai_chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not self.current_project_dir: return
        
        mem_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_memories.json")
        if os.path.exists(mem_file):
            try:
                with open(mem_file, "r") as f:
                    data = json.load(f)
                if self.current_project_dir in data:
                    self.chat_history = data[self.current_project_dir]
                    for msg in self.chat_history:
                        if msg["role"] == "system": continue
                        role = "user" if msg["role"] == "user" else "assistant"
                        self._add_chat_bubble(msg['content'], role)
            except:
                pass

    def save_ai_memory(self):
        if not self.current_project_dir: return
        mem_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_memories.json")
        data = {}
        if os.path.exists(mem_file):
            try:
                with open(mem_file, "r") as f:
                    data = json.load(f)
            except:
                pass
        data[self.current_project_dir] = self.chat_history
        try:
            with open(mem_file, "w") as f:
                json.dump(data, f)
        except:
            pass

    def load_example(self, example_folder):
        base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples")
        ex_path = os.path.join(base_dir, example_folder)
        
        if not os.path.exists(ex_path):
            QMessageBox.warning(self, "Example Not Found", f"Could not find example folder: {ex_path}")
            return
            
        self.set_project_dir(ex_path)
        
        # Open the .v and tb_ files
        for f in os.listdir(ex_path):
            if f.endswith('.v'):
                self.open_file(os.path.join(ex_path, f))
                
        self.console_output.appendPlainText(f"Loaded Example Project: {example_folder}")
        
    def toggle_split_editor(self):
        if self.editor_tabs_right.isHidden():
            self.editor_tabs_right.show()
            self.editor_splitter.setSizes([self.width() // 2, self.width() // 2])
            
            # Clone active file
            current_editor = self.editor_tabs.currentWidget()
            if current_editor and current_editor.property("file_path"):
                file_path = current_editor.property("file_path")
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                    new_editor = CodeEditor()
                    new_editor.setPlainText(content)
                    new_editor.setProperty("file_path", file_path)
                    idx = self.editor_tabs_right.addTab(new_editor, os.path.basename(file_path))
                    self.editor_tabs_right.setCurrentIndex(idx)
                except Exception:
                    pass
        else:
            self.editor_tabs_right.hide()
            
    def show_documentation(self):
        doc_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples", "how_to_code.txt")
        if os.path.exists(doc_path):
            self.open_file(doc_path)
        else:
            QMessageBox.information(self, "Help", "Documentation file 'how_to_code.txt' not found in examples folder.")

    def show_history(self):
        if not self.current_project_dir:
            QMessageBox.warning(self, "No Project", "Please open a project first.")
            return
        if not self.is_vc_enabled():
            QMessageBox.warning(self, "VC Disabled", "Change tracking is disabled for this project.")
            return
        dlg = VersionHistoryDialog(self.current_project_dir, self)
        dlg.exec()

    def is_vc_enabled(self):
        if not self.current_project_dir: return False
        try:
            with open(os.path.join(self.current_project_dir, "project.json"), "r") as f:
                data = json.load(f)
                return data.get("vc_enabled", False)
        except:
            # Check if git exists as fallback
            return os.path.exists(os.path.join(self.current_project_dir, ".git"))

    def new_file(self):
        editor = CodeEditor()
        target_tabs = self.last_focused_tabs if not self.editor_tabs_right.isHidden() else self.editor_tabs
        index = target_tabs.addTab(editor, "Untitled")
        target_tabs.setCurrentIndex(index)
        
    def save_file(self):
        target_tabs = self.last_focused_tabs if not self.editor_tabs_right.isHidden() else self.editor_tabs
        current_editor = target_tabs.currentWidget()
        if not current_editor:
            # Try the other one if focused one is empty
            target_tabs = self.editor_tabs if target_tabs == self.editor_tabs_right else self.editor_tabs_right
            current_editor = target_tabs.currentWidget()
            if not current_editor:
                return
            
        idx = target_tabs.currentIndex()
        title = target_tabs.tabText(idx)
        
        if title == "Untitled" or title.startswith("*"):
            file_path, _ = QFileDialog.getSaveFileName(self, "Save File", self.current_project_dir or "", "Verilog Files (*.v *.sv);;All Files (*)")
            if file_path:
                with open(file_path, 'w') as f:
                    f.write(current_editor.toPlainText())
                target_tabs.setTabText(idx, os.path.basename(file_path))
                current_editor.setProperty("file_path", file_path)
                self.console_output.appendPlainText(f"Saved: {file_path}")
        else:
            file_path = current_editor.property("file_path")
            if file_path:
                with open(file_path, 'w') as f:
                    f.write(current_editor.toPlainText())
                self.console_output.appendPlainText(f"Saved: {file_path}")
                
    def commit_changes(self, choice=None):
        if not self.is_vc_enabled():
            QMessageBox.warning(self, "VC Disabled", "Change tracking is disabled for this project.\nYou can recreate the project with Version Control enabled.")
            return
            
        if choice is None:
            options = ["Commit Current File Only", "Commit All Changed Files"]
            choice, ok = QInputDialog.getItem(self, "Commit Options", "Select what to commit:", options, 0, False)
            if not (ok and choice):
                return
        
        msg, ok2 = QInputDialog.getText(self, "Change Tracker", f"Enter a change name for {choice}:")
        if ok2 and msg.strip():
            try:
                if "All" in choice:
                    subprocess.run(["git", "add", "."], cwd=self.current_project_dir, capture_output=True)
                else:
                    target_tabs = self.last_focused_tabs if not self.editor_tabs_right.isHidden() else self.editor_tabs
                    current_editor = target_tabs.currentWidget()
                    if current_editor and current_editor.property("file_path"):
                        subprocess.run(["git", "add", current_editor.property("file_path")], cwd=self.current_project_dir, capture_output=True)
                    else:
                        QMessageBox.warning(self, "No file", "No valid file is currently active.")
                        return
                        
                subprocess.run(["git", "commit", "-m", msg.strip()], cwd=self.current_project_dir, capture_output=True)
                self.console_output.appendPlainText(f"Changes committed: {msg.strip()}")
            except Exception as e:
                QMessageBox.warning(self, "Git Error", f"Failed to commit. Is Git installed on your system?\n{e}")
        
    def on_tree_double_clicked(self, index):
        file_path = self.file_system_model.filePath(index)
        if os.path.isfile(file_path):
            self.open_file(file_path)
            
    def open_file(self, file_path):
        # Check both tab widgets
        for tabs in [self.editor_tabs, self.editor_tabs_right]:
            for i in range(tabs.count()):
                editor = tabs.widget(i)
                if editor.property("file_path") == file_path:
                    tabs.setCurrentIndex(i)
                    return
                
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            editor = CodeEditor()
            editor.setPlainText(content)
            editor.setProperty("file_path", file_path)
            
            target_tabs = self.last_focused_tabs if not self.editor_tabs_right.isHidden() else self.editor_tabs
            idx = target_tabs.addTab(editor, os.path.basename(file_path))
            target_tabs.setCurrentIndex(idx)
        except Exception as e:
            self.console_output.appendPlainText(f"Error opening file: {e}")

    def close_tab(self, index):
        self.editor_tabs.removeTab(index)
        # If left pane becomes empty but right pane is open, move right tabs to left
        if self.editor_tabs.count() == 0 and not self.editor_tabs_right.isHidden():
            while self.editor_tabs_right.count() > 0:
                widget = self.editor_tabs_right.widget(0)
                text = self.editor_tabs_right.tabText(0)
                self.editor_tabs.addTab(widget, text)
            self.editor_tabs_right.hide()
            self.last_focused_tabs = self.editor_tabs
        
    def close_tab_right(self, index):
        self.editor_tabs_right.removeTab(index)
        # Auto collapse right pane if empty
        if self.editor_tabs_right.count() == 0:
            self.editor_tabs_right.hide()
            self.last_focused_tabs = self.editor_tabs
        
    def undo_edit(self):
        target_tabs = self.last_focused_tabs if not self.editor_tabs_right.isHidden() else self.editor_tabs
        current_editor = target_tabs.currentWidget()
        if current_editor:
            current_editor.undo()

    def redo_edit(self):
        target_tabs = self.last_focused_tabs if not self.editor_tabs_right.isHidden() else self.editor_tabs
        current_editor = target_tabs.currentWidget()
        if current_editor:
            current_editor.redo()

    def eventFilter(self, obj, event):
        """Catch Ctrl+Enter in ai_input to send message."""
        from PyQt6.QtCore import QEvent
        if (obj is self.ai_input
                and event.type() == QEvent.Type.KeyPress
                and event.key() == Qt.Key.Key_Return
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.ask_ai()
            return True
        return super().eventFilter(obj, event)
            
    def run_simulation(self):
        self.save_file() # Auto-save before running
        self.console_output.appendPlainText("\n--- Starting Synthesis/Simulation ---")
        self.console_dock.raise_()
        
        proj_dir = self.current_project_dir or os.getcwd()
        v_files = [f for f in os.listdir(proj_dir) if f.endswith('.v')]
        
        if not v_files:
            self.console_output.appendPlainText("No Verilog (.v) files found in the current directory.")
            return
            
        iverilog_path = shutil.which("iverilog")
        if not iverilog_path:
            fallback = "C:\\iverilog\\bin\\iverilog.exe"
            if os.path.exists(fallback):
                iverilog_path = fallback
            else:
                iverilog_path = "iverilog" # Let it fail with FileNotFoundError

        sim_vvp = os.path.join(proj_dir, "sim.vvp")
        cmd_compile = [iverilog_path, "-o", "sim.vvp"] + v_files
        self.console_output.appendPlainText(f"> {' '.join(cmd_compile)}")
        
        try:
            res_comp = subprocess.run(cmd_compile, cwd=proj_dir, capture_output=True, text=True)
            if res_comp.stdout: self.console_output.appendPlainText(res_comp.stdout.strip())
            if res_comp.stderr: self.console_output.appendPlainText(res_comp.stderr.strip())
            
            if res_comp.returncode != 0:
                self.console_output.appendPlainText("Compilation failed. Check errors above.")
                return
                
            self.console_output.appendPlainText("Compilation successful. Running simulation...")
            
            vvp_path = shutil.which("vvp")
            if not vvp_path:
                fallback_vvp = "C:\\iverilog\\bin\\vvp.exe"
                if os.path.exists(fallback_vvp):
                    vvp_path = fallback_vvp
                else:
                    vvp_path = "vvp"

            cmd_sim = [vvp_path, "sim.vvp"]
            self.console_output.appendPlainText(f"> {' '.join(cmd_sim)}")
            res_sim = subprocess.run(cmd_sim, cwd=proj_dir, capture_output=True, text=True)
            if res_sim.stdout: self.console_output.appendPlainText(res_sim.stdout.strip())
            if res_sim.stderr: self.console_output.appendPlainText(res_sim.stderr.strip())
            
            self.console_output.appendPlainText("Simulation completed.")
            
            vcd_files = [f for f in os.listdir(proj_dir) if f.endswith('.vcd')]
            if vcd_files:
                vcd_path = os.path.join(proj_dir, vcd_files[0])
                self.console_output.appendPlainText(f"Loading VCD into ILA: {vcd_path}")
                self.waveform_viewer.load_vcd_data(vcd_path)
                self.ila_dock.raise_()
            else:
                self.console_output.appendPlainText("No .vcd file found. Did you add $dumpfile and $dumpvars to your testbench?")
                
        except FileNotFoundError as e:
            self.console_output.appendPlainText("Error: 'iverilog' or 'vvp' was not found on your system.\nPlease make sure Icarus Verilog is installed and added to your system's PATH variable.")
        except Exception as e:
            self.console_output.appendPlainText(f"Error during simulation: {e}")

    # ── Gate Diagram Helper ──────────────────────────────────────────
    def _get_active_verilog_code(self):
        """Return (code, file_path) for the currently active editor tab."""
        for tabs in [self.editor_tabs, self.editor_tabs_right]:
            editor = tabs.currentWidget()
            if editor:
                code = editor.toPlainText().strip()
                if code:
                    fp = editor.property("file_path") or ""
                    return code, fp
        return "", ""

    def vio_parse_module(self):
        """Parse active editor and draw the logic gate diagram."""
        code, fp = self._get_active_verilog_code()
        if not code:
            self.console_output.appendPlainText("Gate Viewer: No active Verilog file to parse.")
            return
        module_name = os.path.basename(fp).replace(".v", "") if fp else "module"
        self.vio_dashboard.load_module(code, module_name)
        self.vio_dock.raise_()
        self.console_output.appendPlainText(f"Gate Viewer: Drew diagram for '{module_name}'")

    # ── Console → AI helper ─────────────────────────────────────────────────
    def _insert_console_to_ai(self):
        """Insert the full Debug Console text into the AI chat input (not sent)."""
        text = self.console_output.toPlainText().strip()
        if not text:
            return

        # Build a contextual prompt snippet
        snippet = (
            f"Here is the Debug Console output from the simulation:\n\n"
            f"```\n{text}\n```\n\n"
        )

        # Append to whatever is already in the AI input box
        current = self.ai_input.toPlainText()
        if current.strip():
            self.ai_input.setPlainText(current + "\n\n" + snippet)
        else:
            self.ai_input.setPlainText(snippet)

        # Place cursor at the end so user can add more context
        cursor = self.ai_input.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.ai_input.setTextCursor(cursor)

        # Raise the AI dock and focus the input
        self.ai_dock.raise_()
        self.ai_input.setFocus()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = VerilogIDE()
    window.show()
    sys.exit(app.exec())