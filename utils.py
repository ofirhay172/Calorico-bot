import re
import datetime
import openai
from typing import List, Optional

def extract_openai_response_content(response):
    """Extracts the content string from an OpenAI response object safely."""
    return (
        response.choices[0].message.content.strip()
        if response
        and hasattr(response, 'choices')
        and response.choices
        and hasattr(response.choices[0], 'message')
        and response.choices[0].message
        and hasattr(response.choices[0].message, 'content')
        and response.choices[0].message.content
        else ""
    )

# Global variable to store OpenAI client
_openai_client = None


def set_openai_client(client):
    """Set the global OpenAI client."""
    global _openai_client
    _openai_client = client


def strip_html_tags(text):
    """מסיר תגיות HTML מהטקסט."""
    return re.sub(r"<[^>]+>", "", text)


def calculate_bmr(gender, age, height, weight, activity, goal):
    """מחשב BMR לפי נוסחת Mifflin-St Jeor."""
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
    }.get(activity, 1.2)
    
    bmr *= activity_factor
    
    # התאמת מטרה
    if goal == "ירידה במשקל":
        bmr -= 300
    elif goal == "עלייה במסת שריר":
        bmr += 300
    
    return int(bmr)


def get_gendered_text(gender, male_text, female_text, other_text=None):
    """מחזיר טקסט מגדרי לפי מין."""
    if gender == "נקבה":
        return female_text
    elif gender == "אחר" and other_text is not None:
        return other_text
    return male_text


def parse_date_from_text(text):
    """מנסה לחלץ תאריך מטקסט בעברית (אתמול, שלשום, תאריך מפורש וכו')."""
    # TODO: לשפר זיהוי תאריכים
    today = datetime.date.today()
    if "אתמול" in text:
        return (today - datetime.timedelta(days=1)).isoformat()
    if "שלשום" in text:
        return (today - datetime.timedelta(days=2)).isoformat()
    # דוגמה: "01/06/2024"
    match = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", text)
    if match:
        day, month, year = map(int, match.groups())
        if year < 100:
            year += 2000
        try:
            return datetime.date(year, month, day).isoformat()
        except Exception:
            return None
    return None


def markdown_to_html(text):
    """ממיר סימוני Markdown ל-HTML."""
    # בולד: **טקסט** או *טקסט* => <b>טקסט</b>
    text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.*?)\*", r"<b>\1</b>", text)
    # נטוי: __טקסט__ או _טקסט_ => <i>טקסט</i>
    text = re.sub(r"__(.*?)__", r"<i>\1</i>", text)
    text = re.sub(r"_(.*?)_", r"<i>\1</i>", text)
    return text


def clean_desc(desc):
    """מנקה תיאור מאכל מתווים מיותרים."""
    return desc.strip()


def clean_meal_text(text):
    """מסיר ביטויים כמו 'בצהריים אכלתי', 'בערב אכלתי', 'בבוקר אכלתי', 'ושתיתי', 'ואכלתי' וכו'."""
    # הסרת ביטויי זמן
    time_patterns = [
        r"בצהריים\s+אכלתי\s*",
        r"בערב\s+אכלתי\s*",
        r"בבוקר\s+אכלתי\s*",
        r"ושתיתי\s*",
        r"ואכלתי\s*",
        r"אכלתי\s*",
    ]
    for pattern in time_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text.strip()


def water_recommendation(context) -> str:
    """מחזיר המלצת שתיית מים לפי משקל המשתמש."""
    weight = context.user_data.get("weight", 70)
    min_l = round(weight * 30 / 1000, 1)
    max_l = round(weight * 35 / 1000, 1)
    min_cups = round((weight * 30) / 240)
    max_cups = round((weight * 35) / 240)
    return f"{min_l}–{max_l} ליטר מים (כ-{min_cups}–{max_cups} כוסות)"


def learning_logic(context) -> str:
    """מחזיר הודעה לימודית לפי נתוני המשתמש."""
    user = context.user_data
    goal = user.get("goal", "")
    weight = user.get("weight", 70)
    height = user.get("height", 170)
    age = user.get("age", 30)
    gender = user.get("gender", "זכר")
    
    # חישוב BMI
    bmi = weight / ((height / 100) ** 2)
    
    # הודעות לפי מטרה
    if goal == "ירידה במשקל":
        if bmi > 25:
            return "💡 <b>טיפ לירידה במשקל:</b> התמקד/י בגירעון קלורי של 300-500 קלוריות ליום. זה יאפשר ירידה בריאה של 0.5-1 ק\"ג בשבוע."
        else:
            return "💡 <b>טיפ לירידה במשקל:</b> ה-BMI שלך תקין. התמקד/י בחיטוב במקום ירידה במשקל."
    
    elif goal == "עלייה במסת שריר":
        return "💡 <b>טיפ לעלייה במסת שריר:</b> צרוך/י 1.6-2.2 גרם חלבון לק\"ג משקל גוף ליום, והתאמן/י 3-4 פעמים בשבוע."
    
    elif goal == "שמירה":
        return "💡 <b>טיפ לשמירה על משקל:</b> שמור/י על איזון בין צריכת קלוריות להוצאה אנרגטית. עקוב/י אחר התקדמותך."
    
    elif goal == "חיטוב":
        return "💡 <b>טיפ לחיטוב:</b> התמקד/י באימוני כוח עם גירעון קלורי קל. שמור/י על צריכת חלבון גבוהה."
    
    else:
        return "💡 <b>טיפ כללי:</b> שמור/י על תזונה מאוזנת, שתה/י הרבה מים, והתאמן/י באופן קבוע."


async def build_daily_menu(user: dict, context=None) -> str:
    """בונה תפריט יומי מותאם אישית באמצעות OpenAI."""
    if not _openai_client:
        return "לא ניתן לבנות תפריט כרגע - OpenAI client לא זמין."
    
    diet_str = ", ".join(user.get("diet", []))
    eaten_today = ""
    if context and hasattr(context, "user_data"):
        eaten_today = "\n".join(
            [
                (
                    strip_html_tags(e["desc"])
                    if isinstance(e, dict)
                    else strip_html_tags(e)
                )
                for e in context.user_data.get("eaten_today", [])
            ]
        )
    
    # חישוב BMR לפי Mifflin-St Jeor
    calorie_budget = calculate_bmr(
        user.get("gender", "זכר"),
        user.get("age", 30),
        user.get("height", 170),
        user.get("weight", 70),
        user.get("activity", "בינונית"),
        user.get("goal", "שמירה על משקל"),
    )
    
    prompt = (
        f"המשתמש/ת: {user.get('name','')}, גיל: {user.get('age','')}, מגדר: {user.get('gender','')}, גובה: {user.get('height','')}, משקל: {user.get('weight','')}, מטרה: {user.get('goal','')}, רמת פעילות: {user.get('activity','')}, העדפות תזונה: {diet_str}, תקציב קלורי יומי: {calorie_budget}.\n"
        f"המשתמש/ת כבר אכל/ה היום: {eaten_today}.\n"
        "בנה לי תפריט יומי מאוזן ובריא, ישראלי, פשוט, עם 5–6 ארוחות (בוקר, ביניים, צהריים, ביניים, ערב, קינוח רשות). \n"
        "השתמש בעברית יומיומית, פשוטה וברורה בלבד. אל תשתמש במילים לא שגרתיות, תיאורים פיוטיים, או מנות לא הגיוניות. \n"
        "הצג דוגמאות אמיתיות בלבד, כמו: חביתה, גבינה, יוגורט, עוף, אורז, ירקות, פירות, אגוזים. \n"
        "הימנע מתרגום מילולי מאנגלית, אל תשתמש במנות מוזרות או מומצאות. \n"
        "הקפד על מגדר נכון, סדר ארוחות, כמויות סבירות, והימנע מחזרות. \n"
        "בכל ארוחה עיקרית יהיה חלבון, בכל יום לפחות 2–3 מנות ירק, 1–2 מנות פרי, ודגנים מלאים. \n"
        "אחרי כל ארוחה (בוקר, ביניים, צהריים, ערב, קינוח), כתוב בסוגריים הערכה של קלוריות, חלבון, פחמימות, שומן. \n"
        "אם אינך בטוח – אל תמציא. \n"
        f"הנחיה מגדרית: כתוב את כל ההנחיות בלשון {user.get('gender','זכר')}.\n"
        "אל תמליץ/י, אל תציע/י, ואל תכלול/י מאכלים, מוצרים או מרכיבים שאינם מופיעים בהעדפות התזונה שלי, גם לא כהמלצה או דוגמה.\n"
        "אם כבר אכלתי היום עוף או חלבון, אל תמליץ/י לי שוב על עוף או חלבון, אלא אם זה הכרחי לתפריט מאוזן.\n"
    )
    
    try:
        response = await _openai_client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": prompt}]
        )
        menu_text = extract_openai_response_content(response)
        return menu_text
    except Exception as e:
        return f"שגיאה בבניית תפריט: {str(e)}"


def build_main_keyboard():
    """Returns the main reply keyboard for the bot."""
    from telegram import KeyboardButton
    return [
        [KeyboardButton("להרכבת ארוחה לפי מה שיש בבית")],
        [KeyboardButton("מה אכלתי היום")],
        [KeyboardButton("📊 דוחות")],
        [KeyboardButton("סיימתי")],
    ]


def extract_allergens_from_text(text: str) -> List[str]:
    """מזהה אלרגנים נפוצים מתוך טקסט."""
    text_lower = text.lower()
    allergens = []
    
    # מיפוי אלרגנים נפוצים
    allergen_mapping = {
        "חלב": ["חלב", "לקטוז", "גבינה", "יוגורט", "קוטג", "גלידה", "חמאה", "שמנת"],
        "בוטנים": ["בוטנים", "חמאת בוטנים", "בוטן"],
        "אגוזים": ["אגוזים", "שקדים", "קשיו", "פיסטוקים", "ברזיל", "מקדמיה", "פקאן"],
        "גלוטן": ["גלוטן", "חיטה", "לחם", "פסטה", "בורגול", "קוסקוס", "קמח"],
        "ביצים": ["ביצים", "ביצה", "חלבון", "חלמון"],
        "סויה": ["סויה", "טופו", "רוטב סויה", "מיסו"],
        "דגים": ["דג", "דגים", "סלמון", "טונה", "בקלה", "סרדינים"],
        "שומשום": ["שומשום", "טחינה", "חלבה"],
        "סלרי": ["סלרי"],
        "חרדל": ["חרדל"],
        "סולפיטים": ["סולפיטים", "סולפיט"],
    }
    
    for allergen, keywords in allergen_mapping.items():
        if any(keyword in text_lower for keyword in keywords):
            allergens.append(allergen)
    
    return list(set(allergens))  # הסרת כפילויות


def validate_text_input(text: str) -> bool:
    """מאמת קלט טקסט - בודק תווים אסורים."""
    if not text or not text.strip():
        return False
    
    # בדיקת תווים אסורים
    forbidden_chars = ['<', '>', '{', '}', '[', ']', '\\', '/', '*', '&', '%', '$', '#', '@', '!']
    if any(char in text for char in forbidden_chars):
        return False
    
    # בדיקת אורך סביר
    if len(text.strip()) > 500:
        return False
    
    return True


def validate_numeric_input(value: str, min_val: float, max_val: float) -> bool:
    """מאמת קלט מספרי."""
    try:
        num = float(value)
        return min_val <= num <= max_val
    except (ValueError, TypeError):
        return False


def add_rtl_markup(text: str) -> str:
    """מוסיף סימון RTL להודעות HTML."""
    if text.startswith('<'):
        return f'‎{text}'  # RTL mark at start
    return text
