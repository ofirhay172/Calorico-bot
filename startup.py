#!/usr/bin/env python3
"""
Startup script for Railway deployment
"""

import os
import sys
import logging
import asyncio
import signal

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info("Received shutdown signal, stopping bot...")
    sys.exit(0)

async def run_bot():
    """Run the bot in async mode"""
    try:
        # Check if required environment variables are set
        bot_token = os.getenv("TELEGRAM_TOKEN")
        if not bot_token:
            logger.error("TELEGRAM_TOKEN not found in environment variables")
            sys.exit(1)
            
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            logger.warning("OPENAI_API_KEY not found - GPT features will be limited")
        
        # Import and run the main bot
        from main import main as bot_main
        await bot_main()
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        sys.exit(1)

def main():
    """Initialize and start the bot"""
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Starting bot...")
    
    # Run the bot in async mode
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 