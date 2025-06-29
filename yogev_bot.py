"""
קלוריקו – בוט תזונה אישי בעברית
דרישות: python-telegram-bot>=20, openai
"""

from nutrition_db import init_db, save_daily_entry, get_weekly_summary
from report_generator import (
    get_weekly_report, build_weekly_summary_text, plot_calories,
    get_nutrition_by_date, search_meals_by_keyword, get_last_occurrence_of_meal,
    format_date_query_response, parse_date_from_text
)

# אתחול בסיס הנתונים
init_db()

import logging
import asyncio
import json
import os
import datetime
import re
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
)
from openai import AsyncOpenAI
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- מפתחות דרך משתני סביבה ---
import os
from openai import AsyncOpenAI

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
openai_client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

# --- לוגים ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- קבועים ראשיים ---
USERS_FILE = "calorico_users.json"

# --- מצבי שיחה (ConversationHandler) ---
(
    NAME, GENDER, AGE, HEIGHT, WEIGHT, GOAL, BODY_FAT, ACTIVITY, DIET, ALLERGIES, MENU, DAILY, EATEN, SUMMARY, SCHEDULE, EDIT, BODY_FAT_TARGET
) = range(17)

# --- טקסטי פעולה מגדריים (לכפתורים/הודעות) ---
GENDERED_ACTION = {
    'זכר': 'בחר פעולה:',
    'נקבה': 'האם סיימת לאכול להיום?',
    'אחר': 'בחר/י פעולה:'
}

# --- שאלון פתיחה ---

GENDER_OPTIONS = ["זכר", "נקבה", "אחר"]
GOAL_OPTIONS = [
    "ירידה במשקל", "חיטוב", "שמירה", "עלייה במסת שריר", "עלייה כללית", "שיפור ספורט", "פשוט תזונה בריאה", "לרדת באחוזי שומן"
]
# רמות פעילות עם ניסוח מגדרי
ACTIVITY_OPTIONS_MALE = [
    "לא מתאמן",
    "מעט (2-3 אימונים בשבוע)",
    "הרבה (4-5 אימונים בשבוע)",
    "כל יום"
]
ACTIVITY_OPTIONS_FEMALE = [
    "לא מתאמנת",
    "מעט (2-3 אימונים בשבוע)",
    "הרבה (4-5 אימונים בשבוע)",
    "כל יום"
]
DIET_OPTIONS = [
    "צמחוני", "טבעוני", "עוף", "בשר", "כשרות", "דגים"
]
ALLERGY_OPTIONS = [
    "בוטנים", "שקדים", "אגוזים", "סויה", "חלב", "ביצים", "גלוטן", "דגים", "שומשום", "אחר"
]

# Time options for scheduling
TIME_OPTIONS = [f"{h:02d}:00" for h in range(7, 13)]

# User data keys
USER_FIELDS = [
    'name', 'gender', 'age', 'height', 'weight', 'goal', 'body_fat', 'activity', 'diet', 'allergies',
    'calorie_budget', 'menu', 'eaten_today', 'remaining_calories', 'schedule_time', 'water_reminder_opt_in', 'water_reminder_task', 'water_reminder_active', 'body_fat_target'
]

# תבנית תפריט יומי כללית
MENU_TEMPLATE = (
    "הנה המלצה לתפריט יומי:\n"
    "\nבוקר: חביתה, גבינה, ירקות, לחם מלא\n"
    "צהריים: עוף/דג, אורז/פסטה, ירקות\n"
    "ערב: יוגורט, ירקות, ביצה קשה\n"
    "נשנוש: פרי, אגוזים, יוגורט\n"
    "\nבהצלחה!"
)

# --- עזר: שמירה וטעינה ל-JSON ---
def load_user(user_id: int):
    if not os.path.exists(USERS_FILE):
        return None
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get(str(user_id))

def save_user(user_id: int, user_data: dict):
    if not os.path.exists(USERS_FILE):
        data = {}
    else:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    data[str(user_id)] = user_data
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- עזר: ניסוח מגדרי ---
def get_gendered_text(context, male_text, female_text, other_text=None):
    gender = context.user_data.get('gender', 'זכר') if context and hasattr(context, 'user_data') else 'זכר'
    if gender == 'נקבה':
        return female_text
    elif gender == 'אחר' and other_text is not None:
        return other_text
    return male_text

# Utility: ניקוי תגיות HTML מהטקסט (לשימוש לפני שליחה ל-GPT)
def strip_html_tags(text):
    return re.sub(r'<[^>]+>', '', text)

# --- עדכון פרומפטים ל-GPT ---
async def build_daily_menu(user: dict, context=None) -> str:
    diet_str = ', '.join(user.get('diet', []))
    eaten_today = ''
    if context and hasattr(context, 'user_data'):
        eaten_today = '\n'.join([strip_html_tags(e['desc']) if isinstance(e, dict) else strip_html_tags(e) for e in context.user_data.get('eaten_today', [])])
    prompt = (
        f"המשתמש/ת: {user.get('name','')}, גיל: {user.get('age','')}, מגדר: {user.get('gender','')}, גובה: {user.get('height','')}, משקל: {user.get('weight','')}, מטרה: {user.get('goal','')}, רמת פעילות: {user.get('activity','')}, העדפות תזונה: {diet_str}, אלרגיות: {user.get('allergies') or 'אין'}.\n"
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
        # אין עיצוב בפרומפט ל-GPT!
    )
    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    menu_text = response.choices[0].message.content.strip() if response and response.choices and response.choices[0].message and response.choices[0].message.content else ''
    return menu_text

# --- Conversation Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_first_name = update.effective_user.first_name or ""
    welcome_message = (
        f"שלום {user_first_name}! אני <b>קלוריקו</b> – הבוט שיעזור לך לשמור על תזונה, מעקב והתמדה 🙌\n\n"
        "<b>הנה מה שאני יודע לעשות:</b>\n"
        "✅ התאמה אישית של תפריט יומי – לפי הגובה, משקל, גיל, מטרה ותזונה שלך\n"
        "📊 דוחות תזונתיים – שבועי וחודשי\n"
        "💧 תזכורות חכמות לשתיית מים\n"
        "🍽 רישום יומי של \"מה אכלתי היום\" או \"מה אכלתי אתמול\"\n"
        "🔥 מעקב קלוריות יומי, ממוצע לארוחה וליום\n"
        "📅 ניתוח מגמות – צריכת חלבון, שומן ופחמימות\n"
        "🏋️ חיבור לאימונים שדיווחת עליהם\n"
        "📝 אפשרות לעדכן בכל שלב את המשקל, המטרה, התזונה או רמת הפעילות שלך\n"
        "⏰ תפריט יומי שנשלח אליך אוטומטית בשעה שתבחר\n\n"
        "<b>בוא/י נתחיל בהרשמה קצרה:</b>"
    )
    await update.message.reply_text(
        welcome_message,
        reply_markup=ReplyKeyboardRemove(),
        parse_mode='HTML'
    )
    # התחלת השאלון מיד אחרי הודעת הפתיחה
    await get_name(update, context)
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message and update.message.text:
        if not update.message or not update.message.text:
            return NAME
        name = update.message.text.strip()
        context.user_data['name'] = name
        keyboard = [[KeyboardButton(opt)] for opt in GENDER_OPTIONS]
        await update.message.reply_text(
            get_gendered_text(context, "מה המגדר שלך?", "מה המגדר שלך?"),
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
            parse_mode='HTML'
        )
        return GENDER

async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message and update.message.text:
        if not update.message or not update.message.text:
            return GENDER
        gender = update.message.text.strip()
        if gender not in GENDER_OPTIONS:
            keyboard = [[KeyboardButton(opt)] for opt in GENDER_OPTIONS]
            await update.message.reply_text(get_gendered_text(context, "בחר מגדר מהתפריט למטה:", "בחרי מגדר מהתפריט למטה:"), reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True), parse_mode='HTML')
            return GENDER
        context.user_data['gender'] = gender
        await update.message.reply_text(get_gendered_text(context, "בן כמה אתה?", "בת כמה את?"), reply_markup=ReplyKeyboardRemove(), parse_mode='HTML')
        return AGE

async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message and update.message.text:
        if not update.message or not update.message.text:
            return AGE
        age = update.message.text.strip()
        if not age.isdigit() or not (5 <= int(age) <= 120):
            await update.message.reply_text(get_gendered_text(context, "אנא הזן גיל תקין (5-120).", "אנא הזיני גיל תקין (5-120)."), parse_mode='HTML')
            return AGE
        context.user_data['age'] = int(age)
        await update.message.reply_text(get_gendered_text(context, "מה הגובה שלך בס\"מ?", "מה הגובה שלך בס\"מ?"), reply_markup=ReplyKeyboardRemove(), parse_mode='HTML')
        return HEIGHT

async def get_height(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message and update.message.text:
        if not update.message or not update.message.text:
            return HEIGHT
        height = update.message.text.strip()
        if not height.isdigit() or not (80 <= int(height) <= 250):
            await update.message.reply_text(get_gendered_text(context, "אנא הזן גובה תקין בס\"מ (80-250).", "אנא הזיני גובה תקין בס\"מ (80-250)."), parse_mode='HTML')
            return HEIGHT
        context.user_data['height'] = int(height)
        await update.message.reply_text(get_gendered_text(context, "מה המשקל שלך בק\"ג?", "מה המשקל שלך בק\"ג?"), reply_markup=ReplyKeyboardRemove(), parse_mode='HTML')
        return WEIGHT

async def get_weight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message and update.message.text:
        if not update.message or not update.message.text:
            return WEIGHT
        weight = update.message.text.strip()
        if not weight.isdigit() or not (20 <= int(weight) <= 300):
            await update.message.reply_text(get_gendered_text(context, "אנא הזן משקל תקין בק\"ג (20-300).", "אנא הזיני משקל תקין בק\"ג (20-300)."), parse_mode='HTML')
            return WEIGHT
        context.user_data['weight'] = int(weight)
        keyboard = [[KeyboardButton(opt)] for opt in GOAL_OPTIONS]
        await update.message.reply_text(
            get_gendered_text(context, "מה המטרה התזונתית שלך?", "מה המטרה התזונתית שלך?"),
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
            parse_mode='HTML'
        )
        return GOAL

async def get_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message and update.message.text:
        if not update.message or not update.message.text:
            return GOAL
        goal = update.message.text.strip()
        if goal not in GOAL_OPTIONS:
            keyboard = [[KeyboardButton(opt)] for opt in GOAL_OPTIONS]
            await update.message.reply_text(get_gendered_text(context, "בחר מטרה מהתפריט למטה:", "בחרי מטרה מהתפריט למטה:"), reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True), parse_mode='HTML')
            return GOAL
        context.user_data['goal'] = goal
        if goal == 'לרדת באחוזי שומן':
            keyboard = [[KeyboardButton(str(i))] for i in range(10, 41, 2)]
            keyboard.append([KeyboardButton('לא ידוע')])
            await update.message.reply_text(
                get_gendered_text(context, 'מה אחוזי השומן שלך? (אם לא ידוע, בחר "לא ידוע")', 'מה אחוזי השומן שלך? (אם לא ידוע, בחרי "לא ידוע")'),
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
                parse_mode='HTML'
            )
            return BODY_FAT
        gender = context.user_data.get('gender', 'זכר')
        options = ACTIVITY_OPTIONS_MALE if gender == 'זכר' else ACTIVITY_OPTIONS_FEMALE
        keyboard = [[KeyboardButton(opt)] for opt in options]
        await update.message.reply_text(
            get_gendered_text(context, "מה רמת הפעילות הגופנית שלך?", "מה רמת הפעילות הגופנית שלך?"),
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
            parse_mode='HTML'
        )
        return ACTIVITY

async def get_body_fat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message and update.message.text:
        if not update.message or not update.message.text:
            return BODY_FAT
        value = update.message.text.strip()
        if value == 'לא ידוע':
            context.user_data['body_fat'] = 'לא ידוע'
        else:
            try:
                context.user_data['body_fat'] = float(value)
            except Exception:
                await update.message.reply_text('אנא הזן ערך מספרי או בחר "לא ידוע".', parse_mode='HTML')
                return BODY_FAT
        # אם המטרה היא ירידה באחוזי שומן, שאל יעד
        if context.user_data.get('goal') == 'לרדת באחוזי שומן' and 'body_fat_target' not in context.user_data:
            await update.message.reply_text('לאיזה אחוז שומן תרצה/י להגיע?', parse_mode='HTML')
            return BODY_FAT_TARGET
        gender = context.user_data.get('gender', 'זכר')
        options = ACTIVITY_OPTIONS_MALE if gender == 'זכר' else ACTIVITY_OPTIONS_FEMALE
        keyboard = [[KeyboardButton(opt)] for opt in options]
        await update.message.reply_text(
            get_gendered_text(context, "מה רמת הפעילות הגופנית שלך?", "מה רמת הפעילות הגופנית שלך?"),
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
            parse_mode='HTML'
        )
        return ACTIVITY

async def get_body_fat_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message and update.message.text:
        value = update.message.text.strip()
        try:
            context.user_data['body_fat_target'] = float(value)
        except Exception:
            await update.message.reply_text('אנא הזן ערך מספרי ליעד אחוזי שומן.', parse_mode='HTML')
            return BODY_FAT_TARGET
        gender = context.user_data.get('gender', 'זכר')
        options = ACTIVITY_OPTIONS_MALE if gender == 'זכר' else ACTIVITY_OPTIONS_FEMALE
        keyboard = [[KeyboardButton(opt)] for opt in options]
        await update.message.reply_text(
            get_gendered_text(context, "מה רמת הפעילות הגופנית שלך?", "מה רמת הפעילות הגופנית שלך?"),
            reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
            parse_mode='HTML'
        )
        return ACTIVITY

async def get_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message and update.message.text:
        if not update.message or not update.message.text:
            return ACTIVITY
        activity = update.message.text.strip()
        gender = context.user_data.get('gender', 'זכר')
        options = ACTIVITY_OPTIONS_MALE if gender == 'זכר' else ACTIVITY_OPTIONS_FEMALE
        if activity not in options:
            keyboard = [[KeyboardButton(opt)] for opt in options]
            # הודעה מגדרית ברורה
            await update.message.reply_text(get_gendered_text(context, "בחר רמת פעילות מהתפריט למטה:", "בחרי רמת פעילות מהתפריט למטה:", "בחר/י רמת פעילות מהתפריט למטה:"), reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True), parse_mode='HTML')
            return ACTIVITY
        context.user_data['activity'] = activity
        keyboard = [[KeyboardButton(opt)] for opt in DIET_OPTIONS]
        keyboard.append([KeyboardButton(get_gendered_text(context, "המשך", "המשיכי"))])
        context.user_data['diet'] = []
        await update.message.reply_text(get_gendered_text(context, "מהן העדפות התזונה שלך? ניתן לבחור כמה אפשרויות. לסיום לחצ/י 'המשך'.", "מהן העדפות התזונה שלך? ניתן לבחור כמה אפשרויות. לסיום לחצי 'המשיכי'."), reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True), parse_mode='HTML')
        return DIET

async def get_diet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message and update.message.text:
        if 'diet' not in context.user_data:
            context.user_data['diet'] = []
        if not update.message or not update.message.text:
            return DIET
        choice = update.message.text.strip()
        skip_btn = get_gendered_text(context, "דלג", "דלגי")
        continue_btn = get_gendered_text(context, "המשך", "המשיכי")
        # --- לחיצה על המשך ---
        if choice == continue_btn:
            if not context.user_data['diet']:
                context.user_data['diet'] = ["ללא העדפה"]
            gender = context.user_data.get('gender', 'זכר')
            keyboard = [[KeyboardButton(opt)] for opt in ALLERGY_OPTIONS]
            keyboard.append([KeyboardButton(skip_btn)])
            await update.message.reply_text(
                get_gendered_text(context, f"יש לך אלרגיות? אם אין, לחצ/י '{skip_btn}'.", f"יש לך אלרגיות? אם אין, לחצי '{skip_btn}'."),
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
                parse_mode='HTML'
            )
            return ALLERGIES
        # --- לחיצה על אפשרות עם ❌ (הסרה) ---
        if choice.endswith(' ❌'):
            real_choice = choice.replace(' ❌', '')
            if real_choice in context.user_data['diet']:
                context.user_data['diet'].remove(real_choice)
            # עדכון מקלדת
            selected = set(context.user_data['diet'])
            keyboard = []
            for opt in DIET_OPTIONS:
                if opt in selected:
                    keyboard.append([KeyboardButton(f"{opt} ❌")])
                else:
                    keyboard.append([KeyboardButton(opt)])
            keyboard.append([KeyboardButton(continue_btn)])
            await update.message.reply_text(
                get_gendered_text(context, f"נבחר: {', '.join(context.user_data['diet']) if context.user_data['diet'] else 'ללא'}", f"נבחרו: {', '.join(context.user_data['diet']) if context.user_data['diet'] else 'ללא'}"),
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
                parse_mode='HTML'
            )
            return DIET
        # --- לחיצה על אפשרות רגילה (הוספה) ---
        if choice in DIET_OPTIONS and choice not in context.user_data['diet']:
            context.user_data['diet'].append(choice)
        # עדכון מקלדת
        selected = set(context.user_data['diet'])
        keyboard = []
        for opt in DIET_OPTIONS:
            if opt in selected:
                keyboard.append([KeyboardButton(f"{opt} ❌")])
            else:
                keyboard.append([KeyboardButton(opt)])
        keyboard.append([KeyboardButton(continue_btn)])
        await update.message.reply_text(
            get_gendered_text(context, f"נבחר: {', '.join(context.user_data['diet'])}", f"נבחרו: {', '.join(context.user_data['diet'])}"),
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode='HTML'
        )
        return DIET
        # --- טיפול בבחירה לא חוקית ---
        if choice not in DIET_OPTIONS and choice != continue_btn:
            keyboard = []
            for opt in DIET_OPTIONS:
                if opt in context.user_data['diet']:
                    keyboard.append([KeyboardButton(f"{opt} ❌")])
                else:
                    keyboard.append([KeyboardButton(opt)])
            keyboard.append([KeyboardButton(continue_btn)])
            await update.message.reply_text(get_gendered_text(context, "בחר העדפת תזונה מהתפריט למטה:", "בחרי העדפת תזונה מהתפריט למטה:", "בחר/י העדפת תזונה מהתפריט למטה:"), reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True), parse_mode='HTML')
            return DIET

def calculate_bmr(gender: str, age: int, height: int, weight: int, activity: str, goal: str) -> int:
    """
    חישוב BMR ותקציב קלורי יומי לפי Harris-Benedict, כולל התאמה למטרה.
    """
    # Harris-Benedict BMR
    if gender == "זכר":
        bmr = 88.362 + (13.397 * weight) + (4.799 * height) - (5.677 * age)
    elif gender == "נקבה":
        bmr = 447.593 + (9.247 * weight) + (3.098 * height) - (4.330 * age)
    else:
        # ממוצע בין זכר לנקבה
        bmr = ((88.362 + (13.397 * weight) + (4.799 * height) - (5.677 * age)) +
               (447.593 + (9.247 * weight) + (3.098 * height) - (4.330 * age))) / 2
    # Activity factor
    activity_map = {
        "לא פעיל": 1.2,
        "קל": 1.375,
        "בינוני": 1.55,
        "גבוה": 1.725
    }
    activity_factor = activity_map.get(activity, 1.2)
    calorie_budget = bmr * activity_factor
    # התאמה למטרה
    if "ירידה" in goal:
        calorie_budget -= 350
    elif "עלייה" in goal:
        calorie_budget += 350
    # עיגול
    return int(calorie_budget)

async def get_allergies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if 'allergies' not in context.user_data:
        context.user_data['allergies'] = []
    if not update.message or not update.message.text:
        return ALLERGIES
    choice = update.message.text.strip()
    skip_btn = get_gendered_text(context, "דלג", "דלגי")
    # --- לחיצה על דלג ---
    if choice == skip_btn:
        if not context.user_data['allergies']:
            context.user_data['allergies'] = ["אין"]
        # חישוב BMR ותקציב קלורי
        user = context.user_data
        user['calorie_budget'] = calculate_bmr(
            gender=user['gender'],
            age=user['age'],
            height=user['height'],
            weight=user['weight'],
            activity=user['activity'],
            goal=user['goal']
        )
        # שמירה ל-JSON
        user_id = update.effective_user.id if update.effective_user else None
        if user_id:
            save_user(user_id, user)
        # מעבר לשאלה האם לקבל תפריט יומי מותאם
        return await after_questionnaire(update, context)
    # --- לחיצה על אפשרות עם ❌ (הסרה) ---
    if choice.endswith(' ❌'):
        real_choice = choice.replace(' ❌', '')
        if real_choice in context.user_data['allergies']:
            context.user_data['allergies'].remove(real_choice)
        # עדכון מקלדת
        selected = set(context.user_data['allergies'])
        keyboard = []
        for opt in ALLERGY_OPTIONS:
            if opt in selected:
                keyboard.append([KeyboardButton(f"{opt} ❌")])
            else:
                keyboard.append([KeyboardButton(opt)])
        keyboard.append([KeyboardButton(skip_btn)])
        await update.message.reply_text(
            get_gendered_text(context, f"נבחר: {', '.join(context.user_data['allergies']) if context.user_data['allergies'] else 'אין'}", f"נבחרו: {', '.join(context.user_data['allergies']) if context.user_data['allergies'] else 'אין'}"),
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode='HTML'
        )
        return ALLERGIES
    # --- לחיצה על אפשרות רגילה (הוספה) ---
    if choice in ALLERGY_OPTIONS and choice not in context.user_data['allergies']:
        context.user_data['allergies'].append(choice)
    # עדכון מקלדת
    selected = set(context.user_data['allergies'])
    keyboard = []
    for opt in ALLERGY_OPTIONS:
        if opt in selected:
            keyboard.append([KeyboardButton(f"{opt} ❌")])
        else:
            keyboard.append([KeyboardButton(opt)])
    keyboard.append([KeyboardButton(skip_btn)])
    await update.message.reply_text(
        get_gendered_text(context, f"נבחר: {', '.join(context.user_data['allergies'])}", f"נבחרו: {', '.join(context.user_data['allergies'])}"),
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        parse_mode='HTML'
    )
    return ALLERGIES
    # --- טיפול בבחירה לא חוקית ---
    if choice not in ALLERGY_OPTIONS and choice != skip_btn:
        keyboard = []
        for opt in ALLERGY_OPTIONS:
            if opt in context.user_data['allergies']:
                keyboard.append([KeyboardButton(f"{opt} ❌")])
            else:
                keyboard.append([KeyboardButton(opt)])
        keyboard.append([KeyboardButton(skip_btn)])
        await update.message.reply_text(get_gendered_text(context, "בחר אלרגיה מהתפריט למטה:", "בחרי אלרגיה מהתפריט למטה:"), reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True), parse_mode='HTML')
        return ALLERGIES

async def send_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, new_menu: bool = False):
    user = context.user_data
    # פרומפט משופר ל-GPT
    prompt = (
        f"המשתמש/ת: {user.get('name','')}, גיל: {user.get('age','')}, מגדר: {'זכר' if user.get('gender','male')=='male' else 'נקבה'}, גובה: {user.get('height','')}, משקל: {user.get('weight','')}, מטרה: {user.get('goal','')}, רמת פעילות: {user.get('activity','')}, העדפות תזונה: {', '.join(user.get('diet', []))}, אלרגיות: {user.get('allergies') or 'אין'}.\n"
        "בנה לי תפריט יומי מאוזן ובריא, ישראלי, פשוט, עם 5–6 ארוחות (בוקר, ביניים, צהריים, ביניים, ערב, קינוח רשות). \n"
        "השתמש בעברית יומיומית, פשוטה וברורה בלבד. אל תשתמש במילים לא שגרתיות, תיאורים פיוטיים, או מנות לא הגיוניות. \n"
        "הצג דוגמאות אמיתיות בלבד, כמו: חביתה, גבינה, יוגורט, עוף, אורז, ירקות, פירות, אגוזים. \n"
        "הימנע מתרגום מילולי מאנגלית, אל תשתמש במנות מוזרות או מומצאות. \n"
        "הקפד על מגדר נכון, סדר ארוחות, כמויות סבירות, והימנע מחזרות. \n"
        "בכל ארוחה עיקרית יהיה חלבון, בכל יום לפחות 2–3 מנות ירק, 1–2 מנות פרי, ודגנים מלאים. \n"
        "אחרי כל ארוחה (בוקר, ביניים, צהריים, ערב, קינוח), כתוב בסוגריים הערכה של קלוריות, חלבון, פחמימות, שומן. \n"
        "אם אינך בטוח – אל תמציא. \n"
        f"הנחיה מגדרית: כתוב את כל ההנחיות בלשון {user.get('gender','זכר')}."
    )
    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    menu_text = response.choices[0].message.content.strip() if response and response.choices and response.choices[0].message and response.choices[0].message.content else ''
    user['menu'] = menu_text
    user['eaten_today'] = []
    user['remaining_calories'] = user.get('calorie_budget', 1800)
    if update.message:
        calorie_budget = user.get('calorie_budget', 1800)
        keyboard = [
            [KeyboardButton('להרכבת ארוחה לפי מה שיש בבית')],
            [KeyboardButton('מה אכלתי היום')],
            [KeyboardButton('📊 דוחות')],
            [KeyboardButton('סיימתי')]
        ]
        await update.message.reply_text(f"<b>התקציב היומי שלך: {calorie_budget} קלוריות</b>\n\n{menu_text}", parse_mode='HTML', reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        # המלצת שתייה יומית בליטרים
        weight = user.get('weight', 70)
        min_l = round(weight * 30 / 1000, 1)
        max_l = round(weight * 35 / 1000, 1)
        min_cups = round((weight * 30) / 240)
        max_cups = round((weight * 35) / 240)
        await update.message.reply_text(f"<b>המלצת שתייה להיום:</b> {min_l}–{max_l} ליטר מים (כ-{min_cups}–{max_cups} כוסות)", parse_mode='HTML')
    return EATEN

async def show_daily_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton('מה אכלתי')],
        [KeyboardButton('סיימתי')],
        [KeyboardButton('עריכה')]
    ]
    user = context.user_data if context.user_data is not None else {}
    gender = user.get('gender', 'male')
    action_text = GENDERED_ACTION['female'] if gender == 'female' else GENDERED_ACTION['male']
    if update.message:
        await update.message.reply_text(
            action_text,
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode='HTML'
        )
    return DAILY

async def daily_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("רגע, בונה עבורך תפריט...")
    if update.message and update.message.text:
        if not update.message or not update.message.text:
            return DAILY
        choice = update.message.text.strip()
        if choice == 'סיימתי':
            await send_summary(update, context)
            return SCHEDULE
        else:
            return await eaten(update, context)

# --- רשימת כפתורי מערכת ---
SYSTEM_BUTTONS = [
    'להרכבת ארוחה לפי מה שיש בבית',
    'מה אכלתי היום',
    'סיימתי',
    'לקבל תפריט יומי',
    'לקבלת תפריט יומי',
    'להרכבת ארוחה נוספת לפי מה שיש בבית',
    'מה אכלתי היום?',
    'עריכה'
]

# --- המרת כוכביות ל-HTML (בולד/נטוי) ---
def markdown_to_html(text):
    # בולד: **טקסט** או *טקסט* => <b>טקסט</b>
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.*?)\*', r'<b>\1</b>', text)
    # נטוי: __טקסט__ או _טקסט_ => <i>טקסט</i>
    text = re.sub(r'__(.*?)__', r'<i>\1</i>', text)
    text = re.sub(r'_(.*?)_', r'<i>\1</i>', text)
    return text

# --- עדכון eaten ---
async def eaten(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    import re
    if update.message and update.message.text:
        if not update.message or not update.message.text:
            return DAILY
        eaten_text = strip_html_tags(update.message.text.strip())
        # לוג ל-Google Sheets
        if eaten_text == 'מה אכלתי היום':
            await update.message.reply_text('מה אכלת היום? להזין עם פסיקים.', parse_mode='HTML')
            return DAILY
        # החרגת כפתורי מערכת
        if eaten_text in SYSTEM_BUTTONS:
            return DAILY
        # זיהוי שאלה על מאכל
        question_starts = ("האם", "אפשר", "מותר", "כמה", "להוסיף")
        # --- תמיכה בשאלה 'מה אני יכולה/יכול לאכול עכשיו?' ---
        if eaten_text in ["מה אני יכולה לאכול עכשיו?", "מה אני יכול לאכול עכשיו?", "מה אפשר לאכול עכשיו?", "מה כדאי לאכול עכשיו?"]:
            user = context.user_data if context.user_data is not None else {}
            calorie_budget = user.get('calorie_budget', 0)
            total_eaten = sum(e['calories'] for e in user.get('eaten_today', []))
            remaining = calorie_budget - total_eaten
            diet = ', '.join(user.get('diet', []))
            allergies = ', '.join(user.get('allergies', []))
            menu = user.get('menu', '')
            prompt = (
                f"המשתמשת שואלת: מה אני יכולה לאכול עכשיו?\n"
                f"העדפות תזונה: {diet}\n"
                f"אלרגיות: {allergies}\n"
                f"מה שנאכל היום: {', '.join(clean_desc(e['desc']) for e in user.get('eaten_today', []))}\n"
                f"תקציב קלורי יומי: {calorie_budget}, נשארו: {remaining} קלוריות\n"
                f"תפריט מוצע: {menu}\n"
                f"המלץ/י על מאכלים שמתאימים להעדפות, לתקציב, למטרות, ולמה שנאכל עד כה. אל תמליץ/י על מאכלים שכבר נאכלו או שאינם בהעדפות. הצג המלצה מגדרית, מסודרת, ב-HTML בלבד, עם בולד, רשימות, כותרות, והסבר קצר. אל תשתמש/י ב-Markdown."
            )
            response = await openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}]
            )
            rec = response.choices[0].message.content.strip() if response and response.choices and response.choices[0].message and response.choices[0].message.content else ''
            await update.message.reply_text(rec, parse_mode='HTML')
            return DAILY
        if eaten_text.endswith('?') or any(eaten_text.startswith(q) for q in question_starts):
            # חילוץ שם המאכל מהשאלה
            match = re.search(r'לאכול ([^?]*)', eaten_text)
            food = match.group(1).strip() if match else None
            if not food:
                # fallback: כל המילה האחרונה לפני סימן שאלה
                food = eaten_text.replace('?', '').split()[-1]
            # שליחת כל המידע לצ'אט
            user = context.user_data if context.user_data is not None else {}
            calorie_budget = user.get('calorie_budget', 0)
            total_eaten = sum(e['calories'] for e in user.get('eaten_today', []))
            remaining = calorie_budget - total_eaten
            diet = ', '.join(user.get('diet', []))
            allergies = ', '.join(user.get('allergies', []))
            menu = user.get('menu', '')
            eaten_list = ', '.join(clean_desc(e['desc']) for e in user.get('eaten_today', []))
            prompt = (
                f"המשתמשת שואלת: {eaten_text}\n"
                f"העדפות תזונה: {diet}\n"
                f"אלרגיות: {allergies}\n"
                f"מה שנאכל היום: {eaten_list}\n"
                f"תקציב קלורי יומי: {calorie_budget}, נשארו: {remaining} קלוריות\n"
                f"מטרה: {user.get('goal', '')}\n"
                f"תפריט מוצע: {menu}\n"
                f"האם אפשר לאכול {food}? ענה/י תשובה תזונתית אמיתית, בהתחשב בכל הנתונים, כולל תקציב, העדפות, אלרגיות, מטרות, ומה שכבר נאכל. הצג המלצה מגדרית, מסודרת, ב-HTML בלבד, עם בולד, רשימות, כותרות, והסבר קצר. אל תשתמש/י ב-Markdown."
            )
            response = await openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}]
            )
            answer = response.choices[0].message.content.strip() if response and response.choices and response.choices[0].message and response.choices[0].message.content else ''
            await update.message.reply_text(answer, parse_mode='HTML')
            return DAILY
        if context.user_data is None:
            context.user_data = {}
        if 'eaten_today' not in context.user_data:
            context.user_data['eaten_today'] = []
        user = context.user_data
        meal_text = clean_meal_text(update.message.text)
        # 1. חיזוק הפרומפט ל-GPT
        calorie_prompt = (
            f"עבור הארוחה הבאה: {meal_text}\n"
            "פירוט כל פריט בשורה נפרדת: שם, כמות (אם יש), קלוריות, חלבון (גרם).\n"
            "בסוף, כתוב שורה מסכמת: סה\"כ קלוריות, סה\"כ חלבון.\n"
            "אל תוסיף טקסט נוסף, רק טבלה פשוטה. אם יש שתייה מתוקה (קולה, מיץ, תה ממותק, וכו'), כלול גם אותה.\n"
            "אם התוצאה נמוכה מ-50 קלוריות, כנראה יש טעות – נסה להעריך שוב ולהחזיר תשובה ריאלית בלבד.\n"
            "דוגמה:\n"
            "קלט: 2 ביצים, 2 פרוסות לחם, כף חמאה, סלט ירקות, קפה עם חלב סויה, 2 קוביות חלווה.\n"
            "פלט:\n"
            "ביצים (2): 140 קלוריות, 12 גרם חלבון\n"
            "לחם לבן (2 פרוסות): 140 קלוריות, 4 גרם חלבון\n"
            "חמאה (כף): 100 קלוריות, 0 גרם חלבון\n"
            "סלט ירקות: 30 קלוריות, 1 גרם חלבון\n"
            "קפה עם חלב סויה: 50 קלוריות, 2 גרם חלבון\n"
            "חלווה (2 קוביות): 60 קלוריות, 1 גרם חלבון\n"
            "סה\"כ: 520 קלוריות, 20 גרם חלבון"
        )
        # 2. שלח הודעת טעינה אחת בלבד ב-eaten
        await update.message.reply_text("רגע, מחשב... 🤖")
        # שלח ל-GPT את calorie_prompt
        calorie_response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": calorie_prompt}]
        )
        calorie_str = calorie_response.choices[0].message.content.strip() if calorie_response and calorie_response.choices and calorie_response.choices[0].message and calorie_response.choices[0].message.content else ''
        import re
        match = re.search(r"(\d+)", calorie_str)
        calories = int(match.group(1)) if match else 0
        # 3. אם החישוב נכשל, שלח גם הודעה עם הקלוריות שנותרו (לפי מה שידוע כרגע) ותבצע לה pin
        if calories < 50:
            retry_prompt = calorie_prompt + "\nשים לב: התוצאה שחישבת נמוכה מ-50 קלוריות, כנראה יש טעות. אנא הערך מחדש והחזר תשובה ריאלית בלבד."
            retry_response = await openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": retry_prompt}]
            )
            retry_str = retry_response.choices[0].message.content.strip() if retry_response and retry_response.choices and retry_response.choices[0].message and retry_response.choices[0].message.content else ''
            match_retry = re.search(r"(\d+)", retry_str)
            retry_calories = int(match_retry.group(1)) if match_retry else 0
            if retry_calories >= 50:
                calories = retry_calories
                calorie_str = retry_str
            else:
                await update.message.reply_text("⚠️ החישוב לא נראה הגיוני. נסה לנסח שוב או לפרט יותר את מה שאכלת.")
                # שלח הודעה עם הקלוריות שנותרו ותבצע לה pin
                total_eaten = sum(e['calories'] for e in user['eaten_today'])
                remaining = user.get('calorie_budget', 0) - total_eaten
                try:
                    await context.bot.unpin_all_chat_messages(chat_id=update.effective_chat.id)
                except Exception:
                    pass
                msg = await update.message.reply_text(f"נשארו לך: {remaining} קלוריות להיום.")
                try:
                    await context.bot.pin_chat_message(chat_id=update.effective_chat.id, message_id=msg.message_id)
                except Exception:
                    pass
                return DAILY
        user['eaten_today'].append({'desc': eaten_text, 'calories': calories})
        total_eaten = sum(e['calories'] for e in user['eaten_today'])
        remaining = user.get('calorie_budget', 0) - total_eaten
        user['remaining_calories'] = remaining
        summary = f"<b>הוספת:</b> {clean_desc(eaten_text)} (<b>{calories}</b> קלוריות)\n<b>סה\"כ נאכל היום:</b> <b>{total_eaten}</b> קלוריות\n<b>נשארו לך:</b> <b>{remaining}</b> קלוריות להיום."
        summary = markdown_to_html(summary)
        await update.message.reply_text(summary, parse_mode='HTML')
        # 3. נסה להצמיד (pin) את ההודעה עם 'נשארו לך: ... קלוריות להיום' (אם אפשרי)
        # אחרי שליחת ההודעה עם הקלוריות שנותרו:
        msg = await update.message.reply_text(f"נשארו לך: {remaining} קלוריות להיום.")
        try:
            await context.bot.pin_chat_message(chat_id=update.effective_chat.id, message_id=msg.message_id)
        except Exception:
            pass
        # לא לשאול שוב 'מה אכלת היום?'. להציע רק 'סיימתי'.
        keyboard = [
            [KeyboardButton('סיימתי')]
        ]
        gender = user.get('gender', 'זכר')
        action_text = GENDERED_ACTION.get(gender, GENDERED_ACTION['אחר'])
        await update.message.reply_text(action_text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True), parse_mode='HTML')
        return DAILY

async def handle_daily_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """טיפול בבחירות בתפריט היומי"""
    if not update.message or not update.message.text:
        return DAILY
    
    choice = update.message.text.strip()
    
    if choice == '📊 דוחות':
        # הצגת תפריט דוחות
        keyboard = [
            [InlineKeyboardButton("📅 שבוע אחרון", callback_data="report_weekly")],
            [InlineKeyboardButton("📊 חודש אחרון", callback_data="report_monthly")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📊 <b>בחר/י סוג דוח:</b>",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
        # החזרת מקלדת רגילה
        keyboard = [
            [KeyboardButton('מה אכלתי היום')],
            [KeyboardButton('📊 דוחות')],
            [KeyboardButton('סיימתי')]
        ]
        await update.message.reply_text(
            "בחר/י פעולה:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return DAILY
    
    elif choice == 'סיימתי':
        await send_summary(update, context)
        return SCHEDULE
    
    else:
        # טיפול בדיווח אכילה
        return await eaten(update, context)

# --- עיצוב סיכום יומי ---
async def send_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = context.user_data if context.user_data is not None else {}
    if 'eaten_today' in user and user['eaten_today']:
        eaten_lines = [f"• <b>{clean_desc(e['desc'])}</b> (<b>{e['calories']}</b> קלוריות)" for e in user['eaten_today']]
        eaten = '\n'.join(eaten_lines)
        total_eaten = sum(e['calories'] for e in user['eaten_today'])
    else:
        eaten = 'לא דווח'
        total_eaten = 0
    remaining = user.get('calorie_budget', 0) - total_eaten
    summary = f"<b>סיכום יומי:</b>\n{eaten}\n\n<b>סה\"כ נאכל:</b> <b>{total_eaten}</b> קלוריות\n<b>נשארו:</b> <b>{remaining}</b> קלוריות להיום."
    summary = markdown_to_html(summary)
    await update.message.reply_text(summary, parse_mode='HTML')
    
    # --- שמירה לבסיס הנתונים ---
    user_id = update.effective_user.id if update.effective_user else None
    if user_id and total_eaten > 0:
        try:
            # חישוב ממוצעי מאקרו-נוטריאנטים (הערכה)
            meals_list = [clean_desc(e['desc']) for e in user['eaten_today']]
            
            # הערכה פשוטה של חלבון, שומן, פחמימות (15%, 30%, 55% מהקלוריות)
            estimated_protein = (total_eaten * 0.15) / 4  # 4 קלוריות לגרם חלבון
            estimated_fat = (total_eaten * 0.30) / 9      # 9 קלוריות לגרם שומן
            estimated_carbs = (total_eaten * 0.55) / 4    # 4 קלוריות לגרם פחמימות
            
            # שמירה לבסיס הנתונים
            save_daily_entry(
                user_id=user_id,
                date=datetime.datetime.now().strftime('%Y-%m-%d'),
                calories=total_eaten,
                protein=estimated_protein,
                fat=estimated_fat,
                carbs=estimated_carbs,
                meals=meals_list,
                goal=user.get('goal', '')
            )
            
            # הודעה על שמירה
            await update.message.reply_text("✅ הנתונים נשמרו בהצלחה! אפשר לראות דוח שבועי עם /report", parse_mode='HTML')
            
        except Exception as e:
            logging.error(f"שגיאה בשמירה לבסיס הנתונים: {e}")
            await update.message.reply_text("⚠️ לא הצלחתי לשמור את הנתונים, אבל הסיכום נשאר.", parse_mode='HTML')
    
    # המלצה דינמית למחר
    learning = learning_logic(context)
    await update.message.reply_text(f"<b>המלצה למחר:</b>\n{learning}", parse_mode='HTML')
    # המלצת מים
    water = water_recommendation(context)
    await update.message.reply_text(water, parse_mode='HTML')
    # איפוס הארוחות ליום הבא
    user['eaten_today'] = []
    user['remaining_calories'] = user.get('calorie_budget', 0)
    # שאלה על תזמון תפריט למחר
    times = [f"{h:02d}:00" for h in range(7, 13)]
    keyboard = [[KeyboardButton(t)] for t in times]
    await update.message.reply_text(
        get_gendered_text(context, 'מתי לשלוח לך את התפריט היומי למחר?', 'מתי לשלוח לך את התפריט היומי למחר?'),
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
        parse_mode='HTML'
    )
    return SCHEDULE

# --- תזמון תפריט ליום הבא (שלד) ---
async def schedule_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return SCHEDULE
    time = update.message.text.strip()
    if context.user_data is None:
        context.user_data = {}
    context.user_data['schedule_time'] = time
    user_id = update.effective_user.id if update.effective_user else None
    if user_id:
        save_user(user_id, context.user_data)
    await update.message.reply_text(
        get_gendered_text(context, f'מעולה! אשלח לך תפריט חדש כל יום בשעה {time}.', f'מעולה! אשלח לך תפריט חדש כל יום בשעה {time}.'),
        reply_markup=ReplyKeyboardRemove(),
        parse_mode='HTML'
    )
    return ConversationHandler.END

# --- בדיקת חריגה: אפשר קינוח? ---
async def check_dessert_permission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = context.user_data
    rem = user.get('remaining_calories', user.get('calorie_budget', 0))
    msg = get_gendered_text(
        context,
        f"נותרו לך {rem} קלוריות. אפשר קינוח! תתפנק 🙂" if rem > 150 else "לא מומלץ קינוח כרגע. נשארו מעט קלוריות.",
        f"נותרו לך {rem} קלוריות. אפשר קינוח! תתפנקי 🙂" if rem > 150 else "לא מומלץ קינוח כרגע. נשארו מעט קלוריות."
    )
    await update.message.reply_text(msg, parse_mode='HTML')
    return DAILY

# --- המלצה לצריכת מים ---
def water_recommendation(context) -> str:
    user = context.user_data
    weight = user.get('weight', 70)
    min_l = round(weight * 30 / 1000, 1)
    max_l = round(weight * 35 / 1000, 1)
    min_cups = round((weight * 30) / 240)
    max_cups = round((weight * 35) / 240)
    return get_gendered_text(
        context,
        f"מומלץ לשתות {min_l}–{max_l} ליטר מים (כ-{min_cups}–{max_cups} כוסות) ביום.",
        f"מומלץ לשתות {min_l}–{max_l} ליטר מים (כ-{min_cups}–{max_cups} כוסות) ביום."
    )

# --- לוגיקת למידה (הערות לתפריט הבא) ---
def learning_logic(context) -> str:
    user = context.user_data
    notes = []
    eaten = '\n'.join(e['desc'] for e in user.get('eaten_today', []))
    # בדיקת קבוצות מזון עיקריות
    protein_keywords = ['ביצה', 'טונה', 'עוף', 'בשר', 'גבינה', 'יוגורט', 'קוטג', 'דג', 'קטניות', 'עדשים', 'טופו', 'סויה']
    veg_keywords = ['ירק', 'סלט', 'עגבניה', 'מלפפון', 'גזר', 'חסה', 'פלפל', 'ברוקולי', 'קישוא', 'קולורבי', 'תרד', 'פטרוזיליה', 'פטריה']
    carb_keywords = ['לחם', 'פיתה', 'אורז', 'פסטה', 'קוסקוס', 'תפוח אדמה', 'בטטה', 'דגן', 'שיבולת', 'גרנולה', 'קוואקר']
    found_protein = any(any(word in e for word in protein_keywords) for e in eaten.split('\n'))
    found_veg = any(any(word in e for word in veg_keywords) for e in eaten.split('\n'))
    found_carb = any(any(word in e for word in carb_keywords) for e in eaten.split('\n'))
    if not found_protein:
        notes.append(get_gendered_text(context, "מחר כדאי לשלב חלבון איכותי (למשל: ביצה, גבינה, יוגורט, עוף, טונה, קטניות).", "מחר כדאי לשלב חלבון איכותי (למשל: ביצה, גבינה, יוגורט, עוף, טונה, קטניות)."))
    if not found_veg:
        notes.append(get_gendered_text(context, "מחר כדאי לשלב ירקות טריים או מבושלים.", "מחר כדאי לשלב ירקות טריים או מבושלים."))
    if not found_carb:
        notes.append(get_gendered_text(context, "מחר כדאי לשלב דגנים מלאים או פחמימה מורכבת (אורז, פסטה, לחם מלא, קוואקר).", "מחר כדאי לשלב דגנים מלאים או פחמימה מורכבת (אורז, פסטה, לחם מלא, קוואקר)."))
    if not notes:
        notes.append(get_gendered_text(context, "כל הכבוד על איזון! המשיכי כך.", "כל הכבוד על איזון! המשך כך."))
    return '\n'.join(notes)

# --- אחרי השאלון: האם לקבל תפריט יומי מותאם? ---
async def after_questionnaire(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await ask_water_reminder_opt_in(update, context)
    return EDIT

async def ask_water_reminder_opt_in(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton('כן, אשמח!'), KeyboardButton('לא, תודה')]]
    await update.message.reply_text(
        get_gendered_text(context, 'האם תרצה לקבל תזכורת לשתות מים כל שעה וחצי?', 'האם תרצי לקבל תזכורת לשתות מים כל שעה וחצי?'),
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
        parse_mode='HTML'
    )
    return EDIT

async def set_water_reminder_opt_in(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        return EDIT
    choice = update.message.text.strip()
    user_id = update.effective_user.id if update.effective_user else None
    if choice == 'כן, אשמח!':
        context.user_data['water_reminder_opt_in'] = True
        context.user_data['water_reminder_active'] = True
        await update.message.reply_text(get_gendered_text(context, 'מעולה! אזכיר לך לשתות מים כל שעה וחצי עד שתסיים/י את היום.', 'מעולה! אזכיר לך לשתות מים כל שעה וחצי עד שתסיימי את היום.'), parse_mode='HTML')
        if user_id:
            save_user(user_id, context.user_data)
        asyncio.create_task(start_water_reminder_loop_with_buttons(update, context))
    else:
        context.user_data['water_reminder_opt_in'] = False
        context.user_data['water_reminder_active'] = False
        await update.message.reply_text(get_gendered_text(context, 'אין בעיה! אפשר להפעיל תזכורות מים בכל שלב.', 'אין בעיה! אפשר להפעיל תזכורות מים בכל שלב.'), parse_mode='HTML')
        if user_id:
            save_user(user_id, context.user_data)
    # אחרי תשובה על מים – שואלים מה תרצי לעשות
    keyboard = [
        [
            KeyboardButton(get_gendered_text(context, 'לקבל תפריט יומי', 'לקבל תפריט יומי')),
            KeyboardButton(get_gendered_text(context, 'רק לעקוב אחרי הארוחות', 'רק לעקוב אחרי הארוחות'))
        ],
        [
            KeyboardButton(get_gendered_text(context, 'לקבל תפריט/ארוחה לפי מוצרים בבית', 'לקבל תפריט/ארוחה לפי מוצרים בבית'))
        ]
    ]
    await update.message.reply_text(
        get_gendered_text(context, 'מה תרצה לעשות כעת?', 'מה תרצי לעשות כעת?'),
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
        parse_mode='HTML'
    )
    return MENU

async def start_water_reminder_loop_with_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    if context.user_data is None:
        context.user_data = {}
    while context.user_data.get('water_reminder_opt_in') and context.user_data.get('water_reminder_active'):
        await asyncio.sleep(90 * 60)  # שעה וחצי
        if not context.user_data.get('water_reminder_opt_in') or not context.user_data.get('water_reminder_active'):
            break
        try:
            if update.message:
                await send_water_reminder(update, context)
        except Exception as e:
            logger.error(f'Water reminder error: {e}')
        if user_id:
            save_user(user_id, context.user_data)

async def send_water_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton('שתיתי, תודה')],
        [KeyboardButton('תזכיר לי בעוד עשר דקות')],
        [KeyboardButton('תפסיק להזכיר לי לשתות מים')]
    ]
    await update.message.reply_text(
        get_gendered_text(context, 'תזכורת: הגיע הזמן לשתות מים! 🥤', 'תזכורת: הגיע הזמן לשתות מים! 🥤'),
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
        parse_mode='HTML'
    )

async def remind_in_10_minutes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('בסדר! אזכיר לך לשתות מים בעוד 10 דקות.', reply_markup=ReplyKeyboardRemove(), parse_mode='HTML')
    await asyncio.sleep(10 * 60)
    await send_water_reminder(update, context)

async def cancel_water_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ביטול תזכורות מים"""
    if context.user_data is None:
        context.user_data = {}
    context.user_data['water_reminder_opt_in'] = False
    context.user_data['water_reminder_active'] = False
    user_id = update.effective_user.id if update.effective_user else None
    if user_id:
        save_user(user_id, context.user_data)
    
    await update.message.reply_text(
        get_gendered_text(context, 'בסדר! הפסקתי להזכיר לך לשתות מים. אפשר להפעיל שוב בכל שלב.', 'בסדר! הפסקתי להזכיר לך לשתות מים. אפשר להפעיל שוב בכל שלב.'),
        reply_markup=ReplyKeyboardRemove(),
        parse_mode='HTML'
    )

async def handle_free_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """מטפל בכל קלט טקסט חופשי - מזהה אם זה שאלה או דיווח אכילה"""
    if not update.message or not update.message.text:
        return
    
    user_text = update.message.text.strip()
    
    # לוג כל הודעה ל-Google Sheets
    log_to_sheet({
        'username': update.effective_user.username if update.effective_user else '',
        'user_id': update.effective_user.id if update.effective_user else '',
        'text': user_text,
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'event_type': 'הודעה חופשית'
    })
    
    user_id = update.effective_user.id if update.effective_user else None
    user = context.user_data if context.user_data else {}
    
    # --- זיהוי שאלות על נתונים היסטוריים ---
    historical_indicators = [
        'אתמול', 'שלשום', 'אתמול', 'שלשום', 'לפני', 'יום', 'שבוע', 'חודש',
        'צרכתי', 'אכלתי', 'שתיתי', 'היה לי', 'היתה לי', 'אכל', 'שתה'
    ]
    
    is_historical_query = any(indicator in user_text for indicator in historical_indicators)
    
    if is_historical_query and user_id:
        # ניסיון לחלץ תאריך מהטקסט
        target_date = parse_date_from_text(user_text)
        
        if target_date:
            # שאלה על תאריך ספציפי
            nutrition_data = get_nutrition_by_date(user_id, target_date)
            
            if nutrition_data:
                # חילוץ סוג השאלה
                if 'קלוריות' in user_text or 'צרכתי' in user_text:
                    response = format_date_query_response(nutrition_data, "calories")
                elif 'אכלתי' in user_text or 'אכל' in user_text:
                    response = format_date_query_response(nutrition_data, "meals")
                else:
                    response = format_date_query_response(nutrition_data, "summary")
                
                await update.message.reply_text(response, parse_mode='HTML')
                return
            else:
                await update.message.reply_text(f"❌ לא נמצאו נתונים ל{target_date}.", parse_mode='HTML')
                return
        
        # חיפוש מאכל ספציפי
        meal_keywords = ['המבורגר', 'פיצה', 'סושי', 'פסטה', 'עוף', 'בשר', 'דג', 'סלט', 'תפוח', 'בננה', 'קולה', 'קפה']
        found_meal = None
        for keyword in meal_keywords:
            if keyword.lower() in user_text.lower():
                found_meal = keyword
                break
        
        if found_meal:
            last_occurrence = get_last_occurrence_of_meal(user_id, found_meal)
            if last_occurrence:
                meals_text = ", ".join(last_occurrence['meals'])
                response = f"🍽️ הפעם האחרונה שאכלת {found_meal} הייתה ב{last_occurrence['date']}: {meals_text}"
                await update.message.reply_text(response, parse_mode='HTML')
                return
            else:
                await update.message.reply_text(f"❌ לא נמצאו רשומות של {found_meal} ב-30 הימים האחרונים.", parse_mode='HTML')
                return
    
    # --- זיהוי אם זה נראה כמו דיווח אכילה או שאלה רגילה ---
    eating_indicators = ['אכלתי', 'שתיתי', 'אכלתי', 'שתיתי', 'אכל', 'שתה', 'אכלה', 'שתתה']
    question_indicators = ['?', 'כמה', 'האם', 'אפשר', 'מותר', 'איך', 'מה', 'מתי', 'איפה', 'למה', 'איזה']
    
    is_eating_report = any(indicator in user_text for indicator in eating_indicators)
    is_question = any(indicator in user_text for indicator in question_indicators) or user_text.endswith('?')
    
    # בניית פרומפט ל-GPT
    calorie_budget = user.get('calorie_budget', 1800)
    total_eaten = sum(e['calories'] for e in user.get('eaten_today', []))
    remaining = calorie_budget - total_eaten
    diet = ', '.join(user.get('diet', []))
    allergies = ', '.join(user.get('allergies', []))
    eaten_today = ', '.join([clean_desc(e['desc']) for e in user.get('eaten_today', [])])
    
    if is_eating_report:
        # זה נראה כמו דיווח אכילה - GPT יחשוב קלוריות ויוסיף
        prompt = f"""המשתמש/ת כתב/ה: "{user_text}"

זה נראה כמו דיווח אכילה. אנא:
1. זהה את המאכל/ים
2. חשב/י קלוריות מדויקות (במיוחד למשקאות - קולה, מיץ וכו')
3. הוסף/י את זה למה שנאכל היום
4. הצג/י סיכום: מה נוסף, כמה קלוריות, סה"כ היום, כמה נשארו

מידע על המשתמש/ת:
- תקציב יומי: {calorie_budget} קלוריות
- נאכל היום: {eaten_today}
- נשארו: {remaining} קלוריות
- העדפות תזונה: {diet}
- אלרגיות: {allergies}

הצג תשובה בעברית, עם HTML בלבד (<b>, <i>), בלי Markdown. אל תמציא ערכים - אם אינך בטוח, ציין זאת."""
    else:
        # זה נראה כמו שאלה - GPT יענה על השאלה
        prompt = f"""המשתמש/ת שואל/ת: "{user_text}"

ענה/י על השאלה בהקשר תזונתי. אם השאלה על קלוריות או תזונה - תן/י תשובה מדויקת.
אם השאלה כללית - תן/י תשובה מקצועית ומועילה.

מידע על המשתמש/ת (אם רלוונטי):
- תקציב יומי: {calorie_budget} קלוריות
- נאכל היום: {eaten_today}
- נשארו: {remaining} קלוריות
- העדפות תזונה: {diet}
- אלרגיות: {allergies}

הצג תשובה בעברית, עם HTML בלבד (<b>, <i>), בלי Markdown. אל תמציא ערכים - אם אינך בטוח, ציין זאת."""

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        gpt_response = response.choices[0].message.content.strip() if response and response.choices and response.choices[0].message and response.choices[0].message.content else 'לא הצלחתי לעבד את הבקשה.'
        
        await update.message.reply_text(gpt_response, parse_mode='HTML')
        
        # אם זה היה דיווח אכילה, עדכן את הנתונים
        if is_eating_report:
            # נסה לחלץ קלוריות מהתשובה של GPT
            import re
            calorie_match = re.search(r'(\d+)\s*קלוריות?', gpt_response)
            if calorie_match:
                calories = int(calorie_match.group(1))
                if 'eaten_today' not in user:
                    user['eaten_today'] = []
                user['eaten_today'].append({'desc': user_text, 'calories': calories})
                user['remaining_calories'] = remaining - calories
                
                # שמירה
                if user_id:
                    save_user(user_id, user)
    
    except Exception as e:
        logging.error(f"שגיאה בטיפול בקלט חופשי: {e}")
        await update.message.reply_text("❌ לא הצלחתי לעבד את הבקשה. נסה/י שוב.")

# --- עדכון menu_decision: הסרת כפתור סיימתי מהשאלה הראשונה ---
async def menu_decision(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("רגע, בונה עבורך תפריט...")
    if not update.message or not update.message.text:
        return MENU
    # אם נלחץ כפתור 'להרכבת ארוחה לפי מה שיש בבית' – בקשת פירוט
    if update.message.text.strip() == 'להרכבת ארוחה לפי מה שיש בבית':
        await update.message.reply_text('מה יש בבית? להזין עם פסיקים.', parse_mode='HTML')
        context.user_data['awaiting_products'] = True
        return MENU
    if context.user_data.get('awaiting_products'):
        products_text = update.message.text.strip()
        context.user_data['awaiting_products'] = False
        user = context.user_data
        calorie_budget = user.get('calorie_budget', 1800)
        diet_str = ', '.join(user.get('diet', []))
        prompt = (
            f"יש לי בבית: {products_text}.\n"
            f"העדפות תזונה: {diet_str}.\n"
            f"אל תמליץ/י, אל תציע/י, ואל תכלול/י מאכלים, מוצרים או מרכיבים שאינם מופיעים בהעדפות התזונה שלי, גם לא כהמלצה או דוגמה.\n"
            f"תציע לי מתכון/ים טעימים, בריאים, פשוטים, שמבוססים על מוצר מרכזי מתוך הרשימה (אם יש), ותשתמש בכל מה שיש לי בבית.\n"
            f"אם צריך מוצרים שאין לי – תכתוב אותם בסוף ברשימת קניות.\n"
            f"עבור כל רכיב עיקרי במתכון, כתוב גם את כמות הקלוריות, החלבון, הפחמימות והשומן (לדוג׳: 2 ביצים – 140 קלוריות, 12 גרם חלבון, 0 גרם פחמימות, 10 גרם שומן).\n"
            f"אפשר להניח שיש לי גם שמן זית, שמן קנולה, בצל, גזר, גבינה לבנה, מלח, פלפל.\n"
            f"אל תמציא מנות מוזרות. כתוב בעברית יומיומית, פשוטה וברורה בלבד, בלי תרגום מילולי, בלי מילים מוזרות.\n"
            f"הצג את כל הערכים התזונתיים בצורה מסודרת, עם בולד, ורשימה ממוספרת. בסוף הארוחה, כתוב סיכום: קלוריות, חלבון, פחמימות, שומן. ואז כתוב כמה קלוריות יישארו לי מהתקציב היומי אם אוכל את הארוחה הזו. אם זו הארוחה הראשונה היום, תן המלצה כללית (למשל: היום כדאי לשלב בשר טחון לארוחת צהריים). אם זו לא הארוחה הראשונה, תן המלצה דינמית לפי מה שנאכל עד כה.\n"
            "השתמש/י בתגיות HTML בלבד (למשל <b>, <i>, <u>) להדגשה, ולא בכוכביות או סימנים אחרים. אל תשתמש/י ב-Markdown."
        )
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        menu_text = response.choices[0].message.content.strip() if response and response.choices and response.choices[0].message and response.choices[0].message.content else ''
        user['menu'] = menu_text
        # לא להוסיף את הארוחה הזו ל-eaten_today ולא לחשב קלוריות
        await show_menu_with_keyboard(update, context, menu_text)
        return MENU
    choice = update.message.text.strip()
    opt_menu = get_gendered_text(context, 'לקבל תפריט יומי', 'לקבל תפריט יומי')
    opt_track = get_gendered_text(context, 'רק לעקוב אחרי הארוחות', 'רק לעקוב אחרי הארוחות')
    opt_products = get_gendered_text(context, 'לקבל תפריט/ארוחה לפי מוצרים בבית', 'לקבל תפריט/ארוחה לפי מוצרים בבית')
    user = context.user_data
    if choice == opt_menu:
        menu = await build_daily_menu(user, context)
        user['menu'] = menu
        await show_menu_with_keyboard(update, context, menu)
        return EATEN
    elif choice == opt_products:
        await update.message.reply_text(
            get_gendered_text(context, 'כתוב כאן את רשימת המוצרים שיש לך בבית (לדוג׳: ביצים, גבינה, עגבנייה, טונה, פסטה, חלווה, סלמון, גמבה, מלפפון וכו").',
                                             'כתבי כאן את רשימת המוצרים שיש לך בבית (לדוג׳: ביצים, גבינה, עגבנייה, טונה, פסטה, חלווה, סלמון, גמבה, מלפפון וכו").'),
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='HTML'
        )
        context.user_data['awaiting_products'] = True
        return MENU
    else:
        await update.message.reply_text(
            get_gendered_text(context, f"תקציב הקלוריות היומי שלך: {user['calorie_budget']} קלוריות.", f"תקציב הקלוריות היומי שלך: {user['calorie_budget']} קלוריות."),
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='HTML'
        )
        # כאן לא מוצג כפתור סיימתי בשאלה הראשונה
        await update.message.reply_text(
            get_gendered_text(context, 'מה אכלת היום? כתוב בקצרה (לדוג׳: חביתה, סלט, קוטג׳ 5%).',
                                         'מה אכלת היום? כתבי בקצרה (לדוג׳: חביתה, סלט, קוטג׳ 5%).'),
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='HTML'
        )
        return DAILY

# --- הצגת תפריט יומי אחיד עם תקציב ומקלדת ---
async def show_menu_with_keyboard(update, context, menu_text=None):
    user = context.user_data
    calorie_budget = user.get('calorie_budget', 1800)
    # איפוס יומי
    user['eaten_today'] = []
    user['remaining_calories'] = calorie_budget
    if menu_text is None:
        menu_text = user.get('menu', '')
    msg = f"<b>התקציב היומי שלך: {calorie_budget} קלוריות</b>\n\n{menu_text}"
    keyboard = [
        [KeyboardButton('להרכבת ארוחה לפי מה שיש בבית')],
        [KeyboardButton('מה אכלתי היום')],
        [KeyboardButton('📊 דוחות')],
        [KeyboardButton('סיימתי')]
    ]
    await update.message.reply_text(msg, parse_mode='HTML', reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    # המלצת שתייה יומית בליטרים
    weight = user.get('weight', 70)
    min_l = round(weight * 30 / 1000, 1)
    max_l = round(weight * 35 / 1000, 1)
    min_cups = round((weight * 30) / 240)
    max_cups = round((weight * 35) / 240)
    await update.message.reply_text(f"<b>המלצת שתייה להיום:</b> {min_l}–{max_l} ליטר מים (כ-{min_cups}–{max_cups} כוסות)", parse_mode='HTML')
    # הודעה מגדרית נוספת
    await update.message.reply_text(
        get_gendered_text(
            context,
            'אני כאן אם תרצה להתייעץ אם אפשר לאכול נניח תפוח, או אם תרצה לכתוב לי מה אכלת היום',
            'אני כאן אם תרצי להתייעץ אם אפשר לאכול נניח תפוח, או אם תרצי לכתוב לי מה אכלת היום'
        ),
        parse_mode='HTML'
    )
    # הודעת פתיחה ליום חדש + כפתור מה אכלתי היום
    await update.message.reply_text(
        'יום חדש התחיל! אפשר להתחיל לדווח מה אכלת היום.',
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton('מה אכלתי היום')]], resize_keyboard=True),
        parse_mode='HTML'
    )

def clean_desc(desc):
    import re
    return re.sub(r'^(אכלתי|שתיתי|שתיתי קפה|אכלתי קפה)\s+', '', desc.strip())

def clean_meal_text(text):
    # מסיר ביטויים כמו "בצהריים אכלתי", "בערב אכלתי", "בבוקר אכלתי", "ושתיתי", "ואכלתי" וכו'
    text = re.sub(r'ב(בוקר|צהריים|ערב|לילה)\s*אכלתי\s*', '', text)
    text = re.sub(r'ואכלתי\s*', '', text)
    text = re.sub(r'ושתיתי\s*', '', text)
    return text.strip()

# --- Water Intake Handlers ---
from telegram import ReplyKeyboardMarkup, KeyboardButton

# Add to the bottom of the file, before main()

async def water_intake_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Ask how much water was drunk
    keyboard = [
        [KeyboardButton('כוס אחת (240 מ"ל)'), KeyboardButton('שתי כוסות (480 מ"ל)')],
        [KeyboardButton('בקבוק קטן (500 מ"ל)'), KeyboardButton('בקבוק גדול (1 ליטר)')],
        [KeyboardButton('אחר')]
    ]
    await update.message.reply_text(
        get_gendered_text(context, 'כמה מים שתית?', 'כמה מים שתית?'),
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
        parse_mode='HTML'
    )
    return 'WATER_AMOUNT'

async def water_intake_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Parse amount and update user data
    amount_map = {
        'כוס אחת (240 מ"ל)': 240,
        'שתי כוסות (480 מ"ל)': 480,
        'בקבוק קטן (500 מ"ל)': 500,
        'בקבוק גדול (1 ליטר)': 1000
    }
    if context.user_data is None:
        context.user_data = {}
    if 'water_today' not in context.user_data:
        context.user_data['water_today'] = 0
    amount_text = update.message.text.strip()
    if amount_text in amount_map:
        amount = amount_map[amount_text]
    elif amount_text.isdigit():
        amount = int(amount_text)
    else:
        # If 'אחר', ask for manual input
        await update.message.reply_text('הזן כמות במ"ל (למשל: 300):', reply_markup=ReplyKeyboardRemove(), parse_mode='HTML')
        return 'WATER_AMOUNT'
    context.user_data['water_today'] += amount
    # Log to Google Sheets
    log_to_sheet({
        'username': update.effective_user.username if update.effective_user else '',
        'user_id': update.effective_user.id if update.effective_user else '',
        'text': f'שתה מים: {amount} מ"ל',
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'event_type': 'שתייה'
    })
    await update.message.reply_text(
        get_gendered_text(context, f'כל הכבוד! שתית {amount} מ"ל מים. סה"כ היום: {context.user_data["water_today"]} מ"ל', f'כל הכבוד! שתית {amount} מ"ל מים. סה"כ היום: {context.user_data["water_today"]} מ"ל'),
        reply_markup=ReplyKeyboardRemove(),
        parse_mode='HTML'
    )
    return ConversationHandler.END

# --- Main ---
def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # --- UX: Cancel Command ---
    async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        context.user_data.clear()
        await update.message.reply_text("הפעולה בוטלה. אפשר להתחיל מחדש בכל עת עם /start.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    # --- UX: Help Command ---
    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """הצגת עזרה"""
        help_text = """
🤖 <b>קלוריקו - בוט תזונה אישי</b>

📋 <b>פקודות זמינות:</b>
/start - התחלת שיחה חדשה
/reset - איפוס נתונים והתחלה מחדש
/reports - תפריט דוחות
/help - הצגת עזרה זו

💡 <b>איך להשתמש:</b>
• כתוב/י מה אכלת/ת וקבל/י חישוב קלוריות
• שאל/י שאלות על תזונה
• קבל/י תזכורות שתיית מים
• עקוב/י אחרי ההתקדמות שלך
• צפה/י בדוחות שבועיים וחודשיים

🎯 <b>דוגמאות:</b>
"אכלתי תפוח"
"כמה קלוריות יש בבננה?"
"שתיתי כוס מים"
"כמה קלוריות צרכתי אתמול?"
    """
        await update.message.reply_text(help_text, parse_mode='HTML')

    async def reports_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """הצגת תפריט דוחות"""
        await show_reports_menu(update, context)

    async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """איפוס נתונים והתחלה מחדש"""
        user_id = update.effective_user.id if update.effective_user else None
        
        if user_id:
            # מחיקת כל הנתונים של המשתמש
            context.user_data.clear()
            
            # מחיקת נתונים מבסיס הנתונים (אם קיים)
            try:
                import sqlite3
                conn = sqlite3.connect("nutrition_data.db")
                cursor = conn.cursor()
                cursor.execute("DELETE FROM nutrition_logs WHERE user_id = ?", (user_id,))
                conn.commit()
                conn.close()
            except Exception as e:
                logging.warning(f"לא הצלחתי למחוק נתונים מבסיס הנתונים: {e}")
        
        # הודעה למשתמש
        await update.message.reply_text(
            "🔄 איפסתי את כל הנתונים שלך. בוא/י נתחיל מחדש!",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='HTML'
        )
        
        # התחלת תהליך ההרשמה מחדש
        await start(update, context)

    async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """הצגת דוח שבועי"""
        user_id = update.effective_user.id if update.effective_user else None
        
        if not user_id:
            await update.message.reply_text("❌ לא הצלחתי לזהות את המשתמש שלך.")
            return
        
        try:
            # קבלת נתונים שבועיים
            weekly_data = get_weekly_report(user_id)
            
            if not weekly_data:
                await update.message.reply_text(
                    "📊 אין עדיין נתונים לשבוע האחרון.\n"
                    "התחל/י לדווח על הארוחות שלך עם /start או פשוט כתוב/י מה אכלת/ת!",
                    parse_mode='HTML'
                )
                return
            
            # בניית טקסט הדוח
            report_text = build_weekly_summary_text(weekly_data)
            await update.message.reply_text(report_text, parse_mode='HTML')
            
            # יצירת גרף
            chart_path = plot_calories(weekly_data)
            if chart_path and os.path.exists(chart_path):
                await update.message.reply_photo(
                    photo=open(chart_path, 'rb'),
                    caption="📈 גרף צריכת קלוריות שבועית"
                )
                # מחיקת הקובץ הזמני
                try:
                    os.remove(chart_path)
                except:
                    pass
            else:
                await update.message.reply_text("📊 לא הצלחתי ליצור גרף הפעם.")
                
        except Exception as e:
            logging.error(f"שגיאה ביצירת דוח: {e}")
            await update.message.reply_text("❌ לא הצלחתי ליצור דוח הפעם. נסה/י שוב מאוחר יותר.")

    # --- תפריט דוחות ---
    async def show_reports_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """הצגת תפריט דוחות ראשי"""
        keyboard = [
            [InlineKeyboardButton("📊 דוחות", callback_data="reports_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🤖 <b>קלוריקו - בוט תזונה אישי</b>\n\n"
            "בחר/י פעולה מהתפריט למטה:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

    async def handle_reports_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """טיפול בלחיצות על כפתורי דוחות"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id if update.effective_user else None
        if not user_id:
            await query.edit_message_text("❌ לא הצלחתי לזהות את המשתמש שלך.")
            return
        
        if query.data == "reports_main":
            # תפריט דוחות ראשי
            keyboard = [
                [InlineKeyboardButton("📅 שבוע אחרון", callback_data="report_weekly")],
                [InlineKeyboardButton("📊 חודש אחרון", callback_data="report_monthly")],
                [InlineKeyboardButton("🔙 חזרה", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "📊 <b>בחר/י סוג דוח:</b>",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        
        elif query.data == "report_weekly":
            await generate_weekly_report(query, user_id)
        
        elif query.data == "report_monthly":
            await generate_monthly_report(query, user_id)
        
        elif query.data == "back_to_main":
            keyboard = [
                [InlineKeyboardButton("📊 דוחות", callback_data="reports_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "🤖 <b>קלוריקו - בוט תזונה אישי</b>\n\n"
                "בחר/י פעולה מהתפריט למטה:",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )

    async def generate_weekly_report(query, user_id):
        """יצירת דוח שבועי"""
        try:
            # קבלת נתונים שבועיים
            weekly_data = get_weekly_report(user_id)
            
            if not weekly_data:
                await query.edit_message_text(
                    "📊 <b>דוח שבועי</b>\n\n"
                    "אין עדיין נתונים לשבוע האחרון.\n"
                    "התחל/י לדווח על הארוחות שלך!",
                    parse_mode='HTML'
                )
                return
            
            # בדיקה אם הדוח חלקי
            days_found = len(weekly_data)
            days_expected = 7
            partial_note = ""
            if days_found < days_expected:
                partial_note = f"\n⚠️ <b>דוח חלקי – נמצאו רק {days_found} ימים מתוך {days_expected}</b>\n"
            
            # בניית טקסט הדוח
            report_text = f"📊 <b>דוח שבועי</b>{partial_note}\n"
            report_text += build_weekly_summary_text(weekly_data)
            
            # שליחת הטקסט
            await query.edit_message_text(report_text, parse_mode='HTML')
            
            # יצירת ושליחת גרף
            chart_path = plot_calories(weekly_data)
            if chart_path and os.path.exists(chart_path):
                await query.message.reply_photo(
                    photo=open(chart_path, 'rb'),
                    caption="📈 גרף צריכת קלוריות שבועית"
                )
                # מחיקת הקובץ הזמני
                try:
                    os.remove(chart_path)
                except:
                    pass
            
            # כפתור חזרה
            keyboard = [[InlineKeyboardButton("🔙 חזרה לדוחות", callback_data="reports_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                "בחר/י פעולה נוספת:",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logging.error(f"שגיאה ביצירת דוח שבועי: {e}")
            await query.edit_message_text(
                "❌ לא הצלחתי ליצור דוח שבועי הפעם.\n"
                "נסה/י שוב מאוחר יותר."
            )

    async def generate_monthly_report(query, user_id):
        """יצירת דוח חודשי"""
        try:
            # קבלת נתונים חודשיים
            monthly_data = get_monthly_report(user_id)
            
            if not monthly_data:
                await query.edit_message_text(
                    "📊 <b>דוח חודשי</b>\n\n"
                    "אין עדיין נתונים לחודש האחרון.\n"
                    "התחל/י לדווח על הארוחות שלך!",
                    parse_mode='HTML'
                )
                return
            
            # בדיקה אם הדוח חלקי
            days_found = len(monthly_data)
            days_expected = 30
            partial_note = ""
            if days_found < days_expected:
                partial_note = f"\n⚠️ <b>דוח חלקי – נמצאו רק {days_found} ימים מתוך {days_expected}</b>\n"
            
            # בניית טקסט הדוח
            report_text = f"📊 <b>דוח חודשי</b>{partial_note}\n"
            report_text += build_monthly_summary_text(monthly_data)
            
            # שליחת הטקסט
            await query.edit_message_text(report_text, parse_mode='HTML')
            
            # יצירת ושליחת גרף
            chart_path = plot_calories(monthly_data)
            if chart_path and os.path.exists(chart_path):
                await query.message.reply_photo(
                    photo=open(chart_path, 'rb'),
                    caption="📈 גרף צריכת קלוריות חודשי"
                )
                # מחיקת הקובץ הזמני
                try:
                    os.remove(chart_path)
                except:
                    pass
            
            # כפתור חזרה
            keyboard = [[InlineKeyboardButton("🔙 חזרה לדוחות", callback_data="reports_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                "בחר/י פעולה נוספת:",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logging.error(f"שגיאה ביצירת דוח חודשי: {e}")
            await query.edit_message_text(
                "❌ לא הצלחתי ליצור דוח חודשי הפעם.\n"
                "נסה/י שוב מאוחר יותר."
            )

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_gender)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_height)],
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_weight)],
            GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_goal)],
            BODY_FAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_body_fat)],
            ACTIVITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_activity)],
            DIET: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_diet)],
            ALLERGIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_allergies)],
            MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, menu_decision)],
            DAILY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_daily_choice)],
            EATEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, eaten)],
            SUMMARY: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_summary)],
            SCHEDULE: [MessageHandler(filters.TEXT & ~filters.COMMAND, schedule_menu)],
            EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_water_reminder_opt_in)],
            BODY_FAT_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_body_fat_target)]
        },
        fallbacks=[CommandHandler('start', start), CommandHandler('cancel', cancel), CommandHandler('help', help_command), MessageHandler(filters.TEXT & ~filters.COMMAND, handle_free_text_input)],
    )
    application.add_handler(conv_handler)

    water_conv = ConversationHandler(
        entry_points=[
            CommandHandler('shititi', water_intake_start),
            MessageHandler(filters.Regex('^שתיתי$'), water_intake_start),
            MessageHandler(filters.Regex('^שתיתי, תודה$'), water_intake_start)
        ],
        states={
            'WATER_AMOUNT': [MessageHandler(filters.TEXT & ~filters.COMMAND, water_intake_amount)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )
    application.add_handler(water_conv)

    # --- Handler for 'תזכיר לי בעוד עשר דקות' button globally ---
    application.add_handler(MessageHandler(filters.Regex('^תזכיר לי בעוד עשר דקות$'), remind_in_10_minutes))

    # --- Handler for canceling water reminders globally ---
    application.add_handler(MessageHandler(filters.Regex('^(תפסיק להזכיר לי לשתות מים|ביטול תזכורות מים|תפסיק תזכורות מים)$'), cancel_water_reminders))

    # --- Global handler for any free text input ---
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_free_text_input))

    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('cancel', cancel))
    application.add_handler(CommandHandler('reset', reset_command))
    application.add_handler(CommandHandler('report', report_command))
    application.add_handler(CommandHandler('reports', reports_command))

    # --- Callback Query Handler for Reports Menu ---
    application.add_handler(CallbackQueryHandler(handle_reports_callback))

    application.run_polling()

if __name__ == '__main__':
    print("TELEGRAM_TOKEN:", os.environ.get("TELEGRAM_TOKEN"))
    main() 