import os

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
USERS_FILE = "calorico_users.json"

# Conversation states
(
    NAME,
    AGE,
    GENDER,
    HEIGHT,
    WEIGHT,
    GOAL,
    ACTIVITY_YES_NO,
    ACTIVITY,
    ACTIVITY_TYPE,
    ACTIVITY_FREQUENCY,
    ACTIVITY_DURATION,
    MIXED_ACTIVITIES,
    MIXED_FREQUENCY,
    MIXED_DURATION,
    MIXED_MENU_ADAPTATION,
    ALLERGIES,
    ALLERGIES_ADDITIONAL,
    DIET,
    DIET_OPTIONS,
    ACTIVITY_YES_NO_OPTIONS,
    BODY_FAT,
    BODY_FAT_TARGET,
    TRAINING_TIME,
    CARDIO_GOAL,
    STRENGTH_GOAL,
    SUPPLEMENTS,
    SUPPLEMENT_TYPES,
    LIMITATIONS,
    MENU,
    DAILY,
    EATEN,
    SUMMARY,
    SCHEDULE,
    EDIT,
    WATER_REMINDER_OPT_IN,
) = range(35)

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

# New simplified activity options
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
    "15-30 דקות",
    "30-45 דקות",
    "45-60 דקות",
    "60+ דקות",
]

TRAINING_TIME_OPTIONS = [
    "בוקר",
    "צהריים",
    "ערב",
]

CARDIO_GOAL_OPTIONS = [
    "ירידה במשקל",
    "שיפור סיבולת לב-ריאה",
    "תחזוקה כללית",
]

STRENGTH_GOAL_OPTIONS = [
    "חיטוב",
    "עלייה במסת שריר",
    "ירידה באחוזי שומן",
    "שילוב",
]

SUPPLEMENT_OPTIONS = [
    "אבקת חלבון",
    "קראטין",
    "מולטי ויטמין",
    "אומגה 3",
    "BCAA",
    "אחר",
]

MIXED_ACTIVITY_OPTIONS = [
    "אימוני כוח",
    "הליכה / ריצה",
    "יוגה / פילאטיס",
    "אימוני HIIT",
    "שחייה",
    "אופניים",
    "ספורט קבוצתי",
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

MIXED_DURATION_OPTIONS = [
    ["15-30 דקות"],
    ["30-45 דקות"],
    ["45-60 דקות"],
    ["60-90 דקות"],
    ["90+ דקות"],
]

MIXED_FREQUENCY_OPTIONS = [
    ["1-2 פעמים בשבוע"],
    ["3-4 פעמים בשבוע"],
    ["5-6 פעמים בשבוע"],
    ["כל יום"],
]

# אפשר להוסיף כאן קבועים נוספים בעתיד
