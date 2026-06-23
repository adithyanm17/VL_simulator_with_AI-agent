import os
import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Locate the TerminalWidget
start_marker = "class TerminalWidget(QWidget):"
end_marker = "# ── Provider URL presets ─────────────────────────────────────────────────────"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("Could not find TerminalWidget boundaries")
    exit(1)

new_terminal_code = """class TerminalWidget(QWidget):
    \"\"\"A VS Code-style inline integrated terminal.
    
    Each command is run as a fresh subprocess (cmd /c or powershell -Command)
    so output is always captured and displayed reliably on Windows.
    \"\"\"

    # Theme palette
    DARK = {
        "bar_bg": "#252526",
        "bar_border": "#333333",
        "output_bg": "#1e1e1e",
        "output_fg": "#d4d4d4",
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
        self._running_proc: QProcess | None = None
        self._cwd: str = os.getcwd()
        self._colors = dict(self.DARK)
        self._prompt_pos = 0  # To track where the prompt ends
        self._is_locked = False
        
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

        # ── Inline Output & Input ───────────────────────────────────
        self._output = QPlainTextEdit()
        self._output.setFont(QFont("Consolas", 11))
        self._output.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self._output.installEventFilter(self)
        root.addWidget(self._output, stretch=1)

        self._apply_palette()

    def _shell_executable(self) -> str:
        ps = shutil.which("powershell.exe") or shutil.which("powershell")
        return ps if ps else "cmd.exe"

    def _shell_name(self) -> str:
        exe = self._shell_executable()
        return "PowerShell" if "powershell" in exe.lower() else "CMD"

    def _print_banner(self):
        shell_name = self._shell_name()
        self._shell_label.setText(f"⚡ {shell_name}")
        self._append_text(
            f"[Terminal] {shell_name} — each command runs as a subprocess.\\n"
            f"  Working dir: {self._cwd}\\n"
            f"  Use 'cd <path>' to change directory.\\n",
            color="info"
        )
        self._print_prompt()

    def _print_prompt(self):
        shell_name = self._shell_name()
        prefix = "PS " if "PowerShell" in shell_name else ""
        prompt = f"{prefix}{self._cwd}> "
        self._append_text(prompt, color="prompt")
        
        # Mark the uneditable position
        cursor = self._output.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._output.setTextCursor(cursor)
        self._prompt_pos = cursor.position()
        self._is_locked = False

    def apply_theme(self, theme_name: str):
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

    def _build_args(self, cmd: str) -> tuple[str, list[str]]:
        if cmd.lower().startswith("ps:"):
            ps_cmd = cmd[3:].strip()
            exe = self._shell_executable()
            full = f'Push-Location "{self._cwd}"; {ps_cmd}; Pop-Location'
            return exe, ["-NoLogo", "-NonInteractive", "-Command", full]
        return "cmd.exe", ["/c", f'cd /d "{self._cwd}" && {cmd}']

    def _send_command(self):
        # Extract command after prompt
        cursor = self._output.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.setPosition(self._prompt_pos, QTextCursor.KeepAnchor)
        cmd = cursor.selectedText().strip()
        
        # Move cursor to end and print newline
        cursor.movePosition(QTextCursor.End)
        self._output.setTextCursor(cursor)
        self._append_text("\\n")
        
        self._is_locked = True

        if not cmd:
            self._print_prompt()
            return

        # History
        if not self._history or self._history[-1] != cmd:
            self._history.append(cmd)
        self._hist_idx = -1

        cd_match = re.match(r'^cd\s+(.+)$', cmd, re.IGNORECASE)
        if cd_match:
            target = cd_match.group(1).strip().strip('"').strip("'")
            new_path = target if os.path.isabs(target) else os.path.join(self._cwd, target)
            new_path = os.path.normpath(new_path)
            if os.path.isdir(new_path):
                self._cwd = new_path
                self._cwd_label.setText(new_path)
            else:
                self._append_text(f"cd: No such directory: {new_path}\\n", color="error")
            self._print_prompt()
            return

        exe, args = self._build_args(cmd)
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.MergedChannels)
        proc.readyReadStandardOutput.connect(lambda: self._on_proc_output(proc))
        proc.finished.connect(lambda code, status: self._on_proc_finished(proc, code))
        proc.setWorkingDirectory(self._cwd)
        proc.start(exe, args)

        if proc.waitForStarted(3000):
            self._running_proc = proc
            self._kill_btn.setEnabled(True)
        else:
            self._append_text(f"[Terminal] Failed to start: {exe}\\n", color="error")
            self._print_prompt()

    def _kill_process(self):
        if self._running_proc and self._running_proc.state() != QProcess.NotRunning:
            self._running_proc.kill()
            self._append_text("[Terminal] Process killed.\\n", color="error")

    def _clear_output(self):
        self._output.clear()
        self._print_banner()

    def set_cwd(self, path: str):
        self._cwd = path
        self._cwd_label.setText(path)
        self._append_text(f"\\n[Terminal] Working directory set to: {path}\\n", color="info")
        if not self._is_locked:
            self._print_prompt()

    def _on_proc_output(self, proc: QProcess):
        raw: QByteArray = proc.readAllStandardOutput()
        try:
            text = raw.data().decode("utf-8", errors="replace")
        except Exception:
            text = str(raw.data())
        text = re.sub(r'\\x1b\\[[0-9;]*[mGKHFJK]', '', text)
        text = text.replace('\\r\\n', '\\n').replace('\\r', '\\n')
        self._append_text(text)

    def _on_proc_finished(self, proc: QProcess, exit_code: int):
        self._on_proc_output(proc)
        if exit_code != 0:
            self._append_text(f"[Exit code: {exit_code}]\\n", color="error")
        self._running_proc = None
        self._kill_btn.setEnabled(False)
        self._print_prompt()

    def _append_text(self, text: str, color: str = "normal"):
        cursor = self._output.textCursor()
        cursor.movePosition(QTextCursor.End)
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

    def eventFilter(self, obj, event):
        from PyQt5.QtCore import QEvent, Qt
        if obj is self._output and event.type() == QEvent.KeyPress:
            if self._is_locked:
                return True # Block all input while running
            
            key = event.key()
            cursor = self._output.textCursor()
            
            # Force cursor to end if it's before the prompt
            if cursor.position() < self._prompt_pos:
                cursor.movePosition(QTextCursor.End)
                self._output.setTextCursor(cursor)

            if key == Qt.Key_Return or key == Qt.Key_Enter:
                self._send_command()
                return True
                
            elif key == Qt.Key_Backspace:
                if cursor.position() <= self._prompt_pos:
                    return True # Prevent deleting prompt
                    
            elif key == Qt.Key_Left:
                if cursor.position() <= self._prompt_pos:
                    return True # Prevent moving cursor into prompt
                    
            elif key == Qt.Key_Home:
                cursor.setPosition(self._prompt_pos)
                self._output.setTextCursor(cursor)
                return True
                
            elif key == Qt.Key_Up:
                if self._history:
                    if self._hist_idx == -1:
                        self._hist_idx = len(self._history) - 1
                    elif self._hist_idx > 0:
                        self._hist_idx -= 1
                    self._replace_input(self._history[self._hist_idx])
                return True
                
            elif key == Qt.Key_Down:
                if self._hist_idx != -1:
                    self._hist_idx += 1
                    if self._hist_idx >= len(self._history):
                        self._hist_idx = -1
                        self._replace_input("")
                    else:
                        self._replace_input(self._history[self._hist_idx])
                return True
                
        return super().eventFilter(obj, event)

    def _replace_input(self, text: str):
        cursor = self._output.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.setPosition(self._prompt_pos, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        
        # Reset color to normal text
        fmt = self._output.currentCharFormat()
        fmt.setForeground(QColor(self._colors["output_fg"]))
        cursor.setCharFormat(fmt)
        cursor.insertText(text)
        self._output.setTextCursor(cursor)

"""

new_content = content[:start_idx] + new_terminal_code + "\n" + content[end_idx:]

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
print("Done")
