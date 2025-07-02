"""
Database module for the Calorico Telegram bot.

This module handles all database operations including user data storage,
daily entries, food tracking, and data persistence.
"""

import sqlite3
import json
import logging
import os
from datetime import datetime, date
from typing import Dict, List, Optional, Any, Tuple

from config import USERS_FILE, DB_NAME

logger = logging.getLogger(__name__)


def init_db() -> None:
    """יוצר את טבלת nutrition_logs אם אינה קיימת."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
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
            logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise


def save_daily_entry(user_id: int, calories: int, protein: float, fat: float,
                     carbs: float, meals_list: List[str], goal: str) -> bool:
    """שומר כניסה יומית לטבלת nutrition_logs."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
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
            logger.info(f"Saved daily entry for user {user_id}")
            return True
    except Exception as e:
        logger.error(f"Error saving daily entry: {e}")
        return False


def get_weekly_summary(user_id: int) -> List[Tuple[Any, ...]]:
    """מחזיר נתוני סיכום שבועיים למשתמש."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT date, calories, protein, fat, carbs, meals, goal
                FROM nutrition_logs
                WHERE user_id = ?
                ORDER BY date DESC
                LIMIT 7
                """,
                (user_id,)
            )
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error getting weekly summary: {e}")
        return []


def save_user(user_id: int, user_data: Dict[str, Any]) -> bool:
    """שומר נתוני משתמש לקובץ JSON."""
    try:
        if not os.path.exists(USERS_FILE):
            data = {}
        else:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

        data[str(user_id)] = user_data

        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved user data for user {user_id}")
        return True
    except (OSError, json.JSONDecodeError) as e:
        logger.error(f"Error saving user: {e}")
        return False


def load_user(user_id: int) -> Optional[Dict[str, Any]]:
    """טוען נתוני משתמש מקובץ JSON."""
    try:
        if not os.path.exists(USERS_FILE):
            return None

        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        user_data = data.get(str(user_id))
        if user_data:
            logger.info(f"Loaded user data for user {user_id}")
        return user_data
    except (OSError, json.JSONDecodeError) as e:
        logger.error(f"Error loading user: {e}")
        return None


class NutritionDB:
    """מחלקה לניהול מסד נתונים של משתמשים, יומן אכילה, תפריטים ואלרגיות."""

    def __init__(self, db_path: str = "nutrition.db"):
        """מאתחל את מחלקת מסד הנתונים."""
        self.db_path = db_path
        self.init_database()

    def init_database(self) -> None:
        """מאתחל את מסד הנתונים עם הטבלאות הנדרשות."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # טבלת משתמשים
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        name TEXT,
                        age INTEGER,
                        gender TEXT,
                        height REAL,
                        weight REAL,
                        goal TEXT,
                        activity TEXT,
                        diet TEXT,  -- JSON string
                        allergies TEXT,  -- JSON string
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

                # טבלת יומן אכילה
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS food_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        meal_date DATE,
                        meal_type TEXT,  -- breakfast, lunch, dinner, snack
                        description TEXT,
                        calories INTEGER,
                        protein REAL,
                        carbs REAL,
                        fat REAL,
                        logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                    """
                )

                # טבלת תפריטים יומיים
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS daily_menus (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        menu_date DATE,
                        menu_content TEXT,
                        calorie_budget INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                    """
                )

                # טבלת אלרגיות
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_allergies (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        allergen TEXT,
                        severity TEXT DEFAULT 'moderate',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                    """
                )

                conn.commit()
                logger.info("NutritionDB initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing NutritionDB: {e}")
            raise

    def save_user(self, user_id: int, user_data: Dict[str, Any]) -> bool:
        """שומר או מעדכן משתמש במסד הנתונים."""
        logger.info(f"save_user called with user_id: {user_id}, user_data keys: {list(user_data.keys()) if user_data else 'None'}")
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                logger.info(f"Connected to database: {self.db_path}")

                # המרת רשימות ל-JSON
                diet_json = json.dumps(user_data.get(
                    "diet", []), ensure_ascii=False)
                allergies_json = json.dumps(
                    user_data.get("allergies", []), ensure_ascii=False
                )
                logger.info(f"Converted diet: {diet_json}, allergies: {allergies_json}")

                # הכנת הנתונים ל-INSERT
                insert_data = (
                        user_id,
                        user_data.get("name"),
                        user_data.get("age"),
                        user_data.get("gender"),
                        user_data.get("height"),
                        user_data.get("weight"),
                        user_data.get("goal"),
                        user_data.get("activity"),
                        diet_json,
                        allergies_json,
                )
                logger.info(f"Insert data: {insert_data}")

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO users
                    (user_id, name, age, gender, height, weight, goal, activity, diet, allergies, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    insert_data,
                )
                logger.info(f"SQL executed successfully, rows affected: {cursor.rowcount}")
                
                conn.commit()
                logger.info(f"Commit successful for user {user_id}")
                return True
        except Exception as e:
            logger.error(f"Error saving user to database: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def load_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """טוען משתמש ממסד הנתונים."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM users WHERE user_id = ?", (user_id,)
                )
                row = cursor.fetchone()

                if row:
                    # המרת JSON חזרה לרשימות
                    user_data = {
                        "user_id": row[0],
                        "name": row[1],
                        "age": row[2],
                        "gender": row[3],
                        "height": row[4],
                        "weight": row[5],
                        "goal": row[6],
                        "activity": row[7],
                        "diet": json.loads(row[8]) if row[8] else [],
                        "allergies": json.loads(row[9]) if row[9] else [],
                        "created_at": row[10],
                        "updated_at": row[11],
                    }
                    logger.info(f"Loaded user {user_id} from database")
                    return user_data
                return None
        except Exception as e:
            logger.error(f"Error loading user from database: {e}")
            return None

    def save_food_log(self, user_id: int, meal_data: Dict[str, Any]) -> bool:
        """שומר רשומת מזון למסד הנתונים."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO food_log
                    (user_id, meal_date, meal_type, description, calories, protein, carbs, fat)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        meal_data.get("date", date.today().isoformat()),
                        meal_data.get("meal_type", "snack"),
                        meal_data.get("description", ""),
                        meal_data.get("calories", 0),
                        meal_data.get("protein", 0.0),
                        meal_data.get("carbs", 0.0),
                        meal_data.get("fat", 0.0),
                    ),
                )
                conn.commit()
                logger.info(f"Saved food log for user {user_id}")
                return True
        except Exception as e:
            logger.error(f"Error saving food log: {e}")
            return False

    def get_food_log(
        self, user_id: int, meal_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """מחזיר יומן מזון למשתמש."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                if meal_date:
                    cursor.execute(
                        """
                        SELECT * FROM food_log
                        WHERE user_id = ? AND meal_date = ?
                        ORDER BY logged_at DESC
                        """,
                        (user_id, meal_date)
                    )
                else:
                    cursor.execute(
                        """
                        SELECT * FROM food_log
                        WHERE user_id = ?
                        ORDER BY logged_at DESC
                        LIMIT 50
                        """,
                        (user_id,)
                    )

                rows = cursor.fetchall()
                food_logs = []

                for row in rows:
                    food_logs.append({
                        "id": row[0],
                        "user_id": row[1],
                        "meal_date": row[2],
                        "meal_type": row[3],
                        "description": row[4],
                        "calories": row[5],
                        "protein": row[6],
                        "carbs": row[7],
                        "fat": row[8],
                        "logged_at": row[9],
                    })

                return food_logs
        except Exception as e:
            logger.error(f"Error getting food log: {e}")
            return []

    def save_daily_menu(self, user_id: int, menu_data: Dict[str, Any]) -> bool:
        """שומר תפריט יומי למסד הנתונים."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO daily_menus
                    (user_id, menu_date, menu_content, calorie_budget)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        menu_data.get("date", date.today().isoformat()),
                        menu_data.get("content", ""),
                        menu_data.get("calorie_budget", 0),
                    ),
                )
                conn.commit()
                logger.info(f"Saved daily menu for user {user_id}")
                return True
        except Exception as e:
            logger.error(f"Error saving daily menu: {e}")
            return False

    def get_daily_menu(
        self, user_id: int, menu_date: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """מחזיר תפריט יומי למשתמש."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                if menu_date:
                    cursor.execute(
                        """
                        SELECT * FROM daily_menus
                        WHERE user_id = ? AND menu_date = ?
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        (user_id, menu_date)
                    )
                else:
                    cursor.execute(
                        """
                        SELECT * FROM daily_menus
                        WHERE user_id = ?
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        (user_id,)
                    )

                row = cursor.fetchone()

                if row:
                    return {
                        "id": row[0],
                        "user_id": row[1],
                        "menu_date": row[2],
                        "menu_content": row[3],
                        "calorie_budget": row[4],
                        "created_at": row[5],
                    }
                return None
        except Exception as e:
            logger.error(f"Error getting daily menu: {e}")
            return None

    def save_user_allergies(self, user_id: int, allergies: List[str]) -> bool:
        """שומר אלרגיות משתמש למסד הנתונים."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # מחיקת אלרגיות קיימות
                cursor.execute(
                    "DELETE FROM user_allergies WHERE user_id = ?", (user_id,))

                # הוספת אלרגיות חדשות
                for allergy in allergies:
                    if allergy and allergy.strip():
                        cursor.execute(
                            """
                            INSERT INTO user_allergies (user_id, allergen)
                            VALUES (?, ?)
                            """,
                            (user_id, allergy.strip())
                        )

                conn.commit()
                logger.info(f"Saved allergies for user {user_id}")
                return True
        except Exception as e:
            logger.error(f"Error saving user allergies: {e}")
            return False

    def get_user_allergies(self, user_id: int) -> List[str]:
        """מחזיר אלרגיות משתמש ממסד הנתונים."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT allergen FROM user_allergies WHERE user_id = ?",
                    (user_id,)
                )
                allergies = [row[0] for row in cursor.fetchall()]
                return allergies
        except Exception as e:
            logger.error(f"Error getting user allergies: {e}")
            return []

    def get_daily_summary(
        self, user_id: int, summary_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """מחזיר סיכום יומי למשתמש."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                target_date = summary_date or date.today().isoformat()

                cursor.execute(
                    """
                    SELECT
                        SUM(calories) as total_calories,
                        SUM(protein) as total_protein,
                        SUM(carbs) as total_carbs,
                        SUM(fat) as total_fat,
                        COUNT(*) as meal_count
                    FROM food_log
                    WHERE user_id = ? AND meal_date = ?
                    """,
                    (user_id, target_date)
                )

                row = cursor.fetchone()

                if row and row[0] is not None:
                    return {
                        "date": target_date,
                        "total_calories": row[0],
                        "total_protein": row[1],
                        "total_carbs": row[2],
                        "total_fat": row[3],
                        "meal_count": row[4],
                    }
                else:
                    return {
                        "date": target_date,
                        "total_calories": 0,
                        "total_protein": 0.0,
                        "total_carbs": 0.0,
                        "total_fat": 0.0,
                        "meal_count": 0,
                    }
        except Exception as e:
            logger.error(f"Error getting daily summary: {e}")
            return {
                "date": summary_date or date.today().isoformat(),
                "total_calories": 0,
                "total_protein": 0.0,
                "total_carbs": 0.0,
                "total_fat": 0.0,
                "meal_count": 0,
            }

    def get_all_users(self) -> Dict[int, Dict[str, Any]]:
        """מחזיר את כל המשתמשים מהמסד עם הנתונים שלהם."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT user_id, name, age, gender, height, weight, goal, 
                           activity, diet, allergies, created_at, updated_at
                    FROM users
                    """
                )
                rows = cursor.fetchall()
                
                users = {}
                for row in rows:
                    user_id = row[0]
                    users[user_id] = {
                        "name": row[1],
                        "age": row[2],
                        "gender": row[3],
                        "height": row[4],
                        "weight": row[5],
                        "goal": row[6],
                        "activity": row[7],
                        "diet": json.loads(row[8]) if row[8] else [],
                        "allergies": json.loads(row[9]) if row[9] else [],
                        "created_at": row[10],
                        "updated_at": row[11]
                    }
                
                return users
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return {}


# Wrapper functions for backward compatibility
def save_user_data(user_id: int, user_data: Dict[str, Any]) -> bool:
    """Wrapper function for saving user data."""
    db = NutritionDB()
    return db.save_user(user_id, user_data)


def load_user_data(user_id: int) -> Optional[Dict[str, Any]]:
    """Wrapper function for loading user data."""
    db = NutritionDB()
    return db.load_user(user_id)


def save_food_entry(user_id: int, meal_data: Dict[str, Any]) -> bool:
    """Wrapper function for saving food entry."""
    db = NutritionDB()
    return db.save_food_log(user_id, meal_data)


def get_daily_food_log(
    user_id: int, meal_date: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Wrapper function for getting daily food log."""
    db = NutritionDB()
    return db.get_food_log(user_id, meal_date)


def save_daily_menu_data(user_id: int, menu_data: Dict[str, Any]) -> bool:
    """Wrapper function for saving daily menu."""
    db = NutritionDB()
    return db.save_daily_menu(user_id, menu_data)


def get_daily_menu_data(
    user_id: int, menu_date: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Wrapper function for getting daily menu."""
    db = NutritionDB()
    return db.get_daily_menu(user_id, menu_date)


def save_user_allergies_data(user_id: int, allergies: List[str]) -> bool:
    """Wrapper function for saving user allergies."""
    db = NutritionDB()
    return db.save_user_allergies(user_id, allergies)


def get_user_allergies_data(user_id: int) -> List[str]:
    """Wrapper function for getting user allergies."""
    db = NutritionDB()
    return db.get_user_allergies(user_id)


def get_daily_summary_data(
    user_id: int, summary_date: Optional[str] = None
) -> Dict[str, Any]:
    """Wrapper function for getting daily summary."""
    db = NutritionDB()
    return db.get_daily_summary(user_id, summary_date)
