"""
Nutrition database module for the Calorico Telegram bot.

This module handles nutrition data storage and retrieval operations.
"""

import sqlite3
import json
import re
import logging
from datetime import date, datetime
from typing import List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

DB_NAME = "nutrition_data.db"


def init_db() -> None:
    """יצירת בסיס הנתונים (פעם אחת בלבד)."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS nutrition_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                calories INTEGER DEFAULT 0,
                protein REAL DEFAULT 0.0,
                fat REAL DEFAULT 0.0,
                carbs REAL DEFAULT 0.0,
                meals TEXT DEFAULT '[]',
                goal TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # יצירת אינדקסים לביצועים טובים יותר
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_date ON nutrition_logs(user_id, date)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_id ON nutrition_logs(user_id)"
        )

        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise


def save_daily_entry(user_id: int, calories: int, protein: float, fat: float,
                     carbs: float, meals_list: List[str], goal: str) -> bool:
    """שמירת יום חדש למסד הנתונים."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # המרת רשימת ארוחות ל-JSON
        meals_json = json.dumps(meals_list,
                                ensure_ascii=False) if meals_list else "[]"
        today = date.today().isoformat()

        # בדיקה אם כבר יש רשומה ליום זה
        cursor.execute(
            "SELECT id FROM nutrition_logs WHERE user_id = ? AND date = ?",
            (user_id, today)
        )
        existing = cursor.fetchone()

        if existing:
            # עדכון רשומה קיימת
            cursor.execute(
                """
                UPDATE nutrition_logs
                SET calories = ?, protein = ?, fat = ?, carbs = ?, meals = ?, goal = ?
                WHERE user_id = ? AND date = ?
                """,
                (calories, protein, fat, carbs, meals_json, goal, user_id, today)
            )
        else:
            # יצירת רשומה חדשה
            cursor.execute(
                """
                INSERT INTO nutrition_logs (user_id, date, calories, protein, fat, carbs, meals, goal)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (user_id, today, calories, protein, fat, carbs, meals_json, goal))

        conn.commit()
        conn.close()
        logger.info(f"Saved daily entry for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving daily entry: {e}")
        return False


def get_weekly_summary(user_id: int) -> List[Tuple[Any, ...]]:
    """מחזיר דוח שבועי של נתוני תזונה."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT date, calories, protein, fat, carbs FROM nutrition_logs
            WHERE user_id = ? ORDER BY date DESC LIMIT 7
            """,
            (user_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        logger.error(f"Error getting weekly summary: {e}")
        return []


def get_nutrition_by_date(
        user_id: int, target_date: str) -> Optional[Tuple[Any, ...]]:
    """מחזיר נתוני תזונה לתאריך ספציפי."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT date, calories, protein, fat, carbs, meals FROM nutrition_logs
            WHERE user_id = ? AND date = ?
            """,
            (user_id, target_date)
        )
        row = cursor.fetchone()
        conn.close()
        return row
    except Exception as e:
        logger.error(f"Error getting nutrition by date: {e}")
        return None


def get_last_occurrence_of_meal(
        user_id: int, meal_name: str) -> Optional[Tuple[Any, ...]]:
    """מחזיר את הפעם האחרונה שהמשתמש אכל מאכל מסוים."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT date, meals FROM nutrition_logs
            WHERE user_id = ? AND meals LIKE ?
            ORDER BY date DESC LIMIT 1
            """,
            (user_id, f"%{meal_name}%")
        )
        row = cursor.fetchone()
        conn.close()
        return row
    except Exception as e:
        logger.error(f"Error getting last meal occurrence: {e}")
        return None


def format_date_query_response(
        nutrition_data: Optional[Tuple[Any, ...]]) -> str:
    """מעצב תשובה לשאילתת תאריך."""
    if not nutrition_data:
        return "לא נמצאו נתונים לתאריך זה."

    try:
        date_str, calories, protein, fat, carbs, meals = nutrition_data

        # המרת meals מ-JSON
        try:
            meals_list = json.loads(meals) if meals else []
        except (json.JSONDecodeError, TypeError):
            meals_list = []

        response = f"📅 <b>נתונים ליום {date_str}:</b>\n\n"
        response += f"🔥 קלוריות: {calories or 0}\n"
        response += f"🥩 חלבון: {(protein or 0):.1f}g\n"
        response += f"🍯 שומן: {(fat or 0):.1f}g\n"
        response += f"🍞 פחמימות: {(carbs or 0):.1f}g\n\n"

        if meals_list:
            response += "<b>מה אכלת:</b>\n"
            for meal in meals_list:
                if isinstance(meal, dict):
                    meal_desc = meal.get('desc', '')
                    meal_calories = meal.get('calories', 0)
                    response += f"• {meal_desc} ({meal_calories} קלוריות)\n"
                else:
                    response += f"• {meal}\n"

        return response
    except Exception as e:
        logger.error(f"Error formatting date query response: {e}")
        return "שגיאה בעיבוד הנתונים."


def get_user_stats(user_id: int, days: int = 30) -> dict:
    """מחזיר סטטיסטיקות משתמש לתקופה מסוימת."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                AVG(calories) as avg_calories,
                AVG(protein) as avg_protein,
                AVG(fat) as avg_fat,
                AVG(carbs) as avg_carbs,
                COUNT(*) as days_count
            FROM nutrition_logs
            WHERE user_id = ? AND date >= date('now', '-{} days')
            """.format(days),
            (user_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if row and row[0] is not None:
            return {
                'avg_calories': round(row[0], 1),
                'avg_protein': round(row[1], 1),
                'avg_fat': round(row[2], 1),
                'avg_carbs': round(row[3], 1),
                'days_count': row[4]
            }
        else:
            return {
                'avg_calories': 0,
                'avg_protein': 0,
                'avg_fat': 0,
                'avg_carbs': 0,
                'days_count': 0
            }
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        return {
            'avg_calories': 0,
            'avg_protein': 0,
            'avg_fat': 0,
            'avg_carbs': 0,
            'days_count': 0
        }


def save_food_entry(user_id: int, meal_data: dict) -> bool:
    """שמירת רשומת מזון חדשה."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # יצירת טבלה נפרדת למזונות אם לא קיימת
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS food_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                meal_type TEXT DEFAULT 'snack',
                description TEXT NOT NULL,
                calories INTEGER DEFAULT 0,
                protein REAL DEFAULT 0.0,
                carbs REAL DEFAULT 0.0,
                fat REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            INSERT INTO food_entries (user_id, date, meal_type, description, calories, protein, carbs, fat)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                meal_data.get('date', date.today().isoformat()),
                meal_data.get('meal_type', 'snack'),
                meal_data.get('description', ''),
                meal_data.get('calories', 0),
                meal_data.get('protein', 0.0),
                meal_data.get('carbs', 0.0),
                meal_data.get('fat', 0.0)
            )
        )

        conn.commit()
        conn.close()
        logger.info(f"Saved food entry for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving food entry: {e}")
        return False


def get_user_allergies(user_id: int) -> List[str]:
    """מחזיר את האלרגיות של המשתמש."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # יצירת טבלת אלרגיות אם לא קיימת
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_allergies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                allergy TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, allergy)
            )
            """
        )

        cursor.execute(
            "SELECT allergy FROM user_allergies WHERE user_id = ?",
            (user_id,)
        )
        allergies = [row[0] for row in cursor.fetchall()]
        conn.close()
        return allergies
    except Exception as e:
        logger.error(f"Error getting user allergies: {e}")
        return []


def save_user_allergies(user_id: int, allergies: List[str]) -> bool:
    """שמירת אלרגיות משתמש."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # יצירת טבלת אלרגיות אם לא קיימת
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_allergies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                allergy TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, allergy)
            )
            """
        )

        # מחיקת אלרגיות קיימות
        cursor.execute(
            "DELETE FROM user_allergies WHERE user_id = ?", (user_id,))

        # הוספת אלרגיות חדשות
        for allergy in allergies:
            if allergy and allergy.strip():
                cursor.execute(
                    "INSERT OR IGNORE INTO user_allergies (user_id, allergy) VALUES (?, ?)",
                    (user_id, allergy.strip())
                )

        conn.commit()
        conn.close()
        logger.info(f"Saved allergies for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving user allergies: {e}")
        return False
