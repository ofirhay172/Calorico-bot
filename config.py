"""Configuration constants for the Calorico nutrition bot.

This module contains all the configuration constants used throughout the bot,
including conversation states, keyboard options, and system settings.
"""

from typing import Dict, List

# Conversation states
NAME = 1
GENDER = 2
AGE = 3
HEIGHT = 4
WEIGHT = 5
GOAL = 6
BODY_FAT_CURRENT = 7
BODY_FAT_TARGET_GOAL = 8
ACTIVITY = 9
ACTIVITY_TYPE = 10
ACTIVITY_FREQUENCY = 11
ACTIVITY_DURATION = 12
TRAINING_TIME = 13
CARDIO_GOAL = 14
STRENGTH_GOAL = 15
SUPPLEMENTS = 16
SUPPLEMENT_TYPES = 17
LIMITATIONS = 18
MIXED_ACTIVITIES = 19
MIXED_FREQUENCY = 20
MIXED_DURATION = 21
MIXED_MENU_ADAPTATION = 22
DIET = 23
ALLERGIES = 24
ALLERGIES_ADDITIONAL = 25
WATER_REMINDER_OPT_IN = 26
DAILY = 27
EATEN = 28
MENU = 29
SCHEDULE = 30
SUMMARY = 31
EDIT = 32
BODY_FAT = 33
BODY_FAT_TARGET = 34

# Gender options
GENDER_OPTIONS = ["זכר", "נקבה", "אחר"]

# Goal options
GOAL_OPTIONS = [
    "ירידה במשקל",
    "ירידה באחוזי שומן",
    "שמירה על משקל",
    "עלייה במשקל",
    "בניית שריר",
]

# Activity options
ACTIVITY_YES_NO_OPTIONS = ["כן", "לא"]

ACTIVITY_TYPE_OPTIONS = [
    "אין פעילות",
    "הליכה קלה",
    "הליכה מהירה / ריצה קלה",
    "אימוני כוח",
    "אימוני HIIT / קרוספיט",
    "יוגה / פילאטיס",
    "שילוב של כמה סוגים",
]

ACTIVITY_FREQUENCY_OPTIONS = [
    "1-2 פעמים בשבוע",
    "3-4 פעמים בשבוע",
    "5-6 פעמים בשבוע",
    "כל יום",
]

ACTIVITY_DURATION_OPTIONS = [
    "פחות מ-30 דקות",
    "30-45 דקות",
    "45-60 דקות",
    "יותר מ-60 דקות",
]

TRAINING_TIME_OPTIONS = [
    "בוקר (6:00-9:00)",
    "צהריים (12:00-14:00)",
    "אחר הצהריים (15:00-18:00)",
    "ערב (19:00-22:00)",
]

CARDIO_GOAL_OPTIONS = [
    "שיפור סיבולת לב-ריאה",
    "שריפת שומן",
    "שיפור ביצועים",
    "בריאות כללית",
]

STRENGTH_GOAL_OPTIONS = [
    "בניית שריר",
    "חיזוק כללי",
    "שיפור כוח",
    "שיפור יציבה",
]

SUPPLEMENT_OPTIONS = [
    "חלבון",
    "קריאטין",
    "ויטמין D",
    "אומגה 3",
    "מולטי-ויטמין",
    "BCAA",
    "גלוטמין",
    "אחר",
]

# Diet options
DIET_OPTIONS = [
    "אין העדפות מיוחדות",
    "צמחוני",
    "טבעוני",
    "קטוגני",
    "דל פחמימות",
    "דל שומן",
    "גלוטן חופשי",
    "חלב חופשי",
    "דל נתרן",
    "דל סוכר",
    "פליאו",
    "מדיטראני",
    "אחר",
]

# Mixed activities options
MIXED_ACTIVITY_OPTIONS = [
    "הליכה",
    "ריצה",
    "אימוני כוח",
    "יוגה",
    "פילאטיס",
    "שחייה",
    "רכיבה",
    "אימוני HIIT",
    "קרוספיט",
    "אין",
]

MIXED_FREQUENCY_OPTIONS = [
    "1-2 פעמים בשבוע",
    "3-4 פעמים בשבוע",
    "5-6 פעמים בשבוע",
    "כל יום",
]

MIXED_DURATION_OPTIONS = [
    "פחות מ-30 דקות",
    "30-45 דקות",
    "45-60 דקות",
    "יותר מ-60 דקות",
]

# Allergy options
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

# System buttons
SYSTEM_BUTTONS = [
    "לקבלת תפריט יומי מותאם אישית",
    "מה אכלתי היום",
    "בניית ארוחה לפי מה שיש לי בבית",
    "קבלת דוח",
    "תזכורות על שתיית מים",
]

# Gendered action text
GENDERED_ACTION = {
    "זכר": {
        "choose": "בחר",
        "you": "אתה",
        "your": "שלך",
        "do": "עושה",
        "train": "מתאמן",
        "perform": "מבצע",
        "want": "תרצה",
        "select": "בחר",
    },
    "נקבה": {
        "choose": "בחרי",
        "you": "את",
        "your": "שלך",
        "do": "עושה",
        "train": "מתאמנת",
        "perform": "מבצעת",
        "want": "תרצי",
        "select": "בחרי",
    },
}

# Water reminder options
WATER_REMINDER_OPT_IN = ["כן", "לא"]

USERS_FILE = "users.json"
DB_NAME = "nutrition.db"
