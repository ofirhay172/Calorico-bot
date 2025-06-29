"""
Database setup module for the Calorico Telegram bot.

This module handles initial database creation and setup.
"""

from nutrition_db import init_db
import sqlite3

init_db()
print("✅ בסיס הנתונים נוצר בהצלחה.")
