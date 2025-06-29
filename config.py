import os

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
USERS_FILE = "calorico_users.json"

# Conversation states
(
    NAME,
    GENDER,
    AGE,
    HEIGHT,
    WEIGHT,
    GOAL,
    BODY_FAT,
    ACTIVITY,
    ACTIVITY_TYPE,
    DIET,
    ALLERGIES,
    MENU,
    DAILY,
    EATEN,
    SUMMARY,
    SCHEDULE,
    EDIT,
    BODY_FAT_TARGET,
) = range(18)

GENDER_OPTIONS = ["זכר", "נקבה", "אחר"]
GOAL_OPTIONS = [
    "ירידה במשקל",
    "חיטוב",
    "שמירה",
    "עלייה במסת שריר",
    "עלייה כללית",
    "שיפור ספורט",
    "פשוט תזונה בריאה",
    "לרדת באחוזי שומן",
]
ACTIVITY_OPTIONS_MALE = [
    "לא מתאמן",
    "מעט (2-3 אימונים בשבוע)",
    "הרבה (4-5 אימונים בשבוע)",
    "כל יום",
]
ACTIVITY_OPTIONS_FEMALE = [
    "לא מתאמנת",
    "מעט (2-3 אימונים בשבוע)",
    "הרבה (4-5 אימונים בשבוע)",
    "כל יום",
]

ACTIVITY_TYPE_OPTIONS = [
    "אימוני כוח",
    "אימוני כושר",
    "ריצה",
    "שחייה",
    "אופניים",
    "יוגה",
    "פילאטיס",
    "ספורט קבוצתי",
    "הליכה",
    "אין סוג ספציפי",
]

DIET_OPTIONS = [
    "צמחוני",
    "טבעוני",
    "קטוגני",
    "ללא גלוטן",
    "ללא לקטוז",
    "דל פחמימות",
    "דל שומן",
    "דל נתרן",
    "פאלאו",
    "אין העדפות מיוחדות",
]

# System buttons and gendered actions
SYSTEM_BUTTONS = [
    "להרכבת ארוחה לפי מה שיש בבית",
    "מה אכלתי היום",
    "📊 דוחות",
    "סיימתי",
    "שתיתי",
    "שתיתי, תודה",
    "תזכיר לי בעוד עשר דקות",
    "תפסיק להזכיר לי לשתות מים",
    "ביטול תזכורות מים",
    "תפסיק תזכורות מים",
]

GENDERED_ACTION = {
    "זכר": "בחר פעולה:",
    "נקבה": "האם סיימת לאכול להיום?",
    "אחר": "בחר/י פעולה:",
}

# אפשר להוסיף כאן קבועים נוספים בעתיד
