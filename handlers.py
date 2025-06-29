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
    ACTIVITY_OPTIONS_FEMALE,
    ACTIVITY_OPTIONS_MALE,
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
    MIXED_ACTIVITY_OPTIONS,
    MIXED_FREQUENCY,
    MIXED_MENU_ADAPTATION,
    ALLERGIES,
    BODY_FAT,
    BODY_FAT_TARGET,
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
    SUMMARY,
    WEIGHT,
    SYSTEM_BUTTONS,
    GENDERED_ACTION,
    USERS_FILE,
    AGE,
    GOAL,
    BODY_FAT,
    ACTIVITY,
    DIET,
    SUMMARY,
    ACTIVITY_TYPE_OPTIONS,
    DIET_OPTIONS,
    ACTIVITY_YES_NO_OPTIONS,
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
        
        # Ask for name directly
        await update.message.reply_text(
            "מה השם שלך?",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש לשמו וממשיך לשאלת מגדר."""
    logger.info(f"get_name called with text: {update.message.text if update.message and update.message.text else 'None'}")
    if update.message and update.message.text:
        # This is when user provides their name
        name = update.message.text.strip()
        logger.info(f"Name provided: '{name}'")
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
    else:
        # This is when called from start function - ask for name
        logger.info("get_name called from start - asking for name")
        if update.message:
            await update.message.reply_text(
                "מה השם שלך?",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML",
            )
        return NAME


async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש למגדר וממשיך לשאלת גיל."""
    logger.info(f"get_gender called with text: {update.message.text if update.message and update.message.text else 'None'}")
    if update.message and update.message.text:
        gender = update.message.text.strip()
        logger.info(f"Gender selected: '{gender}', valid options: {GENDER_OPTIONS}")
        if gender not in GENDER_OPTIONS:
            logger.warning(f"Invalid gender selected: '{gender}'")
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
        logger.info(f"Gender saved: {gender}")
        gender_text = "בת כמה את?" if gender == "נקבה" else "בן כמה אתה?"
        await update.message.reply_text(
            gender_text,
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
        return AGE
    else:
        logger.error("get_gender called without text")
        return GENDER


async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש גילו וממשיך לשאלת גובה."""
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
                'מה אחוזי השומן שלך? (אם לא ידוע, בחר/י "לא ידוע")',
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


async def get_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש האם הוא עושה פעילות גופנית."""
    if update.message and update.message.text:
        activity_answer = update.message.text.strip()
        if activity_answer not in ACTIVITY_YES_NO_OPTIONS:
            keyboard = [[KeyboardButton(opt)] for opt in ACTIVITY_YES_NO_OPTIONS]
            gender = context.user_data.get("gender", "זכר") if context.user_data else "זכר"
            if gender == "נקבה":
                error_text = "בחרי כן או לא מהתפריט למטה:"
            elif gender == "זכר":
                error_text = "בחר כן או לא מהתפריט למטה:"
            else:
                error_text = "בחר/י כן או לא מהתפריט למטה:"
            await update.message.reply_text(
                error_text,
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
            return ACTIVITY
        
        context.user_data["does_activity"] = activity_answer
        
        if activity_answer == "לא":
            # Skip to diet questions
            keyboard = [[KeyboardButton(opt)] for opt in DIET_OPTIONS]
            gender = context.user_data.get("gender", "זכר") if context.user_data else "זכר"
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
        else:
            # Ask for activity type
            keyboard = [[KeyboardButton(opt)] for opt in ACTIVITY_TYPE_OPTIONS]
            gender = context.user_data.get("gender", "זכר") if context.user_data else "זכר"
            if gender == "נקבה":
                activity_text = "איזו פעילות גופנית את עושה?"
            elif gender == "זכר":
                activity_text = "איזו פעילות גופנית אתה עושה?"
            else:
                activity_text = "איזו פעילות גופנית את/ה עושה?"
            await update.message.reply_text(
                activity_text,
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
            return ACTIVITY_TYPE
    else:
        # First time asking the question
        keyboard = [[KeyboardButton(opt)] for opt in ACTIVITY_YES_NO_OPTIONS]
        gender = context.user_data.get("gender", "זכר") if context.user_data else "זכר"
        if gender == "נקבה":
            question_text = "האם את עושה פעילות גופנית?"
        elif gender == "זכר":
            question_text = "האם אתה עושה פעילות גופנית?"
        else:
            question_text = "האם את/ה עושה פעילות גופנית?"
        await update.message.reply_text(
            question_text,
            reply_markup=ReplyKeyboardMarkup(
                keyboard, one_time_keyboard=True, resize_keyboard=True
            ),
            parse_mode="HTML",
        )
        return ACTIVITY


async def get_activity_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש לסוג הפעילות וממשיך לשאלות המתאימות."""
    if update.message and update.message.text:
        activity_type = update.message.text.strip()
        if activity_type not in ACTIVITY_TYPE_OPTIONS:
            keyboard = [[KeyboardButton(opt)] for opt in ACTIVITY_TYPE_OPTIONS]
            await update.message.reply_text(
                "בחר/י סוג פעילות מהתפריט למטה:",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
            return ACTIVITY_TYPE
        
        context.user_data["activity_type"] = activity_type
        
        # Route to appropriate next question based on activity type
        if activity_type in ["אין פעילות", "הליכה קלה"]:
            # Skip to diet questions
            keyboard = [[KeyboardButton(opt)] for opt in DIET_OPTIONS]
            gender = context.user_data.get("gender", "זכר") if context.user_data else "זכר"
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
            keyboard = [[KeyboardButton(opt)] for opt in ACTIVITY_FREQUENCY_OPTIONS]
            gender = context.user_data.get("gender", "זכר") if context.user_data else "זכר"
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
            keyboard = [[KeyboardButton(opt)] for opt in ACTIVITY_FREQUENCY_OPTIONS]
            gender = context.user_data.get("gender", "זכר") if context.user_data else "זכר"
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
            keyboard = [[KeyboardButton(opt)] for opt in ACTIVITY_FREQUENCY_OPTIONS]
            gender = context.user_data.get("gender", "זכר") if context.user_data else "זכר"
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
            keyboard = [[KeyboardButton(opt)] for opt in MIXED_ACTIVITY_OPTIONS]
            gender = context.user_data.get("gender", "זכר") if context.user_data else "זכר"
            if gender == "נקבה":
                mixed_text = "אילו סוגי אימונים את מבצעת במהלך השבוע? (בחרי כל מה שמתאים)"
            elif gender == "זכר":
                mixed_text = "אילו סוגי אימונים אתה מבצע במהלך השבוע? (בחר כל מה שמתאים)"
            else:
                mixed_text = "אילו סוגי אימונים את/ה מבצע/ת במהלך השבוע? (בחר/י כל מה שמתאים)"
            await update.message.reply_text(
                mixed_text,
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
            return MIXED_ACTIVITIES
        
        return DIET


async def get_activity_frequency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש לתדירות הפעילות וממשיך לשאלה הבאה."""
    if update.message and update.message.text:
        frequency = update.message.text.strip()
        if frequency not in ACTIVITY_FREQUENCY_OPTIONS:
            keyboard = [[KeyboardButton(opt)] for opt in ACTIVITY_FREQUENCY_OPTIONS]
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


async def get_activity_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש למשך הפעילות וממשיך לשאלה הבאה."""
    if update.message and update.message.text:
        duration = update.message.text.strip()
        if duration not in ACTIVITY_DURATION_OPTIONS:
            keyboard = [[KeyboardButton(opt)] for opt in ACTIVITY_DURATION_OPTIONS]
            await update.message.reply_text(
                "בחר/י משך מהתפריט למטה:",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
            return ACTIVITY_DURATION
        
        context.user_data["activity_duration"] = duration
        activity_type = context.user_data.get("activity_type", "")
        
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


async def get_training_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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


async def get_cardio_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
        
        context.user_data["cardio_goal"] = goal
        
        # Continue to diet questions
        keyboard = [[KeyboardButton(opt)] for opt in DIET_OPTIONS]
        gender = context.user_data.get("gender", "זכר") if context.user_data else "זכר"
        diet_text = "מה העדפות התזונה שלך? (בחרי כל מה שמתאים)" if gender == "נקבה" else "מה העדפות התזונה שלך? (בחר/י כל מה שמתאים)"
        await update.message.reply_text(
            diet_text,
            reply_markup=ReplyKeyboardMarkup(
                keyboard, one_time_keyboard=True, resize_keyboard=True
            ),
            parse_mode="HTML",
        )
        return DIET


async def get_strength_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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


async def get_supplements(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
        
        context.user_data["takes_supplements"] = (choice == "כן")
        
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


async def get_supplement_types(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש לסוגי התוספים וממשיך לשאלת מגבלות."""
    if update.message and update.message.text:
        supplements_text = update.message.text.strip()
        
        # Parse selected supplements
        selected_supplements = []
        for option in SUPPLEMENT_OPTIONS:
            if option in supplements_text:
                selected_supplements.append(option)
        
        context.user_data["supplements"] = selected_supplements
        
        # Ask about limitations
        await update.message.reply_text(
            "האם יש מגבלות פיזיות / כאבים? (אם לא, כתוב 'אין')",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )
        return LIMITATIONS


async def get_limitations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש על מגבלות וממשיך לתזונה."""
    if update.message and update.message.text:
        limitations = update.message.text.strip()
        if limitations.lower() in ["אין", "לא", "ללא"]:
            context.user_data["limitations"] = "אין"
        else:
            context.user_data["limitations"] = limitations
        
        # Continue to diet questions
        keyboard = [[KeyboardButton(opt)] for opt in DIET_OPTIONS]
        gender = context.user_data.get("gender", "זכר") if context.user_data else "זכר"
        diet_text = "מה העדפות התזונה שלך? (בחרי כל מה שמתאים)" if gender == "נקבה" else "מה העדפות התזונה שלך? (בחר/י כל מה שמתאים)"
        await update.message.reply_text(
            diet_text,
            reply_markup=ReplyKeyboardMarkup(
                keyboard, one_time_keyboard=True, resize_keyboard=True
            ),
            parse_mode="HTML",
        )
        return DIET


async def get_mixed_activities(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש לסוגי הפעילויות המעורבות וממשיך לשאלה הבאה."""
    if update.message and update.message.text:
        activities_text = update.message.text.strip()
        
        # Parse selected activities
        selected_activities = []
        for option in MIXED_ACTIVITY_OPTIONS:
            if option in activities_text:
                selected_activities.append(option)
        
        if not selected_activities:
            keyboard = [[KeyboardButton(opt)] for opt in MIXED_ACTIVITY_OPTIONS]
            await update.message.reply_text(
                "בחר/י לפחות פעילות אחת מהתפריט למטה:",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
            return MIXED_ACTIVITIES
        
        context.user_data["mixed_activities"] = selected_activities
        
        # Ask about frequency
        keyboard = [[KeyboardButton(opt)] for opt in ACTIVITY_FREQUENCY_OPTIONS]
        await update.message.reply_text(
            "כמה פעמים בשבוע את/ה עושה כל סוג?",
            reply_markup=ReplyKeyboardMarkup(
                keyboard, one_time_keyboard=True, resize_keyboard=True
            ),
            parse_mode="HTML",
        )
        return MIXED_FREQUENCY


async def get_mixed_frequency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש לתדירות הפעילויות המעורבות וממשיך לשאלה הבאה."""
    if update.message and update.message.text:
        frequency = update.message.text.strip()
        if frequency not in ACTIVITY_FREQUENCY_OPTIONS:
            keyboard = [[KeyboardButton(opt)] for opt in ACTIVITY_FREQUENCY_OPTIONS]
            await update.message.reply_text(
                "בחר/י תדירות מהתפריט למטה:",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard, one_time_keyboard=True, resize_keyboard=True
                ),
                parse_mode="HTML",
            )
            return MIXED_FREQUENCY
        
        context.user_data["mixed_frequency"] = frequency
        
        # Ask about menu adaptation
        keyboard = [[KeyboardButton("כן"), KeyboardButton("לא")]]
        await update.message.reply_text(
            "האם את/ה רוצה שהתפריט יותאם לפי הימים השונים?",
            reply_markup=ReplyKeyboardMarkup(
                keyboard, one_time_keyboard=True, resize_keyboard=True
            ),
            parse_mode="HTML",
        )
        return MIXED_MENU_ADAPTATION


async def get_mixed_menu_adaptation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
        
        context.user_data["menu_adaptation"] = (choice == "כן")
        
        # Continue to diet questions
        keyboard = [[KeyboardButton(opt)] for opt in DIET_OPTIONS]
        gender = context.user_data.get("gender", "זכר") if context.user_data else "זכר"
        diet_text = "מה העדפות התזונה שלך? (בחרי כל מה שמתאים)" if gender == "נקבה" else "מה העדפות התזונה שלך? (בחר/י כל מה שמתאים)"
        await update.message.reply_text(
            diet_text,
            reply_markup=ReplyKeyboardMarkup(
                keyboard, one_time_keyboard=True, resize_keyboard=True
            ),
            parse_mode="HTML",
        )
        return DIET


async def get_diet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """שואל את המשתמש להעדפות תזונה וממשיך לשאלת אלרגיות."""
    if update.message and update.message.text:
        diet_text = update.message.text.strip()
        
        # Handle multiple selections
        if "אין העדפות מיוחדות" in diet_text:
            selected_diet = ["אין העדפות מיוחדות"]
        else:
            # Parse selected diet options
            selected_diet = []
            for option in DIET_OPTIONS:
                if option in diet_text:
                    selected_diet.append(option)
            
            # If no specific options selected, default to no preferences
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
        
        # Save user data
        user_id = update.effective_user.id if update.effective_user else None
        if user_id:
            save_user(user_id, context.user_data)
        
        # Show calorie budget in separate message
        await update.message.reply_text(
            f"<b>תקציב הקלוריות היומי שלך: {calorie_budget} קלוריות</b>",
            parse_mode="HTML",
        )
        
        # Create comprehensive user profile JSON
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
            "calorie_budget": calorie_budget,
        }
        
        # Show summary
        summary = f"""<b>סיכום הנתונים שלך:</b>
• שם: {user.get('name', 'לא צוין')}
• מגדר: {user.get('gender', 'לא צוין')}
• גיל: {user.get('age', 'לא צוין')}
• גובה: {user.get('height', 'לא צוין')} ס"מ
• משקל: {user.get('weight', 'לא צוין')} ק"ג
• מטרה: {user.get('goal', 'לא צוינה')}
• סוג פעילות: {user.get('activity_type', 'לא צוין')}
• תזונה: {', '.join(user.get('diet', []))}
• אלרגיות: {', '.join(user.get('allergies', [])) if user.get('allergies') else 'אין'}"""
        
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
    
    # After water answer - show new main menu
    keyboard = [
        [KeyboardButton("מה אכלתי היום")],
        [KeyboardButton("בניית ארוחה לפי מה שיש לי בבית")],
        [KeyboardButton("קבלת דוח")],
        [KeyboardButton("תזכורות על שתיית מים")],
    ]
    gender = context.user_data.get("gender", "זכר") if context.user_data else "זכר"
    action_text = "מה תרצי לעשות כעת?" if gender == "נקבה" else "מה תרצה לעשות כעת?"
    await update.message.reply_text(
        action_text,
        reply_markup=ReplyKeyboardMarkup(
            keyboard, resize_keyboard=True
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
    logger.info(f"handle_free_text_input called with text: {update.message.text if update.message and update.message.text else 'None'}")
    if not update.message or not update.message.text:
        return MENU

    user_text = update.message.text.strip()
    user_id = update.effective_user.id if update.effective_user else None
    user = context.user_data if context.user_data else {}


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
