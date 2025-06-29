import sqlite3
import json
from config import USERS_FILE
import os


def init_db():
    """יוצר את טבלת nutrition_logs אם אינה קיימת."""
    with sqlite3.connect("nutrition_data.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS nutrition_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                date TEXT,
                calories INTEGER,
                protein REAL,
                fat REAL,
                carbs REAL,
                meals TEXT,
                goal TEXT
            )
            """
        )
        conn.commit()


def save_daily_entry(user_id, calories, protein, fat, carbs, meals_list, goal):
    """שומר כניסה יומית לטבלת nutrition_logs."""
    with sqlite3.connect("nutrition_data.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO nutrition_logs (user_id, date, calories, protein, fat, carbs, meals, goal)
            VALUES (?, date('now', 'localtime'), ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                calories,
                protein,
                fat,
                carbs,
                json.dumps(meals_list, ensure_ascii=False),
                goal,
            ),
        )
        conn.commit()


def get_weekly_summary(user_id):
    """מחזיר נתוני סיכום שבועיים למשתמש."""
    with sqlite3.connect("nutrition_data.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT date, calories, protein, fat, carbs, meals, goal
            FROM nutrition_logs
            WHERE user_id = ?
            ORDER BY date DESC
            LIMIT 7
            """,
            (user_id,),
        )
        return cursor.fetchall()


def save_user(user_id, user_data):
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
    except Exception as e:
        # TODO: טיפול בשגיאות כתיבה
        print(f"שגיאה בשמירת משתמש: {e}")


def load_user(user_id):
    """טוען נתוני משתמש מקובץ JSON."""
    try:
        if not os.path.exists(USERS_FILE):
            return None
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get(str(user_id))
    except Exception as e:
        # TODO: טיפול בשגיאות קריאה
        print(f"שגיאה בטעינת משתמש: {e}")
        return None
