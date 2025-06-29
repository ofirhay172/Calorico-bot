"""Telegram bot handlers for nutrition management."""

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from typing import Optional

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import ContextTypes, ConversationHandler

from config import (
    ALLERGIES,
    BODY_FAT_TARGET,
    DAILY,
    EDIT,
    EATEN,
    MENU,
    SCHEDULE,
    SYSTEM_BUTTONS,
    GENDERED_ACTION,
    GENDER_OPTIONS,
    GOAL_OPTIONS,
    ACTIVITY_OPTIONS_MALE,
    ACTIVITY_OPTIONS_FEMALE,
    USERS_FILE,
    NAME,
    GENDER,
    AGE,
    HEIGHT,
    WEIGHT,
    GOAL,
    BODY_FAT,
    ACTIVITY,
    DIET,
    SUMMARY,
)
from db import save_user, load_user, save_daily_entry
from utils import (
    clean_desc,
    clean_meal_text,
    get_gendered_text,
    markdown_to_html,
    strip_html_tags,
    calculate_bmr,
    build_daily_menu,
    water_recommendation,
    learning_logic,
    set_openai_client,
    _openai_client,
    extract_openai_response_content,
    build_main_keyboard,
    parse_date_from_text,
)
from report_generator import (
    get_weekly_report, 
    build_weekly_summary_text, 
    plot_calories,
    get_nutrition_by_date,
    get_last_occurrence_of_meal,
    format_date_query_response,
)

# TODO: להוסיף את כל ה-handlers מהקובץ המקורי, כולל שאלון, תפריט, דוחות, free text, מים וכו'.
# כל handler צריך לכלול docstring קצרה.

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """פותח שיחה עם המשתמש ומתחיל את שאלון הפתיחה."""
    if update.effective_user:
        user_first_name = update.effective_user.first_name or ""
    else:
        user_first_name = ""
    welcome_message = (
        f"שלום {user_first_name}! אני <b>קלוריקו</b> – הבוט שיעזור לך לשמור על תזונה, מעקב והתמדה 🙌\n\n"
        "<b>הנה מה שאני יודע לעשות:</b>\n"
        "✅ התאמה אישית של תפריט יומי – לפי הגובה, משקל, גיל, מטרה ותזונה שלך\n"
        "📊 דוחות תזונתיים – שבועי וחודשי\n"
        "💧 תזכורות חכמות לשתיית מים\n"
        '🍽 רישום יומי של "מה אכלתי היום" או "מה אכלתי אתמול"\n'
        "🔥 מעקב קלוריות יומי, ממוצע לארוחה וליום\n"
        "📅 ניתוח מגמות – צריכת חלבון, שומן ופחמימות\n"
        "🏋️ חיבור לאימונים שדיווחת עליהם\n"
        "📝 אפשרות לעדכן בכל שלב את המשקל, המטרה, התזונה או רמת הפעילות שלך\n"
        "⏰ תפריט יומי שנשלח אליך אוטומטית בשעה שתבחר\n\n"
        "<b>בוא/י נתחיל בהרשמה קצרה:</b>"
    )
    if update.message:
        await update.message.reply_text(
            welcome_message, reply_markup=ReplyKeyboardRemove(), parse_mode="HTML"
        )
        
        # Add 5 second delay
        await asyncio.sleep(5)
        
        # Add additional message
        await update.message.reply_text(
            "אשמח להכיר אותך קצת 😊",
            parse_mode="HTML"
        )
        
        # Add another 5 second delay
        await asyncio.sleep(5)
        
        await get_name(update, context)
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש לשמו וממשיך לשאלת מגדר."""
    if update.message and update.message.text:
        name = update.message.text.strip()
        context.user_data["name"] = name
        keyboard = [[KeyboardButton(opt)] for opt in GENDER_OPTIONS]
        await update.message.reply_text(
            "מה המגדר שלך?",
            reply_markup=ReplyKeyboardMarkup(
                keyboard, one_time_keyboard=True, resize_keyboard=True
            ),
            parse_mode="HTML",
        )
        return GENDER


async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש למגדר וממשיך לשאלת גיל."""
    if update.message and update.message.text:
        gender = update.message.text.strip()
        if gender not in GENDER_OPTIONS:
            keyboard = [[KeyboardButton(opt)] for opt in GENDER_OPTIONS]
            await update.message.reply_text(
                "בחר/י מגדר מהתפריט למטה:",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
            return GENDER
        context.user_data["gender"] = gender
        gender_text = "בת כמה את?" if gender == "נקבה" else "בן כמה אתה?"
        await update.message.reply_text(
            gender_text,
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
        return AGE


async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש לגילו וממשיך לשאלת גובה."""
    if update.message and update.message.text:
        age = update.message.text.strip()
        if not age.isdigit() or not (5 <= int(age) <= 120):
            gender = context.user_data.get("gender", "זכר") if context.user_data else "זכר"
            error_text = "אנא הזיני גיל תקין (5-120)." if gender == "נקבה" else "אנא הזן גיל תקין (5-120)."
            await update.message.reply_text(
                error_text,
                parse_mode="HTML",
            )
            return AGE
        context.user_data["age"] = int(age)
        await update.message.reply_text(
            'מה הגובה שלך בס"מ?',
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
        return HEIGHT


async def get_height(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש לגובהו וממשיך לשאלת משקל."""
    if update.message and update.message.text:
        height = update.message.text.strip()
        if not height.isdigit() or not (80 <= int(height) <= 250):
            gender = context.user_data.get("gender", "זכר") if context.user_data else "זכר"
            error_text = 'אנא הזיני גובה תקין בס"מ (80-250).' if gender == "נקבה" else 'אנא הזן גובה תקין בס"מ (80-250).'
            await update.message.reply_text(
                error_text,
                parse_mode="HTML",
            )
            return HEIGHT
        context.user_data["height"] = int(height)
        await update.message.reply_text(
            'מה המשקל שלך בק"ג?',
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
        return WEIGHT


async def get_weight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש למשקלו וממשיך לשאלת מטרה."""
    if update.message and update.message.text:
        weight = update.message.text.strip()
        if not weight.isdigit() or not (20 <= int(weight) <= 300):
            gender = context.user_data.get("gender", "זכר") if context.user_data else "זכר"
            error_text = 'אנא הזיני משקל תקין בק"ג (20-300).' if gender == "נקבה" else 'אנא הזן משקל תקין בק"ג (20-300).'
            await update.message.reply_text(
                error_text,
                parse_mode="HTML",
            )
            return WEIGHT
        context.user_data["weight"] = int(weight)
        keyboard = [[KeyboardButton(opt)] for opt in GOAL_OPTIONS]
        await update.message.reply_text(
            "מה המטרה התזונתית שלך?",
            reply_markup=ReplyKeyboardMarkup(
                keyboard, one_time_keyboard=True, resize_keyboard=True
            ),
            parse_mode="HTML",
        )
        return GOAL


async def get_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש למטרה וממשיך לשאלת אחוזי שומן או פעילות גופנית."""
    if update.message and update.message.text:
        goal = update.message.text.strip()
        if goal not in GOAL_OPTIONS:
            keyboard = [[KeyboardButton(opt)] for opt in GOAL_OPTIONS]
            gender = context.user_data.get("gender", "זכר") if context.user_data else "זכר"
            error_text = "בחרי מטרה מהתפריט למטה:" if gender == "נקבה" else "בחר מטרה מהתפריט למטה:"
            await update.message.reply_text(
                error_text,
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
            return GOAL
        context.user_data["goal"] = goal
        if goal == "לרדת באחוזי שומן":
            keyboard = [[KeyboardButton(str(i))] for i in range(10, 41, 2)]
            keyboard.append([KeyboardButton("לא ידוע")])
            await update.message.reply_text(
                get_gendered_text(
                    context,
                    'מה אחוזי השומן שלך? (אם לא ידוע, בחר/י "לא ידוע")',
                    'מה אחוזי השומן שלך? (אם לא ידוע, בחרי "לא ידוע")',
                ),
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
            return BODY_FAT
        gender = context.user_data.get("gender", "זכר")
        options = ACTIVITY_OPTIONS_MALE if gender == "זכר" else ACTIVITY_OPTIONS_FEMALE
        keyboard = [[KeyboardButton(opt)] for opt in options]
        await asyncio.sleep(2)
        await update.message.reply_text(
            "מה רמת הפעילות הגופנית שלך?",
            reply_markup=ReplyKeyboardMarkup(
                keyboard, one_time_keyboard=True, resize_keyboard=True
            ),
            parse_mode="HTML",
        )
        return ACTIVITY


async def get_body_fat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש לאחוזי שומן וממשיך ליעד או פעילות גופנית."""
    if update.message and update.message.text:
        value = update.message.text.strip()
        if value == "לא ידוע":
            context.user_data["body_fat"] = "לא ידוע"
        else:
            try:
                context.user_data["body_fat"] = float(value)
            except Exception:
                await update.message.reply_text(
                    'אנא הזן ערך מספרי או בחר "לא ידוע".', parse_mode="HTML"
                )
                return BODY_FAT
        if (
            context.user_data.get("goal") == "לרדת באחוזי שומן"
            and "body_fat_target" not in context.user_data
        ):
            await update.message.reply_text(
                "לאיזה אחוז שומן תרצה/י להגיע?", parse_mode="HTML"
            )
            return BODY_FAT_TARGET
        gender = context.user_data.get("gender", "זכר")
        options = ACTIVITY_OPTIONS_MALE if gender == "זכר" else ACTIVITY_OPTIONS_FEMALE
        keyboard = [[KeyboardButton(opt)] for opt in options]
        await asyncio.sleep(2)
        await update.message.reply_text(
            get_gendered_text(
                context, "מה רמת הפעילות הגופנית שלך?", "מה רמת הפעילות הגופנית שלך?"
            ),
            reply_markup=ReplyKeyboardMarkup(
                keyboard, one_time_keyboard=True, resize_keyboard=True
            ),
            parse_mode="HTML",
        )
        return ACTIVITY


async def get_body_fat_target(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """שואל את המשתמש ליעד אחוזי שומן וממשיך לשאלת פעילות גופנית."""
    if update.message and update.message.text:
        value = update.message.text.strip()
        try:
            context.user_data["body_fat_target"] = float(value)
        except Exception:
            await update.message.reply_text(
                "אנא הזן ערך מספרי ליעד אחוזי שומן.", parse_mode="HTML"
            )
            return BODY_FAT_TARGET
        gender = context.user_data.get("gender", "זכר")
        options = ACTIVITY_OPTIONS_MALE if gender == "זכר" else ACTIVITY_OPTIONS_FEMALE
        keyboard = [[KeyboardButton(opt)] for opt in options]
        await asyncio.sleep(2)
        await update.message.reply_text(
            "מה רמת הפעילות הגופנית שלך?",
            reply_markup=ReplyKeyboardMarkup(
                keyboard, one_time_keyboard=True, resize_keyboard=True
            ),
            parse_mode="HTML",
        )
        return ACTIVITY


# TODO: להמשיך להעביר את כל שאר ה-handlers מהקובץ המקורי, כולל free text, דוחות, מים, תפריט וכו'.

logger = logging.getLogger(__name__)


async def get_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש לרמת פעילות וממשיך לשאלת תזונה."""
    if update.message and update.message.text:
        activity = update.message.text.strip()
        gender = context.user_data.get("gender", "זכר")
        options = ACTIVITY_OPTIONS_MALE if gender == "זכר" else ACTIVITY_OPTIONS_FEMALE
        if activity not in options:
            keyboard = [[KeyboardButton(opt)] for opt in options]
            gender = context.user_data.get("gender", "זכר") if context.user_data else "זכר"
            error_text = "בחרי רמת פעילות מהתפריט למטה:" if gender == "נקבה" else "בחר רמת פעילות מהתפריט למטה:"
            await update.message.reply_text(
                error_text,
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
            return ACTIVITY
        context.user_data["activity"] = activity
        gender = context.user_data.get("gender", "זכר") if context.user_data else "זכר"
        diet_text = "מה העדפות התזונה שלך? (בחרי כל מה שמתאים)" if gender == "נקבה" else "מה העדפות התזונה שלך? (בחר/י כל מה שמתאים)"
        await update.message.reply_text(
            diet_text,
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
        return DIET


async def get_diet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש להעדפות תזונה וממשיך לשאלת אלרגיות."""
    if update.message and update.message.text:
        diet_text = update.message.text.strip()
        # Parse diet preferences
        diet_options = [
            "צמחוני",
            "טבעוני",
            "קטוגני",
            "ללא גלוטן",
            "ללא לקטוז",
            "דל פחמימות",
            "דל שומן",
            "דל נתרן",
            "פאלאו",
            "אין העדפות מיוחדות",
        ]
        selected_diet = []
        for option in diet_options:
            if option.lower() in diet_text.lower():
                selected_diet.append(option)
        if not selected_diet:
            selected_diet = ["אין העדפות מיוחדות"]
        context.user_data["diet"] = selected_diet
        
        # Calculate BMR and calorie budget
        user = context.user_data
        calorie_budget = calculate_bmr(
            user.get("gender", "זכר"),
            user.get("age", 30),
            user.get("height", 170),
            user.get("weight", 70),
            user.get("activity", "בינונית"),
            user.get("goal", "שמירה על משקל"),
        )
        context.user_data["calorie_budget"] = calorie_budget
        
        await update.message.reply_text(
            "האם יש לך אלרגיות למזון? (אם לא, כתוב 'אין')",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
        return ALLERGIES


async def get_allergies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש לאלרגיות ומסיים את השאלון."""
    if update.message and update.message.text:
        allergies_text = update.message.text.strip()
        if allergies_text.lower() in ["אין", "לא", "ללא"]:
            context.user_data["allergies"] = []
        else:
            # Parse allergies
            allergies = [allergy.strip() for allergy in allergies_text.split(",")]
            context.user_data["allergies"] = allergies
        
        # Save user data
        user_id = update.effective_user.id if update.effective_user else None
        if user_id:
            save_user(user_id, context.user_data)
        
        # Show summary and next steps
        user = context.user_data
        calorie_budget = user.get("calorie_budget", 1800)
        summary = f"""<b>סיכום הנתונים שלך:</b>
• שם: {user.get('name', 'לא צוין')}
• מגדר: {user.get('gender', 'לא צוין')}
• גיל: {user.get('age', 'לא צוין')}
• גובה: {user.get('height', 'לא צוין')} ס"מ
• משקל: {user.get('weight', 'לא צוין')} ק"ג
• מטרה: {user.get('goal', 'לא צוינה')}
• פעילות: {user.get('activity', 'לא צוינה')}
• תזונה: {', '.join(user.get('diet', []))}
• אלרגיות: {', '.join(user.get('allergies', [])) if user.get('allergies') else 'אין'}
• תקציב קלורי יומי: <b>{calorie_budget} קלוריות</b>"""
        
        await update.message.reply_text(summary, parse_mode="HTML")
        
        # Ask about water reminders
        await ask_water_reminder_opt_in(update, context)
        return EDIT


async def ask_water_reminder_opt_in(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask user if they want water reminders."""
    keyboard = [[KeyboardButton("כן, אשמח!"), KeyboardButton("לא, תודה")]]
    gender = context.user_data.get("gender", "זכר") if context.user_data else "זכר"
    reminder_text = "האם תרצי לקבל תזכורת לשתות מים כל שעה וחצי?" if gender == "נקבה" else "האם תרצה לקבל תזכורת לשתות מים כל שעה וחצי?"
    await update.message.reply_text(
        reminder_text,
        reply_markup=ReplyKeyboardMarkup(
            keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
        parse_mode="HTML",
    )


async def set_water_reminder_opt_in(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Set water reminder preferences."""
    if not update.message or not update.message.text:
        return EDIT
    choice = update.message.text.strip()
    user_id = update.effective_user.id if update.effective_user else None
    if choice == "כן, אשמח!":
        context.user_data["water_reminder_opt_in"] = True
        context.user_data["water_reminder_active"] = True
        await update.message.reply_text(
            get_gendered_text(
                context,
                "מעולה! אזכיר לך לשתות מים כל שעה וחצי עד שתסיים/י את היום.",
                "מעולה! אזכיר לך לשתות מים כל שעה וחצי עד שתסיימי את היום.",
            ),
            parse_mode="HTML",
        )
        if user_id:
            save_user(user_id, context.user_data)
        asyncio.create_task(start_water_reminder_loop_with_buttons(update, context))
    else:
        context.user_data["water_reminder_opt_in"] = False
        context.user_data["water_reminder_active"] = False
        await update.message.reply_text(
            get_gendered_text(
                context,
                "אין בעיה! אפשר להפעיל תזכורות מים בכל שלב.",
                "אין בעיה! אפשר להפעיל תזכורות מים בכל שלב.",
            ),
            parse_mode="HTML",
        )
        if user_id:
            save_user(user_id, context.user_data)
    
    # After water answer - ask what they want to do
    keyboard = [
        [
            KeyboardButton("לקבל תפריט יומי"),
            KeyboardButton("רק לעקוב אחרי הארוחות"),
        ],
        [
            KeyboardButton("לקבל תפריט/ארוחה לפי מוצרים בבית")
        ],
    ]
    gender = context.user_data.get("gender", "זכר") if context.user_data else "זכר"
    action_text = "מה תרצי לעשות כעת?" if gender == "נקבה" else "מה תרצה לעשות כעת?"
    await update.message.reply_text(
        action_text,
        reply_markup=ReplyKeyboardMarkup(
            keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
        parse_mode="HTML",
    )
    return MENU


async def start_water_reminder_loop_with_buttons(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Start water reminder loop with buttons."""
    user_id = update.effective_user.id if update.effective_user else None
    if context.user_data is None:
        context.user_data = {}
    while context.user_data.get("water_reminder_opt_in") and context.user_data.get(
        "water_reminder_active"
    ):
        await asyncio.sleep(90 * 60)  # 1.5 hours
        if not context.user_data.get(
            "water_reminder_opt_in"
        ) or not context.user_data.get("water_reminder_active"):
            break
        try:
            if update.message:
                await send_water_reminder(update, context)
        except Exception as e:
            logger.error(f"Water reminder error: {e}")
        if user_id:
            save_user(user_id, context.user_data)


async def send_water_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send water reminder with buttons."""
    keyboard = [
        [KeyboardButton("שתיתי, תודה")],
        [KeyboardButton("תזכיר לי בעוד עשר דקות")],
        [KeyboardButton("תפסיק להזכיר לי לשתות מים")],
    ]
    await update.message.reply_text(
        get_gendered_text(
            context,
            "תזכורת: הגיע הזמן לשתות מים! 🥤",
            "תזכורת: הגיע הזמן לשתות מים! 🥤",
        ),
        reply_markup=ReplyKeyboardMarkup(
            keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
        parse_mode="HTML",
    )


async def remind_in_10_minutes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remind in 10 minutes."""
    await update.message.reply_text(
        "בסדר! אזכיר לך לשתות מים בעוד 10 דקות.",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML",
    )
    await asyncio.sleep(10 * 60)
    await send_water_reminder(update, context)


async def cancel_water_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel water reminders."""
    if context.user_data is None:
        context.user_data = {}
    context.user_data["water_reminder_opt_in"] = False
    context.user_data["water_reminder_active"] = False
    user_id = update.effective_user.id if update.effective_user else None
    if user_id:
        save_user(user_id, context.user_data)

    await update.message.reply_text(
        get_gendered_text(
            context,
            "בסדר! הפסקתי להזכיר לך לשתות מים. אפשר להפעיל שוב בכל שלב.",
            "בסדר! הפסקתי להזכיר לך לשתות מים. אפשר להפעיל שוב בכל שלב.",
        ),
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML",
    )


async def water_intake_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start water intake tracking."""
    keyboard = [
        [KeyboardButton('כוס אחת (240 מ"ל)'), KeyboardButton('שתי כוסות (480 מ"ל)')],
        [KeyboardButton('בקבוק קטן (500 מ"ל)'), KeyboardButton("בקבוק גדול (1 ליטר)")],
        [KeyboardButton("אחר")],
    ]
    await update.message.reply_text(
        "כמה מים שתית?",
        reply_markup=ReplyKeyboardMarkup(
            keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
        parse_mode="HTML",
    )
    return "WATER_AMOUNT"


async def water_intake_amount(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Parse water amount and update user data."""
    amount_map = {
        'כוס אחת (240 מ"ל)': 240,
        'שתי כוסות (480 מ"ל)': 480,
        'בקבוק קטן (500 מ"ל)': 500,
        "בקבוק גדול (1 ליטר)": 1000,
    }
    if context.user_data is None:
        context.user_data = {}
    if "water_today" not in context.user_data:
        context.user_data["water_today"] = 0
    amount_text = update.message.text.strip()
    if amount_text in amount_map:
        amount = amount_map[amount_text]
    elif amount_text.isdigit():
        amount = int(amount_text)
    else:
        # If 'אחר', ask for manual input
        await update.message.reply_text(
            'הזן כמות במ"ל (למשל: 300):',
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
        return "WATER_AMOUNT"
    context.user_data["water_today"] += amount
    
    await update.message.reply_text(
        f'כל הכבוד! שתית {amount} מ"ל מים. סה"כ היום: {context.user_data["water_today"]} מ"ל',
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML",
    )
    return ConversationHandler.END


async def show_daily_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show daily menu with keyboard options."""
    keyboard = [
        [KeyboardButton("מה אכלתי")],
        [KeyboardButton("סיימתי")],
        [KeyboardButton("עריכה")],
    ]
    user = context.user_data if context.user_data is not None else {}
    gender = user.get("gender", "male")
    action_text = (
        GENDERED_ACTION["female"] if gender == "female" else GENDERED_ACTION["male"]
    )
    if update.message:
        await update.message.reply_text(
            action_text,
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode="HTML",
        )
    return DAILY


async def daily_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle daily menu requests."""
    await update.message.reply_text("רגע, בונה עבורך תפריט...")
    if update.message and update.message.text:
        if not update.message or not update.message.text:
            return DAILY
        choice = update.message.text.strip()
        if choice == "סיימתי":
            await send_summary(update, context)
            return SCHEDULE
        else:
            return await eaten(update, context)


async def eaten(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle food intake reporting."""
    if update.message and update.message.text:
        if not update.message or not update.message.text:
            return DAILY
        eaten_text = strip_html_tags(update.message.text.strip())
        
        # Identify questions about food
        question_starts = (
            "האם",
            "אפשר",
            "מותר",
            "כמה",
            "מה",
            "איך",
            "מדוע",
            "למה",
            "היכן",
            "איפה",
            "מתי",
            "מי",
        )
        is_question = eaten_text.endswith("?") or any(
            eaten_text.strip().startswith(q) for q in question_starts
        )
        
        if is_question:
            # Send all text to GPT as a question
            user = context.user_data if context.user_data is not None else {}
            calorie_budget = user.get("calorie_budget", 0)
            total_eaten = sum(e["calories"] for e in user.get("eaten_today", []))
            remaining = calorie_budget - total_eaten
            diet = ", ".join(user.get("diet", []))
            allergies = ", ".join(user.get("allergies", []))
            eaten_list = ", ".join(
                clean_desc(e["desc"]) for e in user.get("eaten_today", [])
            )
            prompt = (
                f"המשתמש/ת שואל/ת: {eaten_text}\n"
                f"העדפות תזונה: {diet}\n"
                f"אלרגיות: {allergies}\n"
                f"מה שנאכל היום: {eaten_list}\n"
                f"תקציב קלורי יומי: {calorie_budget}, נשארו: {remaining} קלוריות\n"
                f"ענה/י תשובה תזונתית אמיתית, בהתחשב בכל הנתונים, כולל תקציב, העדפות, אלרגיות, מטרות, ומה שכבר נאכל. הצג המלצה מגדרית, מסודרת, ב-HTML בלבד, עם בולד, רשימות, כותרות, והסבר קצר. אל תשתמש/י ב-Markdown."
            )
            response = await _openai_client.chat.completions.create(
                model="gpt-4o", messages=[{"role": "user", "content": prompt}]
            )
            answer = extract_openai_response_content(response)
            await update.message.reply_text(answer, parse_mode="HTML")
            return DAILY
        
        # Regular eating report
        if context.user_data is None:
            context.user_data = {}
        if "eaten_today" not in context.user_data:
            context.user_data["eaten_today"] = []
        user = context.user_data
        
        # Split components
        meal_components = [eaten_text]  # Keep original text as single component
        results = []
        total_calories = 0
        gpt_details = []
        
        for component in meal_components:
            calorie_prompt = f"כמה קלוריות יש ב: {component}? כתוב רק את שם המאכל, מספר הקלוריות, ואם אפשר – אייקון מתאים. אל תוסיף טקסט נוסף. דוגמה: ביצת עין – 95 קק'ל 🍳"
            calorie_response = await _openai_client.chat.completions.create(
                model="gpt-4o", messages=[{"role": "user", "content": calorie_prompt}]
            )
            gpt_str = extract_openai_response_content(calorie_response)
            
            # Extract calories
            match = re.search(r"(\d+)\s*קק\'ל", gpt_str)
            calories = int(match.group(1)) if match else 0
            results.append({"desc": component, "calories": calories})
            total_calories += calories
            gpt_details.append(gpt_str)
        
        user["eaten_today"].extend(results)
        user["remaining_calories"] = user.get("calorie_budget", 0) - sum(
            e["calories"] for e in user["eaten_today"]
        )
        
        # Build summary output
        details_text = "\n".join(gpt_details)
        summary = f"{details_text}\n<b>📊 סה\"כ לארוחה: {total_calories} קק'ל</b>"
        await update.message.reply_text(summary, parse_mode="HTML")
        
        # Show remaining calories
        remaining = user["remaining_calories"]
        msg = await update.message.reply_text(f"נשארו לך: {remaining} קלוריות להיום.")
        try:
            await context.bot.pin_chat_message(
                chat_id=update.effective_chat.id, message_id=msg.message_id
            )
        except Exception:
            pass
        
        # Don't ask 'what did you eat today?' again. Only suggest 'finished'.
        keyboard = [[KeyboardButton("סיימתי")]]
        gender = user.get("gender", "זכר")
        action_text = GENDERED_ACTION.get(gender, GENDERED_ACTION["אחר"])
        await update.message.reply_text(
            action_text,
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode="HTML",
        )
        return DAILY


async def handle_daily_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle choices in daily menu."""
    if not update.message or not update.message.text:
        return DAILY

    choice = update.message.text.strip()

    if choice == "📊 דוחות":
        # Show reports menu
        keyboard = [
            [InlineKeyboardButton("📅 שבוע אחרון", callback_data="report_weekly")],
            [InlineKeyboardButton("📊 חודש אחרון", callback_data="report_monthly")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "📊 <b>בחר/י סוג דוח:</b>", reply_markup=reply_markup, parse_mode="HTML"
        )

        # Return to normal keyboard
        keyboard = [
            [KeyboardButton("מה אכלתי היום")],
            [KeyboardButton("📊 דוחות")],
            [KeyboardButton("סיימתי")],
        ]
        await update.message.reply_text(
            "בחר/י פעולה:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
        return DAILY

    elif choice == "סיימתי":
        await send_summary(update, context)
        return SCHEDULE

    else:
        # Handle eating report
        return await eaten(update, context)


async def send_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send daily summary."""
    user = context.user_data if context.user_data is not None else {}
    if "eaten_today" in user and user["eaten_today"]:
        eaten_lines = [
            f"• <b>{clean_desc(e['desc'])}</b> (<b>{e['calories']}</b> קלוריות)"
            for e in user["eaten_today"]
        ]
        eaten = "\n".join(eaten_lines)
        total_eaten = sum(e["calories"] for e in user["eaten_today"])
    else:
        eaten = "לא דווח"
        total_eaten = 0
    
    remaining = user.get("calorie_budget", 0) - total_eaten
    summary = f'<b>סיכום יומי:</b>\n{eaten}\n\n<b>סה"כ נאכל:</b> <b>{total_eaten}</b> קלוריות\n<b>נשארו:</b> <b>{remaining}</b> קלוריות להיום.'
    summary = markdown_to_html(summary)
    await update.message.reply_text(summary, parse_mode="HTML")

    # Save to database
    user_id = update.effective_user.id if update.effective_user else None
    if user_id and total_eaten > 0:
        try:
            # Calculate macro averages (estimate)
            meals_list = [clean_desc(e["desc"]) for e in user["eaten_today"]]

            # Simple estimate of protein, fat, carbs (15%, 30%, 55% of calories)
            estimated_protein = (total_eaten * 0.15) / 4  # 4 calories per gram protein
            estimated_fat = (total_eaten * 0.30) / 9  # 9 calories per gram fat
            estimated_carbs = (total_eaten * 0.55) / 4  # 4 calories per gram carbs

            # Save to database
            save_daily_entry(
                user_id=user_id,
                calories=total_eaten,
                protein=estimated_protein,
                fat=estimated_fat,
                carbs=estimated_carbs,
                meals_list=meals_list,
                goal=user.get("goal", ""),
            )

            # Save confirmation message
            await update.message.reply_text(
                "✅ הנתונים נשמרו בהצלחה! אפשר לראות דוח שבועי עם /report",
                parse_mode="HTML",
            )

        except Exception as e:
            logging.error(f"שגיאה בשמירה לבסיס הנתונים: {e}")
            await update.message.reply_text(
                "⚠️ לא הצלחתי לשמור את הנתונים, אבל הסיכום נשאר.", parse_mode="HTML"
            )

    # Dynamic recommendation for tomorrow
    learning = learning_logic(context)
    await update.message.reply_text(
        f"<b>המלצה למחר:</b>\n{learning}", parse_mode="HTML"
    )
    
    # Water recommendation
    water = water_recommendation(context)
    await update.message.reply_text(water, parse_mode="HTML")
    
    # Reset meals for next day
    user["eaten_today"] = []
    user["remaining_calories"] = user.get("calorie_budget", 0)
    
    # Ask about menu timing for tomorrow
    times = [f"{h:02d}:00" for h in range(7, 13)]
    keyboard = [[KeyboardButton(t)] for t in times]
    await update.message.reply_text(
        get_gendered_text(
            context,
            "מתי לשלוח לך את התפריט היומי למחר?",
            "מתי לשלוח לך את התפריט היומי למחר?",
        ),
        reply_markup=ReplyKeyboardMarkup(
            keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
        parse_mode="HTML",
    )
    return SCHEDULE


async def schedule_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Schedule menu for next day."""
    if not update.message or not update.message.text:
        return SCHEDULE
    time = update.message.text.strip()
    if context.user_data is None:
        context.user_data = {}
    context.user_data["schedule_time"] = time
    user_id = update.effective_user.id if update.effective_user else None
    if user_id:
        save_user(user_id, context.user_data)
    await update.message.reply_text(
        get_gendered_text(
            context,
            f"מעולה! אשלח לך תפריט חדש כל יום בשעה {time}.",
            f"מעולה! אשלח לך תפריט חדש כל יום בשעה {time}.",
        ),
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML",
    )
    return ConversationHandler.END


async def check_dessert_permission(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Check if dessert is allowed based on remaining calories."""
    user = context.user_data
    rem = user.get("remaining_calories", user.get("calorie_budget", 0))
    msg = get_gendered_text(
        context,
        (
            f"נותרו לך {rem} קלוריות. אפשר קינוח! תתפנק 🙂"
            if rem > 150
            else "לא מומלץ קינוח כרגע. נשארו מעט קלוריות."
        ),
        (
            f"נותרו לך {rem} קלוריות. אפשר קינוח! תתפנקי 🙂"
            if rem > 150
            else "לא מומלץ קינוח כרגע. נשארו מעט קלוריות."
        ),
    )
    await update.message.reply_text(msg, parse_mode="HTML")
    return DAILY


async def after_questionnaire(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle post-questionnaire flow."""
    await ask_water_reminder_opt_in(update, context)
    return EDIT


async def handle_free_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all free text input - identify if it's a question or eating report."""
    if not update.message or not update.message.text:
        return

    user_text = update.message.text.strip()

    user_id = update.effective_user.id if update.effective_user else None
    user = context.user_data if context.user_data else {}

    # Identify historical data questions
    historical_indicators = [
        "אתמול",
        "שלשום",
        "אתמול",
        "שלשום",
        "לפני",
        "יום",
        "שבוע",
        "חודש",
        "צרכתי",
        "אכלתי",
        "שתיתי",
        "היה לי",
        "היתה לי",
        "אכל",
        "שתה",
    ]

    is_historical_query = any(
        indicator in user_text for indicator in historical_indicators
    )

    if is_historical_query and user_id:
        # Try to extract date from text
        target_date = parse_date_from_text(user_text)

        if target_date:
            # Question about specific date
            nutrition_data = get_nutrition_by_date(user_id, target_date)

            if nutrition_data:
                # Extract question type
                if "קלוריות" in user_text or "צרכתי" in user_text:
                    response = format_date_query_response(nutrition_data, "calories")
                elif "אכלתי" in user_text or "אכל" in user_text:
                    response = format_date_query_response(nutrition_data, "meals")
                else:
                    response = format_date_query_response(nutrition_data, "summary")

                await update.message.reply_text(response, parse_mode="HTML")
                return
            else:
                await update.message.reply_text(
                    f"❌ לא נמצאו נתונים ל{target_date}.", parse_mode="HTML"
                )
                return

        # Search for specific food
        meal_keywords = [
            "המבורגר",
            "פיצה",
            "סושי",
            "פסטה",
            "עוף",
            "בשר",
            "דג",
            "סלט",
            "תפוח",
            "בננה",
            "קולה",
            "קפה",
        ]
        found_meal = None
        for keyword in meal_keywords:
            if keyword.lower() in user_text.lower():
                found_meal = keyword
                break

        if found_meal:
            last_occurrence = get_last_occurrence_of_meal(user_id, found_meal)
            if last_occurrence:
                meals_text = ", ".join(last_occurrence["meals"])
                response = f"🍽️ הפעם האחרונה שאכלת {found_meal} הייתה ב{last_occurrence['date']}: {meals_text}"
                await update.message.reply_text(response, parse_mode="HTML")
                return
            else:
                await update.message.reply_text(
                    f"❌ לא נמצאו רשומות של {found_meal} ב-30 הימים האחרונים.",
                    parse_mode="HTML",
                )
                return

    # Identify if it looks like an eating report or regular question
    eating_indicators = [
        "שתיתי",
        "אכלתי",
        "שתיתי",
        "אכל",
        "שתה",
        "אכלה",
        "שתתה",
    ]
    question_indicators = [
        "?",
        "כמה",
        "האם",
        "אפשר",
        "מותר",
        "איך",
        "מה",
        "מתי",
        "איפה",
        "למה",
        "איזה",
    ]

    is_eating_report = any(indicator in user_text for indicator in eating_indicators)
    is_question = any(
        indicator in user_text for indicator in question_indicators
    ) or user_text.endswith("?")

    # Build prompt for GPT
    calorie_budget = user.get("calorie_budget", 1800)
    total_eaten = sum(e["calories"] for e in user.get("eaten_today", []))
    remaining = calorie_budget - total_eaten
    diet = ", ".join(user.get("diet", []))
    allergies = ", ".join(user.get("allergies", []))
    eaten_today = ", ".join(
        [clean_desc(e["desc"]) for e in user.get("eaten_today", [])]
    )

    if is_eating_report:
        # This looks like an eating report - GPT will think calories and add
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
        # This looks like a question - GPT will answer the question
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
        response = await _openai_client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": prompt}]
        )
        gpt_response = extract_openai_response_content(response)

        await update.message.reply_text(gpt_response, parse_mode="HTML")

        # If it was an eating report, update the data
        if is_eating_report:
            # Try to extract calories from GPT response
            calorie_match = re.search(r"(\d+)\s*קלוריות?", gpt_response)
            if calorie_match:
                calories = int(calorie_match.group(1))
                if "eaten_today" not in user:
                    user["eaten_today"] = []
                user["eaten_today"].append({"desc": user_text, "calories": calories})
                user["remaining_calories"] = remaining - calories

                # Save
                if user_id:
                    save_user(user_id, user)

    except Exception as e:
        logging.error(f"שגיאה בטיפול בקלט חופשי: {e}")
        await update.message.reply_text("❌ לא הצלחתי לעבד את הבקשה. נסה/י שוב.")


async def menu_decision(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle menu decision choices."""
    await update.message.reply_text("רגע, בונה עבורך תפריט...")
    if not update.message or not update.message.text:
        return MENU
    
    # If 'build meal from what's at home' button was pressed - request details
    if update.message.text.strip() == "להרכבת ארוחה לפי מה שיש בבית":
        await update.message.reply_text(
            "מה יש בבית? להזין עם פסיקים.", parse_mode="HTML"
        )
        context.user_data["awaiting_products"] = True
        return MENU
    
    if context.user_data.get("awaiting_products"):
        products_text = update.message.text.strip()
        context.user_data["awaiting_products"] = False
        user = context.user_data
        calorie_budget = user.get("calorie_budget", 1800)
        diet_str = ", ".join(user.get("diet", []))
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
        response = await _openai_client.chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": prompt}]
        )
        menu_text = extract_openai_response_content(response)
        user["menu"] = menu_text
        # Don't add this meal to eaten_today or calculate calories
        await show_menu_with_keyboard(update, context, menu_text)
        return MENU
    
    choice = update.message.text.strip()
    opt_menu = "לקבל תפריט יומי"
    opt_track = "רק לעקוב אחרי הארוחות"
    opt_products = "לקבל תפריט/ארוחה לפי מוצרים בבית"
    user = context.user_data
    
    if choice == opt_menu:
        menu = await build_daily_menu(user, context)
        user["menu"] = menu
        await show_menu_with_keyboard(update, context, menu)
        return EATEN
    elif choice == opt_products:
        gender = context.user_data.get("gender", "זכר") if context.user_data else "זכר"
        await update.message.reply_text(
            get_gendered_text(
                context,
                'כתוב כאן את רשימת המוצרים שיש לך בבית (לדוג׳: ביצים, גבינה, עגבנייה, טונה, פסטה, חלווה, סלמון, גמבה, מלפפון וכו").',
                'כתבי כאן את רשימת המוצרים שיש לך בבית (לדוג׳: ביצים, גבינה, עגבנייה, טונה, פסטה, חלווה, סלמון, גמבה, מלפפון וכו").',
            ),
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
        context.user_data["awaiting_products"] = True
        return MENU
    else:
        await update.message.reply_text(
            get_gendered_text(
                context,
                f"תקציב הקלוריות היומי שלך: {user['calorie_budget']} קלוריות.",
                f"תקציב הקלוריות היומי שלך: {user['calorie_budget']} קלוריות.",
            ),
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
        # Don't show 'finished' button in first question
        await update.message.reply_text(
            get_gendered_text(
                context,
                "מה אכלת היום? כתוב בקצרה (לדוג׳: חביתה, סלט, קוטג׳ 5%).",
                "מה אכלת היום? כתבי בקצרה (לדוג׳: חביתה, סלט, קוטג׳ 5%).",
            ),
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
        return DAILY


async def show_menu_with_keyboard(update, context, menu_text=None):
    """Show daily menu with unified keyboard and budget."""
    user = context.user_data
    calorie_budget = user.get("calorie_budget", 1800)
    # Daily reset
    user["eaten_today"] = []
    user["remaining_calories"] = calorie_budget
    if menu_text is None:
        menu_text = user.get("menu", "")
    msg = f"<b>התקציב היומי שלך: {calorie_budget} קלוריות</b>\n\n{menu_text}"
    keyboard = build_main_keyboard()
    await update.message.reply_text(
        msg,
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )
    
    # Daily water recommendation in liters
    weight = user.get("weight", 70)
    min_l = round(weight * 30 / 1000, 1)
    max_l = round(weight * 35 / 1000, 1)
    min_cups = round((weight * 30) / 240)
    max_cups = round((weight * 35) / 240)
    await update.message.reply_text(
        f"<b>המלצת שתייה להיום:</b> {min_l}–{max_l} ליטר מים (כ-{min_cups}–{max_cups} כוסות)",
        parse_mode="HTML",
    )
    
    # Additional gendered message
    gender = context.user_data.get("gender", "זכר") if context.user_data else "זכר"
    additional_text = "אני כאן אם תרצי להתייעץ אם אפשר לאכול נניח תפוח, או אם תרצי לכתוב לי מה אכלת היום" if gender == "נקבה" else "אני כאן אם תרצה להתייעץ אם אפשר לאכול נניח תפוח, או אם תרצה לכתוב לי מה אכלת היום"
    await update.message.reply_text(
        additional_text,
        parse_mode="HTML",
    )
    
    # New day opening message + what did you eat today button
    await update.message.reply_text(
        "יום חדש התחיל! אפשר להתחיל לדווח מה אכלת היום. (הפרד/י בין מאכלים באמצעות פסיק – לדוגמה: ביצת עין, סלט ירקות, פרוסת לחם עם גבינה)",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("מה אכלתי היום")]], resize_keyboard=True
        ),
        parse_mode="HTML",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help information."""
    help_text = """<b>עזרה - קלוריקו</b>

<b>פקודות זמינות:</b>
/start - התחלת שיחה חדשה
/help - הצגת עזרה זו
/cancel - ביטול פעולה נוכחית
/reset - איפוס נתונים אישיים
/report - דוח תזונתי מהיר
/reports - תפריט דוחות
/shititi - דיווח שתיית מים

<b>איך להשתמש:</b>
1. התחל/י עם /start לעבור שאלון התאמה אישית
2. דווח/י על הארוחות שלך עם "מה אכלתי היום"
3. קבל/י תפריטים יומיים מותאמים אישית
4. עקוב/י אחרי התקדמות עם דוחות שבועיים וחודשיים

<b>תכונות נוספות:</b>
• תזכורות מים אוטומטיות
• מעקב קלוריות יומי
• המלצות תזונה מותאמות אישית
• דוחות מפורטים עם גרפים

<b>תמיכה:</b>
אם יש לך שאלות או בעיות, פנה/י אל המפתח."""

    await update.message.reply_text(help_text, parse_mode="HTML")


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset user data."""
    user_id = update.effective_user.id if update.effective_user else None
    if user_id:
        # Clear user data
        context.user_data.clear()
        # Remove from file
        if os.path.exists(USERS_FILE):
            try:
                with open(USERS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if str(user_id) in data:
                    del data[str(user_id)]
                    with open(USERS_FILE, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"Error resetting user data: {e}")

    await update.message.reply_text(
        "✅ הנתונים שלך אופסו בהצלחה. תוכל/י להתחיל מחדש עם /start",
        parse_mode="HTML",
    )


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate a quick report."""
    user_id = update.effective_user.id if update.effective_user else None
    if not user_id:
        await update.message.reply_text(
            "❌ לא נמצאו נתונים. התחל/י עם /start", parse_mode="HTML"
        )
        return

    try:
        # Get weekly report
        report_data = get_weekly_report(user_id)
        if report_data:
            report_text = build_weekly_summary_text(report_data)
            await update.message.reply_text(report_text, parse_mode="HTML")
            
            # Send chart if available
            chart_path = plot_calories(report_data)
            if chart_path and os.path.exists(chart_path):
                await update.message.reply_photo(
                    photo=open(chart_path, "rb"), caption="📈 גרף צריכת קלוריות שבועי"
                )
                try:
                    os.remove(chart_path)
                except:
                    pass
        else:
            await update.message.reply_text(
                "❌ לא נמצאו נתונים לדוח. התחל/י לדווח על הארוחות שלך!",
                parse_mode="HTML",
            )
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        await update.message.reply_text(
            "❌ שגיאה ביצירת הדוח. נסה/י שוב מאוחר יותר.", parse_mode="HTML"
        )


async def reports_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show reports menu."""
    await show_reports_menu(update, context)


async def show_reports_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show reports menu with inline buttons."""
    keyboard = [
        [InlineKeyboardButton("📅 שבוע אחרון", callback_data="report_weekly")],
        [InlineKeyboardButton("📊 חודש אחרון", callback_data="report_monthly")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "📊 <b>בחר/י סוג דוח:</b>", reply_markup=reply_markup, parse_mode="HTML"
    )


async def handle_reports_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle reports menu callbacks."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id if update.effective_user else None
    if not user_id:
        await query.edit_message_text(
            "❌ לא נמצאו נתונים. התחל/י עם /start", parse_mode="HTML"
        )
        return

    if query.data == "report_weekly":
        await generate_weekly_report(query, user_id)
    elif query.data == "report_monthly":
        await generate_monthly_report(query, user_id)
    elif query.data == "reports_main":
        await show_reports_menu(update, context)


async def generate_weekly_report(query, user_id):
    """Generate weekly report."""
    try:
        report_data = get_weekly_report(user_id)
        if not report_data:
            await query.edit_message_text(
                "❌ לא נמצאו נתונים לשבוע האחרון.\n"
                "התחל/י לדווח על הארוחות שלך!",
                parse_mode="HTML",
            )
            return

        report_text = build_weekly_summary_text(report_data)
        await query.edit_message_text(report_text, parse_mode="HTML")

        # Send chart
        chart_path = plot_calories(report_data)
        if chart_path and os.path.exists(chart_path):
            await query.message.reply_photo(
                photo=open(chart_path, "rb"), caption="📈 גרף צריכת קלוריות שבועי"
            )
            try:
                os.remove(chart_path)
            except:
                pass

        # Back button
        keyboard = [
            [InlineKeyboardButton("🔙 חזרה לדוחות", callback_data="reports_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "בחר/י פעולה נוספת:", reply_markup=reply_markup
        )

    except Exception as e:
        logging.error(f"שגיאה ביצירת דוח שבועי: {e}")
        await query.edit_message_text(
            "❌ לא הצלחתי ליצור דוח שבועי הפעם.\n" "נסה/י שוב מאוחר יותר."
        )


async def generate_monthly_report(query, user_id):
    """Generate monthly report."""
    try:
        # TODO: Implement monthly report generation
        monthly_data = []
        # report_text += build_monthly_summary_text(monthly_data)  # פונקציה לא קיימת - הסר

        if not monthly_data:
            await query.edit_message_text(
                "📊 <b>דוח חודשי</b>\n\n"
                "אין עדיין נתונים לחודש האחרון.\n"
                "התחל/י לדווח על הארוחות שלך!",
                parse_mode="HTML",
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
        # report_text += build_monthly_summary_text(monthly_data)

        # שליחת הטקסט
        await query.edit_message_text(report_text, parse_mode="HTML")

        # יצירת ושליחת גרף
        chart_path = plot_calories(monthly_data)
        if chart_path and os.path.exists(chart_path):
            await query.message.reply_photo(
                photo=open(chart_path, "rb"), caption="📈 גרף צריכת קלוריות חודשי"
            )
            # מחיקת הקובץ הזמני
            try:
                os.remove(chart_path)
            except:
                pass

        # כפתור חזרה
        keyboard = [
            [InlineKeyboardButton("🔙 חזרה לדוחות", callback_data="reports_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "בחר/י פעולה נוספת:", reply_markup=reply_markup
        )

    except Exception as e:
        logging.error(f"שגיאה ביצירת דוח חודשי: {e}")
        await query.edit_message_text(
            "❌ לא הצלחתי ליצור דוח חודשי הפעם.\n" "נסה/י שוב מאוחר יותר."
        )
