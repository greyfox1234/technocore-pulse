"""Unit tests for Technocore client normalization and validation."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import unittest
from technocore_pulse.client import normalize_text


class TestClient(unittest.TestCase):
    def test_normalize_text(self):
        raw = "   Hello \u200bworld! \n  "
        cleaned = normalize_text(raw)
        self.assertEqual(cleaned, "Hello  world!")

    def test_normalize_empty(self):
        with self.assertRaises(ValueError):
            normalize_text("   \u200b  ")


if __name__ == "__main__":
    unittest.main()
