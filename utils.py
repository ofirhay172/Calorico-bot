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
import json

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
        return get_gendered_text(context, 
            "💡 <b>טיפ כללי:</b> שמור על תזונה מאוזנת, שתה הרבה מים, והתאמן באופן קבוע.",
            "💡 <b>טיפ כללי:</b> שמרי על תזונה מאוזנת, שתי הרבה מים, והתאמני באופן קבוע.")

    goal = context.user_data.get("goal", "")
    weight = context.user_data.get("weight", 70)
    height = context.user_data.get("height", 170)
    bmi = weight / ((height / 100) ** 2)

    tips = []
    
    if "ירידה" in goal:
        if bmi > 25:
            tips.append(get_gendered_text(context, 
                "התמקד בגירעון קלורי של 300-500 קלוריות ליום",
                "התמקדי בגירעון קלורי של 300-500 קלוריות ליום"))
        tips.append(get_gendered_text(context, 
            "התאמן לפחות 3 פעמים בשבוע",
            "התאמני לפחות 3 פעמים בשבוע"))
        tips.append(get_gendered_text(context, 
            "שמור על צריכת חלבון גבוהה (1.6-2.2 גרם לק\"ג)",
            "שמרי על צריכת חלבון גבוהה (1.6-2.2 גרם לק\"ג)"))
    
    elif "עלייה" in goal or "בניית שריר" in goal:
        tips.append(get_gendered_text(context, 
            "צרוך עודף קלורי של 200-300 קלוריות ליום",
            "צרכי עודף קלורי של 200-300 קלוריות ליום"))
        tips.append(get_gendered_text(context, 
            "התאמן כוח 3-4 פעמים בשבוע",
            "התאמני כוח 3-4 פעמים בשבוע"))
        tips.append(get_gendered_text(context, 
            "צרוך 1.6-2.2 גרם חלבון לק\"ג משקל",
            "צרכי 1.6-2.2 גרם חלבון לק\"ג משקל"))
    
    else:  # שמירה על משקל
        tips.append(get_gendered_text(context, 
            "שמור על איזון קלורי",
            "שמרי על איזון קלורי"))
        tips.append(get_gendered_text(context, 
            "התאמן באופן קבוע",
            "התאמני באופן קבוע"))
        tips.append(get_gendered_text(context, 
            "שמור על תזונה מגוונת",
            "שמרי על תזונה מגוונת"))

    if not tips:
        tips = [
            get_gendered_text(context, "שמור על תזונה מאוזנת", "שמרי על תזונה מאוזנת"),
            get_gendered_text(context, "שתה הרבה מים", "שתי הרבה מים"),
            get_gendered_text(context, "התאמן באופן קבוע", "התאמני באופן קבוע")
        ]

    tip_text = " • ".join(tips)
    return f"💡 <b>טיפ מותאם אישית:</b> {tip_text}"


def build_main_keyboard(hide_menu_button: bool = False, user_data: dict = None) -> ReplyKeyboardMarkup:
    """בונה מקלדת ראשית עם כל האפשרויות, עם אפשרות להסתיר כפתורים מסוימים.
    כפתור 'סיימתי' יופיע רק אם המשתמש צרך משהו היום."""
    from datetime import date
    show_end_button = False
    show_menu_button = True
    today = date.today().isoformat()
    if user_data:
        food_log = user_data.get('daily_food_log', [])
        if food_log:
            show_end_button = True
        # הסתר כפתור תפריט יומי אם כבר נשלח היום
        menu_sent_today = user_data.get('menu_sent_today')
        menu_sent_date = user_data.get('menu_sent_date')
        if menu_sent_today and menu_sent_date == today:
            show_menu_button = False
    keyboard = []
    if not hide_menu_button and show_menu_button:
        keyboard.append([KeyboardButton("לקבלת תפריט יומי מותאם אישית")])
    keyboard.append([KeyboardButton("מה אכלתי היום")])
    keyboard.append([KeyboardButton("בניית ארוחה לפי מה שיש לי בבית")])
    if show_end_button:
        keyboard.append([KeyboardButton("סיימתי")])
    keyboard.append([KeyboardButton("קבלת דוח")])
    keyboard.append([KeyboardButton("עדכון פרטים אישיים")])
    keyboard.append([KeyboardButton("עזרה")])
    # הסר שורות ריקות (אם כפתור הוסתר)
    keyboard = [row for row in keyboard if row]
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
    """בונה פרומפט מותאם אישית עבור GPT לפי כללי איזון, פשטות, מניעת כפילויות והגבלת רכיבים."""
    name = user_data.get('telegram_name') or user_data.get('name', 'חבר/ה')
    gender = user_data.get('gender', 'לא צוין')
    age = user_data.get('age', 'לא צוין')
    height = user_data.get('height', 'לא צוין')
    weight = user_data.get('weight', 'לא צוין')
    goal = user_data.get('goal', 'לא צוין')
    activity_level = user_data.get('activity_type', user_data.get('activity', 'לא צוין'))
    diet_preferences = ", ".join(user_data.get('diet', [])) if user_data.get('diet') else "אין העדפות מיוחדות"
    allergies = ", ".join(user_data.get('allergies', [])) if user_data.get('allergies') else "אין"
    daily_calories = user_data.get('calorie_budget', 1800)
    activity_details = user_data.get('activity_details', {})
    activity_details_text = ""
    if activity_details:
        activity_details_text = "\n\nפירוט פעילות גופנית של המשתמש/ת:\n"
        for act, details in activity_details.items():
            freq = details.get('frequency', '')
            duration = details.get('duration', '')
            intensity = details.get('intensity', '')
            activity_details_text += f"- {act}: {freq} בשבוע, {duration} דקות, עצימות: {intensity}\n"
    prompt = f"""
המשתמש השלים שאלון הכולל:
- שם: {name}
- מגדר: {gender}
- גיל: {age}
- גובה: {height} ס"מ
- משקל: {weight} ק"ג
- מטרה: {goal}
- רמת פעילות גופנית: {activity_level}
- העדפות תזונתיות: {diet_preferences}
- אלרגיות: {allergies}
- תקציב קלוריות מחושב: {daily_calories}
{activity_details_text}

🎯 משימה:
בהתבסס על המידע שלמעלה, צור תפריט יומי מדויק, פשוט ומאוזן, הכולל:
- 3 ארוחות עיקריות (בוקר, צהריים, ערב) + 1–2 נשנושים.
- בכל ארוחה: עד 4 רכיבים עיקריים בלבד (כולל עיקרית, תוספת, ירק/סלט, שומן/רטבים).
- אין לשלב יותר ממקור פחמימה אחד בארוחה (למשל: או אורז או קינואה, לא שניהם).
- אין לשלב גם לחם וגם דגן נוסף (קוסקוס/פסטה/אורז/קינואה) באותה ארוחה.
- להימנע מכפילות של רכיבים דומים באותה ארוחה (למשל: לא גם טוסט וגם קוסקוס).
- חלבון חייב להופיע לפחות פעמיים ביום (ביצה, יוגורט, טונה, עוף, קטניות וכו').
- כל ארוחה תכלול איזון בין פחמימה, חלבון, ירק ושומן (רק אם צריך).
- לפרט כמויות בגרמים וקלוריות לכל רכיב.
- סך הקלוריות לכל הארוחות יחד לא יעלה על התקציב הנתון (±5%).
- להימנע מהעמסת רכיבים – שמור על פשטות, גיוון וקלות הכנה.

📤 מבנה הפלט:
🍳 ארוחת בוקר (xxx קלוריות):
- פריט (כמות, קלוריות)
- ...

🥗 ארוחת צהריים (xxx קלוריות):
- ...

🍲 ארוחת ערב (xxx קלוריות):
- ...

🍎 נשנושים (xxx קלוריות):
- ...

סה״כ קלוריות: xxxx

אם נותרו פחות מ־5% מהקלוריות, הוסף הצעה אופציונלית לנשנוש נוסף.

דגשים:
- אל תשלב יותר ממקור פחמימה אחד בארוחה.
- אל תשלב גם לחם וגם דגן נוסף באותה ארוחה.
- שמור על פשטות – לא יותר מ־4 רכיבים עיקריים לארוחה.
- איזון בין קבוצות המזון.
- אל תחרוג מהתקציב הקלורי.
- התאם להעדפות, אלרגיות ומגבלות.

דוגמה לארוחה טובה:
- עוף בגריל, אורז, סלט ירקות, כף שמן זית.

דוגמה לארוחה לא טובה:
- אורז + קינואה + לחם + טוסט + גבינה + שמן זית.
"""
    return prompt


async def call_gpt(prompt: str) -> str:
    """קורא ל-GPT API ומחזיר תשובה."""
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OpenAI API key not found")
            return get_gendered_text(None, 
                "לא הצלחתי ליצור קשר עם שירות ה-AI. אנא נסה שוב מאוחר יותר.",
                "לא הצלחתי ליצור קשר עם שירות ה-AI. אנא נסי שוב מאוחר יותר.")
        client = openai.AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model="gpt-4-0125-preview",  # או "gpt-4o"
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1000
        )
        if response and response.choices and response.choices[0].message:
            content = response.choices[0].message.content
            return content.strip() if content else get_gendered_text(None, 
                "לא קיבלתי תשובה מ-AI. אנא נסה שוב.",
                "לא קיבלתי תשובה מ-AI. אנא נסי שוב.")
        else:
            logger.error("Empty response from OpenAI")
            return get_gendered_text(None, 
                "לא קיבלתי תשובה מ-AI. אנא נסה שוב.",
                "לא קיבלתי תשובה מ-AI. אנא נסי שוב.")
    except openai.AuthenticationError:
        logger.error("OpenAI authentication failed")
        return "שגיאה באימות עם שירות ה-AI. אנא פנה למנהל המערכת."
    except openai.RateLimitError:
        logger.error("OpenAI rate limit exceeded")
        return get_gendered_text(None, 
            "שירות ה-AI עמוס כרגע. אנא נסה שוב בעוד כמה דקות.",
            "שירות ה-AI עמוס כרגע. אנא נסי שוב בעוד כמה דקות.")
    except openai.APIError as e:
        logger.error(f"OpenAI API error: {e}")
        return get_gendered_text(None, 
            "שגיאה בשירות ה-AI. אנא נסה שוב מאוחר יותר.",
            "שגיאה בשירות ה-AI. אנא נסי שוב מאוחר יותר.")
    except Exception as e:
        logger.error(f"Unexpected error in call_gpt: {e}")
        return get_gendered_text(None, 
            "אירעה שגיאה לא צפויה. אנא נסה שוב.",
            "אירעה שגיאה לא צפויה. אנא נסי שוב.")


async def analyze_meal_with_gpt(text: str) -> dict:
    """
    שולח ל-GPT תיאור ארוחה חופשי ומקבל רשימת פריטים עם קלוריות לכל פריט וסך הכל.
    מחזיר dict: {'items': [{'name': str, 'calories': int, 'protein': float, 'fat': float, 'carbs': float}], 'total': int}
    """
    prompt = f"""
אתה תזונאי מנוסה. פענח את הארוחה הבאה למרכיבים ברורים עם כמויות מדויקות וקלוריות.

חשוב מאוד:
- השתמש בטקסט המקורי של המשתמש כפי שנכתב, כולל כל הכמויות (גרם, כף, פרוסות, וכו')
- אל תסיר או תשנה יחידות מידה
- חשב קלוריות, חלבון, שומן ופחמימות לכל פריט
- אם לא צוינה כמות, השתמש בברירת מחדל הגיונית (למשל: פרוסת לחם, ביצה אחת, קערת סלט קטנה)

החזר תשובה בפורמט JSON בלבד:
{{
  "items": [
    {{
      "name": "שם הפריט עם הכמות המדויקת",
      "calories": מספר קלוריות,
      "protein": גרם חלבון,
      "fat": גרם שומן,
      "carbs": גרם פחמימות
    }}
  ],
  "total": סכום כל הקלוריות
}}

הארוחה שכתב המשתמש:
{text}

הנחיות נוספות:
- השתמש בערכים מדויקים ממאגר תזונתי אמיתי
- אם יש בלבול בכמויות, השתמש בערכים סבירים
- אל תוסיף פריטים שלא הוזכרו
- שמור על הכמויות המקוריות ככל האפשר
"""
    response = await call_gpt(prompt)
    
    # ננסה להוציא JSON מהתשובה
    try:
        # מצא את ה-json הראשון בתשובה
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        json_str = response[json_start:json_end]
        data = json.loads(json_str)
        
        # וודא שיש לנו את כל השדות הנדרשים
        if 'items' not in data or 'total' not in data:
            raise ValueError("Missing required fields in GPT response")
            
        # וודא שכל פריט יש את כל השדות הנדרשים
        for item in data['items']:
            if 'name' not in item or 'calories' not in item:
                raise ValueError("Missing required fields in meal item")
            # הוסף ערכים ברירת מחדל אם חסרים
            item.setdefault('protein', 0.0)
            item.setdefault('fat', 0.0)
            item.setdefault('carbs', 0.0)
            
        return data
    except Exception as e:
        logger.error(f"Failed to parse GPT meal JSON: {e}, response: {response}")
        # החזר מבנה ברירת מחדל
        return {
            "items": [{"name": text, "calories": 0, "protein": 0.0, "fat": 0.0, "carbs": 0.0}],
            "total": 0
        }


def build_free_text_prompt(user_data: dict, user_text: str) -> str:
    """בונה פרומפט מותאם לשאלה חופשית ל-GPT, כולל כל ההקשר הרלוונטי."""
    name = user_data.get('telegram_name') or user_data.get('name', 'חבר/ה')
    gender = user_data.get('gender', 'לא צוין')
    age = user_data.get('age', 'לא צוין')
    height = user_data.get('height', 'לא צוין')
    weight = user_data.get('weight', 'לא צוין')
    goal = user_data.get('goal', 'לא צוין')
    activity_level = user_data.get('activity_type', user_data.get('activity', 'לא צוין'))
    diet_preferences = ", ".join(user_data.get('diet', [])) if user_data.get('diet') else "אין העדפות מיוחדות"
    allergies = ", ".join(user_data.get('allergies', [])) if user_data.get('allergies') else "אין"
    daily_calories = user_data.get('calorie_budget', 1800)
    eaten_today = user_data.get('daily_food_log', [])
    eaten_desc = ", ".join([item.get('name', '') for item in eaten_today]) if eaten_today else "עדיין לא נאכל כלום היום"
    calories_consumed = user_data.get('calories_consumed', 0)
    calories_remaining = daily_calories - calories_consumed
    prompt = f"""
המשתמש/ת שואל/ת: {user_text}

נתוני המשתמש/ת:
- שם: {name}
- מגדר: {gender}
- גיל: {age}
- גובה: {height} ס"מ
- משקל: {weight} ק"ג
- מטרה: {goal}
- רמת פעילות: {activity_level}
- העדפות תזונה: {diet_preferences}
- אלרגיות: {allergies}
- תקציב קלוריות יומי: {daily_calories}
- קלוריות שנצרכו היום: {calories_consumed}
- קלוריות שנותרו להיום: {calories_remaining}
- מה נאכל היום: {eaten_desc}

הנחיות חשובות:
- ענה בקצרה (עד 3 שורות), בצורה מדויקת וברורה
- הימנע מניסוחים כלליים מדי
- התייחס לכמות הקלוריות שנותרה היום ולמה המשתמש כבר אכל
- אם המשתמש/ת שואל/ת על מאכל מסוים (למשל "אפשר לאכול המבורגר?", "בא לי שוקולד", "אני רוצה פיצה") – בדוק האם נשארו מספיק קלוריות לתקציב היומי, וענה בהתאם (אם אפשר, כמה קלוריות זה, ואם לא – הסבר למה)
- אם השאלה כללית – ענה בקצרה, בעברית, בהתאמה אישית לנתונים
- אל תוסיף המלצות כלליות אם לא התבקשת
- ענה בעברית, בשפה טבעית וברורה
- אל תשתמש ב-HTML או Markdown
"""
    return prompt


def build_meal_from_ingredients_prompt(ingredients: str, user_data: dict) -> str:
    """בונה פרומפט לבניית ארוחה מרכיבים זמינים."""
    name = user_data.get('telegram_name') or user_data.get('name', 'חבר/ה')
    gender = user_data.get('gender', 'לא צוין')
    goal = user_data.get('goal', 'לא צוין')
    diet_preferences = ", ".join(user_data.get('diet', [])) if user_data.get('diet') else "אין העדפות מיוחדות"
    allergies = ", ".join(user_data.get('allergies', [])) if user_data.get('allergies') else "אין"
    daily_calories = user_data.get('calorie_budget', 1800)
    calories_consumed = user_data.get('calories_consumed', 0)
    calories_remaining = daily_calories - calories_consumed
    
    prompt = f"""
אתה תזונאי מנוסה. המשתמש/ת כתב/ה את רשימת הרכיבים שיש לו/לה בבית:

{ingredients}

נתוני המשתמש/ת:
- שם: {name}
- מגדר: {gender}
- מטרה: {goal}
- העדפות תזונה: {diet_preferences}
- אלרגיות: {allergies}
- קלוריות שנותרו להיום: {calories_remaining}

בנה הצעה לארוחה פשוטה ובריאה מתוך מה שצוין. 

הנחיות:
- השתמש רק ברכיבים שצוינו (או רכיבים בסיסיים כמו מלח, פלפל, שמן)
- הוסף כמויות מדויקות לכל רכיב
- חשב הערכה קלורית מדויקת
- התחשב בהעדפות התזונה והאלרגיות
- שמור על איזון תזונתי (חלבון, פחמימות, שומן)
- אל תחרוג מהקלוריות שנותרו להיום

החזר תשובה בפורמט:
🍽️ שם הארוחה (X קלוריות)

רכיבים:
- רכיב 1 (כמות מדויקת) - X קלוריות
- רכיב 2 (כמות מדויקת) - X קלוריות
...

סה"כ: X קלוריות
חלבון: X גרם
שומן: X גרם
פחמימות: X גרם

הוראות הכנה קצרות (2-3 משפטים)
"""
    return prompt


async def fallback_via_gpt(text: str, user_context: dict = None) -> dict:
    """
    שולח ל-GPT טקסט חופשי ומבקש זיהוי האם מדובר בצריכה בפועל או בשאלה כללית.
    מחזיר dict:
      - אם צריכה: {"action": "consume", "item": ..., "amount": ..., "calories": ...}
      - אם לא: {"action": "reply", "text": ...}
    """
    if user_context is None:
        user_context = {}
    from utils import call_gpt
    prompt = f'''
המשתמש שלח: "{text}"

האם מדובר בצריכה בפועל של מזון או שתייה? אם כן, החזר JSON:
{{"action": "consume", "item": "שם המזון/שתייה", "amount": "כמות", "calories": מספר}}
אם לא, החזר JSON:
{{"action": "reply", "text": "תשובה קצרה וברורה"}}
ענה רק בפורמט JSON, ללא הסברים נוספים.
'''
    response = await call_gpt(prompt)
    import json
    try:
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        json_str = response[json_start:json_end]
        data = json.loads(json_str)
        return data
    except Exception as e:
        return {"action": "reply", "text": response.strip()}
