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
    QTableWidgetItem, QHeaderView, QMessageBox, QGroupBox, QDialog, QFormLayout, QDialogButtonBox, QLineEdit, QInputDialog
)
import html
from PyQt6.QtGui import QAction, QKeySequence, QFont, QIcon, QColor, QPainter, QPen, QFileSystemModel, QTextFormat
from PyQt6.QtCore import Qt, QDir, QSize, QRect, QThread, pyqtSignal, QProcess, QByteArray

OLLAMA_CLOUD_API_KEY = "949a3f58fcfb475ebd95be644b8aa7b1.Wex8pxkLXUrUGqQKBPWDSEyD"
OLLAMA_CLOUD_BASE_URL = "https://ollama.com"

class OllamaWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, model, messages, api_key=None):
        super().__init__()
        self.model = model
        self.messages = messages
        self.api_key = api_key or OLLAMA_CLOUD_API_KEY

    def stop(self):
        self.terminate()

    def run(self):
        url = f"{OLLAMA_CLOUD_BASE_URL}/api/chat"
        data = {
            "model": self.model,
            "messages": self.messages,
            "stream": False
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
            self.error.emit(f"HTTP {e.code} Error from Ollama Cloud: {body}")
        except urllib.error.URLError as e:
            self.error.emit(f"Failed to connect to Ollama Cloud: {str(e)}")
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
    """A VS Code-style integrated terminal powered by QProcess."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: list[str] = []
        self._hist_idx: int = -1
        self._process: QProcess | None = None
        self._cwd: str = os.getcwd()
        self._setup_ui()
        self._start_shell()

    # ── UI ──────────────────────────────────────────────────────────
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top toolbar ─────────────────────────────────────────────
        bar = QHBoxLayout()
        bar.setContentsMargins(6, 4, 6, 4)

        self._shell_label = QLabel()
        self._shell_label.setStyleSheet("color:#9CDCFE; font-weight:bold; font-family:Consolas;")

        self._cwd_label = QLabel()
        self._cwd_label.setStyleSheet("color:#888; font-family:Consolas; font-size:10px;")
        self._cwd_label.setWordWrap(False)

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(60)
        clear_btn.setStyleSheet(
            "QPushButton{background:#3a3a3a;color:#ccc;border:1px solid #555;"
            "border-radius:3px;padding:2px 6px;}"
            "QPushButton:hover{background:#505050;}"
        )
        clear_btn.clicked.connect(self._clear_output)

        new_btn = QPushButton("+ New")
        new_btn.setFixedWidth(60)
        new_btn.setStyleSheet(
            "QPushButton{background:#3a3a3a;color:#ccc;border:1px solid #555;"
            "border-radius:3px;padding:2px 6px;}"
            "QPushButton:hover{background:#505050;}"
        )
        new_btn.clicked.connect(self._restart_shell)

        bar.addWidget(self._shell_label)
        bar.addSpacing(10)
        bar.addWidget(self._cwd_label)
        bar.addStretch()
        bar.addWidget(clear_btn)
        bar.addWidget(new_btn)

        bar_widget = QWidget()
        bar_widget.setLayout(bar)
        bar_widget.setStyleSheet("background:#252526; border-bottom:1px solid #333;")
        root.addWidget(bar_widget)

        # ── Output display ──────────────────────────────────────────
        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self._output.setFont(QFont("Consolas", 11))
        self._output.setStyleSheet(
            "QPlainTextEdit{"
            "  background:#1e1e1e; color:#d4d4d4;"
            "  border:none;"
            "}"
        )
        self._output.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        root.addWidget(self._output, stretch=1)

        # ── Input row ───────────────────────────────────────────────
        input_row = QHBoxLayout()
        input_row.setContentsMargins(4, 2, 4, 4)
        input_row.setSpacing(4)

        self._prompt_label = QLabel("❯")
        self._prompt_label.setStyleSheet(
            "color:#4EC9B0; font-family:Consolas; font-size:13px; font-weight:bold;"
        )
        input_row.addWidget(self._prompt_label)

        self._input = QLineEdit()
        self._input.setFont(QFont("Consolas", 11))
        self._input.setStyleSheet(
            "QLineEdit{"
            "  background:#252526; color:#d4d4d4;"
            "  border:1px solid #3a3a3a; border-radius:3px; padding:3px 6px;"
            "}"
            "QLineEdit:focus{border:1px solid #4EC9B0;}"
        )
        self._input.setPlaceholderText("Type a command and press Enter...")
        self._input.returnPressed.connect(self._send_command)
        self._input.installEventFilter(self)
        input_row.addWidget(self._input)

        input_widget = QWidget()
        input_widget.setLayout(input_row)
        input_widget.setStyleSheet("background:#1e1e1e;")
        root.addWidget(input_widget)

    # ── Shell management ────────────────────────────────────────────
    def _shell_executable(self) -> str:
        ps = shutil.which("powershell.exe") or shutil.which("powershell")
        if ps:
            return ps
        return "cmd.exe"

    def _shell_args(self, exe: str) -> list[str]:
        if "powershell" in exe.lower():
            # -NoLogo: suppress banner  -NoExit: stay alive  -Command: set cwd first
            return ["-NoLogo", "-NoExit",
                    "-Command", f"Set-Location -LiteralPath '{self._cwd}'"]
        return []  # cmd.exe needs no extra args

    def _start_shell(self):
        exe = self._shell_executable()
        shell_name = "PowerShell" if "powershell" in exe.lower() else "cmd"
        self._shell_label.setText(f"⚡ {shell_name}")
        self._cwd_label.setText(self._cwd)

        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_output)
        self._process.finished.connect(self._on_finished)
        self._process.setWorkingDirectory(self._cwd)
        self._process.start(exe, self._shell_args(exe))

        if not self._process.waitForStarted(3000):
            self._append_text("[Terminal] Failed to start shell process.\n", error=True)

    def _restart_shell(self):
        if self._process and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()
            self._process.waitForFinished(500)
        self._output.clear()
        self._start_shell()

    # ── Commands ────────────────────────────────────────────────────
    def _send_command(self):
        cmd = self._input.text()
        if not cmd.strip():
            return

        # Echo the command in output like a real terminal
        self._append_text(f"❯ {cmd}\n", prompt=True)

        # Store history
        if not self._history or self._history[-1] != cmd:
            self._history.append(cmd)
        self._hist_idx = -1
        self._input.clear()

        if self._process and self._process.state() == QProcess.ProcessState.Running:
            self._process.write((cmd + "\n").encode("utf-8", errors="replace"))
        else:
            self._append_text("[Terminal] Shell is not running. Click '+ New' to restart.\n", error=True)

    def _clear_output(self):
        self._output.clear()

    # ── CWD control (called by IDE when project opens) ───────────────
    def set_cwd(self, path: str):
        self._cwd = path
        self._cwd_label.setText(path)
        if self._process and self._process.state() == QProcess.ProcessState.Running:
            exe = self._shell_executable()
            if "powershell" in exe.lower():
                cd_cmd = f"Set-Location -LiteralPath '{path}'"
            else:
                cd_cmd = f'cd /d "{path}"'
            self._process.write((cd_cmd + "\n").encode("utf-8", errors="replace"))

    # ── Output handling ─────────────────────────────────────────────
    def _on_output(self):
        raw: QByteArray = self._process.readAllStandardOutput()
        try:
            text = raw.data().decode("utf-8", errors="replace")
        except Exception:
            text = str(raw.data())
        # Strip basic ANSI escape codes
        text = re.sub(r'\x1b\[[0-9;]*[mGKHF]', '', text)
        self._append_text(text)

    def _on_finished(self, exit_code, exit_status):
        self._append_text(f"\n[Terminal] Process exited (code {exit_code}). Click '+ New' to restart.\n",
                          error=True)
        self._prompt_label.setStyleSheet("color:#F44747; font-family:Consolas; font-size:13px; font-weight:bold;")

    def _append_text(self, text: str, error: bool = False, prompt: bool = False):
        cursor = self._output.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)

        fmt = self._output.currentCharFormat()
        if prompt:
            fmt.setForeground(QColor("#4EC9B0"))
        elif error:
            fmt.setForeground(QColor("#F44747"))
        else:
            fmt.setForeground(QColor("#d4d4d4"))

        cursor.setCharFormat(fmt)
        cursor.insertText(text)
        self._output.setTextCursor(cursor)
        self._output.ensureCursorVisible()

    # ── Arrow-key history navigation ────────────────────────────────
    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QKeyEvent
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
        self.console_output = QPlainTextEdit()
        self.console_output.setReadOnly(True)
        font = QFont("Consolas", 11)
        self.console_output.setFont(font)
        self.console_dock.setWidget(self.console_output)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.console_dock)
        
        self.tabifyDockWidget(self.ila_dock, self.console_dock)

        # Dock: Integrated Terminal
        self.terminal_dock = QDockWidget("Terminal", self)
        self.terminal_widget = TerminalWidget()
        self.terminal_dock.setWidget(self.terminal_widget)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.terminal_dock)
        self.tabifyDockWidget(self.console_dock, self.terminal_dock)
        
        # Dock: AI Assistant
        self.ai_dock = QDockWidget("AI Coding Assistant", self)
        self.ai_dock.setMinimumWidth(450)
        ai_widget = QWidget()
        ai_layout = QVBoxLayout(ai_widget)
        
        # API Key row
        api_key_layout = QHBoxLayout()
        api_key_layout.addWidget(QLabel("API Key:"))
        self.ai_api_key_input = QLineEdit()
        self.ai_api_key_input.setText(OLLAMA_CLOUD_API_KEY)
        self.ai_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.ai_api_key_input.setPlaceholderText("Enter Ollama Cloud API Key...")
        self.ai_api_key_input.setToolTip("Your Ollama Cloud API key (from ollama.com account settings)")
        api_key_layout.addWidget(self.ai_api_key_input)
        
        show_key_btn = QPushButton("👁")
        show_key_btn.setFixedWidth(32)
        show_key_btn.setCheckable(True)
        show_key_btn.setToolTip("Show/Hide API Key")
        show_key_btn.toggled.connect(lambda checked: self.ai_api_key_input.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        ))
        api_key_layout.addWidget(show_key_btn)
        ai_layout.addLayout(api_key_layout)

        # Model row
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model:"))
        self.ai_model_combo = QComboBox()
        self.ai_model_combo.addItems(["llama3.2", "llama3", "llama3.1", "gemma3:4b", "qwen2.5-coder:7b", "deepseek-coder-v2", "mistral", "codellama"])
        model_layout.addWidget(self.ai_model_combo)
        
        self.ai_refresh_btn = QPushButton("Refresh Models")
        self.ai_refresh_btn.clicked.connect(self.refresh_ollama_models)
        model_layout.addWidget(self.ai_refresh_btn)
        ai_layout.addLayout(model_layout)
        
        font_ai = QFont("Consolas", 10)
        self.ai_output = QTextEdit()
        self.ai_output.setReadOnly(True)
        self.ai_output.setFont(font_ai)
        ai_layout.addWidget(self.ai_output)
        
        input_layout = QHBoxLayout()
        self.ai_input = QTextEdit()
        self.ai_input.setMaximumHeight(80)
        self.ai_input.setFont(font_ai)
        self.ai_input.setPlaceholderText("Message AI...")
        input_layout.addWidget(self.ai_input)
        
        btn_layout = QVBoxLayout()
        self.ai_send_btn = QPushButton("➤")
        self.ai_send_btn.setFixedSize(40, 35)
        self.ai_send_btn.setFont(QFont("Segoe UI", 14))
        self.ai_send_btn.clicked.connect(self.ask_ai)
        
        self.ai_stop_btn = QPushButton("⏹")
        self.ai_stop_btn.setFixedSize(40, 35)
        self.ai_stop_btn.setFont(QFont("Segoe UI", 12))
        self.ai_stop_btn.clicked.connect(self.stop_ai)
        self.ai_stop_btn.setEnabled(False)
        
        btn_layout.addWidget(self.ai_send_btn)
        btn_layout.addWidget(self.ai_stop_btn)
        input_layout.addLayout(btn_layout)
        
        ai_layout.addLayout(input_layout)
        
        self.ai_dock.setWidget(ai_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.ai_dock)
        
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

    def refresh_ollama_models(self):
        api_key = self.ai_api_key_input.text().strip() if hasattr(self, 'ai_api_key_input') else OLLAMA_CLOUD_API_KEY
        if not api_key:
            return
        try:
            headers = {
                'Authorization': f'Bearer {api_key}'
            }
            req = urllib.request.Request(f"{OLLAMA_CLOUD_BASE_URL}/api/tags", headers=headers)
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

    def stop_ai(self):
        if hasattr(self, 'ai_worker') and self.ai_worker.isRunning():
            self.ai_worker.stop()
            self.ai_send_btn.setEnabled(True)
            self.ai_stop_btn.setEnabled(False)
            cursor = self.ai_output.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            cursor.select(cursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            self.ai_output.append("<i style='color:orange;'>Stopped.</i>")

    def ask_ai(self):
        prompt = self.ai_input.toPlainText().strip()
        if not prompt: return
        
        model = self.ai_model_combo.currentText() or "llama3.2"
        api_key = self.ai_api_key_input.text().strip() or OLLAMA_CLOUD_API_KEY

        if not api_key:
            self.ai_output.append("<b style='color:red;'>Error:</b> No API key provided. Please enter your Ollama Cloud API key.")
            return
            
        self.ai_send_btn.setEnabled(False)
        self.ai_stop_btn.setEnabled(True)
        self.ai_output.append(f"<br><b>You:</b> {html.escape(prompt)}")
        self.ai_output.append("<i>Generating... (Ollama Cloud)</i>")
        
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
            
        messages = [{"role": "system", "content": system_prompt}] + self.chat_history + [{"role": "user", "content": prompt}]
            
        self.ai_worker = OllamaWorker(model, messages, api_key=api_key)
        self.ai_worker.finished.connect(self.on_ai_finished)
        self.ai_worker.error.connect(self.on_ai_error)
        self.ai_worker.start()

    def on_ai_finished(self, response):
        self.ai_send_btn.setEnabled(True)
        self.ai_stop_btn.setEnabled(False)
        cursor = self.ai_output.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.select(cursor.SelectionType.BlockUnderCursor)
        cursor.removeSelectedText()
        
        self.ai_input.clear()
        
        # Add to chat history
        prompt = self.ai_worker.messages[-1]["content"]
        self.chat_history.append({"role": "user", "content": prompt})
        self.chat_history.append({"role": "assistant", "content": response})
        self.save_ai_memory()
        
        # Display response
        self.ai_output.append(f"<b>AI ({self.ai_worker.model}):</b><br><pre>{html.escape(response)}</pre>")
        
        # Parse for creations/edits
        create_matches = re.finditer(r'\[CREATE_FILE:\s*([^\]\s]+)\]\s*```(?:verilog|v)?\n(.*?)\n?```', response, re.DOTALL | re.IGNORECASE)
        for match in create_matches:
            filename = match.group(1).strip()
            code = match.group(2)
            proj_dir = self.current_project_dir or os.getcwd()
            filepath = os.path.join(proj_dir, filename)
            try:
                with open(filepath, 'w') as f:
                    f.write(code)
                self.open_file(filepath)
                self.ai_output.append(f"<i style='color:green;'>Created and opened file: {filename}</i>")
            except Exception as e:
                self.ai_output.append(f"<b style='color:red;'>Failed to create file {filename}: {e}</b>")
                
        edit_matches = re.finditer(r'\[EDIT_ACTIVE_FILE\]\s*```(?:verilog|v)?\n(.*?)```', response, re.DOTALL | re.IGNORECASE)
        for match in edit_matches:
            code = match.group(1)
            target_tabs = self.last_focused_tabs if not self.editor_tabs_right.isHidden() else self.editor_tabs
            current_editor = target_tabs.currentWidget()
            if current_editor:
                current_editor.setPlainText(code)
                self.ai_output.append("<i style='color:green;'>Updated active file.</i>")
            else:
                self.ai_output.append("<b style='color:red;'>No active file to edit.</b>")

    def on_ai_error(self, error):
        self.ai_send_btn.setEnabled(True)
        self.ai_stop_btn.setEnabled(False)
        cursor = self.ai_output.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.select(cursor.SelectionType.BlockUnderCursor)
        cursor.removeSelectedText()
        self.ai_output.append(f"<b style='color:red;'>Error:</b> {error}")

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
        self.ai_output.clear()
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
                        role = "You" if msg["role"] == "user" else "AI"
                        self.ai_output.append(f"<b>{role}:</b><br><pre>{html.escape(msg['content'])}</pre>")
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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = VerilogIDE()
    window.show()
    sys.exit(app.exec())