"""Main entry point for the Telegram nutrition bot."""

import asyncio
import json
import logging
import os
from datetime import datetime

import openai
from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import (
    USERS_FILE,
    NAME,
    GENDER,
    AGE,
    HEIGHT,
    WEIGHT,
    GOAL,
    BODY_FAT,
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
    MIXED_MENU_ADAPTATION,
    DIET,
    ALLERGIES,
    MENU,
    DAILY,
    EATEN,
    SUMMARY,
    SCHEDULE,
    EDIT,
    BODY_FAT_TARGET,
    ACTIVITY_YES_NO,
    ACTIVITY_YES_NO_OPTIONS,
    ALLERGIES_ADDITIONAL,
    DIET_OPTIONS,
    TELEGRAM_TOKEN,
)
from db import save_user
from handlers import (
    start,
    get_name,
    get_age,
    get_gender,
    get_height,
    get_weight,
    get_goal,
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
    get_allergies,
    get_allergies_additional,
    get_diet,
    handle_free_text_input,
    help_command,
    remind_in_10_minutes,
    schedule_menu,
    send_summary,
    send_water_reminder,
    set_water_reminder_opt_in,
    show_daily_menu,
    water_intake_amount,
    water_intake_start,
    ask_water_reminder_opt_in,
    cancel_water_reminders,
    daily_menu,
    eaten,
    generate_personalized_menu,
)
from utils import calculate_bmr, set_openai_client, build_main_keyboard, build_daily_menu

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


async def cancel(update, context):
    """Cancel the current conversation."""
    await update.message.reply_text(
        "הפעולה בוטלה. תוכל/י להתחיל מחדש עם /start",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


async def start_scheduler(application):
    """Start the scheduler for daily menu delivery."""
    async def send_daily_menus_to_all_users(application):
        now = datetime.now()
        current_time = now.strftime("%H:00")
        if not os.path.exists(USERS_FILE):
            return
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for user_id_str, user_data in data.items():
            schedule_time = user_data.get("schedule_time")
            if schedule_time == current_time:
                try:
                    chat_id = int(user_id_str)
                    menu_text = await build_daily_menu(user_data)
                    calorie_budget = user_data.get("calorie_budget", 1800)
                    keyboard = build_main_keyboard()
                    await application.bot.send_message(
                        chat_id=chat_id,
                        text=f"<b>התקציב היומי שלך: {calorie_budget} קלוריות</b>\n\n{menu_text}",
                        parse_mode="HTML",
                        reply_markup=ReplyKeyboardMarkup(
                            keyboard, resize_keyboard=True
                        ),
                    )
                    weight = user_data.get("weight", 70)
                    min_l = round(weight * 30 / 1000, 1)
                    max_l = round(weight * 35 / 1000, 1)
                    min_cups = round((weight * 30) / 240)
                    max_cups = round((weight * 35) / 240)
                    await application.bot.send_message(
                        chat_id=chat_id,
                        text=f"<b>המלצת שתייה להיום:</b> {min_l}–{max_l} ליטר מים (כ-{min_cups}–{max_cups} כוסות)",
                        parse_mode="HTML",
                    )
                except Exception as e:
                    logger.error(
                        f"שגיאה בשליחת תפריט יומי אוטומטי ל-{user_id_str}: {e}"
                    )

    async def scheduler_tick():
        await send_daily_menus_to_all_users(application)

    # Simple scheduler without APScheduler for now
    # TODO: Implement proper scheduler
    logger.info("Scheduler initialized (not yet implemented)")


def main():
    """הפונקציה הראשית של הבוט."""
    # יצירת הבוט
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # הוספת handlers
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_gender)],
            HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_height)],
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_weight)],
            GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_goal)],
            ACTIVITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_activity)],
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
            MIXED_MENU_ADAPTATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_mixed_menu_adaptation)],
            ALLERGIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_allergies)],
            ALLERGIES_ADDITIONAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_allergies_additional)],
            DIET: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_diet)],
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("help", help_command),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_free_text_input),
        ],
        name="nutrition_conversation",
        persistent=True,
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))
    # הוספת handler לטקסט חופשי
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_free_text_input))
    # הפעלת הבוט
    application.run_polling()


if __name__ == "__main__":
    main()
