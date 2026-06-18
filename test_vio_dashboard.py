import unittest
import sys
import os

# Ensure the parent directory is in the sys.path if needed
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from vio_dashboard import VerilogGateParser

class TestVerilogGateParser(unittest.TestCase):
    def setUp(self):
        self.parser = VerilogGateParser()

    def test_parse_primitives(self):
        # Space added before '(' to match the parser's regex `(?:\w+\s+)?`
        code = "and g1 (out, a, b);"
        gates = self.parser.parse(code)
        self.assertEqual(len(gates), 1)
        self.assertEqual(gates[0].gate_type, "AND")
        self.assertEqual(gates[0].output, "out")
        self.assertEqual(gates[0].inputs, ["a", "b"])

    def test_parse_assigns_and(self):
        code = "assign out = a & b;"
        gates = self.parser.parse(code)
        self.assertEqual(len(gates), 1)
        self.assertEqual(gates[0].gate_type, "AND")
        self.assertEqual(gates[0].output, "out")
        self.assertEqual(gates[0].inputs, ["a", "b"])

    def test_parse_assigns_nand(self):
        code = "assign out = ~(a & b);"
        gates = self.parser.parse(code)
        self.assertEqual(len(gates), 1)
        self.assertEqual(gates[0].gate_type, "NAND")
        self.assertEqual(gates[0].output, "out")
        self.assertEqual(gates[0].inputs, ["a", "b"])
        
    def test_parse_assigns_or(self):
        code = "assign out = a | b;"
        gates = self.parser.parse(code)
        self.assertEqual(len(gates), 1)
        self.assertEqual(gates[0].gate_type, "OR")
        self.assertEqual(gates[0].output, "out")
        self.assertEqual(gates[0].inputs, ["a", "b"])

    def test_parse_assigns_xor(self):
        code = "assign out = a ^ b;"
        gates = self.parser.parse(code)
        self.assertEqual(len(gates), 1)
        self.assertEqual(gates[0].gate_type, "XOR")
        self.assertEqual(gates[0].output, "out")
        self.assertEqual(gates[0].inputs, ["a", "b"])

    def test_parse_assigns_not(self):
        code = "assign out = ~a;"
        gates = self.parser.parse(code)
        self.assertEqual(len(gates), 1)
        self.assertEqual(gates[0].gate_type, "NOT")
        self.assertEqual(gates[0].output, "out")
        self.assertEqual(gates[0].inputs, ["a"])
        
    def test_parse_assigns_buf(self):
        code = "assign out = a;"
        gates = self.parser.parse(code)
        self.assertEqual(len(gates), 1)
        self.assertEqual(gates[0].gate_type, "BUF")
        self.assertEqual(gates[0].output, "out")
        self.assertEqual(gates[0].inputs, ["a"])

if __name__ == '__main__':
    unittest.main()
