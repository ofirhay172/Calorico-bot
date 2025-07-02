#!/usr/bin/env python3
"""
Startup script for Railway deployment
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

def main():
    """Initialize and start the bot"""
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
        bot_main()
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 