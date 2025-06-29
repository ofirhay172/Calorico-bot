import sqlite3
import json
from config import USERS_FILE
import os
from datetime import datetime, date
from typing import Dict, List, Optional, Any


def init_db():
    """יוצר את טבלת nutrition_logs אם אינה קיימת."""
    with sqlite3.connect("nutrition_data.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS nutrition_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                date TEXT,
                calories INTEGER,
                protein REAL,
                fat REAL,
                carbs REAL,
                meals TEXT,
                goal TEXT
            )
            """
        )
        conn.commit()


def save_daily_entry(user_id, calories, protein, fat, carbs, meals_list, goal):
    """שומר כניסה יומית לטבלת nutrition_logs."""
    with sqlite3.connect("nutrition_data.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO nutrition_logs (user_id, date, calories, protein, fat, carbs, meals, goal)
            VALUES (?, date('now', 'localtime'), ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                calories,
                protein,
                fat,
                carbs,
                json.dumps(meals_list, ensure_ascii=False),
                goal,
            ),
        )
        conn.commit()


def get_weekly_summary(user_id):
    """מחזיר נתוני סיכום שבועיים למשתמש."""
    with sqlite3.connect("nutrition_data.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT date, calories, protein, fat, carbs, meals, goal
            FROM nutrition_logs
            WHERE user_id = ?
            ORDER BY date DESC
            LIMIT 7
            """,
            (user_id,),
        )
        return cursor.fetchall()


def save_user(user_id, user_data):
    """שומר נתוני משתמש לקובץ JSON."""
    try:
        if not os.path.exists(USERS_FILE):
            data = {}
        else:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        data[str(user_id)] = user_data
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        # TODO: טיפול בשגיאות כתיבה
        print(f"שגיאה בשמירת משתמש: {e}")


def load_user(user_id):
    """טוען נתוני משתמש מקובץ JSON."""
    try:
        if not os.path.exists(USERS_FILE):
            return None
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get(str(user_id))
    except Exception as e:
        # TODO: טיפול בשגיאות קריאה
        print(f"שגיאה בטעינת משתמש: {e}")
        return None


class NutritionDB:
    def __init__(self, db_path="nutrition.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """מאתחל את מסד הנתונים עם הטבלאות הנדרשות."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # טבלת משתמשים
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    name TEXT,
                    age INTEGER,
                    gender TEXT,
                    height REAL,
                    weight REAL,
                    goal TEXT,
                    activity TEXT,
                    diet TEXT,  -- JSON string
                    allergies TEXT,  -- JSON string
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # טבלת יומן אכילה
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS food_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    meal_date DATE,
                    meal_type TEXT,  -- breakfast, lunch, dinner, snack
                    description TEXT,
                    calories INTEGER,
                    protein REAL,
                    carbs REAL,
                    fat REAL,
                    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # טבלת תפריטים יומיים
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_menus (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    menu_date DATE,
                    menu_content TEXT,
                    calorie_budget INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # טבלת אלרגיות
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_allergies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    allergen TEXT,
                    severity TEXT DEFAULT 'moderate',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            conn.commit()
    
    def save_user(self, user_id: int, user_data: Dict[str, Any]) -> bool:
        """שומר או מעדכן משתמש במסד הנתונים."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # המרת רשימות ל-JSON
                diet_json = json.dumps(user_data.get('diet', []), ensure_ascii=False)
                allergies_json = json.dumps(user_data.get('allergies', []), ensure_ascii=False)
                
                cursor.execute('''
                    INSERT OR REPLACE INTO users 
                    (user_id, name, age, gender, height, weight, goal, activity, diet, allergies, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id,
                    user_data.get('name'),
                    user_data.get('age'),
                    user_data.get('gender'),
                    user_data.get('height'),
                    user_data.get('weight'),
                    user_data.get('goal'),
                    user_data.get('activity'),
                    diet_json,
                    allergies_json,
                    datetime.now()
                ))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"שגיאה בשמירת משתמש: {e}")
            return False
    
    def load_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """טוען משתמש ממסד הנתונים."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
                row = cursor.fetchone()
                
                if row:
                    user_data = {
                        'user_id': row[0],
                        'name': row[1],
                        'age': row[2],
                        'gender': row[3],
                        'height': row[4],
                        'weight': row[5],
                        'goal': row[6],
                        'activity': row[7],
                        'diet': json.loads(row[8]) if row[8] else [],
                        'allergies': json.loads(row[9]) if row[9] else [],
                        'created_at': row[10],
                        'updated_at': row[11]
                    }
                    return user_data
                return None
        except Exception as e:
            print(f"שגיאה בטעינת משתמש: {e}")
            return None
    
    def save_food_log(self, user_id: int, meal_data: Dict[str, Any]) -> bool:
        """שומר רשומת אכילה במסד הנתונים."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO food_log 
                    (user_id, meal_date, meal_type, description, calories, protein, carbs, fat)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id,
                    meal_data.get('date', date.today().isoformat()),
                    meal_data.get('meal_type', 'snack'),
                    meal_data.get('description', ''),
                    meal_data.get('calories', 0),
                    meal_data.get('protein', 0.0),
                    meal_data.get('carbs', 0.0),
                    meal_data.get('fat', 0.0)
                ))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"שגיאה בשמירת רשומת אכילה: {e}")
            return False
    
    def get_food_log(self, user_id: int, meal_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """מחזיר יומן אכילה למשתמש לתאריך מסוים."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if meal_date:
                    cursor.execute('''
                        SELECT * FROM food_log 
                        WHERE user_id = ? AND meal_date = ?
                        ORDER BY logged_at DESC
                    ''', (user_id, meal_date))
                else:
                    cursor.execute('''
                        SELECT * FROM food_log 
                        WHERE user_id = ?
                        ORDER BY meal_date DESC, logged_at DESC
                    ''', (user_id,))
                
                rows = cursor.fetchall()
                return [
                    {
                        'id': row[0],
                        'user_id': row[1],
                        'meal_date': row[2],
                        'meal_type': row[3],
                        'description': row[4],
                        'calories': row[5],
                        'protein': row[6],
                        'carbs': row[7],
                        'fat': row[8],
                        'logged_at': row[9]
                    }
                    for row in rows
                ]
        except Exception as e:
            print(f"שגיאה בטעינת יומן אכילה: {e}")
            return []
    
    def save_daily_menu(self, user_id: int, menu_data: Dict[str, Any]) -> bool:
        """שומר תפריט יומי במסד הנתונים."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO daily_menus 
                    (user_id, menu_date, menu_content, calorie_budget)
                    VALUES (?, ?, ?, ?)
                ''', (
                    user_id,
                    menu_data.get('date', date.today().isoformat()),
                    menu_data.get('content', ''),
                    menu_data.get('calorie_budget', 0)
                ))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"שגיאה בשמירת תפריט יומי: {e}")
            return False
    
    def get_daily_menu(self, user_id: int, menu_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """מחזיר תפריט יומי למשתמש לתאריך מסוים."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query_date = menu_date or date.today().isoformat()
                cursor.execute('''
                    SELECT * FROM daily_menus 
                    WHERE user_id = ? AND menu_date = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                ''', (user_id, query_date))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'id': row[0],
                        'user_id': row[1],
                        'menu_date': row[2],
                        'menu_content': row[3],
                        'calorie_budget': row[4],
                        'created_at': row[5]
                    }
                return None
        except Exception as e:
            print(f"שגיאה בטעינת תפריט יומי: {e}")
            return None
    
    def save_user_allergies(self, user_id: int, allergies: List[str]) -> bool:
        """שומר אלרגיות משתמש במסד הנתונים."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # מחיקת אלרגיות קיימות
                cursor.execute('DELETE FROM user_allergies WHERE user_id = ?', (user_id,))
                
                # הוספת אלרגיות חדשות
                for allergen in allergies:
                    cursor.execute('''
                        INSERT INTO user_allergies (user_id, allergen)
                        VALUES (?, ?)
                    ''', (user_id, allergen))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"שגיאה בשמירת אלרגיות: {e}")
            return False
    
    def get_user_allergies(self, user_id: int) -> List[str]:
        """מחזיר אלרגיות משתמש."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT allergen FROM user_allergies WHERE user_id = ?', (user_id,))
                rows = cursor.fetchall()
                return [row[0] for row in rows]
        except Exception as e:
            print(f"שגיאה בטעינת אלרגיות: {e}")
            return []
    
    def get_daily_summary(self, user_id: int, summary_date: Optional[str] = None) -> Dict[str, Any]:
        """מחזיר סיכום יומי של אכילה."""
        try:
            query_date = summary_date or date.today().isoformat()
            food_log = self.get_food_log(user_id, query_date)
            
            total_calories = sum(item.get('calories', 0) for item in food_log)
            total_protein = sum(item.get('protein', 0) for item in food_log)
            total_carbs = sum(item.get('carbs', 0) for item in food_log)
            total_fat = sum(item.get('fat', 0) for item in food_log)
            
            return {
                'date': query_date,
                'total_calories': total_calories,
                'total_protein': total_protein,
                'total_carbs': total_carbs,
                'total_fat': total_fat,
                'meals_count': len(food_log),
                'meals': food_log
            }
        except Exception as e:
            print(f"שגיאה בחישוב סיכום יומי: {e}")
            return {
                'date': query_date,
                'total_calories': 0,
                'total_protein': 0,
                'total_carbs': 0,
                'total_fat': 0,
                'meals_count': 0,
                'meals': []
            }

# יצירת מופע גלובלי
nutrition_db = NutritionDB()

def save_user_data(user_id: int, user_data: Dict[str, Any]) -> bool:
    """פונקציה גלובלית לשמירת נתוני משתמש."""
    return nutrition_db.save_user(user_id, user_data)

def load_user_data(user_id: int) -> Optional[Dict[str, Any]]:
    """פונקציה גלובלית לטעינת נתוני משתמש."""
    return nutrition_db.load_user(user_id)

def save_food_entry(user_id: int, meal_data: Dict[str, Any]) -> bool:
    """פונקציה גלובלית לשמירת רשומת אכילה."""
    return nutrition_db.save_food_log(user_id, meal_data)

def get_daily_food_log(user_id: int, meal_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """פונקציה גלובלית לקבלת יומן אכילה יומי."""
    return nutrition_db.get_food_log(user_id, meal_date)

def save_daily_menu_data(user_id: int, menu_data: Dict[str, Any]) -> bool:
    """פונקציה גלובלית לשמירת תפריט יומי."""
    return nutrition_db.save_daily_menu(user_id, menu_data)

def get_daily_menu_data(user_id: int, menu_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """פונקציה גלובלית לקבלת תפריט יומי."""
    return nutrition_db.get_daily_menu(user_id, menu_date)

def save_user_allergies_data(user_id: int, allergies: List[str]) -> bool:
    """פונקציה גלובלית לשמירת אלרגיות משתמש."""
    return nutrition_db.save_user_allergies(user_id, allergies)

def get_user_allergies_data(user_id: int) -> List[str]:
    """פונקציה גלובלית לקבלת אלרגיות משתמש."""
    return nutrition_db.get_user_allergies(user_id)

def get_daily_summary_data(user_id: int, summary_date: Optional[str] = None) -> Dict[str, Any]:
    """פונקציה גלובלית לקבלת סיכום יומי."""
    return nutrition_db.get_daily_summary(user_id, summary_date)
