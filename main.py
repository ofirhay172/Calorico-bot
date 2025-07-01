"""
Main entry point for the Calorico nutrition bot.

This module initializes and runs the Telegram bot with all necessary handlers
and conversation flows for nutrition management.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import CallbackQueryHandler
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import (
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
    ACTIVITY_TYPES_SELECTION,
    ALLERGIES,
    ALLERGIES_ADDITIONAL,
    DIET,
    GENDER,
    AGE,
    HEIGHT,
    WEIGHT,
    GOAL,
    BODY_FAT_CURRENT,
    BODY_FAT_TARGET_GOAL,
    WATER_REMINDER_OPT_IN,
    MENU,
    NAME,
    USERS_FILE,
    DB_NAME,
)
from handlers import (
    start,
    get_name,
    get_gender,
    get_age,
    get_height,
    get_weight,
    get_goal,
    get_body_fat_current,
    get_body_fat_target_goal,
    get_activity,
    get_activity_type,
    get_activity_frequency,
    get_activity_duration,
    get_training_time,
    get_cardio_goal,
    get_strength_goal,
    get_supplements,
    get_supplement_types,
    get_limitations,
    get_mixed_activities,
    get_mixed_frequency,
    get_mixed_duration,
    get_mixed_menu_adaptation,
    handle_activity_types_selection,
    get_diet,
    get_allergies,
    get_allergies_additional,
    ask_water_reminder_opt_in,
    set_water_reminder_opt_in,
    start_water_reminder_loop_with_buttons,
    send_water_reminder,
    cancel_water_reminders,
    daily_menu,
    eaten,
    handle_daily_choice,
    send_summary,
    schedule_menu,
    check_dessert_permission,
    after_questionnaire,
    handle_free_text_input,
    handle_food_report,
    help_command,
    generate_personalized_menu,
    show_daily_menu,
    water_intake_start,
    water_intake_amount,
    remind_in_10_minutes,
)
from utils import build_main_keyboard

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# File paths
DAILY_MENUS_FILE = "daily_menus.json"


async def daily_menu_scheduler(context):
    """שולח תפריט יומי למשתמשים שנרשמו לכך."""
    try:
        if not os.path.exists(USERS_FILE):
            logger.info(
                "Users file not found, skipping daily menu delivery")
            return

        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)

        for user_id_str, user_data in users.items():
            if user_data.get("daily_menu_enabled", False):
                try:
                    user_id = int(user_id_str)
                    await context.bot.send_message(
                        chat_id=user_id,
                        text="🍽️ התפריט היומי שלך מוכן! לחץ על 'לקבלת תפריט יומי מותאם אישית'",
                        reply_markup=build_main_keyboard(),
                    )
                    logger.info("Sent daily menu to user %s", user_id_str)
                except Exception as e:
                    logger.error(
                        "Error sending daily menu to user %s: %s", user_id_str, e)
    except Exception as e:
        logger.error("Error in daily menu scheduler: %s", e)


def main():
    """הפונקציה הראשית שמתחילה את הבוט."""
    # Get bot token from environment
    bot_token = os.getenv("TELEGRAM_TOKEN")
    if not bot_token:
        logger.error("TELEGRAM_TOKEN not found in environment variables")
        return

    # Create application
    application = Application.builder().token(bot_token).build()

    # Create conversation handler for questionnaire
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_gender)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_height)],
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_weight)],
            GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_goal)],
            BODY_FAT_CURRENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_body_fat_current)],
            BODY_FAT_TARGET_GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_body_fat_target_goal)],
            ACTIVITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_activity)],
            ACTIVITY_TYPES_SELECTION: [CallbackQueryHandler(handle_activity_types_selection)],
            ACTIVITY_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_activity_type)],
            ACTIVITY_FREQUENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_activity_frequency)],
            ACTIVITY_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_activity_duration)],
            TRAINING_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_training_time)],
            CARDIO_GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_cardio_goal)],
            STRENGTH_GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_strength_goal)],
            SUPPLEMENTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_supplements)],
            SUPPLEMENT_TYPES: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_supplement_types)],
            LIMITATIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_limitations)],
            MIXED_ACTIVITIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_mixed_activities)],
            MIXED_FREQUENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_mixed_frequency)],
            MIXED_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_mixed_duration)],
            MIXED_MENU_ADAPTATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_mixed_menu_adaptation)],
            DIET: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_diet)],
            ALLERGIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_allergies)],
            ALLERGIES_ADDITIONAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_allergies_additional)],
            WATER_REMINDER_OPT_IN: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_water_reminder_opt_in)],
        },
        fallbacks=[CommandHandler("help", help_command)],
    )

    application.add_handler(conv_handler)

    # Add handlers for main menu options
    menu_regex = r"^(לקבלת תפריט יומי מותאם אישית|מה אכלתי היום|בניית ארוחה לפי מה שיש לי בבית|קבלת דוח|תזכורות על שתיית מים)$"
    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(menu_regex),
            handle_daily_choice))

    # Add handler for free text input (only if not in conversation)
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & ~filters.Regex(menu_regex),
            handle_free_text_input
        )
    )

    # Add command handlers
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("menu", show_daily_menu))

    # Add global error handler
    async def global_error_handler(update, context):
        logger.error("Unhandled exception", exc_info=context.error)
    application.add_error_handler(global_error_handler)

    # Initialize scheduler
    # start_scheduler(application)  # TODO: Implement proper async
    # scheduler

    logger.info("Bot started successfully")
    application.run_polling()


if __name__ == "__main__":
    main()
