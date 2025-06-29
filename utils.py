"""
Utility functions for the Calorico Telegram bot.

This module contains helper functions for text processing, calculations,
OpenAI integration, and various utility operations.
"""

import re
import datetime
import logging
from typing import List, Optional
from telegram import KeyboardButton, ReplyKeyboardMarkup
import os
import openai

logger = logging.getLogger(__name__)

# Global variable to store OpenAI client
OPENAI_CLIENT = None


def extract_openai_response_content(response) -> str:
    """Extracts the content string from an OpenAI response object safely."""
    try:
        if (response and hasattr(response, "choices") and response.choices and 
            hasattr(response.choices[0], "message") and response.choices[0].message and 
            hasattr(response.choices[0].message, "content") and response.choices[0].message.content):
            return response.choices[0].message.content.strip()
        return ""
    except Exception as e:
        logger.error("Error extracting OpenAI response content: %s", e)
        return ""


def set_openai_client(client):
    """Set the global OpenAI client."""
    global OPENAI_CLIENT
    OPENAI_CLIENT = client


def strip_html_tags(text: str) -> str:
    """מסיר תגיות HTML מהטקסט."""
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text)


def calculate_bmr(gender: str, age: int, height: float, weight: float,
                  activity: str, goal: str) -> int:
    """מחשב BMR לפי נוסחת Mifflin-St Jeor."""
    try:
        # Mifflin-St Jeor Formula
        if gender == "נקבה":
            bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161
        else:
            bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5

        # התאמת פעילות - שיפור המפתחות
        activity_factor = {
            "לא מתאמן": 1.2,
            "לא מתאמנת": 1.2,
            "מעט (2-3 אימונים בשבוע)": 1.375,
            "הרבה (4-5 אימונים בשבוע)": 1.55,
            "כל יום": 1.725,
            "1-2 פעמים בשבוע": 1.375,
            "3-4 פעמים בשבוע": 1.55,
            "5-6 פעמים בשבוע": 1.725,
            "בינונית": 1.375,  # ברירת מחדל
        }.get(activity, 1.2)

        bmr *= activity_factor

        # התאמת מטרה
        if goal == "ירידה במשקל":
            bmr -= 300
        elif goal == "עלייה במסת שריר":
            bmr += 300
        elif goal == "ירידה באחוזי שומן":
            bmr -= 200

        return max(int(bmr), 1200)  # מינימום 1200 קלוריות
    except Exception as e:
        logger.error("Error calculating BMR: %s", e)
        return 1800  # ברירת מחדל


def get_gendered_text(
        context,
        male_text: str,
        female_text: str,
        other_text: Optional[str] = None) -> str:
    """מחזיר טקסט מגדרי לפי מין מהקונטקסט."""
    if not context or not hasattr(context, 'user_data') or not context.user_data:
        return male_text

    gender = context.user_data.get("gender", "זכר")
    if gender == "נקבה":
        return female_text
    if gender == "אחר" and other_text is not None:
        return other_text
    return male_text


def parse_date_from_text(text: str) -> Optional[str]:
    """מנסה לחלץ תאריך מטקסט בעברית (אתמול, שלשום, תאריך מפורש וכו')."""
    if not text:
        return None

    try:
        today = datetime.date.today()
        text_lower = text.lower()

        if "אתמול" in text_lower:
            return (today - datetime.timedelta(days=1)).isoformat()
        if "שלשום" in text_lower:
            return (today - datetime.timedelta(days=2)).isoformat()
        if "היום" in text_lower:
            return today.isoformat()

        # דוגמה: "01/06/2024"
        match = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", text)
        if match:
            day, month, year = map(int, match.groups())
            if year < 100:
                year += 2000
            date_obj = datetime.date(year, month, day)
            return date_obj.isoformat()

        return None
    except Exception as e:
        logger.error("Error parsing date from text: %s", e)
        return None


def markdown_to_html(text: str) -> str:
    """ממיר סימוני Markdown ל-HTML."""
    if not text:
        return ""

    # בולד: **טקסט** או *טקסט* => <b>טקסט</b>
    text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.*?)\*", r"<b>\1</b>", text)
    # נטוי: __טקסט__ או _טקסט_ => <i>טקסט</i>
    text = re.sub(r"__(.*?)__", r"<i>\1</i>", text)
    text = re.sub(r"_(.*?)_", r"<i>\1</i>", text)
    return text


def clean_desc(desc: str) -> str:
    """מנקה תיאור מאכל מתווים מיותרים."""
    if not desc:
        return ""
    return desc.strip()


def clean_meal_text(text: str) -> str:
    """מסיר ביטויים כמו 'בצהריים אכלתי', 'בערב אכלתי', 'בבוקר אכלתי', 'ושתיתי', 'ואכלתי' וכו'."""
    if not text:
        return ""

    # הסרת ביטויי זמן
    time_patterns = [
        r"בצהריים\s+אכלתי\s*",
        r"בערב\s+אכלתי\s*",
        r"בבוקר\s+אכלתי\s*",
        r"ושתיתי\s*",
        r"ואכלתי\s*",
        r"אכלתי\s*",
        r"אכלתי\s+היום\s*",
        r"אכלתי\s+אתמול\s*",
    ]
    for pattern in time_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text.strip()


def water_recommendation(context) -> str:
    """מחזיר המלצת שתיית מים לפי משקל המשתמש."""
    if not context or not hasattr(context, 'user_data') or not context.user_data:
        return "2.1–2.5 ליטר מים (כ-9–10 כוסות)"

    weight = context.user_data.get("weight", 70)
    min_l = round(weight * 30 / 1000, 1)
    max_l = round(weight * 35 / 1000, 1)
    min_cups = round((weight * 30) / 240)
    max_cups = round((weight * 35) / 240)
    return f"{min_l}–{max_l} ליטר מים (כ-{min_cups}–{max_cups} כוסות)"


def learning_logic(context) -> str:
    """מחזיר הודעה לימודית לפי נתוני המשתמש."""
    if not context or not hasattr(context, 'user_data') or not context.user_data:
        return "💡 <b>טיפ כללי:</b> שמור/י על תזונה מאוזנת, שתה/י הרבה מים, והתאמן/י באופן קבוע."

    goal = context.user_data.get("goal", "")
    weight = context.user_data.get("weight", 70)
    height = context.user_data.get("height", 170)
    bmi = weight / ((height / 100) ** 2)

    tips = []
    
    if "ירידה" in goal:
        if bmi > 25:
            tips.append("התמקד/י בגירעון קלורי של 300-500 קלוריות ליום")
        tips.append("התאמן/י לפחות 3 פעמים בשבוע")
        tips.append("שמור/י על צריכת חלבון גבוהה (1.6-2.2 גרם לק\"ג)")
    
    elif "עלייה" in goal or "בניית שריר" in goal:
        tips.append("צרוך/י עודף קלורי של 200-300 קלוריות ליום")
        tips.append("התאמן/י כוח 3-4 פעמים בשבוע")
        tips.append("צרוך/י 1.6-2.2 גרם חלבון לק\"ג משקל")
    
    else:  # שמירה על משקל
        tips.append("שמור/י על איזון קלורי")
        tips.append("התאמן/י באופן קבוע")
        tips.append("שמור/י על תזונה מגוונת")

    if not tips:
        tips = ["שמור/י על תזונה מאוזנת", "שתה/י הרבה מים", "התאמן/י באופן קבוע"]

    tip_text = " • ".join(tips)
    return f"💡 <b>טיפ מותאם אישית:</b> {tip_text}"


def build_main_keyboard():
    """בונה מקלדת ראשית עם כל האפשרויות."""
    keyboard = [
        [KeyboardButton("לקבלת תפריט יומי מותאם אישית")],
        [KeyboardButton("מה אכלתי היום")],
        [KeyboardButton("בניית ארוחה לפי מה שיש לי בבית")],
        [KeyboardButton("קבלת דוח")],
        [KeyboardButton("תזכורות על שתיית מים")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def extract_allergens_from_text(text: str) -> List[str]:
    """מזהה אלרגנים נפוצים מתוך טקסט."""
    allergens = [
        "בוטנים", "אגוזים", "חלב", "גלוטן", "ביצים", "סויה", 
        "דגים", "שומשום", "סלרי", "חרדל", "סולפיטים"
    ]
    
    found_allergens = []
    for allergen in allergens:
        if allergen.lower() in text.lower():
            found_allergens.append(allergen)
    
    return found_allergens


def validate_numeric_input(text: str, min_val: float, max_val: float, field_name: str) -> tuple[bool, float, str]:
    """בודק תקינות קלט מספרי ומחזיר (תקין, ערך, הודעת שגיאה)."""
    try:
        value = float(text.strip())
        if min_val <= value <= max_val:
            return True, value, ""
        return False, 0, f"{field_name} חייב להיות בין {min_val} ל-{max_val}."
    except ValueError:
        return False, 0, f"אנא הזן מספר תקין ל-{field_name}."


def build_user_prompt_for_gpt(user_data: dict) -> str:
    return f"""
    בנה תפריט יומי מותאם אישית עבור המשתמש/ת:
    - שם: {user_data.get('name')}
    - מגדר: {user_data.get('gender')}
    - גיל: {user_data.get('age')}
    - גובה: {user_data.get('height')} ס\"מ
    - משקל: {user_data.get('weight')} ק\"ג
    - מטרה: {user_data.get('goal')}
    - תקציב קלורי יומי: {user_data.get('calories')}
    - העדפות תזונה: {user_data.get('diet_preferences')}
    - אלרגיות: {user_data.get('allergies')}
    - סוג פעילות: {user_data.get('activity_type')}
    - תדירות פעילות: {user_data.get('activity_frequency', 'לא צוין')}
    - משך פעילות: {user_data.get('activity_duration', 'לא צוין')}
    
    התפריט צריך לכלול:
    - ארוחת בוקר (~25%)
    - ארוחת צהריים (~35%)
    - ארוחת ערב (~30%)
    - 2-3 נשנושים (~10%)

    הפק תפריט ב-HTML ברור, עם כותרות, רשימות ואחוז קלוריות לכל חלק.
    """

async def call_gpt(prompt: str) -> str:
    openai.api_key = os.getenv("OPENAI_API_KEY")
    response = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return response.choices[0].message.content.strip()
