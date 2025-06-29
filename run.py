#!/usr/bin/env python3
"""
Simple runner script for Calorico Telegram Bot.
"""

import os
import sys

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    from main import main
    main() 