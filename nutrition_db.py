import sqlite3
import json
import re
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


def get_nutrition_by_date(user_id, target_date):
    """מחזיר נתוני תזונה לתאריך ספציפי."""
    conn = sqlite3.connect("nutrition_data.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date, calories, protein, fat, carbs, meals FROM nutrition_logs
        WHERE user_id = ? AND date = ?
    """, (user_id, target_date))
    row = cursor.fetchone()
    conn.close()
    return row


def get_last_occurrence_of_meal(user_id, meal_name):
    """מחזיר את הפעם האחרונה שהמשתמש אכל מאכל מסוים."""
    conn = sqlite3.connect("nutrition_data.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date, meals FROM nutrition_logs
        WHERE user_id = ? AND meals LIKE ?
        ORDER BY date DESC LIMIT 1
    """, (user_id, f"%{meal_name}%"))
    row = cursor.fetchone()
    conn.close()
    return row


def format_date_query_response(nutrition_data):
    """מעצב תשובה לשאילתת תאריך."""
    if not nutrition_data:
        return "לא נמצאו נתונים לתאריך זה."
    
    date_str, calories, protein, fat, carbs, meals = nutrition_data
    
    # המרת meals מ-JSON
    try:
        meals_list = json.loads(meals) if meals else []
    except:
        meals_list = []
    
    response = f"📅 <b>נתונים ליום {date_str}:</b>\n\n"
    response += f"🔥 קלוריות: {calories}\n"
    response += f"🥩 חלבון: {protein:.1f}g\n"
    response += f"🍯 שומן: {fat:.1f}g\n"
    response += f"🍞 פחמימות: {carbs:.1f}g\n\n"
    
    if meals_list:
        response += "<b>מה אכלת:</b>\n"
        for meal in meals_list:
            if isinstance(meal, dict):
                response += f"• {meal.get('desc', '')} ({meal.get('calories', 0)} קלוריות)\n"
            else:
                response += f"• {meal}\n"
    
    return response
