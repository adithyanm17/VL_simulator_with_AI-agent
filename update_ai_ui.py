import os
import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update the UI layout
start_marker_ui = "# ── Input bar ─────────────────────────────────────────────────────────"
end_marker_ui = "self.ai_dock.setWidget(ai_widget)"

start_idx_ui = content.find(start_marker_ui)
end_idx_ui = content.find(end_marker_ui)

if start_idx_ui == -1 or end_idx_ui == -1:
    print("Could not find AI Input Bar boundaries")
    exit(1)

new_ui_code = """# ── Input bar ─────────────────────────────────────────────────────────
        self._ai_input_bar = QFrame()
        self._ai_input_bar.setObjectName("AIInputBar")
        # Will be styled dynamically in apply_theme
        
        input_bar_lay = QVBoxLayout(self._ai_input_bar)
        input_bar_lay.setContentsMargins(6, 6, 6, 6)
        input_bar_lay.setSpacing(4)

        # Attachments area
        self.ai_attachments_lay = QHBoxLayout()
        input_bar_lay.addLayout(self.ai_attachments_lay)

        # Bottom row
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(6)

        self.ai_attach_btn = QPushButton("➕")
        self.ai_attach_btn.setFixedSize(32, 32)
        self.ai_attach_btn.setToolTip("Attach Image")
        self.ai_attach_btn.clicked.connect(self.attach_ai_image)
        bottom_row.addWidget(self.ai_attach_btn)

        self.ai_input = QTextEdit()
        self.ai_input.setMaximumHeight(80)
        self.ai_input.setMinimumHeight(32)
        self.ai_input.setFont(QFont("Consolas", 10))
        self.ai_input.setPlaceholderText("Ask anything, @ to mention, / for actions")
        self.ai_input.installEventFilter(self)
        bottom_row.addWidget(self.ai_input)

        self.ai_action_btn = QPushButton("➤")
        self.ai_action_btn.setFixedSize(32, 32)
        self.ai_action_btn.setToolTip("Send message")
        self.ai_action_btn.clicked.connect(self.on_ai_action_clicked)
        bottom_row.addWidget(self.ai_action_btn)

        input_bar_lay.addLayout(bottom_row)
        ai_layout.addWidget(self._ai_input_bar)
        
        self._current_attachments = []
        self._ai_prompt_history = []
        self._ai_hist_idx = -1

        """

content = content[:start_idx_ui] + new_ui_code + content[end_idx_ui:]

# 2. Add new methods and modify ask_ai / stop_ai
# Let's locate stop_ai and ask_ai
start_marker_methods = "    def stop_ai(self):"
end_marker_methods = "    def on_ai_finished(self, response):"

start_idx_methods = content.find(start_marker_methods)
end_idx_methods = content.find(end_marker_methods)

new_methods_code = """    def attach_ai_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Attach Image", "", "Images (*.png *.xpm *.jpg *.jpeg *.bmp)")
        if not file_path:
            return
        
        # Read and encode to base64
        try:
            import base64
            with open(file_path, "rb") as img_file:
                b64 = base64.b64encode(img_file.read()).decode("utf-8")
        except Exception as e:
            QMessageBox.warning(self, "Image Error", f"Failed to load image: {e}")
            return
            
        self._current_attachments.append(b64)
        
        # Add thumbnail to layout
        lbl = QLabel()
        from PyQt5.QtGui import QPixmap
        pix = QPixmap(file_path)
        lbl.setPixmap(pix.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        lbl.setFixedSize(40, 40)
        lbl.setStyleSheet("border: 1px solid gray; border-radius: 4px;")
        self.ai_attachments_lay.addWidget(lbl)

    def clear_ai_attachments(self):
        self._current_attachments.clear()
        while self.ai_attachments_lay.count():
            item = self.ai_attachments_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def on_ai_action_clicked(self):
        if self.ai_action_btn.text() == "⏹":
            self.stop_ai()
        else:
            self.ask_ai()

    def stop_ai(self):
        if hasattr(self, 'ai_worker') and self.ai_worker.isRunning():
            self.ai_worker.stop()
            self._set_ai_action_state("send")
            self._add_chat_bubble("Generation stopped.", "system")

    def _set_ai_action_state(self, state):
        c = self._colors if hasattr(self, '_colors') else {}
        if state == "stop":
            self.ai_action_btn.setText("⏹")
            self.ai_action_btn.setToolTip("Stop AI generation")
            self.ai_action_btn.setStyleSheet(f"QPushButton {{ border: none; border-radius: 16px; background: {c.get('error_color', '#F44747')}; color: white; font-size: 14px; }} QPushButton:hover {{ background: darkred; }}")
        else:
            self.ai_action_btn.setText("➤")
            self.ai_action_btn.setToolTip("Send message")
            self.ai_action_btn.setStyleSheet(f"QPushButton {{ border: none; border-radius: 16px; background: {c.get('input_focus', '#007acc')}; color: white; font-size: 14px; }} QPushButton:hover {{ opacity: 0.8; }}")

    def ask_ai(self):
        prompt = self.ai_input.toPlainText().strip()
        if not prompt and not self._current_attachments:
            return

        if prompt and (not self._ai_prompt_history or self._ai_prompt_history[-1] != prompt):
            self._ai_prompt_history.append(prompt)
        self._ai_hist_idx = -1

        model = self.ai_model_combo.currentText() or "llama3.2"
        profile = self.get_active_key()
        api_key = profile.get("key", "") or OLLAMA_CLOUD_API_KEY
        base_url = profile.get("base_url", OLLAMA_CLOUD_BASE_URL)
        max_tokens = int(self.ai_ctx_combo.currentText())

        if not api_key:
            self._add_chat_bubble("No API key configured. Go to Edit → Manage API Keys to add one.", "error")
            return

        self._set_ai_action_state("stop")
        self.ai_input.clear()

        # Build message payload
        user_msg = {"role": "user", "content": prompt}
        if self._current_attachments:
            user_msg["images"] = list(self._current_attachments)
        self.clear_ai_attachments()

        # Show user bubble
        self._add_chat_bubble(prompt or "[Image attached]", "user")
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
            "You are an advanced AI coding assistant integrated into a Verilog IDE.\\n"
            "You can create or edit files directly. To create a new file, your response MUST contain exactly:\\n"
            "[CREATE_FILE: filename.v]\\n```verilog\\n// complete code here\\n```\\n\\n"
            "To completely replace/edit the currently active file, use exactly:\\n"
            "[EDIT_ACTIVE_FILE]\\n```verilog\\n// complete new code here\\n```\\n\\n"
            "Always output the full file content without placeholders when using these tags."
        )
        if context:
            system_prompt += f"\\n\\nCURRENT ACTIVE FILE ({active_file_name}):\\n```verilog\\n{context}\\n```"

        messages = ([{"role": "system", "content": system_prompt}]
                    + self.chat_history
                    + [user_msg])

        self.ai_worker = OllamaWorker(model, messages,
                                      api_key=api_key,
                                      base_url=base_url,
                                      max_tokens=max_tokens)
        self.ai_worker.finished.connect(self.on_ai_finished)
        self.ai_worker.error.connect(self.on_ai_error)
        self.ai_worker.start()

"""

content = content[:start_idx_methods] + new_methods_code + content[end_idx_methods:]

# 3. Update finished and error to reset the button
content = content.replace("self.ai_send_btn.setEnabled(True)", "self._set_ai_action_state('send')")
content = content.replace("self.ai_stop_btn.setEnabled(False)", "")

# 4. Modify apply_theme to handle the new frame properly
theme_search = "        self._ai_header.setStyleSheet(f\"background:{c['bar_bg']}; border-bottom:1px solid {c['bar_border']};\")"

theme_append = """
        if hasattr(self, '_ai_input_bar'):
            self._ai_input_bar.setStyleSheet(
                f"QFrame#AIInputBar {{ border: 1px solid {c['input_border']}; border-radius: 8px; background: {c['input_bg']}; }}"
            )
            self.ai_input.setStyleSheet(f"QTextEdit {{ border: none; background: transparent; color: {c['input_fg']}; }}")
            self.ai_attach_btn.setStyleSheet(f"QPushButton {{ border: none; border-radius: 16px; background: transparent; font-size: 16px; color: {c['input_fg']}; }} QPushButton:hover {{ background: {c['btn_hover']}; }}")
            self._set_ai_action_state("send")
"""
content = content.replace(theme_search, theme_search + theme_append)

# 5. Add eventFilter for history navigation
# VerilogIDE's eventFilter
start_ef = "        if obj is self.ai_input and event.type() == Qt.Key_KeyPress:"

ef_code = """        if obj is self.ai_input and event.type() == Qt.Key_KeyPress:
            if event.key() == Qt.Key_Up:
                if self._ai_prompt_history:
                    if self._ai_hist_idx == -1:
                        self._ai_hist_idx = len(self._ai_prompt_history) - 1
                    elif self._ai_hist_idx > 0:
                        self._ai_hist_idx -= 1
                    self.ai_input.setPlainText(self._ai_prompt_history[self._ai_hist_idx])
                    cursor = self.ai_input.textCursor()
                    cursor.movePosition(QTextCursor.End)
                    self.ai_input.setTextCursor(cursor)
                return True
            elif event.key() == Qt.Key_Down:
                if self._ai_hist_idx != -1:
                    self._ai_hist_idx += 1
                    if self._ai_hist_idx >= len(self._ai_prompt_history):
                        self._ai_hist_idx = -1
                        self.ai_input.clear()
                    else:
                        self.ai_input.setPlainText(self._ai_prompt_history[self._ai_hist_idx])
                        cursor = self.ai_input.textCursor()
                        cursor.movePosition(QTextCursor.End)
                        self.ai_input.setTextCursor(cursor)
                return True
"""
if "event.type() == Qt.Key_KeyPress" in content:
    print("Found exact eventFilter match.")
    pass
else:
    # Need to find VerilogIDE eventFilter
    ef_idx = content.find("def eventFilter(self, obj, event):")
    ef_idx = content.find("def eventFilter(self, obj, event):", ef_idx + 1)
    # The second one is VerilogIDE's
    if ef_idx != -1:
        # replace inside VerilogIDE's eventFilter
        search_target = "        if obj == getattr(self, 'ai_input', None) and event.type() == QEvent.KeyPress:"
        if search_target in content:
            replace_target = """        if obj == getattr(self, 'ai_input', None) and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Up:
                if getattr(self, '_ai_prompt_history', None):
                    if self._ai_hist_idx == -1:
                        self._ai_hist_idx = len(self._ai_prompt_history) - 1
                    elif self._ai_hist_idx > 0:
                        self._ai_hist_idx -= 1
                    self.ai_input.setPlainText(self._ai_prompt_history[self._ai_hist_idx])
                    cursor = self.ai_input.textCursor()
                    cursor.movePosition(QTextCursor.End)
                    self.ai_input.setTextCursor(cursor)
                return True
            elif event.key() == Qt.Key_Down:
                if getattr(self, '_ai_prompt_history', None) and self._ai_hist_idx != -1:
                    self._ai_hist_idx += 1
                    if self._ai_hist_idx >= len(self._ai_prompt_history):
                        self._ai_hist_idx = -1
                        self.ai_input.clear()
                    else:
                        self.ai_input.setPlainText(self._ai_prompt_history[self._ai_hist_idx])
                        cursor = self.ai_input.textCursor()
                        cursor.movePosition(QTextCursor.End)
                        self.ai_input.setTextCursor(cursor)
                return True
"""
            content = content.replace(search_target, replace_target)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done")
