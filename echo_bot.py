from telegram.ext import Application, MessageHandler, filters
import os

async def echo(update, context):
    print(f"Received: {update.message.text}")
    await update.message.reply_text(update.message.text)

if __name__ == "__main__":
    token = os.getenv("TELEGRAM_TOKEN")
    app = Application.builder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    app.run_polling() 