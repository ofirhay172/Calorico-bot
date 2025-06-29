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
    DIET,
    ALLERGIES,
    MENU,
    DAILY,
    EATEN,
    SUMMARY,
    SCHEDULE,
    EDIT,
    BODY_FAT_TARGET,
)
from db import save_user
from handlers import (
    after_questionnaire,
    ask_water_reminder_opt_in,
    build_daily_menu,
    cancel_water_reminders,
    check_dessert_permission,
    daily_menu,
    eaten,
    get_activity,
    get_age,
    get_allergies,
    get_body_fat,
    get_body_fat_target,
    get_diet,
    get_gender,
    get_goal,
    get_height,
    get_name,
    get_weight,
    handle_daily_choice,
    handle_free_text_input,
    handle_reports_callback,
    help_command,
    menu_decision,
    remind_in_10_minutes,
    report_command,
    reports_command,
    reset_command,
    schedule_menu,
    send_summary,
    send_water_reminder,
    set_water_reminder_opt_in,
    show_daily_menu,
    show_menu_with_keyboard,
    show_reports_menu,
    start,
    water_intake_amount,
    water_intake_start,
)
from utils import calculate_bmr, set_openai_client, build_main_keyboard

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
    """Main function to set up and run the bot."""
    # Check for required environment variables
    telegram_token = os.environ.get("TELEGRAM_TOKEN")
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    
    if not telegram_token:
        logger.error("TELEGRAM_TOKEN environment variable is not set")
        return
    
    if not openai_api_key:
        logger.error("OPENAI_API_KEY environment variable is not set")
        return

    # Initialize OpenAI client
    openai_client = openai.AsyncOpenAI(api_key=openai_api_key)
    set_openai_client(openai_client)

    # Create application
    application = Application.builder().token(telegram_token).build()

    # Main conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
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
            BODY_FAT_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_body_fat_target)],
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("cancel", cancel),
            CommandHandler("help", help_command),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_free_text_input),
        ],
    )
    application.add_handler(conv_handler)

    # Water conversation handler
    water_conv = ConversationHandler(
        entry_points=[
            CommandHandler("shititi", water_intake_start),
            MessageHandler(filters.Regex("^שתיתי$"), water_intake_start),
            MessageHandler(filters.Regex("^שתיתי, תודה$"), water_intake_start),
        ],
        states={
            "WATER_AMOUNT": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, water_intake_amount)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    application.add_handler(water_conv)

    # Global handlers
    application.add_handler(
        MessageHandler(filters.Regex("^תזכיר לי בעוד עשר דקות$"), remind_in_10_minutes)
    )
    application.add_handler(
        MessageHandler(
            filters.Regex(
                "^(תפסיק להזכיר לי לשתות מים|ביטול תזכורות מים|תפסיק תזכורות מים)$"
            ),
            cancel_water_reminders,
        )
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_free_text_input)
    )

    # Command handlers
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(CommandHandler("report", report_command))
    application.add_handler(CommandHandler("reports", reports_command))

    # Callback query handler for reports
    application.add_handler(CallbackQueryHandler(handle_reports_callback))

    # Set up scheduler
    application.post_init = start_scheduler

    # Start the bot
    logger.info("Starting bot...")
    application.run_polling()


if __name__ == "__main__":
    main()
