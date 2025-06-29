#!/usr/bin/env python3
"""
Basic tests for Calorico Telegram Bot.
"""

import unittest
import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import validate_numeric_input, calculate_bmr, detect_allergens_in_text
from nutrition_db import init_db
from config import GENDER_OPTIONS, GOAL_OPTIONS, DIET_OPTIONS


class TestUtils(unittest.TestCase):
    """Test utility functions."""

    def test_validate_numeric_input(self):
        """Test numeric input validation."""
        # Valid inputs
        self.assertTrue(validate_numeric_input("25", 13, 120))
        self.assertTrue(validate_numeric_input("170", 100, 250))
        self.assertTrue(validate_numeric_input("70", 30, 300))
        
        # Invalid inputs
        self.assertFalse(validate_numeric_input("abc", 13, 120))
        self.assertFalse(validate_numeric_input("12", 13, 120))  # Below range
        self.assertFalse(validate_numeric_input("130", 13, 120))  # Above range
        self.assertFalse(validate_numeric_input("", 13, 120))
        self.assertFalse(validate_numeric_input(None, 13, 120))

    def test_calculate_bmr(self):
        """Test BMR calculation."""
        # Test male
        bmr_male = calculate_bmr("זכר", 30, 170, 70, "בינונית", "שמירה על משקל")
        self.assertIsInstance(bmr_male, int)
        self.assertGreater(bmr_male, 0)
        
        # Test female
        bmr_female = calculate_bmr("נקבה", 25, 160, 60, "בינונית", "שמירה על משקל")
        self.assertIsInstance(bmr_female, int)
        self.assertGreater(bmr_female, 0)
        
        # Test that female BMR is generally lower than male
        self.assertLess(bmr_female, bmr_male)

    def test_detect_allergens_in_text(self):
        """Test allergen detection."""
        # Test with allergens
        text_with_allergens = "אכלתי לחם עם חלב וביצים"
        allergens = detect_allergens_in_text(text_with_allergens)
        self.assertIn("חלב", allergens)
        self.assertIn("ביצים", allergens)
        
        # Test without allergens
        text_without_allergens = "אכלתי תפוח עץ"
        allergens = detect_allergens_in_text(text_without_allergens)
        self.assertEqual(len(allergens), 0)


class TestConfig(unittest.TestCase):
    """Test configuration constants."""

    def test_gender_options(self):
        """Test gender options."""
        self.assertIn("זכר", GENDER_OPTIONS)
        self.assertIn("נקבה", GENDER_OPTIONS)
        self.assertIn("אחר", GENDER_OPTIONS)

    def test_goal_options(self):
        """Test goal options."""
        self.assertIn("ירידה במשקל", GOAL_OPTIONS)
        self.assertIn("עלייה במסת שריר", GOAL_OPTIONS)
        self.assertIn("שמירה על משקל", GOAL_OPTIONS)

    def test_diet_options(self):
        """Test diet options."""
        self.assertIn("צמחוני", DIET_OPTIONS)
        self.assertIn("טבעוני", DIET_OPTIONS)
        self.assertIn("קטוגני", DIET_OPTIONS)


class TestDatabase(unittest.TestCase):
    """Test database functions."""

    def test_init_db(self):
        """Test database initialization."""
        try:
            init_db()
            # If no exception is raised, the test passes
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Database initialization failed: {e}")


if __name__ == "__main__":
    # Run tests
    unittest.main(verbosity=2) 