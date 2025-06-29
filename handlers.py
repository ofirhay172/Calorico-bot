"""Telegram bot handlers for nutrition management.

This module contains all conversation handlers and message processing functions
for the Calorico nutritional bot, including questionnaire flow, menu generation,
and user interactions."""

import asyncio
import logging
from datetime import date

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
    ACTIVITY,
    ACTIVITY_TYPE,
    ACTIVITY_TYPE_OPTIONS,
    ACTIVITY_FREQUENCY,
    ACTIVITY_FREQUENCY_OPTIONS,
    ACTIVITY_DURATION,
    ACTIVITY_DURATION_OPTIONS,
    TRAINING_TIME,
    TRAINING_TIME_OPTIONS,
    CARDIO_GOAL,
    CARDIO_GOAL_OPTIONS,
    STRENGTH_GOAL,
    STRENGTH_GOAL_OPTIONS,
    SUPPLEMENTS,
    SUPPLEMENT_OPTIONS,
    SUPPLEMENT_TYPES,
    LIMITATIONS,
    MIXED_ACTIVITIES,
    MIXED_FREQUENCY,
    MIXED_FREQUENCY_OPTIONS,
    MIXED_DURATION_OPTIONS,
    MIXED_DURATION,
    MIXED_MENU_ADAPTATION,
    MIXED_ACTIVITY_OPTIONS,
    ALLERGIES,
    ALLERGIES_ADDITIONAL,
    DAILY,
    DIET,
    DIET_OPTIONS,
    EDIT,
    EATEN,
    GENDER,
    GENDER_OPTIONS,
    GOAL,
    GOAL_OPTIONS,
    HEIGHT,
    MENU,
    NAME,
    SCHEDULE,
    WEIGHT,
    GENDERED_ACTION,
    AGE,
    ACTIVITY_YES_NO_OPTIONS,
    WATER_REMINDER_OPT_IN,
    BODY_FAT_CURRENT,
    BODY_FAT_TARGET_GOAL,
)
from db import (
    save_user,
    save_daily_entry,
    save_user_allergies_data,
    save_food_entry,
)
from utils import (
    clean_desc,
    clean_meal_text,
    get_gendered_text,
    markdown_to_html,
    calculate_bmr,
    water_recommendation,
    learning_logic,
    extract_openai_response_content,
    build_main_keyboard,
    extract_allergens_from_text,
)
from report_generator import (
    get_weekly_report,
    build_weekly_summary_text,
    plot_calories,
    get_nutrition_by_date,
    get_last_occurrence_of_meal,
    format_date_query_response,
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
    """בונה מקלדת אלרגיות עם סימון בחירות."""
    keyboard = []
    for opt in ALLERGY_OPTIONS:
        label = opt
        if opt in selected and opt != "אין":
            label += " ❌"
        keyboard.append([KeyboardButton(label)])
    return keyboard


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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """מתחיל את הבוט ומציג תפריט ראשי."""
    if not update.message:
        return

    user = update.effective_user
    if not user:
        return

    logger.info("Bot started by user %s", user.id)

    # בדיקה אם המשתמש כבר קיים במערכת
    if context.user_data and context.user_data.get("name"):
        # המשתמש כבר עבר את השאלון - הצג תפריט ראשי
        keyboard = build_main_keyboard()
        await update.message.reply_text(
            f"שלום {context.user_data['name']}! מה תרצה/י לעשות?",
            reply_markup=ReplyKeyboardMarkup(
                keyboard, resize_keyboard=True, one_time_keyboard=False
            ),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    # המשתמש חדש - התחל שאלון
    await update.message.reply_text(
        "ברוכים הבאים לבוט התזונה קלוריקו! 🥗\n\n"
        "אני כאן כדי לעזור לך להשיג את המטרות התזונתיות שלך.\n"
        "בואו נתחיל בשאלון קצר כדי להתאים לך תפריט אישי.",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML",
    )
    return await get_name(update, context)


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש לשמו וממשיך לשאלת מגדר."""
    if update.message and update.message.text:
        name = update.message.text.strip()
        if not name:
            await update.message.reply_text(
                "אנא הזן שם תקין.",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
            return NAME

        if context.user_data is None:
            context.user_data = {}
        logger.info("Name provided: '%s'", name)
        context.user_data["name"] = name

        # שמירה למסד נתונים
        user_id = update.effective_user.id if update.effective_user else None
        if user_id and context.user_data:
            save_user(user_id, context.user_data)

        keyboard = [[KeyboardButton(opt)] for opt in GENDER_OPTIONS]
        await update.message.reply_text(
            "מה המגדר שלך?",
            reply_markup=ReplyKeyboardMarkup(
                keyboard, one_time_keyboard=True, resize_keyboard=True
            ),
            parse_mode="HTML",
        )
        return GENDER

    # This is when called from start function - ask for name
    logger.info("get_name called from start - asking for name")
    if update.message:
        await update.message.reply_text(
            "מה השם שלך?",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
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
            await update.message.reply_text(
                "בחר מגדר מהתפריט למטה:",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
            return GENDER

        if context.user_data is None:
            context.user_data = {}
        context.user_data["gender"] = gender
        logger.info("Gender saved: %s", gender)

        # שמירה למסד נתונים
        user_id = update.effective_user.id if update.effective_user else None
        if user_id and context.user_data:
            save_user(user_id, context.user_data)

        gender_text = "בת כמה את?" if gender == "נקבה" else "בן כמה אתה?"
        await update.message.reply_text(
            gender_text,
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
        return AGE

    logger.error("get_gender called without text")
    return GENDER


async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש לגילו וממשיך לשאלת גובה."""
    if update.message and update.message.text:
        age_text = update.message.text.strip()
        is_valid, age, error_msg = validate_age(age_text)

        if not is_valid:
            await update.message.reply_text(
                error_msg,
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
            return AGE

        if context.user_data is None:
            context.user_data = {}
        context.user_data["age"] = age

        # שמירה למסד נתונים
        user_id = update.effective_user.id if update.effective_user else None
        if user_id and context.user_data:
            save_user(user_id, context.user_data)

        gender = context.user_data.get("gender", "זכר")
        height_text = "מה הגובה שלך בס\"מ?" if gender == "זכר" else "מה הגובה שלך בס\"מ?"
        await update.message.reply_text(
            height_text,
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
        return HEIGHT

    if context.user_data is None:
        context.user_data = {}
    gender = context.user_data.get("gender", "זכר")
    age_text = "בת כמה את?" if gender == "נקבה" else "בן כמה אתה?"
    if update.message:
        await update.message.reply_text(
            age_text,
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
    return AGE


async def get_height(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש לגובהו וממשיך לשאלת משקל."""
    if update.message and update.message.text:
        height_text = update.message.text.strip()
        is_valid, height, error_msg = validate_height(height_text)

        if not is_valid:
            await update.message.reply_text(
                error_msg,
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
            return HEIGHT

        if context.user_data is None:
            context.user_data = {}
        context.user_data["height"] = height

        # שמירה למסד נתונים
        user_id = update.effective_user.id if update.effective_user else None
        if user_id and context.user_data:
            save_user(user_id, context.user_data)

        gender = context.user_data.get("gender", "זכר")
        weight_text = "מה המשקל שלך בק\"ג?" if gender == "זכר" else "מה המשקל שלך בק\"ג?"
        await update.message.reply_text(
            weight_text,
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
        return WEIGHT

    if context.user_data is None:
        context.user_data = {}
    gender = context.user_data.get("gender", "זכר")
    height_text = "מה הגובה שלך בס\"מ?" if gender == "זכר" else "מה הגובה שלך בס\"מ?"
    if update.message:
        await update.message.reply_text(
            height_text,
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
    return HEIGHT


async def get_weight(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש למשקלו וממשיך לשאלת מטרה."""
    if update.message and update.message.text:
        weight_text = update.message.text.strip()
        is_valid, weight, error_msg = validate_weight(weight_text)

        if not is_valid:
            await update.message.reply_text(
                error_msg,
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
            return WEIGHT

        if context.user_data is None:
            context.user_data = {}
        context.user_data["weight"] = weight

        # שמירה למסד נתונים
        user_id = update.effective_user.id if update.effective_user else None
        if user_id and context.user_data:
            save_user(user_id, context.user_data)

        keyboard = [[KeyboardButton(opt)] for opt in GOAL_OPTIONS]
        gender = context.user_data.get("gender", "זכר")
        goal_text = "מה המטרה שלך?" if gender == "זכר" else "מה המטרה שלך?"
        await update.message.reply_text(
            goal_text,
            reply_markup=ReplyKeyboardMarkup(
                keyboard, one_time_keyboard=True, resize_keyboard=True
            ),
            parse_mode="HTML",
        )
        return GOAL

    if context.user_data is None:
        context.user_data = {}
    gender = context.user_data.get("gender", "זכר")
    weight_text = "מה המשקל שלך בק\"ג?" if gender == "זכר" else "מה המשקל שלך בק\"ג?"
    if update.message:
        await update.message.reply_text(
            weight_text,
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
    return WEIGHT


async def get_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש למטרתו וממשיך לשאלת אחוז שומן או פעילות."""
    if update.message and update.message.text:
        goal = update.message.text.strip()
        if goal not in GOAL_OPTIONS:
            keyboard = [[KeyboardButton(opt)] for opt in GOAL_OPTIONS]
            if context.user_data is None:
                context.user_data = {}
            gender = context.user_data.get("gender", "זכר")
            error_text = "בחר מטרה מהתפריט למטה:" if gender == "זכר" else "בחרי מטרה מהתפריט למטה:"
            await update.message.reply_text(
                error_text,
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
            return GOAL

        if context.user_data is None:
            context.user_data = {}
        context.user_data["goal"] = goal

        # שמירה למסד נתונים
        user_id = update.effective_user.id if update.effective_user else None
        if user_id and context.user_data:
            save_user(user_id, context.user_data)

        # המשך לשאלת אחוז שומן נוכחי
        gender = context.user_data.get("gender", "זכר")
        fat_text = "מה אחוז השומן הנוכחי שלך?" if gender == "זכר" else "מה אחוז השומן הנוכחי שלך?"
        await update.message.reply_text(
            fat_text,
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
        return BODY_FAT_CURRENT

    if context.user_data is None:
        context.user_data = {}
    gender = context.user_data.get("gender", "זכר")
    goal_text = "מה המטרה שלך?" if gender == "זכר" else "מה המטרה שלך?"
    keyboard = [[KeyboardButton(opt)] for opt in GOAL_OPTIONS]
    if update.message:
        await update.message.reply_text(
            goal_text,
            reply_markup=ReplyKeyboardMarkup(
                keyboard, one_time_keyboard=True, resize_keyboard=True
            ),
            parse_mode="HTML",
        )
    return GOAL


async def get_body_fat_current(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """שואל את המשתמש לאחוז שומן נוכחי וממשיך לאחוז יעד."""
    if update.message and update.message.text:
        body_fat_text = update.message.text.strip()
        is_valid, body_fat, error_msg = validate_body_fat(body_fat_text)

        if not is_valid:
            await update.message.reply_text(
                error_msg,
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
            return BODY_FAT_CURRENT

        if context.user_data is None:
            context.user_data = {}
        context.user_data["body_fat_current"] = body_fat

        # שמירה למסד נתונים
        user_id = update.effective_user.id if update.effective_user else None
        if user_id:
            save_user(user_id, context.user_data)

        gender = context.user_data.get(
            "gender", "זכר") if context.user_data else "זכר"
        target_text = "מה אחוז השומן היעד שלך?" if gender == "זכר" else "מה אחוז השומן היעד שלך?"
        await update.message.reply_text(
            target_text,
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
        return BODY_FAT_TARGET_GOAL
    else:
        gender = context.user_data.get(
            "gender", "זכר") if context.user_data else "זכר"
        body_fat_text = "מה אחוז השומן הנוכחי שלך?" if gender == "זכר" else "מה אחוז השומן הנוכחי שלך?"
        if update.message:
            await update.message.reply_text(
                body_fat_text,
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
        return BODY_FAT_CURRENT


async def get_body_fat_target_goal(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """שואל את המשתמש לאחוז שומן יעד וממשיך לשאלת פעילות."""
    if update.message and update.message.text:
        target_text = update.message.text.strip()
        is_valid, target_fat, error_msg = validate_body_fat(target_text)

        if not is_valid:
            await update.message.reply_text(
                error_msg,
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
            return BODY_FAT_TARGET_GOAL

        current_fat = context.user_data.get("body_fat_current", 0) if context.user_data else 0
        if target_fat >= current_fat:
            await update.message.reply_text(
                "אחוז השומן היעד חייב להיות נמוך מהנוכחי כדי לרדת באחוזי שומן.",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
            return BODY_FAT_TARGET_GOAL

        if context.user_data is None:
            context.user_data = {}
        context.user_data["body_fat_target"] = target_fat

        # שמירה למסד נתונים
        user_id = update.effective_user.id if update.effective_user else None
        if user_id and context.user_data:
            save_user(user_id, context.user_data)

        # המשך לשאלת פעילות
        return await get_activity(update, context)
    else:
        if context.user_data is None:
            context.user_data = {}
        gender = context.user_data.get("gender", "זכר")
        target_text = "מה אחוז השומן היעד שלך?" if gender == "זכר" else "מה אחוז השומן היעד שלך?"
        if update.message:
            await update.message.reply_text(
                target_text,
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
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
                error_text = "האם את עושה פעילות גופנית? (בחרי כן או לא מהתפריט למטה)"
            elif gender == "זכר":
                error_text = "האם אתה עושה פעילות גופנית? (בחר כן או לא מהתפריט למטה)"
            else:
                error_text = (
                    "האם את/ה עושה פעילות גופנית? (בחר/י כן או לא מהתפריט למטה)"
                )
            await update.message.reply_text(
                error_text,
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
            return ACTIVITY
        
        if context.user_data is None:
            context.user_data = {}
        context.user_data["does_activity"] = activity_answer

        # שמירה למסד נתונים
        user_id = update.effective_user.id if update.effective_user else None
        if user_id and context.user_data:
            save_user(user_id, context.user_data)

        if activity_answer == "לא":
            # Skip to diet questions
            keyboard = [[KeyboardButton(opt)] for opt in DIET_OPTIONS]
            gender = context.user_data.get("gender", "זכר")
            if gender == "נקבה":
                diet_text = "מה העדפות התזונה שלך? (בחרי כל מה שמתאים)"
            elif gender == "זכר":
                diet_text = "מה העדפות התזונה שלך? (בחר כל מה שמתאים)"
            else:
                diet_text = "מה העדפות התזונה שלך? (בחר/י כל מה שמתאים)"
            await update.message.reply_text(
                diet_text,
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
            return DIET
        # אם כן - המשך לשאלות פעילות
        return await get_activity_type(update, context)
    # אם אין הודעה, הצג את השאלה
    if update.message:
        keyboard = [[KeyboardButton(opt)] for opt in ACTIVITY_YES_NO_OPTIONS]
        if context.user_data is None:
            context.user_data = {}
        gender = context.user_data.get("gender", "זכר")
        if gender == "נקבה":
            activity_text = "האם את עושה פעילות גופנית? (בחרי כן או לא)"
        elif gender == "זכר":
            activity_text = "האם אתה עושה פעילות גופנית? (בחר כן או לא)"
        else:
            activity_text = "האם את/ה עושה פעילות גופנית? (בחר/י כן או לא)"
        await update.message.reply_text(
            activity_text,
            reply_markup=ReplyKeyboardMarkup(
                keyboard, one_time_keyboard=True, resize_keyboard=True
            ),
            parse_mode="HTML",
        )
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
            await update.message.reply_text(
                error_text,
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
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
                diet_text = "מה העדפות התזונה שלך? (בחרי כל מה שמתאים)"
            elif gender == "זכר":
                diet_text = "מה העדפות התזונה שלך? (בחר כל מה שמתאים)"
            else:
                diet_text = "מה העדפות התזונה שלך? (בחר/י כל מה שמתאים)"
            await update.message.reply_text(
                diet_text,
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
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
                frequency_text = "כמה פעמים בשבוע את/ה מבצע/ת את הפעילות?"
            await update.message.reply_text(
                frequency_text,
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
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
                frequency_text = "כמה פעמים בשבוע את/ה מתאמן/ת?"
            await update.message.reply_text(
                frequency_text,
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
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
                frequency_text = "כמה פעמים בשבוע את/ה מתאמן/ת?"
            await update.message.reply_text(
                frequency_text,
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
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
                mixed_text = (
                    "אילו סוגי אימונים את/ה מבצע/ת במהלך השבוע? (בחר/י כל מה שמתאים)"
                )
            await update.message.reply_text(
                mixed_text,
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
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
            await update.message.reply_text(
                "בחר/י תדירות מהתפריט למטה:",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
            return ACTIVITY_FREQUENCY

        context.user_data["activity_frequency"] = frequency

        # Ask duration
        keyboard = [[KeyboardButton(opt)] for opt in ACTIVITY_DURATION_OPTIONS]
        await update.message.reply_text(
            "כמה זמן נמשך כל אימון? (בדקות)",
            reply_markup=ReplyKeyboardMarkup(
                keyboard, one_time_keyboard=True, resize_keyboard=True
            ),
            parse_mode="HTML",
        )
        return ACTIVITY_DURATION
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
            await update.message.reply_text(
                "בחר/י משך מהתפריט למטה:",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
            return ACTIVITY_DURATION

        context.user_data["activity_duration"] = duration
        activity_type = context.user_data.get("activity_type", "") if context.user_data else ""

        # Route based on activity type
        if activity_type == "הליכה מהירה / ריצה קלה":
            # Ask cardio goal
            keyboard = [[KeyboardButton(opt)] for opt in CARDIO_GOAL_OPTIONS]
            await update.message.reply_text(
                "מה מטרת הפעילות?",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
            return CARDIO_GOAL

        elif activity_type in ["אימוני כוח", "אימוני HIIT / קרוספיט"]:
            # Ask training time
            keyboard = [[KeyboardButton(opt)] for opt in TRAINING_TIME_OPTIONS]
            await update.message.reply_text(
                "באיזה שעה בדרך כלל את/ה מתאמן/ת?",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
            return TRAINING_TIME

        elif activity_type == "יוגה / פילאטיס":
            # Ask if this is the only activity
            keyboard = [[KeyboardButton("כן"), KeyboardButton("לא")]]
            await update.message.reply_text(
                "האם זו הפעילות היחידה שלך?",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
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
            await update.message.reply_text(
                "בחר/י שעה מהתפריט למטה:",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
            return TRAINING_TIME

        if context.user_data is None:
            context.user_data = {}
        context.user_data["training_time"] = training_time

        # Ask strength goal
        keyboard = [[KeyboardButton(opt)] for opt in STRENGTH_GOAL_OPTIONS]
        await update.message.reply_text(
            "מה המטרה?",
            reply_markup=ReplyKeyboardMarkup(
                keyboard, one_time_keyboard=True, resize_keyboard=True
            ),
            parse_mode="HTML",
        )
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
            await update.message.reply_text(
                "בחר/י מטרה מהתפריט למטה:",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
            return CARDIO_GOAL

        if context.user_data is None:
            context.user_data = {}
        context.user_data["cardio_goal"] = goal

        # Continue to diet questions
        keyboard = [[KeyboardButton(opt)] for opt in DIET_OPTIONS]
        gender = context.user_data.get("gender", "זכר")
        diet_text = (
            "מה העדפות התזונה שלך? (בחרי כל מה שמתאים)"
            if gender == "נקבה"
            else "מה העדפות התזונה שלך? (בחר/י כל מה שמתאים)"
        )
        await update.message.reply_text(
            diet_text,
            reply_markup=ReplyKeyboardMarkup(
                keyboard, one_time_keyboard=True, resize_keyboard=True
            ),
            parse_mode="HTML",
        )
        return DIET
    return CARDIO_GOAL


async def get_strength_goal(update: Update,
                            context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש למטרת האימון וממשיך לשאלת תוספים."""
    if update.message and update.message.text:
        goal = update.message.text.strip()
        if goal not in STRENGTH_GOAL_OPTIONS:
            keyboard = [[KeyboardButton(opt)] for opt in STRENGTH_GOAL_OPTIONS]
            await update.message.reply_text(
                "בחר/י מטרה מהתפריט למטה:",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
            return STRENGTH_GOAL

        if context.user_data is None:
            context.user_data = {}
        context.user_data["strength_goal"] = goal

        # Ask about supplements
        keyboard = [[KeyboardButton("כן"), KeyboardButton("לא")]]
        await update.message.reply_text(
            "האם את/ה משתמש/ת בתוספי תזונה?",
            reply_markup=ReplyKeyboardMarkup(
                keyboard, one_time_keyboard=True, resize_keyboard=True
            ),
            parse_mode="HTML",
        )
        return SUPPLEMENTS
    return STRENGTH_GOAL


async def get_supplements(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש על תוספי תזונה וממשיך לשאלה הבאה."""
    if update.message and update.message.text:
        choice = update.message.text.strip()
        if choice not in ["כן", "לא"]:
            keyboard = [[KeyboardButton("כן"), KeyboardButton("לא")]]
            await update.message.reply_text(
                "בחר/י כן או לא:",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
            return SUPPLEMENTS

        if context.user_data is None:
            context.user_data = {}
        context.user_data["takes_supplements"] = choice == "כן"

        if choice == "כן":
            # Ask for supplement types
            keyboard = [[KeyboardButton(opt)] for opt in SUPPLEMENT_OPTIONS]
            await update.message.reply_text(
                "איזה תוספים את/ה לוקח/ת? (בחר/י כל מה שמתאים)",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
            return SUPPLEMENT_TYPES
        else:
            # Ask about limitations
            await update.message.reply_text(
                "האם יש מגבלות פיזיות / כאבים? (אם לא, כתוב 'אין')",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
            return LIMITATIONS
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

        # Ask about limitations
        await update.message.reply_text(
            "האם יש מגבלות פיזיות / כאבים? (אם לא, כתוב 'אין')",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
        return LIMITATIONS
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

        # Continue to diet questions
        keyboard = [[KeyboardButton(opt)] for opt in DIET_OPTIONS]
        gender = context.user_data.get("gender", "זכר")
        diet_text = (
            "מה העדפות התזונה שלך? (בחרי כל מה שמתאים)"
            if gender == "נקבה"
            else "מה העדפות התזונה שלך? (בחר/י כל מה שמתאים)"
        )
        await update.message.reply_text(
            diet_text,
            reply_markup=ReplyKeyboardMarkup(
                keyboard, one_time_keyboard=True, resize_keyboard=True
            ),
            parse_mode="HTML",
        )
        return DIET
    return LIMITATIONS


async def get_mixed_activities(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """מטפל בבחירת סוגי פעילות מרובות."""
    if context.user_data is None:
        context.user_data = {}
    if "mixed_activities_selected" not in context.user_data:
        context.user_data["mixed_activities_selected"] = set()

    selected = context.user_data["mixed_activities_selected"]

    if update.message and update.message.text:
        text = update.message.text.strip().replace(" ❌", "")

        if text == "המשך":
            if not selected:
                await update.message.reply_text(
                    "אנא בחר/י לפחות סוג פעילות אחד לפני ההמשך.",
                    reply_markup=build_mixed_activities_keyboard(selected),
                )
                return MIXED_ACTIVITIES

            # שמירת הפעילויות שנבחרו
            context.user_data["mixed_activities"] = list(selected)
            del context.user_data["mixed_activities_selected"]

            # מעבר לשאלת תדירות כוללת
            return await get_mixed_frequency(update, context)

        elif text in MIXED_ACTIVITY_OPTIONS:
            if text in selected:
                selected.remove(text)
            else:
                selected.add(text)

        elif text == "אין":
            selected.clear()
            selected.add("אין")

    # הצג מקלדת עם הפעילויות שנבחרו
    if update.message:
        await update.message.reply_text(
            "בחר/י את סוגי הפעילות הגופנית שלך (לחיצה נוספת מבטלת בחירה):",
            reply_markup=build_mixed_activities_keyboard(selected),
        )
    return MIXED_ACTIVITIES


async def get_mixed_frequency(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """שואל על תדירות כוללת לפעילות מעורבת."""
    if update.message and update.message.text:
        text = update.message.text.strip()

        if text in MIXED_FREQUENCY_OPTIONS:
            if context.user_data is None:
                context.user_data = {}
            context.user_data["mixed_frequency"] = text

            # מעבר לשאלת משך כולל
            if update.message:
                await update.message.reply_text(
                    "כמה זמן נמשך כל אימון בממוצע?",
                    reply_markup=ReplyKeyboardMarkup(
                        MIXED_DURATION_OPTIONS, resize_keyboard=True
                    ),
                )
            return MIXED_DURATION

    if update.message:
        await update.message.reply_text(
            "כמה פעמים בשבוע את/ה מתאמן/ת?",
            reply_markup=ReplyKeyboardMarkup(MIXED_FREQUENCY_OPTIONS, resize_keyboard=True),
        )
    return MIXED_FREQUENCY


async def get_mixed_duration(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """שואל על משך כולל לפעילות מעורבת."""
    if update.message and update.message.text:
        text = update.message.text.strip()

        if text in MIXED_DURATION_OPTIONS:
            if context.user_data is None:
                context.user_data = {}
            context.user_data["mixed_duration"] = text

            # חישוב כולל של תדירות ומשך
            frequency = context.user_data.get("mixed_frequency", "")
            duration = context.user_data.get("mixed_duration", "")
            activities = context.user_data.get("mixed_activities", [])

            # יצירת סיכום פעילות
            activity_summary = (
                f"שילוב: {', '.join(activities)}, {frequency}, {duration}"
            )
            context.user_data["activity"] = activity_summary

            # מעבר לשאלת התאמת תפריט
            return await get_mixed_menu_adaptation(update, context)

    if update.message:
        await update.message.reply_text(
            "כמה זמן נמשך כל אימון בממוצע?",
            reply_markup=ReplyKeyboardMarkup(MIXED_DURATION_OPTIONS, resize_keyboard=True),
        )
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
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def get_mixed_menu_adaptation(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """שואל את המשתמש על התאמת תפריט וממשיך לתזונה."""
    if update.message and update.message.text:
        choice = update.message.text.strip()
        if choice not in ["כן", "לא"]:
            keyboard = [[KeyboardButton("כן"), KeyboardButton("לא")]]
            await update.message.reply_text(
                "בחר/י כן או לא:",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
            return MIXED_MENU_ADAPTATION

        context.user_data["menu_adaptation"] = choice == "כן"

        # Continue to diet questions
        keyboard = [[KeyboardButton(opt)] for opt in DIET_OPTIONS]
        gender = context.user_data.get(
            "gender", "זכר") if context.user_data else "זכר"
        diet_text = (
            "מה העדפות התזונה שלך? (בחרי כל מה שמתאים)"
            if gender == "נקבה"
            else "מה העדפות התזונה שלך? (בחר/י כל מה שמתאים)"
        )
        await update.message.reply_text(
            diet_text,
            reply_markup=ReplyKeyboardMarkup(
                keyboard, one_time_keyboard=True, resize_keyboard=True
            ),
            parse_mode="HTML",
        )
        return DIET


async def get_diet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש להעדפות תזונה עם בחירה מרובה אינטראקטיבית."""
    if update.message and update.message.text:
        diet_text = update.message.text.strip()

        # אתחול בחירות אם לא קיימות
        if "selected_diet_options" not in context.user_data:
            context.user_data["selected_diet_options"] = []

        selected_options = context.user_data["selected_diet_options"]

        # בדיקה אם המשתמש לחץ על "סיימתי"
        if "סיימתי בחירת העדפות" in diet_text:
            # שמירת הבחירות הסופיות
            if not selected_options:
                selected_options = ["אין העדפות מיוחדות"]
            context.user_data["diet"] = selected_options

            # חישוב BMR ותקציב קלוריות
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

            # הצגת סיכום הבחירות
            diet_summary = ", ".join(selected_options)
            await update.message.reply_text(
                f"העדפות התזונה שלך: {diet_summary}\n\n"
                "עכשיו בואו נמשיך לשאלה הבאה...",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )

            await update.message.reply_text(
                "האם יש לך אלרגיות למזון? (אם לא, כתוב 'אין')",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
            return ALLERGIES

        # בדיקה אם המשתמש לחץ על אפשרות
        for option in DIET_OPTIONS:
            if option in diet_text:
                if option in selected_options:
                    # הסרת הבחירה אם כבר נבחרה
                    selected_options.remove(option)
                else:
                    # הוספת הבחירה אם לא נבחרה
                    selected_options.append(option)

                # עדכון context
                context.user_data["selected_diet_options"] = selected_options

                # הצגת מקלדת מעודכנת
                keyboard = build_diet_keyboard(selected_options)
                gender = (
                    context.user_data.get("gender", "זכר")
                    if context.user_data
                    else "זכר"
                )
                if gender == "נקבה":
                    diet_text = (
                        "מה העדפות התזונה שלך? (לחצי על אפשרות כדי לבחור/לבטל בחירה)"
                    )
                elif gender == "זכר":
                    diet_text = (
                        "מה העדפות התזונה שלך? (לחץ על אפשרות כדי לבחור/לבטל בחירה)"
                    )
                else:
                    diet_text = (
                        "מה העדפות התזונה שלך? (לחץ/י על אפשרות כדי לבחור/לבטל בחירה)"
                    )

                await update.message.reply_text(
                    diet_text,
                    reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
                    parse_mode="HTML",
                )
                return DIET

        # אם לא זוהתה בחירה - הצג הודעה
        keyboard = build_diet_keyboard(selected_options)
        await update.message.reply_text(
            "אנא בחר/י אפשרות מהתפריט למטה או לחץ/י על 'סיימתי בחירת העדפות'",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode="HTML",
        )
        return DIET
    else:
        # פעם ראשונה - הצג מקלדת
        context.user_data["selected_diet_options"] = []
        keyboard = build_diet_keyboard([])
        gender = context.user_data.get(
            "gender", "זכר") if context.user_data else "זכר"
        if gender == "נקבה":
            diet_text = "מה העדפות התזונה שלך? (לחצי על אפשרות כדי לבחור/לבטל בחירה)"
        elif gender == "זכר":
            diet_text = "מה העדפות התזונה שלך? (לחץ על אפשרות כדי לבחור/לבטל בחירה)"
        else:
            diet_text = "מה העדפות התזונה שלך? (לחץ/י על אפשרות כדי לבחור/לבטל בחירה)"
        await update.message.reply_text(
            diet_text,
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode="HTML",
        )
        return DIET


async def get_allergies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """מטפל בשאלת אלרגיות עם זיהוי אוטומטי."""
    text = update.message.text.strip()

    # זיהוי אלרגנים אוטומטית
    detected_allergies = extract_allergens_from_text(text)

    if detected_allergies:
        # שמירת אלרגיות במסד נתונים
        user_id = update.effective_user.id
        save_user_allergies_data(user_id, detected_allergies)

        # עדכון context
        context.user_data["allergies"] = detected_allergies

        # הודעה עם האלרגנים שזוהו
        allergies_text = ", ".join(detected_allergies)
        await update.message.reply_text(
            f"זיהיתי את האלרגיות הבאות: {allergies_text}\n\n"
            "אם יש אלרגיות נוספות שלא זוהו, אנא כתוב אותן.",
            reply_markup=ReplyKeyboardMarkup(
                [["אין אלרגיות נוספות"]], resize_keyboard=True
            ),
        )
        return ALLERGIES_ADDITIONAL
    else:
        # אם לא זוהו אלרגנים, בדוק אם המשתמש כתב "אין" או משהו דומה
        if any(word in text.lower()
               for word in ["אין", "לא", "ללא", "אפס", "כלום"]):
            context.user_data["allergies"] = []
            save_user_allergies_data(update.effective_user.id, [])

            await update.message.reply_text(
                "מעולה! אין אלרגיות.\n\n" "עכשיו בואו נמשיך לשאלה הבאה...",
                reply_markup=ReplyKeyboardRemove(),
            )
            return await ask_water_reminder_opt_in(update, context)
        else:
            # בקשה להבהרה
            await update.message.reply_text(
                "לא זיהיתי אלרגנים ספציפיים בטקסט שלך.\n\n"
                "אנא כתוב את האלרגיות שלך בצורה ברורה, למשל:\n"
                "• חלב, בוטנים\n"
                "• גלוטן, ביצים\n"
                "• אין אלרגיות\n\n"
                "או כתוב 'אין' אם אין לך אלרגיות.",
                reply_markup=ReplyKeyboardMarkup(
                    [["אין אלרגיות"]], resize_keyboard=True
                ),
            )
            return ALLERGIES


async def get_allergies_additional(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """מטפל באלרגיות נוספות."""
    text = update.message.text.strip()

    if "אין" in text.lower():
        # המשך לשאלה הבאה
        await update.message.reply_text(
            "מעולה! עכשיו בואו נמשיך לשאלה הבאה...", reply_markup=ReplyKeyboardRemove()
        )
        return await ask_water_reminder_opt_in(update, context)
    else:
        # זיהוי אלרגנים נוספים
        additional_allergies = extract_allergens_from_text(text)
        if additional_allergies:
            # הוספה לאלרגיות הקיימות
            current_allergies = context.user_data.get("allergies", [])
            all_allergies = list(set(current_allergies + additional_allergies))

            # שמירה במסד נתונים
            user_id = update.effective_user.id
            save_user_allergies_data(user_id, all_allergies)
            context.user_data["allergies"] = all_allergies

            allergies_text = ", ".join(all_allergies)
            await update.message.reply_text(
                f'סה"כ האלרגיות שלך: {allergies_text}\n\n'
                "עכשיו בואו נמשיך לשאלה הבאה...",
                reply_markup=ReplyKeyboardRemove(),
            )
            return await ask_water_reminder_opt_in(update, context)
        else:
            await update.message.reply_text(
                "לא זיהיתי אלרגיות נוספות. אם אין עוד אלרגיות, כתוב 'אין'.",
                reply_markup=ReplyKeyboardMarkup(
                    [["אין אלרגיות נוספות"]], resize_keyboard=True
                ),
            )
            return ALLERGIES_ADDITIONAL


async def ask_water_reminder_opt_in(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """Ask user if they want water reminders."""
    keyboard = [[KeyboardButton("כן, אשמח!"), KeyboardButton("לא, תודה")]]
    gender = context.user_data.get(
        "gender", "זכר") if context.user_data else "זכר"
    reminder_text = (
        "האם תרצי לקבל תזכורת לשתות מים כל שעה וחצי?"
        if gender == "נקבה"
        else "האם תרצה לקבל תזכורת לשתות מים כל שעה וחצי?"
    )
    await update.message.reply_text(
        reminder_text,
        reply_markup=ReplyKeyboardMarkup(
            keyboard, one_time_keyboard=True, resize_keyboard=True
        ),
        parse_mode="HTML",
    )
    return WATER_REMINDER_OPT_IN


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
        asyncio.create_task(
            start_water_reminder_loop_with_buttons(
                update, context))
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

    # After water answer - show new main menu
    keyboard = [
        [KeyboardButton("לקבלת תפריט יומי מותאם אישית")],
        [KeyboardButton("מה אכלתי היום")],
        [KeyboardButton("בניית ארוחה לפי מה שיש לי בבית")],
        [KeyboardButton("קבלת דוח")],
        [KeyboardButton("תזכורות על שתיית מים")],
    ]
    gender = context.user_data.get(
        "gender", "זכר") if context.user_data else "זכר"
    action_text = "מה תרצי לעשות כעת?" if gender == "נקבה" else "מה תרצה לעשות כעת?"
    await update.message.reply_text(
        action_text,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        parse_mode="HTML",
    )
    return ConversationHandler.END


async def start_water_reminder_loop_with_buttons(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Start water reminder loop with buttons."""
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
            logger.error(f"Water reminder error: {e}")
        if user_id:
            save_user(user_id, context.user_data)


async def send_water_reminder(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
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


async def remind_in_10_minutes(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
    """Remind in 10 minutes."""
    await update.message.reply_text(
        "בסדר! אזכיר לך לשתות מים בעוד 10 דקות.",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML",
    )
    await asyncio.sleep(10 * 60)
    await send_water_reminder(update, context)


async def cancel_water_reminders(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE):
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


async def water_intake_start(update: Update,
                             context: ContextTypes.DEFAULT_TYPE) -> int:
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
        GENDERED_ACTION["female"] if gender == "female" else GENDERED_ACTION["male"])
    if update.message:
        await update.message.reply_text(
            action_text,
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode="HTML",
        )
    return DAILY


async def daily_menu(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE) -> int:
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
    user = context.user_data if context.user_data else {}
    gender = user.get("gender", "זכר")
    if not user.get("eaten_prompted", False):
        if update.message:
            if gender == "נקבה":
                prompt = "אשמח שתפרטי מה אכלת היום, בצורה הבאה: ביצת עין, 2 פרוסות לחם לבן עם גבינה לבנה 5%, סלט ירקות ממלפפון ועגבנייה"
            elif gender == "זכר":
                prompt = "אשמח שתפרט מה אכלת היום, בצורה הבאה: ביצת עין, 2 פרוסות לחם לבן עם גבינה לבנה 5%, סלט ירקות ממלפפון ועגבנייה"
            else:
                prompt = "אשמח שתפרט/י מה אכלת היום, בצורה הבאה: ביצת עין, 2 פרוסות לחם לבן עם גבינה לבנה 5%, סלט ירקות ממלפפון ועגבנייה"
            await update.message.reply_text(
                prompt, reply_markup=ReplyKeyboardRemove(), parse_mode="HTML"
            )
        user["eaten_prompted"] = True
        return EATEN
    # המשך הלוגיקה הקיימת של eaten רק אם eaten_prompted כבר קיים


async def handle_daily_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle choices in daily menu."""
    if not update.message or not update.message.text:
        return MENU

    choice = update.message.text.strip()

    if choice == "לקבלת תפריט יומי מותאם אישית":
        await generate_personalized_menu(update, context)
        return MENU

    elif choice == "בניית ארוחה לפי מה שיש לי בבית":
        await update.message.reply_text(
            "פרטי לי מה יש לך בבית, לדוגמא - חזה עוף, בשר טחון, סלמון, פסטה וכו'",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
        return EATEN

    elif choice == "מה אכלתי היום":
        return await eaten(update, context)

    elif choice == "קבלת דוח":
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
            [KeyboardButton("לקבלת תפריט יומי מותאם אישית")],
            [KeyboardButton("מה אכלתי היום")],
            [KeyboardButton("בניית ארוחה לפי מה שיש לי בבית")],
            [KeyboardButton("קבלת דוח")],
            [KeyboardButton("תזכורות על שתיית מים")],
        ]
        await update.message.reply_text(
            "בחר/י פעולה:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
        return MENU

    elif choice == "תזכורות על שתיית מים":
        await water_intake_start(update, context)
        return "WATER_AMOUNT"

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

            # Simple estimate of protein, fat, carbs (15%, 30%, 55% of
            # calories)
            estimated_protein = (total_eaten * 0.15) / \
                4  # 4 calories per gram protein
            estimated_fat = (total_eaten * 0.30) / 9  # 9 calories per gram fat
            estimated_carbs = (total_eaten * 0.55) / \
                4  # 4 calories per gram carbs

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


async def schedule_menu(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE) -> int:
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
    """מטפל בטקסט חופשי ומסווג אותו."""
    text = update.message.text.strip()
    main_menu_buttons = [
        "לקבלת תפריט יומי מותאם אישית",
        "מה אכלתי היום",
        "בניית ארוחה לפי מה שיש לי בבית",
        "קבלת דוח",
        "תזכורות על שתיית מים",
    ]
    if text in main_menu_buttons:
        return await handle_daily_choice(update, context)

    text_type = classify_text_input(text)

    if text_type == "question":
        # טיפול בשאלה
        await update.message.reply_text(
            "זיהיתי שזו שאלה. אנא השתמש/י בתפריט הראשי או פנה/י אליי ישירות עם השאלה שלך.",
            reply_markup=ReplyKeyboardMarkup(
                build_main_keyboard(), resize_keyboard=True
            ),
        )
        return ConversationHandler.END

    elif text_type == "food_list":
        # טיפול ברשימת מאכלים
        return await handle_food_report(update, context, text)

    else:
        # טקסט לא מזוהה
        await update.message.reply_text(
            "לא הצלחתי לזהות אם זו רשימת מאכלים או שאלה.\n\n"
            "אם זו רשימת מאכלים, אנא כתוב אותם עם פסיקים ביניהם.\n"
            "אם זו שאלה, אנא השתמש/י בתפריט הראשי.",
            reply_markup=ReplyKeyboardMarkup(
                build_main_keyboard(), resize_keyboard=True
            ),
        )
        return ConversationHandler.END


async def handle_food_report(
    update: Update, context: ContextTypes.DEFAULT_TYPE, food_text: str = None
):
    """מטפל בדיווח אכילה."""
    if food_text is None:
        food_text = update.message.text.strip()

    # ניקוי הטקסט
    cleaned_food = clean_meal_text(food_text)

    # שמירה במסד נתונים
    user_id = update.effective_user.id
    meal_data = {
        "date": date.today().isoformat(),
        "meal_type": "snack",
        "description": cleaned_food,
        "calories": 0,  # TODO: חישוב קלוריות אוטומטי
        "protein": 0.0,
        "carbs": 0.0,
        "fat": 0.0,
    }

    if save_food_entry(user_id, meal_data):
        # עדכון context
        if "eaten_today" not in context.user_data:
            context.user_data["eaten_today"] = []
        context.user_data["eaten_today"].append(cleaned_food)

        await update.message.reply_text(
            f"תודה! רשמתי שאכלת: {cleaned_food}\n\n" "האם יש עוד משהו שאכלת היום?",
            reply_markup=ReplyKeyboardMarkup([["סיימתי"]], resize_keyboard=True),
        )
        return "FOOD_REPORT"
    else:
        await update.message.reply_text(
            "שגיאה בשמירת הדיווח. אנא נסה שוב.",
            reply_markup=ReplyKeyboardMarkup(
                build_main_keyboard(), resize_keyboard=True
            ),
        )
        return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "<b>עזרה - קלוריקו</b>\n\n"
        "פקודות:\n"
        "/start - התחלה מחדש\n"
        "/help - עזרה\n"
        "/cancel - ביטול פעולה\n"
        "/reset - איפוס נתונים\n"
        "/report - דוח מהיר\n"
        "/reports - תפריט דוחות\n"
        "/shititi - דיווח שתיית מים\n"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")


async def generate_personalized_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Generate a personalized daily menu based on user profile."""
    user = context.user_data if context.user_data else {}

    # Create comprehensive user profile for GPT
    user_profile = {
        "name": user.get("name", ""),
        "gender": user.get("gender", ""),
        "age": user.get("age", 0),
        "height_cm": user.get("height", 0),
        "weight_kg": user.get("weight", 0),
        "goal": user.get("goal", ""),
        "diet_preferences": user.get("diet", []),
        "allergies": user.get("allergies", []),
        "activity_type": user.get("activity_type", ""),
        "activity_frequency": user.get("activity_frequency", ""),
        "activity_duration": user.get("activity_duration", ""),
        "training_time": user.get("training_time", ""),
        "cardio_goal": user.get("cardio_goal", ""),
        "strength_goal": user.get("strength_goal", ""),
        "takes_supplements": user.get("takes_supplements", False),
        "supplements": user.get("supplements", []),
        "limitations": user.get("limitations", ""),
        "mixed_activities": user.get("mixed_activities", []),
        "mixed_frequency": user.get("mixed_frequency", ""),
        "menu_adaptation": user.get("menu_adaptation", False),
        "calorie_budget": user.get("calorie_budget", 1800),
    }

    # Create prompt for GPT
    prompt = f"""בנה תפריט יומי מותאם אישית עבור המשתמש/ת הבא/ה:

פרופיל המשתמש/ת:
- שם: {user_profile['name']}
- מגדר: {user_profile['gender']}
- גיל: {user_profile['age']}
- גובה: {user_profile['height_cm']} ס"מ
- משקל: {user_profile['weight_kg']} ק"ג
- מטרה: {user_profile['goal']}
- תקציב קלורי יומי: {user_profile['calorie_budget']} קלוריות
- העדפות תזונה: {', '.join(user_profile['diet_preferences'])}
- אלרגיות: {', '.join(user_profile['allergies']) if user_profile['allergies'] else 'אין'}
- סוג פעילות: {user_profile['activity_type']}
- תדירות פעילות: {user_profile['activity_frequency']}
- משך פעילות: {user_profile['activity_duration']}

בנה תפריט יומי מלא הכולל:
1. ארוחת בוקר (כ-25% מהקלוריות היומיות)
2. ארוחת צהריים (כ-35% מהקלוריות היומיות)
3. ארוחת ערב (כ-30% מהקלוריות היומיות)
4. 2-3 נשנושים (כ-10% מהקלוריות היומיות)

התפריט צריך להיות:
- מותאם למטרה של המשתמש/ת
- מתחשב בהעדפות התזונה והאלרגיות
- מתאים לפעילות הגופנית
- מגוון וטעים
- עם הסברים קצרים לכל מנה

הצג את התפריט בפורמט HTML עם כותרות, רשימות, ואחוזי קלוריות לכל ארוחה."""

    try:
        # Generate menu using GPT
        response = await get_openai_client().chat.completions.create(
            model="gpt-4o", messages=[{"role": "user", "content": prompt}]
        )
        menu_text = extract_openai_response_content(response)

        # Send the personalized menu
        await update.message.reply_text(
            f"<b>🍽️ תפריט יומי מותאם אישית עבור {user_profile['name']}</b>\n\n{menu_text}",
            parse_mode="HTML",
        )

        # Show main menu again
        keyboard = [
            [KeyboardButton("לקבלת תפריט יומי מותאם אישית")],
            [KeyboardButton("מה אכלתי היום")],
            [KeyboardButton("בניית ארוחה לפי מה שיש לי בבית")],
            [KeyboardButton("קבלת דוח")],
            [KeyboardButton("תזכורות על שתיית מים")],
        ]
        gender = user.get("gender", "זכר")
        action_text = "מה תרצי לעשות כעת?" if gender == "נקבה" else "מה תרצה לעשות כעת?"
        await update.message.reply_text(
            action_text,
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode="HTML",
        )

    except Exception as e:
        logger.error(f"Error generating personalized menu: {e}")
        await update.message.reply_text(
            "מצטער, לא הצלחתי ליצור תפריט מותאם אישית כרגע. נסה/י שוב מאוחר יותר.",
            parse_mode="HTML",
        )

