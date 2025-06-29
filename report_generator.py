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

# הגדרת תמיכה בעברית
plt.rcParams['font.family'] = ['Arial', 'DejaVu Sans', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False

def get_weekly_report(user_id):
    """
    מחזירה את כל הרשומות מ־7 הימים האחרונים עבור המשתמש
    ממיינת לפי תאריך עולה
    """
    conn = sqlite3.connect("nutrition_data.db")
    cursor = conn.cursor()
    
    # חישוב תאריך לפני 7 ימים
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    cursor.execute("""
        SELECT date, calories, protein, fat, carbs, meals, goal
        FROM nutrition_logs
        WHERE user_id = ? AND date >= ?
        ORDER BY date ASC
    """, (user_id, week_ago))
    
    rows = cursor.fetchall()
    conn.close()
    
    # המרת התוצאות לרשימת מילונים
    data = []
    for row in rows:
        date_str, calories, protein, fat, carbs, meals_json, goal = row
        try:
            meals = json.loads(meals_json) if meals_json else []
        except json.JSONDecodeError:
            meals = []
        
        data.append({
            'date': date_str,
            'calories': calories,
            'protein': protein,
            'fat': fat,
            'carbs': carbs,
            'meals': meals,
            'goal': goal
        })
    
    return data

def build_weekly_summary_text(data):
    """
    מקבלת את התוצאות של get_weekly_report
    מחזירה טקסט מוכן להודעת טלגרם
    """
    if not data:
        return "אין נתונים לשבוע האחרון. התחל/י לדווח על הארוחות שלך!"
    
    # חישוב ממוצעים
    total_calories = sum(day['calories'] for day in data)
    total_protein = sum(day['protein'] for day in data)
    total_fat = sum(day['fat'] for day in data)
    total_carbs = sum(day['carbs'] for day in data)
    
    avg_calories = total_calories / len(data)
    avg_protein = total_protein / len(data)
    avg_fat = total_fat / len(data)
    avg_carbs = total_carbs / len(data)
    
    # בניית הטקסט
    text = f"<b>📊 דוח שבועי - {len(data)} ימים</b>\n\n"
    
    # סיכום יומי
    for day in data:
        date_obj = datetime.strptime(day['date'], '%Y-%m-%d')
        hebrew_date = date_obj.strftime('%d/%m/%Y')
        day_name = ['שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת', 'ראשון'][date_obj.weekday()]
        
        text += f"<b>{day_name} {hebrew_date}</b>\n"
        text += f"🔥 קלוריות: {day['calories']}\n"
        text += f"🥩 חלבון: {day['protein']:.1f}ג\n"
        text += f"🧈 שומן: {day['fat']:.1f}ג\n"
        text += f"🍞 פחמימות: {day['carbs']:.1f}ג\n"
        
        if day['meals']:
            meals_text = ", ".join(day['meals'][:3])  # רק 3 ארוחות ראשונות
            if len(day['meals']) > 3:
                meals_text += f" (+{len(day['meals']) - 3} נוספות)"
            text += f"🍽️ ארוחות: {meals_text}\n"
        
        text += "\n"
    
    # סיכום שבועי
    text += f"<b>📈 סיכום שבועי:</b>\n"
    text += f"🔥 ממוצע קלוריות יומי: {avg_calories:.0f}\n"
    text += f"🥩 ממוצע חלבון יומי: {avg_protein:.1f}ג\n"
    text += f"🧈 ממוצע שומן יומי: {avg_fat:.1f}ג\n"
    text += f"🍞 ממוצע פחמימות יומי: {avg_carbs:.1f}ג\n"
    
    # הערה על המטרה
    if data and data[0]['goal']:
        text += f"\n🎯 מטרה: {data[0]['goal']}\n"
    
    return text

def plot_calories(data):
    """
    יוצרת גרף של קלוריות לפי תאריכים
    מחזירה את הנתיב לקובץ
    """
    if not data:
        return None
    
    # הכנת הנתונים
    dates = [datetime.strptime(day['date'], '%Y-%m-%d') for day in data]
    calories = [day['calories'] for day in data]
    
    # המרה ל-numpy arrays
    dates_array = np.array(dates)
    calories_array = np.array(calories)
    
    # יצירת הגרף
    plt.figure(figsize=(12, 6))
    plt.plot(dates_array, calories_array, marker='o', linewidth=2, markersize=8, color='#2E86AB')
    
    # עיצוב הגרף
    plt.title('צריכת קלוריות שבועית', fontsize=16, fontweight='bold', pad=20)
    plt.xlabel('תאריך', fontsize=12)
    plt.ylabel('קלוריות', fontsize=12)
    plt.grid(True, alpha=0.3)
    
    # עיצוב ציר התאריכים
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator())
    plt.xticks(rotation=45)
    
    # הוספת ערכים על הנקודות
    for i, (date, cal) in enumerate(zip(dates_array, calories_array)):
        plt.annotate(str(int(cal)), (float(mdates.date2num(date)), float(cal)), textcoords="offset points", 
                    xytext=(0,10), ha='center', fontsize=10)
    
    # הוספת קו ממוצע
    avg_calories = float(np.mean(calories_array))
    plt.axhline(y=avg_calories, color='red', linestyle='--', alpha=0.7, 
                label=f'ממוצע: {avg_calories:.0f} קלוריות')
    plt.legend()
    
    # התאמת המרווחים
    plt.tight_layout()
    
    # שמירת הקובץ
    filename = 'weekly_calories_chart.png'
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()
    
    return os.path.abspath(filename)

def get_monthly_report(user_id):
    """
    מחזירה את כל הרשומות מ־30 הימים האחרונים
    (לעתיד - כשתוסיף נתונים על מים ואימונים)
    """
    conn = sqlite3.connect("nutrition_data.db")
    cursor = conn.cursor()
    
    month_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    cursor.execute("""
        SELECT date, calories, protein, fat, carbs, meals, goal
        FROM nutrition_logs
        WHERE user_id = ? AND date >= ?
        ORDER BY date ASC
    """, (user_id, month_ago))
    
    rows = cursor.fetchall()
    conn.close()
    
    data = []
    for row in rows:
        date_str, calories, protein, fat, carbs, meals_json, goal = row
        try:
            meals = json.loads(meals_json) if meals_json else []
        except json.JSONDecodeError:
            meals = []
        
        data.append({
            'date': date_str,
            'calories': calories,
            'protein': protein,
            'fat': fat,
            'carbs': carbs,
            'meals': meals,
            'goal': goal
        })
    
    return data

def build_monthly_summary_text(data):
    """
    מחזירה טקסט סיכום חודשי
    (לעתיד - כשתוסיף נתונים על מים ואימונים)
    """
    if not data:
        return "אין נתונים לחודש האחרון."
    
    # חישוב ממוצעים
    total_calories = sum(day['calories'] for day in data)
    total_protein = sum(day['protein'] for day in data)
    total_fat = sum(day['fat'] for day in data)
    total_carbs = sum(day['carbs'] for day in data)
    
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
    
    cursor.execute("""
        SELECT date, calories, protein, fat, carbs, meals, goal
        FROM nutrition_logs
        WHERE user_id = ? AND date = ?
    """, (user_id, target_date))
    
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
        'date': date_str,
        'calories': calories,
        'protein': protein,
        'fat': fat,
        'carbs': carbs,
        'meals': meals,
        'goal': goal
    }

def get_nutrition_by_date_range(user_id, start_date, end_date):
    """
    מחזירה נתוני תזונה לטווח תאריכים
    """
    conn = sqlite3.connect("nutrition_data.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT date, calories, protein, fat, carbs, meals, goal
        FROM nutrition_logs
        WHERE user_id = ? AND date BETWEEN ? AND ?
        ORDER BY date ASC
    """, (user_id, start_date, end_date))
    
    rows = cursor.fetchall()
    conn.close()
    
    data = []
    for row in rows:
        date_str, calories, protein, fat, carbs, meals_json, goal = row
        try:
            meals = json.loads(meals_json) if meals_json else []
        except json.JSONDecodeError:
            meals = []
        
        data.append({
            'date': date_str,
            'calories': calories,
            'protein': protein,
            'fat': fat,
            'carbs': carbs,
            'meals': meals,
            'goal': goal
        })
    
    return data

def search_meals_by_keyword(user_id, keyword, days_back=30):
    """
    מחפש ארוחות שמכילות מילת מפתח בטווח ימים
    """
    conn = sqlite3.connect("nutrition_data.db")
    cursor = conn.cursor()
    
    # חישוב תאריך לפני X ימים
    start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    
    cursor.execute("""
        SELECT date, meals
        FROM nutrition_logs
        WHERE user_id = ? AND date >= ? AND meals LIKE ?
        ORDER BY date DESC
    """, (user_id, start_date, f'%{keyword}%'))
    
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
                results.append({
                    'date': date_str,
                    'meals': matching_meals
                })
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
        meals_text = ", ".join(data['meals'])
        return f"🍽️ ב{data['date']} אכלת: {meals_text}"
    elif query_type == "summary":
        meals_text = ", ".join(data['meals'][:3]) if data['meals'] else "לא דווח"
        if len(data['meals']) > 3:
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
        return (today - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # שלשום
    if "שלשום" in text:
        return (today - timedelta(days=2)).strftime('%Y-%m-%d')
    
    # לפני X ימים
    import re
    days_match = re.search(r'לפני (\d+) ימים?', text)
    if days_match:
        days = int(days_match.group(1))
        return (today - timedelta(days=days)).strftime('%Y-%m-%d')
    
    # יום בשבוע
    weekdays = {
        'ראשון': 6, 'שני': 0, 'שלישי': 1, 'רביעי': 2, 
        'חמישי': 3, 'שישי': 4, 'שבת': 5
    }
    
    for day_name, day_num in weekdays.items():
        if day_name in text:
            # חישוב היום האחרון של היום הזה בשבוע
            days_since = (today.weekday() - day_num) % 7
            if days_since == 0:  # אם זה היום
                days_since = 7
            return (today - timedelta(days=days_since)).strftime('%Y-%m-%d')
    
    # תאריך בפורמט dd/mm/yyyy או yyyy-mm-dd
    date_patterns = [
        r'(\d{1,2})/(\d{1,2})/(\d{4})',  # dd/mm/yyyy
        r'(\d{4})-(\d{1,2})-(\d{1,2})',  # yyyy-mm-dd
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            if '/' in pattern:
                day, month, year = match.groups()
            else:
                year, month, day = match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    
    return None 