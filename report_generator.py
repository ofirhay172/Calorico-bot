"""
דוח שבועי לבוט תזונה
מייצר דוחות שבועיים, טקסט סיכום וגרפים
"""

import sqlite3
import json
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from datetime import datetime, timedelta
import os
from db import get_weekly_summary

# הגדרת תמיכה בעברית
plt.rcParams["font.family"] = ["Arial", "DejaVu Sans", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False


def get_weekly_report(user_id):
    """מחזיר נתוני דוח שבועי למשתמש (רשימת dict)."""
    rows = get_weekly_summary(user_id)
    data = []
    for row in rows:
        date, calories, protein, fat, carbs, meals, goal = row
        data.append(
            {
                "date": date,
                "calories": calories,
                "protein": protein,
                "fat": fat,
                "carbs": carbs,
                "meals": json.loads(meals),
                "goal": goal,
            }
        )
    return data


def build_weekly_summary_text(data):
    """בונה טקסט מסכם שבועי לדוח."""
    if not data:
        return "אין נתונים לשבוע האחרון."
    lines = []
    for day in data:
        lines.append(
            f"{day['date']}: {day['calories']} קלוריות, חלבון: {day['protein']}, שומן: {day['fat']}, פחמימות: {day['carbs']}"
        )
    return "\n".join(lines)


def plot_calories(data):
    """יוצר גרף קלוריות שבועי ושומר לקובץ זמני. מחזיר את הנתיב."""
    if not data:
        return None
    dates = [d["date"] for d in data]
    calories = [d["calories"] for d in data]
    plt.figure(figsize=(8, 4))
    plt.plot(dates, calories, marker="o")
    plt.title("צריכת קלוריות שבועית")
    plt.xlabel("תאריך")
    plt.ylabel("קלוריות")
    plt.tight_layout()
    path = "weekly_calories.png"
    plt.savefig(path)
    plt.close()
    return path


def get_monthly_report(user_id):
    """
    מחזירה את כל הרשומות מ־30 הימים האחרונים
    (לעתיד - כשתוסיף נתונים על מים ואימונים)
    """
    conn = sqlite3.connect("nutrition_data.db")
    cursor = conn.cursor()

    month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    cursor.execute(
        """
        SELECT date, calories, protein, fat, carbs, meals, goal
        FROM nutrition_logs
        WHERE user_id = ? AND date >= ?
        ORDER BY date ASC
    """,
        (user_id, month_ago),
    )

    rows = cursor.fetchall()
    conn.close()

    data = []
    for row in rows:
        date_str, calories, protein, fat, carbs, meals_json, goal = row
        try:
            meals = json.loads(meals_json) if meals_json else []
        except json.JSONDecodeError:
            meals = []

        data.append(
            {
                "date": date_str,
                "calories": calories,
                "protein": protein,
                "fat": fat,
                "carbs": carbs,
                "meals": meals,
                "goal": goal,
            }
        )

    return data


def build_monthly_summary_text(data):
    """
    מחזירה טקסט סיכום חודשי
    (לעתיד - כשתוסיף נתונים על מים ואימונים)
    """
    if not data:
        return "אין נתונים לחודש האחרון."

    # חישוב ממוצעים
    total_calories = sum(day["calories"] for day in data)
    total_protein = sum(day["protein"] for day in data)
    total_fat = sum(day["fat"] for day in data)
    total_carbs = sum(day["carbs"] for day in data)

    avg_calories = total_calories / len(data)
    avg_protein = total_protein / len(data)
    avg_fat = total_fat / len(data)
    avg_carbs = total_carbs / len(data)

    text = f"<b>📊 דוח חודשי - {len(data)} ימים</b>\n\n"
    text += f"🔥 ממוצע קלוריות יומי: {avg_calories:.0f}\n"
    text += f"🥩 ממוצע חלבון יומי: {avg_protein:.1f}ג\n"
    text += f"🧈 ממוצע שומן יומי: {avg_fat:.1f}ג\n"
    text += f"🍞 ממוצע פחמימות יומי: {avg_carbs:.1f}ג\n"

    return text


# פונקציות עזר לעתיד
def add_water_data(user_id, date, water_ml):
    """
    פונקציה לעתיד - הוספת נתוני שתיית מים
    """
    # TODO: להוסיף טבלה נפרדת לנתוני מים
    pass


def add_exercise_data(user_id, date, exercise_type, duration_minutes, calories_burned):
    """
    פונקציה לעתיד - הוספת נתוני אימונים
    """
    # TODO: להוסיף טבלה נפרדת לנתוני אימונים
    pass


def get_nutrition_by_date(user_id, target_date):
    """
    מחזירה נתוני תזונה לתאריך ספציפי
    """
    conn = sqlite3.connect("nutrition_data.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT date, calories, protein, fat, carbs, meals, goal
        FROM nutrition_logs
        WHERE user_id = ? AND date = ?
    """,
        (user_id, target_date),
    )

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    date_str, calories, protein, fat, carbs, meals_json, goal = row
    try:
        meals = json.loads(meals_json) if meals_json else []
    except json.JSONDecodeError:
        meals = []

    return {
        "date": date_str,
        "calories": calories,
        "protein": protein,
        "fat": fat,
        "carbs": carbs,
        "meals": meals,
        "goal": goal,
    }


def get_nutrition_by_date_range(user_id, start_date, end_date):
    """
    מחזירה נתוני תזונה לטווח תאריכים
    """
    conn = sqlite3.connect("nutrition_data.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT date, calories, protein, fat, carbs, meals, goal
        FROM nutrition_logs
        WHERE user_id = ? AND date BETWEEN ? AND ?
        ORDER BY date ASC
    """,
        (user_id, start_date, end_date),
    )

    rows = cursor.fetchall()
    conn.close()

    data = []
    for row in rows:
        date_str, calories, protein, fat, carbs, meals_json, goal = row
        try:
            meals = json.loads(meals_json) if meals_json else []
        except json.JSONDecodeError:
            meals = []

        data.append(
            {
                "date": date_str,
                "calories": calories,
                "protein": protein,
                "fat": fat,
                "carbs": carbs,
                "meals": meals,
                "goal": goal,
            }
        )

    return data


def search_meals_by_keyword(user_id, keyword, days_back=30):
    """
    מחפש ארוחות שמכילות מילת מפתח בטווח ימים
    """
    conn = sqlite3.connect("nutrition_data.db")
    cursor = conn.cursor()

    # חישוב תאריך לפני X ימים
    start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    cursor.execute(
        """
        SELECT date, meals
        FROM nutrition_logs
        WHERE user_id = ? AND date >= ? AND meals LIKE ?
        ORDER BY date DESC
    """,
        (user_id, start_date, f"%{keyword}%"),
    )

    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        date_str, meals_json = row
        try:
            meals = json.loads(meals_json) if meals_json else []
            # סינון רק ארוחות שמכילות את המילת מפתח
            matching_meals = [meal for meal in meals if keyword.lower() in meal.lower()]
            if matching_meals:
                results.append({"date": date_str, "meals": matching_meals})
        except json.JSONDecodeError:
            continue

    return results


def get_last_occurrence_of_meal(user_id, meal_keyword):
    """
    מחזירה את הפעם האחרונה שאכלו מאכל מסוים
    """
    results = search_meals_by_keyword(user_id, meal_keyword, days_back=365)
    if results:
        return results[0]  # הראשון (הכי חדש) ברשימה
    return None


def format_date_query_response(data, query_type="calories"):
    """
    מעצב תשובה לשאילתת תאריך
    """
    if not data:
        return "לא נמצאו נתונים לתאריך זה."

    if query_type == "calories":
        return f"🔥 ב{data['date']} צרכת {data['calories']} קלוריות"
    elif query_type == "meals":
        meals_text = ", ".join(data["meals"])
        return f"🍽️ ב{data['date']} אכלת: {meals_text}"
    elif query_type == "summary":
        meals_text = ", ".join(data["meals"][:3]) if data["meals"] else "לא דווח"
        if len(data["meals"]) > 3:
            meals_text += f" (+{len(data['meals']) - 3} נוספות)"
        return f"📊 ב{data['date']}:\n🔥 קלוריות: {data['calories']}\n🥩 חלבון: {data['protein']:.1f}ג\n🧈 שומן: {data['fat']:.1f}ג\n🍞 פחמימות: {data['carbs']:.1f}ג\n🍽️ ארוחות: {meals_text}"


def parse_date_from_text(text):
    """
    מנסה לחלץ תאריך מטקסט בעברית
    """
    from datetime import datetime, timedelta

    text = text.lower()
    today = datetime.now()

    # אתמול
    if "אתמול" in text:
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")

    # שלשום
    if "שלשום" in text:
        return (today - timedelta(days=2)).strftime("%Y-%m-%d")

    # לפני X ימים
    import re

    days_match = re.search(r"לפני (\d+) ימים?", text)
    if days_match:
        days = int(days_match.group(1))
        return (today - timedelta(days=days)).strftime("%Y-%m-%d")

    # יום בשבוע
    weekdays = {
        "ראשון": 6,
        "שני": 0,
        "שלישי": 1,
        "רביעי": 2,
        "חמישי": 3,
        "שישי": 4,
        "שבת": 5,
    }

    for day_name, day_num in weekdays.items():
        if day_name in text:
            # חישוב היום האחרון של היום הזה בשבוע
            days_since = (today.weekday() - day_num) % 7
            if days_since == 0:  # אם זה היום
                days_since = 7
            return (today - timedelta(days=days_since)).strftime("%Y-%m-%d")

    # תאריך בפורמט dd/mm/yyyy או yyyy-mm-dd
    date_patterns = [
        r"(\d{1,2})/(\d{1,2})/(\d{4})",  # dd/mm/yyyy
        r"(\d{4})-(\d{1,2})-(\d{1,2})",  # yyyy-mm-dd
    ]

    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            if "/" in pattern:
                day, month, year = match.groups()
            else:
                year, month, day = match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"

    return None
