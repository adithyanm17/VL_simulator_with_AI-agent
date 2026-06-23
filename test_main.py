import unittest
from unittest.mock import patch, MagicMock
import json
import urllib.error

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from PyQt5.QtWidgets import QApplication
import main  # Import main after adding to sys.path

# Need a QApplication instance before creating QWidget subclasses
app = QApplication(sys.argv)

class TestOllamaWorker(unittest.TestCase):
    @patch('main.urllib.request.urlopen')
    def test_run_success(self, mock_urlopen):
        # Mock successful response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "message": {"content": "Hello from Ollama!"}
        }).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        worker = main.OllamaWorker(model="llama3.2", messages=[])
        
        # We need to capture the emitted signal
        self.finished_result = None
        def on_finished(content):
            self.finished_result = content
            
        worker.finished.connect(on_finished)
        worker.run()
        
        self.assertEqual(self.finished_result, "Hello from Ollama!")

    @patch('main.urllib.request.urlopen')
    def test_run_http_error(self, mock_urlopen):
        # Mock HTTP Error
        error_mock = urllib.error.HTTPError(url="", code=404, msg="Not Found", hdrs={}, fp=MagicMock())
        error_mock.read = MagicMock(return_value=b'Model not found')
        mock_urlopen.side_effect = error_mock

        worker = main.OllamaWorker(model="nonexistent", messages=[])
        
        self.error_result = None
        def on_error(msg):
            self.error_result = msg
            
        worker.error.connect(on_error)
        worker.run()
        
        self.assertEqual(self.error_result, "HTTP 404 Error: Model not found")


class TestTerminalWidget(unittest.TestCase):
    def setUp(self):
        self.terminal = main.TerminalWidget()

    def test_build_args_default(self):
        exe, args = self.terminal._build_args("dir")
        self.assertEqual(exe, "cmd.exe")
        self.assertTrue(args[0] == "/c")
        self.assertEqual(args[1], "dir")

    def test_build_args_powershell(self):
        exe, args = self.terminal._build_args("ps: ls")
        self.assertTrue("powershell" in exe.lower() or "cmd.exe" in exe.lower())
        self.assertTrue("-Command" in args)
        
    def test_set_cwd(self):
        test_path = "C:\\test\\path"
        self.terminal.set_cwd(test_path)
        self.assertEqual(self.terminal._cwd, test_path)
        self.assertEqual(self.terminal._cwd_label.text(), test_path)

if __name__ == '__main__':
    unittest.main()
