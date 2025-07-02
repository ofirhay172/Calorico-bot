"""
Database setup module for the Calorico Telegram bot.

This module handles initial database creation and setup.
"""

from db import NutritionDB
import sqlite3

# Initialize database
nutrition_db = NutritionDB()
print("✅ בסיס הנתונים נוצר בהצלחה.")
