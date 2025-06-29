
import sqlite3
import json
from datetime import date

# יצירת בסיס הנתונים (פעם אחת בלבד)
def init_db():
    conn = sqlite3.connect("nutrition_data.db")
    cursor = conn.cursor()
    cursor.execute("""
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
    """)
    conn.commit()
    conn.close()

# שמירת יום חדש
def save_daily_entry(user_id, calories, protein, fat, carbs, meals_list, goal):
    conn = sqlite3.connect("nutrition_data.db")
    cursor = conn.cursor()
    meals_json = json.dumps(meals_list, ensure_ascii=False)
    today = date.today().isoformat()
    cursor.execute("""
        INSERT INTO nutrition_logs (user_id, date, calories, protein, fat, carbs, meals, goal)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, today, calories, protein, fat, carbs, meals_json, goal))
    conn.commit()
    conn.close()

# דוח שבועי
def get_weekly_summary(user_id):
    conn = sqlite3.connect("nutrition_data.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date, calories, protein, fat, carbs FROM nutrition_logs
        WHERE user_id = ? ORDER BY date DESC LIMIT 7
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows
