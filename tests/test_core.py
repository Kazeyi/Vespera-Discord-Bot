import unittest
import sys
import os

# Add bot root to path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_manager import sanitize_input

class TestCoreSecurity(unittest.TestCase):
    def test_sanitize_input_basic(self):
        self.assertEqual(sanitize_input("hello world"), "hello world")

    def test_sanitize_input_truncation(self):
        long_string = "a" * 3000
        result = sanitize_input(long_string, max_length=2000)
        self.assertEqual(len(result), 2000)
        self.assertEqual(result, "a" * 2000)

    def test_sanitize_input_escapes(self):
        # Ensure it removes null bytes and escapes quotes according to its documented behavior
        result = sanitize_input("test\\string\x00data")
        
        # Original code replaces '\x00' with '' and '\\' with '\\\\'
        self.assertEqual(result, "test\\\\stringdata")

    def test_sanitize_input_not_string(self):
        self.assertEqual(sanitize_input(1234), "")
        self.assertEqual(sanitize_input(["list"]), "")

if __name__ == '__main__':
    unittest.main()
