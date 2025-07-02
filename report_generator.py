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
    """בונה טקסט מסכם שבועי לדוח, כולל אימוג'י ליד כל פריט מזון אם יש פירוט."""
    if not data:
        return "אין נתונים לשבוע האחרון."

    try:
        from utils import get_food_emoji
        lines = []
        for day in data:
            calories = day.get('calories', 0)
            protein = day.get('protein', 0.0)
            fat = day.get('fat', 0.0)
            carbs = day.get('carbs', 0.0)
            date = day.get('date', '')
            meals = day.get('meals', [])
            meal_lines = []
            for meal in meals:
                meal_name = meal.get('name', meal) if isinstance(meal, dict) else str(meal)
                emoji = get_food_emoji(meal_name)
                meal_lines.append(f"{emoji} {meal_name}")
            meal_text = " | ".join(meal_lines) if meal_lines else ""
            lines.append(
                f"{date}: {calories} קלוריות, חלבון: {protein:.1f}g, שומן: {fat:.1f}g, פחמימות: {carbs:.1f}g" + (f"\n    🍽️ {meal_text}" if meal_text else "")
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
    """מחזירה טקסט סיכום חודשי, כולל אימוג'י ליד כל פריט מזון אם יש פירוט."""
    if not data:
        return "אין נתונים לחודש האחרון."

    try:
        from utils import get_food_emoji
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

        # הצג דוגמה של מאכלים עיקריים מהחודש
        meals_counter = {}
        for day in data:
            meals = day.get('meals', [])
            for meal in meals:
                meal_name = meal.get('name', meal) if isinstance(meal, dict) else str(meal)
                meals_counter[meal_name] = meals_counter.get(meal_name, 0) + 1
        if meals_counter:
            text += "\n<b>🍽️ מאכלים עיקריים החודש:</b>\n"
            # הצג עד 7 מאכלים נפוצים
            for meal_name, count in sorted(meals_counter.items(), key=lambda x: -x[1])[:7]:
                emoji = get_food_emoji(meal_name)
                text += f"{emoji} {meal_name} ({count} ימים)\n"
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


def generate_long_term_feedback(user_id: int, days: int = 7) -> str:
    """מייצר פידבק חכם לאורך זמן על בסיס דפוסי תזונה."""
    try:
        from datetime import date, timedelta
        from db import NutritionDB
        
        nutrition_db = NutritionDB()
        
        # קבל נתונים של הימים האחרונים
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        # קבל את כל הרשומות מהימים האחרונים
        food_logs = []
        for i in range(days):
            check_date = end_date - timedelta(days=i)
            daily_log = nutrition_db.get_food_log(user_id, check_date.isoformat())
            if daily_log:
                food_logs.extend(daily_log)
        
        if not food_logs:
            return "אין מספיק נתונים לניתוח דפוסי תזונה. נסה שוב בעוד כמה ימים."
        
        # ניתוח דפוסים
        patterns = analyze_eating_patterns(food_logs, days)
        
        # בניית פרומפט ל-GPT
        prompt = build_long_term_feedback_prompt(patterns, user_id)
        
        # שליחה ל-GPT
        from utils import call_gpt
        import asyncio
        
        # יצירת event loop אם אין
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        response = loop.run_until_complete(call_gpt(prompt))
        
        return response if response else "לא הצלחתי לייצר פידבק חכם כרגע."
        
    except Exception as e:
        logger.error(f"Error generating long-term feedback: {e}")
        return "אירעה שגיאה בניתוח דפוסי התזונה."


def analyze_eating_patterns(food_logs: List[Dict[str, Any]], days: int) -> Dict[str, Any]:
    """מנתח דפוסי אכילה מהלוגים."""
    patterns = {
        "total_calories": 0,
        "avg_calories_per_day": 0,
        "protein_deficiency": False,
        "overeating_days": 0,
        "late_night_eating": False,
        "meal_skipping": False,
        "unhealthy_choices": 0
    }
    
    if not food_logs:
        return patterns
    
    # חישוב קלוריות כוללות וממוצע יומי
    total_calories = sum(meal.get('calories', 0) for meal in food_logs)
    patterns["total_calories"] = total_calories
    patterns["avg_calories_per_day"] = total_calories / days
    
    # בדיקת חוסר חלבון (פחות מ-50 גרם ליום בממוצע)
    total_protein = sum(meal.get('protein', 0) for meal in food_logs)
    avg_protein = total_protein / days
    if avg_protein < 50:
        patterns["protein_deficiency"] = True
    
    # בדיקת ימי אכילה מוגזמת (יותר מ-2500 קלוריות)
    daily_calories = {}
    for meal in food_logs:
        meal_date = meal.get('meal_date', '')
        if meal_date not in daily_calories:
            daily_calories[meal_date] = 0
        daily_calories[meal_date] += meal.get('calories', 0)
    
    overeating_days = sum(1 for calories in daily_calories.values() if calories > 2500)
    patterns["overeating_days"] = overeating_days
    
    # בדיקת אכילה בלילה (אחרי 22:00)
    late_night_meals = [meal for meal in food_logs if meal.get('meal_time', '').startswith('22:') or meal.get('meal_time', '').startswith('23:')]
    if len(late_night_meals) > days * 0.3:  # יותר מ-30% מהימים
        patterns["late_night_eating"] = True
    
    # בדיקת דילוג על ארוחות (פחות מ-2 ארוחות ביום)
    meals_per_day = len(food_logs) / days
    if meals_per_day < 2:
        patterns["meal_skipping"] = True
    
    # בדיקת בחירות לא בריאות
    unhealthy_keywords = ['פיצה', 'המבורגר', 'צ\'יפס', 'שוקולד', 'עוגה', 'גלידה', 'ממתקים']
    unhealthy_meals = 0
    for meal in food_logs:
        meal_name = meal.get('name', '').lower()
        if any(keyword in meal_name for keyword in unhealthy_keywords):
            unhealthy_meals += 1
    
    patterns["unhealthy_choices"] = unhealthy_meals
    
    return patterns


def build_long_term_feedback_prompt(patterns: Dict[str, Any], user_id: int) -> str:
    """בונה פרומפט לפידבק חכם לאורך זמן."""
    from db import NutritionDB
    
    nutrition_db = NutritionDB()
    user_data = nutrition_db.load_user(user_id) or {}
    
    name = user_data.get('name', 'חבר/ה')
    gender = user_data.get('gender', 'לא צוין')
    goal = user_data.get('goal', 'לא צוין')
    calorie_budget = user_data.get('calorie_budget', 1800)
    
    avg_calories = patterns.get('avg_calories_per_day', 0)
    protein_deficiency = patterns.get('protein_deficiency', False)
    overeating_days = patterns.get('overeating_days', 0)
    late_night_eating = patterns.get('late_night_eating', False)
    meal_skipping = patterns.get('meal_skipping', False)
    unhealthy_choices = patterns.get('unhealthy_choices', 0)
    
    prompt = f"""
אתה תזונאי מנוסה. נתח את דפוסי התזונה של המשתמש/ת וספק פידבק חכם ומעודד.

נתוני המשתמש/ת:
- שם: {name}
- מגדר: {gender}
- מטרה: {goal}
- תקציב קלוריות יומי: {calorie_budget}

ניתוח דפוסי אכילה (7 ימים אחרונים):
- ממוצע קלוריות יומי: {avg_calories:.0f}
- חוסר חלבון: {'כן' if protein_deficiency else 'לא'}
- ימי אכילה מוגזמת: {overeating_days}
- אכילה בלילה: {'כן' if late_night_eating else 'לא'}
- דילוג על ארוחות: {'כן' if meal_skipping else 'לא'}
- בחירות לא בריאות: {unhealthy_choices}

הנחיות:
- ספק פידבק מעודד וחיובי
- התמקד ב-2-3 נקודות לשיפור
- תן המלצות מעשיות ופשוטות
- התחשב במטרת המשתמש/ת
- השתמש בשפה מותאמת מגדרית
- ענה בעברית, בשפה טבעית וברורה
- אל תשתמש ב-HTML או Markdown

הפידבק צריך להיות:
1. פתיח מעודד (2-3 משפטים)
2. 2-3 נקודות לשיפור עם המלצות מעשיות
3. סיכום חיובי ומעודד
"""
    return prompt
