import os
import logging
import asyncio
import json
import re
import time
from functools import wraps
import random
from datetime import datetime, timedelta
import aiohttp
import hashlib
import io
from typing import List, Dict, Any, Optional
import base64
import subprocess
import sys
import tempfile
import shutil
import sqlite3

# Telegram Bot imports
try:
    from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
    print("✅ تم استيراد مكتبة telegram بنجاح")
except ImportError as e:
    print(f"❌ خطأ في استيراد مكتبة telegram: {e}")
    print("🔧 يتم تثبيت المكتبة الصحيحة...")
    import subprocess
    import sys

    try:
        # إزالة جميع الإصدارات المتضاربة
        subprocess.check_call([sys.executable, '-m', 'pip', 'uninstall', '-y', 'telegram', 'python-telegram-bot'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        pass

    # تثبيت الإصدار الصحيح
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'python-telegram-bot==20.7'])

    # محاولة الاستيراد مرة أخرى
    try:
        from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
        from telegram.ext import Application, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
        print("✅ تم استيراد مكتبة telegram بعد إعادة التثبيت")
    except ImportError as e2:
        print(f"❌ فشل نهائي في الاستيراد: {e2}")
        print("⚠️ تم إنشاء حلول مؤقتة - قد تحتاج لإعادة تشغيل البوت")

        # إنشاء classes بديلة مؤقتة
        class MockUpdate:
            def __init__(self):
                self.effective_user = None
                self.message = None
                self.callback_query = None

        class MockContext:
            def __init__(self):
                self.args = []
                self.bot = None

        Update = MockUpdate
        ContextTypes = type('ContextTypes', (), {'DEFAULT_TYPE': MockContext})


# AI Integrations
from openai import OpenAI
import google.generativeai as genai

# PIL for image processing
from PIL import Image, ImageFilter, ImageEnhance

# ReportLab for PDF generation
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_RIGHT, TA_LEFT, TA_CENTER
from reportlab.pdfbase.ttfonts import TTFont

# نظام صانع البوتات المتقدم
import tempfile
import threading
from typing import Dict, Any
import json

# استيراد مدير الاستضافة مع معالجة الأخطاء
try:
    from bot_hosting_manager import hosting_manager
    print("✅ تم استيراد مدير الاستضافة بنجاح")
except ImportError as e:
    print(f"❌ خطأ في استيراد مدير الاستضافة: {e}")
    print("🔄 محاولة إعادة تثبيت المتطلبات...")
    import subprocess
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'python-telegram-bot[ext]==20.7'])
    try:
        from bot_hosting_manager import hosting_manager
        print("✅ تم استيراد مدير الاستضافة بعد إعادة التثبيت")
    except ImportError as e2:
        print(f"❌ فشل نهائي في الاستيراد: {e2}")
        # إنشاء مدير استضافة مؤقت
        class TempHostingManager:
            def start_user_bot(self, owner_id, username, bot_token):
                print(f"⚠️ مدير الاستضافة غير متوفر - البوت {username} لن يعمل")
                return False
            def stop_user_bot(self, owner_id, username):
                return True
            def get_bot_status(self, owner_id, username):
                return "stopped"
        hosting_manager = TempHostingManager()

# ===================== الإعدادات العامة =====================
TELEGRAM_TOKEN = "7600795766:AAHKhHjZH-WDdynUp5eJq_Pbx14upfinj6I"
COPYRIGHT_LINE = "© linux0root - AI Developer Platform"

# معرف المدير الرئيسي (ضع معرفك هنا)
MASTER_ADMIN_ID = 1268981585  # استبدل بمعرفك الشخصي

# قاعدة البيانات المركزية
MAIN_DB_PATH = "main_users.db"

# بيانات البوتات المستضافة
HOSTED_BOTS = {}  # {user_id: bot_instance}
BOT_FACTORY_DATA = {}  # بيانات مؤقتة لإنشاء البوتات
USER_STATES = {}  # حالات المستخدمين

# كلمات الإلغاء
CANCEL_WORDS = {"إلغاء", "الغاء", "معليه", "cancel", "الغاء العملية"}

# نظام الجلسات المؤقت (مدة ساعة)
TEMP_SESSIONS = {}  # {user_id: {'username': str, 'owner_id': int, 'expires': datetime}}
SESSION_DURATION = timedelta(hours=1)  # مدة الجلسة ساعة واحدة

# ===================== إعداد قاعدة البيانات المركزية =====================
def init_main_database():
    """تهيئة قاعدة البيانات المركزية مع إصلاح الأعمدة المفقودة"""
    conn = sqlite3.connect(MAIN_DB_PATH)
    cursor = conn.cursor()

    # جدول المستخدمين الرئيسي - السماح بعدة حسابات لنفس tg_id
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS main_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            bot_token TEXT,
            is_banned INTEGER DEFAULT 0,
            temp_ban_until TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            bot_type TEXT DEFAULT 'عام',
            bot_created INTEGER DEFAULT 0,
            bots_count INTEGER DEFAULT 0,
            max_bots INTEGER DEFAULT 3
        )
    ''')

    # التحقق من وجود الأعمدة وإضافتها إذا كانت مفقودة
    try:
        # فحص هيكل الجدول الحالي
        cursor.execute("PRAGMA table_info(main_users)")
        existing_columns = [column[1] for column in cursor.fetchall()]

        # الأعمدة المطلوبة
        required_columns = {
            'bot_token': 'TEXT',
            'password_salt': 'TEXT',
            'is_banned': 'INTEGER DEFAULT 0',
            'temp_ban_until': 'TIMESTAMP',
            'last_login': 'TIMESTAMP',
            'bot_type': 'TEXT DEFAULT "عام"',
            'bot_created': 'INTEGER DEFAULT 0',
            'bots_count': 'INTEGER DEFAULT 0',
            'max_bots': 'INTEGER DEFAULT 3'
        }

        # إضافة الأعمدة المفقودة
        for column_name, column_type in required_columns.items():
            if column_name not in existing_columns:
                try:
                    cursor.execute(f'ALTER TABLE main_users ADD COLUMN {column_name} {column_type}')
                    print(f"✅ تم إضافة العمود المفقود: {column_name}")
                except Exception as e:
                    print(f"⚠️ خطأ في إضافة العمود {column_name}: {e}")

    except Exception as e:
        print(f"⚠️ خطأ في فحص هيكل الجدول: {e}")

    # جدول إعدادات البوتات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            buttons_count INTEGER DEFAULT 0,
            group_command TEXT,
            linked_group_id INTEGER,
            admin_username TEXT,
            admin_password TEXT,
            bot_token TEXT,
            bot_status TEXT DEFAULT 'stopped',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # جدول سجل الأنشطة
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER,
            action TEXT,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ تم تهيئة قاعدة البيانات المركزية مع إصلاح الأعمدة")

# ===================== إدارة الجلسات المؤقتة =====================
def create_temp_session(user_id: int, username: str, owner_id: int):
    """إنشاء جلسة مؤقتة للمستخدم"""
    TEMP_SESSIONS[user_id] = {
        'username': username,
        'owner_id': owner_id,
        'expires': datetime.now() + SESSION_DURATION
    }
    print(f"✅ تم إنشاء جلسة مؤقتة للمستخدم {username} - تنتهي في {SESSION_DURATION}")

def get_temp_session(user_id: int) -> Optional[dict]:
    """الحصول على الجلسة المؤقتة إذا كانت صالحة"""
    if user_id in TEMP_SESSIONS:
        session = TEMP_SESSIONS[user_id]
        if datetime.now() < session['expires']:
            return session
        else:
            # الجلسة منتهية الصلاحية
            del TEMP_SESSIONS[user_id]
            print(f"⏰ انتهت صلاحية الجلسة للمستخدم {user_id}")
    return None

def extend_temp_session(user_id: int):
    """تمديد الجلسة المؤقتة"""
    if user_id in TEMP_SESSIONS:
        TEMP_SESSIONS[user_id]['expires'] = datetime.now() + SESSION_DURATION
        print(f"🔄 تم تمديد الجلسة للمستخدم {user_id}")

def clear_temp_session(user_id: int):
    """مسح الجلسة المؤقتة"""
    if user_id in TEMP_SESSIONS:
        del TEMP_SESSIONS[user_id]
        print(f"🚪 تم مسح الجلسة للمستخدم {user_id}")

# ===================== أدوات قاعدة البيانات =====================
def hash_password(password: str, salt: str = None) -> tuple:
    """تشفير كلمة المرور مع salt عشوائي"""
    import secrets
    if salt is None:
        salt = secrets.token_hex(16)  # إنشاء salt عشوائي 32 حرف

    # تشفير كلمة المرور مع salt
    password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return password_hash, salt

def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """التحقق من كلمة المرور"""
    password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return password_hash == stored_hash

def create_main_user(tg_id: int, username: str, password: str) -> dict:
    """إنشاء مستخدم جديد مع تفاصيل أفضل للأخطاء - للاستخدام القديم"""
    return create_main_user_with_token(tg_id, username, password, None)

def create_main_user_with_token(tg_id: int, username: str, password: str, bot_token: str = None) -> dict:
    """إنشاء مستخدم جديد مع توكين البوت"""
    conn = None
    try:
        # التأكد من وجود ملف قاعدة البيانات
        if not os.path.exists(MAIN_DB_PATH):
            print(f"⚠️ ملف قاعدة البيانات غير موجود، سيتم إنشاؤه: {MAIN_DB_PATH}")
            init_main_database()

        conn = sqlite3.connect(MAIN_DB_PATH, timeout=10.0)
        cursor = conn.cursor()

        # فحص اتصال قاعدة البيانات
        cursor.execute('SELECT 1')
        print(f"✅ اتصال ناجح بقاعدة البيانات: {MAIN_DB_PATH}")

        # التحقق من تفرد اسم المستخدم
        cursor.execute('SELECT tg_id, username FROM main_users WHERE username = ?', (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            print(f"❌ اسم المستخدم موجود مسبقاً: {username}")
            return {
                "success": False,
                "error_type": "username_taken",
                "message": f"اسم المستخدم '{username}' مُستخدم مسبقاً",
                "suggestion": f"جرب: {username}_{tg_id % 1000}"
            }

        # تشفير كلمة المرور مع salt
        password_hash, salt = hash_password(password)
        print(f"🔐 تم تشفير كلمة المرور للمستخدم: {username}")

        # إدخال المستخدم الجديد
        cursor.execute('''
            INSERT INTO main_users (tg_id, username, password_hash, password_salt, bot_token, bot_created)
            VALUES (?, ?, ?, ?, ?, 0)
        ''', (tg_id, username, password_hash, salt, bot_token))

        print(f"✅ تم إدخال المستخدم في جدول main_users: {username}")

        # إنشاء إعدادات افتراضية في جدول منفصل
        try:
            cursor.execute('''
                INSERT INTO bot_settings (tg_id, username, admin_username, admin_password, bot_token, bot_status)
                VALUES (?, ?, ?, ?, ?, 'stopped')
            ''', (tg_id, username, username, password, bot_token))
            print(f"✅ تم إنشاء إعدادات البوت للمستخدم: {username}")
        except Exception as settings_error:
            print(f"⚠️ خطأ في إنشاء الإعدادات (غير حرج): {settings_error}")

        # حفظ التغييرات
        conn.commit()
        print(f"💾 تم حفظ جميع البيانات للمستخدم: {username}")

        return {
            "success": True,
            "message": "تم إنشاء الحساب بنجاح",
            "username": username,
            "tg_id": tg_id
        }

    except sqlite3.IntegrityError as e:
        error_msg = str(e)
        print(f"❌ خطأ في قيود قاعدة البيانات: {error_msg}")

        if "UNIQUE constraint failed" in error_msg:
            return {
                "success": False,
                "error_type": "username_taken",
                "message": f"اسم المستخدم '{username}' مُستخدم مسبقاً",
                "suggestion": f"جرب: {username}_{tg_id % 1000}"
            }
        else:
            return {
                "success": False,
                "error_type": "database_constraint",
                "message": "خطأ في قيود قاعدة البيانات"
            }

    except sqlite3.OperationalError as e:
        error_msg = str(e)
        print(f"❌ خطأ في تشغيل قاعدة البيانات: {error_msg}")

        if "database is locked" in error_msg:
            return {
                "success": False,
                "error_type": "database_locked",
                "message": "قاعدة البيانات مقفلة، حاول مرة أخرى"
            }
        else:
            return {
                "success": False,
                "error_type": "database_operational",
                "message": f"خطأ في تشغيل قاعدة البيانات: {error_msg}"
            }

    except Exception as e:
        error_msg = str(e)
        print(f"❌ خطأ عام في إنشاء المستخدم: {error_msg}")
        import traceback
        print(f"📋 تفاصيل الخطأ الكاملة: {traceback.format_exc()}")

        return {
            "success": False,
            "error_type": "general_error",
            "message": f"خطأ في النظام: {error_msg}"
        }
    finally:
        if conn:
            try:
                conn.close()
                print(f"🔌 تم إغلاق اتصال قاعدة البيانات")
            except Exception as close_error:
                print(f"⚠️ خطأ في إغلاق قاعدة البيانات: {close_error}")

def verify_user_login(username: str, password: str) -> Optional[int]:
    """التحقق من تسجيل الدخول مع التشفير المحسن"""
    try:
        conn = sqlite3.connect(MAIN_DB_PATH)
        cursor = conn.cursor()

        # جلب كلمة المرور المشفرة و salt
        cursor.execute('''
            SELECT tg_id, password_hash, password_salt, is_banned, temp_ban_until FROM main_users
            WHERE username = ?
        ''', (username,))

        result = cursor.fetchone()

        if not result:
            conn.close()
            return None

        tg_id, stored_hash, salt, is_banned, temp_ban_until = result

        # التحقق من كلمة المرور
        if not verify_password(password, stored_hash, salt or ""):
            conn.close()
            return None

        # فحص الحظر
        if is_banned:
            return -1  # محظور دائماً

        if temp_ban_until:
            ban_time = datetime.fromisoformat(temp_ban_until)
            if datetime.now() < ban_time:
                return -2  # محظور مؤقتاً

        # تحديث آخر تسجيل دخول
        conn = sqlite3.connect(MAIN_DB_PATH)
        cursor = conn.cursor()
        cursor.execute('UPDATE main_users SET last_login = CURRENT_TIMESTAMP WHERE username = ?', (username,))
        conn.commit()
        conn.close()

        return tg_id
    except Exception as e:
        print(f"خطأ في التحقق من تسجيل الدخول: {e}")
        return None

def get_user_by_username(username: str) -> Optional[dict]:
    """الحصول على بيانات المستخدم بالاسم"""
    try:
        conn = sqlite3.connect(MAIN_DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT tg_id, username, is_banned, temp_ban_until, bot_created, bots_count, max_bots FROM main_users
            WHERE username = ?
        ''', (username,))
        result = cursor.fetchone()
        conn.close()

        if result:
            return {
                'tg_id': result[0],
                'username': result[1],
                'is_banned': result[2],
                'temp_ban_until': result[3],
                'bot_created': result[4],
                'bots_count': result[5],
                'max_bots': result[6]
            }
        return None
    except Exception as e:
        print(f"خطأ في جلب بيانات المستخدم: {e}")
        return None

def get_user_by_tg_id(tg_id: int) -> Optional[dict]:
    """الحصول على بيانات المستخدم بمعرف تليجرام"""
    try:
        conn = sqlite3.connect(MAIN_DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT tg_id, username, is_banned, temp_ban_until, bot_created, bots_count, max_bots FROM main_users
            WHERE tg_id = ?
        ''', (tg_id,))
        result = cursor.fetchone()
        conn.close()

        if result:
            return {
                'tg_id': result[0],
                'username': result[1],
                'is_banned': result[2],
                'temp_ban_until': result[3],
                'bot_created': result[4],
                'bots_count': result[5],
                'max_bots': result[6]
            }
        return None
    except Exception as e:
        print(f"خطأ في جلب بيانات المستخدم: {e}")
        return None

def ban_user(username: str, hours: int = 0) -> bool:
    """حظر مستخدم"""
    try:
        conn = sqlite3.connect(MAIN_DB_PATH)
        cursor = conn.cursor()

        if hours > 0:
            # حظر مؤقت
            ban_until = (datetime.now() + timedelta(hours=hours)).isoformat()
            cursor.execute('''
                UPDATE main_users SET temp_ban_until = ? WHERE username = ?
            ''', (ban_until, username))
        else:
            # حظر دائم
            cursor.execute('''
                UPDATE main_users SET is_banned = 1 WHERE username = ?
            ''', (username,))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"خطأ في حظر المستخدم: {e}")
        return False

def unban_user(username: str) -> bool:
    """إلغاء حظر مستخدم"""
    try:
        conn = sqlite3.connect(MAIN_DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE main_users SET is_banned = 0, temp_ban_until = NULL WHERE username = ?
        ''', (username,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"خطأ في إلغاء حظر المستخدم: {e}")
        return False

def delete_user_completely(username: str) -> bool:
    """حذف مستخدم نهائياً"""
    try:
        user = get_user_by_username(username)
        if not user:
            return False

        tg_id = user['tg_id']

        # حذف قاعدة بيانات البوت الخاص به
        bot_db_path = f"user_data/{tg_id}_{username}" # Adjusted path
        if os.path.exists(bot_db_path):
            shutil.rmtree(bot_db_path)

        # حذف من قاعدة البيانات المركزية
        conn = sqlite3.connect(MAIN_DB_PATH)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM bot_settings WHERE tg_id = ?', (tg_id,))
        cursor.execute('DELETE FROM activity_log WHERE tg_id = ?', (tg_id,))
        cursor.execute('DELETE FROM main_users WHERE tg_id = ?', (tg_id,))
        conn.commit()
        conn.close()

        # إيقاف البوت إذا كان يعمل
        bot_key = f"{tg_id}_{username}"
        if bot_key in HOSTED_BOTS:
            # This requires an async context, so we'll assume it's handled elsewhere or needs adaptation.
            # For now, we'll just remove it from the dict.
            # await HOSTED_BOTS[tg_id].stop_bot() # Cannot await here directly
            del HOSTED_BOTS[bot_key]

        return True
    except Exception as e:
        print(f"خطأ في حذف المستخدم: {e}")
        return False

# ===================== فئة البوت المستضاف المحدثة =====================
class HostedBot:
    """فئة البوت المستضاف مع قاعدة البيانات المحدثة"""

    def __init__(self, owner_id: int, username: str, password: str, bot_token: str = None):
        self.owner_id = owner_id
        self.username = username
        self.password = password
        self.bot_token = bot_token

        # إنشاء مسار منفصل لكل مستخدم
        import os
        self.user_directory = f"user_data/{owner_id}_{username}"
        os.makedirs(self.user_directory, exist_ok=True)

        # إنشاء قاعدة البيانات الخاصة بالمستخدم في مجلده المنفصل
        self.db_path = os.path.join(self.user_directory, f"linux0root_{owner_id}_{username}.db")
        self.files_directory = os.path.join(self.user_directory, "files")
        os.makedirs(self.files_directory, exist_ok=True)

        self.init_user_database()

        # متغيرات حالة البوت مع معرف فريد
        self.bot_instance_id = f"{owner_id}_{username}_{int(time.time())}"
        self.application = None
        self.pending_operations = {}
        self.bot_status = "stopped" # Default status

    def init_user_database(self):
        """تهيئة قاعدة بيانات المستخدم الفرعية مع إصلاح الأعمدة المفقودة"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # جدول الأزرار
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS buttons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    file_id TEXT,
                    file_type TEXT,
                    file_path TEXT,
                    clicks INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # إضافة عمود file_path إذا لم يكن موجوداً
            try:
                cursor.execute('ALTER TABLE buttons ADD COLUMN file_path TEXT')
            except sqlite3.OperationalError:
                pass  # العمود موجود بالفعل

            # جدول الإحصائيات
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action TEXT,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # جدول إعدادات البوت الفرعي
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bot_config (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # إضافة حالة البوت الافتراضية
            cursor.execute('''
                INSERT OR IGNORE INTO bot_config (key, value) VALUES ('bot_status', 'stopped')
            ''')

            # جدول الجلسات المستقلة
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE,
                    user_tg_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE
                )
            ''')

            conn.commit()
            conn.close()
            print(f"✅ تم إنشاء قاعدة البيانات: {self.db_path}")

        except Exception as e:
            print(f"❌ خطأ في إنشاء قاعدة البيانات: {e}")

    def add_button(self, name: str, file_id: str = None, file_type: str = None, button_type: str = "text", content: str = None, url: str = None):
        """إضافة زر جديد مع دعم أنواع مختلفة"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # تحديث هيكل الجدول إذا لزم الأمر
            try:
                cursor.execute('ALTER TABLE buttons ADD COLUMN button_type TEXT DEFAULT "text"')
                cursor.execute('ALTER TABLE buttons ADD COLUMN content TEXT')
                cursor.execute('ALTER TABLE buttons ADD COLUMN url TEXT')
            except sqlite3.OperationalError:
                pass  # الأعمدة موجودة بالفعل

            # حفظ مسار الملف في مجلد المستخدم
            file_path = None
            if file_id:
                file_path = os.path.join(self.files_directory, f"{name}_{file_id}_{file_type}")

            cursor.execute('''
                INSERT OR REPLACE INTO buttons (name, file_id, file_type, file_path, button_type, content, url, clicks)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            ''', (name, file_id, file_type, file_path, button_type, content, url))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"خطأ في إضافة الزر: {e}")
            return False

    def delete_button(self, name: str):
        """حذف زر"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM buttons WHERE name = ?', (name,))
            success = cursor.rowcount > 0
            conn.commit()
            conn.close()
            return success
        except Exception as e:
            print(f"خطأ في حذف الزر: {e}")
            return False

    def get_buttons(self):
        """الحصول على قائمة الأزرار مع معلومات مفصلة"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # التحقق من وجود الأعمدة الجديدة
            cursor.execute("PRAGMA table_info(buttons)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'button_type' in columns:
                cursor.execute('''
                    SELECT name, file_id, file_type, clicks, button_type, content, url, created_at
                    FROM buttons ORDER BY id
                ''')
            else:
                cursor.execute('SELECT name, file_id, file_type, clicks FROM buttons ORDER BY id')

            buttons = cursor.fetchall()
            conn.close()
            return buttons
        except Exception as e:
            print(f"خطأ في جلب الأزرار: {e}")
            return []

    def increment_button_click(self, name: str):
        """زيادة عداد النقرات للزر"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('UPDATE buttons SET clicks = clicks + 1 WHERE name = ?', (name,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"خطأ في تحديث عداد النقرات: {e}")

    def get_stats(self):
        """الحصول على الإحصائيات"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # عدد الأزرار
            cursor.execute('SELECT COUNT(*) FROM buttons')
            total_buttons = cursor.fetchone()[0]

            # مجموع النقرات
            cursor.execute('SELECT SUM(clicks) FROM buttons')
            total_clicks = cursor.fetchone()[0] or 0

            conn.close()

            return {
                'total_buttons': total_buttons,
                'total_clicks': total_clicks
            }
        except Exception as e:
            print(f"خطأ في جلب الإحصائيات: {e}")
            return {}

    def rename_button(self, old_name: str, new_name: str):
        """تغيير اسم زر"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('UPDATE buttons SET name = ? WHERE name = ?', (new_name, old_name))
            success = cursor.rowcount > 0
            conn.commit()
            conn.close()
            return success
        except Exception as e:
            print(f"خطأ في تغيير اسم الزر: {e}")
            return False

    def set_bot_status(self, status):
        """تحديث حالة البوت في قاعدة البيانات الفرعية"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO bot_config (key, value, updated_at)
                VALUES ('bot_status', ?, CURRENT_TIMESTAMP)
            ''', (status,))
            conn.commit()
            conn.close()
            self.bot_status = status
            return True
        except Exception as e:
            print(f"خطأ في تحديث حالة البوت: {e}")
            return False

    def start_user_bot(self):
        """تشغيل البوت الخاص بالمستخدم مع التحقق من التوكين"""
        try:
            # الحصول على أحدث توكين من قاعدة البيانات
            conn = sqlite3.connect(MAIN_DB_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT bot_token FROM main_users WHERE tg_id = ? AND username = ?', (self.owner_id, self.username))
            result = cursor.fetchone()
            conn.close()

            if result and result[0]:
                self.bot_token = result[0].strip()
                print(f"🔄 تم تحديث التوكين من قاعدة البيانات: {self.bot_token[:20]}...")

            # التحقق من وجود التوكين وصحته
            if not self.bot_token:
                print(f"❌ لا يوجد توكين للبوت: {self.username}")
                self.set_bot_status("no_token")
                return False

            if len(self.bot_token) < 30 or ':' not in self.bot_token:
                print(f"❌ توكين غير صالح للبوت: {self.username}")
                self.set_bot_status("invalid_token")
                return False

            # تحقق إضافي من تنسيق التوكين
            if not self.validate_token_format(self.bot_token):
                print(f"❌ تنسيق التوكين غير صحيح للبوت: {self.username}")
                self.set_bot_status("invalid_format")
                return False

            print(f"🔄 محاولة تشغيل البوت: {self.username}")
            print(f"🔑 التوكين: {self.bot_token[:20]}...")

            # استخدام مدير الاستضافة لتشغيل البوت فعلياً مع التوكين
            success = hosting_manager.start_user_bot(self.owner_id, self.username, self.bot_token)

            if success:
                self.set_bot_status("running")
                print(f"✅ تم تشغيل البوت بنجاح: {self.username}")
                return True
            else:
                self.set_bot_status("failed")
                print(f"❌ فشل في تشغيل البوت: {self.username}")
                return False

        except Exception as e:
            print(f"❌ خطأ في تشغيل البوت: {e}")
            import traceback
            print(f"📋 تفاصيل الخطأ: {traceback.format_exc()}")
            self.set_bot_status("error")
            return False

    def validate_token_format(self, token: str) -> bool:
        """التحقق من صحة تنسيق التوكين"""
        try:
            if ':' not in token:
                return False
            parts = token.split(':')
            if len(parts) != 2:
                return False
            bot_id, bot_hash = parts
            return bot_id.isdigit() and len(bot_hash) >= 35
        except:
            return False

    async def stop_user_bot(self):
        """إيقاف البوت الخاص بالمستخدم"""
        try:
            # استخدام مدير الاستضافة لإيقاف البوت فعلياً
            success = await hosting_manager.stop_user_bot(self.owner_id, self.username)

            if success:
                self.set_bot_status("stopped")
                print(f"⏹️ تم إيقاف البوت فعلياً: {self.username}")
                return True
            else:
                print(f"❌ فشل في إيقاف البوت: {self.username}")
                return False
        except Exception as e:
            print(f"خطأ في إيقاف البوت: {e}")
            return False

    def get_bot_status(self):
        """الحصول على حالة البوت من مدير الاستضافة"""
        try:
            # الحصول على الحالة الفعلية من مدير الاستضافة
            real_status = hosting_manager.get_bot_status(self.owner_id, self.username)
            self.bot_status = real_status

            # تحديث قاعدة البيانات بالحالة الفعلية
            self.set_bot_status(real_status)

            return real_status
        except Exception as e:
            print(f"خطأ في جلب حالة البوت: {e}")
            return "stopped"

    def get_detailed_stats(self):
        """إحصائيات مفصلة"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # إحصائيات الأزرار
            cursor.execute('SELECT COUNT(*) FROM buttons')
            total_buttons = cursor.fetchone()[0]

            cursor.execute('SELECT SUM(clicks) FROM buttons')
            total_clicks = cursor.fetchone()[0] or 0

            # أكثر الأزرار استخداماً
            cursor.execute('SELECT name, clicks FROM buttons ORDER BY clicks DESC LIMIT 5')
            top_buttons = cursor.fetchall()

            # إحصائيات الأنشطة
            cursor.execute('SELECT COUNT(*) FROM stats')
            total_activities = cursor.fetchone()[0]

            conn.close()

            return {
                'total_buttons': total_buttons,
                'total_clicks': total_clicks,
                'top_buttons': top_buttons,
                'total_activities': total_activities,
                'bot_status': self.bot_status
            }
        except Exception as e:
            print(f"خطأ في جلب الإحصائيات المفصلة: {e}")
            return {}

    def update_bot_token(self, new_token: str):
        """تحديث التوكين الخاص بالبوت مع التحقق من صحته"""
        try:
            # التحقق من صحة التوكين
            if not new_token or ':' not in new_token or len(new_token) < 30:
                print(f"❌ توكين غير صالح: {new_token}")
                return False

            self.bot_token = new_token

            # تحديث التوكين في قاعدة البيانات المركزية
            conn = sqlite3.connect(MAIN_DB_PATH)
            cursor = conn.cursor()
            cursor.execute('UPDATE main_users SET bot_token = ? WHERE tg_id = ? AND username = ?', (new_token, self.owner_id, self.username))

            # التأكد من التحديث
            if cursor.rowcount > 0:
                conn.commit()
                print(f"✅ تم تحديث التوكين في قاعدة البيانات الرئيسية للمستخدم: {self.username}")
            else:
                print(f"⚠️ لم يتم العثور على المستخدم لتحديث التوكين: {self.username}")

            conn.close()

            # تحديث التوكين في قاعدة بيانات البوت الفرعية
            conn_user = sqlite3.connect(self.db_path)
            cursor_user = conn_user.cursor()
            cursor_user.execute('''
                INSERT OR REPLACE INTO bot_config (key, value, updated_at)
                VALUES ('bot_token', ?, CURRENT_TIMESTAMP)
            ''', (new_token,))
            conn_user.commit()
            conn_user.close()
            print(f"✅ تم تحديث التوكين في قاعدة بيانات البوت الفرعية للمستخدم: {self.username}")

            # تحديث التوكين في مدير الاستضافة إذا كان البوت يعمل
            bot_key = f"{self.owner_id}_{self.username}"
            if bot_key in hosting_manager.hosted_bots:
                hosting_manager.hosted_bots[bot_key].bot_token = new_token
                print(f"✅ تم تحديث التوكين في مدير الاستضافة")

            return True

        except Exception as e:
            print(f"❌ خطأ في تحديث التوكين: {e}")
            return False

    async def handle_linux0root_access(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالج الوصول لقاعدة linux0root"""
        user_id = update.effective_user.id
        text = update.message.text.strip()

        # التحقق من كلمة المرور
        if text == self.password:
            await update.message.reply_text(
                f"🔐 **مرحباً بك في قاعدة linux0root**\n\n"
                f"👤 **المستخدم:** {self.username}\n"
                f"🗃️ **قاعدة البيانات:** {self.db_path}\n\n"
                f"📊 **الإحصائيات:**\n"
                f"• الأزرار: {self.get_stats()['total_buttons']}\n"
                f"• النقرات: {self.get_stats()['total_clicks']}\n\n"
                f"⚙️ **الأوامر المتاحة:**\n"
                f"• إضافة زر: اكتب اسم الزر\n"
                f"• تغيير اسم [القديم] إلى [الجديد]\n"
                f"• إحصائيات: إحصائيات\n"
                f"• خروج: خروج"
            )
            USER_STATES[user_id] = {'state': 'linux0root_authenticated', 'owner_id': self.owner_id, 'username': self.username} # Fix: Set state directly to authenticated
        else:
            await update.message.reply_text("❌ كلمة مرور خاطئة")

# ===================== القائمة الرئيسية =====================
def main_menu():
    """إنشاء القائمة الرئيسية المُحدثة"""
    buttons = [
        [KeyboardButton("🤖 المجيب الذكي")],
        [KeyboardButton("💻 مطور الكود"), KeyboardButton("🔧 صانع البوتات")],
        [KeyboardButton("🌐 مطور المواقع"), KeyboardButton("📱 مفكك التطبيق")],
        [KeyboardButton("📊 الإحصائيات"), KeyboardButton("📄 تحويل PDF")],
        [KeyboardButton("🎨 معالجة الصور"), KeyboardButton("📨 إرسال SMS")],
        [KeyboardButton("ℹ️ معلومات البوت")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=False)

# ===================== معالجات الأوامر =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر البدء المُحدث"""
    user = update.effective_user

    welcome_text = f"""🤖 **مرحباً {user.first_name}!**

أهلاً بك في منصة الذكاء الاصطناعي للتطوير المحدثة!

🔧 **صانع البوتات المتقدم:**
• إنشاء بوتات مخصصة مع قواعد بيانات منفصلة
• نظام إدارة مركزي آمن
• وصول لقاعدة linux0root لإدارة بوتك

💡 **للبدء:**
• اضغط على "🔧 صانع البوتات" لإنشاء أو إدارة بوتك
• استخدم اسم المستخدم وكلمة المرور لإدارة قاعدة بياناتك

{COPYRIGHT_LINE}"""

    await update.message.reply_text(welcome_text, reply_markup=main_menu())

# معالجات أوامر المشرف
async def cmd_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حظر مستخدم - للمشرف فقط"""
    if update.effective_user.id != MASTER_ADMIN_ID:
        await update.message.reply_text("❌ هذا الأمر مخصص للمشرف الرئيسي فقط")
        return

    if not context.args:
        await update.message.reply_text("استخدم: /ban <username> [hours]")
        return

    username = context.args[0]
    hours = int(context.args[1]) if len(context.args) > 1 and context.args[1].isdigit() else 0

    if ban_user(username, hours):
        msg = f"✅ تم حظر المستخدم {username}"
        if hours > 0:
            msg += f" لمدة {hours} ساعة"
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("❌ فشل في حظر المستخدم")

async def cmd_unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء حظر مستخدم - للمشرف فقط"""
    if update.effective_user.id != MASTER_ADMIN_ID:
        await update.message.reply_text("❌ هذا الأمر مخصص للمشرف الرئيسي فقط")
        return

    if not context.args:
        await update.message.reply_text("استخدم: /unban <username>")
        return

    username = context.args[0]

    if unban_user(username):
        await update.message.reply_text(f"✅ تم إلغاء حظر المستخدم {username}")
    else:
        await update.message.reply_text("❌ فشل في إلغاء حظر المستخدم")

async def cmd_delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف مستخدم نهائياً - للمشرف فقط"""
    if update.effective_user.id != MASTER_ADMIN_ID:
        await update.message.reply_text("❌ هذا الأمر مخصص للمشرف الرئيسي فقط")
        return

    if not context.args:
        await update.message.reply_text("استخدم: /delete <username>")
        return

    username = context.args[0]

    if delete_user_completely(username):
        await update.message.reply_text(f"🗑️ تم حذف المستخدم {username} وقاعدة بياناته نهائياً")
    else:
        await update.message.reply_text("❌ فشل في حذف المستخدم")

# ===================== معالج صانع البوتات =====================

async def handle_bot_maker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج صانع البوتات المحدث"""
    keyboard = [
        [InlineKeyboardButton("🤖 إنشاء بوت جديد", callback_data="bot_create_new")],
        [InlineKeyboardButton("🔐 الوصول لقاعدة linux0root", callback_data="bot_access_linux0root")],
        [InlineKeyboardButton("📢 إدارة المجموعات", callback_data="bot_manage_groups")],
        [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    bot_info = """🔧 **صانع البوتات المتقدم مع قاعدة البيانات المركزية**

🎯 **الخيارات المتاحة:**

🤖 **إنشاء بوت جديد:**
• تسجيل حساب جديد أو تسجيل دخول
• نظام إدارة مركزي آمن
• وصول لقاعدة linux0root لإدارة بوتك

🔐 **الوصول لقاعدة linux0root:**
• إدارة بوتك باستخدام اسم المستخدم وكلمة المرور
• إضافة وحذف الأزرار
• ربط الملفات والمحتوى
• إحصائيات مفصلة

📢 **إدارة المجموعات:**
• ربط بوتك بالمجموعات
• أوامر نشر مخصصة
• استجابة ذكية في المجموعات

✨ **المميزات الجديدة:**
• تحكم مركزي في جميع المستخدمين
• نظام حظر ذكي (مؤقت/دائم)
• استضافة البوتات على نفس السيرفر
• قواعد بيانات منفصلة ومؤمنة

👆 **اختر الخيار المطلوب:**"""

    await update.message.reply_text(bot_info, reply_markup=reply_markup)

# ===================== معالجات التفاعل =====================
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الاستعلامات المحدث"""
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id

    # محاولة الإجابة على الاستعلام مع معالجة timeout
    try:
        await query.answer()
    except Exception as e:
        # تجاهل أخطاء timeout في callback queries
        if "Query is too old" in str(e) or "response timeout expired" in str(e):
            print(f"⚠️ تم تجاهل خطأ timeout في callback: {e}")
            pass
        else:
            print(f"❌ خطأ في callback answer: {e}")

    # استخراج owner_id و username إذا كانت موجودة في البيانات
    owner_id, username = None, None
    if "_" in data:
        parts = data.split("_")
        if len(parts) >= 3: # التأكد من وجود 3 أجزاء على الأقل (action, owner_id, username)
            try:
                # محاولة استخراج owner_id و username من أجزاء مختلفة
                if parts[0] == "linux" and parts[1] == "menu":
                    owner_id = int(parts[2])
                    username = parts[3] if len(parts) > 3 else None
                elif len(parts) >= 3:
                    owner_id = int(parts[-2])
                    username = parts[-1]
            except (ValueError, IndexError):
                pass # تجاهل إذا لم تكن البيانات صحيحة

    # --- معالجة الأزرار الرئيسية ---
    if data == "back_main":
        try:
            await query.edit_message_text("🏠 **القائمة الرئيسية**", reply_markup=main_menu())
        except:
            await query.message.reply_text("🏠 **القائمة الرئيسية**", reply_markup=main_menu())
        return

    if data == "bot_create_new":
        await handle_bot_creation_start(query, context)
        return

    if data == "bot_access_linux0root":
        await handle_linux0root_access_start(query, context)
        return

    if data == "bot_manage_groups":
        await handle_group_management(query, context)
        return

    if data == "register_new":
        await handle_callback_register_new(query, context)
        return

    if data == "login_existing":
        await handle_callback_login_existing(query, context)
        return

    if data == "start_register_new":
        await start_register_process(query, context)
        return

    if data == "start_login_existing":
        await start_login_process(query, context)
        return

    if data == "confirm_delete_account":
        await confirm_delete_account(query, context)
        return

    if data == "delete_account_confirmed":
        await delete_account_confirmed(query, context)
        return

    # --- معالجة أزرار linux0root ---
    if owner_id and username:
        # تحديث حالة المستخدم إذا كان في سياق linux0root
        if user_id not in USER_STATES or USER_STATES[user_id].get('state') != 'linux0root_authenticated':
            USER_STATES[user_id] = {
                'state': 'linux0root_authenticated',
                'owner_id': owner_id,
                'username': username
            }

        # قائمة الأزرار الرئيسية لـ linux0root
        if data == f"linux_menu_{owner_id}_{username}":
            # تمديد الجلسة المؤقتة
            extend_temp_session(user_id)

            bot_instance = HostedBot(owner_id, username, "", "")
            stats = bot_instance.get_stats()
            # الحصول على حالة البوت الفعلية من مدير الاستضافة
            actual_status = hosting_manager.get_bot_status(owner_id, username)

            # ترجمة حالة البوت
            if actual_status == "running":
                status_text = "🟢 يعمل"
            elif actual_status == "stopped":
                status_text = "🔴 متوقف"
            elif actual_status == "error":
                status_text = "🟡 خطأ"
            else:
                status_text = "🔴 غير معروف"

            keyboard = [
                [InlineKeyboardButton("➕ إضافة زر", callback_data=f"add_button_{owner_id}_{username}")],
                [InlineKeyboardButton("🎛️ إدارة الأزرار", callback_data=f"manage_buttons_{owner_id}_{username}")],
                [InlineKeyboardButton("📊 إحصائيات", callback_data=f"stats_{owner_id}_{username}")],
                [InlineKeyboardButton("✏️ تغيير اسم زر", callback_data=f"rename_button_{owner_id}_{username}")],
                [InlineKeyboardButton("🔧 تحديث التوكين", callback_data=f"update_token_{owner_id}_{username}")],
                [InlineKeyboardButton("🚀 تشغيل البوت", callback_data=f"start_bot_{owner_id}_{username}")],
                [InlineKeyboardButton("⏹️ إيقاف البوت", callback_data=f"stop_bot_{owner_id}_{username}")],
                [InlineKeyboardButton("🚪 تسجيل الخروج", callback_data=f"logout_linux_{owner_id}_{username}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            try:
                await query.edit_message_text(
                    f"🔐 **مرحباً بك في قاعدة linux0root**\n\n"
                    f"👤 **المستخدم:** {username}\n"
                    f"🗃️ **قاعدة البيانات:** linux0root_{owner_id}_{username}.db\n\n"
                    f"📊 **الإحصائيات:**\n"
                    f"• الأزرار: {stats['total_buttons']}\n"
                    f"• النقرات: {stats['total_clicks']}\n"
                    f"• حالة البوت: {status_text}\n\n"
                    f"⚙️ **الأوامر المتاحة:**\n"
                    f"• إضافة زر: اكتب اسم الزر\n"
                    f"• تغيير اسم [القديم] إلى [الجديد]\n"
                    f"• إحصائيات: إحصائيات\n"
                    f"• خروج: خروج",
                    reply_markup=reply_markup
                )
            except Exception as e:
                print(f"خطأ في تحديث رسالة linux_menu: {e}")
                await query.message.reply_text("تم تحديث قائمة linux0root", reply_markup=reply_markup)
            return

        # إضافة زر
        if data == f"add_button_{owner_id}_{username}":
            await handle_add_button_logic(query, context, owner_id, username)
            return

        # إحصائيات
        if data == f"stats_{owner_id}_{username}":
            bot_instance = HostedBot(owner_id, username, "", "")
            stats = bot_instance.get_stats()
            buttons = bot_instance.get_buttons()
            buttons_list = "\n".join([f"• {btn[0]} - {btn[3]} نقرة" for btn in buttons]) or "لا توجد أزرار"
            keyboard = [
                [InlineKeyboardButton("🔄 تحديث الإحصائيات", callback_data=f"stats_{owner_id}_{username}")],
                [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data=f"linux_menu_{owner_id}_{username}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"📊 **إحصائيات قاعدة البيانات:**\n\n"
                f"🔘 **عدد الأزرار:** {stats['total_buttons']}\n"
                f"👆 **مجموع النقرات:** {stats['total_clicks']}\n"
                f"🤖 **حالة البوت:** {bot_instance.get_bot_status()}\n\n"
                f"📋 **قائمة الأزرار:**\n{buttons_list}",
                reply_markup=reply_markup
            )
            return

        # قائمة الأزرار مع أزرار إدارة تفاعلية
        if data == f"manage_buttons_{owner_id}_{username}":
            await handle_buttons_management(query, context, owner_id, username)
            return

        # معالجة إدارة زر محدد (النظام الجديد)
        if data.startswith(f"button_manage_{owner_id}_{username}_"):
            button_index = data.replace(f"button_manage_{owner_id}_{username}_", "")
            try:
                index = int(button_index)
                bot_instance = HostedBot(owner_id, username, "", "")
                buttons = bot_instance.get_buttons()

                if 1 <= index <= len(buttons):
                    button_data = buttons[index - 1]
                    button_name = button_data[0] if button_data[0] else f"زر_{index}"
                    await handle_single_button_management(query, context, owner_id, username, button_name)
                else:
                    await query.answer("❌ الزر غير موجود")
            except (ValueError, IndexError) as e:
                print(f"خطأ في معالجة فهرس الزر: {e}")
                await query.answer("❌ خطأ في معالجة الزر")
            return

        # معالجة إدارة زر محدد (النظام المُحدث)
        if data.startswith(f"manage_button_{owner_id}_{username}_"):
            encoded_name = data.replace(f"manage_button_{owner_id}_{username}_", "")
            # فك ترميز اسم الزر
            try:
                import base64
                button_name = base64.b64decode(encoded_name.encode('ascii')).decode('utf-8')
                await handle_single_button_management(query, context, owner_id, username, button_name)
            except Exception as decode_error:
                print(f"خطأ في فك ترميز اسم الزر: {decode_error}")
                # في حالة فشل فك الترميز، نعتبر encoded_name هو اسم الزر مباشرة
                button_name = encoded_name
                await handle_single_button_management(query, context, owner_id, username, button_name)
            return

        # معالجة قائمة حذف الأزرار
        if data == f"delete_button_list_{owner_id}_{username}":
            await handle_delete_button_list(query, context, owner_id, username)
            return

        # معالجة قائمة تغيير أسماء الأزرار
        if data == f"rename_button_list_{owner_id}_{username}":
            await handle_rename_button_list(query, context, owner_id, username)
            return

        # معالجة حذف زر محدد
        if data.startswith(f"delete_specific_button_{owner_id}_{username}_"):
            button_name = data.replace(f"delete_specific_button_{owner_id}_{username}_", "")
            await handle_delete_specific_button(query, context, owner_id, username, button_name)
            return

        # معالجة إعدادات زر محدد
        if data.startswith(f"button_settings_{owner_id}_{username}_"):
            button_name = data.replace(f"button_settings_{owner_id}_{username}_", "")
            await handle_button_settings(query, context, owner_id, username, button_name)
            return

        # معالجة حذف ملف معين من زر
        if data.startswith(f"delete_file_{owner_id}_{username}_"):
            parts = data.replace(f"delete_file_{owner_id}_{username}_", "").split("_FILE_")
            if len(parts) == 2:
                button_name, file_id = parts
                await handle_delete_button_file(query, context, owner_id, username, button_name, file_id)
            return

        # معالجة تأكيد حذف زر
        if data.startswith(f"confirm_delete_{owner_id}_{username}_"):
            encoded_name = data.replace(f"confirm_delete_{owner_id}_{username}_", "")
            try:
                import base64
                button_name = base64.b64decode(encoded_name.encode('ascii')).decode('utf-8')
                await handle_confirm_delete_button(query, context, owner_id, username, button_name)
            except Exception as decode_error:
                print(f"خطأ في فك ترميز اسم الزر للحذف: {decode_error}")
                await query.answer("❌ خطأ في معالجة اسم الزر")
            return

        # معالجة بدء تغيير اسم زر
        if data.startswith(f"start_rename_{owner_id}_{username}_"):
            encoded_name = data.replace(f"start_rename_{owner_id}_{username}_", "")
            try:
                import base64
                button_name = base64.b64decode(encoded_name.encode('ascii')).decode('utf-8')
                await handle_start_rename_button(query, context, owner_id, username, button_name)
            except Exception as decode_error:
                print(f"خطأ في فك ترميز اسم الزر للتعديل: {decode_error}")
                await query.answer("❌ خطأ في معالجة اسم الزر")
            return

        # معالجة حذف جميع ملفات الزر
        if data.startswith(f"delete_all_files_{owner_id}_{username}_"):
            button_name = data.replace(f"delete_all_files_{owner_id}_{username}_", "")
            await handle_delete_all_button_files(query, context, owner_id, username, button_name)
            return

        # تغيير اسم زر - الخطوة الأولى
        if data == f"rename_button_{owner_id}_{username}":
            await handle_rename_button_step1(query, context, owner_id, username)
            return

        # حذف زر - الخطوة الأولى
        if data == f"delete_button_{owner_id}_{username}":
            await handle_delete_button_step1(query, context, owner_id, username)
            return

        # تحديث التوكين - الخطوة الأولى
        if data == f"update_token_{owner_id}_{username}":
            await handle_update_token_step1(query, context, owner_id, username)
            return

        # تشغيل البوت
        if data == f"start_bot_{owner_id}_{username}":
            try:
                # فحص الحالة الحالية أولاً
                current_status = hosting_manager.get_bot_status(owner_id, username)

                keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                if current_status == "running":
                    # البوت يعمل بالفعل
                    await query.edit_message_text(
                        "✅ **البوت يعمل بالفعل!**\n\n"
                        f"🤖 **اسم البوت:** {username}\n"
                        f"🔗 **الرابط:** https://t.me/{username}bot\n"
                        f"🟢 **الحالة:** نشط ويعمل على Replit\n\n"
                        f"💡 **البوت جاهز للاستخدام من خلال الرابط أعلاه**",
                        reply_markup=reply_markup
                    )
                    return

                # عرض رسالة انتظار
                await query.edit_message_text("🔄 جاري تشغيل البوت... يرجى الانتظار")

                # إنشاء instance البوت للتحقق من البيانات
                bot_instance = HostedBot(owner_id, username, "")
                success = bot_instance.start_user_bot()

                if success:
                    await query.edit_message_text(
                        "🚀 **تم تشغيل البوت بنجاح!**\n\n"
                        f"🤖 **اسم البوت:** {username}\n"
                        f"🔗 **الرابط:** https://t.me/{username}bot\n"
                        f"✅ **الحالة:** يعمل الآن على Replit\n\n"
                        f"💡 **يمكنك الآن استخدام البوت من خلال الرابط أعلاه**",
                        reply_markup=reply_markup
                    )
                else:
                    # فحص سبب الفشل
                    status = bot_instance.get_bot_status()
                    if status == "no_token":
                        message = "❌ **لا يوجد توكين مسجل**\n\n"
                        message += "🔧 **يرجى تحديث التوكين أولاً من القائمة**"
                    elif status == "invalid_token":
                        message = "❌ **التوكين غير صالح**\n\n"
                        message += "🔧 **يرجى تحديث التوكين من القائمة**"
                    else:
                        message = (
                            "❌ **فشل في تشغيل البوت**\n\n"
                            f"🔍 **الأسباب المحتملة:**\n"
                            f"• التوكين غير صحيح أو منتهي الصلاحية\n"
                            f"• البوت غير مفعل من @BotFather\n"
                            f"• مشكلة في الاتصال بخوادم تليجرام\n\n"
                            f"💡 **الحل:**\n"
                            f"• تحديث التوكين من القائمة\n"
                            f"• التأكد من تفعيل البوت عند @BotFather\n"
                            f"• المحاولة مرة أخرى بعد دقائق"
                        )

                    await query.edit_message_text(message, reply_markup=reply_markup)

            except Exception as e:
                print(f"❌ خطأ في callback تشغيل البوت: {e}")
                import traceback
                print(f"📋 تفاصيل الخطأ: {traceback.format_exc()}")
                keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    "❌ **حدث خطأ تقني في تشغيل البوت**\n\n"
                    f"🔧 **يرجى المحاولة مرة أخرى أو تحديث التوكين**",
                    reply_markup=reply_markup
                )
            return

        elif data == f"stop_bot_{owner_id}_{username}":
            try:
                # عرض رسالة انتظار
                await query.edit_message_text("⏹️ جاري إيقاف البوت...")

                # محاولة إيقاف البوت باستخدام مدير الاستضافة
                success = await hosting_manager.stop_user_bot(owner_id, username)

                keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                if success:
                    # تحديث حالة البوت في قاعدة البيانات
                    bot_instance = HostedBot(owner_id, username, "", "")
                    bot_instance.set_bot_status("stopped")

                    await query.edit_message_text(
                        "⏹️ **تم إيقاف البوت بنجاح**\n\n"
                        f"🤖 **البوت:** {username}\n"
                        f"✅ **الحالة:** متوقف\n\n"
                        f"💡 **يمكنك تشغيله مرة أخرى من القائمة**",
                        reply_markup=reply_markup
                    )
                else:
                    await query.edit_message_text(
                        "ℹ️ **البوت متوقف مسبقاً**\n\n"
                        f"🤖 **البوت:** {username}\n"
                        f"📊 **الحالة:** متوقف",
                        reply_markup=reply_markup
                    )
            except Exception as e:
                print(f"خطأ في callback إيقاف البوت: {e}")
                keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    "❌ **حدث خطأ في إيقاف البوت**\n\n"
                    f"🔧 **حاول مرة أخرى**",
                    reply_markup=reply_markup
                )
            return

        # إلغاء تحديث التوكين
        if data == f"cancel_token_update_{owner_id}_{username}":
            await handle_cancel_token_update(query, context, owner_id, username)
            return

        # إلغاء تغيير اسم الزر
        if data == f"cancel_rename_{owner_id}_{username}":
            # إزالة حالة انتظار تغيير الاسم
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_rename_old', None)
                state_data.pop('waiting_for_rename_new', None)
                state_data.pop('rename_old_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء تغيير اسم الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # إلغاء حذف الزر
        if data == f"cancel_delete_{owner_id}_{username}":
            # إزالة حالة انتظار حذف الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_delete_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء حذف الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة تأكيد إضافة زر نصي
        if data == f"confirm_text_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    # طلب محتوى الرسالة النصية
                    state_data['waiting_text_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"📝 **محتوى الزر النصي: {button_name}**\n\n"
                        "اكتب النص الذي سيتم إرساله عند الضغط على الزر:\n\n"
                        "💡 يمكنك استخدام:\n"
                        "• نصوص عادية\n"
                        "• رموز تعبيرية\n"
                        "• رسائل متعددة الأسطر",
                        reply_markup=reply_markup
                    )
            return

        # معالجة إضافة رابط للزر
        if data == f"add_url_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    state_data['waiting_url_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"🔗 **رابط الزر: {button_name}**\n\n"
                        "أدخل الرابط الذي سيتم فتحه عند الضغط على الزر:\n\n"
                        "💡 مثال:\n"
                        "• https://telegram.org\n"
                        "• https://youtube.com\n"
                        "• https://github.com\n\n"
                        "⚠️ تأكد من أن الرابط يبدأ بـ http:// أو https://",
                        reply_markup=reply_markup
                    )
            return

        # معالجة طلب تحميل ملف للزر
        if data == f"upload_file_button_{owner_id}_{username}":
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "📎 **تحميل ملف للزر**\n\n"
                "أرسل الملف الذي تريد ربطه بالزر:\n"
                "• 📷 صورة\n"
                "• 📄 مستند\n"
                "• 🎥 فيديو\n"
                "• 🎵 صوت\n\n"
                "سيتم ربط الملف بالزر تلقائياً عند الإرسال",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر
        if data == f"cancel_add_button_{owner_id}_{username}":
            # حذف الزر المؤقت وإلغاء العملية
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    bot_instance = HostedBot(owner_id, username, "", "")
                    bot_instance.delete_button(button_name)

                state_data.pop('waiting_file_for', None)
                state_data['waiting_for_button_name'] = False

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر من الصفحة الرئيسية
        if data == f"cancel_add_button_main_{owner_id}_{username}":
            # إزالة حالة انتظار اسم الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_button_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء تحديث التوكين
        if data == f"cancel_token_update_{owner_id}_{username}":
            await handle_cancel_token_update(query, context, owner_id, username)
            return

        # إلغاء تغيير اسم الزر
        if data == f"cancel_rename_{owner_id}_{username}":
            # إزالة حالة انتظار تغيير الاسم
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_rename_old', None)
                state_data.pop('waiting_for_rename_new', None)
                state_data.pop('rename_old_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء تغيير اسم الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # إلغاء حذف الزر
        if data == f"cancel_delete_{owner_id}_{username}":
            # إزالة حالة انتظار حذف الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_delete_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء حذف الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة تأكيد إضافة زر نصي
        if data == f"confirm_text_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    # طلب محتوى الرسالة النصية
                    state_data['waiting_text_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"📝 **محتوى الزر النصي: {button_name}**\n\n"
                        "اكتب النص الذي سيتم إرساله عند الضغط على الزر:\n\n"
                        "💡 يمكنك استخدام:\n"
                        "• نصوص عادية\n"
                        "• رموز تعبيرية\n"
                        "• رسائل متعددة الأسطر",
                        reply_markup=reply_markup
                    )
            return

        # معالجة إضافة رابط للزر
        if data == f"add_url_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    state_data['waiting_url_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"🔗 **رابط الزر: {button_name}**\n\n"
                        "أدخل الرابط الذي سيتم فتحه عند الضغط على الزر:\n\n"
                        "💡 مثال:\n"
                        "• https://telegram.org\n"
                        "• https://youtube.com\n"
                        "• https://github.com\n\n"
                        "⚠️ تأكد من أن الرابط يبدأ بـ http:// أو https://",
                        reply_markup=reply_markup
                    )
            return

        # معالجة طلب تحميل ملف للزر
        if data == f"upload_file_button_{owner_id}_{username}":
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "📎 **تحميل ملف للزر**\n\n"
                "أرسل الملف الذي تريد ربطه بالزر:\n"
                "• 📷 صورة\n"
                "• 📄 مستند\n"
                "• 🎥 فيديو\n"
                "• 🎵 صوت\n\n"
                "سيتم ربط الملف بالزر تلقائياً عند الإرسال",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر
        if data == f"cancel_add_button_{owner_id}_{username}":
            # حذف الزر المؤقت وإلغاء العملية
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    bot_instance = HostedBot(owner_id, username, "", "")
                    bot_instance.delete_button(button_name)

                state_data.pop('waiting_file_for', None)
                state_data['waiting_for_button_name'] = False

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر من الصفحة الرئيسية
        if data == f"cancel_add_button_main_{owner_id}_{username}":
            # إزالة حالة انتظار اسم الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_button_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء تحديث التوكين
        if data == f"cancel_token_update_{owner_id}_{username}":
            await handle_cancel_token_update(query, context, owner_id, username)
            return

        # إلغاء تغيير اسم الزر
        if data == f"cancel_rename_{owner_id}_{username}":
            # إزالة حالة انتظار تغيير الاسم
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_rename_old', None)
                state_data.pop('waiting_for_rename_new', None)
                state_data.pop('rename_old_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء تغيير اسم الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # إلغاء حذف الزر
        if data == f"cancel_delete_{owner_id}_{username}":
            # إزالة حالة انتظار حذف الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_delete_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء حذف الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة تأكيد إضافة زر نصي
        if data == f"confirm_text_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    # طلب محتوى الرسالة النصية
                    state_data['waiting_text_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"📝 **محتوى الزر النصي: {button_name}**\n\n"
                        "اكتب النص الذي سيتم إرساله عند الضغط على الزر:\n\n"
                        "💡 يمكنك استخدام:\n"
                        "• نصوص عادية\n"
                        "• رموز تعبيرية\n"
                        "• رسائل متعددة الأسطر",
                        reply_markup=reply_markup
                    )
            return

        # معالجة إضافة رابط للزر
        if data == f"add_url_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    state_data['waiting_url_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"🔗 **رابط الزر: {button_name}**\n\n"
                        "أدخل الرابط الذي سيتم فتحه عند الضغط على الزر:\n\n"
                        "💡 مثال:\n"
                        "• https://telegram.org\n"
                        "• https://youtube.com\n"
                        "• https://github.com\n\n"
                        "⚠️ تأكد من أن الرابط يبدأ بـ http:// أو https://",
                        reply_markup=reply_markup
                    )
            return

        # معالجة طلب تحميل ملف للزر
        if data == f"upload_file_button_{owner_id}_{username}":
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "📎 **تحميل ملف للزر**\n\n"
                "أرسل الملف الذي تريد ربطه بالزر:\n"
                "• 📷 صورة\n"
                "• 📄 مستند\n"
                "• 🎥 فيديو\n"
                "• 🎵 صوت\n\n"
                "سيتم ربط الملف بالزر تلقائياً عند الإرسال",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر
        if data == f"cancel_add_button_{owner_id}_{username}":
            # حذف الزر المؤقت وإلغاء العملية
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    bot_instance = HostedBot(owner_id, username, "", "")
                    bot_instance.delete_button(button_name)

                state_data.pop('waiting_file_for', None)
                state_data['waiting_for_button_name'] = False

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر من الصفحة الرئيسية
        if data == f"cancel_add_button_main_{owner_id}_{username}":
            # إزالة حالة انتظار اسم الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_button_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء تحديث التوكين
        if data == f"cancel_token_update_{owner_id}_{username}":
            await handle_cancel_token_update(query, context, owner_id, username)
            return

        # إلغاء تغيير اسم الزر
        if data == f"cancel_rename_{owner_id}_{username}":
            # إزالة حالة انتظار تغيير الاسم
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_rename_old', None)
                state_data.pop('waiting_for_rename_new', None)
                state_data.pop('rename_old_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء تغيير اسم الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # إلغاء حذف الزر
        if data == f"cancel_delete_{owner_id}_{username}":
            # إزالة حالة انتظار حذف الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_delete_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء حذف الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة تأكيد إضافة زر نصي
        if data == f"confirm_text_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    # طلب محتوى الرسالة النصية
                    state_data['waiting_text_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"📝 **محتوى الزر النصي: {button_name}**\n\n"
                        "اكتب النص الذي سيتم إرساله عند الضغط على الزر:\n\n"
                        "💡 يمكنك استخدام:\n"
                        "• نصوص عادية\n"
                        "• رموز تعبيرية\n"
                        "• رسائل متعددة الأسطر",
                        reply_markup=reply_markup
                    )
            return

        # معالجة إضافة رابط للزر
        if data == f"add_url_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    state_data['waiting_url_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"🔗 **رابط الزر: {button_name}**\n\n"
                        "أدخل الرابط الذي سيتم فتحه عند الضغط على الزر:\n\n"
                        "💡 مثال:\n"
                        "• https://telegram.org\n"
                        "• https://youtube.com\n"
                        "• https://github.com\n\n"
                        "⚠️ تأكد من أن الرابط يبدأ بـ http:// أو https://",
                        reply_markup=reply_markup
                    )
            return

        # معالجة طلب تحميل ملف للزر
        if data == f"upload_file_button_{owner_id}_{username}":
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "📎 **تحميل ملف للزر**\n\n"
                "أرسل الملف الذي تريد ربطه بالزر:\n"
                "• 📷 صورة\n"
                "• 📄 مستند\n"
                "• 🎥 فيديو\n"
                "• 🎵 صوت\n\n"
                "سيتم ربط الملف بالزر تلقائياً عند الإرسال",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر
        if data == f"cancel_add_button_{owner_id}_{username}":
            # حذف الزر المؤقت وإلغاء العملية
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    bot_instance = HostedBot(owner_id, username, "", "")
                    bot_instance.delete_button(button_name)

                state_data.pop('waiting_file_for', None)
                state_data['waiting_for_button_name'] = False

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر من الصفحة الرئيسية
        if data == f"cancel_add_button_main_{owner_id}_{username}":
            # إزالة حالة انتظار اسم الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_button_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء تحديث التوكين
        if data == f"cancel_token_update_{owner_id}_{username}":
            await handle_cancel_token_update(query, context, owner_id, username)
            return

        # إلغاء تغيير اسم الزر
        if data == f"cancel_rename_{owner_id}_{username}":
            # إزالة حالة انتظار تغيير الاسم
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_rename_old', None)
                state_data.pop('waiting_for_rename_new', None)
                state_data.pop('rename_old_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء تغيير اسم الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # إلغاء حذف الزر
        if data == f"cancel_delete_{owner_id}_{username}":
            # إزالة حالة انتظار حذف الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_delete_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء حذف الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة تأكيد إضافة زر نصي
        if data == f"confirm_text_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    # طلب محتوى الرسالة النصية
                    state_data['waiting_text_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"📝 **محتوى الزر النصي: {button_name}**\n\n"
                        "اكتب النص الذي سيتم إرساله عند الضغط على الزر:\n\n"
                        "💡 يمكنك استخدام:\n"
                        "• نصوص عادية\n"
                        "• رموز تعبيرية\n"
                        "• رسائل متعددة الأسطر",
                        reply_markup=reply_markup
                    )
            return

        # معالجة إضافة رابط للزر
        if data == f"add_url_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    state_data['waiting_url_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"🔗 **رابط الزر: {button_name}**\n\n"
                        "أدخل الرابط الذي سيتم فتحه عند الضغط على الزر:\n\n"
                        "💡 مثال:\n"
                        "• https://telegram.org\n"
                        "• https://youtube.com\n"
                        "• https://github.com\n\n"
                        "⚠️ تأكد من أن الرابط يبدأ بـ http:// أو https://",
                        reply_markup=reply_markup
                    )
            return

        # معالجة طلب تحميل ملف للزر
        if data == f"upload_file_button_{owner_id}_{username}":
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "📎 **تحميل ملف للزر**\n\n"
                "أرسل الملف الذي تريد ربطه بالزر:\n"
                "• 📷 صورة\n"
                "• 📄 مستند\n"
                "• 🎥 فيديو\n"
                "• 🎵 صوت\n\n"
                "سيتم ربط الملف بالزر تلقائياً عند الإرسال",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر
        if data == f"cancel_add_button_{owner_id}_{username}":
            # حذف الزر المؤقت وإلغاء العملية
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    bot_instance = HostedBot(owner_id, username, "", "")
                    bot_instance.delete_button(button_name)

                state_data.pop('waiting_file_for', None)
                state_data['waiting_for_button_name'] = False

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر من الصفحة الرئيسية
        if data == f"cancel_add_button_main_{owner_id}_{username}":
            # إزالة حالة انتظار اسم الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_button_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء تحديث التوكين
        if data == f"cancel_token_update_{owner_id}_{username}":
            await handle_cancel_token_update(query, context, owner_id, username)
            return

        # إلغاء تغيير اسم الزر
        if data == f"cancel_rename_{owner_id}_{username}":
            # إزالة حالة انتظار تغيير الاسم
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_rename_old', None)
                state_data.pop('waiting_for_rename_new', None)
                state_data.pop('rename_old_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء تغيير اسم الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # إلغاء حذف الزر
        if data == f"cancel_delete_{owner_id}_{username}":
            # إزالة حالة انتظار حذف الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_delete_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء حذف الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة تأكيد إضافة زر نصي
        if data == f"confirm_text_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    # طلب محتوى الرسالة النصية
                    state_data['waiting_text_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"📝 **محتوى الزر النصي: {button_name}**\n\n"
                        "اكتب النص الذي سيتم إرساله عند الضغط على الزر:\n\n"
                        "💡 يمكنك استخدام:\n"
                        "• نصوص عادية\n"
                        "• رموز تعبيرية\n"
                        "• رسائل متعددة الأسطر",
                        reply_markup=reply_markup
                    )
            return

        # معالجة إضافة رابط للزر
        if data == f"add_url_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    state_data['waiting_url_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"🔗 **رابط الزر: {button_name}**\n\n"
                        "أدخل الرابط الذي سيتم فتحه عند الضغط على الزر:\n\n"
                        "💡 مثال:\n"
                        "• https://telegram.org\n"
                        "• https://youtube.com\n"
                        "• https://github.com\n\n"
                        "⚠️ تأكد من أن الرابط يبدأ بـ http:// أو https://",
                        reply_markup=reply_markup
                    )
            return

        # معالجة طلب تحميل ملف للزر
        if data == f"upload_file_button_{owner_id}_{username}":
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "📎 **تحميل ملف للزر**\n\n"
                "أرسل الملف الذي تريد ربطه بالزر:\n"
                "• 📷 صورة\n"
                "• 📄 مستند\n"
                "• 🎥 فيديو\n"
                "• 🎵 صوت\n\n"
                "سيتم ربط الملف بالزر تلقائياً عند الإرسال",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر
        if data == f"cancel_add_button_{owner_id}_{username}":
            # حذف الزر المؤقت وإلغاء العملية
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    bot_instance = HostedBot(owner_id, username, "", "")
                    bot_instance.delete_button(button_name)

                state_data.pop('waiting_file_for', None)
                state_data['waiting_for_button_name'] = False

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر من الصفحة الرئيسية
        if data == f"cancel_add_button_main_{owner_id}_{username}":
            # إزالة حالة انتظار اسم الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_button_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء تحديث التوكين
        if data == f"cancel_token_update_{owner_id}_{username}":
            await handle_cancel_token_update(query, context, owner_id, username)
            return

        # إلغاء تغيير اسم الزر
        if data == f"cancel_rename_{owner_id}_{username}":
            # إزالة حالة انتظار تغيير الاسم
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_rename_old', None)
                state_data.pop('waiting_for_rename_new', None)
                state_data.pop('rename_old_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء تغيير اسم الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # إلغاء حذف الزر
        if data == f"cancel_delete_{owner_id}_{username}":
            # إزالة حالة انتظار حذف الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_delete_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء حذف الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة تأكيد إضافة زر نصي
        if data == f"confirm_text_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    # طلب محتوى الرسالة النصية
                    state_data['waiting_text_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"📝 **محتوى الزر النصي: {button_name}**\n\n"
                        "اكتب النص الذي سيتم إرساله عند الضغط على الزر:\n\n"
                        "💡 يمكنك استخدام:\n"
                        "• نصوص عادية\n"
                        "• رموز تعبيرية\n"
                        "• رسائل متعددة الأسطر",
                        reply_markup=reply_markup
                    )
            return

        # معالجة إضافة رابط للزر
        if data == f"add_url_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    state_data['waiting_url_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"🔗 **رابط الزر: {button_name}**\n\n"
                        "أدخل الرابط الذي سيتم فتحه عند الضغط على الزر:\n\n"
                        "💡 مثال:\n"
                        "• https://telegram.org\n"
                        "• https://youtube.com\n"
                        "• https://github.com\n\n"
                        "⚠️ تأكد من أن الرابط يبدأ بـ http:// أو https://",
                        reply_markup=reply_markup
                    )
            return

        # معالجة طلب تحميل ملف للزر
        if data == f"upload_file_button_{owner_id}_{username}":
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "📎 **تحميل ملف للزر**\n\n"
                "أرسل الملف الذي تريد ربطه بالزر:\n"
                "• 📷 صورة\n"
                "• 📄 مستند\n"
                "• 🎥 فيديو\n"
                "• 🎵 صوت\n\n"
                "سيتم ربط الملف بالزر تلقائياً عند الإرسال",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر
        if data == f"cancel_add_button_{owner_id}_{username}":
            # حذف الزر المؤقت وإلغاء العملية
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    bot_instance = HostedBot(owner_id, username, "", "")
                    bot_instance.delete_button(button_name)

                state_data.pop('waiting_file_for', None)
                state_data['waiting_for_button_name'] = False

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر من الصفحة الرئيسية
        if data == f"cancel_add_button_main_{owner_id}_{username}":
            # إزالة حالة انتظار اسم الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_button_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء تحديث التوكين
        if data == f"cancel_token_update_{owner_id}_{username}":
            await handle_cancel_token_update(query, context, owner_id, username)
            return

        # إلغاء تغيير اسم الزر
        if data == f"cancel_rename_{owner_id}_{username}":
            # إزالة حالة انتظار تغيير الاسم
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_rename_old', None)
                state_data.pop('waiting_for_rename_new', None)
                state_data.pop('rename_old_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء تغيير اسم الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # إلغاء حذف الزر
        if data == f"cancel_delete_{owner_id}_{username}":
            # إزالة حالة انتظار حذف الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_delete_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء حذف الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة تأكيد إضافة زر نصي
        if data == f"confirm_text_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    # طلب محتوى الرسالة النصية
                    state_data['waiting_text_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"📝 **محتوى الزر النصي: {button_name}**\n\n"
                        "اكتب النص الذي سيتم إرساله عند الضغط على الزر:\n\n"
                        "💡 يمكنك استخدام:\n"
                        "• نصوص عادية\n"
                        "• رموز تعبيرية\n"
                        "• رسائل متعددة الأسطر",
                        reply_markup=reply_markup
                    )
            return

        # معالجة إضافة رابط للزر
        if data == f"add_url_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    state_data['waiting_url_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"🔗 **رابط الزر: {button_name}**\n\n"
                        "أدخل الرابط الذي سيتم فتحه عند الضغط على الزر:\n\n"
                        "💡 مثال:\n"
                        "• https://telegram.org\n"
                        "• https://youtube.com\n"
                        "• https://github.com\n\n"
                        "⚠️ تأكد من أن الرابط يبدأ بـ http:// أو https://",
                        reply_markup=reply_markup
                    )
            return

        # معالجة طلب تحميل ملف للزر
        if data == f"upload_file_button_{owner_id}_{username}":
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "📎 **تحميل ملف للزر**\n\n"
                "أرسل الملف الذي تريد ربطه بالزر:\n"
                "• 📷 صورة\n"
                "• 📄 مستند\n"
                "• 🎥 فيديو\n"
                "• 🎵 صوت\n\n"
                "سيتم ربط الملف بالزر تلقائياً عند الإرسال",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر
        if data == f"cancel_add_button_{owner_id}_{username}":
            # حذف الزر المؤقت وإلغاء العملية
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    bot_instance = HostedBot(owner_id, username, "", "")
                    bot_instance.delete_button(button_name)

                state_data.pop('waiting_file_for', None)
                state_data['waiting_for_button_name'] = False

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر من الصفحة الرئيسية
        if data == f"cancel_add_button_main_{owner_id}_{username}":
            # إزالة حالة انتظار اسم الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_button_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء تحديث التوكين
        if data == f"cancel_token_update_{owner_id}_{username}":
            await handle_cancel_token_update(query, context, owner_id, username)
            return

        # إلغاء تغيير اسم الزر
        if data == f"cancel_rename_{owner_id}_{username}":
            # إزالة حالة انتظار تغيير الاسم
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_rename_old', None)
                state_data.pop('waiting_for_rename_new', None)
                state_data.pop('rename_old_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء تغيير اسم الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # إلغاء حذف الزر
        if data == f"cancel_delete_{owner_id}_{username}":
            # إزالة حالة انتظار حذف الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_delete_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء حذف الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة تأكيد إضافة زر نصي
        if data == f"confirm_text_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    # طلب محتوى الرسالة النصية
                    state_data['waiting_text_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"📝 **محتوى الزر النصي: {button_name}**\n\n"
                        "اكتب النص الذي سيتم إرساله عند الضغط على الزر:\n\n"
                        "💡 يمكنك استخدام:\n"
                        "• نصوص عادية\n"
                        "• رموز تعبيرية\n"
                        "• رسائل متعددة الأسطر",
                        reply_markup=reply_markup
                    )
            return

        # معالجة إضافة رابط للزر
        if data == f"add_url_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    state_data['waiting_url_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"🔗 **رابط الزر: {button_name}**\n\n"
                        "أدخل الرابط الذي سيتم فتحه عند الضغط على الزر:\n\n"
                        "💡 مثال:\n"
                        "• https://telegram.org\n"
                        "• https://youtube.com\n"
                        "• https://github.com\n\n"
                        "⚠️ تأكد من أن الرابط يبدأ بـ http:// أو https://",
                        reply_markup=reply_markup
                    )
            return

        # معالجة طلب تحميل ملف للزر
        if data == f"upload_file_button_{owner_id}_{username}":
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "📎 **تحميل ملف للزر**\n\n"
                "أرسل الملف الذي تريد ربطه بالزر:\n"
                "• 📷 صورة\n"
                "• 📄 مستند\n"
                "• 🎥 فيديو\n"
                "• 🎵 صوت\n\n"
                "سيتم ربط الملف بالزر تلقائياً عند الإرسال",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر
        if data == f"cancel_add_button_{owner_id}_{username}":
            # حذف الزر المؤقت وإلغاء العملية
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    bot_instance = HostedBot(owner_id, username, "", "")
                    bot_instance.delete_button(button_name)

                state_data.pop('waiting_file_for', None)
                state_data['waiting_for_button_name'] = False

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر من الصفحة الرئيسية
        if data == f"cancel_add_button_main_{owner_id}_{username}":
            # إزالة حالة انتظار اسم الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_button_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء تحديث التوكين
        if data == f"cancel_token_update_{owner_id}_{username}":
            await handle_cancel_token_update(query, context, owner_id, username)
            return

        # إلغاء تغيير اسم الزر
        if data == f"cancel_rename_{owner_id}_{username}":
            # إزالة حالة انتظار تغيير الاسم
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_rename_old', None)
                state_data.pop('waiting_for_rename_new', None)
                state_data.pop('rename_old_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء تغيير اسم الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # إلغاء حذف الزر
        if data == f"cancel_delete_{owner_id}_{username}":
            # إزالة حالة انتظار حذف الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_delete_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء حذف الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة تأكيد إضافة زر نصي
        if data == f"confirm_text_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    # طلب محتوى الرسالة النصية
                    state_data['waiting_text_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"📝 **محتوى الزر النصي: {button_name}**\n\n"
                        "اكتب النص الذي سيتم إرساله عند الضغط على الزر:\n\n"
                        "💡 يمكنك استخدام:\n"
                        "• نصوص عادية\n"
                        "• رموز تعبيرية\n"
                        "• رسائل متعددة الأسطر",
                        reply_markup=reply_markup
                    )
            return

        # معالجة إضافة رابط للزر
        if data == f"add_url_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    state_data['waiting_url_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"🔗 **رابط الزر: {button_name}**\n\n"
                        "أدخل الرابط الذي سيتم فتحه عند الضغط على الزر:\n\n"
                        "💡 مثال:\n"
                        "• https://telegram.org\n"
                        "• https://youtube.com\n"
                        "• https://github.com\n\n"
                        "⚠️ تأكد من أن الرابط يبدأ بـ http:// أو https://",
                        reply_markup=reply_markup
                    )
            return

        # معالجة طلب تحميل ملف للزر
        if data == f"upload_file_button_{owner_id}_{username}":
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "📎 **تحميل ملف للزر**\n\n"
                "أرسل الملف الذي تريد ربطه بالزر:\n"
                "• 📷 صورة\n"
                "• 📄 مستند\n"
                "• 🎥 فيديو\n"
                "• 🎵 صوت\n\n"
                "سيتم ربط الملف بالزر تلقائياً عند الإرسال",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر
        if data == f"cancel_add_button_{owner_id}_{username}":
            # حذف الزر المؤقت وإلغاء العملية
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    bot_instance = HostedBot(owner_id, username, "", "")
                    bot_instance.delete_button(button_name)

                state_data.pop('waiting_file_for', None)
                state_data['waiting_for_button_name'] = False

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر من الصفحة الرئيسية
        if data == f"cancel_add_button_main_{owner_id}_{username}":
            # إزالة حالة انتظار اسم الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_button_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء تحديث التوكين
        if data == f"cancel_token_update_{owner_id}_{username}":
            await handle_cancel_token_update(query, context, owner_id, username)
            return

        # إلغاء تغيير اسم الزر
        if data == f"cancel_rename_{owner_id}_{username}":
            # إزالة حالة انتظار تغيير الاسم
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_rename_old', None)
                state_data.pop('waiting_for_rename_new', None)
                state_data.pop('rename_old_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء تغيير اسم الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # إلغاء حذف الزر
        if data == f"cancel_delete_{owner_id}_{username}":
            # إزالة حالة انتظار حذف الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_delete_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء حذف الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة تأكيد إضافة زر نصي
        if data == f"confirm_text_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    # طلب محتوى الرسالة النصية
                    state_data['waiting_text_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"📝 **محتوى الزر النصي: {button_name}**\n\n"
                        "اكتب النص الذي سيتم إرساله عند الضغط على الزر:\n\n"
                        "💡 يمكنك استخدام:\n"
                        "• نصوص عادية\n"
                        "• رموز تعبيرية\n"
                        "• رسائل متعددة الأسطر",
                        reply_markup=reply_markup
                    )
            return

        # معالجة إضافة رابط للزر
        if data == f"add_url_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    state_data['waiting_url_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"🔗 **رابط الزر: {button_name}**\n\n"
                        "أدخل الرابط الذي سيتم فتحه عند الضغط على الزر:\n\n"
                        "💡 مثال:\n"
                        "• https://telegram.org\n"
                        "• https://youtube.com\n"
                        "• https://github.com\n\n"
                        "⚠️ تأكد من أن الرابط يبدأ بـ http:// أو https://",
                        reply_markup=reply_markup
                    )
            return

        # معالجة طلب تحميل ملف للزر
        if data == f"upload_file_button_{owner_id}_{username}":
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "📎 **تحميل ملف للزر**\n\n"
                "أرسل الملف الذي تريد ربطه بالزر:\n"
                "• 📷 صورة\n"
                "• 📄 مستند\n"
                "• 🎥 فيديو\n"
                "• 🎵 صوت\n\n"
                "سيتم ربط الملف بالزر تلقائياً عند الإرسال",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر
        if data == f"cancel_add_button_{owner_id}_{username}":
            # حذف الزر المؤقت وإلغاء العملية
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    bot_instance = HostedBot(owner_id, username, "", "")
                    bot_instance.delete_button(button_name)

                state_data.pop('waiting_file_for', None)
                state_data['waiting_for_button_name'] = False

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر من الصفحة الرئيسية
        if data == f"cancel_add_button_main_{owner_id}_{username}":
            # إزالة حالة انتظار اسم الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_button_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء تحديث التوكين
        if data == f"cancel_token_update_{owner_id}_{username}":
            await handle_cancel_token_update(query, context, owner_id, username)
            return

        # إلغاء تغيير اسم الزر
        if data == f"cancel_rename_{owner_id}_{username}":
            # إزالة حالة انتظار تغيير الاسم
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_rename_old', None)
                state_data.pop('waiting_for_rename_new', None)
                state_data.pop('rename_old_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء تغيير اسم الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # إلغاء حذف الزر
        if data == f"cancel_delete_{owner_id}_{username}":
            # إزالة حالة انتظار حذف الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_delete_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء حذف الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة تأكيد إضافة زر نصي
        if data == f"confirm_text_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    # طلب محتوى الرسالة النصية
                    state_data['waiting_text_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"📝 **محتوى الزر النصي: {button_name}**\n\n"
                        "اكتب النص الذي سيتم إرساله عند الضغط على الزر:\n\n"
                        "💡 يمكنك استخدام:\n"
                        "• نصوص عادية\n"
                        "• رموز تعبيرية\n"
                        "• رسائل متعددة الأسطر",
                        reply_markup=reply_markup
                    )
            return

        # معالجة إضافة رابط للزر
        if data == f"add_url_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    state_data['waiting_url_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"🔗 **رابط الزر: {button_name}**\n\n"
                        "أدخل الرابط الذي سيتم فتحه عند الضغط على الزر:\n\n"
                        "💡 مثال:\n"
                        "• https://telegram.org\n"
                        "• https://youtube.com\n"
                        "• https://github.com\n\n"
                        "⚠️ تأكد من أن الرابط يبدأ بـ http:// أو https://",
                        reply_markup=reply_markup
                    )
            return

        # معالجة طلب تحميل ملف للزر
        if data == f"upload_file_button_{owner_id}_{username}":
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "📎 **تحميل ملف للزر**\n\n"
                "أرسل الملف الذي تريد ربطه بالزر:\n"
                "• 📷 صورة\n"
                "• 📄 مستند\n"
                "• 🎥 فيديو\n"
                "• 🎵 صوت\n\n"
                "سيتم ربط الملف بالزر تلقائياً عند الإرسال",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر
        if data == f"cancel_add_button_{owner_id}_{username}":
            # حذف الزر المؤقت وإلغاء العملية
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    bot_instance = HostedBot(owner_id, username, "", "")
                    bot_instance.delete_button(button_name)

                state_data.pop('waiting_file_for', None)
                state_data['waiting_for_button_name'] = False

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر من الصفحة الرئيسية
        if data == f"cancel_add_button_main_{owner_id}_{username}":
            # إزالة حالة انتظار اسم الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_button_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء تحديث التوكين
        if data == f"cancel_token_update_{owner_id}_{username}":
            await handle_cancel_token_update(query, context, owner_id, username)
            return

        # إلغاء تغيير اسم الزر
        if data == f"cancel_rename_{owner_id}_{username}":
            # إزالة حالة انتظار تغيير الاسم
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_rename_old', None)
                state_data.pop('waiting_for_rename_new', None)
                state_data.pop('rename_old_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء تغيير اسم الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # إلغاء حذف الزر
        if data == f"cancel_delete_{owner_id}_{username}":
            # إزالة حالة انتظار حذف الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_delete_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء حذف الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة تأكيد إضافة زر نصي
        if data == f"confirm_text_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    # طلب محتوى الرسالة النصية
                    state_data['waiting_text_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"📝 **محتوى الزر النصي: {button_name}**\n\n"
                        "اكتب النص الذي سيتم إرساله عند الضغط على الزر:\n\n"
                        "💡 يمكنك استخدام:\n"
                        "• نصوص عادية\n"
                        "• رموز تعبيرية\n"
                        "• رسائل متعددة الأسطر",
                        reply_markup=reply_markup
                    )
            return

        # معالجة إضافة رابط للزر
        if data == f"add_url_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    state_data['waiting_url_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"🔗 **رابط الزر: {button_name}**\n\n"
                        "أدخل الرابط الذي سيتم فتحه عند الضغط على الزر:\n\n"
                        "💡 مثال:\n"
                        "• https://telegram.org\n"
                        "• https://youtube.com\n"
                        "• https://github.com\n\n"
                        "⚠️ تأكد من أن الرابط يبدأ بـ http:// أو https://",
                        reply_markup=reply_markup
                    )
            return

        # معالجة طلب تحميل ملف للزر
        if data == f"upload_file_button_{owner_id}_{username}":
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "📎 **تحميل ملف للزر**\n\n"
                "أرسل الملف الذي تريد ربطه بالزر:\n"
                "• 📷 صورة\n"
                "• 📄 مستند\n"
                "• 🎥 فيديو\n"
                "• 🎵 صوت\n\n"
                "سيتم ربط الملف بالزر تلقائياً عند الإرسال",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر
        if data == f"cancel_add_button_{owner_id}_{username}":
            # حذف الزر المؤقت وإلغاء العملية
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    bot_instance = HostedBot(owner_id, username, "", "")
                    bot_instance.delete_button(button_name)

                state_data.pop('waiting_file_for', None)
                state_data['waiting_for_button_name'] = False

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر من الصفحة الرئيسية
        if data == f"cancel_add_button_main_{owner_id}_{username}":
            # إزالة حالة انتظار اسم الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_button_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء تحديث التوكين
        if data == f"cancel_token_update_{owner_id}_{username}":
            await handle_cancel_token_update(query, context, owner_id, username)
            return

        # إلغاء تغيير اسم الزر
        if data == f"cancel_rename_{owner_id}_{username}":
            # إزالة حالة انتظار تغيير الاسم
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_rename_old', None)
                state_data.pop('waiting_for_rename_new', None)
                state_data.pop('rename_old_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء تغيير اسم الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # إلغاء حذف الزر
        if data == f"cancel_delete_{owner_id}_{username}":
            # إزالة حالة انتظار حذف الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_delete_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء حذف الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة تأكيد إضافة زر نصي
        if data == f"confirm_text_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    # طلب محتوى الرسالة النصية
                    state_data['waiting_text_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"📝 **محتوى الزر النصي: {button_name}**\n\n"
                        "اكتب النص الذي سيتم إرساله عند الضغط على الزر:\n\n"
                        "💡 يمكنك استخدام:\n"
                        "• نصوص عادية\n"
                        "• رموز تعبيرية\n"
                        "• رسائل متعددة الأسطر",
                        reply_markup=reply_markup
                    )
            return

        # معالجة إضافة رابط للزر
        if data == f"add_url_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    state_data['waiting_url_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"🔗 **رابط الزر: {button_name}**\n\n"
                        "أدخل الرابط الذي سيتم فتحه عند الضغط على الزر:\n\n"
                        "💡 مثال:\n"
                        "• https://telegram.org\n"
                        "• https://youtube.com\n"
                        "• https://github.com\n\n"
                        "⚠️ تأكد من أن الرابط يبدأ بـ http:// أو https://",
                        reply_markup=reply_markup
                    )
            return

        # معالجة طلب تحميل ملف للزر
        if data == f"upload_file_button_{owner_id}_{username}":
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "📎 **تحميل ملف للزر**\n\n"
                "أرسل الملف الذي تريد ربطه بالزر:\n"
                "• 📷 صورة\n"
                "• 📄 مستند\n"
                "• 🎥 فيديو\n"
                "• 🎵 صوت\n\n"
                "سيتم ربط الملف بالزر تلقائياً عند الإرسال",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر
        if data == f"cancel_add_button_{owner_id}_{username}":
            # حذف الزر المؤقت وإلغاء العملية
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    bot_instance = HostedBot(owner_id, username, "", "")
                    bot_instance.delete_button(button_name)

                state_data.pop('waiting_file_for', None)
                state_data['waiting_for_button_name'] = False

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر من الصفحة الرئيسية
        if data == f"cancel_add_button_main_{owner_id}_{username}":
            # إزالة حالة انتظار اسم الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_button_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء تحديث التوكين
        if data == f"cancel_token_update_{owner_id}_{username}":
            await handle_cancel_token_update(query, context, owner_id, username)
            return

        # إلغاء تغيير اسم الزر
        if data == f"cancel_rename_{owner_id}_{username}":
            # إزالة حالة انتظار تغيير الاسم
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_rename_old', None)
                state_data.pop('waiting_for_rename_new', None)
                state_data.pop('rename_old_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء تغيير اسم الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # إلغاء حذف الزر
        if data == f"cancel_delete_{owner_id}_{username}":
            # إزالة حالة انتظار حذف الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_delete_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء حذف الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة تأكيد إضافة زر نصي
        if data == f"confirm_text_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    # طلب محتوى الرسالة النصية
                    state_data['waiting_text_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"📝 **محتوى الزر النصي: {button_name}**\n\n"
                        "اكتب النص الذي سيتم إرساله عند الضغط على الزر:\n\n"
                        "💡 يمكنك استخدام:\n"
                        "• نصوص عادية\n"
                        "• رموز تعبيرية\n"
                        "• رسائل متعددة الأسطر",
                        reply_markup=reply_markup
                    )
            return

        # معالجة إضافة رابط للزر
        if data == f"add_url_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    state_data['waiting_url_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"🔗 **رابط الزر: {button_name}**\n\n"
                        "أدخل الرابط الذي سيتم فتحه عند الضغط على الزر:\n\n"
                        "💡 مثال:\n"
                        "• https://telegram.org\n"
                        "• https://youtube.com\n"
                        "• https://github.com\n\n"
                        "⚠️ تأكد من أن الرابط يبدأ بـ http:// أو https://",
                        reply_markup=reply_markup
                    )
            return

        # معالجة طلب تحميل ملف للزر
        if data == f"upload_file_button_{owner_id}_{username}":
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "📎 **تحميل ملف للزر**\n\n"
                "أرسل الملف الذي تريد ربطه بالزر:\n"
                "• 📷 صورة\n"
                "• 📄 مستند\n"
                "• 🎥 فيديو\n"
                "• 🎵 صوت\n\n"
                "سيتم ربط الملف بالزر تلقائياً عند الإرسال",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر
        if data == f"cancel_add_button_{owner_id}_{username}":
            # حذف الزر المؤقت وإلغاء العملية
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    bot_instance = HostedBot(owner_id, username, "", "")
                    bot_instance.delete_button(button_name)

                state_data.pop('waiting_file_for', None)
                state_data['waiting_for_button_name'] = False

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر من الصفحة الرئيسية
        if data == f"cancel_add_button_main_{owner_id}_{username}":
            # إزالة حالة انتظار اسم الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_button_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء تحديث التوكين
        if data == f"cancel_token_update_{owner_id}_{username}":
            await handle_cancel_token_update(query, context, owner_id, username)
            return

        # إلغاء تغيير اسم الزر
        if data == f"cancel_rename_{owner_id}_{username}":
            # إزالة حالة انتظار تغيير الاسم
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_rename_old', None)
                state_data.pop('waiting_for_rename_new', None)
                state_data.pop('rename_old_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء تغيير اسم الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # إلغاء حذف الزر
        if data == f"cancel_delete_{owner_id}_{username}":
            # إزالة حالة انتظار حذف الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_delete_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء حذف الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة تأكيد إضافة زر نصي
        if data == f"confirm_text_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    # طلب محتوى الرسالة النصية
                    state_data['waiting_text_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"📝 **محتوى الزر النصي: {button_name}**\n\n"
                        "اكتب النص الذي سيتم إرساله عند الضغط على الزر:\n\n"
                        "💡 يمكنك استخدام:\n"
                        "• نصوص عادية\n"
                        "• رموز تعبيرية\n"
                        "• رسائل متعددة الأسطر",
                        reply_markup=reply_markup
                    )
            return

        # معالجة إضافة رابط للزر
        if data == f"add_url_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    state_data['waiting_url_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"🔗 **رابط الزر: {button_name}**\n\n"
                        "أدخل الرابط الذي سيتم فتحه عند الضغط على الزر:\n\n"
                        "💡 مثال:\n"
                        "• https://telegram.org\n"
                        "• https://youtube.com\n"
                        "• https://github.com\n\n"
                        "⚠️ تأكد من أن الرابط يبدأ بـ http:// أو https://",
                        reply_markup=reply_markup
                    )
            return

        # معالجة طلب تحميل ملف للزر
        if data == f"upload_file_button_{owner_id}_{username}":
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "📎 **تحميل ملف للزر**\n\n"
                "أرسل الملف الذي تريد ربطه بالزر:\n"
                "• 📷 صورة\n"
                "• 📄 مستند\n"
                "• 🎥 فيديو\n"
                "• 🎵 صوت\n\n"
                "سيتم ربط الملف بالزر تلقائياً عند الإرسال",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر
        if data == f"cancel_add_button_{owner_id}_{username}":
            # حذف الزر المؤقت وإلغاء العملية
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    bot_instance = HostedBot(owner_id, username, "", "")
                    bot_instance.delete_button(button_name)

                state_data.pop('waiting_file_for', None)
                state_data['waiting_for_button_name'] = False

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر من الصفحة الرئيسية
        if data == f"cancel_add_button_main_{owner_id}_{username}":
            # إزالة حالة انتظار اسم الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_button_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء تحديث التوكين
        if data == f"cancel_token_update_{owner_id}_{username}":
            await handle_cancel_token_update(query, context, owner_id, username)
            return

        # إلغاء تغيير اسم الزر
        if data == f"cancel_rename_{owner_id}_{username}":
            # إزالة حالة انتظار تغيير الاسم
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_rename_old', None)
                state_data.pop('waiting_for_rename_new', None)
                state_data.pop('rename_old_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء تغيير اسم الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # إلغاء حذف الزر
        if data == f"cancel_delete_{owner_id}_{username}":
            # إزالة حالة انتظار حذف الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_delete_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء حذف الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة تأكيد إضافة زر نصي
        if data == f"confirm_text_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    # طلب محتوى الرسالة النصية
                    state_data['waiting_text_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"📝 **محتوى الزر النصي: {button_name}**\n\n"
                        "اكتب النص الذي سيتم إرساله عند الضغط على الزر:\n\n"
                        "💡 يمكنك استخدام:\n"
                        "• نصوص عادية\n"
                        "• رموز تعبيرية\n"
                        "• رسائل متعددة الأسطر",
                        reply_markup=reply_markup
                    )
            return

        # معالجة إضافة رابط للزر
        if data == f"add_url_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    state_data['waiting_url_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"🔗 **رابط الزر: {button_name}**\n\n"
                        "أدخل الرابط الذي سيتم فتحه عند الضغط على الزر:\n\n"
                        "💡 مثال:\n"
                        "• https://telegram.org\n"
                        "• https://youtube.com\n"
                        "• https://github.com\n\n"
                        "⚠️ تأكد من أن الرابط يبدأ بـ http:// أو https://",
                        reply_markup=reply_markup
                    )
            return

        # معالجة طلب تحميل ملف للزر
        if data == f"upload_file_button_{owner_id}_{username}":
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "📎 **تحميل ملف للزر**\n\n"
                "أرسل الملف الذي تريد ربطه بالزر:\n"
                "• 📷 صورة\n"
                "• 📄 مستند\n"
                "• 🎥 فيديو\n"
                "• 🎵 صوت\n\n"
                "سيتم ربط الملف بالزر تلقائياً عند الإرسال",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر
        if data == f"cancel_add_button_{owner_id}_{username}":
            # حذف الزر المؤقت وإلغاء العملية
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    bot_instance = HostedBot(owner_id, username, "", "")
                    bot_instance.delete_button(button_name)

                state_data.pop('waiting_file_for', None)
                state_data['waiting_for_button_name'] = False

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر من الصفحة الرئيسية
        if data == f"cancel_add_button_main_{owner_id}_{username}":
            # إزالة حالة انتظار اسم الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_button_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء تحديث التوكين
        if data == f"cancel_token_update_{owner_id}_{username}":
            await handle_cancel_token_update(query, context, owner_id, username)
            return

        # إلغاء تغيير اسم الزر
        if data == f"cancel_rename_{owner_id}_{username}":
            # إزالة حالة انتظار تغيير الاسم
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_rename_old', None)
                state_data.pop('waiting_for_rename_new', None)
                state_data.pop('rename_old_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء تغيير اسم الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # إلغاء حذف الزر
        if data == f"cancel_delete_{owner_id}_{username}":
            # إزالة حالة انتظار حذف الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_delete_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء حذف الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة تأكيد إضافة زر نصي
        if data == f"confirm_text_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    # طلب محتوى الرسالة النصية
                    state_data['waiting_text_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"📝 **محتوى الزر النصي: {button_name}**\n\n"
                        "اكتب النص الذي سيتم إرساله عند الضغط على الزر:\n\n"
                        "💡 يمكنك استخدام:\n"
                        "• نصوص عادية\n"
                        "• رموز تعبيرية\n"
                        "• رسائل متعددة الأسطر",
                        reply_markup=reply_markup
                    )
            return

        # معالجة إضافة رابط للزر
        if data == f"add_url_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    state_data['waiting_url_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"🔗 **رابط الزر: {button_name}**\n\n"
                        "أدخل الرابط الذي سيتم فتحه عند الضغط على الزر:\n\n"
                        "💡 مثال:\n"
                        "• https://telegram.org\n"
                        "• https://youtube.com\n"
                        "• https://github.com\n\n"
                        "⚠️ تأكد من أن الرابط يبدأ بـ http:// أو https://",
                        reply_markup=reply_markup
                    )
            return

        # معالجة طلب تحميل ملف للزر
        if data == f"upload_file_button_{owner_id}_{username}":
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "📎 **تحميل ملف للزر**\n\n"
                "أرسل الملف الذي تريد ربطه بالزر:\n"
                "• 📷 صورة\n"
                "• 📄 مستند\n"
                "• 🎥 فيديو\n"
                "• 🎵 صوت\n\n"
                "سيتم ربط الملف بالزر تلقائياً عند الإرسال",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر
        if data == f"cancel_add_button_{owner_id}_{username}":
            # حذف الزر المؤقت وإلغاء العملية
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    bot_instance = HostedBot(owner_id, username, "", "")
                    bot_instance.delete_button(button_name)

                state_data.pop('waiting_file_for', None)
                state_data['waiting_for_button_name'] = False

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر من الصفحة الرئيسية
        if data == f"cancel_add_button_main_{owner_id}_{username}":
            # إزالة حالة انتظار اسم الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_button_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء تحديث التوكين
        if data == f"cancel_token_update_{owner_id}_{username}":
            await handle_cancel_token_update(query, context, owner_id, username)
            return

        # إلغاء تغيير اسم الزر
        if data == f"cancel_rename_{owner_id}_{username}":
            # إزالة حالة انتظار تغيير الاسم
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_rename_old', None)
                state_data.pop('waiting_for_rename_new', None)
                state_data.pop('rename_old_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء تغيير اسم الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # إلغاء حذف الزر
        if data == f"cancel_delete_{owner_id}_{username}":
            # إزالة حالة انتظار حذف الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_delete_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء حذف الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة تأكيد إضافة زر نصي
        if data == f"confirm_text_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    # طلب محتوى الرسالة النصية
                    state_data['waiting_text_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"📝 **محتوى الزر النصي: {button_name}**\n\n"
                        "اكتب النص الذي سيتم إرساله عند الضغط على الزر:\n\n"
                        "💡 يمكنك استخدام:\n"
                        "• نصوص عادية\n"
                        "• رموز تعبيرية\n"
                        "• رسائل متعددة الأسطر",
                        reply_markup=reply_markup
                    )
            return

        # معالجة إضافة رابط للزر
        if data == f"add_url_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    state_data['waiting_url_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"🔗 **رابط الزر: {button_name}**\n\n"
                        "أدخل الرابط الذي سيتم فتحه عند الضغط على الزر:\n\n"
                        "💡 مثال:\n"
                        "• https://telegram.org\n"
                        "• https://youtube.com\n"
                        "• https://github.com\n\n"
                        "⚠️ تأكد من أن الرابط يبدأ بـ http:// أو https://",
                        reply_markup=reply_markup
                    )
            return

        # معالجة طلب تحميل ملف للزر
        if data == f"upload_file_button_{owner_id}_{username}":
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "📎 **تحميل ملف للزر**\n\n"
                "أرسل الملف الذي تريد ربطه بالزر:\n"
                "• 📷 صورة\n"
                "• 📄 مستند\n"
                "• 🎥 فيديو\n"
                "• 🎵 صوت\n\n"
                "سيتم ربط الملف بالزر تلقائياً عند الإرسال",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر
        if data == f"cancel_add_button_{owner_id}_{username}":
            # حذف الزر المؤقت وإلغاء العملية
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    bot_instance = HostedBot(owner_id, username, "", "")
                    bot_instance.delete_button(button_name)

                state_data.pop('waiting_file_for', None)
                state_data['waiting_for_button_name'] = False

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر من الصفحة الرئيسية
        if data == f"cancel_add_button_main_{owner_id}_{username}":
            # إزالة حالة انتظار اسم الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_button_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء تحديث التوكين
        if data == f"cancel_token_update_{owner_id}_{username}":
            await handle_cancel_token_update(query, context, owner_id, username)
            return

        # إلغاء تغيير اسم الزر
        if data == f"cancel_rename_{owner_id}_{username}":
            # إزالة حالة انتظار تغيير الاسم
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_rename_old', None)
                state_data.pop('waiting_for_rename_new', None)
                state_data.pop('rename_old_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء تغيير اسم الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # إلغاء حذف الزر
        if data == f"cancel_delete_{owner_id}_{username}":
            # إزالة حالة انتظار حذف الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_delete_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء حذف الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة تأكيد إضافة زر نصي
        if data == f"confirm_text_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    # طلب محتوى الرسالة النصية
                    state_data['waiting_text_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"📝 **محتوى الزر النصي: {button_name}**\n\n"
                        "اكتب النص الذي سيتم إرساله عند الضغط على الزر:\n\n"
                        "💡 يمكنك استخدام:\n"
                        "• نصوص عادية\n"
                        "• رموز تعبيرية\n"
                        "• رسائل متعددة الأسطر",
                        reply_markup=reply_markup
                    )
            return

        # معالجة إضافة رابط للزر
        if data == f"add_url_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    state_data['waiting_url_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"🔗 **رابط الزر: {button_name}**\n\n"
                        "أدخل الرابط الذي سيتم فتحه عند الضغط على الزر:\n\n"
                        "💡 مثال:\n"
                        "• https://telegram.org\n"
                        "• https://youtube.com\n"
                        "• https://github.com\n\n"
                        "⚠️ تأكد من أن الرابط يبدأ بـ http:// أو https://",
                        reply_markup=reply_markup
                    )
            return

        # معالجة طلب تحميل ملف للزر
        if data == f"upload_file_button_{owner_id}_{username}":
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "📎 **تحميل ملف للزر**\n\n"
                "أرسل الملف الذي تريد ربطه بالزر:\n"
                "• 📷 صورة\n"
                "• 📄 مستند\n"
                "• 🎥 فيديو\n"
                "• 🎵 صوت\n\n"
                "سيتم ربط الملف بالزر تلقائياً عند الإرسال",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر
        if data == f"cancel_add_button_{owner_id}_{username}":
            # حذف الزر المؤقت وإلغاء العملية
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    bot_instance = HostedBot(owner_id, username, "", "")
                    bot_instance.delete_button(button_name)

                state_data.pop('waiting_file_for', None)
                state_data['waiting_for_button_name'] = False

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر من الصفحة الرئيسية
        if data == f"cancel_add_button_main_{owner_id}_{username}":
            # إزالة حالة انتظار اسم الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_button_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء تحديث التوكين
        if data == f"cancel_token_update_{owner_id}_{username}":
            await handle_cancel_token_update(query, context, owner_id, username)
            return

        # إلغاء تغيير اسم الزر
        if data == f"cancel_rename_{owner_id}_{username}":
            # إزالة حالة انتظار تغيير الاسم
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_rename_old', None)
                state_data.pop('waiting_for_rename_new', None)
                state_data.pop('rename_old_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء تغيير اسم الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # إلغاء حذف الزر
        if data == f"cancel_delete_{owner_id}_{username}":
            # إزالة حالة انتظار حذف الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_delete_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء حذف الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة تأكيد إضافة زر نصي
        if data == f"confirm_text_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    # طلب محتوى الرسالة النصية
                    state_data['waiting_text_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"📝 **محتوى الزر النصي: {button_name}**\n\n"
                        "اكتب النص الذي سيتم إرساله عند الضغط على الزر:\n\n"
                        "💡 يمكنك استخدام:\n"
                        "• نصوص عادية\n"
                        "• رموز تعبيرية\n"
                        "• رسائل متعددة الأسطر",
                        reply_markup=reply_markup
                    )
            return

        # معالجة إضافة رابط للزر
        if data == f"add_url_button_{owner_id}_{username}":
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    state_data['waiting_url_content'] = True
                    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"🔗 **رابط الزر: {button_name}**\n\n"
                        "أدخل الرابط الذي سيتم فتحه عند الضغط على الزر:\n\n"
                        "💡 مثال:\n"
                        "• https://telegram.org\n"
                        "• https://youtube.com\n"
                        "• https://github.com\n\n"
                        "⚠️ تأكد من أن الرابط يبدأ بـ http:// أو https://",
                        reply_markup=reply_markup
                    )
            return

        # معالجة طلب تحميل ملف للزر
        if data == f"upload_file_button_{owner_id}_{username}":
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "📎 **تحميل ملف للزر**\n\n"
                "أرسل الملف الذي تريد ربطه بالزر:\n"
                "• 📷 صورة\n"
                "• 📄 مستند\n"
                "• 🎥 فيديو\n"
                "• 🎵 صوت\n\n"
                "سيتم ربط الملف بالزر تلقائياً عند الإرسال",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر
        if data == f"cancel_add_button_{owner_id}_{username}":
            # حذف الزر المؤقت وإلغاء العملية
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                button_name = state_data.get('waiting_file_for')
                if button_name:
                    bot_instance = HostedBot(owner_id, username, "", "")
                    bot_instance.delete_button(button_name)

                state_data.pop('waiting_file_for', None)
                state_data['waiting_for_button_name'] = False

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء إضافة الزر من الصفحة الرئيسية
        if data == f"cancel_add_button_main_{owner_id}_{username}":
            # إزالة حالة انتظار اسم الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_button_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ **تم إلغاء إضافة الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء تحديث التوكين
        if data == f"cancel_token_update_{owner_id}_{username}":
            await handle_cancel_token_update(query, context, owner_id, username)
            return

        # إلغاء تغيير اسم الزر
        if data == f"cancel_rename_{owner_id}_{username}":
            # إزالة حالة انتظار تغيير الاسم
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_rename_old', None)
                state_data.pop('waiting_for_rename_new', None)
                state_data.pop('rename_old_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء تغيير اسم الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # إلغاء حذف الزر
        if data == f"cancel_delete_{owner_id}_{username}":
            # إزالة حالة انتظار حذف الزر
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_delete_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء حذف الزر**\n\n"
                "لم يتم حفظ أي تغييرات",
                reply_markup=reply_markup
            )
            return

        # معالجة إلغاء اختيار زر لتغيير الاسم
        if data.startswith(f"cancel_rename_{owner_id}_{username}"):
            if user_id in USER_STATES:
                state_data = USER_STATES[user_id]
                state_data.pop('waiting_for_rename_new', None)
                state_data.pop('rename_old_name', None)
                state_data['waiting_for_rename_old'] = True # العودة لطلب الزر القديم

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **تم إلغاء اختيار الزر**\n\n"
                "اكتب اسم الزر القديم مرة أخرى",
                reply_markup=reply_markup
            )
            return

        # معالجة اختيار زر لتغيير الاسم
        if data.startswith(f"rename_select_{owner_id}_{username}_"):
            button_name = data.replace(f"rename_select_{owner_id}_{username}_", "")

            # حفظ اسم الزر المختار وطلب الاسم الجديد
            USER_STATES[user_id] = {
                'state': 'linux0root_authenticated',
                'owner_id': owner_id,
                'username': username,
                'waiting_for_rename_new': True,
                'rename_old_name': button_name
            }

            keyboard = [
                [InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_rename_{owner_id}_{username}")],
                [InlineKeyboardButton("🔙 اختيار زر آخر", callback_data=f"rename_button_{owner_id}_{username}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                f"✏️ **تغيير اسم الزر**\n\n"
                f"🔘 **الزر المختار:** {button_name}\n\n"
                f"📝 **اكتب الاسم الجديد للزر:**\n\n"
                f"💡 **تأكد من اختيار اسم مميز وواضح**",
                reply_markup=reply_markup
            )
            return

    # التحقق من callback data بتنسيق مختلف
    if "_" in data and len(data.split("_")) >= 3:
        action = data.split("_")[0]

        # إضافة معالجة للأزرار المفقودة
        if action in ["start", "stop", "rename", "delete", "stats", "add"]:
            try:
                parts = data.split("_")
                action_type = parts[0] + "_" + parts[1] if len(parts) > 1 else parts[0]
                extracted_owner_id = int(parts[-2]) if len(parts) >= 2 else None
                extracted_username = parts[-1] if len(parts) >= 1 else None

                if extracted_owner_id and extracted_username:
                    # معالجة مباشرة بدلاً من إعادة الاستدعاء
                    if action_type in ["start_bot", "stop_bot", "add_button", "delete_button", "rename_button", "update_token"]:
                        # تحديث USER_STATES للمستخدم
                        USER_STATES[user_id] = {
                            'state': 'linux0root_authenticated',
                            'owner_id': extracted_owner_id,
                            'username': extracted_username
                        }

                        # معالجة مباشرة للأزرار
                        corrected_data = f"{action_type}_{extracted_owner_id}_{extracted_username}"
                        await handle_callback_query_corrected(query, context, corrected_data)
                        return

            except (ValueError, IndexError) as e:
                print(f"⚠️ خطأ في تحليل callback data: {data} - {e}")

    # معالجة خاصة للأزرار المفقودة
    if data.startswith("logout_linux_"):
        # استخراج owner_id و username من البيانات
        parts = data.split("_")
        if len(parts) >= 4:
            try:
                logout_owner_id = int(parts[2])
                logout_username = parts[3]
                if user_id in USER_STATES:
                    del USER_STATES[user_id]
                await query.edit_message_text("👋 تم تسجيل الخروج من قاعدة linux0root")
                await query.message.reply_text("🏠 **القائمة الرئيسية**", reply_markup=main_menu())
                return
            except (ValueError, IndexError):
                pass

    # فحص إضافي للـ callback data غير المعروف
    if data.startswith("linux_menu_") or "_" in data:
        # محاولة استخراج البيانات
        if data.startswith("linux_menu_"):
            parts = data.replace("linux_menu_", "").split("_")
            if len(parts) >= 2:
                try:
                    extracted_owner_id = int(parts[0])
                    extracted_username = parts[1]
                    # إعادة توجيه للمعالج الصحيح
                    corrected_data = f"linux_menu_{extracted_owner_id}_{extracted_username}"
                    return await handle_callback_query_corrected(query, context, corrected_data)
                except:
                    pass

    # معالجة الخيارات غير المعروفة فقط إذا لم تتطابق مع أي من الشروط السابقة
    print(f"⚠️ callback data غير معروف: {data}")

    # رد تلقائي للمستخدم
    try:
        await query.answer("⚠️ هذا الخيار غير متاح حالياً")
    except:
        pass

async def handle_callback_query_corrected(query, context, data):
    """معالج مساعد للتعامل مع callback data المصحح"""
    # معالجة مباشرة للبيانات المصححة بدلاً من إعادة الاستدعاء
    user_id = query.from_user.id

    # استخراج owner_id و username من البيانات المصححة
    parts = data.split("_")
    if len(parts) >= 3:
        try:
            action_type = parts[0] + "_" + parts[1]
            owner_id = int(parts[2])
            username = parts[3] if len(parts) > 3 else None

            # تحديث USER_STATES للمستخدم
            USER_STATES[user_id] = {
                'state': 'linux0root_authenticated',
                'owner_id': owner_id,
                'username': username
            }

            # معالجة الأزرار المختلفة مباشرة
            if action_type == "start_bot":
                await handle_start_bot_corrected(query, context, owner_id, username)
            elif action_type == "stop_bot":
                await handle_stop_bot_corrected(query, context, owner_id, username)
            elif action_type == "add_button":
                await handle_add_button_logic(query, context, owner_id, username)
            elif action_type == "delete_button":
                await handle_delete_button_step1(query, context, owner_id, username)
            elif action_type == "rename_button":
                await handle_rename_button_step1(query, context, owner_id, username)
            elif action_type == "update_token":
                await handle_update_token_step1(query, context, owner_id, username)
            else:
                await query.answer("⚠️ هذا الخيار غير متاح حالياً")

        except (ValueError, IndexError) as e:
            print(f"⚠️ خطأ في تحليل callback data المصحح: {data} - {e}")
            await query.answer("❌ خطأ في معالجة الطلب")

# ===================== معالجات الأزرار المفقودة =====================

async def handle_buttons_management(query, context, owner_id, username):
    """معالج إدارة الأزرار مع قائمة تفاعلية محسنة"""
    try:
        bot_instance = HostedBot(owner_id, username, "", "")
        buttons = bot_instance.get_buttons()

        if not buttons:
            keyboard = [
                [InlineKeyboardButton("➕ إضافة أول زر", callback_data=f"add_button_{owner_id}_{username}")],
                [InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "📭 **لا توجد أزرار محفوظة**\n\n"
                "💡 ابدأ بإضافة أول زر لبوتك",
                reply_markup=reply_markup
            )
            return

        # إنشاء قائمة الأزرار التفاعلية
        keyboard = []
        valid_buttons_count = 0

        for i, button_data in enumerate(buttons[:10], 1):  # حد أقصى 10 أزرار
            # فحص صحة بيانات الزر
            if not button_data or len(button_data) < 1:
                continue

            button_name = button_data[0]
            if not button_name or not button_name.strip():
                button_name = f"زر_{i}"

            # تنظيف اسم الزر
            button_name = button_name.strip()

            file_type = button_data[2] if len(button_data) > 2 and button_data[2] else "نص"
            clicks = button_data[3] if len(button_data) > 3 and button_data[3] else 0

            # إنشاء نص العرض
            display_text = f"{valid_buttons_count + 1}. {button_name} ({file_type}) - {clicks} نقرة"

            # استخدام تشفير base64 آمن لاسم الزر
            import base64
            encoded_name = base64.b64encode(button_name.encode('utf-8')).decode('ascii')
            safe_callback = f"manage_button_{owner_id}_{username}_{encoded_name}"

            keyboard.append([InlineKeyboardButton(display_text, callback_data=safe_callback)])
            valid_buttons_count += 1

        # إذا لم تكن هناك أزرار صالحة
        if valid_buttons_count == 0:
            keyboard = [
                [InlineKeyboardButton("➕ إضافة أول زر", callback_data=f"add_button_{owner_id}_{username}")],
                [InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "📭 **لا توجد أزرار صالحة**\n\n"
                "💡 ابدأ بإضافة زر جديد",
                reply_markup=reply_markup
            )
            return

        # أزرار التحكم
        keyboard.append([InlineKeyboardButton("➕ إضافة زر جديد", callback_data=f"add_button_{owner_id}_{username}")])
        keyboard.append([InlineKeyboardButton("🗑️ حذف زر", callback_data=f"delete_button_list_{owner_id}_{username}")])
        keyboard.append([InlineKeyboardButton("✏️ تغيير اسم زر", callback_data=f"rename_button_list_{owner_id}_{username}")])
        keyboard.append([InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        total_clicks = sum([btn[3] if len(btn) > 3 and btn[3] else 0 for btn in buttons])

        await query.edit_message_text(
            f"🎛️ **إدارة الأزرار**\n\n"
            f"📊 **الإحصائيات:**\n"
            f"• عدد الأزرار: {valid_buttons_count}\n"
            f"• إجمالي النقرات: {total_clicks}\n\n"
            f"💡 اضغط على أي زر لإدارته:",
            reply_markup=reply_markup
        )

    except Exception as e:
        print(f"❌ خطأ في معالج إدارة الأزرار: {e}")
        import traceback
        print(f"📋 تفاصيل الخطأ: {traceback.format_exc()}")
        keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("❌ حدث خطأ في عرض الأزرار", reply_markup=reply_markup)

async def handle_single_button_management(query, context, owner_id, username, button_name):
    """معالج إدارة زر واحد مع خيارات تفصيلية محسنة"""
    try:
        bot_instance = HostedBot(owner_id, username, "", "")

        # جلب معلومات الزر مع معالجة أفضل للأخطاء
        conn = sqlite3.connect(bot_instance.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT name, file_id, file_type, clicks, created_at FROM buttons WHERE name = ?', (button_name,))
        button_data = cursor.fetchone()
        conn.close()

        if not button_data:
            keyboard = [[InlineKeyboardButton("🔙 العودة للأزرار", callback_data=f"manage_buttons_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("❌ الزر غير موجود", reply_markup=reply_markup)
            return

        name = button_data[0] or "زر بلا اسم"
        file_id = button_data[1]
        file_type = button_data[2] or "نص"
        clicks = button_data[3] or 0
        created_at = button_data[4] if len(button_data) > 4 else "غير محدد"

        # تحديد نوع الملف
        if file_id and file_type:
            if file_type == "photo":
                file_info = "📷 صورة"
            elif file_type == "document":
                file_info = "📄 مستند"
            elif file_type == "video":
                file_info = "🎥 فيديو"
            elif file_type == "audio":
                file_info = "🎵 صوت"
            else:
                file_info = f"📎 {file_type}"
        else:
            file_info = "📝 نص فقط"

        # استخدام base64 لتشفير اسم الزر في callback data
        import base64
        encoded_name = base64.b64encode(name.encode('utf-8')).decode('ascii')

        keyboard = [
            [InlineKeyboardButton("✏️ تغيير الاسم", callback_data=f"start_rename_{owner_id}_{username}_{encoded_name}")],
            [InlineKeyboardButton("🗑️ حذف الزر", callback_data=f"confirm_delete_{owner_id}_{username}_{encoded_name}")],
            [InlineKeyboardButton("🔙 العودة للأزرار", callback_data=f"manage_buttons_{owner_id}_{username}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"🔘 **إدارة الزر: {name}**\n\n"
            f"📋 **المعلومات:**\n"
            f"• النوع: {file_info}\n"
            f"• النقرات: {clicks}\n"
            f"• تاريخ الإنشاء: {created_at}\n\n"
            f"⚙️ **اختر الإجراء المطلوب:**",
            reply_markup=reply_markup
        )

    except Exception as e:
        print(f"❌ خطأ في معالج إدارة الزر الواحد: {e}")
        import traceback
        print(f"📋 تفاصيل الخطأ: {traceback.format_exc()}")
        keyboard = [[InlineKeyboardButton("🔙 العودة للأزرار", callback_data=f"manage_buttons_{owner_id}_{username}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("❌ حدث خطأ في عرض تفاصيل الزر", reply_markup=reply_markup)

async def handle_delete_specific_button(query, context, owner_id, username, button_name):
    """معالج حذف زر محدد"""
    try:
        bot_instance = HostedBot(owner_id, username, "", "")
        success = bot_instance.delete_button(button_name)

        keyboard = [[InlineKeyboardButton("🔙 العودة للأزرار", callback_data=f"manage_buttons_{owner_id}_{username}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if success:
            await query.edit_message_text(
                f"✅ **تم حذف الزر بنجاح**\n\n"
                f"🗑️ **الزر المحذوف:** {button_name}\n\n"
                f"💡 يمكنك إضافة أزرار جديدة من القائمة الرئيسية",
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text(
                f"❌ **فشل في حذف الزر**\n\n"
                f"🔍 **الزر:** {button_name}\n"
                f"💡 قد يكون الزر محذوف مسبقاً",
                reply_markup=reply_markup
            )

    except Exception as e:
        print(f"خطأ في حذف الزر: {e}")
        keyboard = [[InlineKeyboardButton("🔙 العودة للأزرار", callback_data=f"manage_buttons_{owner_id}_{username}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("❌ حدث خطأ في حذف الزر", reply_markup=reply_markup)

async def handle_button_settings(query, context, owner_id, username, button_name):
    """معالج إعدادات الزر التفصيلية"""
    try:
        bot_instance = HostedBot(owner_id, username, "", "")

        # جلب معلومات مفصلة عن الزر
        conn = sqlite3.connect(bot_instance.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM buttons WHERE name = ?', (button_name,))
        button_data = cursor.fetchone()
        conn.close()

        if not button_data:
            await query.answer("❌ الزر غير موجود")
            return

        keyboard = [
            [InlineKeyboardButton("🔙 العودة للزر", callback_data=f"manage_button_{owner_id}_{username}_{button_name}")],
            [InlineKeyboardButton("🔙 العودة للأزرار", callback_data=f"manage_buttons_{owner_id}_{username}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # تفاصيل الزر
        details_text = f"📊 **تفاصيل الزر: {button_name}**\n\n"

        if len(button_data) >= 4:
            details_text += f"🔘 **الاسم:** {button_data[1]}\n"
            details_text += f"📎 **معرف الملف:** {button_data[2] or 'لا يوجد'}\n"
            details_text += f"📂 **نوع الملف:** {button_data[3] or 'نص فقط'}\n"
            details_text += f"👆 **النقرات:** {button_data[5] if len(button_data) > 5 else 0}\n"
            if len(button_data) > 6:
                details_text += f"📅 **تاريخ الإنشاء:** {button_data[6]}\n"

        details_text += f"\n💡 **معلومات النظام:**\n"
        details_text += f"• قاعدة البيانات: linux0root_{owner_id}_{username}.db\n"
        details_text += f"• المالك: {owner_id}\n"

        await query.edit_message_text(details_text, reply_markup=reply_markup)

    except Exception as e:
        print(f"خطأ في معالج إعدادات الزر: {e}")
        keyboard = [[InlineKeyboardButton("🔙 العودة للأزرار", callback_data=f"manage_buttons_{owner_id}_{username}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("❌ حدث خطأ في عرض إعدادات الزر", reply_markup=reply_markup)

async def handle_add_button_logic(query, context, owner_id, username):
    """معالج منطق إضافة زر جديد"""
    user_id = query.from_user.id

    # تحديث حالة المستخدم
    USER_STATES[user_id] = {
        'state': 'linux0root_authenticated',
        'owner_id': owner_id,
        'username': username,
        'waiting_for_button_name': True
    }

    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_main_{owner_id}_{username}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "➕ **إضافة زر جديد**\n\n"
        "📝 **اكتب اسم الزر الجديد:**\n\n"
        "💡 **نصائح:**\n"
        "• استخدم اسماً واضحاً ومميزاً\n"
        "• تجنب الأسماء المكررة\n"
        "• يمكن استخدام الرموز التعبيرية\n\n"
        "❌ للإلغاء اضغط على زر الإلغاء أو اكتب 'إلغاء'",
        reply_markup=reply_markup
    )

async def handle_button_name_input(update, context, state_data, owner_id, username):
    """معالج إدخال اسم الزر الجديد"""
    user_id = update.effective_user.id
    button_name = update.message.text.strip()

    # التحقق من صحة اسم الزر
    if len(button_name) < 1:
        await update.message.reply_text("❌ اسم الزر لا يمكن أن يكون فارغاً")
        return

    if len(button_name) > 50:
        await update.message.reply_text("❌ اسم الزر طويل جداً (الحد الأقصى 50 حرف)")
        return

    try:
        bot_instance = HostedBot(owner_id, username, "", "")

        # التحقق من عدم تكرار الاسم
        existing_buttons = bot_instance.get_buttons()
        existing_names = [btn[0] for btn in existing_buttons]

        if button_name in existing_names:
            await update.message.reply_text(f"❌ الزر '{button_name}' موجود مسبقاً\nاختر اسماً آخر")
            return

        # إضافة الزر المؤقت
        success = bot_instance.add_button(button_name)

        if success:
            # تحديث الحالة
            state_data['waiting_for_button_name'] = False
            state_data['waiting_file_for'] = button_name

            keyboard = [
                [InlineKeyboardButton("✅ حفظ كزر نصي", callback_data=f"confirm_text_button_{owner_id}_{username}")],
                [InlineKeyboardButton("📎 إضافة ملف", callback_data=f"upload_file_button_{owner_id}_{username}")],
                [InlineKeyboardButton("🔗 إضافة رابط", callback_data=f"add_url_button_{owner_id}_{username}")],
                [InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"✅ **تم إنشاء الزر: {button_name}**\n\n"
                f"📋 **اختر نوع المحتوى:**\n\n"
                f"✅ **زر نصي:** إرسال رسالة نصية\n"
                f"📎 **زر ملف:** إرفاق ملف أو صورة\n"
                f"🔗 **زر رابط:** ربط برابط خارجي\n"
                f"❌ **إلغاء:** حذف الزر",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text("❌ فشل في إنشاء الزر")

    except Exception as e:
        print(f"خطأ في معالج اسم الزر: {e}")
        await update.message.reply_text("❌ حدث خطأ في إنشاء الزر")

async def handle_rename_button_step1(query, context, owner_id, username):
    """معالج الخطوة الأولى لتغيير اسم الزر"""
    try:
        bot_instance = HostedBot(owner_id, username, "", "")
        buttons = bot_instance.get_buttons()

        if not buttons:
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "📭 **لا توجد أزرار لتغيير أسمائها**\n\n"
                "💡 أضف أزرار أولاً من القائمة الرئيسية",
                reply_markup=reply_markup
            )
            return

        # إنشاء قائمة الأزرار للاختيار
        keyboard = []
        for button_data in buttons[:10]:  # حد أقصى 10 أزرار
            button_name = button_data[0]
            keyboard.append([InlineKeyboardButton(
                f"✏️ {button_name}",
                callback_data=f"rename_select_{owner_id}_{username}_{button_name}"
            )])

        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_rename_{owner_id}_{username}")])
        keyboard.append([InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "✏️ **تغيير اسم زر**\n\n"
            "📋 **اختر الزر الذي تريد تغيير اسمه:**",
            reply_markup=reply_markup
        )

    except Exception as e:
        print(f"خطأ في معالج تغيير اسم الزر - الخطوة 1: {e}")
        keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("❌ حدث خطأ في عرض الأزرار", reply_markup=reply_markup)

async def handle_rename_button_step2(update, context, state_data, owner_id, username):
    """معالج الخطوة الثانية لتغيير اسم الزر"""
    user_id = update.effective_user.id

    if state_data.get('waiting_for_rename_new'):
        # إدخال الاسم الجديد
        new_name = update.message.text.strip()
        old_name = state_data.get('rename_old_name')

        if not old_name:
            await update.message.reply_text("❌ خطأ في النظام، حاول مرة أخرى")
            return

        if len(new_name) < 1:
            await update.message.reply_text("❌ الاسم الجديد لا يمكن أن يكون فارغاً")
            return

        if len(new_name) > 50:
            await update.message.reply_text("❌ الاسم الجديد طويل جداً (الحد الأقصى 50 حرف)")
            return

        try:
            bot_instance = HostedBot(owner_id, username, "", "")
            success = bot_instance.rename_button(old_name, new_name)

            # مسح الحالة
            state_data.pop('waiting_for_rename_new', None)
            state_data.pop('rename_old_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            if success:
                await update.message.reply_text(
                    f"✅ **تم تغيير اسم الزر بنجاح**\n\n"
                    f"🔄 **من:** {old_name}\n"
                    f"➡️ **إلى:** {new_name}\n\n"
                    f"💡 الآن يمكن للمستخدمين الوصول للزر بالاسم الجديد",
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text(
                    f"❌ **فشل في تغيير اسم الزر**\n\n"
                    f"🔍 **الأسباب المحتملة:**\n"
                    f"• الاسم الجديد مستخدم مسبقاً\n"
                    f"• الزر القديم غير موجود\n"
                    f"• خطأ في قاعدة البيانات",
                    reply_markup=reply_markup
                )

        except Exception as e:
            print(f"خطأ في تغيير اسم الزر: {e}")
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("❌ حدث خطأ في تغيير اسم الزر", reply_markup=reply_markup)

async def handle_delete_button_step1(query, context, owner_id, username):
    """معالج الخطوة الأولى لحذف زر"""
    user_id = query.from_user.id

    # تفعيل وضع انتظار اسم الزر للحذف
    USER_STATES[user_id] = {
        'state': 'linux0root_authenticated',
        'owner_id': owner_id,
        'username': username,
        'waiting_for_delete_name': True
    }

    keyboard = [
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_delete_{owner_id}_{username}")],
        [InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "🗑️ **حذف زر**\n\n"
        "📝 **اكتب اسم الزر الذي تريد حذفه:**\n\n"
        "⚠️ **تحذير:** هذا الإجراء لا يمكن التراجع عنه\n"
        "❌ للإلغاء اضغط على زر الإلغاء أو اكتب 'إلغاء'",
        reply_markup=reply_markup
    )

async def handle_delete_button_step2(update, context, state_data, owner_id, username):
    """معالج الخطوة الثانية لحذف زر"""
    button_name = update.message.text.strip()

    try:
        bot_instance = HostedBot(owner_id, username, "", "")
        success = bot_instance.delete_button(button_name)

        # مسح الحالة
        state_data.pop('waiting_for_delete_name', None)

        keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if success:
            await update.message.reply_text(
                f"✅ **تم حذف الزر بنجاح**\n\n"
                f"🗑️ **الزر المحذوف:** {button_name}\n\n"
                f"💡 لن يعود المستخدمون قادرين على الوصول لهذا الزر",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                f"❌ **فشل في حذف الزر**\n\n"
                f"🔍 **الزر:** {button_name}\n"
                f"💡 تأكد من صحة اسم الزر",
                reply_markup=reply_markup
            )

    except Exception as e:
        print(f"خطأ في حذف الزر: {e}")
        keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("❌ حدث خطأ في حذف الزر", reply_markup=reply_markup)

async def handle_update_token_step1(query, context, owner_id, username):
    """معالج الخطوة الأولى لتحديث التوكين"""
    user_id = query.from_user.id

    # تفعيل وضع انتظار التوكين الجديد
    USER_STATES[user_id] = {
        'state': 'linux0root_authenticated',
        'owner_id': owner_id,
        'username': username,
        'waiting_for_new_token': True
    }

    keyboard = [
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_token_update_{owner_id}_{username}")],
        [InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "🔧 **تحديث توكين البوت**\n\n"
        "🔑 **أدخل التوكين الجديد:**\n\n"
        "📋 **خطوات الحصول على التوكين:**\n"
        "1. اذهب إلى @BotFather\n"
        "2. أرسل /newbot أو /mybots\n"
        "3. اختر بوتك واحصل على التوكين\n"
        "4. انسخ التوكين والصقه هنا\n\n"
        "⚠️ **التوكين يجب أن يكون بالشكل:**\n"
        "`1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`\n\n"
        "❌ للإلغاء اضغط على زر الإلغاء",
        reply_markup=reply_markup
    )

async def handle_update_token_step2(update, context, state_data, owner_id, username):
    """معالج الخطوة الثانية لتحديث التوكين"""
    new_token = update.message.text.strip()

    # التحقق من صحة التوكين
    if not new_token or ':' not in new_token or len(new_token) < 30:
        await update.message.reply_text(
            "❌ **توكين غير صالح**\n\n"
            "🔍 **التوكين يجب أن يكون:**\n"
            "• يحتوي على : في المنتصف\n"
            "• طوله أكثر من 30 حرف\n"
            "• بالشكل: `1234567890:ABCdefGHI...`\n\n"
            "🔄 أرسل التوكين الصحيح أو اكتب 'إلغاء'"
        )
        return

    try:
        bot_instance = HostedBot(owner_id, username, "", "")
        success = bot_instance.update_bot_token(new_token)

        # مسح الحالة
        state_data.pop('waiting_for_new_token', None)

        keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if success:
            await update.message.reply_text(
                f"✅ **تم تحديث التوكين بنجاح**\n\n"
                f"🔑 **التوكين الجديد:** {new_token[:20]}...\n\n"
                f"🚀 **يمكنك الآن تشغيل البوت بالتوكين الجديد**\n"
                f"💡 استخدم زر 'تشغيل البوت' من القائمة الرئيسية",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                f"❌ **فشل في تحديث التوكين**\n\n"
                f"🔍 **الأسباب المحتملة:**\n"
                f"• التوكين غير صحيح\n"
                f"• خطأ في قاعدة البيانات\n"
                f"• البوت غير مفعل من @BotFather\n\n"
                f"🔄 تأكد من التوكين وحاول مرة أخرى",
                reply_markup=reply_markup
            )

    except Exception as e:
        print(f"خطأ في تحديث التوكين: {e}")
        keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("❌ حدث خطأ في تحديث التوكين", reply_markup=reply_markup)

async def handle_cancel_token_update(query, context, owner_id, username):
    """معالج إلغاء تحديث التوكين"""
    user_id = query.from_user.id

    # إزالة حالة انتظار التوكين
    if user_id in USER_STATES:
        state_data = USER_STATES[user_id]
        state_data.pop('waiting_for_new_token', None)

    keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "❌ **تم إلغاء تحديث التوكين**\n\n"
        "لم يتم حفظ أي تغييرات على التوكين",
        reply_markup=reply_markup
    )

async def handle_delete_button_list(query, context, owner_id, username):
    """عرض قائمة الأزرار للحذف"""
    try:
        bot_instance = HostedBot(owner_id, username, "", "")
        buttons = bot_instance.get_buttons()

        if not buttons:
            keyboard = [[InlineKeyboardButton("🔙 العودة لإدارة الأزرار", callback_data=f"manage_buttons_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "📭 **لا توجد أزرار للحذف**\n\n"
                "💡 أضف أزرار أولاً من القائمة",
                reply_markup=reply_markup
            )
            return

        keyboard = []
        for button_data in buttons[:10]:
            button_name = button_data[0]
            if button_name and button_name.strip():
                import base64
                encoded_name = base64.b64encode(button_name.encode('utf-8')).decode('ascii')
                keyboard.append([InlineKeyboardButton(f"🗑️ حذف: {button_name}", callback_data=f"confirm_delete_{owner_id}_{username}_{encoded_name}")])

        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data=f"manage_buttons_{owner_id}_{username}")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "🗑️ **حذف زر**\n\n"
            "⚠️ **تحذير:** هذا الإجراء لا يمكن التراجع عنه\n\n"
            "📋 **اختر الزر المراد حذفه:**",
            reply_markup=reply_markup
        )

    except Exception as e:
        print(f"خطأ في عرض قائمة حذف الأزرار: {e}")
        keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("❌ حدث خطأ في عرض قائمة الحذف", reply_markup=reply_markup)

async def handle_rename_button_list(query, context, owner_id, username):
    """عرض قائمة الأزرار لتغيير الاسم"""
    try:
        bot_instance = HostedBot(owner_id, username, "", "")
        buttons = bot_instance.get_buttons()

        if not buttons:
            keyboard = [[InlineKeyboardButton("🔙 العودة لإدارة الأزرار", callback_data=f"manage_buttons_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "📭 **لا توجد أزرار لتغيير الاسم**\n\n"
                "💡 أضف أزرار أولاً من القائمة",
                reply_markup=reply_markup
            )
            return

        keyboard = []
        for button_data in buttons[:10]:
            button_name = button_data[0]
            if button_name and button_name.strip():
                import base64
                encoded_name = base64.b64encode(button_name.encode('utf-8')).decode('ascii')
                keyboard.append([InlineKeyboardButton(f"✏️ تعديل: {button_name}", callback_data=f"start_rename_{owner_id}_{username}_{encoded_name}")])

        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data=f"manage_buttons_{owner_id}_{username}")])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "✏️ **تغيير اسم زر**\n\n"
            "📋 **اختر الزر المراد تغيير اسمه:**",
            reply_markup=reply_markup
        )

    except Exception as e:
        print(f"خطأ في عرض قائمة تغيير الأسماء: {e}")
        keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("❌ حدث خطأ في عرض قائمة التعديل", reply_markup=reply_markup)

async def handle_start_bot_corrected(query, context, owner_id, username):
    """معالج تشغيل البوت المصحح"""
    try:
        await query.edit_message_text("🔄 جاري تشغيل البوت... يرجى الانتظار")

        # التحقق من وجود توكين صالح
        conn = sqlite3.connect(MAIN_DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT bot_token FROM main_users WHERE tg_id = ? AND username = ?', (owner_id, username))
        result = cursor.fetchone()
        conn.close()

        if not result or not result[0]:
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **لا يوجد توكين مسجل**\n\n"
                "🔧 **يرجى تحديث التوكين أولاً من القائمة**",
                reply_markup=reply_markup
            )
            return

        bot_token = result[0].strip()

        # التحقق من صحة التوكين
        if not bot_token or len(bot_token) < 30 or ':' not in bot_token:
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "❌ **التوكين غير صالح**\n\n"
                "🔧 **يرجى تحديث التوكين من القائمة**",
                reply_markup=reply_markup
            )
            return

        # استخدام مدير الاستضافة لتشغيل البوت
        success = hosting_manager.start_user_bot(owner_id, username, bot_token)

        keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if success:
            # تحديث حالة البوت في قاعدة البيانات
            bot_instance = HostedBot(owner_id, username, "", bot_token)
            bot_instance.set_bot_status("running")

            await query.edit_message_text(
                "🚀 **تم تشغيل البوت بنجاح!**\n\n"
                f"🤖 **اسم البوت:** {username}\n"
                f"🔗 **الرابط:** https://t.me/{username}bot\n"
                f"✅ **الحالة:** يعمل الآن على Replit\n\n"
                f"💡 **يمكنك الآن استخدام البوت من خلال الرابط أعلاه**",
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text(
                "❌ **فشل في تشغيل البوت**\n\n"
                f"🔍 **الأسباب المحتملة:**\n"
                f"• التوكين غير صحيح أو منتهي الصلاحية\n"
                f"• البوت غير مفعل من @BotFather\n"
                f"• مشكلة في الاتصال بخوادم تليجرام\n\n"
                f"💡 **الحل:**\n"
                f"• تحديث التوكين من القائمة\n"
                f"• التأكد من تفعيل البوت عند @BotFather\n"
                f"• المحاولة مرة أخرى بعد دقائق",
                reply_markup=reply_markup
            )
    except Exception as e:
        print(f"❌ خطأ في تشغيل البوت: {e}")
        keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "❌ **حدث خطأ تقني في تشغيل البوت**\n\n"
            f"🔧 **يرجى المحاولة مرة أخرى أو تحديث التوكين**",
            reply_markup=reply_markup
        )

async def handle_stop_bot_corrected(query, context, owner_id, username):
    """معالج إيقاف البوت المصحح"""
    try:
        await query.edit_message_text("⏹️ جاري إيقاف البوت...")

        success = await hosting_manager.stop_user_bot(owner_id, username)

        keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if success:
            bot_instance = HostedBot(owner_id, username, "", "")
            bot_instance.set_bot_status("stopped")

            await query.edit_message_text(
                "⏹️ **تم إيقاف البوت بنجاح**\n\n"
                f"🤖 **البوت:** {username}\n"
                f"✅ **الحالة:** متوقف\n\n"
                f"💡 **يمكنك تشغيله مرة أخرى من القائمة**",
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text(
                "ℹ️ **البوت متوقف مسبقاً**\n\n"
                f"🤖 **البوت:** {username}\n"
                f"📊 **الحالة:** متوقف",
                reply_markup=reply_markup
            )
    except Exception as e:
        print(f"خطأ في إيقاف البوت: {e}")
        keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "❌ **حدث خطأ في إيقاف البوت**\n\n"
            f"🔧 **حاول مرة أخرى**",
            reply_markup=reply_markup
        )

async def handle_confirm_delete_button(query, context, owner_id, username, button_name):
    """تأكيد حذف الزر"""
    try:
        bot_instance = HostedBot(owner_id, username, "", "")
        success = bot_instance.delete_button(button_name)

        keyboard = [[InlineKeyboardButton("🔙 العودة لإدارة الأزرار", callback_data=f"manage_buttons_{owner_id}_{username}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if success:
            await query.edit_message_text(
                f"✅ **تم حذف الزر بنجاح**\n\n"
                f"🗑️ **الزر المحذوف:** {button_name}\n\n"
                f"💡 لن يعود المستخدمون قادرين على الوصول لهذا الزر",
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text(
                f"❌ **فشل في حذف الزر**\n\n"
                f"🔍 **الزر:** {button_name}\n"
                f"💡 قد يكون الزر محذوف مسبقاً",
                reply_markup=reply_markup
            )

    except Exception as e:
        print(f"خطأ في حذف الزر: {e}")
        keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("❌ حدث خطأ في حذف الزر", reply_markup=reply_markup)

async def handle_start_rename_button(query, context, owner_id, username, button_name):
    """بدء عملية تغيير اسم الزر"""
    user_id = query.from_user.id

    # تحديث حالة المستخدم
    USER_STATES[user_id] = {
        'state': 'linux0root_authenticated',
        'owner_id': owner_id,
        'username': username,
        'waiting_for_rename_new': True,
        'rename_old_name': button_name
    }

    keyboard = [
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_rename_{owner_id}_{username}")],
        [InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"manage_buttons_{owner_id}_{username}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"✏️ **تغيير اسم الزر**\n\n"
        f"🔘 **الزر الحالي:** {button_name}\n\n"
        f"📝 **اكتب الاسم الجديد للزر:**\n\n"
        f"💡 **تأكد من اختيار اسم مميز وواضح**\n"
        f"❌ للإلغاء اضغط على زر الإلغاء أو اكتب 'إلغاء'",
        reply_markup=reply_markup
    )


# ===================== معالج الرسائل النصية المحدث =====================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الرسائل المحدث"""
    user = update.effective_user
    text = update.message.text
    user_id = user.id

    # التحقق من كلمات الإلغاء
    if text.strip().lower() in CANCEL_WORDS:
        # إلغاء جميع العمليات المؤقتة
        BOT_FACTORY_DATA.pop(user_id, None)
        USER_STATES.pop(user_id, None)
        await update.message.reply_text("✅ تم إلغاء العملية", reply_markup=main_menu())
        return

    # معالجة أمر linux0root المباشر
    if text.lower() == "linux0root":
        await handle_linux0root_command(update, context)
        return

    # معالجة أزرار القائمة الرئيسية
    if text == "🔧 صانع البوتات":
        await handle_bot_maker(update, context)
        return

    # معالجة حالات التفاعل
    if user_id in USER_STATES:
        state_data = USER_STATES[user_id]
        state = state_data.get('state')

        if state == 'waiting_username_linux0root':
            await handle_user_state(update, context) # معالجة إدخال اسم المستخدم
        elif state == 'waiting_password_linux0root':
            await handle_user_state(update, context) # معالجة إدخال كلمة المرور
        elif state == 'linux0root_authenticated':
            # إذا كان المستخدم في سياق linux0root، يتم تمرير الرسالة للمعالجة المخصصة
            await handle_linux0root_management(update, context, state_data)
        elif state_data.get('waiting_for_button_name'):
            # إذا كان ينتظر اسم زر
            await handle_button_name_input(update, context, state_data, state_data['owner_id'], state_data['username'])
        elif state_data.get('waiting_for_rename_old') or state_data.get('waiting_for_rename_new'):
            # إذا كان ينتظر اسم الزر القديم أو الجديد لتغييره
            await handle_rename_button_step2(update, context, state_data, state_data['owner_id'], state_data['username'])
        elif state_data.get('waiting_for_delete_name'):
            # إذا كان ينتظر اسم الزر المراد حذفه
            await handle_delete_button_step2(update, context, state_data, state_data['owner_id'], state_data['username'])
        elif state_data.get('waiting_for_new_token'):
            # إذا كان ينتظر التوكين الجديد
            await handle_update_token_step2(update, context, state_data, state_data['owner_id'], state_data['username'])
        else:
            # حالة غير معروفة ضمن USER_STATES
            await update.message.reply_text("❌ حدث خطأ في حالة التفاعل")
        return

    if user_id in BOT_FACTORY_DATA:
        await handle_bot_factory_interaction(update, context)
        return

    # معالجة الأزرار الأخرى (يمكن إضافة المزيد هنا)
    if text == "🤖 المجيب الذكي":
        await update.message.reply_text(
            "🤖 **المجيب الذكي**\n\n"
            "اكتب سؤالك وسأجيب عليه باستخدام الذكاء الاصطناعي"
        )
    elif text == "📊 الإحصائيات":
        await update.message.reply_text(
            "📊 **إحصائيات البوت**\n\n"
            "• المستخدمين: يتم الحساب...\n"
            "• البوتات المستضافة: يتم الحساب...\n"
            "• الرسائل المعالجة: يتم الحساب..."
        )
    elif text == "ℹ️ معلومات البوت":
        await update.message.reply_text(
            f"ℹ️ **معلومات البوت**\n\n"
            f"🔧 **صانع البوتات المتقدم**\n"
            f"• نظام قواعد بيانات منفصلة\n"
            f"• تشفير وحماية متقدمة\n"
            f"• إدارة مركزية للمستخدمين\n\n"
            f"{COPYRIGHT_LINE}"
        )
    else:
        # إذا لم توجد حالة خاصة، رد عام
        await update.message.reply_text("🤖 استخدم الأزرار أو /help للمساعدة")

async def handle_user_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة حالات المستخدم"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    state_data = USER_STATES[user_id]
    state = state_data['state']

    if state == 'waiting_username_linux0root':
        # التحقق من اسم المستخدم
        if len(text) < 3:
            await update.message.reply_text(
                "❌ **اسم المستخدم قصير جداً**\n\n"
                "يجب أن يكون على الأقل 3 أحرف\n"
                "🔄 أرسل اسم مستخدم آخر أو اكتب 'إلغاء'"
            )
            return
        if ' ' in text:
            await update.message.reply_text(
                "❌ **اسم المستخدم يحتوي على مسافات**\n\n"
                "يجب أن يكون بدون مسافات\n"
                "🔄 أرسل اسم مستخدم آخر أو اكتب 'إلغاء'"
            )
            return

        # التحقق من أن اسم المستخدم لا يحتوي على أحرف غير مسموحة (يمكن تعديل هذا)
        if not re.match(r'^[a-zA-Z0-9_]+$', text):
             await update.message.reply_text(
                "❌ **اسم المستخدم يحتوي على أحرف غير مسموحة**\n\n"
                "يمكن استخدام الأحرف الإنجليزية والأرقام والشرطة السفلية فقط\n"
                "🔄 أرسل اسم مستخدم آخر أو اكتب 'إلغاء'"
            )
             return

        # حفظ اسم المستخدم والانتقال لكلمة المرور
        state_data['username'] = text
        state_data['state'] = 'waiting_password_linux0root'
        await update.message.reply_text(
            f"✅ **اسم المستخدم:** {text}\n\n"
            "🔒 **أدخل كلمة المرور:**"
        )

    elif state == 'waiting_password_linux0root':
        username = state_data['username']
        password = text

        # التحقق من قوة كلمة المرور
        if len(password) < 6:
            await update.message.reply_text(
                "❌ **كلمة المرور ضعيفة**\n\n"
                "يجب أن تكون على الأقل 6 أحرف\n"
                "🔄 أرسل كلمة مرور أقوى أو اكتب 'إلغاء'"
            )
            return

        # التحقق من تسجيل الدخول
        result = verify_user_login(username, password)

        if result is None:
            await update.message.reply_text("❌ اسم المستخدم أو كلمة المرور غير صحيحة")
            return
        elif result == -1:
            await update.message.reply_text("🚫 حسابك محظور من النظام")
            return
        elif result == -2:
            await update.message.reply_text("⏳ حسابك محظور مؤقتاً")
            return

        # تسجيل دخول ناجح
        owner_id = result
        state_data['owner_id'] = owner_id
        state_data['username'] = username
        state_data['state'] = 'linux0root_authenticated'

        # إنشاء جلسة مؤقتة
        create_temp_session(user_id, username, owner_id)

        # إنشاء البوت وقاعدة البيانات إذا لم تكن موجودة
        bot_instance = HostedBot(owner_id, username, password)
        stats = bot_instance.get_stats()

        keyboard = [
            [InlineKeyboardButton("➕ إضافة زر", callback_data=f"add_button_{owner_id}_{username}")],
            [InlineKeyboardButton("🎛️ إدارة الأزرار", callback_data=f"manage_buttons_{owner_id}_{username}")],
            [InlineKeyboardButton("📊 إحصائيات", callback_data=f"stats_{owner_id}_{username}")],
            [InlineKeyboardButton("✏️ تغيير اسم زر", callback_data=f"rename_button_{owner_id}_{username}")],
            [InlineKeyboardButton("🔧 تحديث التوكين", callback_data=f"update_token_{owner_id}_{username}")],
            [InlineKeyboardButton("🚀 تشغيل البوت", callback_data=f"start_bot_{owner_id}_{username}")],
            [InlineKeyboardButton("⏹️ إيقاف البوت", callback_data=f"stop_bot_{owner_id}_{username}")],
            [InlineKeyboardButton("🚪 تسجيل الخروج", callback_data=f"logout_linux_{owner_id}_{username}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"🔐 **مرحباً بك في قاعدة linux0root**\n\n"
            f"👤 **المستخدم:** {username}\n"
            f"🗃️ **قاعدة البيانات:** linux0root_{owner_id}_{username}.db\n\n"
            f"📊 **الإحصائيات:**\n"
            f"• الأزرار: {stats['total_buttons']}\n"
            f"• النقرات: {stats['total_clicks']}\n"
            f"• حالة البوت: {bot_instance.get_bot_status()}\n\n"
            f"⚙️ **الأوامر المتاحة:**\n"
            f"• إضافة زر: اكتب اسم الزر\n"
            f"• تغيير اسم [القديم] إلى [الجديد]\n"
            f"• إحصائيات: إحصائيات\n"
            f"• خروج: خروج",
            reply_markup=reply_markup
        )

    elif state == 'linux0root_authenticated':
        await handle_linux0root_management(update, context)

async def handle_linux0root_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أمر linux0root المباشر"""
    user_id = update.effective_user.id

    USER_STATES[user_id] = {'state': 'waiting_username_linux0root'}

    await update.message.reply_text(
        "🔐 **الوصول لقاعدة linux0root**\n\n"
        "👤 **أدخل اسم المستخدم:**\n"
        "💡 استخدم اسم المستخدم الذي أنشأت به بوتك\n"
        "❌ للإلغاء اكتب: إلغاء"
    )

async def handle_linux0root_management(update: Update, context: ContextTypes.DEFAULT_TYPE, state_data):
    """معالجة أوامر قاعدة linux0root المتقدمة"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    username = state_data.get('username')
    owner_id = state_data['owner_id']

    bot_instance = HostedBot(owner_id, username, "", "") # password not needed here

    # التحقق من حالات انتظار خاصة أولاً
    if state_data.get('waiting_for_new_token'):
        await handle_update_token_step2(update, context, state_data, owner_id, username)
        return

    # معالجة محتوى الزر النصي
    if state_data.get('waiting_text_content'):
        button_name = state_data.get('waiting_file_for')
        text_content = text

        bot_instance = HostedBot(owner_id, username, "", "")
        success = bot_instance.add_button(button_name, button_type="text", content=text_content)

        if success:
            # مسح الحالة
            state_data.pop('waiting_text_content', None)
            state_data.pop('waiting_file_for', None)
            state_data['waiting_for_button_name'] = False

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"✅ **تم إنشاء الزر النصي بنجاح!**\n\n"
                f"🔘 **اسم الزر:** {button_name}\n"
                f"📝 **المحتوى:** {text_content[:50]}{'...' if len(text_content) > 50 else ''}\n\n"
                f"🤖 **الزر متاح الآن في بوتك**",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text("❌ فشل في حفظ الزر النصي")
        return

    # معالجة رابط الزر
    if state_data.get('waiting_url_content'):
        button_name = state_data.get('waiting_file_for')
        url = text.strip()

        # التحقق من صحة الرابط
        if not (url.startswith('http://') or url.startswith('https://')):
            await update.message.reply_text(
                "❌ **رابط غير صالح**\n\n"
                "يجب أن يبدأ الرابط بـ http:// أو https://\n"
                "🔄 أرسل الرابط الصحيح أو اكتب 'إلغاء'"
            )
            return

        bot_instance = HostedBot(owner_id, username, "", "")
        success = bot_instance.add_button(button_name, button_type="url", url=url)

        if success:
            # مسح الحالة
            state_data.pop('waiting_url_content', None)
            state_data.pop('waiting_file_for', None)
            state_data['waiting_for_button_name'] = False

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"✅ **تم إنشاء زر الرابط بنجاح!**\n\n"
                f"🔘 **اسم الزر:** {button_name}\n"
                f"🔗 **الرابط:** {url}\n\n"
                f"🤖 **الزر متاح الآن في بوتك**",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text("❌ فشل في حفظ زر الرابط")
        return

    text_lower = text.lower()

    if text_lower == "خروج":
        USER_STATES.pop(user_id, None)
        await update.message.reply_text("👋 تم تسجيل الخروج من قاعدة linux0root", reply_markup=main_menu())

    elif text_lower == "إحصائيات":
        stats = bot_instance.get_stats()
        buttons = bot_instance.get_buttons()

        buttons_text = "📋 **قائمة الأزرار:**\n\n"
        if buttons:
            for i, btn in enumerate(buttons, 1):
                file_info = f" ({btn[2]})" if btn[1] else " (نص فقط)"
                buttons_text += f"{i}. **{btn[0]}**{file_info} - {btn[3]} نقرة\n"
        else:
            buttons_text = "📭 لا توجد أزرار محفوظة"

        keyboard = [
            [InlineKeyboardButton("🔄 تحديث الإحصائيات", callback_data="refresh_stats")],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data=f"linux_menu_{owner_id}_{username}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"📊 **إحصائيات قاعدة البيانات:**\n\n"
            f"🔘 **عدد الأزرار:** {stats['total_buttons']}\n"
            f"👆 **مجموع النقرات:** {stats['total_clicks']}\n"
            f"🤖 **حالة البوت:** {bot_instance.bot_status}\n\n"
            f"{buttons_text}",
            reply_markup=reply_markup
        )

    elif text_lower.startswith("احذف "):
        button_name = text[5:].strip()
        if bot_instance.delete_button(button_name):
            await update.message.reply_text(f"✅ تم حذف الزر: {button_name}")
        else:
            await update.message.reply_text(f"❌ الزر '{button_name}' غير موجود")

    elif text_lower.startswith("تغيير اسم "):
        # تغيير اسم زر
        parts = text[10:].split(" إلى ")
        if len(parts) == 2:
            old_name, new_name = parts[0].strip(), parts[1].strip()
            if bot_instance.rename_button(old_name, new_name):
                await update.message.reply_text(f"✅ تم تغيير اسم الزر من '{old_name}' إلى '{new_name}'")
            else:
                await update.message.reply_text(f"❌ فشل في تغيير اسم الزر")
        else:
            await update.message.reply_text("❌ الصيغة الصحيحة: تغيير اسم [الاسم القديم] إلى [الاسم الجديد]")

    elif text_lower == "قائمة الأوامر":
        await update.message.reply_text(
            "⚙️ **قائمة الأوامر المتاحة:**\n\n"
            "📝 **إدارة الأزرار:**\n"
            "• `[اسم الزر]` - إضافة زر جديد\n"
            "• `تغيير اسم [القديم] إلى [الجديد]` - تغيير اسم زر\n\n"
            "📊 **الإحصائيات:**\n"
            "• `إحصائيات` - عرض الإحصائيات\n"
            "• `قائمة الأزرار` - عرض جميع الأزرار\n\n"
            "🤖 **إدارة البوت:**\n"
            "• `تشغيل البوت` - تشغيل البوت\n"
            "• `إيقاف البوت` - إيقاف البوت\n"
            "• `حالة البوت` - فحص حالة البوت\n"
            "• `تحديث التوكين` - تحديث توكين البوت\n\n"
            "🚪 **أخرى:**\n"
            "• `قائمة الأوامر` - عرض هذه القائمة\n"
            "• `خروج` - تسجيل الخروج"
        )

    elif text_lower == "قائمة الأزرار":
        buttons = bot_instance.get_buttons()
        if buttons:
            buttons_text = "📋 **قائمة الأزرار:**\n\n"
            for i, btn in enumerate(buttons, 1):
                file_info = f" ({btn[2]})" if btn[1] else " (نص فقط)"
                buttons_text += f"{i}. **{btn[0]}**{file_info} - {btn[3]} نقرة\n"
        else:
            buttons_text = "📭 لا توجد أزرار محفوظة"

        await update.message.reply_text(buttons_text)

    elif text_lower == "تشغيل البوت":
        # تشغيل البوت الخاص بالمستخدم
        try:
            # الحصول على التوكين من قاعدة البيانات
            conn = sqlite3.connect(MAIN_DB_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT bot_token FROM main_users WHERE tg_id = ? AND username = ?', (owner_id, username))
            result = cursor.fetchone()
            conn.close()

            if not result or not result[0]:
                await update.message.reply_text(
                    "❌ **لا يوجد توكين مسجل**\n\n"
                    "🔧 **يرجى تحديث التوكين أولاً:**\n"
                    "اكتب: `تحديث التوكين`"
                )
                return

            bot_token = result[0].strip()

            # محاولة تشغيل البوت
            success = hosting_manager.start_user_bot(owner_id, username, bot_token)

            if success:
                bot_instance.set_bot_status("running")
                await update.message.reply_text(
                    "🚀 **تم تشغيل البوت بنجاح!**\n\n"
                    f"🤖 **اسم البوت:** {username}\n"
                    f"🔗 **الرابط:** https://t.me/{username}bot\n"
                    f"✅ **الحالة:** يعمل الآن على Replit"
                )
            else:
                await update.message.reply_text(
                    "❌ **فشل في تشغيل البوت**\n\n"
                    "🔍 **تحقق من:**\n"
                    "• صحة التوكين\n"
                    "• تفعيل البوت من @BotFather\n\n"
                    "💡 **حاول تحديث التوكين**"
                )
        except Exception as e:
            print(f"خطأ في تشغيل البوت: {e}")
            await update.message.reply_text("❌ حدث خطأ في تشغيل البوت")

    elif text_lower == "إيقاف البوت":
        # إيقاف البوت
        try:
            success = await hosting_manager.stop_user_bot(owner_id, username)

            if success:
                bot_instance.set_bot_status("stopped")
                await update.message.reply_text(
                    "⏹️ **تم إيقاف البوت بنجاح**\n\n"
                    f"🤖 **البوت:** {username}\n"
                    f"✅ **الحالة:** متوقف"
                )
            else:
                await update.message.reply_text(
                    "ℹ️ **البوت متوقف مسبقاً**\n\n"
                    f"🤖 **البوت:** {username}"
                )
        except Exception as e:
            print(f"خطأ في إيقاف البوت: {e}")
            await update.message.reply_text("❌ حدث خطأ في إيقاف البوت")

    elif text_lower == "حالة البوت":
        try:
            # الحصول على الحالة الفعلية من مدير الاستضافة
            actual_status = hosting_manager.get_bot_status(owner_id, username)

            # تحديث حالة البوت في قاعدة البيانات
            bot_instance.set_bot_status(actual_status)

            if actual_status == "running":
                status_text = "🟢 يعمل"
                status_emoji = "✅"
                status_details = "البوت نشط ويستجيب للرسائل"
            elif actual_status == "stopped":
                status_text = "🔴 متوقف"
                status_emoji = "⏹️"
                status_details = "البوت غير نشط"
            elif actual_status == "error":
                status_text = "🟡 خطأ"
                status_emoji = "⚠️"
                status_details = "هناك مشكلة في البوت"
            else:
                status_text = "🔴 غير معروف"
                status_emoji = "❓"
                status_details = "حالة غير محددة"

            await update.message.reply_text(
                f"🤖 **حالة البوت {username}:**\n\n"
                f"{status_emoji} **الحالة:** {status_text}\n"
                f"📋 **التفاصيل:** {status_details}\n"
                f"🔗 **الرابط:** https://t.me/{username}bot"
            )
        except Exception as e:
            print(f"خطأ في فحص حالة البوت: {e}")
            await update.message.reply_text("❌ حدث خطأ في فحص حالة البوت")

    # التحقق من أن النص يبدو كتوكين بوت قبل إضافته كزر
    elif ':' in text and len(text) > 30 and text.count(':') == 1:
        # يبدو كتوكين بوت، لكن لم يتم طلب تحديث التوكين
        await update.message.reply_text(
            "🤖 **يبدو أنك تحاول إدخال توكين بوت**\n\n"
            "📌 **للتحديث:**\n"
            "• استخدم زر 'تحديث التوكين' من القائمة\n"
            "• أو اكتب الأمر: `تحديث التوكين`\n\n"
            "❌ **لم يتم حفظ التوكين كزر**"
        )

    elif text_lower == "تحديث التوكين":
        # تفعيل وضع تحديث التوكين
        state_data['waiting_for_new_token'] = True
        await update.message.reply_text(
            "🔧 **تحديث توكين البوت**\n\n"
            "• أدخل التوكين الجديد لبوتك.\n"
            "• ستحتاج إلى الحصول عليه من @BotFather.\n"
            "• هذا التوكين ضروري لتشغيل بوتك الخاص.\n\n"
            "❌ للإلغاء اكتب: إلغاء"
        )

    elif text_lower == "مسح التوكينات":
        # حذف أي أزرار تحتوي على توكينات
        buttons = bot_instance.get_buttons()
        deleted_count = 0
        for btn in buttons:
            button_name = btn[0]
            # التحقق من أن الزر يحتوي على توكين
            if ':' in button_name and len(button_name) > 30 and button_name.count(':') == 1:
                if bot_instance.delete_button(button_name):
                    deleted_count += 1

        if deleted_count > 0:
            await update.message.reply_text(f"✅ تم حذف {deleted_count} توكين تم حفظه كزر بالخطأ")
        else:
            await update.message.reply_text("ℹ️ لم يتم العثور على توكينات محفوظة كأزرار")

    else:
        # إضافة زر جديد
        button_name = update.message.text.strip()
        if bot_instance.add_button(button_name):
            state_data['waiting_for_button_name'] = True
            state_data['waiting_file_for'] = button_name

            # إنشاء أزرار للخيارات مع خيارات متقدمة
            keyboard = [
                [InlineKeyboardButton("✅ حفظ الزر (نصي)", callback_data=f"confirm_text_button_{owner_id}_{username}")],
                [InlineKeyboardButton("📎 إضافة ملف", callback_data=f"upload_file_button_{owner_id}_{username}")],
                [InlineKeyboardButton("🔗 إضافة رابط", callback_data=f"add_url_button_{owner_id}_{username}")],
                [InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"✅ **تم إنشاء الزر: {button_name}**\n\n"
                f"📋 **اختر ما تريد فعله:**\n\n"
                f"✅ **زر نصي:** إرسال رسالة نصية عند الضغط\n"
                f"📎 **زر ملف:** إرفاق ملف أو صورة للزر\n"
                f"🔗 **زر رابط:** ربط الزر برابط خارجي\n"
                f"❌ **إلغاء:** حذف الزر وإلغاء العملية",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(f"❌ فشل في إنشاء الزر (قد يكون موجوداً مسبقاً)")

# ===================== معالج الملفات =====================
async def handle_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة رفع الملفات"""
    user_id = update.effective_user.id

    # التحقق من حالة المستخدم
    if user_id in USER_STATES:
        state_data = USER_STATES[user_id]
        if state_data.get('state') == 'linux0root_authenticated' and 'waiting_file_for' in state_data:
            button_name = state_data['waiting_file_for']
            owner_id = state_data['owner_id']
            username = state_data.get('username', '')

            # تحديد نوع الملف
            file_id = None
            file_type = None
            file_name = None

            if update.message.document:
                file_id = update.message.document.file_id
                file_type = "document"
                file_name = update.message.document.file_name
            elif update.message.photo:
                file_id = update.message.photo[-1].file_id
                file_type = "photo"
                file_name = "صورة"
            elif update.message.video:
                file_id = update.message.video.file_id
                file_type = "video"
                file_name = "فيديو"
            elif update.message.audio:
                file_id = update.message.audio.file_id
                file_type = "audio"
                file_name = "صوت"

            if file_id:
                bot_instance = HostedBot(owner_id, username, "", "")
                if bot_instance.add_button(button_name, file_id, file_type):
                    await update.message.reply_text(
                        f"📎 **تم ربط الملف بالزر بنجاح!**\n\n"
                        f"🔘 **اسم الزر:** {button_name}\n"
                        f"📄 **نوع الملف:** {file_type}\n"
                        f"📝 **اسم الملف:** {file_name or 'غير محدد'}\n\n"
                        f"✅ **الزر جاهز للاستخدام في بوتك**",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]] )
                    )
                    del state_data['waiting_file_for'] # إزالة حالة انتظار الملف بعد الربط الناجح
                else:
                    await update.message.reply_text("❌ فشل في ربط الملف")
            else:
                await update.message.reply_text("❌ نوع ملف غير مدعوم")
        else:
            # إذا لم يكن المستخدم في السياق الصحيح أو ينتظر ملفاً
            await update.message.reply_text("⚠️ لا يمكن معالجة هذا الملف الآن.")
    else:
        await update.message.reply_text("⚠️ يجب أن تكون داخل سياق linux0root لمعالجة الملفات.")


# ===================== معالجات تسجيل الدخول وإنشاء البوت =====================
async def handle_bot_factory_interaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة تفاعلات صانع البوتات"""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # التحقق من الحالات النشطة
    if user_id in USER_STATES and USER_STATES[user_id].get('state') == 'linux0root_authenticated':
        # إذا كان المستخدم في سياق linux0root، يتم معالجة الرسائل بواسطة handle_linux0root_management
        return

    if user_id not in BOT_FACTORY_DATA:
        return # تجاهل إذا لم يكن المستخدم في سياق إنشاء البوت

    factory_data = BOT_FACTORY_DATA[user_id]
    step = factory_data.get('step')

    if step == 'waiting_username':
        # التحقق من صحة اسم المستخدم
        if len(text) < 3:
            await update.message.reply_text(
                "❌ **اسم المستخدم قصير جداً**\n\n"
                "يجب أن يكون على الأقل 3 أحرف\n"
                "🔄 أرسل اسم مستخدم آخر أو اكتب 'إلغاء'"
            )
            return

        if ' ' in text:
            await update.message.reply_text(
                "❌ **اسم المستخدم يحتوي على مسافات**\n\n"
                "يجب أن يكون بدون مسافات\n"
                "🔄 أرسل اسم مستخدم آخر أو اكتب 'إلغاء'"
            )
            return

        # التحقق من أن اسم المستخدم لا يحتوي على أحرف غير مسموحة (يمكن تعديل هذا)
        if not re.match(r'^[a-zA-Z0-9_]+$', text):
             await update.message.reply_text(
                "❌ **اسم المستخدم يحتوي على أحرف غير مسموحة**\n\n"
                "يمكن استخدام الأحرف الإنجليزية والأرقام والشرطة السفلية فقط\n"
                "🔄 أرسل اسم مستخدم آخر أو اكتب 'إلغاء'"
            )
             return

        # حفظ اسم المستخدم
        factory_data['username'] = text
        factory_data['step'] = 'waiting_password'
        await update.message.reply_text(
            f"✅ **اسم المستخدم:** {text}\n\n"
            "🔒 **أدخل كلمة المرور:**\n"
            "• يجب أن تكون قوية وآمنة\n"
            "• ستستخدمها للوصول لقاعدة linux0root\n"
            "❌ للإلغاء اكتب: إلغاء"
        )

    elif step == 'waiting_password':
        username = factory_data['username']
        password = text

        # التحقق من قوة كلمة المرور
        if len(password) < 6:
            await update.message.reply_text(
                "❌ **كلمة المرور ضعيفة**\n\n"
                "يجب أن تكون على الأقل 6 أحرف\n"
                "🔄 أرسل كلمة مرور أقوى أو اكتب 'إلغاء'"
            )
            return

        factory_data['password'] = password
        factory_data['step'] = 'waiting_bot_token'

        await update.message.reply_text(
            f"✅ **كلمة المرور محفوظة**\n\n"
            "🤖 **أدخل توكين البوت:**\n"
            "• احصل على التوكين من @BotFather\n"
            "• يجب أن يكون بالشكل: 123456789:ABC...\n"
            "• هذا التوكين سيستخدم لتشغيل بوتك الخاص\n\n"
            "💡 **لإنشاء بوت جديد:**\n"
            "1. اذهب إلى @BotFather\n"
            "2. اكتب /newbot\n"
            "3. اتبع التعليمات\n"
            "4. انسخ التوكين وألصقه هنا\n\n"
            "❌ للإلغاء اكتب: إلغاء"
        )

    elif step == 'waiting_bot_token':
        username = factory_data['username']
        password = factory_data['password']
        bot_token = text

        # التحقق من صحة التوكين
        if not bot_token or ':' not in bot_token or len(bot_token) < 30:
            await update.message.reply_text(
                "❌ **توكين غير صالح**\n\n"
                "🔍 **تأكد من:**\n"
                "• التوكين يحتوي على ':'\n"
                "• التوكين كامل وغير مقطوع\n"
                "• تم نسخه بالكامل من @BotFather\n\n"
                "🔄 **أرسل التوكين الصحيح أو اكتب 'إلغاء'**"
            )
            return

        try:
            # تهيئة قاعدة البيانات المركزية إذا لم تكن موجودة
            init_main_database()

            print(f"🔄 محاولة إنشاء مستخدم: {username} للمعرف: {user_id}")

            # التحقق من الحد الأقصى لعدد البوتات
            user_data = get_user_by_tg_id(user_id)
            if user_data and user_data.get('bot_created', 0) == 1:
                if user_data.get('bots_count', 0) >= user_data.get('max_bots', 3):
                    await update.message.reply_text(
                        f"❌ **لقد تجاوزت الحد الأقصى للبوتات المسموح بها**\n\n"
                        f"• الحد الأقصى هو {user_data.get('max_bots', 3)} بوت.\n"
                        f"• لديك حالياً {user_data.get('bots_count', 0)} بوت.\n\n"
                        f"💡 **يمكنك شراء ترقية لزيادة الحد الأقصى.**"
                    )
                    return

            # إنشاء المستخدم الجديد مع التوكين
            result = create_main_user_with_token(user_id, username, password, bot_token)

            print(f"📋 نتيجة إنشاء المستخدم: {result}")

            if result["success"]:
                # إنشاء البوت والقاعدة
                try:
                    bot_instance = HostedBot(user_id, username, password, bot_token)

                    # تحديث التوكين في البوت باستخدام الدالة المحدثة
                    bot_instance.update_bot_token(bot_token)

                    HOSTED_BOTS[f"{user_id}_{username}"] = bot_instance
                    print(f"✅ تم إنشاء bot_instance للمستخدم: {username}")
                    print(f"✅ تم حفظ التوكين: {bot_token[:20]}...")
                except Exception as bot_error:
                    print(f"خطأ في إنشاء bot_instance: {bot_error}")

                # تحديث حالة إنشاء البوت وزيادة عداد البوتات
                try:
                    conn = sqlite3.connect(MAIN_DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute('UPDATE main_users SET bot_created = 1, bots_count = bots_count + 1 WHERE tg_id = ? AND username = ?', (user_id, username))
                    conn.commit()
                    conn.close()
                    print(f"✅ تم تحديث حالة إنشاء البوت وزيادة عداد البوتات للمستخدم: {username}")
                except Exception as db_error:
                    print(f"خطأ في تحديث قاعدة البيانات: {db_error}")

                await update.message.reply_text(
                    f"🎉 **تم إنشاء بوتك بنجاح!**\n\n"
                    f"👤 **اسم المستخدم:** {username}\n"
                    f"🔐 **كلمة المرور:** {password}\n"
                    f"🤖 **توكين البوت:** {bot_token[:20]}...\n"
                    f"🗃️ **قاعدة البيانات:** linux0root_{user_id}_{username}.db\n\n"
                    f"🔧 **للوصول لإدارة بوتك:**\n"
                    f"• اكتب: `linux0root`\n"
                    f"• أدخل اسم المستخدم وكلمة المرور\n\n"
                    f"🚀 **البوت يعمل الآن على استضافة Replit!**\n"
                    f"✅ **يمكنك إنشاء بوتات إضافية بأسماء مستخدمين مختلفة**",
                    reply_markup=main_menu()
                )

                # مسح البيانات المؤقتة
                del BOT_FACTORY_DATA[user_id]
            else:
                # عرض رسالة خطأ مفصلة حسب نوع المشكلة
                error_type = result.get("error_type", "unknown")
                print(f"❌ فشل إنشاء المستخدم - نوع الخطأ: {error_type}")

                if error_type == "username_taken":
                    await update.message.reply_text(
                        f"❌ **{result['message']}**\n\n"
                        f"💡 **اقتراح:** {result.get('suggestion', 'جرب اسم مستخدم آخر')}\n\n"
                        f"🔄 **أرسل اسم مستخدم جديد أو اكتب 'إلغاء'**"
                    )
                    # العودة لخطوة اسم المستخدم
                    factory_data['step'] = 'waiting_username'
                    return
                else:
                    await update.message.reply_text(
                        f"❌ **فشل في إنشاء الحساب**\n\n"
                        f"🔍 **السبب:** {result.get('message', 'خطأ غير معروف')}\n\n"
                        f"💡 **الحل:** حاول مرة أخرى بمعطيات مختلفة",
                        reply_markup=main_menu()
                    )

                # مسح البيانات المؤقتة فقط في حالات معينة
                if error_type != "username_taken":
                    BOT_FACTORY_DATA.pop(user_id, None)

        except Exception as e:
            print(f"❌ خطأ عام في تسجيل المستخدم: {e}")
            import traceback
            print(f"📋 تفاصيل الخطأ: {traceback.format_exc()}")

            await update.message.reply_text(
                "❌ **حدث خطأ تقني في النظام**\n\n"
                "🔧 **يتم العمل على حل المشكلة**\n"
                "🔄 **حاول مرة أخرى خلال دقائق**\n\n"
                "💡 **إذا استمرت المشكلة، تواصل مع المطور**",
                reply_markup=main_menu()
            )
            # مسح البيانات المؤقتة في حالة الخطأ
            BOT_FACTORY_DATA.pop(user_id, None)

# ===================== معالجات callback المفقودة (لمعالجة تسجيل الدخول وإنشاء البوت) =====================
async def handle_bot_creation_start(query, context):
    """بدء عملية إنشاء البوت"""
    user_id = query.from_user.id

    BOT_FACTORY_DATA[user_id] = {
        'step': 'choose_action',
        'action': None
    }

    keyboard = [
        [InlineKeyboardButton("📝 تسجيل حساب جديد", callback_data="register_new")],
        [InlineKeyboardButton("🔐 تسجيل دخول", callback_data="login_existing")],
        [InlineKeyboardButton("🔙 العودة", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "🤖 **إنشاء/إدارة البوت**\n\n"
        "📋 **اختر العملية المطلوبة:**\n\n"
        "📝 **تسجيل حساب جديد:** إنشاء حساب جديد مع يوزر وباسورد\n"
        "🔐 **تسجيل دخول:** الدخول بحساب موجود\n\n"
        "💡 **ملاحظة:** كل مستخدم له قاعدة بيانات linux0root منفصلة",
        reply_markup=reply_markup
    )

async def handle_linux0root_access_start(query, context):
    """بدء الوصول لقاعدة linux0root مع فحص الجلسة المؤقتة"""
    user_id = query.from_user.id

    # فحص الجلسة المؤقتة أولاً
    temp_session = get_temp_session(user_id)
    if temp_session:
        # المستخدم لديه جلسة صالحة - تمديدها والدخول مباشرة
        extend_temp_session(user_id)
        owner_id = temp_session['owner_id']
        username = temp_session['username']

        # تحديث حالة المستخدم
        USER_STATES[user_id] = {
            'state': 'linux0root_authenticated',
            'owner_id': owner_id,
            'username': username
        }

        # الانتقال مباشرة لقائمة linux0root
        bot_instance = HostedBot(owner_id, username, "", "")
        stats = bot_instance.get_stats()
        actual_status = hosting_manager.get_bot_status(owner_id, username)

        if actual_status == "running":
            status_text = "🟢 يعمل"
        elif actual_status == "stopped":
            status_text = "🔴 متوقف"
        elif actual_status == "error":
            status_text = "🟡 خطأ"
        else:
            status_text = "🔴 غير معروف"

        keyboard = [
            [InlineKeyboardButton("➕ إضافة زر", callback_data=f"add_button_{owner_id}_{username}")],
            [InlineKeyboardButton("🎛️ إدارة الأزرار", callback_data=f"manage_buttons_{owner_id}_{username}")],
            [InlineKeyboardButton("📊 إحصائيات", callback_data=f"stats_{owner_id}_{username}")],
            [InlineKeyboardButton("✏️ تغيير اسم زر", callback_data=f"rename_button_{owner_id}_{username}")],
            [InlineKeyboardButton("🔧 تحديث التوكين", callback_data=f"update_token_{owner_id}_{username}")],
            [InlineKeyboardButton("🚀 تشغيل البوت", callback_data=f"start_bot_{owner_id}_{username}")],
            [InlineKeyboardButton("⏹️ إيقاف البوت", callback_data=f"stop_bot_{owner_id}_{username}")],
            [InlineKeyboardButton("🚪 تسجيل الخروج", callback_data=f"logout_linux_{owner_id}_{username}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"🔐 **مرحباً بك مرة أخرى في قاعدة linux0root**\n\n"
            f"👤 **المستخدم:** {username}\n"
            f"🗃️ **قاعدة البيانات:** linux0root_{owner_id}_{username}.db\n"
            f"⏰ **جلسة نشطة:** باقي {SESSION_DURATION} من وقت آخر نشاط\n\n"
            f"📊 **الإحصائيات:**\n"
            f"• الأزرار: {stats['total_buttons']}\n"
            f"• النقرات: {stats['total_clicks']}\n"
            f"• حالة البوت: {status_text}\n\n"
            f"⚙️ **الأوامر المتاحة:**\n"
            f"• إضافة زر: اكتب اسم الزر\n"
            f"• تغيير اسم [القديم] إلى [الجديد]\n"
            f"• إحصائيات: إحصائيات\n"
            f"• خروج: خروج",
            reply_markup=reply_markup
        )
        return

    # لا توجد جلسة صالحة - طلب تسجيل دخول
    USER_STATES[user_id] = {'state': 'waiting_username_linux0root'}

    await query.edit_message_text(
        "🔐 **الوصول لقاعدة linux0root**\n\n"
        "🎯 **أدخل اسم المستخدم:**\n\n"
        "💡 استخدم اسم المستخدم الذي أنشأت به بوتك\n"
        "❌ للإلغاء اكتب: إلغاء"
    )

async def handle_group_management(query, context):
    """إدارة المجموعات"""
    await query.edit_message_text(
        "📢 **إدارة المجموعات**\n\n"
        "🔗 **لربط مجموعة ببوتك:**\n"
        "1. أضف البوت للمجموعة\n"
        "2. اكتب الأمر: /setgroup <اسم_الأمر>\n"
        "3. سيتم ربط المجموعة تلقائياً\n\n"
        "🎯 **مثال:**\n"
        "`/setgroup mybot`\n\n"
        "🎯 **الآن في المجموعة اكتب:** `/mybot`\n"
        "وسيقوم البوت بنشر محتواه بكفاءة\n\n"
        "✨ **المميزات:**\n"
        "• استجابة فورية للأوامر\n"
        "• نشر ذكي للمحتوى\n"
        "• تحكم في عدد المنشورات"
    )

# ===================== معالجات تسجيل الدخول وإنشاء البوت (مُعاد تسميتها وتحديثها) =====================
async def handle_callback_register_new(query, context):
    """معالج تسجيل حساب جديد"""
    user_id = query.from_user.id
    existing_user = get_user_by_tg_id(user_id)

    if existing_user:
        # المستخدم لديه حساب مسبقاً
        keyboard = [
            [InlineKeyboardButton("🔐 تسجيل دخول للحساب الحالي", callback_data="start_login_existing")],
            [InlineKeyboardButton("🗑️ حذف الحساب وإنشاء جديد", callback_data="confirm_delete_account")],
            [InlineKeyboardButton("🔙 العودة", callback_data="back_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"⚠️ **لديك حساب مسبقاً!**\n\n"
            f"👤 **اسم المستخدم:** {existing_user['username']}\n"
            f"📅 **حالة البوت:** {'✅ مُنشأ' if existing_user['bot_created'] else '❌ غير مُنشأ'}\n\n"
            f"📋 **خياراتك:**\n\n"
            f"🔐 **تسجيل دخول:** للوصول لحسابك الحالي\n"
            f"🗑️ **حذف وإنشاء جديد:** سيحذف جميع بياناتك\n\n"
            f"⚠️ **تحذير:** حذف الحساب سيمحو جميع الأزرار والإعدادات",
            reply_markup=reply_markup
        )
    else:
        # لا يوجد حساب، يمكن إنشاء جديد
        keyboard = [
            [InlineKeyboardButton("📝 إنشاء حساب جديد", callback_data="start_register_new")],
            [InlineKeyboardButton("🔐 تسجيل دخول", callback_data="start_login_existing")],
            [InlineKeyboardButton("🔙 العودة", callback_data="back_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "🤖 **إنشاء/إدارة البوت**\n\n"
            "📋 **اختر العملية المطلوبة:**\n\n"
            "📝 **إنشاء حساب جديد:** تسجيل حساب جديد مع يوزر وباسورد\n"
            "🔐 **تسجيل دخول:** الدخول بحساب موجود\n\n"
            "💡 **ملاحظة:** كل مستخدم له قاعدة بيانات linux0root منفصلة",
            reply_markup=reply_markup
        )

async def handle_callback_login_existing(query, context):
    """معالج تسجيل الدخول"""
    user_id = query.from_user.id

    USER_STATES[user_id] = {'state': 'waiting_username_linux0root'}

    await query.edit_message_text(
        "🔐 **الوصول لقاعدة linux0root**\n\n"
        "👤 **أدخل اسم المستخدم:**\n"
        "❌ للإلغاء اكتب: إلغاء"
    )

async def start_register_process(query, context):
    """بدء عملية تسجيل حساب جديد"""
    user_id = query.from_user.id

    BOT_FACTORY_DATA[user_id] = {
        'step': 'waiting_username',
        'action': 'register'
    }

    await query.edit_message_text(
        "📝 **تسجيل حساب جديد**\n\n"
        "👤 **أدخل اسم المستخدم:**\n"
        "• يجب أن يكون فريداً\n"
        "• بدون مسافات\n"
        "• الأحرف العربية والإنجليزية مسموحة\n"
        "❌ للإلغاء اكتب: إلغاء"
    )

async def start_login_process(query, context):
    """بدء عملية تسجيل الدخول"""
    user_id = query.from_user.id

    USER_STATES[user_id] = {'state': 'waiting_username_linux0root'}

    await query.edit_message_text(
        "🔐 **الوصول لقاعدة linux0root**\n\n"
        "👤 **أدخل اسم المستخدم:**\n"
        "💡 استخدم نفس اسم المستخدم الذي أنشأت به بوتك\n"
        "❌ للإلغاء اكتب: إلغاء"
    )

async def confirm_delete_account(query, context):
    """تأكيد حذف الحساب"""
    user_id = query.from_user.id
    existing_user = get_user_by_tg_id(user_id)

    keyboard = [
        [InlineKeyboardButton("✅ نعم، احذف حسابي", callback_data="delete_account_confirmed")],
        [InlineKeyboardButton("❌ لا، احتفظ بالحساب", callback_data="bot_create_new")],
        [InlineKeyboardButton("🔙 العودة", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"⚠️ **تأكيد حذف الحساب**\n\n"
        f"👤 **الحساب المراد حذفه:** {existing_user['username']}\n\n"
        f"🗑️ **سيتم حذف:**\n"
        f"• جميع أزرار البوت\n"
        f"• قاعدة بيانات linux0root\n"
        f"• جميع الإعدادات والملفات\n"
        f"• سجل النشاط والإحصائيات\n\n"
        f"⚠️ **تحذير:** هذا الإجراء لا يمكن التراجع عنه!\n\n"
        f"❓ **هل أنت متأكد من المتابعة؟**",
        reply_markup=reply_markup
    )

async def delete_account_confirmed(query, context):
    """تنفيذ حذف الحساب"""
    user_id = query.from_user.id
    existing_user = get_user_by_tg_id(user_id)

    if not existing_user:
        await query.edit_message_text("❌ لم يتم العثور على حساب للحذف")
        return

    username = existing_user['username']

    # حذف الحساب نهائياً
    if delete_user_completely(username):
        await query.edit_message_text(
            f"✅ **تم حذف الحساب بنجاح**\n\n"
            f"🗑️ **الحساب المحذوف:** {username}\n\n"
            f"📝 **يمكنك الآن إنشاء حساب جديد**\n"
            f"اضغط على '🔧 صانع البوتات' مرة أخرى لبدء إنشاء حساب جديد"
        )
    else:
        await query.edit_message_text(
            f"❌ **فشل في حذف الحساب**\n\n"
            f"🔧 **يرجى التواصل مع المطور لحل المشكلة**"
        )

# ===================== دوال إدارة الأزرار المتقدمة =====================

async def handle_buttons_management(query, context, owner_id, username):
    """معالج قائمة إدارة الأزرار"""
    try:
        bot_instance = HostedBot(owner_id, username, "", "")
        buttons = bot_instance.get_buttons()

        if not buttons:
            keyboard = [
                [InlineKeyboardButton("➕ إضافة أول زر", callback_data=f"add_button_{owner_id}_{username}")],
                [InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "📭 **لا توجد أزرار محفوظة**\n\n"
                "ابدأ بإنشاء أول زر لبوتك!",
                reply_markup=reply_markup
            )
            return

        # إنشاء قائمة تفاعلية للأزرار
        keyboard = []
        message_text = "🎛️ **إدارة الأزرار**\n\n"
        message_text += "📋 **قائمة الأزرار المحفوظة:**\n\n"

        for i, btn in enumerate(buttons[:15], 1):  # عرض أول 15 زر
            button_name = btn[0]
            file_type = btn[2] if len(btn) > 2 and btn[2] else "نص"
            clicks = btn[3] if len(btn) > 3 else 0

            # تحديد أيقونة حسب نوع المحتوى
            if len(btn) > 4 and btn[4]:  # button_type
                button_type = btn[4]
                if button_type == "file":
                    icon = "📎"
                elif button_type == "url":
                    icon = "🔗"
                else:
                    icon = "📝"
            else:
                icon = "📝" if not btn[1] else "📎"

            # إضافة معلومات الزر للرسالة
            message_text += f"{i}. {icon} **{button_name}**\n"
            message_text += f"   📊 النقرات: {clicks} | 🏷️ النوع: {file_type}\n\n"

            # إضافة زر تفاعلي
            keyboard.append([
                InlineKeyboardButton(
                    f"{icon} {button_name} ({clicks} نقرة)",
                    callback_data=f"manage_button_{owner_id}_{username}_{button_name}"
                )
            ])

        # أزرار إضافية
        keyboard.append([InlineKeyboardButton("➕ إضافة زر جديد", callback_data=f"add_button_{owner_id}_{username}")])
        keyboard.append([InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            message_text + "💡 **اضغط على أي زر لإدارته**",
            reply_markup=reply_markup
        )

    except Exception as e:
        print(f"خطأ في handle_buttons_management: {e}")
        keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("❌ حدث خطأ في تحميل قائمة الأزرار", reply_markup=reply_markup)

async def handle_single_button_management(query, context, owner_id, username, button_name):
    """معالج إدارة زر محدد"""
    try:
        bot_instance = HostedBot(owner_id, username, "", "")

        # البحث عن الزر المحدد
        buttons = bot_instance.get_buttons()
        button_data = None

        for btn in buttons:
            if btn[0] == button_name:
                button_data = btn
                break

        if not button_data:
            await query.edit_message_text("❌ الزر غير موجود")
            return

        # عرض تفاصيل الزر
        button_name = button_data[0]
        file_id = button_data[1] if len(button_data) > 1 else None
        file_type = button_data[2] if len(button_data) > 2 else "نص"
        clicks = button_data[3] if len(button_data) > 3 else 0
        button_type = button_data[4] if len(button_data) > 4 else "text"
        content = button_data[5] if len(button_data) > 5 else None
        url = button_data[6] if len(button_data) > 6 else None

        # تحديد أيقونة ونوع المحتوى
        if button_type == "file":
            icon = "📎"
            content_info = f"📁 **ملف:** {file_type}" if file_type else "📁 **ملف محفوظ**"
        elif button_type == "url":
            icon = "🔗"
            content_info = f"🔗 **رابط:** {url}" if url else "🔗 **رابط محفوظ**"
        else:
            icon = "📝"
            content_info = f"📝 **نص:** {content[:50]}..." if content and len(content) > 50 else f"📝 **نص:** {content}" if content else "📝 **رسالة نصية**"

        message_text = f"🎛️ **إدارة الزر: {button_name}**\n\n"
        message_text += f"{icon} **اسم الزر:** {button_name}\n"
        message_text += f"📊 **عدد النقرات:** {clicks}\n"
        message_text += f"🏷️ **نوع المحتوى:** {button_type}\n"
        message_text += f"{content_info}\n\n"
        message_text += "**اختر العملية المطلوبة:**"

        keyboard = [
            [InlineKeyboardButton("🗑️ حذف الزر", callback_data=f"delete_specific_button_{owner_id}_{username}_{button_name}")],
            [InlineKeyboardButton("⚙️ إعدادات الزر", callback_data=f"button_settings_{owner_id}_{username}_{button_name}")],
            [InlineKeyboardButton("🔙 العودة لقائمة الأزرار", callback_data=f"manage_buttons_{owner_id}_{username}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message_text, reply_markup=reply_markup)

    except Exception as e:
        print(f"خطأ في handle_single_button_management: {e}")
        keyboard = [[InlineKeyboardButton("🔙 العودة لقائمة الأزرار", callback_data=f"manage_buttons_{owner_id}_{username}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("❌ حدث خطأ في تحميل بيانات الزر", reply_markup=reply_markup)

async def handle_delete_specific_button(query, context, owner_id, username, button_name):
    """معالج حذف زر محدد مع تأكيد"""
    try:
        message_text = f"🗑️ **تأكيد حذف الزر**\n\n"
        message_text += f"🔘 **الزر:** {button_name}\n\n"
        message_text += "⚠️ **تحذير:** هذا الإجراء لا يمكن التراجع عنه!\n"
        message_text += "سيتم حذف الزر وجميع ملفاته نهائياً.\n\n"
        message_text += "هل أنت متأكد من المتابعة؟"

        keyboard = [
            [InlineKeyboardButton("✅ تأكيد الحذف", callback_data=f"confirm_delete_{owner_id}_{username}_{button_name}")],
            [InlineKeyboardButton("❌ إلغاء", callback_data=f"manage_button_{owner_id}_{username}_{button_name}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message_text, reply_markup=reply_markup)

    except Exception as e:
        print(f"خطأ في handle_delete_specific_button: {e}")

async def handle_button_settings(query, context, owner_id, username, button_name):
    """معالج إعدادات الزر وإدارة الملفات"""
    try:
        bot_instance = HostedBot(owner_id, username, "", "")

        # البحث عن الزر
        buttons = bot_instance.get_buttons()
        button_data = None

        for btn in buttons:
            if btn[0] == button_name:
                button_data = btn
                break

        if not button_data:
            await query.edit_message_text("❌ الزر غير موجود")
            return

        file_id = button_data[1] if len(button_data) > 1 else None
        file_type = button_data[2] if len(button_data) > 2 else None
        button_type = button_data[4] if len(button_data) > 4 else "text"
        content = button_data[5] if len(button_data) > 5 else None
        url = button_data[6] if len(button_data) > 6 else None

        # تحديد أيقونة ونوع المحتوى
        if button_type == "file":
            icon = "📎"
            content_info = f"📁 **ملف:** {file_type}" if file_type else "📁 **ملف محفوظ**"
        elif button_type == "url":
            icon = "🔗"
            content_info = f"🔗 **رابط:** {url}" if url else "🔗 **رابط محفوظ**"
        else:
            icon = "📝"
            content_info = f"📝 **نص:** {content[:50]}..." if content and len(content) > 50 else f"📝 **نص:** {content}" if content else "📝 **رسالة نصية**"

        message_text = f"⚙️ **إعدادات الزر: {button_name}**\n\n"
        message_text += f"{icon} **اسم الزر:** {button_name}\n"
        message_text += f"📊 **عدد النقرات:** {clicks}\n"
        message_text += f"🏷️ **نوع المحتوى:** {button_type}\n"
        message_text += f"{content_info}\n\n"
        message_text += "**اختر العملية المطلوبة:**"

        keyboard = [
            [InlineKeyboardButton("🗑️ حذف الزر", callback_data=f"delete_specific_button_{owner_id}_{username}_{button_name}")],
            [InlineKeyboardButton("⚙️ إعدادات الزر", callback_data=f"button_settings_{owner_id}_{username}_{button_name}")],
            [InlineKeyboardButton("🔙 العودة لقائمة الأزرار", callback_data=f"manage_buttons_{owner_id}_{username}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message_text, reply_markup=reply_markup)

    except Exception as e:
        print(f"خطأ في handle_button_settings: {e}")
        keyboard = [[InlineKeyboardButton("🔙 العودة لقائمة الأزرار", callback_data=f"manage_buttons_{owner_id}_{username}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("❌ حدث خطأ في تحميل إعدادات الزر", reply_markup=reply_markup)

async def handle_delete_button_file(query, context, owner_id, username, button_name, file_id):
    """معالج حذف ملف محدد من الزر"""
    try:
        bot_instance = HostedBot(owner_id, username, "", "")

        # تحديث الزر لإزالة الملف
        success = bot_instance.add_button(button_name, button_type="text", content="تم حذف الملف")

        if success:
            message_text = f"✅ **تم حذف الملف بنجاح**\n\n"
            message_text += f"🔘 **الزر:** {button_name}\n"
            message_text += f"🗑️ **الملف المحذوف:** {file_id[:20]}...\n\n"
            message_text += "تم تحويل الزر إلى زر نصي."
        else:
            message_text = "❌ فشل في حذف الملف"

        keyboard = [[InlineKeyboardButton("🔙 العودة لإعدادات الزر", callback_data=f"button_settings_{owner_id}_{username}_{button_name}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message_text, reply_markup=reply_markup)

    except Exception as e:
        print(f"خطأ في handle_delete_button_file: {e}")

async def handle_delete_all_button_files(query, context, owner_id, username, button_name):
    """معالج حذف جميع ملفات الزر"""
    try:
        bot_instance = HostedBot(owner_id, username, "", "")

        # حذف جميع الملفات وتحويل الزر إلى نصي
        success = bot_instance.add_button(button_name, button_type="text", content="تم حذف جميع الملفات")

        if success:
            message_text = f"✅ **تم حذف جميع الملفات بنجاح**\n\n"
            message_text += f"🔘 **الزر:** {button_name}\n"
            message_text += "🗑️ تم حذف جميع الملفات المرتبطة بالزر\n"
            message_text += "تم تحويل الزر إلى زر نصي."
        else:
            message_text = "❌ فشل في حذف الملفات"

        keyboard = [[InlineKeyboardButton("🔙 العودة لإعدادات الزر", callback_data=f"button_settings_{owner_id}_{username}_{button_name}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message_text, reply_markup=reply_markup)

    except Exception as e:
        print(f"خطأ في handle_delete_all_button_files: {e}")

# ===================== دوال إدارة الأزرار المفقودة =====================
async def handle_add_button_logic(query, context, owner_id, username):
    """معالج منطق إضافة الأزرار"""
    user_id = query.from_user.id

    # تحديث حالة المستخدم
    USER_STATES[user_id] = {
        'state': 'linux0root_authenticated',
        'owner_id': owner_id,
        'username': username,
        'waiting_for_button_name': True
    }

    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_main_{owner_id}_{username}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "➕ **إضافة زر جديد**\n\n"
        "📝 **اكتب اسم الزر الجديد:**\n\n"
        "💡 **نصائح:**\n"
        "• اختر اسماً واضحاً ومفهوماً\n"
        "• تجنب الأسماء المكررة\n"
        "• استخدم أسماء قصيرة ومعبرة\n\n"
        "❌ للإلغاء اضغط الزر أدناه",
        reply_markup=reply_markup
    )

async def handle_button_name_input(update, context, state_data, owner_id, username):
    """معالج إدخال اسم الزر"""
    user_id = update.effective_user.id
    button_name = update.message.text.strip()

    if len(button_name) < 1:
        await update.message.reply_text("❌ اسم الزر لا يمكن أن يكون فارغاً")
        return

    if len(button_name) > 50:
        await update.message.reply_text("❌ اسم الزر طويل جداً (الحد الأقصى 50 حرف)")
        return

    # إنشاء الزر
    bot_instance = HostedBot(owner_id, username, "", "")
    if bot_instance.add_button(button_name):
        state_data['waiting_for_button_name'] = False
        state_data['waiting_file_for'] = button_name

        # إنشاء أزرار للخيارات
        keyboard = [
            [InlineKeyboardButton("✅ حفظ الزر (نصي)", callback_data=f"confirm_text_button_{owner_id}_{username}")],
            [InlineKeyboardButton("📎 إضافة ملف", callback_data=f"upload_file_button_{owner_id}_{username}")],
            [InlineKeyboardButton("🔗 إضافة رابط", callback_data=f"add_url_button_{owner_id}_{username}")],
            [InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_add_button_{owner_id}_{username}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"✅ **تم إنشاء الزر: {button_name}**\n\n"
            f"📋 **اختر نوع المحتوى:**\n\n"
            f"✅ **زر نصي:** إرسال رسالة نصية عند الضغط\n"
            f"📎 **زر ملف:** إرفاق ملف أو صورة للزر\n"
            f"🔗 **زر رابط:** ربط الزر برابط خارجي\n"
            f"❌ **إلغاء:** حذف الزر وإلغاء العملية",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(f"❌ فشل في إنشاء الزر (قد يكون موجوداً مسبقاً)")

async def handle_rename_button_step1(query, context, owner_id, username):
    """الخطوة الأولى في تغيير اسم الزر"""
    user_id = query.from_user.id

    bot_instance = HostedBot(owner_id, username, "", "")
    buttons = bot_instance.get_buttons()

    if not buttons:
        keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📭 **لا توجد أزرار لتغيير أسمائها**\n\n"
            "قم بإنشاء أزرار أولاً!",
            reply_markup=reply_markup
        )
        return

    # عرض قائمة الأزرار للاختيار
    keyboard = []
    message_text = "✏️ **تغيير اسم زر**\n\n"
    message_text += "📋 **اختر الزر الذي تريد تغيير اسمه:**\n\n"

    for btn in buttons[:10]:  # عرض أول 10 أزرار
        button_name = btn[0]
        keyboard.append([InlineKeyboardButton(f"📝 {button_name}", callback_data=f"rename_select_{owner_id}_{username}_{button_name}")])

    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_rename_{owner_id}_{username}")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(message_text, reply_markup=reply_markup)

async def handle_rename_button_step2(update, context, state_data, owner_id, username):
    """الخطوة الثانية في تغيير اسم الزر"""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if state_data.get('waiting_for_rename_new'):
        # المستخدم يدخل الاسم الجديد
        old_name = state_data.get('rename_old_name')
        new_name = text

        if len(new_name) < 1:
            await update.message.reply_text("❌ الاسم الجديد لا يمكن أن يكون فارغاً")
            return

        if len(new_name) > 50:
            await update.message.reply_text("❌ الاسم الجديد طويل جداً")
            return

        bot_instance = HostedBot(owner_id, username, "", "")
        if bot_instance.rename_button(old_name, new_name):
            # مسح البيانات المؤقتة
            state_data.pop('waiting_for_rename_new', None)
            state_data.pop('rename_old_name', None)

            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"✅ **تم تغيير اسم الزر بنجاح!**\n\n"
                f"📝 **الاسم القديم:** {old_name}\n"
                f"📝 **الاسم الجديد:** {new_name}",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text("❌ فشل في تغيير اسم الزر")

async def handle_delete_button_step1(query, context, owner_id, username):
    """الخطوة الأولى في حذف الزر"""
    user_id = query.from_user.id

    USER_STATES[user_id] = {
        'state': 'linux0root_authenticated',
        'owner_id': owner_id,
        'username': username,
        'waiting_for_delete_name': True
    }

    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_delete_{owner_id}_{username}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "🗑️ **حذف زر**\n\n"
        "📝 **اكتب اسم الزر المراد حذفه:**\n\n"
        "⚠️ **تحذير:** هذا الإجراء لا يمكن التراجع عنه!",
        reply_markup=reply_markup
    )

async def handle_delete_button_step2(update, context, state_data, owner_id, username):
    """الخطوة الثانية في حذف الزر"""
    button_name = update.message.text.strip()

    bot_instance = HostedBot(owner_id, username, "", "")
    if bot_instance.delete_button(button_name):
        # مسح البيانات المؤقتة
        state_data.pop('waiting_for_delete_name', None)

        keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"✅ **تم حذف الزر بنجاح!**\n\n"
            f"🗑️ **الزر المحذوف:** {button_name}",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(f"❌ الزر '{button_name}' غير موجود أو فشل في الحذف")

async def handle_update_token_step1(query, context, owner_id, username):
    """الخطوة الأولى في تحديث التوكين"""
    user_id = query.from_user.id

    USER_STATES[user_id] = {
        'state': 'linux0root_authenticated',
        'owner_id': owner_id,
        'username': username,
        'waiting_for_new_token': True
    }

    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_token_update_{owner_id}_{username}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "🔧 **تحديث توكين البوت**\n\n"
        "🤖 **أدخل التوكين الجديد:**\n\n"
        "💡 **للحصول على التوكين:**\n"
        "1. اذهب إلى @BotFather\n"
        "2. اختر بوتك\n"
        "3. اضغط على 'API Token'\n"
        "4. انسخ التوكين والصقه هنا\n\n"
        "⚠️ **تأكد من صحة التوكين قبل الإرسال**",
        reply_markup=reply_markup
    )

async def handle_update_token_step2(update, context, state_data, owner_id, username):
    """الخطوة الثانية في تحديث التوكين"""
    user_id = update.effective_user.id
    new_token = update.message.text.strip()

    # التحقق من صحة التوكين
    if not new_token or ':' not in new_token or len(new_token) < 30:
        await update.message.reply_text(
            "❌ **توكين غير صالح**\n\n"
            "🔍 **تأكد من:**\n"
            "• التوكين يحتوي على ':'\n"
            "• التوكين كامل وغير مقطوع\n"
            "• تم نسخه بالكامل من @BotFather\n\n"
            "🔄 **أرسل التوكين الصحيح أو اكتب 'إلغاء'**"
        )
        return

    # تحديث التوكين
    bot_instance = HostedBot(owner_id, username, "", "")
    if bot_instance.update_bot_token(new_token):
        # مسح البيانات المؤقتة
        state_data.pop('waiting_for_new_token', None)

        keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"✅ **تم تحديث التوكين بنجاح!**\n\n"
            f"🤖 **البوت:** {username}\n"
            f"🔑 **التوكين الجديد:** {new_token[:20]}...\n\n"
            f"💡 **يمكنك الآن تشغيل البوت بالتوكين الجديد**",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("❌ فشل في تحديث التوكين")

async def handle_cancel_token_update(query, context, owner_id, username):
    """إلغاء تحديث التوكين"""
    user_id = query.from_user.id

    if user_id in USER_STATES:
        state_data = USER_STATES[user_id]
        state_data.pop('waiting_for_new_token', None)

    keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data=f"linux_menu_{owner_id}_{username}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "❌ **تم إلغاء تحديث التوكين**\n\n"
        "لم يتم حفظ أي تغييرات",
        reply_markup=reply_markup
    )

# ===================== معالج الأخطاء =====================
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الأخطاء العام"""
    import traceback

    try:
        # طباعة الخطأ في وحدة التحكم
        print(f"❌ خطأ في البوت: {context.error}")
        print(f"📝 تفاصيل الخطأ: {traceback.format_exc()}")

        # إرسال رسالة خطأ للمستخدم
        if update and update.effective_user:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_user.id,
                    text="❌ حدث خطأ مؤقت في النظام. يرجى المحاولة مرة أخرى."
                )
            except Exception as e:
                print(f"فشل في إرسال رسالة الخطأ: {e}")

    except Exception as e:
        print(f"خطأ في معالج الأخطاء نفسه: {e}")

# ===================== الدوال المساعدة للتشغيل =====================
def ensure_user_bot_files():
    """التأكد من وجود ملفات البوتات لجميع المستخدمين"""
    try:
        if not os.path.exists(MAIN_DB_PATH):
            print("⚠️ لا توجد قاعدة بيانات مركزية")
            return

        conn = sqlite3.connect(MAIN_DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT tg_id, username, bot_token FROM main_users WHERE bot_created = 1')
        users = cursor.fetchall()
        conn.close()

        for user_id, username, bot_token in users:
            if bot_token:
                try:
                    # التأكد من وجود مجلد البيانات
                    user_dir = f"user_data/{user_id}_{username}"
                    os.makedirs(user_dir, exist_ok=True)
                    os.makedirs(f"{user_dir}/files", exist_ok=True)

                    # إنشاء ملف البوت إذا لم يكن موجوداً
                    bot_file = f"{user_dir}/bot_{username}.py"
                    if not os.path.exists(bot_file):
                        bot_instance = HostedBot(user_id, username, "", bot_token)
                        print(f"✅ تم إنشاء ملف البوت للمستخدم: {username}")
                except Exception as e:
                    print(f"⚠️ خطأ في إنشاء ملفات المستخدم {username}: {e}")

        print(f"✅ تم فحص ملفات {len(users)} مستخدم")
    except Exception as e:
        print(f"⚠️ خطأ في ensure_user_bot_files: {e}")

def start_all_hosted_bots():
    """تشغيل جميع البوتات المستضافة عند بدء التشغيل"""
    try:
        if not os.path.exists(MAIN_DB_PATH):
            print("⚠️ لا توجد قاعدة بيانات مركزية لتشغيل البوتات")
            return

        conn = sqlite3.connect(MAIN_DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT tg_id, username, bot_token FROM main_users WHERE bot_created = 1 AND bot_token IS NOT NULL')
        users = cursor.fetchall()
        conn.close()

        started_count = 0
        for user_id, username, bot_token in users:
            try:
                # محاولة تشغيل البوت
                success = hosting_manager.start_user_bot(user_id, username, bot_token)
                if success:
                    started_count += 1
                    print(f"✅ تم تشغيل البوت: {username}")
                else:
                    print(f"⚠️ فشل في تشغيل البوت: {username}")
            except Exception as e:
                print(f"⚠️ خطأ في تشغيل البوت {username}: {e}")

        print(f"🚀 تم تشغيل {started_count} من أصل {len(users)} بوت مستضاف")
    except Exception as e:
        print(f"⚠️ خطأ في start_all_hosted_bots: {e}")

# ===================== التشغيل الرئيسي =====================
def run_bot():
    """الدالة الرئيسية لتشغيل البوت"""
    try:
        # التحقق من توفر مكتبة telegram
        try:
            from telegram.ext import Application
        except ImportError:
            print("❌ مكتبة telegram غير متوفرة - لا يمكن تشغيل البوت")
            print("🔧 حاول إعادة تشغيل الكود مرة أخرى")
            return

        # إيقاف أي عمليات تعارض محتملة
        try:
            import psutil
            import os
            current_process = os.getpid()
            for proc in psutil.process_iter(['pid', 'cmdline']):
                try:
                    if proc.info['pid'] != current_process and proc.info['cmdline']:
                        cmdline = ' '.join(proc.info['cmdline'])
                        if 'main.py' in cmdline and 'python' in cmdline:
                            print(f"🔄 إيقاف عملية متعارضة: PID {proc.info['pid']}")
                            proc.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except ImportError:
            print("⚠️ مكتبة psutil غير متوفرة - سيتم المتابعة بدونها")

        # تهيئة قاعدة البيانات المركزية
        init_main_database()

        # بدء خدمة استضافة البوتات
        print("🏗️ بدء تشغيل خدمة استضافة البوتات...")
        try:
            from bot_hosting_manager import start_hosting_service
            import threading
            hosting_thread = threading.Thread(target=start_hosting_service, daemon=True)
            hosting_thread.start()
            print("✅ تم بدء خدمة الاستضافة")
        except Exception as hosting_error:
            print(f"⚠️ خطأ في بدء خدمة الاستضافة: {hosting_error}")
            print("🔄 سيتم المتابعة بدون خدمة الاستضافة")

        # التأكد من وجود ملفات البوتات لجميع المستخدمين
        ensure_user_bot_files()

        # تشغيل البوتات المستضافة عند بدء التشغيل
        start_all_hosted_bots()

        # إنشاء التطبيق
        application = Application.builder().token(TELEGRAM_TOKEN).build()
    except Exception as e:
        print(f"❌ خطأ في تهيئة البوت: {e}")
        import traceback
        print(f"📋 تفاصيل الخطأ: {traceback.format_exc()}")
        return

    # إضافة معالجات الأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ban", cmd_ban_user))
    application.add_handler(CommandHandler("unban", cmd_unban_user))
    application.add_handler(CommandHandler("delete", cmd_delete_user))
    application.add_handler(CommandHandler("setgroup", lambda u, c: print("setgroup called"))) # Placeholder for setgroup command

    # إضافة معالجات خاصة بالرسائل النصية التي قد تأتي كأمر (مثل /done)
    application.add_handler(MessageHandler(filters.COMMAND, handle_message)) # Catch commands first

    # معالجات التفاعل
    application.add_handler(CallbackQueryHandler(handle_callback_query))

    # معالجات الملفات
    application.add_handler(MessageHandler(
        filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO,
        handle_file_upload
    ))

    # معالج الرسائل النصية (يجب أن يكون الأخير للتعامل مع الرسائل غير المفسرة كأوامر أو callback)
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    # معالج الأخطاء
    try:
        application.add_error_handler(error_handler)
    except Exception as e:
        print(f"⚠️ خطأ في إضافة معالج الأخطاء: {e}")
        print("🔄 سيتم المتابعة بدون معالج الأخطاء")

    print("🚀 ==================================================")
    print("   منصة الذكاء الاصطناعي المطورة - نظام صانع البوتات")
    print("==================================================")
    print("🔧 صانع البوتات: ✅ نظام مركزي متقدم")
    print("🗃️ قاعدة البيانات: ✅ linux0root منفصلة لكل مستخدم")
    print("🔐 نظام الأمان: ✅ تشفير وحماية متقدمة")
    print("👑 إدارة المشرف: ✅ حظر/إلغاء حظر/حذف")
    print("==================================================")
    print("🟢 بدء تشغيل البوت...")

    try:
        # تشغيل البوت مع معالجة أفضل للتعارضات
        try:
            application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
                poll_interval=1.0,
                timeout=20
            )
        except Exception as polling_error:
            if "Conflict" in str(polling_error):
                print("🔄 تم اكتشاف تعارض - محاولة إعادة التشغيل...")
                import time
                time.sleep(5)
                application.run_polling(
                    allowed_updates=Update.ALL_TYPES,
                    drop_pending_updates=True,
                    poll_interval=2.0,
                    timeout=30
                )
            else:
                raise polling_error
    except Exception as e:
        print(f"❌ خطأ في تشغيل البوت: {e}")
        print("🔄 جاري المحاولة مرة أخرى...")
        try:
            application.run_polling()
        except Exception as e2:
            print(f"❌ فشل نهائي في تشغيل البوت: {e2}")
            import traceback
            print(f"📋 تفاصيل الخطأ: {traceback.format_exc()}")
            print("🔧 حاول إعادة تشغيل الكود مرة أخرى")

if __name__ == '__main__':
    run_bot()

async def delete_button_file(update, context, btn_id: int):
    row = ub_get_button(btn_id)
    if not row:
        await update.callback_query.answer("⚠️ الزر غير موجود", show_alert=True)
        return
    ub_update_file(btn_id, file_id=None, file_type=None, file_path=None)
    await update.callback_query.edit_message_text("🗑️ تم حذف الملف من الزر.")


async def preview_button_file(update, context, btn_id: int):
    row = ub_get_button(btn_id)
    if not row:
        await update.callback_query.answer("⚠️ الزر غير موجود", show_alert=True)
        return
    (_id, _owner, _user, text, btype, content, url, file_id, file_type, file_path, clicks, active) = row
    if url:
        await update.callback_query.message.reply_text(f"🔗 الرابط: {url}")
    elif file_id and file_type:
        if file_type == "document":
            await update.callback_query.message.reply_document(file_id)
        elif file_type == "photo":
            await update.callback_query.message.reply_photo(file_id)
        elif file_type == "video":
            await update.callback_query.message.reply_video(file_id)
        elif file_type == "audio":
            await update.callback_query.message.reply_audio(file_id)
        else:
            await update.callback_query.message.reply_text("⚠️ نوع الملف غير مدعوم للاستعراض.")
    elif content:
        await update.callback_query.message.reply_text(f"📝 المحتوى: {content}")
    else:
        await update.callback_query.answer("⚠️ لا يوجد محتوى مرتبط بالزر", show_alert=True)


# === linux0root_patch AUTO-INJECT (append-only) ===
try:
    from linux0root_patch import apply_patch as __linux0root_apply_patch
    __linux0root_apply_patch(globals())
except Exception as __linux0root_e:
    print("linux0root_patch inject error:", __linux0root_e)
# === /linux0root_patch AUTO-INJECT ===


# === linux0root_sync_patch AUTO-REGISTER (append-only) ===
try:
    from linux0root_sync_patch import apply_sync_patch as __l0r_apply_sync, parse_cb as __l0r_parse_cb
    __l0r_apply_sync(globals())
    if 'application' in globals():
        # يضمن تسجيل الهاندلرز حتى لو لم تُستدع register_sync_handlers يدوياً
        if 'register_sync_handlers' in globals():
            try:
                register_sync_handlers(application)
            except Exception as __e_auto_reg:
                print("auto register_sync_handlers error:", __e_auto_reg)
except Exception as __e_sync_auto:
    print("linux0root_sync_patch auto-register error:", __e_sync_auto)
# === /linux0root_sync_patch AUTO-REGISTER ===
