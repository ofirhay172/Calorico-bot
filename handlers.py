"""Telegram bot handlers for nutrition management.

This module contains all conversation handlers and message processing functions
for the Calorico nutritional bot, including questionnaire flow, menu generation,
and user interactions."""

import asyncio
import logging
from datetime import date, datetime
import re

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
    InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes, ConversationHandler
import telegram

from db import NutritionDB, save_user_data

from config import (
    NAME,
    GENDER,
    AGE,
    HEIGHT,
    WEIGHT,
    GOAL,
    BODY_FAT_CURRENT,
    BODY_FAT_TARGET_GOAL,
    ACTIVITY,
    ACTIVITY_TYPE,
    ACTIVITY_FREQUENCY,
    ACTIVITY_DURATION,
    TRAINING_TIME,
    CARDIO_GOAL,
    STRENGTH_GOAL,
    SUPPLEMENTS,
    SUPPLEMENT_TYPES,
    LIMITATIONS,
    MIXED_ACTIVITIES,
    MIXED_FREQUENCY,
    MIXED_DURATION,
    MIXED_MENU_ADAPTATION,
    DIET,
    ALLERGIES,
    WATER_REMINDER_OPT_IN,
    DIET_OPTIONS,
    GENDER_OPTIONS,
    GOAL_OPTIONS,
    ACTIVITY_YES_NO_OPTIONS,
    ACTIVITY_TYPE_OPTIONS,
    ACTIVITY_FREQUENCY_OPTIONS,
    ACTIVITY_DURATION_OPTIONS,
    TRAINING_TIME_OPTIONS,
    CARDIO_GOAL_OPTIONS,
    STRENGTH_GOAL_OPTIONS,
    SUPPLEMENT_OPTIONS,
    MIXED_ACTIVITY_OPTIONS,
    MIXED_FREQUENCY_OPTIONS,
    MIXED_DURATION_OPTIONS,
    ALLERGY_OPTIONS,
    ACTIVITY_TYPES_MULTI,
    ACTIVITY_TYPES_SELECTION,
)
from utils import (
    clean_desc,
    calculate_bmr,
    build_main_keyboard,
    build_user_prompt_for_gpt,
    call_gpt,
    analyze_meal_with_gpt,
    build_free_text_prompt,
)
from report_generator import (
    get_weekly_report,
    build_weekly_summary_text,
    plot_calories,
    get_nutrition_by_date,
    get_last_occurrence_of_meal,
    format_date_query_response,
    get_monthly_report,
    build_monthly_summary_text,
)

# Initialize logger first
logger = logging.getLogger(__name__)

# Import OpenAI client
try:
    from openai import OpenAI
    _openai_client = None
except ImportError:
    _openai_client = None
    logger.warning("OpenAI not available - AI features will be disabled")


def get_openai_client():
    """Get OpenAI client instance."""
    global _openai_client
    if _openai_client is None:
        try:
            from openai import OpenAI as OpenAIClient
            _openai_client = OpenAIClient()
        except ImportError:
            logger.error("OpenAI not available")
            return None
    return _openai_client


ALLERGY_OPTIONS = [
    "אין",
    "בוטנים",
    "אגוזים",
    "חלב",
    "גלוטן",
    "ביצים",
    "סויה",
    "דגים",
    "שומשום",
    "סלרי",
    "חרדל",
    "סולפיטים",
    "שאר (פרט/י)",
]


def build_allergy_keyboard(selected):
    """בונה inline keyboard לבחירת אלרגיות מרובות עם טוגל וכפתור סיום."""
    keyboard = []
    for opt in ALLERGY_OPTIONS:
        if opt == "אין":
            # דלג על כפתור "אין" - הוא יטופל בשלב הקודם
            continue
        else:
            # כפתור טוגל לכל אלרגיה
            text = opt + (" ❌" if opt in selected else "")
            callback_data = f"allergy_toggle_{opt}"
            keyboard.append([InlineKeyboardButton(text, callback_data=callback_data)])
    # כפתור "סיימתי" בסוף
    keyboard.append([InlineKeyboardButton("סיימתי", callback_data="allergy_done")])
    return InlineKeyboardMarkup(keyboard)


def build_diet_keyboard(selected_options):
    """בונה מקלדת תזונה עם אימוג'י איקס על בחירות נבחרות."""
    keyboard = []
    for option in DIET_OPTIONS:
        if option in selected_options:
            # אם נבחר - הוסף איקס
            button_text = f"❌ {option}"
        else:
            # אם לא נבחר - הצג רגיל
            button_text = option
        keyboard.append([KeyboardButton(button_text)])

    # כפתור לסיום
    keyboard.append([KeyboardButton("סיימתי בחירת העדפות")])
    return keyboard


def validate_age(age_text: str) -> tuple[bool, int, str]:
    """בודק תקינות גיל ומחזיר (תקין, גיל, הודעת שגיאה)."""
    try:
        age = int(age_text.strip())
        if 12 <= age <= 120:
            return True, age, ""
        return False, 0, "הגיל חייב להיות בין 12 ל-120 שנים."
    except ValueError:
        return False, 0, "אנא הזן מספר תקין לגיל."


def validate_height(height_text: str) -> tuple[bool, float, str]:
    """בודק תקינות גובה ומחזיר (תקין, גובה, הודעת שגיאה)."""
    try:
        height = float(height_text.strip())
        if 100 <= height <= 250:
            return True, height, ""
        return False, 0, "הגובה חייב להיות בין 100 ל-250 ס\"מ."
    except ValueError:
        return False, 0, "אנא הזן מספר תקין לגובה."


def validate_weight(weight_text: str) -> tuple[bool, float, str]:
    """בודק תקינות משקל ומחזיר (תקין, משקל, הודעת שגיאה)."""
    try:
        weight = float(weight_text.strip())
        if 30 <= weight <= 300:
            return True, weight, ""
        return False, 0, "המשקל חייב להיות בין 30 ל-300 ק\"ג."
    except ValueError:
        return False, 0, "אנא הזן מספר תקין למשקל."


def validate_body_fat(body_fat_text: str) -> tuple[bool, float, str]:
    """בודק תקינות אחוז שומן ומחזיר (תקין, אחוז, הודעת שגיאה)."""
    try:
        body_fat = float(body_fat_text.strip())
        if 5 <= body_fat <= 50:
            return True, body_fat, ""
        return False, 0, "אחוז השומן חייב להיות בין 5% ל-50%."
    except ValueError:
        return False, 0, "אנא הזן מספר תקין לאחוז שומן."


def reset_user(user_id):
    # איפוס נתוני משתמש ב-users.json
    save_user_data(user_id, {})
    # אפשר להוסיף כאן איפוס נוסף ב-nutrition.db אם צריך


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """מתחיל את הבוט ומציג הודעת פתיחה בשלוש הודעות נפרדות, עם השהייה של 3 שניות בין כל הודעה."""
    if not update.message:
        return

    user = update.effective_user
    if not user:
        return

    user_id = user.id
    # איפוס נתוני משתמש במסד נתונים
    reset_user(user_id)
    # איפוס context
    if context.user_data is not None:
        context.user_data.clear()
    else:
        context.user_data = {}

    # קבלת שם המשתמש מטלגרם או שאלת שם
    if user.first_name:
        context.user_data["name"] = user.first_name
        user_name = user.first_name
    else:
        user_name = "חבר/ה"

    logger.info("Bot started by user %s", user.id)

    # הודעה 1: הצגה עצמית ופיצ'רים קיימים
    msg1 = (
        "היי! אני קלוריקו – הבוט שיעזור לך לשמור על תזונה ואיזון יומי 💪🥗\n\n"
        "הנה מה שאני יודע לעשות כבר עכשיו:\n\n"
        "🍽 תפריט יומי מותאם אישית – לפי הגובה, המשקל, הגיל, רמת הפעילות והמטרה שלך  \n"
        "🧮 מעקב קלוריות חכם – כולל חישוב תקציב יומי, סיכום קלורי לארוחות ועדכון שוטף  \n"
        "📝 רישום חופשי של מה שאכלת – פשוט כתוב/י: 'אכלתי...' ואני אחשב הכל  \n"
        "🤔 שאלות חופשיות על אוכל – כמו 'אפשר המבורגר?' או 'כמה קלוריות יש בתפוח?'  \n"
        "📌 הודעות נעוצות עם תקציב יומי מעודכן – מתעדכן אוטומטית אחרי כל ארוחה  \n"
        "📅 תפריט חדש כל בוקר בשעה שתבחר/י  \n"
        "🆕 שינוי קל בכל עת – משקל, יעד, תפריט, אלרגיות, ספורט ועוד"
    )
    await update.message.reply_text(msg1, parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
    await asyncio.sleep(3)

    # הודעה 2: דברים שיגיעו בקרוב
    msg2 = (
        "🚧 מה עוד בדרך?\n\n"
        "📊 דוחות שבועיים וחודשיים – כולל מגמות אישיות  \n"
        "🍳 ניתוח תזונתי לפי חלבון, שומן ופחמימות  \n"
        "💧 תזכורות שתייה חכמות  \n"
        "✅ סיכום יומי עם המלצות לשיפור  \n"
        "📲 תמיכה באפליקציות כושר"
    )
    await update.message.reply_text(msg2, parse_mode="HTML")
    await asyncio.sleep(3)

    # הודעה 3: איך להשתמש ומה עכשיו
    msg3 = (
        "איך מדברים איתי? פשוט מאוד:\n\n"
        "- 'אכלתי 2 פרוסות לחם עם קוטג' וסלט'  \n"
        "- 'בא לי שוקולד. כדאי לי?'  \n"
        "- 'כמה קלוריות יש ב-100 גרם אורז?'  \n"
        "- 'רוצה תפריט יומי'\n\n"
        "📍 בוא/י נתחיל בשאלון קצר כדי שאכיר אותך טוב יותר 👇"
    )
    keyboard = [
        [KeyboardButton("✏️ להתחלת שאלון אישי")],
        [KeyboardButton("📘 עזרה")],
    ]
    await update.message.reply_text(msg3, parse_mode="HTML", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    await asyncio.sleep(3)

    # הודעה 4: הודעה קריטית על כפתור "סיימתי"
    critical_msg = (
        "**כדי לסיים את היום – יש ללחוץ על הכפתור \"סיימתי\"**\n\n"
        "זה מאפס את התקציב, שולח לך סיכום יומי, ושואל מתי לשלוח את התפריט למחר!"
    )
    await update.message.reply_text(critical_msg, parse_mode="HTML")

    # המשך flow: אם אין שם בטלגרם - שאל שם, אחרת המשך לשאלת מגדר
    if not user.first_name:
        return await get_name(update, context)
    else:
        return await get_gender(update, context)


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש לשמו וממשיך לשאלת מגדר."""
    if update.message and update.message.text:
        name = update.message.text.strip()
        if not name:
            try:
                await update.message.reply_text(
                    "אנא הזן שם תקין.",
                    reply_markup=ReplyKeyboardRemove(),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return NAME

        if context.user_data is None:
            context.user_data = {}
        logger.info("Name provided: '%s'", name)
        context.user_data["name"] = name

        # שמירה למסד נתונים
        user_id = update.effective_user.id if update.effective_user else None
        logger.info("About to save user data - user_id: %s, context.user_data keys: %s", user_id, list(context.user_data.keys()) if context.user_data else 'None')
        if user_id and context.user_data:
            nutrition_db.save_user(user_id, context.user_data)

        keyboard = [[KeyboardButton(opt)] for opt in GENDER_OPTIONS]
        try:
            await update.message.reply_text(
                "מה המגדר שלך?",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
        return GENDER

    # This is when called from start function - ask for name
    logger.info("get_name called from start - asking for name")
    if update.message:
        try:
            await update.message.reply_text(
                "איך לקרוא לך?",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
    return NAME


async def get_gender(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש למגדר וממשיך לשאלת גיל."""
    logger.info(
        "get_gender called with text: %s",
        update.message.text if update.message and update.message.text else 'None'
    )
    if update.message and update.message.text:
        gender = update.message.text.strip()
        logger.info(
            "Gender selected: '%s', valid options: %s", gender, GENDER_OPTIONS)
        if gender not in GENDER_OPTIONS:
            logger.warning("Invalid gender selected: '%s'", gender)
            keyboard = [[KeyboardButton(opt)] for opt in GENDER_OPTIONS]
            try:
                await update.message.reply_text(
                    "בחר מגדר מהתפריט למטה:",
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return GENDER

        if context.user_data is None:
            context.user_data = {}
        context.user_data["gender"] = gender
        logger.info("Gender saved: %s", gender)

        # שמירה למסד נתונים
        user_id = update.effective_user.id if update.effective_user else None
        logger.info("About to save user data - user_id: %s, context.user_data keys: %s", user_id, list(context.user_data.keys()) if context.user_data else 'None')
        if user_id and context.user_data:
            nutrition_db.save_user(user_id, context.user_data)

        gender_text = "בת כמה את?" if gender == "נקבה" else "בן כמה אתה?"
        try:
            await update.message.reply_text(
                gender_text,
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
        return AGE

    logger.error("get_gender called without text")
    return GENDER


async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש לגילו וממשיך לשאלת גובה."""
    if update.message and update.message.text:
        age_text = update.message.text.strip()
        is_valid, age, error_msg = validate_age(age_text)

        if not is_valid:
            try:
                await update.message.reply_text(
                    error_msg,
                    reply_markup=ReplyKeyboardRemove(),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return AGE

        if context.user_data is None:
            context.user_data = {}
        context.user_data["age"] = age

        # שמירה למסד נתונים
        user_id = update.effective_user.id if update.effective_user else None
        logger.info("About to save user data - user_id: %s, context.user_data keys: %s", user_id, list(context.user_data.keys()) if context.user_data else 'None')
        if user_id and context.user_data:
            nutrition_db.save_user(user_id, context.user_data)

        gender = context.user_data.get("gender", "זכר")
        height_text = "מה הגובה שלך בס\"מ?" if gender == "זכר" else "מה הגובה שלך בס\"מ?"
        try:
            await update.message.reply_text(
                height_text,
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
        return HEIGHT

    if context.user_data is None:
        context.user_data = {}
    gender = context.user_data.get("gender", "זכר")
    age_text = "בת כמה את?" if gender == "נקבה" else "בן כמה אתה?"
    if update.message:
        try:
            await update.message.reply_text(
                age_text,
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
    return AGE


async def get_height(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש לגובהו וממשיך לשאלת משקל."""
    if update.message and update.message.text:
        height_text = update.message.text.strip()
        is_valid, height, error_msg = validate_height(height_text)

        if not is_valid:
            try:
                await update.message.reply_text(
                    error_msg,
                    reply_markup=ReplyKeyboardRemove(),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return HEIGHT

        if context.user_data is None:
            context.user_data = {}
        context.user_data["height"] = height

        # שמירה למסד נתונים
        user_id = update.effective_user.id if update.effective_user else None
        logger.info("About to save user data - user_id: %s, context.user_data keys: %s", user_id, list(context.user_data.keys()) if context.user_data else 'None')
        if user_id and context.user_data:
            nutrition_db.save_user(user_id, context.user_data)

        gender = context.user_data.get("gender", "זכר")
        weight_text = "מה המשקל שלך בק\"ג?" if gender == "זכר" else "מה המשקל שלך בק\"ג?"
        try:
            await update.message.reply_text(
                weight_text,
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
        return WEIGHT

    if context.user_data is None:
        context.user_data = {}
    gender = context.user_data.get("gender", "זכר")
    height_text = "מה הגובה שלך בס\"מ?" if gender == "זכר" else "מה הגובה שלך בס\"מ?"
    if update.message:
        try:
            await update.message.reply_text(
                height_text,
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
    return HEIGHT


async def get_weight(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש למשקלו וממשיך לשאלת מטרה."""
    if update.message and update.message.text:
        weight_text = update.message.text.strip()
        is_valid, weight, error_msg = validate_weight(weight_text)

        if not is_valid:
            try:
                await update.message.reply_text(
                    error_msg,
                    reply_markup=ReplyKeyboardRemove(),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return WEIGHT

        if context.user_data is None:
            context.user_data = {}
        context.user_data["weight"] = weight

        # שמירה למסד נתונים
        user_id = update.effective_user.id if update.effective_user else None
        logger.info("About to save user data - user_id: %s, context.user_data keys: %s", user_id, list(context.user_data.keys()) if context.user_data else 'None')
        if user_id and context.user_data:
            nutrition_db.save_user(user_id, context.user_data)

        keyboard = [[KeyboardButton(opt)] for opt in GOAL_OPTIONS]
        gender = context.user_data.get("gender", "זכר")
        goal_text = "מה המטרה שלך?" if gender == "זכר" else "מה המטרה שלך?"
        try:
            await update.message.reply_text(
                goal_text,
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
        return GOAL

    if context.user_data is None:
        context.user_data = {}
    gender = context.user_data.get("gender", "זכר")
    weight_text = "מה המשקל שלך בק\"ג?" if gender == "זכר" else "מה המשקל שלך בק\"ג?"
    if update.message:
        try:
            await update.message.reply_text(
                weight_text,
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
    return WEIGHT


async def get_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data is None:
        context.user_data = {}
    if not update.message or not update.message.text:
        return GOAL
    goal = update.message.text.strip()
    context.user_data["goal"] = goal
    if goal == "ירידה באחוזי שומן":
        return await get_body_fat_current(update, context)
    # דלג על אחוז שומן אם המטרה אינה ירידה באחוזי שומן
    return await get_activity(update, context)


async def get_body_fat_current(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """שואל את המשתמש לאחוז שומן נוכחי וממשיך לאחוז יעד."""
    if update.message and update.message.text:
        body_fat_text = update.message.text.strip()
        is_valid, body_fat, error_msg = validate_body_fat(body_fat_text)

        if not is_valid:
            try:
                await update.message.reply_text(
                    error_msg,
                    reply_markup=ReplyKeyboardRemove(),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return BODY_FAT_CURRENT

        if context.user_data is None:
            context.user_data = {}
        context.user_data["body_fat_current"] = body_fat

        # שמירה למסד נתונים
        user_id = update.effective_user.id if update.effective_user else None
        logger.info("About to save user data - user_id: %s, context.user_data keys: %s", user_id, list(context.user_data.keys()) if context.user_data else 'None')
        if user_id:
            nutrition_db.save_user(user_id, context.user_data)

        gender = context.user_data.get(
            "gender", "זכר") if context.user_data else "זכר"
        target_text = "מה אחוז השומן היעד שלך?" if gender == "זכר" else "מה אחוז השומן היעד שלך?"
        try:
            await update.message.reply_text(
                target_text,
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
        return BODY_FAT_TARGET_GOAL
    else:
        gender = context.user_data.get(
            "gender", "זכר") if context.user_data else "זכר"
        body_fat_text = "מה אחוז השומן הנוכחי שלך?" if gender == "זכר" else "מה אחוז השומן הנוכחי שלך?"
        if update.message:
            try:
                await update.message.reply_text(
                    body_fat_text,
                    reply_markup=ReplyKeyboardRemove(),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
        return BODY_FAT_CURRENT


async def get_body_fat_target_goal(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """שואל את המשתמש לאחוז שומן יעד וממשיך לשאלת פעילות."""
    if update.message and update.message.text:
        target_text = update.message.text.strip()
        is_valid, target_fat, error_msg = validate_body_fat(target_text)

        if not is_valid:
            try:
                await update.message.reply_text(
                    error_msg,
                    reply_markup=ReplyKeyboardRemove(),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return BODY_FAT_TARGET_GOAL

        current_fat = context.user_data.get("body_fat_current", 0) if context.user_data else 0
        if target_fat >= current_fat:
            try:
                await update.message.reply_text(
                    "אחוז השומן היעד חייב להיות נמוך מהנוכחי כדי לרדת באחוזי שומן.",
                    reply_markup=ReplyKeyboardRemove(),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return BODY_FAT_TARGET_GOAL

        if context.user_data is None:
            context.user_data = {}
        context.user_data["body_fat_target"] = target_fat

        # שמירה למסד נתונים
        user_id = update.effective_user.id if update.effective_user else None
        logger.info("About to save user data - user_id: %s, context.user_data keys: %s", user_id, list(context.user_data.keys()) if context.user_data else 'None')
        if user_id and context.user_data:
            nutrition_db.save_user(user_id, context.user_data)

        # המשך לשאלת פעילות
        return await get_activity(update, context)
    else:
        if context.user_data is None:
            context.user_data = {}
        gender = context.user_data.get("gender", "זכר")
        target_text = "מה אחוז השומן היעד שלך?" if gender == "זכר" else "מה אחוז השומן היעד שלך?"
        if update.message:
            try:
                await update.message.reply_text(
                    target_text,
                    reply_markup=ReplyKeyboardRemove(),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
        return BODY_FAT_TARGET_GOAL


async def get_activity(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש על פעילות גופנית וממשיך לשאלות המתאימות."""
    if update.message and update.message.text:
        activity_answer = update.message.text.strip()
        if activity_answer not in ACTIVITY_YES_NO_OPTIONS:
            keyboard = [[KeyboardButton(opt)]
                        for opt in ACTIVITY_YES_NO_OPTIONS]
            if context.user_data is None:
                context.user_data = {}
            gender = context.user_data.get("gender", "זכר")
            if gender == "נקבה":
                error_text = gendered_text(
                    "האם אתה עושה פעילות גופנית? (בחר כן או לא מהתפריט למטה)",
                    "האם את עושה פעילות גופנית? (בחרי כן או לא מהתפריט למטה)",
                    context)
            elif gender == "זכר":
                error_text = gendered_text(
                    "האם אתה עושה פעילות גופנית? (בחר כן או לא מהתפריט למטה)",
                    "האם את עושה פעילות גופנית? (בחרי כן או לא מהתפריט למטה)",
                    context)
            else:
                error_text = gendered_text(
                    "האם אתה עושה פעילות גופנית? (בחר כן או לא מהתפריט למטה)",
                    "האם את עושה פעילות גופנית? (בחרי כן או לא מהתפריט למטה)",
                    context)
            try:
                await update.message.reply_text(
                    error_text,
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return ACTIVITY
        
        if context.user_data is None:
            context.user_data = {}
        context.user_data["does_activity"] = activity_answer

        # שמירה למסד נתונים
        user_id = update.effective_user.id if update.effective_user else None
        logger.info("About to save user data - user_id: %s, context.user_data keys: %s", user_id, list(context.user_data.keys()) if context.user_data else 'None')
        if user_id and context.user_data:
            nutrition_db.save_user(user_id, context.user_data)

        if activity_answer == "לא":
            # Skip to diet questions
            keyboard = [[KeyboardButton(opt)] for opt in DIET_OPTIONS]
            gender = context.user_data.get("gender", "זכר")
            if gender == "נקבה":
                diet_text = gendered_text(
                    "מה העדפות התזונה שלך? (בחרי כל מה שמתאים)",
                    "מה העדפות התזונה שלך? (בחרי כל מה שמתאים)",
                    context)
            elif gender == "זכר":
                diet_text = gendered_text(
                    "מה העדפות התזונה שלך? (בחרי כל מה שמתאים)",
                    "מה העדפות התזונה שלך? (בחרי כל מה שמתאים)",
                    context)
            else:
                diet_text = gendered_text(
                    "מה העדפות התזונה שלך? (בחרי כל מה שמתאים)",
                    "מה העדפות התזונה שלך? (בחרי כל מה שמתאים)",
                    context)
            try:
                await update.message.reply_text(
                    diet_text,
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return DIET
        # אם כן - הצג תפריט בחירת סוגי פעילות
        keyboard = build_activity_types_keyboard()
        gender = context.user_data.get("gender", "זכר")
        if gender == "נקבה":
            activity_text = gendered_text(
                "איזה סוגי פעילות אתה עושה? (בחרי כל מה שמתאים)",
                "איזה סוגי פעילות את עושה? (בחרי כל מה שמתאים)",
                context)
        elif gender == "זכר":
            activity_text = gendered_text(
                "איזה סוגי פעילות אתה עושה? (בחרי כל מה שמתאים)",
                "איזה סוגי פעילות את עושה? (בחרי כל מה שמתאים)",
                context)
        else:
            activity_text = gendered_text(
                "איזה סוגי פעילות אתה עושה? (בחרי כל מה שמתאים)",
                "איזה סוגי פעילות את עושה? (בחרי כל מה שמתאים)",
                context)
        
        try:
            await update.message.reply_text(
                activity_text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
        return ACTIVITY_TYPES_SELECTION
    # אם אין הודעה, הצג את השאלה
    if update.message:
        keyboard = [[KeyboardButton(opt)] for opt in ACTIVITY_YES_NO_OPTIONS]
        if context.user_data is None:
            context.user_data = {}
        gender = context.user_data.get("gender", "זכר")
        if gender == "נקבה":
            activity_text = gendered_text(
                "האם את עושה פעילות גופנית? (בחרי כן או לא)",
                "האם את עושה פעילות גופנית? (בחרי כן או לא)",
                context)
        elif gender == "זכר":
            activity_text = gendered_text(
                "האם אתה עושה פעילות גופנית? (בחרי כן או לא)",
                "האם את עושה פעילות גופנית? (בחרי כן או לא)",
                context)
        else:
            activity_text = gendered_text(
                "האם אתה עושה פעילות גופנית? (בחרי כן או לא)",
                "האם את עושה פעילות גופנית? (בחרי כן או לא)",
                context)
        try:
            await update.message.reply_text(
                activity_text,
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
    return ACTIVITY


async def get_activity_type(update: Update,
                            context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש לסוג הפעילות וממשיך לשאלות המתאימות."""
    if update.message and update.message.text:
        activity_type = update.message.text.strip()
        if activity_type not in ACTIVITY_TYPE_OPTIONS:
            keyboard = [[KeyboardButton(opt)] for opt in ACTIVITY_TYPE_OPTIONS]
            if context.user_data is None:
                context.user_data = {}
            gender = context.user_data.get("gender", "זכר")
            error_text = "בחר סוג פעילות מהתפריט למטה:" if gender == "זכר" else "בחרי סוג פעילות מהתפריט למטה:"
            try:
                await update.message.reply_text(
                    error_text,
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return ACTIVITY_TYPE

        if context.user_data is None:
            context.user_data = {}
        context.user_data["activity_type"] = activity_type

        # Route to appropriate next question based on activity type
        if activity_type in ["אין פעילות", "הליכה קלה"]:
            # Skip to diet questions
            keyboard = [[KeyboardButton(opt)] for opt in DIET_OPTIONS]
            gender = context.user_data.get("gender", "זכר")
            if gender == "נקבה":
                diet_text = gendered_text(
                    "מה העדפות התזונה שלך? (בחרי כל מה שמתאים)",
                    "מה העדפות התזונה שלך? (בחרי כל מה שמתאים)",
                    context)
            elif gender == "זכר":
                diet_text = gendered_text(
                    "מה העדפות התזונה שלך? (בחרי כל מה שמתאים)",
                    "מה העדפות התזונה שלך? (בחרי כל מה שמתאים)",
                    context)
            else:
                diet_text = gendered_text(
                    "מה העדפות התזונה שלך? (בחר כל מה שמתאים)",
                    "מה העדפות התזונה שלך? (בחרי כל מה שמתאים)",
                    context)
            try:
                await update.message.reply_text(
                    diet_text,
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return DIET

        elif activity_type == "הליכה מהירה / ריצה קלה":
            # Ask frequency with gender-appropriate text
            keyboard = [[KeyboardButton(opt)]
                        for opt in ACTIVITY_FREQUENCY_OPTIONS]
            gender = context.user_data.get("gender", "זכר")
            if gender == "נקבה":
                frequency_text = "כמה פעמים בשבוע את מבצעת את הפעילות?"
            elif gender == "זכר":
                frequency_text = "כמה פעמים בשבוע אתה מבצע את הפעילות?"
            else:
                frequency_text = gendered_text("כמה פעמים בשבוע אתה מבצע את הפעילות?", "כמה פעמים בשבוע את מבצעת את הפעילות?", context)
            try:
                await update.message.reply_text(
                    frequency_text,
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return ACTIVITY_FREQUENCY

        elif activity_type in ["אימוני כוח", "אימוני HIIT / קרוספיט"]:
            # Ask frequency with gender-appropriate text
            keyboard = [[KeyboardButton(opt)]
                        for opt in ACTIVITY_FREQUENCY_OPTIONS]
            gender = context.user_data.get("gender", "זכר")
            if gender == "נקבה":
                frequency_text = "כמה פעמים בשבוע את מתאמנת?"
            elif gender == "זכר":
                frequency_text = "כמה פעמים בשבוע אתה מתאמן?"
            else:
                frequency_text = gendered_text("כמה פעמים בשבוע אתה מתאמן?", "כמה פעמים בשבוע את מתאמנת?", context)
            try:
                await update.message.reply_text(
                    frequency_text,
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return ACTIVITY_FREQUENCY

        elif activity_type == "יוגה / פילאטיס":
            # Ask frequency with gender-appropriate text
            keyboard = [[KeyboardButton(opt)]
                        for opt in ACTIVITY_FREQUENCY_OPTIONS]
            gender = context.user_data.get("gender", "זכר")
            if gender == "נקבה":
                frequency_text = "כמה פעמים בשבוע את מתאמנת?"
            elif gender == "זכר":
                frequency_text = "כמה פעמים בשבוע אתה מתאמן?"
            else:
                frequency_text = gendered_text("כמה פעמים בשבוע אתה מתאמן?", "כמה פעמים בשבוע את מתאמנת?", context)
            try:
                await update.message.reply_text(
                    frequency_text,
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return ACTIVITY_FREQUENCY

        elif activity_type == "שילוב של כמה סוגים":
            # Ask for mixed activities
            keyboard = [[KeyboardButton(opt)]
                        for opt in MIXED_ACTIVITY_OPTIONS]
            gender = context.user_data.get("gender", "זכר")
            if gender == "נקבה":
                mixed_text = (
                    "אילו סוגי אימונים את מבצעת במהלך השבוע? (בחרי כל מה שמתאים)"
                )
            elif gender == "זכר":
                mixed_text = (
                    "אילו סוגי אימונים אתה מבצע במהלך השבוע? (בחר כל מה שמתאים)"
                )
            else:
                mixed_text = gendered_text(
                    "אילו סוגי אימונים אתה מבצע במהלך השבוע? (בחר כל מה שמתאים)",
                    "אילו סוגי אימונים את מבצעת במהלך השבוע? (בחרי כל מה שמתאים)",
                    context
                )
            try:
                await update.message.reply_text(
                    mixed_text,
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return MIXED_ACTIVITIES

        return DIET
    return ACTIVITY_TYPE


async def get_activity_frequency(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """שואל את המשתמש לתדירות הפעילות וממשיך לשאלה הבאה."""
    if update.message and update.message.text:
        frequency = update.message.text.strip()
        if frequency not in ACTIVITY_FREQUENCY_OPTIONS:
            keyboard = [[KeyboardButton(opt)]
                        for opt in ACTIVITY_FREQUENCY_OPTIONS]
            try:
                await update.message.reply_text(
                    gendered_text("בחר תדירות מהתפריט למטה:", "בחרי תדירות מהתפריט למטה:", context),
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return ACTIVITY_FREQUENCY

        # שמור את המידע הספציפי לסוג הפעילות הנוכחי
        if context.user_data is None:
            context.user_data = {}
        
        current_activity = context.user_data.get("current_activity", "")
        if current_activity:
            # אתחל את activity_details אם לא קיים
            if "activity_details" not in context.user_data:
                context.user_data["activity_details"] = {}
            
            # הסר אימוג'ים מהטקסט לצורך שמירה
            activity_clean = current_activity.replace("🏃", "").replace("🚶", "").replace("🚴", "").replace("🏊", "").replace("🏋️", "").replace("🧘", "").replace("🤸", "").replace("❓", "").strip()
            
            # שמור את התדירות לסוג הפעילות הנוכחי
            context.user_data["activity_details"][activity_clean] = {
                "frequency": frequency
            }

        # Continue to next activity or diet
        return await continue_to_next_activity(update, context)
    return ACTIVITY_FREQUENCY


async def get_activity_duration(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """שואל את המשתמש למשך הפעילות וממשיך לשאלה הבאה."""
    if update.message and update.message.text:
        duration = update.message.text.strip()
        if duration not in ACTIVITY_DURATION_OPTIONS:
            keyboard = [[KeyboardButton(opt)]
                        for opt in ACTIVITY_DURATION_OPTIONS]
            try:
                await update.message.reply_text(
                    gendered_text("בחר משך מהתפריט למטה:", "בחרי משך מהתפריט למטה:", context),
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return ACTIVITY_DURATION

        context.user_data["activity_duration"] = duration
        activity_type = context.user_data.get("activity_type", "") if context.user_data else ""

        # Route based on activity type
        if activity_type == "הליכה מהירה / ריצה קלה":
            # Ask cardio goal
            keyboard = [[KeyboardButton(opt)] for opt in CARDIO_GOAL_OPTIONS]
            try:
                await update.message.reply_text(
                    "מה מטרת הפעילות?",
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return CARDIO_GOAL

        elif activity_type in ["אימוני כוח", "אימוני HIIT / קרוספיט"]:
            # Ask training time
            keyboard = [[KeyboardButton(opt)] for opt in TRAINING_TIME_OPTIONS]
            try:
                await update.message.reply_text(
                    gendered_text("באיזה שעה בדרך כלל את/ה מתאמן/ת?", "באיזה שעה בדרך כלל את מתאמנת?", context),
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return TRAINING_TIME

        elif activity_type == "יוגה / פילאטיס":
            # Ask if this is the only activity
            keyboard = [[KeyboardButton("כן"), KeyboardButton("לא")]]
            try:
                await update.message.reply_text(
                    "האם זו הפעילות היחידה שלך?",
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return DIET  # Continue to diet questions

        return DIET
    return DIET


async def get_training_time(update: Update,
                            context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש לשעת האימון וממשיך לשאלה הבאה."""
    if update.message and update.message.text:
        training_time = update.message.text.strip()
        if training_time not in TRAINING_TIME_OPTIONS:
            keyboard = [[KeyboardButton(opt)] for opt in TRAINING_TIME_OPTIONS]
            try:
                await update.message.reply_text(
                    gendered_text("בחר שעה מהתפריט למטה:", "בחרי שעה מהתפריט למטה:", context),
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return TRAINING_TIME

        if context.user_data is None:
            context.user_data = {}
        context.user_data["training_time"] = training_time

        # Ask strength goal
        keyboard = [[KeyboardButton(opt)] for opt in STRENGTH_GOAL_OPTIONS]
        try:
            await update.message.reply_text(
                "מה המטרה?",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
        return STRENGTH_GOAL
    return TRAINING_TIME


async def get_cardio_goal(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש למטרת הפעילות האירובית וממשיך לתזונה."""
    if update.message and update.message.text:
        goal = update.message.text.strip()
        if goal not in CARDIO_GOAL_OPTIONS:
            keyboard = [[KeyboardButton(opt)] for opt in CARDIO_GOAL_OPTIONS]
            try:
                await update.message.reply_text(
                    gendered_text("בחר מטרה מהתפריט למטה:", "בחרי מטרה מהתפריט למטה:", context),
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return CARDIO_GOAL

        if context.user_data is None:
            context.user_data = {}
        context.user_data["cardio_goal"] = goal

        # Continue to next activity or diet
        return await continue_to_next_activity(update, context)
    return CARDIO_GOAL


async def get_strength_goal(update: Update,
                            context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש למטרת האימון וממשיך לשאלת תוספים."""
    if update.message and update.message.text:
        goal = update.message.text.strip()
        if goal not in STRENGTH_GOAL_OPTIONS:
            keyboard = [[KeyboardButton(opt)] for opt in STRENGTH_GOAL_OPTIONS]
            try:
                await update.message.reply_text(
                    gendered_text("בחר מטרה מהתפריט למטה:", "בחרי מטרה מהתפריט למטה:", context),
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return STRENGTH_GOAL

        if context.user_data is None:
            context.user_data = {}
        context.user_data["strength_goal"] = goal

        # Continue to next activity or diet
        return await continue_to_next_activity(update, context)
    return STRENGTH_GOAL


async def get_supplements(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש על תוספי תזונה וממשיך לשאלה הבאה."""
    if update.message and update.message.text:
        choice = update.message.text.strip()
        if choice not in ["כן", "לא"]:
            keyboard = [[KeyboardButton("כן"), KeyboardButton("לא")]]
            try:
                await update.message.reply_text(
                    gendered_text(context, "בחר כן או לא:", "בחרי כן או לא:"),
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return SUPPLEMENTS

        if context.user_data is None:
            context.user_data = {}
        context.user_data["takes_supplements"] = choice == "כן"

        if choice == "כן":
            # Ask for supplement types
            keyboard = [[KeyboardButton(opt)] for opt in SUPPLEMENT_OPTIONS]
            try:
                await update.message.reply_text(
                    "איזה תוספים את/ה לוקח/ת? (בחר/י כל מה שמתאים)",
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return SUPPLEMENT_TYPES
        else:
            # Continue to next activity or diet
            return await continue_to_next_activity(update, context)
    return SUPPLEMENTS


async def get_supplement_types(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """שואל את המשתמש לסוגי התוספים וממשיך לשאלת מגבלות."""
    if update.message and update.message.text:
        supplements_text = update.message.text.strip()

        # Parse selected supplements
        selected_supplements = []
        for option in SUPPLEMENT_OPTIONS:
            if option in supplements_text:
                selected_supplements.append(option)

        if context.user_data is None:
            context.user_data = {}
        context.user_data["supplements"] = selected_supplements

        # Continue to next activity or diet
        return await continue_to_next_activity(update, context)
    return SUPPLEMENT_TYPES


async def get_limitations(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש על מגבלות וממשיך לתזונה."""
    if update.message and update.message.text:
        limitations = update.message.text.strip()
        if context.user_data is None:
            context.user_data = {}
        if limitations.lower() in ["אין", "לא", "ללא"]:
            context.user_data["limitations"] = "אין"
        else:
            context.user_data["limitations"] = limitations

        # Continue to next activity or diet
        return await continue_to_next_activity(update, context)
    return LIMITATIONS


async def get_mixed_activities(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data is None:
        context.user_data = {}
    if "mixed_activities_selected" not in context.user_data:
        context.user_data["mixed_activities_selected"] = set()
    selected = context.user_data["mixed_activities_selected"]
    if update.message and update.message.text:
        text = update.message.text.strip().replace(" ❌", "")
        if text == "המשך":
            if not selected:
                if update.message:
                    try:
                        await update.message.reply_text(
                            gendered_text(context, "אנא בחר לפחות סוג פעילות אחד לפני ההמשך.", "אנא בחרי לפחות סוג פעילות אחד לפני ההמשך."),
                            reply_markup=ReplyKeyboardMarkup(build_mixed_activities_keyboard(selected), resize_keyboard=True),
                        )
                    except Exception as e:
                        logger.error("Telegram API error in reply_text: %s", e)
                return MIXED_ACTIVITIES
            context.user_data["mixed_activities"] = list(selected)
            del context.user_data["mixed_activities_selected"]
            return await get_mixed_frequency(update, context)
        elif text in MIXED_ACTIVITY_OPTIONS:
            if text in selected:
                selected.remove(text)
            else:
                selected.add(text)
        elif text == "אין":
            selected.clear()
            selected.add("אין")
    if update.message:
        try:
            await update.message.reply_text(
                gendered_text("בחר את סוגי הפעילות הגופנית שלך (לחיצה נוספת מבטלת בחירה):", "בחרי את סוגי הפעילות הגופנית שלך (לחיצה נוספת מבטלת בחירה):", context),
                reply_markup=ReplyKeyboardMarkup(build_mixed_activities_keyboard(selected), resize_keyboard=True),
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
    return MIXED_ACTIVITIES


async def get_mixed_frequency(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data is None:
        context.user_data = {}
    if update.message and update.message.text:
        text = update.message.text.strip()
        if text in MIXED_FREQUENCY_OPTIONS:
            context.user_data["mixed_frequency"] = text
            keyboard = [[KeyboardButton(opt)] for opt in MIXED_DURATION_OPTIONS]
            if update.message:
                try:
                    await update.message.reply_text(
                        "כמה זמן נמשך כל אימון בממוצע?",
                        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
                    )
                except Exception as e:
                    logger.error("Telegram API error in reply_text: %s", e)
            return MIXED_DURATION
    keyboard = [[KeyboardButton(opt)] for opt in MIXED_FREQUENCY_OPTIONS]
    if update.message:
        try:
            await update.message.reply_text(
                "כמה פעמים בשבוע את/ה מתאמן/ת?",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
    return MIXED_FREQUENCY


async def get_mixed_duration(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data is None:
        context.user_data = {}
    if update.message and update.message.text:
        text = update.message.text.strip()
        if text in MIXED_DURATION_OPTIONS:
            context.user_data["mixed_duration"] = text
            frequency = context.user_data.get("mixed_frequency", "")
            duration = context.user_data.get("mixed_duration", "")
            activities = context.user_data.get("mixed_activities", [])
            activity_summary = f"שילוב: {', '.join(activities)}, {frequency}, {duration}"
            context.user_data["activity"] = activity_summary
            return await get_mixed_menu_adaptation(update, context)
    keyboard = [[KeyboardButton(opt)] for opt in MIXED_DURATION_OPTIONS]
    if update.message:
        try:
            await update.message.reply_text(
                "כמה זמן נמשך כל אימון בממוצע?",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
    return MIXED_DURATION


def build_mixed_activities_keyboard(selected_activities):
    """בונה מקלדת לבחירת פעילויות מרובות."""
    keyboard = []
    for activity in MIXED_ACTIVITY_OPTIONS:
        if activity in selected_activities:
            keyboard.append([KeyboardButton(f"{activity} ❌")])
        else:
            keyboard.append([KeyboardButton(activity)])
    keyboard.append([KeyboardButton("המשך")])
    return keyboard


async def get_mixed_menu_adaptation(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if context.user_data is None:
        context.user_data = {}
    if update.message and update.message.text:
        choice = update.message.text.strip()
        if choice not in ["כן", "לא"]:
            keyboard = [[KeyboardButton("כן"), KeyboardButton("לא")]]
            try:
                await update.message.reply_text(
                    gendered_text(context, "בחר כן או לא:", "בחרי כן או לא:"),
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return MIXED_MENU_ADAPTATION
        context.user_data["menu_adaptation"] = choice == "כן"
        keyboard = [[KeyboardButton(opt)] for opt in DIET_OPTIONS]
        gender = context.user_data.get(
            "gender", "זכר") if context.user_data else "זכר"
        diet_text = (
            "מה העדפות התזונה שלך? (בחרי כל מה שמתאים)"
            if gender == "נקבה"
            else "מה העדפות התזונה שלך? (בחר/י כל מה שמתאים)"
        )
        try:
            await update.message.reply_text(
                diet_text,
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
        return DIET
    return ConversationHandler.END


async def get_diet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data is None:
        context.user_data = {}
    if update.message and update.message.text:
        diet_text = update.message.text.strip()
        if "selected_diet_options" not in context.user_data:
            context.user_data["selected_diet_options"] = []
        selected_options = context.user_data["selected_diet_options"]

        # Treat 'אין העדפות מיוחדות' as immediate finish
        if "אין העדפות מיוחדות" in diet_text:
            selected_options.clear()
            selected_options.append("אין העדפות מיוחדות")
            context.user_data["diet"] = selected_options
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
            diet_summary = ", ".join(selected_options)
            try:
                await update.message.reply_text(
                    f"העדפות התזונה שלך: {diet_summary}\n\n",
                    reply_markup=ReplyKeyboardRemove(),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            # המשך ישר לתפריט הראשי
            keyboard = [
                [KeyboardButton("לקבלת תפריט יומי מותאם אישית")],
                [KeyboardButton("מה אכלתי היום")],
                [KeyboardButton("בניית ארוחה לפי מה שיש לי בבית")],
                [KeyboardButton("קבלת דוח")],
                [KeyboardButton("תזכורות על שתיית מים")],
            ]
            gender = context.user_data.get("gender", "זכר")
            action_text = "מה תרצי לעשות כעת?" if gender == "נקבה" else "מה תרצה לעשות כעת?"
            try:
                await update.message.reply_text(
                    f"{action_text}",
                    reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return ConversationHandler.END

        # Check if user clicked "סיימתי בחירת העדפות"
        if "סיימתי בחירת העדפות" in diet_text:
            if not selected_options:
                selected_options = ["אין העדפות מיוחדות"]
            context.user_data["diet"] = selected_options
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
            diet_summary = ", ".join(selected_options)
            try:
                await update.message.reply_text(
                    f"העדפות התזונה שלך: {diet_summary}\n\n",
                    reply_markup=ReplyKeyboardRemove(),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            # המשך ישר לתפריט הראשי
            keyboard = [
                [KeyboardButton("לקבלת תפריט יומי מותאם אישית")],
                [KeyboardButton("מה אכלתי היום")],
                [KeyboardButton("בניית ארוחה לפי מה שיש לי בבית")],
                [KeyboardButton("קבלת דוח")],
                [KeyboardButton("תזכורות על שתיית מים")],
            ]
            gender = context.user_data.get("gender", "זכר")
            action_text = "מה תרצי לעשות כעת?" if gender == "נקבה" else "מה תרצה לעשות כעת?"
            try:
                await update.message.reply_text(
                    f"{action_text}",
                    reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return ConversationHandler.END
        # ... existing code ...

    # Handle individual diet options
    for option in DIET_OPTIONS:
        if option in diet_text:
            if option in selected_options:
                selected_options.remove(option)
            else:
                selected_options.append(option)
            context.user_data["selected_diet_options"] = selected_options
            keyboard = build_diet_keyboard(selected_options)
            gender = context.user_data.get("gender", "זכר")
            
            # Use gender-specific text
            if gender == "נקבה":
                diet_text_msg = gendered_text(
                    "מה העדפות התזונה שלך? (לחצי על אפשרות כדי לבחור או לבטל בחירה)",
                    "מה העדפות התזונה שלך? (לחצי על אפשרות כדי לבחור או לבטל בחירה)",
                    context)
            elif gender == "זכר":
                diet_text_msg = gendered_text(
                    "מה העדפות התזונה שלך? (לחץ על אפשרות כדי לבחור או לבטל בחירה)",
                    "מה העדפות התזונה שלך? (לחץ על אפשרות כדי לבחור או לבטל בחירה)",
                    context)
            else:
                diet_text_msg = gendered_text(
                    "מה העדפות התזונה שלך? (לחץ/י על אפשרות כדי לבחור או לבטל בחירה)",
                    "מה העדפות התזונה שלך? (לחץ/י על אפשרות כדי לבחור או לבטל בחירה)",
                    context)
                
            try:
                await update.message.reply_text(
                    diet_text_msg,
                    reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return DIET
            
    # If no valid option was selected, show error
    keyboard = build_diet_keyboard(selected_options)
    try:
        await update.message.reply_text(
            gendered_text("אנא בחר אפשרות מהתפריט למטה או לחץ על 'סיימתי בחירת העדפות'", "אנא בחרי אפשרות מהתפריט למטה או לחצי על 'סיימתי בחירת העדפות'", context),
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error("Telegram API error in reply_text: %s", e)
    return DIET


async def get_allergies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """שואל את המשתמש על אלרגיות - קודם כן/לא, ואז בחירה מרובה אם כן."""
    if context.user_data is None:
        context.user_data = {}
    
    # בדוק אם זה השלב הראשון (yes/no) או השני (multi-select)
    if "allergy_step" not in context.user_data:
        context.user_data["allergy_step"] = "yes_no"
    
    if context.user_data["allergy_step"] == "yes_no":
        return await get_allergies_yes_no(update, context)
    else:
        return await get_allergies_multi_select(update, context)


async def get_allergies_yes_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """שלב ראשון - שאלת כן/לא על אלרגיות."""
    if update.message and update.message.text:
        answer = update.message.text.strip()
        if answer not in ["כן", "לא"]:
            keyboard = [[KeyboardButton("כן"), KeyboardButton("לא")]]
            gender = context.user_data.get("gender", "זכר")
            if gender == "נקבה":
                error_text = "בחרי 'כן' או 'לא' מהתפריט למטה:"
            else:
                error_text = "בחר 'כן' או 'לא' מהתפריט למטה:"
            try:
                await update.message.reply_text(
                    error_text,
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return ALLERGIES
        
        if answer == "לא":
            context.user_data["allergies"] = []
            context.user_data["allergy_step"] = "yes_no"
            try:
                await update.message.reply_text(
                    "מעולה! נמשיך לשאלה הבאה...",
                    reply_markup=ReplyKeyboardRemove(),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            # המשך ישר לתפריט הראשי
            keyboard = [
                [KeyboardButton("לקבלת תפריט יומי מותאם אישית")],
                [KeyboardButton("מה אכלתי היום")],
                [KeyboardButton("בניית ארוחה לפי מה שיש לי בבית")],
                [KeyboardButton("קבלת דוח")],
                [KeyboardButton("תזכורות על שתיית מים")],
            ]
            gender = context.user_data.get("gender", "זכר")
            action_text = "מה תרצי לעשות כעת?" if gender == "נקבה" else "מה תרצה לעשות כעת?"
            try:
                await update.message.reply_text(
                    f"{action_text}",
                    reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return ConversationHandler.END
        
        else:  # answer == "כן"
            context.user_data["allergy_step"] = "multi_select"
            if "allergies" not in context.user_data:
                context.user_data["allergies"] = []
            keyboard = build_allergy_keyboard(context.user_data["allergies"])
            try:
                await update.message.reply_text(
                    "בחר/י את כל האלרגיות הרלוונטיות:",
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
            return ALLERGIES
    
    # אם אין הודעה - הצג את השאלה הראשונה
    keyboard = [[KeyboardButton("כן"), KeyboardButton("לא")]]
    gender = context.user_data.get("gender", "זכר")
    if gender == "נקבה":
        allergy_text = "האם יש לך אלרגיות למזון? (אם לא, בחרי 'לא')"
    else:
        allergy_text = "האם יש לך אלרגיות למזון? (אם לא, בחר 'לא')"
    
    try:
        await update.message.reply_text(
            allergy_text,
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error("Telegram API error in reply_text: %s", e)
    return ALLERGIES


async def get_allergies_multi_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """שלב שני - בחירה מרובה של אלרגיות."""
    if "allergies" not in context.user_data:
        context.user_data["allergies"] = []
    selected = context.user_data["allergies"]

    query = update.callback_query
    if not query:
        # שלב ראשון - שלח מקלדת
        keyboard = build_allergy_keyboard(selected)
        try:
            await update.message.reply_text(
                "בחר/י את כל האלרגיות הרלוונטיות:",
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
        return ALLERGIES

    # טיפול בלחיצות על כפתורים
    await query.answer()
    
    if query.data == "allergy_done":
        # המשתמש לחץ על "סיימתי" - המשך לשלב הבא
        try:
            await query.edit_message_text(
                "מעולה! עכשיו בואו נמשיך לשאלה הבאה...",
                reply_markup=InlineKeyboardMarkup([])
            )
        except Exception as e:
            logger.error("Telegram API error in edit_message_text: %s", e)
        # איפוס השלב לפעם הבאה
        context.user_data["allergy_step"] = "yes_no"
        # המשך ישר לתפריט הראשי
        keyboard = [
            [KeyboardButton("לקבלת תפריט יומי מותאם אישית")],
            [KeyboardButton("מה אכלתי היום")],
            [KeyboardButton("בניית ארוחה לפי מה שיש לי בבית")],
            [KeyboardButton("קבלת דוח")],
            [KeyboardButton("תזכורות על שתיית מים")],
        ]
        gender = context.user_data.get("gender", "זכר")
        action_text = "מה תרצי לעשות כעת?" if gender == "נקבה" else "מה תרצה לעשות כעת?"
        try:
            await query.message.reply_text(
                f"{action_text}",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
        return ConversationHandler.END
    
    elif query.data.startswith("allergy_toggle_"):
        # טוגל אלרגיה
        allergy = query.data.replace("allergy_toggle_", "")
        if allergy in selected:
            selected.remove(allergy)
        else:
            selected.append(allergy)
        context.user_data["allergies"] = selected
        
        # עדכן את המקלדת
        keyboard = build_allergy_keyboard(selected)
        try:
            await query.edit_message_reply_markup(reply_markup=keyboard)
        except Exception as e:
            logger.error("Telegram API error in edit_message_reply_markup: %s", e)
    
    return ALLERGIES


async def ask_water_reminder_opt_in(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    if context.user_data is None:
        context.user_data = {}
    keyboard = [[KeyboardButton("כן, אשמח!"), KeyboardButton("לא, תודה")]]
    gender = context.user_data.get("gender", "זכר")
    reminder_text = (
        "האם תרצי לקבל תזכורת לשתות מים כל שעה וחצי?"
        if gender == "נקבה"
        else "האם תרצה לקבל תזכורת לשתות מים כל שעה וחצי?"
    )
    if update.message:
        try:
            await update.message.reply_text(
                reminder_text,
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
    return WATER_REMINDER_OPT_IN


async def set_water_reminder_opt_in(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data is None:
        context.user_data = {}
    if not update.message or not update.message.text:
        return ConversationHandler.END
    choice = update.message.text.strip()
    user_id = update.effective_user.id if update.effective_user else None
    if choice == "כן, אשמח!":
        context.user_data["water_reminder_opt_in"] = True
        context.user_data["water_reminder_active"] = True
        if update.message:
            try:
                await update.message.reply_text(
                    gendered_text(
                        context,
                        "מעולה! אזכיר לך לשתות מים כל שעה וחצי עד שתסיים את היום.",
                        "מעולה! אזכיר לך לשתות מים כל שעה וחצי עד שתסיימי את היום.",
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
        if user_id:
            nutrition_db.save_user(user_id, context.user_data)
        asyncio.create_task(start_water_reminder_loop_with_buttons(update, context))
    else:
        context.user_data["water_reminder_opt_in"] = False
        context.user_data["water_reminder_active"] = False
        if update.message:
            try:
                await update.message.reply_text(
                    gendered_text(
                        context,
                        "אין בעיה! אפשר להפעיל תזכורות מים בכל שלב.",
                        "אין בעיה! אפשר להפעיל תזכורות מים בכל שלב.",
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
        if user_id:
            nutrition_db.save_user(user_id, context.user_data)

    keyboard = [
        [KeyboardButton("לקבלת תפריט יומי מותאם אישית")],
        [KeyboardButton("מה אכלתי היום")],
        [KeyboardButton("בניית ארוחה לפי מה שיש לי בבית")],
        [KeyboardButton("קבלת דוח")],
        [KeyboardButton("תזכורות על שתיית מים")],
    ]
    gender = context.user_data.get("gender", "זכר")
    action_text = "מה תרצי לעשות כעת?" if gender == "נקבה" else "מה תרצה לעשות כעת?"
    if update.message:
        try:
            await update.message.reply_text(
                action_text,
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
    return ConversationHandler.END


async def start_water_reminder_loop_with_buttons(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id if update.effective_user else None
    if context.user_data is None:
        context.user_data = {}
    while context.user_data.get("water_reminder_opt_in") and context.user_data.get(
            "water_reminder_active"):
        await asyncio.sleep(90 * 60)  # 1.5 hours
        if not context.user_data.get(
            "water_reminder_opt_in"
        ) or not context.user_data.get("water_reminder_active"):
            break
        try:
            if update.message:
                await send_water_reminder(update, context)
        except Exception as e:
            logger.error("Water reminder error: %s", e)
        if user_id:
            nutrition_db.save_user(user_id, context.user_data)


async def send_water_reminder(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    if context.user_data is None:
        context.user_data = {}
    user_id = update.effective_user.id if update.effective_user else None
    if user_id:
        nutrition_db.save_user(user_id, context.user_data)
    if update.message:
        try:
            await update.message.reply_text(
                gendered_text(
                    context,
                    "בסדר! הפסקתי להזכיר לך לשתות מים. אפשר להפעיל שוב בכל שלב.",
                    "בסדר! הפסקתי להזכיר לך לשתות מים. אפשר להפעיל שוב בכל שלב.",
                ),
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)


async def remind_in_10_minutes(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    if context.user_data is None:
        context.user_data = {}
    await asyncio.sleep(10 * 60)  # 10 minutes
    user_id = update.effective_user.id if update.effective_user else None
    if user_id:
        nutrition_db.save_user(user_id, context.user_data)
    if update.message:
        try:
            await update.message.reply_text(
                gendered_text(
                    context,
                    "זכור לשתות מים! 💧",
                    "זכרי לשתות מים! 💧",
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)


async def cancel_water_reminders(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    if context.user_data is None:
        context.user_data = {}
    context.user_data["water_reminder_active"] = False
    user_id = update.effective_user.id if update.effective_user else None
    if user_id:
        nutrition_db.save_user(user_id, context.user_data)
    if update.message:
        try:
            await update.message.reply_text(
                gendered_text(
                    context,
                    "בסדר! הפסקתי להזכיר לך לשתות מים. אפשר להפעיל שוב בכל שלב.",
                    "בסדר! הפסקתי להזכיר לך לשתות מים. אפשר להפעיל שוב בכל שלב.",
                ),
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)


async def water_intake_start(update: Update,
                             context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data is None:
        context.user_data = {}
    keyboard = [
        [KeyboardButton('כוס אחת (240 מ"ל)'), KeyboardButton('שתי כוסות (480 מ"ל)')],
        [KeyboardButton('בקבוק קטן (500 מ"ל)'), KeyboardButton("בקבוק גדול (1 ליטר)")],
        [KeyboardButton("אחר")],
    ]
    if update.message:
        try:
            await update.message.reply_text(
                "כמה מים שתית?",
                reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
    return WATER_REMINDER_OPT_IN


async def water_intake_amount(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if context.user_data is None:
        context.user_data = {}
    amount_map = {
        'כוס אחת (240 מ"ל)': 240,
        'שתי כוסות (480 מ"ל)': 480,
        'בקבוק קטן (500 מ"ל)': 500,
        "בקבוק גדול (1 ליטר)": 1000,
    }
    if "water_today" not in context.user_data:
        context.user_data["water_today"] = 0
    if not update.message or not update.message.text:
        return ConversationHandler.END
    amount_text = update.message.text.strip()
    if amount_text in amount_map:
        amount = amount_map[amount_text]
    elif amount_text.isdigit():
        amount = int(amount_text)
    else:
        if update.message:
            try:
                await update.message.reply_text(
                    'הזן כמות במ"ל (למשל: 300):',
                    reply_markup=ReplyKeyboardRemove(),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
        return WATER_REMINDER_OPT_IN
    context.user_data["water_today"] += amount
    if update.message:
        try:
            await update.message.reply_text(
                f'כל הכבוד! שתית {amount} מ"ל מים. סה"כ היום: {context.user_data["water_today"]} מ"ל',
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
    return ConversationHandler.END


async def show_daily_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data is None:
        context.user_data = {}
    keyboard = [
        [KeyboardButton("מה אכלתי")],
        [KeyboardButton("סיימתי")],
        [KeyboardButton("עריכה")],
    ]
    user = context.user_data
    gender = user.get("gender", "male")
    action_text = GENDERED_ACTION["female"] if gender == "female" else GENDERED_ACTION["male"]
    if update.message:
        try:
            await update.message.reply_text(
                action_text,
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
    return DAILY


async def daily_menu(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data is None:
        context.user_data = {}
    if update.message:
        try:
            await update.message.reply_text("רגע, בונה עבורך תפריט...")
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
    if update.message and update.message.text:
        choice = update.message.text.strip()
        if choice == "סיימתי":
            await send_summary(update, context)
            return SCHEDULE
        else:
            return await eaten(update, context)
    return DAILY


async def eaten(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data is None:
        context.user_data = {}
    user = context.user_data
    gender = user.get("gender", "זכר")
    
    # Check if this is the first call (asking for food input)
    if not user.get("eaten_prompted", False):
        if update.message:
            if gender == "נקבה":
                prompt = "אשמח שתפרטי מה אכלת היום, בצורה הבאה: ביצת עין, 2 פרוסות לחם לבן עם גבינה לבנה 5%, סלט ירקות ממלפפון ועגבנייה"
            elif gender == "זכר":
                prompt = "אשמח שתפרט מה אכלת היום, בצורה הבאה: ביצת עין, 2 פרוסות לחם לבן עם גבינה לבנה 5%, סלט ירקות ממלפפון ועגבנייה"
            else:
                prompt = "אשמח שתפרט/י מה אכלת היום, בצורה הבאה: ביצת עין, 2 פרוסות לחם לבן עם גבינה לבנה 5%, סלט ירקות ממלפפון ועגבנייה"
            try:
                await update.message.reply_text(
                    prompt, reply_markup=ReplyKeyboardRemove(), parse_mode="HTML"
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
        user["eaten_prompted"] = True
        return EATEN
    
    # Process food input
    if update.message and update.message.text:
        food_text = update.message.text.strip()
        
        try:
            # Use GPT to process the food input
            user_id = update.effective_user.id if update.effective_user else None
            calorie_budget = user.get("calorie_budget", 1800)
            total_eaten = sum(e["calories"] for e in user.get("eaten_today", []))
            remaining = calorie_budget - total_eaten
            diet = ", ".join(user.get("diet", []))
            allergies = ", ".join(user.get("allergies", []))
            eaten_today = ", ".join(
                [clean_desc(e["desc"]) for e in user.get("eaten_today", [])]
            )
            
            prompt = f"""המשתמש/ת כתב/ה: "{food_text}"

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

            response = await call_gpt(prompt)
            
            if response:
                try:
                    await update.message.reply_text(response, parse_mode="HTML")
                    
                    # Try to extract calories from GPT response
                    calorie_match = re.search(r"(\d+)\s*קלוריות?", response)
                    if calorie_match:
                        calories = int(calorie_match.group(1))
                        if "eaten_today" not in user:
                            user["eaten_today"] = []
                        user["eaten_today"].append({"desc": food_text, "calories": calories})
                        user["remaining_calories"] = remaining - calories
                        
                        # Save to database
                        if user_id:
                            nutrition_db.save_user(user_id, user)
                except Exception as e:
                    logger.error("Error processing food input: %s", e)
                    try:
                        await update.message.reply_text(
                            "תודה על הדיווח! עיבדתי את המידע.",
                            parse_mode="HTML",
                        )
                    except Exception as e:
                        logger.error("Telegram API error in reply_text: %s", e)
            else:
                try:
                    await update.message.reply_text(
                        "תודה על הדיווח! עיבדתי את המידע.",
                        parse_mode="HTML",
                    )
                except Exception as e:
                    logger.error("Telegram API error in reply_text: %s", e)
                
        except Exception as e:
            logger.error("Error processing food input: %s", e)
            try:
                await update.message.reply_text(
                    "תודה על הדיווח! עיבדתי את המידע.",
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
    
    return EATEN


async def handle_daily_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if context.user_data is None:
        context.user_data = {}
    if not update.message or not update.message.text:
        return MENU
    choice = update.message.text.strip()
    if choice == "לקבלת תפריט יומי מותאם אישית":
        await generate_personalized_menu(update, context)
        # הסר את כפתור התפריט היומי עד מחר או עד 'סיימתי'
        if update.message:
            await update.message.reply_text(
                gendered_text("התפריט היומי נשלח. כפתור זה יופיע שוב מחר.", "התפריט היומי נשלח. כפתור זה יופיע שוב מחר.", context),
                reply_markup=build_main_keyboard(hide_menu_button=True),
            )
        return MENU
    elif choice == "סיימתי":
        await send_summary(update, context)
        if update.message:
            await update.message.reply_text(
                gendered_text("היום אופס. מחכה לעדכן אותך מחר!", "היום אופס. מחכה לעדכן אותך מחר!", context),
                reply_markup=ReplyKeyboardRemove(),
            )
        # TODO: reset daily data here
        return MENU
    elif choice == "קבלת דוח":
        keyboard = [
            [InlineKeyboardButton("📊 סיכום יומי", callback_data="report_daily")],
            [InlineKeyboardButton("📅 סיכום שבועי", callback_data="report_weekly")],
            [InlineKeyboardButton("🗓 סיכום חודשי", callback_data="report_monthly")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.message:
            await update.message.reply_text(
                gendered_text("📊 בחר סוג דוח:", "📊 בחרי סוג דוח:", context),
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
        if update.message:
            await update.message.reply_text(
                gendered_text("בחר פעולה נוספת:", "בחרי פעולה נוספת:", context),
                reply_markup=build_main_keyboard(),
            )
        return MENU
    elif choice == "עדכון פרטים אישיים":
        await handle_update_personal_details(update, context)
        if update.message:
            await update.message.reply_text(
                gendered_text("הפרטים אופסו. נתחיל מחדש!", "הפרטים אופסו. נתחיל מחדש!", context),
                reply_markup=ReplyKeyboardRemove(),
            )
        # TODO: start questionnaire again
        return MENU
    else:
        return await eaten(update, context)


async def send_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data is None:
        context.user_data = {}
    user = context.user_data
    food_log = user.get("daily_food_log", [])
    calorie_budget = user.get("calorie_budget", 0)
    calories_consumed = user.get("calories_consumed", 0)
    # פירוט ארוחות עיקריות
    if food_log:
        eaten_lines = [f"• <b>{item['name']}</b> (<b>{item['calories']}</b> קלוריות)" for item in food_log]
        eaten = "\n".join(eaten_lines)
        total_eaten = sum(item["calories"] for item in food_log)
    else:
        eaten = "לא דווח"
        total_eaten = 0
    remaining = calorie_budget - total_eaten
    if remaining < 0:
        remaining = 0
    if total_eaten <= calorie_budget:
        budget_status = "✅ עמדת בתקציב!"
    else:
        budget_status = "⚠️ חרגת מהתקציב."
    # בקשת המלצה ליום הבא מ-GPT
    try:
        prompt = f"המשתמש/ת צרך/ה היום {total_eaten} קלוריות מתוך תקציב של {calorie_budget}. תן המלצה קצרה ליום מחר (ב-1-2 משפטים, בעברית, ללא פתיח אישי)."
        from utils import call_gpt
        recommendation = await call_gpt(prompt)
    except Exception as e:
        logger.error(f"Error getting next day recommendation: {e}")
        recommendation = ""
    # שלב 1: שליחת סיכום
    summary = (
        f'<b>סיכום יומי:</b>\n{eaten}\n\n'
        f'<b>סה\'כ נאכל:</b> <b>{total_eaten}</b> קלוריות\n'
        f'<b>נשארו:</b> <b>{remaining}</b> קלוריות להיום.\n'
        f'{budget_status}\n\n'
        f'<b>המלצה למחר:</b> {recommendation}'
    )
    if update.message:
        try:
            await update.message.reply_text(summary, parse_mode="HTML")
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
    # שלב 2: שאלה על שעת שליחת תפריט יומי
    hour_buttons = [
        [KeyboardButton("06:00"), KeyboardButton("07:00")],
        [KeyboardButton("08:00"), KeyboardButton("09:00")],
        [KeyboardButton("מעדיפה לבקש לבד")],
    ]
    gender = user.get("gender", "נקבה")
    ask_time_text = gendered_text(
        "באיזו שעה לשלוח לך את התפריט היומי מחר?",
        "באיזו שעה לשלוח לך את התפריט היומי מחר?",
        context
    )
    if update.message:
        try:
            await update.message.reply_text(
                ask_time_text,
                reply_markup=ReplyKeyboardMarkup(hour_buttons, resize_keyboard=True),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
    # שלב 3: איפוס יומי
    user["daily_food_log"] = []
    user["calories_consumed"] = 0
    # עדכון תאריך ביומן צריכה (אם יש)
    from datetime import date
    user["last_reset_date"] = date.today().isoformat()
    user_id = update.effective_user.id if update.effective_user else None
    if user_id:
        nutrition_db.save_user(user_id, user)
    # שלב 4: פידבק חיובי
    feedback = gendered_text(
        "כל הכבוד שסיימת את היום! 💪",
        "כל הכבוד שסיימת את היום! 💪",
        context
    )
    if update.message:
        try:
            await update.message.reply_text(feedback, parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
    # שלב 5: שלח pin חדש לתקציב
    try:
        chat = update.effective_chat
        calorie_msg = f"📌 תקציב הקלוריות היומי שלך: {calorie_budget} קלוריות"
        calorie_message = await update.message.reply_text(calorie_msg)
        await pin_single_message(chat, calorie_message.message_id)
    except Exception as e:
        logger.error(f"Error sending or pinning calorie budget message: {e}")


async def schedule_menu(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data is None:
        context.user_data = {}
    if not update.message or not update.message.text:
        return SCHEDULE
    time = update.message.text.strip()
    user_id = update.effective_user.id if update.effective_user else None
    if time in ["06:00", "07:00", "08:00", "09:00"]:
        context.user_data["preferred_menu_hour"] = time
        context.user_data["daily_menu_enabled"] = True
        msg = gendered_text(
            f"מעולה! אשלח לך תפריט חדש כל יום בשעה {time}.",
            f"מעולה! אשלח לך תפריט חדש כל יום בשעה {time}.",
            context
        )
    else:
        context.user_data["preferred_menu_hour"] = None
        context.user_data["daily_menu_enabled"] = False
        msg = gendered_text(
            "לא אשלח תפריט אוטומטי. אפשר לבקש תפריט יומי בכל עת מהתפריט הראשי.",
            "לא אשלח תפריט אוטומטי. אפשר לבקש תפריט יומי בכל עת מהתפריט הראשי.",
            context
        )
    # תיעוד במסד
    if user_id:
        from datetime import datetime
        context.user_data["last_menu_schedule_update"] = datetime.now().isoformat()
        nutrition_db.save_user(user_id, context.user_data)
    if update.message:
        try:
            await update.message.reply_text(
                msg,
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
    return ConversationHandler.END


async def check_dessert_permission(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if context.user_data is None:
        context.user_data = {}
    if not update.message or not update.message.text:
        return ConversationHandler.END
    choice = update.message.text.strip()
    if choice == "כן":
        context.user_data["dessert_allowed"] = True
    else:
        context.user_data["dessert_allowed"] = False
    return ConversationHandler.END


async def after_questionnaire(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if context.user_data is None:
        context.user_data = {}
    return ConversationHandler.END


def classify_text_input(text: str) -> str:
    """מסווג טקסט חופשי לקטגוריות."""
    text_lower = text.lower().strip()

    # בדיקה אם זו שאלה
    question_words = ["מה", "האם", "כמה", "איך", "מתי", "איפה", "למה", "מי"]
    if any(
        text_lower.startswith(word) for word in question_words
    ) or text_lower.endswith("?"):
        return "question"

    # בדיקה אם זו רשימת מאכלים (פסיקים או ריבוי מילים מוכרות)
    food_words = [
        "לחם",
        "חלב",
        "ביצה",
        "עוף",
        "בשר",
        "דג",
        "אורז",
        "פסטה",
        "תפוח",
        "בננה",
        "עגבניה",
        "מלפפון",
        "גזר",
        "בטטה",
        "תות",
        "ענבים",
        "אבוקדו",
        "שקדים",
        "אגוזים",
        "יוגורט",
        "גבינה",
        "קוטג",
        "חמאה",
        "שמן",
        "מלח",
        "פלפל",
        "סוכר",
        "קפה",
        "תה",
        "מים",
        "מיץ",
        "חלב",
        "שוקו",
        "גלידה",
        "עוגה",
        "ביסקוויט",
        "קרקר",
        "חטיף",
        "שוקולד",
        "ממתק",
        "פיצה",
        "המבורגר",
        "סושי",
        "סלט",
        "מרק",
        "קציצה",
        "שניצל",
        "סטייק",
        "פאייה",
        "פסטה",
    ]

    words = text_lower.split()
    food_word_count = sum(1 for word in words if word in food_words)

    # אם יש פסיקים או ריבוי מילים מוכרות
    if "," in text or "ו" in text or food_word_count >= 2:
        return "food_list"

    # אם יש מילה אחת מוכרת
    if food_word_count == 1 and len(words) <= 3:
        return "food_list"

    return "other"


async def handle_free_text_input(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """מטפל בקלט טקסט חופשי - מזהה צריכת מזון ושאלות כלליות."""
    if not update.message or not update.message.text:
        return
    
    text = update.message.text.strip()
    
    # זיהוי משפטים שמתחילים ב"אכלתי"
    if text.startswith("אכלתי") or text.startswith("אכלתי ") or "אכלתי" in text[:10]:
        # זהו צריכת מזון - עדכן את יומן הצריכה
        await handle_food_consumption(update, context, text)
        return
    
    # זיהוי שאלות על קלוריות
    if any(keyword in text.lower() for keyword in ["כמה קלוריות", "קלוריות", "תזונה", "בריא", "משקל"]):
        # זהו שאלה כללית - הפנה ל-GPT
        await handle_nutrition_question(update, context, text)
        return
    
    # אם זה לא מזוהה - שלח הודעה כללית
    try:
        await update.message.reply_text(
            "אני לא מבין את הבקשה. אפשר לכתוב:\n"
            "• 'אכלתי [מה אכלת]' - לרישום מזון\n"
            "• שאלות על תזונה וקלוריות\n"
            "• או להשתמש בתפריט למטה",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error("Telegram API error in reply_text: %s", e)

    # כל טקסט חופשי אחר – שלח ל-GPT עם פרומפט מלא
    try:
        from utils import build_user_prompt_for_gpt, call_gpt
        user_data = context.user_data or {}
        # בנה פרומפט מותאם לשאלה חופשית
        prompt = build_free_text_prompt(user_data, text)
        # שלח הודעת המתנה
        await update.message.reply_text("חושב על תשובה... ⏳")
        response = await call_gpt(prompt)
        if response:
            await update.message.reply_text(response, parse_mode=None)
        else:
            await update.message.reply_text(
                "לא הצלחתי למצוא תשובה לשאלה שלך. נסה לשאול בצורה אחרת.",
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Error handling free text input: {e}")
        try:
            await update.message.reply_text(
                "אירעה שגיאה בעיבוד הבקשה. נסה שוב.",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)


async def handle_food_consumption(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    from utils import analyze_meal_with_gpt
    if context.user_data is None:
        context.user_data = {}
    food_desc = text.replace("אכלתי", "").strip()
    if not food_desc:
        try:
            await update.message.reply_text(
                "מה אכלת? אנא פרט את המזון שאכלת.",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)
        return
    user_id = update.effective_user.id if update.effective_user else None
    if user_id:
        try:
            meal_data = await analyze_meal_with_gpt(food_desc)
            items = meal_data.get("items", [])
            total = meal_data.get("total", 0)
            # עדכון יומן הארוחות, בלי כפילויות
            if "daily_food_log" not in context.user_data:
                context.user_data["daily_food_log"] = []
            for item in items:
                if not any(x["name"] == item["name"] and x["calories"] == item["calories"] for x in context.user_data["daily_food_log"]):
                    context.user_data["daily_food_log"].append({
                        "name": item["name"],
                        "calories": item["calories"],
                        "timestamp": datetime.now().isoformat(),
                    })
            # עדכון התקציב
            current_budget = context.user_data.get("calorie_budget", 0)
            if "calories_consumed" not in context.user_data:
                context.user_data["calories_consumed"] = 0
            consumed_before = context.user_data["calories_consumed"]
            context.user_data["calories_consumed"] += total
            consumed_after = context.user_data["calories_consumed"]
            remaining_budget = current_budget - consumed_after
            if remaining_budget < 0:
                remaining_budget = 0
            # שמור למסד נתונים
            nutrition_db.save_user(user_id, context.user_data)
            # בנה הודעת פירוט ארוחה
            meal_lines = [f"{item['name']} – {item['calories']} קלוריות" for item in items]
            meal_text = "\n".join(meal_lines)
            meal_summary = (
                f"🍽️ חישוב קלורי לארוחה:\n\n"
                f"{meal_text}\n"
                f"סה\"כ לארוחה: {total} קלוריות"
            )
            # בנה הודעת מצב יומי (ללא השורה האחרונה)
            daily_status = (
                f"📊 מצב יומי:\n\n"
                f"צריכה עד עכשיו: {consumed_before} קלוריות\n"
                f"תוספת מהארוחה הנוכחית: {total} קלוריות\n"
                f"סה\"כ עד כה: {consumed_after} קלוריות\n\n"
                f"היעד היומי שלי: {current_budget} קלוריות"
            )
            # בנה הודעה נפרדת לתקציב שנותר
            remaining_msg = f"🔄 נותרו לי להיום: {remaining_budget} קלוריות"
            # שלח הודעות
            await update.message.reply_text(meal_summary)
            await update.message.reply_text(daily_status)
            # שלח הודעת תקציב נפרדת וצמד אותה
            try:
                chat = update.effective_chat
                # הסר pin קיים
                try:
                    await chat.unpin_all_messages()
                except Exception as e:
                    logger.error(f"Error unpinning messages: {e}")
                # שלח הודעת תקציב חדשה וצמד אותה
                remaining_message = await update.message.reply_text(remaining_msg)
                await chat.pin_message(remaining_message.message_id)
            except Exception as e:
                logger.error(f"Error sending or pinning calorie budget message: {e}")
        except Exception as e:
            logger.error(f"Error saving food consumption: {e}")
            try:
                await update.message.reply_text(
                    "אירעה שגיאה ברישום המזון. נסה שוב.",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)


async def handle_nutrition_question(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """מטפל בשאלות תזונה כלליות באמצעות GPT."""
    try:
        # שלח הודעת המתנה
        await update.message.reply_text("מחפש תשובה... ⏳")
        
        # בנה פרומפט לשאלה
        prompt = f"""המשתמש/ת שואל/ת: {text}

אנא ענה בקצרה בעברית, בצורה ברורה ומדויקת.
התמקד בתשובה ישירה לשאלה.
אם השאלה על קלוריות - תן ערכים מדויקים.
אם השאלה על בריאות - תן עצה קצרה ומעשית."""

        # קבל תשובה מ-GPT
        response = await call_gpt(prompt)
        
        if response:
            try:
                await update.message.reply_text(
                    response,
                    parse_mode=None
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
        else:
            try:
                await update.message.reply_text(
                    "לא הצלחתי למצוא תשובה לשאלה שלך. נסה לשאול בצורה אחרת.",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)
                
    except Exception as e:
        logger.error(f"Error handling nutrition question: {e}")
        try:
            await update.message.reply_text(
                "אירעה שגיאה בחיפוש התשובה. נסה שוב.",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)


async def estimate_food_calories(food_desc: str) -> int:
    """מעריך קלוריות למזון באמצעות GPT."""
    try:
        prompt = f"""הערך את הקלוריות במזון הבא: {food_desc}

תן רק מספר קלוריות מדויק (למשל: 250).
אל תוסיף טקסט נוסף, רק מספר."""

        response = await call_gpt(prompt)
        
        if response:
            # חלץ מספר מהתשובה
            import re
            numbers = re.findall(r'\d+', response)
            if numbers:
                return int(numbers[0])
        
        # אם לא הצליח - החזר ערך ברירת מחדל
        return 200
        
    except Exception as e:
        logger.error(f"Error estimating calories: {e}")
        return 200


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data is None:
        context.user_data = {}
    help_text = """
🤖 <b>עזרה - בוט התזונה קלוריקו</b>

<b>פקודות זמינות:</b>
/start - התחלת הבוט
/help - הצגת עזרה זו

<b>פונקציות עיקריות:</b>
• שאלון התאמה אישית
• תפריטים יומיים מותאמים
• מעקב אחרי ארוחות
• תזכורות שתיית מים
• דוחות תזונתיים

<b>תמיכה:</b>
אם יש לך שאלות, פשוט כתוב לי!
    """
    if update.message:
        try:
            await update.message.reply_text(help_text, parse_mode="HTML")
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)


async def generate_personalized_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    user_data = context.user_data or {}

    if not update.message:
        return

    try:
        # שלח הודעת המתנה מיד
        try:
            await update.message.reply_text("מכין לך את התפריט היומי... רגע... ⏳")
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)

        # שלח הודעת תקציב קלוריות יומי לפני התפריט
        calorie_budget = user_data.get('calorie_budget', 0)
        if calorie_budget and update.message:
            try:
                calorie_msg = f"📊 תקציב הקלוריות היומי שלך: {calorie_budget} קלוריות"
                calorie_message = await update.message.reply_text(calorie_msg, parse_mode=None)
                # הצמד את ההודעה לראש השיחה
                await calorie_message.pin()
            except Exception as e:
                logger.error(f"Error sending or pinning calorie budget message: {e}")

        # בניית פרומפט מותאם אישית
        prompt = build_user_prompt_for_gpt(user_data)

        # שליחת פרומפט ל-GPT
        response = await call_gpt(prompt)

        if response:
            # המר HTML לטקסט פשוט
            import re
            # הסר תגיות HTML
            response = re.sub(r'<[^>]+>', '', response)
            # החלף תגיות כותרת בטקסט פשוט
            response = re.sub(r'<h[1-6][^>]*>(.*?)</h[1-6]>', r'\1\n', response, flags=re.IGNORECASE)
            # החלף תגיות רשימה
            response = re.sub(r'<li[^>]*>(.*?)</li>', r'• \1', response, flags=re.IGNORECASE)
            response = re.sub(r'<ul[^>]*>|</ul>|<ol[^>]*>|</ol>', '\n', response, flags=re.IGNORECASE)
            # נקה רווחים כפולים
            response = re.sub(r'\n\s*\n', '\n\n', response)
            response = response.strip()

            # שליחת התפריט למשתמש
            menu_text = response
            try:
                await update.message.reply_text(
                    menu_text,
                    parse_mode=None,
                    disable_web_page_preview=True
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)

        # שמירה למסד נתונים
        user_id = update.effective_user.id if update.effective_user else None
        logger.info("About to save user data - user_id: %s, context.user_data keys: %s", user_id, list(context.user_data.keys()) if context.user_data else 'None')
        if user_id:
            try:
                user_data["last_menu"] = menu_text
                user_data["last_menu_date"] = date.today().isoformat()
                nutrition_db.save_user(user_id, user_data)
            except Exception as db_error:
                logger.error("Error saving menu to database: %s", db_error)
        else:
            try:
                await update.message.reply_text(
                    gendered_text("אירעה תקלה בבניית התפריט 😔 נסה שוב בעוד רגע.", "אירעה תקלה בבניית התפריט 😔 נסי שוב בעוד רגע.", context),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error("Telegram API error in reply_text: %s", e)

    except Exception as e:
        logger.error("Error generating personalized menu: %s", e)
        try:
            await update.message.reply_text(
                gendered_text("אירעה תקלה בבניית התפריט 😔 נסה שוב בעוד רגע.", "אירעה תקלה בבניית התפריט 😔 נסי שוב בעוד רגע.", context),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error("Telegram API error in reply_text: %s", e)


def build_activity_types_keyboard(selected_types: list = None) -> InlineKeyboardMarkup:
    """בונה inline keyboard לבחירת סוגי פעילות מרובים."""
    if selected_types is None:
        selected_types = []
    
    keyboard = []
    for activity in ACTIVITY_TYPES_MULTI:
        # השתמש בטקסט המלא של הפעילות ב-callback_data
        activity_clean = activity.replace(" ", "_").replace("🏃", "").replace("🚶", "").replace("🚴", "").replace("🏊", "").replace("🏋️", "").replace("🧘", "").replace("🤸", "").replace("❓", "").strip()
        
        if activity in selected_types:
            # אם נבחר - הצג עם ❌
            text = f"{activity} ❌"
            callback_data = f"activity_remove_{activity_clean}"
        else:
            # אם לא נבחר - הצג עם האימוג'י המקורי
            text = activity
            callback_data = f"activity_add_{activity_clean}"
        
        keyboard.append([InlineKeyboardButton(text, callback_data=callback_data)])
    
    # כפתור "סיימתי" - מופיע רק אם יש לפחות בחירה אחת
    if selected_types:
        keyboard.append([InlineKeyboardButton("סיימתי", callback_data="activity_done")])
    
    return InlineKeyboardMarkup(keyboard)


async def handle_activity_types_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """מטפל בבחירת סוגי פעילות מרובים."""
    if not update.callback_query:
        return ACTIVITY_TYPES_SELECTION
    
    query = update.callback_query
    await query.answer()
    
    if context.user_data is None:
        context.user_data = {}
    
    # אתחל רשימת סוגי פעילות אם לא קיימת
    if "activity_types" not in context.user_data:
        context.user_data["activity_types"] = []
    
    selected_types = context.user_data["activity_types"]
    
    if query.data == "activity_done":
        # המשתמש סיים בחירה - המשך לשלב הבא
        if not selected_types:
            # אם לא נבחר כלום, חזור לתפריט עם הודעת שגיאה
            keyboard = build_activity_types_keyboard(selected_types)
            try:
                await query.edit_message_text(
                    "יש לבחור לפחות סוג פעילות אחד לפני המשך.",
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error("Telegram API error in edit_message_text: %s", e)
            return ACTIVITY_TYPES_SELECTION
        # נסה להסתיר את המקלדת אם יש אחת
        try:
            if query.message.reply_markup:
                try:
                    await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup([]))
                except telegram.error.BadRequest as e:
                    logging.warning("Could not edit markup: %s", e)
        except Exception as e:
            logging.warning("Unexpected error hiding keyboard: %s", e)
        # המשך לשאלות הספציפיות לכל סוג פעילות
        return await process_activity_types(update, context)
    
    elif query.data.startswith("activity_add_"):
        # הוסף סוג פעילות
        activity_clean = query.data.replace("activity_add_", "")
        for activity in ACTIVITY_TYPES_MULTI:
            activity_clean_check = activity.replace(" ", "_").replace("🏃", "").replace("🚶", "").replace("🚴", "").replace("��", "").replace("🏋️", "").replace("🧘", "").replace("🤸", "").replace("❓", "").strip()
            if activity_clean_check == activity_clean:
                if activity not in selected_types:
                    selected_types.append(activity)
                    context.user_data["activity_types"] = selected_types
                    # שלח הודעה מהצד של המשתמש
                    try:
                        await query.message.reply_text(f"בחרת: {activity}")
                    except Exception as e:
                        logger.error("Telegram API error in reply_text: %s", e)
                break
    
    elif query.data.startswith("activity_remove_"):
        # הסר סוג פעילות
        activity_clean = query.data.replace("activity_remove_", "")
        for activity in ACTIVITY_TYPES_MULTI:
            activity_clean_check = activity.replace(" ", "_").replace("🏃", "").replace("🚶", "").replace("🚴", "").replace("🏊", "").replace("🏋️", "").replace("🧘", "").replace("🤸", "").replace("❓", "").strip()
            if activity_clean_check == activity_clean:
                if activity in selected_types:
                    selected_types.remove(activity)
                    context.user_data["activity_types"] = selected_types
                    # שלח הודעה מהצד של המשתמש
                    try:
                        await query.message.reply_text(f"הסרת: {activity}")
                    except Exception as e:
                        logger.error("Telegram API error in reply_text: %s", e)
                break
    
    # עדכן את התפריט
    keyboard = build_activity_types_keyboard(selected_types)
    try:
        await query.edit_message_reply_markup(reply_markup=keyboard)
    except Exception as e:
        logger.error("Telegram API error in edit_message_reply_markup: %s", e)
    
    return ACTIVITY_TYPES_SELECTION


async def process_activity_types(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """מעבד את סוגי הפעילות שנבחרו ועובר לשאלות הספציפיות."""
    if context.user_data is None:
        context.user_data = {}
    
    selected_types = context.user_data.get("activity_types", [])
    if not selected_types:
        # אם אין בחירות, המשך לתזונה
        keyboard = [[KeyboardButton(opt)] for opt in DIET_OPTIONS]
        gender = context.user_data.get("gender", "זכר")
        if gender == "נקבה":
            diet_text = "מה העדפות התזונה שלך? (בחרי כל מה שמתאים)"
        elif gender == "זכר":
            diet_text = "מה העדפות התזונה שלך? (בחר כל מה שמתאים)"
        else:
            diet_text = "מה העדפות התזונה שלך? (בחר/י כל מה שמתאים)"
        try:
            if update.callback_query:
                await update.callback_query.message.reply_text(
                    diet_text,
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
            elif update.message:
                await update.message.reply_text(
                    diet_text,
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
        except Exception as e:
            logger.error("Telegram API error in process_activity_types: %s", e)
        return DIET
    
    # שמור את הסוג הראשון לעיבוד
    current_activity = selected_types[0]
    context.user_data["current_activity_index"] = 0
    context.user_data["current_activity"] = current_activity
    # עבור לשאלות הספציפיות לסוג הפעילות הנוכחי
    return await route_to_activity_questions(update, context, current_activity)


async def route_to_activity_questions(update: Update, context: ContextTypes.DEFAULT_TYPE, activity_type: str) -> int:
    """מנתב לשאלות הספציפיות לסוג הפעילות."""
    # הסר אימוג'ים מהטקסט לצורך השוואה
    activity_clean = activity_type.replace("🏃", "").replace("🚶", "").replace("🚴", "").replace("🏊", "").replace("🏋️", "").replace("🧘", "").replace("🤸", "").replace("❓", "").strip()
    
    if activity_clean == "ריצה":
        keyboard = [[KeyboardButton(opt)] for opt in ACTIVITY_FREQUENCY_OPTIONS]
        gender = context.user_data.get("gender", "זכר")
        if gender == "נקבה":
            frequency_text = "כמה פעמים בשבוע את רצה?"
        elif gender == "זכר":
            frequency_text = "כמה פעמים בשבוע אתה רץ?"
        else:
            frequency_text = "כמה פעמים בשבוע את/ה רץ/ה?"
        try:
            if update.callback_query:
                await update.callback_query.message.reply_text(
                    frequency_text,
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
            elif update.message:
                await update.message.reply_text(
                    frequency_text,
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
        except Exception as e:
            logger.error("Telegram API error in route_to_activity_questions: %s", e)
        return ACTIVITY_FREQUENCY
    
    elif activity_clean == "אימוני כוח":
        keyboard = [[KeyboardButton(opt)] for opt in ACTIVITY_FREQUENCY_OPTIONS]
        gender = context.user_data.get("gender", "זכר")
        if gender == "נקבה":
            frequency_text = "כמה פעמים בשבוע את מתאמנת?"
        elif gender == "זכר":
            frequency_text = "כמה פעמים בשבוע אתה מתאמן?"
        else:
            frequency_text = "כמה פעמים בשבוע את/ה מתאמן/ת?"
        try:
            if update.callback_query:
                await update.callback_query.message.reply_text(
                    frequency_text,
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
            elif update.message:
                await update.message.reply_text(
                    frequency_text,
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
        except Exception as e:
            logger.error("Telegram API error in route_to_activity_questions: %s", e)
        return ACTIVITY_FREQUENCY
    
    elif activity_clean in ["הליכה", "אופניים", "שחייה"]:
        keyboard = [[KeyboardButton(opt)] for opt in ACTIVITY_FREQUENCY_OPTIONS]
        gender = context.user_data.get("gender", "זכר")
        if gender == "נקבה":
            frequency_text = f"כמה פעמים בשבוע את מבצעת {activity_clean}?"
        elif gender == "זכר":
            frequency_text = f"כמה פעמים בשבוע אתה מבצע {activity_clean}?"
        else:
            frequency_text = f"כמה פעמים בשבוע את/ה מבצע/ת {activity_clean}?"
        try:
            if update.callback_query:
                await update.callback_query.message.reply_text(
                    frequency_text,
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
            elif update.message:
                await update.message.reply_text(
                    frequency_text,
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
        except Exception as e:
            logger.error("Telegram API error in route_to_activity_questions: %s", e)
        return ACTIVITY_FREQUENCY
    
    elif activity_clean in ["יוגה", "פילאטיס"]:
        keyboard = [[KeyboardButton(opt)] for opt in ACTIVITY_FREQUENCY_OPTIONS]
        gender = context.user_data.get("gender", "זכר")
        if gender == "נקבה":
            frequency_text = f"כמה פעמים בשבוע את מתאמנת {activity_clean}?"
        elif gender == "זכר":
            frequency_text = f"כמה פעמים בשבוע אתה מתאמן {activity_clean}?"
        else:
            frequency_text = f"כמה פעמים בשבוע את/ה מתאמן/ת {activity_clean}?"
        try:
            if update.callback_query:
                await update.callback_query.message.reply_text(
                    frequency_text,
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
            elif update.message:
                await update.message.reply_text(
                    frequency_text,
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
        except Exception as e:
            logger.error("Telegram API error in route_to_activity_questions: %s", e)
        return ACTIVITY_FREQUENCY
    
    else:  # "אחר"
        keyboard = [[KeyboardButton(opt)] for opt in ACTIVITY_FREQUENCY_OPTIONS]
        gender = context.user_data.get("gender", "זכר")
        if gender == "נקבה":
            frequency_text = "כמה פעמים בשבוע את מבצעת פעילות אחרת?"
        elif gender == "זכר":
            frequency_text = "כמה פעמים בשבוע אתה מבצע פעילות אחרת?"
        else:
            frequency_text = "כמה פעמים בשבוע את/ה מבצע/ת פעילות אחרת?"
        try:
            if update.callback_query:
                await update.callback_query.message.reply_text(
                    frequency_text,
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
            elif update.message:
                await update.message.reply_text(
                    frequency_text,
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
        except Exception as e:
            logger.error("Telegram API error in route_to_activity_questions: %s", e)
        return ACTIVITY_FREQUENCY


async def continue_to_next_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ממשיך לסוג הפעילות הבא או לתזונה אם סיימנו."""
    if context.user_data is None:
        context.user_data = {}
    
    selected_types = context.user_data.get("activity_types", [])
    current_index = context.user_data.get("current_activity_index", 0)
    
    # עבור לסוג הפעילות הבא
    current_index += 1
    context.user_data["current_activity_index"] = current_index
    
    if current_index >= len(selected_types):
        # סיימנו את כל סוגי הפעילות - המשך לתזונה
        keyboard = [[KeyboardButton(opt)] for opt in DIET_OPTIONS]
        gender = context.user_data.get("gender", "זכר")
        if gender == "נקבה":
            diet_text = "מה העדפות התזונה שלך? (בחרי כל מה שמתאים)"
        elif gender == "זכר":
            diet_text = "מה העדפות התזונה שלך? (בחר כל מה שמתאים)"
        else:
            diet_text = "מה העדפות התזונה שלך? (בחר/י כל מה שמתאים)"
        
        try:
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    diet_text,
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
            elif update.message:
                await update.message.reply_text(
                    diet_text,
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard, one_time_keyboard=True, resize_keyboard=True
                    ),
                    parse_mode="HTML",
                )
        except Exception as e:
            logger.error("Telegram API error in continue_to_next_activity: %s", e)
        
        return DIET
    
    # עבור לסוג הפעילות הבא
    next_activity = selected_types[current_index]
    context.user_data["current_activity"] = next_activity
    
    return await route_to_activity_questions(update, context, next_activity)


def gendered_text(text_male: str, text_female: str, context: ContextTypes.DEFAULT_TYPE) -> str:
    """מחזירה טקסט מגדרי לפי context.user_data['gender']. אם אין מגדר – מחזירה טקסט ניטרלי."""
    gender = None
    if hasattr(context, 'user_data') and context.user_data:
        gender = context.user_data.get('gender')
    if gender == "נקבה":
        return text_female
    elif gender == "זכר":
        return text_male
    else:
        # אם אין מגדר, החזר טקסט ניטרלי שמתאים לשני המגדרים
        return text_male.replace("אתה", "את/ה").replace("עושה", "עושה/ת").replace("מתאמן", "מתאמן/ת").replace("מבצע", "מבצע/ת").replace("בחר", "בחר/י")


async def safe_edit_message_text(query, text, reply_markup=None, parse_mode=None):
    """עורכת טקסט של הודעה ומסירה קודם מקלדת אינליין אם קיימת."""
    if query.message and query.message.reply_markup and isinstance(query.message.reply_markup, InlineKeyboardMarkup):
        try:
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup([]))
        except telegram.error.BadRequest as e:
            logging.warning("Could not edit markup before text edit: %s", e)
    kwargs = {"text": text}
    if reply_markup is not None:
        kwargs["reply_markup"] = reply_markup
    if parse_mode is not None:
        kwargs["parse_mode"] = parse_mode
    await query.edit_message_text(**kwargs)


# יצירת instance של NutritionDB לשימוש בכל הפונקציות
nutrition_db = NutritionDB()


async def pin_single_message(chat, message_id):
    """מסיר pin קודם אם יש ומצמיד הודעה חדשה."""
    try:
        pinned = await chat.get_pinned_message()
        if pinned and pinned.message_id != message_id:
            await chat.unpin_message(pinned.message_id)
    except Exception as e:
        logger.warning(f"Could not unpin previous pinned message: {e}")
    try:
        await chat.pin_message(message_id)
    except Exception as e:
        logger.error(f"Error pinning message: {e}")


# Stub for personal details update
async def handle_update_personal_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # שלב 1: שאל אם לעדכן הכל
    keyboard = [[KeyboardButton("כן")], [KeyboardButton("לא")]]
    question = gendered_text(
        "רוצה לעדכן את כל הפרטים האישיים שלך?",
        "רוצה לעדכן את כל הפרטים האישיים שלך?",
        context
    )
    if update.message:
        await update.message.reply_text(
            question,
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode="HTML",
        )
    # שמור flag לזיהוי
    context.user_data["awaiting_reset_confirmation"] = True

async def handle_update_personal_details_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    if not context.user_data.get("awaiting_reset_confirmation"):
        return
    if text == "כן":
        # איפוס מלא
        user_id = update.effective_user.id if update.effective_user else None
        context.user_data.clear()
        context.user_data["reset_in_progress"] = True
        if user_id:
            # מחיקת נתונים מה-DB
            nutrition_db.save_user(user_id, {})
        # שלח הודעה חמה
        msg = gendered_text(
            "מתחילים הכל מההתחלה! אשאל אותך כמה שאלות קצרות כדי להתאים לך תפריט אישי.",
            "מתחילות הכל מההתחלה! אשאל אותך כמה שאלות קצרות כדי להתאים לך תפריט אישי.",
            context
        )
        await update.message.reply_text(msg, reply_markup=ReplyKeyboardRemove(), parse_mode="HTML")
        # התחל את השאלון מחדש (כמו start)
        await start(update, context)
        context.user_data.pop("awaiting_reset_confirmation", None)
        return
    elif text == "לא":
        msg = gendered_text(
            "הפרטים האישיים לא שונו. אפשר להמשיך כרגיל!",
            "הפרטים האישיים לא שונו. אפשר להמשיך כרגיל!",
            context
        )
        await update.message.reply_text(msg, reply_markup=build_main_keyboard(), parse_mode="HTML")
        context.user_data.pop("awaiting_reset_confirmation", None)
        return


async def handle_report_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles report selection from the report menu (CallbackQuery)."""
    query = update.callback_query
    if not query or not query.data:
        return
    user_id = update.effective_user.id if update.effective_user else None
    report_type = query.data.replace('report_', '')
    # שמור בחירה במסד (לניתוח עתידי)
    if user_id:
        if context.user_data is None:
            context.user_data = {}
        context.user_data.setdefault('report_requests', []).append({
            'type': report_type,
            'timestamp': datetime.now().isoformat()
        })
        nutrition_db.save_user(user_id, context.user_data)
    # דוח יומי
    if report_type == 'daily':
        from datetime import date
        today = date.today().isoformat()
        day_data = get_nutrition_by_date(user_id, today)
        if not day_data or not day_data.get('meals'):
            await query.answer()
            await query.edit_message_text(
                gendered_text("לא רשומים נתונים להיום.", "לא רשומים נתונים להיום.", context),
                parse_mode="HTML"
            )
            return
        # בנה סיכום יומי
        summary = f"<b>סיכום יומי ({today}):</b>\n"
        summary += f"סה\'כ קלוריות: <b>{day_data['calories']}</b>\n"
        summary += f"חלבון: <b>{day_data['protein']:.1f}g</b>  שומן: <b>{day_data['fat']:.1f}g</b>  פחמימות: <b>{day_data['carbs']:.1f}g</b>\n"
        summary += "\n<b>ארוחות עיקריות:</b>\n"
        for meal in day_data['meals']:
            desc = meal['desc'] if isinstance(meal, dict) and 'desc' in meal else str(meal)
            summary += f"• {desc}\n"
        # המלצה מ-GPT
        try:
            prompt = f"המשתמש/ת צרך/ה היום {day_data['calories']} קלוריות. תן המלצה קצרה ליום מחר (ב-1-2 משפטים, בעברית, ללא פתיח אישי)."
            from utils import call_gpt
            recommendation = await call_gpt(prompt)
        except Exception as e:
            logger.error(f"Error getting daily report recommendation: {e}")
            recommendation = ""
        if recommendation:
            summary += f"\n<b>המלצה למחר:</b> {recommendation}"
        await query.answer()
        await query.edit_message_text(summary, parse_mode="HTML")
        return
    # דוח שבועי
    elif report_type == 'weekly':
        data = get_weekly_report(user_id)
        if len(data) < 7:
            await query.answer()
            await query.edit_message_text(
                gendered_text(f"נותרו עוד {7-len(data)} ימים כדי שאוכל להציג סיכום שבועי מלא 😊", f"נותרו עוד {7-len(data)} ימים כדי שאוכל להציג סיכום שבועי מלא 😊", context),
                parse_mode="HTML"
            )
            return
        summary = build_weekly_summary_text(data)
        # המלצה מ-GPT
        try:
            prompt = f"המשתמש/ת צרך/ה בממוצע {sum(d['calories'] for d in data)//len(data)} קלוריות ביום בשבוע האחרון. תן המלצה קצרה לשבוע הבא (ב-1-2 משפטים, בעברית, ללא פתיח אישי)."
            from utils import call_gpt
            recommendation = await call_gpt(prompt)
        except Exception as e:
            logger.error(f"Error getting weekly report recommendation: {e}")
            recommendation = ""
        if recommendation:
            summary += f"\n<b>המלצה לשבוע הבא:</b> {recommendation}"
        await query.answer()
        await query.edit_message_text(summary, parse_mode="HTML")
        return
    # דוח חודשי
    elif report_type == 'monthly':
        data = get_monthly_report(user_id)
        if len(data) < 30:
            await query.answer()
            await query.edit_message_text(
                gendered_text(f"נותרו עוד {30-len(data)} ימים כדי שאוכל להציג סיכום חודשי מלא 🙂", f"נותרו עוד {30-len(data)} ימים כדי שאוכל להציג סיכום חודשי מלא 🙂", context),
                parse_mode="HTML"
            )
            return
        summary = build_monthly_summary_text(data)
        # המלצה מ-GPT
        try:
            prompt = f"המשתמש/ת צרך/ה בממוצע {sum(d['calories'] for d in data)//len(data)} קלוריות ביום בחודש האחרון. תן המלצה קצרה לחודש הבא (ב-1-2 משפטים, בעברית, ללא פתיח אישי)."
            from utils import call_gpt
            recommendation = await call_gpt(prompt)
        except Exception as e:
            logger.error(f"Error getting monthly report recommendation: {e}")
            recommendation = ""
        if recommendation:
            summary += f"\n<b>המלצה לחודש הבא:</b> {recommendation}"
        await query.answer()
        await query.edit_message_text(summary, parse_mode="HTML")
        return
    else:
        await query.answer()
        await query.edit_message_text("סוג דוח לא נתמך.")
        return


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a formatted help message with temporary action buttons."""
    help_text = gendered_text(
        """📌 איך אפשר להשתמש בי?

🟢 לקבלת תפריט יומי מותאם אישית – לחצו על "לקבלת תפריט יומי מותאם אישית"
🟢 לרשום מה אכלת – כתבו "אכלתי..." (למשל: אכלתי חביתה וסלט)
🟢 לשאול שאלות – כתבו "אפשר לאכול..." או "כמה קלוריות יש ב..."
🟢 לסיים את היום – לחצו על "סיימתי"
🟢 לקבל דוחות – לחצו על "קבלת דוח"
🟢 לעדכן משקל, תזונה, פעילות – לחצו על "עדכון פרטים אישיים"

🧠 עכשיו אפשר גם:
- לשאול אותי שאלות חופשיות (כל הודעה תנותח ע"י GPT)
- לבחור "מעבר לשאלון אישי" ולהתחיל הכל מחדש

אם צריך עזרה נוספת – פשוט כתבו לי 🙏""",
        """📌 איך אפשר להשתמש בי?

🟢 לקבלת תפריט יומי מותאם אישית – לחצי על "לקבלת תפריט יומי מותאם אישית"
🟢 לרשום מה אכלת – כתבי "אכלתי..." (למשל: אכלתי חביתה וסלט)
🟢 לשאול שאלות – כתבי "אפשר לאכול..." או "כמה קלוריות יש ב..."
🟢 לסיים את היום – לחצי על "סיימתי"
🟢 לקבל דוחות – לחצי על "קבלת דוח"
🟢 לעדכן משקל, תזונה, פעילות – לחצי על "עדכון פרטים אישיים"

🧠 עכשיו אפשר גם:
- לשאול אותי שאלות חופשיות (כל הודעה תנותח ע"י GPT)
- לבחור "מעבר לשאלון אישי" ולהתחיל הכל מחדש

אם צריך עזרה נוספת – פשוט כתבי לי 🙏""",
        context
    )
    # כפתורים מותאמים מגדרית
    free_question_text = gendered_text("שאל שאלה חופשית", "שאלי שאלה חופשית", context)
    questionnaire_text = gendered_text("מעבר לשאלון אישי", "מעבר לשאלון אישי", context)
    keyboard = [
        [KeyboardButton(free_question_text)],
        [KeyboardButton(questionnaire_text)],
    ]
    if update.message:
        await update.message.reply_text(
            help_text,
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )

# Logic for the two temporary buttons
async def handle_help_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    free_question_text = gendered_text("שאל שאלה חופשית", "שאלי שאלה חופשית", context)
    questionnaire_text = gendered_text("מעבר לשאלון אישי", "מעבר לשאלון אישי", context)
    
    if text == free_question_text:
        # החזר למצב free text (הסר מקלדת)
        await update.message.reply_text(
            gendered_text("אפשר לשאול כל שאלה חופשית!", "אפשר לשאול כל שאלה חופשית!", context),
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    elif text == questionnaire_text:
        # הפעל את השאלון מחדש
        await start(update, context)
        return
    else:
        # אם לא מזוהה - החזר למקלדת הראשית
        await update.message.reply_text(
            gendered_text("חזרה לתפריט הראשי", "חזרה לתפריט הראשי", context),
            reply_markup=build_main_keyboard(),
            parse_mode="HTML"
        )
        return

