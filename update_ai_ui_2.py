import os
import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove the old ai_model_combo from row1
start_row1 = content.find("self._ai_model_lbl = QLabel")
end_row1 = content.find("self.ai_refresh_btn = QPushButton", start_row1)
if start_row1 != -1 and end_row1 != -1:
    content = content[:start_row1] + content[end_row1:]

# 2. Add ai_model_combo to the bottom_row of ai_input_bar
combo_code = """
        self.ai_model_combo = QComboBox()
        self.ai_model_combo.addItems(["llama3.2", "llama3", "llama3.1", "gemma3:4b",
                                      "qwen2.5-coder:7b", "deepseek-coder-v2", "mistral", "codellama"])
        self.ai_model_combo.setToolTip("Select Model")
        self.ai_model_combo.setStyleSheet("QComboBox { border: none; background: transparent; padding: 2px 8px; font-weight: bold; } QComboBox::drop-down { border: none; }")
        self.ai_model_combo.currentTextChanged.connect(self.save_ai_model_state)
        bottom_row.addWidget(self.ai_model_combo)
"""
attach_btn_loc = content.find("bottom_row.addWidget(self.ai_attach_btn)")
if attach_btn_loc != -1:
    insert_loc = content.find('\n', attach_btn_loc) + 1
    content = content[:insert_loc] + combo_code + content[insert_loc:]

# 3. Modify attach_ai_image to include 'X' button
old_attach = """    def attach_ai_image(self):
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
        self.ai_attachments_lay.addWidget(lbl)"""

new_attach = """    def attach_ai_image(self):
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
            
        # Create composite widget
        frame = QFrame()
        frame.setFixedSize(48, 48)
        frame.setStyleSheet("QFrame { background: transparent; }")
        
        lbl = QLabel(frame)
        from PyQt5.QtGui import QPixmap
        pix = QPixmap(file_path)
        lbl.setPixmap(pix.scaled(40, 40, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        lbl.setFixedSize(40, 40)
        lbl.move(0, 8)
        lbl.setStyleSheet("border: 1px solid gray; border-radius: 4px; background: white;")
        
        close_btn = QPushButton("✕", frame)
        close_btn.setFixedSize(16, 16)
        close_btn.move(32, 0)
        close_btn.setStyleSheet("QPushButton { border: none; border-radius: 8px; background: #444; color: white; font-size: 10px; font-weight: bold; } QPushButton:hover { background: red; }")
        
        def remove_attachment():
            if b64 in self._current_attachments:
                self._current_attachments.remove(b64)
            frame.deleteLater()
            self._update_ai_attachments_ui()
            
        close_btn.clicked.connect(remove_attachment)
        self.ai_attachments_lay.addWidget(frame)
        self._current_attachments.append(b64)
        self._update_ai_attachments_ui()

    def _update_ai_attachments_ui(self):
        # Update visibility and styling based on count
        has_items = len(self._current_attachments) > 0
        if has_items:
            self._ai_input_bar.setStyleSheet(self._ai_input_bar.styleSheet().replace("border-radius: 8px;", "border-radius: 8px; border-top: 2px solid #ccc;"))
        else:
            # Let apply_theme reset it next time or just basic reset
            pass

    def save_ai_model_state(self, model_name):
        self.save_config("last_ai_model", model_name)
"""

content = content.replace(old_attach, new_attach)

# 4. Modify clear_ai_attachments to call _update_ai_attachments_ui
old_clear = """    def clear_ai_attachments(self):
        self._current_attachments.clear()
        while self.ai_attachments_lay.count():
            item = self.ai_attachments_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()"""
new_clear = """    def clear_ai_attachments(self):
        self._current_attachments.clear()
        while self.ai_attachments_lay.count():
            item = self.ai_attachments_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._update_ai_attachments_ui()"""
content = content.replace(old_clear, new_clear)

# 5. Insert load state logic near self._reload_key_combo()
load_code = """
        last_model = {}
        try:
            if hasattr(self, 'config_path') and os.path.exists(self.config_path):
                import json
                with open(self.config_path, "r") as f:
                    config = json.load(f)
                    last_m = config.get("last_ai_model", "")
                    if last_m:
                        self.ai_model_combo.setCurrentText(last_m)
        except:
            pass
"""
key_combo_loc = content.find("self._reload_key_combo()")
if key_combo_loc != -1:
    insert_loc2 = content.find('\n', key_combo_loc) + 1
    content = content[:insert_loc2] + load_code + content[insert_loc2:]

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done")
