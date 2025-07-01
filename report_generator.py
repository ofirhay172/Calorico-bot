"""
Report generator module for the Calorico Telegram bot.

This module handles generation of nutritional reports, charts, and summaries
for user data analysis.
"""

import sqlite3
import json
import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
import os

# Import from db instead of nutrition_db (since nutrition_db was deleted)
from db import get_weekly_summary

logger = logging.getLogger(__name__)

DB_NAME = "nutrition_data.db"

# הגדרת תמיכה בעברית (רק אם matplotlib זמין)
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import numpy as np
    plt.rcParams["font.family"] = ["Arial", "DejaVu Sans", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("matplotlib not available - charts will be disabled")


def get_weekly_report(user_id: int) -> List[Dict[str, Any]]:
    """מחזיר נתוני דוח שבועי למשתמש (רשימת dict)."""
    try:
        rows = get_weekly_summary(user_id)
        data = []
        for row in rows:
            if len(row) >= 7:
                date, calories, protein, fat, carbs, meals, goal = row
            else:
                # אם חסרים שדות, נמלא ברירות מחדל
                date = row[0] if len(row) > 0 else ""
                calories = row[1] if len(row) > 1 else 0
                protein = row[2] if len(row) > 2 else 0.0
                fat = row[3] if len(row) > 3 else 0.0
                carbs = row[4] if len(row) > 4 else 0.0
                meals = row[5] if len(row) > 5 else "[]"
                goal = row[6] if len(row) > 6 else ""

            try:
                meals_list = json.loads(meals) if meals else []
            except (json.JSONDecodeError, TypeError):
                meals_list = []

            data.append({
                "date": date,
                "calories": calories or 0,
                "protein": protein or 0.0,
                "fat": fat or 0.0,
                "carbs": carbs or 0.0,
                "meals": meals_list,
                "goal": goal or "",
            })
        return data
    except Exception as e:
        logger.error(f"Error getting weekly report: {e}")
        return []


def build_weekly_summary_text(data: List[Dict[str, Any]]) -> str:
    """בונה טקסט מסכם שבועי לדוח."""
    if not data:
        return "אין נתונים לשבוע האחרון."

    try:
        lines = []
        for day in data:
            calories = day.get('calories', 0)
            protein = day.get('protein', 0.0)
            fat = day.get('fat', 0.0)
            carbs = day.get('carbs', 0.0)
            date = day.get('date', '')

            lines.append(
                f"{date}: {calories} קלוריות, חלבון: {protein:.1f}g, שומן: {fat:.1f}g, פחמימות: {carbs:.1f}g"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error building weekly summary text: {e}")
        return "שגיאה בעיבוד הנתונים."


def plot_calories(data: List[Dict[str, Any]]) -> Optional[str]:
    """יוצר גרף קלוריות שבועי ושומר לקובץ זמני. מחזיר את הנתיב."""
    if not MATPLOTLIB_AVAILABLE:
        logger.warning("matplotlib not available - cannot create chart")
        return None

    if not data:
        return None

    try:
        dates = [d.get("date", "") for d in data]
        calories = [d.get("calories", 0) for d in data]

        # המרת תאריכים לפורמט matplotlib
        date_objects = []
        for date_str in dates:
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                date_objects.append(date_obj)
            except ValueError:
                # אם התאריך לא תקין, נשתמש באינדקס
                date_objects.append(datetime.now())

        plt.figure(figsize=(10, 6))
        plt.plot(date_objects, calories, marker="o", linewidth=2, markersize=6)
        plt.title("צריכת קלוריות שבועית", fontsize=14, fontweight='bold')
        plt.xlabel("תאריך", fontsize=12)
        plt.ylabel("קלוריות", fontsize=12)
        plt.grid(True, alpha=0.3)

        # עיצוב ציר התאריכים
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
        plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=1))
        plt.xticks(rotation=45)

        plt.tight_layout()

        # שמירה לקובץ
        path = "weekly_calories.png"
        plt.savefig(path, dpi=300, bbox_inches='tight')
        plt.close()

        return path
    except Exception as e:
        logger.error(f"Error creating calories plot: {e}")
        return None


def get_monthly_report(user_id: int) -> List[Dict[str, Any]]:
    """מחזירה את כל הרשומות מ־30 הימים האחרונים."""
    try:
        conn = sqlite3.connect(DB_NAME)
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
            if len(row) >= 7:
                date_str, calories, protein, fat, carbs, meals_json, goal = row
            else:
                # אם חסרים שדות, נמלא ברירות מחדל
                date_str = row[0] if len(row) > 0 else ""
                calories = row[1] if len(row) > 1 else 0
                protein = row[2] if len(row) > 2 else 0.0
                fat = row[3] if len(row) > 3 else 0.0
                carbs = row[4] if len(row) > 4 else 0.0
                meals_json = row[5] if len(row) > 5 else "[]"
                goal = row[6] if len(row) > 6 else ""

            try:
                meals = json.loads(meals_json) if meals_json else []
            except (json.JSONDecodeError, TypeError):
                meals = []

            data.append({
                "date": date_str,
                "calories": calories or 0,
                "protein": protein or 0.0,
                "fat": fat or 0.0,
                "carbs": carbs or 0.0,
                "meals": meals,
                "goal": goal or "",
            })

        return data
    except Exception as e:
        logger.error(f"Error getting monthly report: {e}")
        return []


def build_monthly_summary_text(data: List[Dict[str, Any]]) -> str:
    """מחזירה טקסט סיכום חודשי."""
    if not data:
        return "אין נתונים לחודש האחרון."

    try:
        # חישוב ממוצעים
        total_calories = sum(day.get("calories", 0) for day in data)
        total_protein = sum(day.get("protein", 0.0) for day in data)
        total_fat = sum(day.get("fat", 0.0) for day in data)
        total_carbs = sum(day.get("carbs", 0.0) for day in data)

        days_count = len(data)
        if days_count == 0:
            return "אין נתונים לחודש האחרון."

        avg_calories = total_calories / days_count
        avg_protein = total_protein / days_count
        avg_fat = total_fat / days_count
        avg_carbs = total_carbs / days_count

        text = f"<b>📊 דוח חודשי - {days_count} ימים</b>\n\n"
        text += f"🔥 ממוצע קלוריות יומי: {avg_calories:.0f}\n"
        text += f"🥩 ממוצע חלבון יומי: {avg_protein:.1f}ג\n"
        text += f"🧈 ממוצע שומן יומי: {avg_fat:.1f}ג\n"
        text += f"🍞 ממוצע פחמימות יומי: {avg_carbs:.1f}ג\n"

        return text
    except Exception as e:
        logger.error(f"Error building monthly summary text: {e}")
        return "שגיאה בעיבוד הנתונים."


def get_nutrition_by_date(user_id: int, target_date: str) -> dict | None:
    """מחזירה נתוני תזונה לתאריך ספציפי מה-DB הכללי."""
    try:
        conn = sqlite3.connect(DB_NAME)
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
        if len(row) >= 7:
            date_str, calories, protein, fat, carbs, meals_json, goal = row
        else:
            date_str = row[0] if len(row) > 0 else target_date
            calories = row[1] if len(row) > 1 else 0
            protein = row[2] if len(row) > 2 else 0.0
            fat = row[3] if len(row) > 3 else 0.0
            carbs = row[4] if len(row) > 4 else 0.0
            meals_json = row[5] if len(row) > 5 else "[]"
            goal = row[6] if len(row) > 6 else ""
        try:
            meals = json.loads(meals_json) if meals_json else []
        except (Exception,):
            meals = []
        return {
            "date": date_str,
            "calories": calories or 0,
            "protein": protein or 0.0,
            "fat": fat or 0.0,
            "carbs": carbs or 0.0,
            "meals": meals,
            "goal": goal or "",
        }
    except Exception as e:
        logger.error(f"Error getting nutrition by date: {e}")
        return None


def get_nutrition_by_date_range(
        user_id: int, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """מחזירה נתוני תזונה לטווח תאריכים."""
    try:
        conn = sqlite3.connect(DB_NAME)
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
            if len(row) >= 7:
                date_str, calories, protein, fat, carbs, meals_json, goal = row
            else:
                # אם חסרים שדות, נמלא ברירות מחדל
                date_str = row[0] if len(row) > 0 else ""
                calories = row[1] if len(row) > 1 else 0
                protein = row[2] if len(row) > 2 else 0.0
                fat = row[3] if len(row) > 3 else 0.0
                carbs = row[4] if len(row) > 4 else 0.0
                meals_json = row[5] if len(row) > 5 else "[]"
                goal = row[6] if len(row) > 6 else ""

            try:
                meals = json.loads(meals_json) if meals_json else []
            except (json.JSONDecodeError, TypeError):
                meals = []

            data.append({
                "date": date_str,
                "calories": calories or 0,
                "protein": protein or 0.0,
                "fat": fat or 0.0,
                "carbs": carbs or 0.0,
                "meals": meals,
                "goal": goal or "",
            })

        return data
    except Exception as e:
        logger.error(f"Error getting nutrition by date range: {e}")
        return []


def search_meals_by_keyword(
        user_id: int, keyword: str, days_back: int = 30) -> List[Dict[str, Any]]:
    """מחפש ארוחות שמכילות מילת מפתח בטווח ימים."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # חישוב תאריך לפני X ימים
        start_date = (
            datetime.now() -
            timedelta(
                days=days_back)).strftime("%Y-%m-%d")

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
            if len(row) >= 2:
                date_str, meals_json = row
            else:
                continue

            try:
                meals = json.loads(meals_json) if meals_json else []
                # סינון רק ארוחות שמכילות את המילת מפתח
                matching_meals = []
                for meal in meals:
                    if isinstance(meal, dict):
                        meal_text = meal.get('desc', '')
                    else:
                        meal_text = str(meal)

                    if keyword.lower() in meal_text.lower():
                        matching_meals.append(meal)

                if matching_meals:
                    results.append({"date": date_str, "meals": matching_meals})
            except (json.JSONDecodeError, TypeError):
                continue

        return results
    except Exception as e:
        logger.error(f"Error searching meals by keyword: {e}")
        return []


def get_last_occurrence_of_meal(
        user_id: int, meal_keyword: str) -> Optional[Dict[str, Any]]:
    """מחזירה את הפעם האחרונה שאכלו מאכל מסוים."""
    try:
        results = search_meals_by_keyword(user_id, meal_keyword, days_back=365)
        if results:
            return results[0]  # הראשון (הכי חדש) ברשימה
        return None
    except Exception as e:
        logger.error(f"Error getting last occurrence of meal: {e}")
        return None


def format_date_query_response(
        data: Optional[Dict[str, Any]], query_type: str = "calories") -> str:
    """מעצב תשובה לשאילתת תאריך."""
    if not data:
        return "לא נמצאו נתונים לתאריך זה."

    try:
        if query_type == "calories":
            calories = data.get('calories', 0)
            return f"🔥 ב{data.get('date', '')} צרכת {calories} קלוריות"
        elif query_type == "meals":
            meals = data.get('meals', [])
            meals_text = ", ".join(str(meal) for meal in meals)
            return f"🍽️ ב{data.get('date', '')} אכלת: {meals_text}"
        elif query_type == "summary":
            meals = data.get('meals', [])
            meals_text = ", ".join(str(meal)
                                   for meal in meals[:3]) if meals else "לא דווח"
            if len(meals) > 3:
                meals_text += f" (+{len(meals) - 3} נוספות)"

            calories = data.get('calories', 0)
            protein = data.get('protein', 0.0)
            fat = data.get('fat', 0.0)
            carbs = data.get('carbs', 0.0)

            return (f"📊 ב{data.get('date', '')}:\n"
                    f"🔥 קלוריות: {calories}\n"
                    f"🥩 חלבון: {protein:.1f}ג\n"
                    f"🧈 שומן: {fat:.1f}ג\n"
                    f"🍞 פחמימות: {carbs:.1f}ג\n"
                    f"🍽️ ארוחות: {meals_text}")
        else:
            return "סוג שאילתה לא מוכר."
    except Exception as e:
        logger.error(f"Error formatting date query response: {e}")
        return "שגיאה בעיבוד הנתונים."


def parse_date_from_text(text: str) -> Optional[str]:
    """מנסה לחלץ תאריך מטקסט בעברית."""
    if not text:
        return None

    try:
        text_lower = text.lower()
        today = datetime.now()

        # אתמול
        if "אתמול" in text_lower:
            return (today - timedelta(days=1)).strftime("%Y-%m-%d")

        # שלשום
        if "שלשום" in text_lower:
            return (today - timedelta(days=2)).strftime("%Y-%m-%d")

        # היום
        if "היום" in text_lower:
            return today.strftime("%Y-%m-%d")

        # לפני X ימים
        days_match = re.search(r"לפני (\d+) ימים?", text_lower)
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
            if day_name in text_lower:
                # חישוב היום האחרון של היום הזה בשבוע
                days_since = (today.weekday() - day_num) % 7
                if days_since == 0:  # אם זה היום
                    days_since = 7
                return (
                    today -
                    timedelta(
                        days=days_since)).strftime("%Y-%m-%d")

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
    except Exception as e:
        logger.error(f"Error parsing date from text: {e}")
        return None


# פונקציות עזר לעתיד
def add_water_data(user_id: int, date: str, water_ml: int) -> bool:
    """פונקציה לעתיד - הוספת נתוני שתיית מים."""
    # TODO: להוסיף טבלה נפרדת לנתוני מים
    logger.info(f"Water data for user {user_id} on {date}: {water_ml}ml")
    return True


def add_exercise_data(user_id: int, date: str, exercise_type: str,
                      duration_minutes: int, calories_burned: int) -> bool:
    """פונקציה לעתיד - הוספת נתוני אימונים."""
    # TODO: להוסיף טבלה נפרדת לנתוני אימונים
    logger.info(
        f"Exercise data for user {user_id} on {date}: {exercise_type}, {duration_minutes}min, {calories_burned}cal")
    return True
