# 🍎 Calorico - Nutrition Telegram Bot

בוט טלגרם חכם לניהול תזונה אישית עם התאמה מגדרית מלאה.

## ✨ תכונות עיקריות

### 🍽️ **ניהול תזונה יומי**
- רישום ארוחות עם ניתוח קלוריות אוטומטי
- חישוב מאקרו-נוטריאנטים (חלבון, שומן, פחמימות)
- תפריטים יומיים מותאמים אישית
- בניית ארוחות מרכיבים זמינים

### 📊 **דוחות וניתוח**
- סיכום יומי, שבועי וחודשי
- פידבק חכם לאורך זמן
- ניתוח דפוסי אכילה
- המלצות מותאמות אישית

### ⏰ **תזכורות אוטומטיות**
- שליחת תפריטים יומיים בשעה שנבחרה
- תזכורות שתיית מים
- ניהול מצב יומי אוטומטי

### 🧠 **AI מתקדם**
- ניתוח ארוחות עם GPT
- המלצות תזונה מותאמות אישית
- מענה לשאלות תזונה כלליות
- בניית ארוחות מרכיבים זמינים

## 🚀 התקנה והפעלה

### Railway Deployment (מומלץ)

1. **Fork את הפרויקט** ל-GitHub שלך

2. **צור פרויקט חדש ב-Railway**
   - היכנס ל-[Railway](https://railway.app)
   - לחץ על "New Project"
   - בחר "Deploy from GitHub repo"
   - בחר את הפרויקט שלך

3. **הגדר Environment Variables**
   - `TELEGRAM_TOKEN` - הטוקן של הבוט שלך מ-BotFather
   - `OPENAI_API_KEY` - מפתח API של OpenAI

4. **הפעל את הבוט**
   - Railway יבנה ויפעיל את הבוט אוטומטית
   - הבוט יתחיל לעבוד מיד

### התקנה מקומית

1. **Clone את הפרויקט**
```bash
git clone https://github.com/your-username/yogev-bot.git
cd yogev-bot
```

2. **התקן dependencies**
```bash
pip install -r requirements.txt
```

3. **הגדר Environment Variables**
```bash
cp .env.example .env
# ערוך את .env עם הטוקנים שלך
```

4. **הפעל את הבוט**
```bash
python3 main.py
```

## 🔧 הגדרת Environment Variables

### Railway
- `TELEGRAM_TOKEN` - הטוקן של הבוט מ-BotFather
- `OPENAI_API_KEY` - מפתח API של OpenAI (אופציונלי)

### מקומי
צור קובץ `.env` עם:
```
TELEGRAM_TOKEN=your_bot_token_here
OPENAI_API_KEY=your_openai_key_here
```

## 📱 שימוש בבוט

### התחלה
- שלח `/start` לבוט
- מלא את השאלון האישי
- קבל תפריט יומי מותאם

### פקודות עיקריות
- `/start` - התחלה/איתחול
- `/help` - עזרה
- `/menu` - תפריט יומי

### כפתורים בתפריט
- **לקבלת תפריט יומי מותאם אישית** - תפריט יומי חדש
- **מה אכלתי היום** - סיכום יומי
- **בניית ארוחה לפי מה שיש לי בבית** - בניית ארוחה מרכיבים
- **קבלת דוח** - דוחות מפורטים
- **עזרה** - עזרה ותמיכה

## 🛠️ פתרון בעיות

### הבוט לא עולה ב-Railway
1. בדוק שה-Environment Variables מוגדרים נכון
2. בדוק את הלוגים ב-Railway Dashboard
3. וודא שה-Procfile מכיל `worker: python3 startup.py`

### שגיאות נפוצות
- **InvalidToken** - בדוק שה-TELEGRAM_TOKEN נכון
- **OpenAI API errors** - בדוק שה-OPENAI_API_KEY נכון
- **Database errors** - הבוט ייצור את המסד אוטומטית

## 📁 מבנה הפרויקט

```
yogev-bot/
├── main.py              # נקודת הכניסה הראשית
├── handlers.py          # handlers לכל הפונקציות
├── utils.py             # פונקציות עזר
├── db.py               # ניהול מסד נתונים
├── report_generator.py  # יצירת דוחות
├── config.py           # הגדרות
├── startup.py          # סקריפט הפעלה ל-Railway
├── Procfile            # הגדרת Railway
├── requirements.txt    # dependencies
└── runtime.txt         # גרסת Python
```

## 🔄 עדכונים אחרונים

### v2.0 - Enhanced Features
- ✅ שליחה אוטומטית של תפריטים כל 10 דקות
- ✅ ניתוח מדויק של כמויות מזון
- ✅ סיכום יומי מפורט
- ✅ בניית ארוחות מרכיבים זמינים
- ✅ פידבק חכם לאורך זמן
- ✅ טיפול מתקדם בטקסט חופשי
- ✅ התאמה מגדרית מלאה

## 📞 תמיכה

אם יש בעיות או שאלות:
1. בדוק את הלוגים ב-Railway Dashboard
2. פתח Issue ב-GitHub
3. בדוק את ה-README הזה

## 📄 רישיון

MIT License - ראה קובץ LICENSE לפרטים. 