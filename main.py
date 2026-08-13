import logging
import os
import json
import re
import asyncio
import sqlite3
import requests
from datetime import datetime
from threading import Thread
from flask import Flask

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# 🌐 Keep-Alive Web Server + Self Ping System
web_app = Flask('')

@web_app.route('/')
def home():
    return "Telegram Auto Reaction SMM Engine: ACTIVE 24/7"

def ping_self():
    render_url = os.environ.get("RENDER_EXTERNAL_URL", "https://reaction-bot-7d1u.onrender.com")
    while True:
        try:
            asyncio.run(asyncio.sleep(280)) # Ping every 4 mins 50 secs
            requests.get(render_url, timeout=10)
            logger.info("📡 Keeping bot server active 24/7...")
        except Exception as e:
            logger.warning(f"Self Ping Warning: {e}")

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t_web = Thread(target=run_web)
    t_web.daemon = True
    t_web.start()
    
    t_ping = Thread(target=ping_self)
    t_ping.daemon = True
    t_ping.start()

# 🔑 Configuration
BOT_TOKEN = "8320025447:AAFWnP_asWXs6WXS-h_gPAy6Baikd6-4jMc"
BOT_USERNAME = "@TGSUPER_SERVICE_BOT"
ADMIN_IDS = [8454401183, 7871224176]
ADMIN_USERNAME = "@SOYABUR_AS_LEADER"

# 📢 Order Logs Channel
LOG_CHANNEL = "@orderchannelsuperfast"

# 🌐 Default SMM Panel Config
SMM_API_URL = "https://1xpanel.com/api/v2"

DB_FILE = "database.db"

# 📝 Logging System
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Cache for preventing duplicate album/media group processing
PROCESSED_MEDIA_GROUPS = set()

# 🗄️ Permanent SQLite Database Manager
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT DEFAULT '',
            credit INTEGER DEFAULT 500,
            ref_count INTEGER DEFAULT 0,
            ref_credit INTEGER DEFAULT 0,
            projects TEXT DEFAULT '[]',
            is_blocked INTEGER DEFAULT 0
        )
    ''')
    
    # Auto migration for username column
    cursor.execute("PRAGMA table_info(users)")
    user_cols = [c[1] for c in cursor.fetchall()]
    if 'username' not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN username TEXT DEFAULT ''")

    # Orders table (Completed Orders)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            order_id TEXT,
            channel_name TEXT,
            count INTEGER,
            post_link TEXT,
            order_type TEXT DEFAULT 'Reacts',
            status TEXT DEFAULT 'completed',
            created_at TEXT
        )
    ''')
    
    # Auto migration if order_type or status doesn't exist in orders
    cursor.execute("PRAGMA table_info(orders)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'order_type' not in columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN order_type TEXT DEFAULT 'Reacts'")
    if 'status' not in columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN status TEXT DEFAULT 'completed'")

    # Top-up Requests Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS topup_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            txid TEXT,
            photo_id TEXT,
            amount INTEGER DEFAULT 0,
            status TEXT DEFAULT 'PENDING',
            created_at TEXT
        )
    ''')
    # Settings table for Admin Configuration
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Default Settings Setup
    defaults = {
        "smm_api_key": "792d092f1f7fdcebcb9233107b2f1f33",
        "smm_service_id": "1936",
        "smm_view_service_id": "7294", # Video View Service ID
        "coin_rate": "1",          # 1 coin = 1 reaction
        "dollar_rate": "1000",     # $1 = 1000 coins
        "referral_bonus": "100"    # 100 coins per referral
    }
    for k, v in defaults.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    conn.commit()
    conn.close()

init_db()

def db_get_setting(key, default_val=""):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default_val

def db_set_setting(key, value):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (str(key), str(value)))
    conn.commit()
    conn.close()

def db_get_user(user_id, username_val=""):
    str_id = str(user_id)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT credit, ref_count, ref_credit, projects, is_blocked, username FROM users WHERE user_id = ?", (str_id,))
    row = cursor.fetchone()
    
    if not row:
        default_projects = json.dumps([])
        cursor.execute(
            "INSERT INTO users (user_id, username, credit, ref_count, ref_credit, projects, is_blocked) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str_id, username_val, 500, 0, 0, default_projects, 0)
        )
        conn.commit()
        conn.close()
        return {
            "user_id": str_id,
            "username": username_val,
            "credit": 500,
            "ref_count": 0,
            "ref_credit": 0,
            "projects": [],
            "is_blocked": 0
        }
    
    # Update username if provided
    current_uname = row[5] or ""
    if username_val and username_val != current_uname:
        cursor.execute("UPDATE users SET username = ? WHERE user_id = ?", (username_val, str_id))
        conn.commit()
        current_uname = username_val

    conn.close()
    return {
        "user_id": str_id,
        "username": current_uname,
        "credit": row[0],
        "ref_count": row[1],
        "ref_credit": row[2],
        "projects": json.loads(row[3]) if row[3] else [],
        "is_blocked": row[4]
    }

def db_save_user(u_data):
    str_id = str(u_data["user_id"])
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users 
        SET username = ?, credit = ?, ref_count = ?, ref_credit = ?, projects = ?, is_blocked = ?
        WHERE user_id = ?
    ''', (
        u_data.get("username", ""),
        u_data["credit"],
        u_data["ref_count"],
        u_data["ref_credit"],
        json.dumps(u_data["projects"], ensure_ascii=False),
        u_data.get("is_blocked", 0),
        str_id
    ))
    conn.commit()
    conn.close()

def db_get_all_users():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, credit, ref_count, ref_credit, projects, is_blocked, username FROM users")
    rows = cursor.fetchall()
    conn.close()
    
    users = {}
    for r in rows:
        users[r[0]] = {
            "user_id": r[0],
            "credit": r[1],
            "ref_count": r[2],
            "ref_credit": r[3],
            "projects": json.loads(r[4]) if r[4] else [],
            "is_blocked": r[5],
            "username": r[6] if len(r) > 6 and r[6] else ""
        }
    return users

def db_get_user_spent_coins(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(count) FROM orders WHERE user_id = ?", (str(user_id),))
    row = cursor.fetchone()
    conn.close()
    coin_rate = float(db_get_setting("coin_rate", "1"))
    total_count = row[0] if row and row[0] else 0
    return int(total_count * coin_rate)

def db_get_user_orders_count(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", (str(user_id),))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

def db_add_order(user_id, order_id, channel_name, count, post_link, order_type="Reacts", status="completed"):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO orders (user_id, order_id, channel_name, count, post_link, order_type, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (str(user_id), str(order_id), channel_name, count, post_link, order_type, status, now_str))
    conn.commit()
    conn.close()

def db_get_user_orders(user_id, limit=10):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT order_id, channel_name, count, post_link, created_at
        FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT ?
    ''', (str(user_id), limit))
    rows = cursor.fetchall()
    conn.close()
    return rows

def db_get_all_bot_orders(limit=50):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT order_id, order_type, status
        FROM orders ORDER BY id DESC LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows

# Topup DB Helpers
def db_add_topup_request(user_id, txid, photo_id, amount):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO topup_requests (user_id, txid, photo_id, amount, status, created_at)
        VALUES (?, ?, ?, ?, 'PENDING', ?)
    ''', (str(user_id), str(txid), str(photo_id), int(amount), now_str))
    conn.commit()
    req_id = cursor.lastrowid
    conn.close()
    return req_id

def db_get_pending_topups():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, user_id, txid, photo_id, amount, created_at
        FROM topup_requests WHERE status = 'PENDING' ORDER BY id ASC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return rows

def db_get_topup_by_id(req_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, user_id, txid, photo_id, amount, status, created_at
        FROM topup_requests WHERE id = ?
    ''', (req_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def db_update_topup_status(req_id, status):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE topup_requests SET status = ? WHERE id = ?', (status, req_id))
    conn.commit()
    conn.close()

# States
(STEP_CHANNEL, STEP_COUNT, STEP_VIEWS, 
 STEP_REVIEW, STEP_EDIT_FIELD, STEP_EDIT_VALUE,
 STEP_ADMIN_SEARCH_USER, STEP_ADMIN_BROADCAST, STEP_ADMIN_EDIT_SETTING,
 STEP_TOPUP_AMOUNT, STEP_TOPUP_PHOTO,
 STEP_ADMIN_ADD_COINS, STEP_ADMIN_DEDUCT_COINS) = range(13)

# 🛒 SMM Order Submit Function
def send_smm_order(link, quantity, service_id_override=None):
    api_key = db_get_setting("smm_api_key", "792d092f1f7fdcebcb9233107b2f1f33")
    service_id = service_id_override if service_id_override else db_get_setting("smm_service_id", "1936")
    
    payload = {
        'key': api_key,
        'action': 'add',
        'service': service_id,
        'link': link,
        'quantity': quantity
    }
    try:
        response = requests.post(SMM_API_URL, data=payload, timeout=15)
        res_data = response.json()
        logger.info(f"SMM Panel Response (Service: {service_id}): {res_data}")
        return res_data
    except Exception as e:
        logger.error(f"SMM API Error: {e}")
        return {"error": str(e)}

# 💳 SMM Panel Balance Check Function
def get_smm_balance():
    api_key = db_get_setting("smm_api_key", "792d092f1f7fdcebcb9233107b2f1f33")
    payload = {
        'key': api_key,
        'action': 'balance'
    }
    try:
        response = requests.post(SMM_API_URL, data=payload, timeout=15)
        res_data = response.json()
        logger.info(f"SMM Balance Response: {res_data}")
        return res_data
    except Exception as e:
        logger.error(f"SMM Balance API Error: {e}")
        return {"error": str(e)}

# 📱 Keyboards
def get_user_keyboard():
    kb = [
        [KeyboardButton("⚙️ Setup"), KeyboardButton("👤 Profile")],
        [KeyboardButton("🛠️ Settings"), KeyboardButton("💰 Top-up")],
        [KeyboardButton("📋 Order List"), KeyboardButton("🎧 Support")],
        [KeyboardButton("👥 Refer & Earn")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def get_admin_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📊 Admin Dashboard")],
        [KeyboardButton("👥 Users Report"), KeyboardButton("📢 Send SMS")],
        [KeyboardButton("👤 Search User"), KeyboardButton("🏠 Main Menu")]
    ], resize_keyboard=True)

def get_admin_dashboard_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🤖 Bot Orders"), KeyboardButton("🌐 API Orders")],
        [KeyboardButton("💳 Panel Balance"), KeyboardButton("📋 All Orders")],
        [KeyboardButton("💰 Telegram Super Service"), KeyboardButton("🧪 Services")],
        [KeyboardButton("🔄 Replace OFF ❌"), KeyboardButton("♻️ Refill OFF ❌")],
        [KeyboardButton("❌ Canceled"), KeyboardButton("⚠️ Failed/Partial")],
        [KeyboardButton("💡 Coin Rate Settings"), KeyboardButton("👥 Referral Settings")],
        [KeyboardButton("🏠 Main Menu")]
    ], resize_keyboard=True)

def cancel_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("❌ Cancel")]], resize_keyboard=True)

# 🚀 /start Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    str_id = str(user.id)
    username = user.username or ""

    u_data = db_get_user(str_id, username_val=username)

    if u_data.get("is_blocked", 0) == 1:
        await update.message.reply_text("🚫 আপনাকে এই বটটি ব্যবহার করা থেকে ব্লক করা হয়েছে।")
        return

    if context.args and len(context.args) > 0:
        referrer_id = context.args[0]
        ref_data = db_get_user(referrer_id)
        if referrer_id != str_id and ref_data:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users WHERE user_id = ?", (str_id,))
            exists = cursor.fetchone()[0]
            conn.close()
            
            if exists <= 1 and u_data["ref_count"] == 0:
                ref_bonus = int(db_get_setting("referral_bonus", "100"))
                ref_data["ref_count"] += 1
                ref_data["credit"] += ref_bonus
                ref_data["ref_credit"] += ref_bonus
                db_save_user(ref_data)

    await update.message.reply_text(
        "👋 স্বাগতম!\n"
        "Telegram Super Service\n\n"
        "📢 https://t.me/orderchannelsuperfast",
        reply_markup=get_user_keyboard()
    )

async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ আপনি অ্যাডমিন নন!")
        return

    all_users = db_get_all_users()
    blocked_count = sum(1 for u in all_users.values() if u.get("is_blocked", 0) == 1)

    text = (
        f"📊 **অ্যাডমিন প্যানেল**\n"
        f"───────────────────\n"
        f"👥 মোট ইউজার: {len(all_users)}\n"
        f"🚫 ব্লকড ইউজার: {blocked_count}\n"
        f"───────────────────"
    )
    await update.message.reply_text(text, reply_markup=get_admin_keyboard())

# --- ⚙️ Setup Logic ---
async def start_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u_data = db_get_user(user_id)

    if u_data['credit'] <= 0:
        clean_admin = ADMIN_USERNAME.replace("@", "")
        inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton("💬 Contact Admin", url=f"https://t.me/{clean_admin}")]])
        await update.message.reply_text("⚠️ আপনার পর্যাপ্ত কয়েন নেই!\nনতুন প্রজেক্ট তৈরি করতে দয়া করে রিচার্জ করুন।", reply_markup=inline_kb)
        return ConversationHandler.END

    context.user_data['draft_project'] = {
        "status": "ON",
        "react_status": "ON",
        "view_status": "ON",
        "target_url": None,
        "username": None,
        "emojis": "POSITIVE 👍❤️🔥",
        "count": 100,
        "views": 0
    }

    text = (
        f"🛰 **ধাপ ১ • চ্যানেল সেটআপ**\n"
        f"───────────────────\n\n"
        f"১) আপনার চ্যানেলে @{BOT_USERNAME} কে **অ্যাডমিন** তৈরি করুন।\n"
        f"২) আপনার চ্যানেলের পাবলিক লিংক পাঠান (যেমন: `https://t.me/your_channel`):"
    )
    await update.message.reply_text(text, reply_markup=cancel_keyboard())
    return STEP_CHANNEL

async def save_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    txt = (msg.text or "").strip()

    if txt in ["❌ Cancel", "Cancel", "❌ বাতিল করুন", "বাতিল করুন"]:
        context.user_data.pop('draft_project', None)
        await msg.reply_text("প্রসেস বাতিল করা হয়েছে।", reply_markup=get_user_keyboard())
        return ConversationHandler.END

    if "https://t.me/" not in txt:
        await msg.reply_text("❌ অকার্যকর লিংক! লিংক অবশ্যই 'https://t.me/' দিয়ে শুরু হতে হবে। আবার চেষ্টা করুন:")
        return STEP_CHANNEL

    match = re.search(r'https://t\.me/([^\s/]+)', txt)
    if not match:
        await msg.reply_text("❌ চ্যানেলের লিংক পাওয়া যায়নি! আবার লিংকটি পাঠান:")
        return STEP_CHANNEL

    ch_username = match.group(1).replace("@", "")
    context.user_data['draft_project']['target_url'] = f"https://t.me/{ch_username}"
    context.user_data['draft_project']['username'] = ch_username

    return await render_count_menu(update, context)

# 📊 Step 2 • Reaction Count
async def render_count_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get('draft_project', {})
    text = (
        f"📊 **ধাপ ২ • রিয়্যাকশন সংখ্যা সিলেকশন**\n"
        f"───────────────────\n"
        f"👉 বর্তমান রিয়্যাকশন সংখ্যা: **{draft.get('count', 100)}**"
    )
    keyboard = [
        [InlineKeyboardButton("10", callback_data="cnt_10"), InlineKeyboardButton("20", callback_data="cnt_20"), InlineKeyboardButton("30", callback_data="cnt_30"), InlineKeyboardButton("50", callback_data="cnt_50")],
        [InlineKeyboardButton("100", callback_data="cnt_100"), InlineKeyboardButton("200", callback_data="cnt_200"), InlineKeyboardButton("300", callback_data="cnt_300"), InlineKeyboardButton("500", callback_data="cnt_500")],
        [InlineKeyboardButton("1000", callback_data="cnt_1000"), InlineKeyboardButton("2000", callback_data="cnt_2000"), InlineKeyboardButton("3000", callback_data="cnt_3000"), InlineKeyboardButton("5000", callback_data="cnt_5000")],
        [InlineKeyboardButton("Continue ➔", callback_data="cnt_done")]
    ]
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await context.bot.send_message(chat_id=update.effective_user.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    return STEP_COUNT

async def count_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get('draft_project', {})

    if query.data == "cnt_done":
        return await render_views_menu(update, context)

    draft['count'] = int(query.data.split("_")[1])
    return await render_count_menu(update, context)

# 👁️ Step 3 • Video Views Count
async def render_views_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get('draft_project', {})
    text = (
        f"👁️ **ধাপ ৩ • ভিডিও ভিউ সিলেকশন**\n"
        f"───────────────────\n"
        f"👉 বর্তমান ভিডিও ভিউ: **{draft.get('views', 0)}**\n"
        f"(কোন ভিডিও পোস্ট করা মাত্রই অটোমেটিক ভিউ যোগ হবে)"
    )
    keyboard = [
        [InlineKeyboardButton("0 (OFF)", callback_data="vw_0"), InlineKeyboardButton("10", callback_data="vw_10"), InlineKeyboardButton("20", callback_data="vw_20"), InlineKeyboardButton("30", callback_data="vw_30")],
        [InlineKeyboardButton("50", callback_data="vw_50"), InlineKeyboardButton("100", callback_data="vw_100"), InlineKeyboardButton("200", callback_data="vw_200"), InlineKeyboardButton("500", callback_data="vw_500")],
        [InlineKeyboardButton("1000", callback_data="vw_1000"), InlineKeyboardButton("2000", callback_data="vw_2000"), InlineKeyboardButton("3000", callback_data="vw_3000"), InlineKeyboardButton("5000", callback_data="vw_5000")],
        [InlineKeyboardButton("Finish & Review ✅", callback_data="vw_done")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return STEP_VIEWS

async def views_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get('draft_project', {})

    if query.data == "vw_done":
        return await render_review_menu(update, context)

    draft['views'] = int(query.data.split("_")[1])
    return await render_views_menu(update, context)

# ✨ Final Review
async def render_review_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get('draft_project', {})

    text = (
        f"✨ **চূড়ান্ত তথ্য পর্যালোচনা** ✨\n"
        f"───────────────────\n\n"
        f"🔗 চ্যানেল লিংক: {draft.get('target_url')}\n"
        f"👍 রিয়্যাকশন অপশন: {draft.get('react_status', 'ON')}\n"
        f"👁️ ভিউ অপশন: {draft.get('view_status', 'ON')}\n"
        f"😊 রিয়্যাকশন ইমোজি: {draft.get('emojis')}\n"
        f"🚀 রিয়্যাকশন সংখ্যা: {draft.get('count')}\n"
        f"👁️ ভিডিও ভিউ: {draft.get('views')}\n\n"
        f"সবকিছু ঠিক থাকলে '✅ Create Project' বাটনে ক্লিক করুন।"
    )
    keyboard = [
        [InlineKeyboardButton("✅ Create Project", callback_data="create_final")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return STEP_REVIEW

async def finalize_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    draft = context.user_data.get('draft_project')
    if not draft or not draft.get('target_url'):
        await query.message.reply_text("❌ কিছু ভুল হয়েছে, দয়া করে আবার চেষ্টা করুন!", reply_markup=get_user_keyboard())
        return ConversationHandler.END

    ch_username = draft.get('username')
    try:
        chat_info = await context.bot.get_chat(f"@{ch_username}")
        channel_id = str(chat_info.id)
        channel_title = chat_info.title or ch_username

        try:
            await context.bot.send_message(
                chat_id=chat_info.id,
                text=f"🤖 **বট সফলভাবে কানেক্ট হয়েছে!**\n\n"
                     f"✅ @{BOT_USERNAME} সফলভাবে এই চ্যানেলে যুক্ত হয়েছে।\n"
                     f"🚀 প্রতিটি নতুন পোস্টের জন্য স্বয়ংক্রিয় রিয়্যাকশন ও ভিউ অর্ডার ট্রিগার হবে।"
            )
        except Exception as e:
            logger.warning(f"Failed to send confirmation message to channel: {e}")

    except Exception as e:
        logger.error(f"Failed to fetch channel @{ch_username}: {e}")
        await query.message.reply_text(
            f"❌ চ্যানেলের সাথে কানেক্ট করা সম্ভব হয়নি!\n\n"
            f"⚠️ নিশ্চিত করুন বটটি আপনার চ্যানেলে **অ্যাডমিন** হিসেবে যুক্ত আছে।", 
            reply_markup=get_user_keyboard()
        )
        context.user_data.pop('draft_project', None)
        return ConversationHandler.END

    u_data = db_get_user(user_id)
    draft['channel_id'] = channel_id
    draft['channel_name'] = channel_title

    u_data['projects'] = [p for p in u_data.get('projects', []) if str(p.get('channel_id')) != channel_id]
    u_data['projects'].append(draft)
    db_save_user(u_data)

    context.user_data.pop('draft_project', None)

    await query.message.reply_text(
        f"🎉 **প্রজেক্ট সফলভাবে তৈরি হয়েছে!**\n\n"
        f"📁 চ্যানেল: {channel_title}\n"
        f"🆔 চ্যানেল আইডি: `{channel_id}`\n"
        f"👍 রিয়্যাকশন: {draft.get('react_status', 'ON')}\n"
        f"👁️ ভিউ: {draft.get('view_status', 'ON')}\n"
        f"🚀 রিয়্যাকশন সংখ্যা: {draft['count']}\n"
        f"👁️ ভিডিও ভিউ: {draft['views']}\n\n"
        f"✅ প্রজেক্ট চালু হয়েছে! এখন থেকে পোস্ট করা মাত্রই অটোমেটিক সার্ভিস চালু হয়ে যাবে।",
        reply_markup=get_user_keyboard()
    )
    return ConversationHandler.END

async def cancel_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('draft_project', None)
    context.user_data.pop('edit_target', None)
    context.user_data.pop('admin_edit_key', None)
    context.user_data.pop('topup_data', None)
    context.user_data.pop('admin_action_target', None)
    msg_text = "প্রসেস বাতিল করা হয়েছে।"
    if update.callback_query:
        await update.callback_query.message.reply_text(msg_text, reply_markup=get_user_keyboard())
    else:
        await update.message.reply_text(msg_text, reply_markup=get_user_keyboard())
    return ConversationHandler.END

# 💰 Top-up Flow Logic
async def start_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u_data = db_get_user(user_id)
    
    binance_pay_id = "839892941"
    dollar_rate = db_get_setting("dollar_rate", "1000")
    context.user_data['topup_data'] = {}
    
    text = (
        f"💎 **আপনার বর্তমান ব্যালেন্স:** {u_data['credit']} coins\n"
        f"💵 **রেট:** $1 = {dollar_rate} Coins\n\n"
        f"🟡 **Binance Pay ID:** `{binance_pay_id}`\n\n"
        f"👉 **ধাপ ১:** কত ডলার ডিপোজিট করেছেন তা লিখুন (যেমন: `1`, `5`, `10`):"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=cancel_keyboard())
    return STEP_TOPUP_AMOUNT

async def save_topup_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt in ["❌ Cancel", "Cancel", "❌ বাতিল করুন", "বাতিল করুন"]:
        context.user_data.pop('topup_data', None)
        await update.message.reply_text("টপ-আপ প্রসেস বাতিল করা হয়েছে।", reply_markup=get_user_keyboard())
        return ConversationHandler.END
        
    try:
        usd_val = float(txt)
        if usd_val <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ অকার্যকর পরিমাণ! শুধুমাত্র সঠিক সংখ্যা লিখুন (যেমন: 1, 5, 10):")
        return STEP_TOPUP_AMOUNT

    dollar_rate = float(db_get_setting("dollar_rate", "1000"))
    calc_coins = int(usd_val * dollar_rate)

    context.user_data['topup_data']['usd_amount'] = usd_val
    context.user_data['topup_data']['amount'] = calc_coins

    await update.message.reply_text(
        f"💰 **আপনার ডিপোজিট:** ${usd_val} = **{calc_coins} Coins**\n\n"
        f"👉 **ধাপ ২:** আপনার পেমেন্টের **স্ক্রিনশট (Photo)** টি পাঠান:",
        reply_markup=cancel_keyboard()
    )
    return STEP_TOPUP_PHOTO

async def save_topup_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg.text and msg.text in ["❌ Cancel", "Cancel", "❌ বাতিল করুন", "বাতিল করুন"]:
        context.user_data.pop('topup_data', None)
        await update.message.reply_text("টপ-আপ প্রসেস বাতিল করা হয়েছে।", reply_markup=get_user_keyboard())
        return ConversationHandler.END

    if not msg.photo:
        await update.message.reply_text("❌ দয়া করে পেমেন্টের একটি স্ক্রিনশট (Photo) পাঠান:")
        return STEP_TOPUP_PHOTO

    photo_id = msg.photo[-1].file_id
    user_id = update.effective_user.id
    topup_info = context.user_data.get('topup_data', {})
    amount = topup_info.get('amount', 0)
    usd_amount = topup_info.get('usd_amount', 0)
    txid = "N/A"

    req_id = db_add_topup_request(user_id, txid, photo_id, amount)
    context.user_data.pop('topup_data', None)

    await msg.reply_text(
        f"🎉 **আপনার টপ-আপ আবেদন সফলভাবে জমা হয়েছে!**\n\n"
        f"🆔 **আবেদন আইডি:** `#{req_id}`\n"
        f"💵 **আমোউন্ট:** ${usd_amount} ({amount} Coins)\n\n"
        f"⏳ অ্যাডমিন যাচাই করে খুব শীঘ্রই আপনার ব্যালেন্স যোগ করে দেবে।",
        reply_markup=get_user_keyboard()
    )
    return ConversationHandler.END

# 💳 Top-up Approve / Reject Callback
async def topup_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if query.from_user.id not in ADMIN_IDS:
        return

    if data.startswith("topup_approve_"):
        req_id = int(data.split("_")[2])
        req = db_get_topup_by_id(req_id)
        if not req:
            await query.message.reply_text("❌ আবেদনটি পাওয়া যায়নি।")
            return

        rid, uid, txid, photo_id, amount, status, created_at = req
        if status != 'PENDING':
            await query.message.reply_text(f"⚠️ এই আবেদনটি ইতোমধ্যে {status} করা হয়েছে।")
            return

        db_update_topup_status(req_id, 'APPROVED')

        u_data = db_get_user(uid)
        u_data['credit'] += amount
        db_save_user(u_data)

        if query.message.caption:
            await query.edit_message_caption(
                caption=f"{query.message.caption}\n\n✅ **স্ট্যাটাস: APPROVED** (কয়েন যোগ করা হয়েছে: {amount})"
            )

        try:
            await context.bot.send_message(
                chat_id=int(uid),
                text=f"🎉 **আপনার টপ-আপ আবেদন অনুমোদিত হয়েছে!**\n\n"
                     f"💰 যোগকৃত কয়েন: {amount}\n"
                     f"💳 বর্তমান ব্যালেন্স: {u_data['credit']} Coins"
            )
        except Exception as e:
            logger.error(f"Failed to notify user for approved topup: {e}")

    elif data.startswith("topup_reject_"):
        req_id = int(data.split("_")[2])
        req = db_get_topup_by_id(req_id)
        if not req:
            await query.message.reply_text("❌ আবেদনটি পাওয়া যায়নি।")
            return

        rid, uid, txid, photo_id, amount, status, created_at = req
        if status != 'PENDING':
            await query.message.reply_text(f"⚠️ এই আবেদনটি ইতোমধ্যে {status} করা হয়েছে।")
            return

        db_update_topup_status(req_id, 'REJECTED')

        if query.message.caption:
            await query.edit_message_caption(
                caption=f"{query.message.caption}\n\n❌ **স্ট্যাটাস: REJECTED**"
            )

        try:
            await context.bot.send_message(
                chat_id=int(uid),
                text=f"❌ **আপনার টপ-আপ আবেদন বাতিল করা হয়েছে!**\n\n"
                     f"প্রয়োজনে এডমিনের সাথে যোগাযোগ করুন।"
            )
        except Exception as e:
            logger.error(f"Failed to notify user for rejected topup: {e}")

# 🛠️ Project Action Callback
async def project_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    data = query.data

    u_data = db_get_user(user_id)
    projects = u_data.get('projects', [])

    if data.startswith("p_togreact_"):
        idx = int(data.split("_")[2])
        if 0 <= idx < len(projects):
            curr = projects[idx].get('react_status', 'ON')
            projects[idx]['react_status'] = "OFF" if curr == "ON" else "ON"
            db_save_user(u_data)
            await query.message.reply_text(f"✅ Reaction Status পরিবর্তিত হয়ে **{projects[idx]['react_status']}** হয়েছে!")
            return await show_my_projects(query.message, user_id)

    elif data.startswith("p_togview_"):
        idx = int(data.split("_")[2])
        if 0 <= idx < len(projects):
            curr = projects[idx].get('view_status', 'ON')
            projects[idx]['view_status'] = "OFF" if curr == "ON" else "ON"
            db_save_user(u_data)
            await query.message.reply_text(f"✅ Views Status পরিবর্তিত হয়ে **{projects[idx]['view_status']}** হয়েছে!")
            return await show_my_projects(query.message, user_id)

    elif data.startswith("p_edit_"):
        idx = int(data.split("_")[2])
        if 0 <= idx < len(projects):
            proj = projects[idx]
            kb = [
                [InlineKeyboardButton("📢 Edit Channel", callback_data=f"fe_{idx}_channel")],
                [InlineKeyboardButton("📊 Edit Reaction Count", callback_data=f"fe_{idx}_count")],
                [InlineKeyboardButton("👁️ Edit Views Count", callback_data=f"fe_{idx}_views")],
                [InlineKeyboardButton("🔙 Back", callback_data="p_back")]
            ]
            await query.edit_message_text(
                f"✏️ **এডিট:** {proj.get('channel_name')}\n\n"
                f"কোন অপশনটি পরিবর্তন করতে চান সিলেক্ট করুন:",
                reply_markup=InlineKeyboardMarkup(kb)
            )

    elif data.startswith("fe_"):
        parts = data.split("_")
        idx, field = int(parts[1]), parts[2]
        context.user_data['edit_target'] = {'idx': idx, 'field': field}
        
        prompt_messages = {
            "channel": "✍️ **নতুন চ্যানেলের লিংক পাঠান:**\n(যেমন: `https://t.me/your_channel`) \n\n⚠️ নিশ্চিত করুন বটটি নতুন চ্যানেলে অ্যাডমিন আছে!",
            "count": "✍️ **নতুন রিয়্যাকশন সংখ্যা পাঠান:**\n(যেমন: `100`, `200`, `500`)",
            "views": "✍️ **নতুন ভিডিও ভিউ সংখ্যা পাঠান:**\n(যেমন: `0`, `100`, `500`)"
        }
        
        msg_to_send = prompt_messages.get(field, "✍️ **নতুন মান লিখে পাঠান:**")
        await query.message.reply_text(msg_to_send, reply_markup=cancel_keyboard())
        return STEP_EDIT_VALUE

    elif data == "p_back":
        await show_my_projects(query.message, user_id)

async def save_edited_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val_txt = update.message.text.strip()
    if val_txt in ["❌ Cancel", "Cancel", "❌ বাতিল করুন", "বাতিল করুন"]:
        context.user_data.pop('edit_target', None)
        await update.message.reply_text("এডিট বাতিল করা হয়েছে।", reply_markup=get_user_keyboard())
        return ConversationHandler.END

    target = context.user_data.get('edit_target')
    if not target:
        await update.message.reply_text("❌ কিছু ভুল হয়েছে!", reply_markup=get_user_keyboard())
        return ConversationHandler.END

    user_id = str(update.effective_user.id)
    u_data = db_get_user(user_id)
    projects = u_data.get('projects', [])

    idx = target['idx']
    field = target['field']

    if 0 <= idx < len(projects):
        if field == 'channel':
            if "https://t.me/" not in val_txt:
                await update.message.reply_text("❌ অকার্যকর লিংক! লিংক অবশ্যই 'https://t.me/' দিয়ে শুরু হতে হবে। আবার চেষ্টা করুন:")
                return STEP_EDIT_VALUE

            match = re.search(r'https://t\.me/([^\s/]+)', val_txt)
            if not match:
                await update.message.reply_text("❌ চ্যানেলের লিংক পাওয়া যায়নি! আবার লিংকটি পাঠান:")
                return STEP_EDIT_VALUE

            ch_username = match.group(1).replace("@", "")
            try:
                chat_info = await context.bot.get_chat(f"@{ch_username}")
                projects[idx]['channel_id'] = str(chat_info.id)
                projects[idx]['channel_name'] = chat_info.title or ch_username
                projects[idx]['target_url'] = f"https://t.me/{ch_username}"
                projects[idx]['username'] = ch_username
            except Exception as e:
                await update.message.reply_text("❌ বট চ্যানেলে এক্সেস করতে পারছে না! বটটি সেই চ্যানেলে **অ্যাডমিন** আছে কিনা নিশ্চিত হয়ে আবার লিংক পাঠান:")
                return STEP_EDIT_VALUE

        elif field in ['count', 'views']:
            try:
                projects[idx][field] = int(val_txt)
            except ValueError:
                await update.message.reply_text("❌ দয়া করে শুধুমাত্র সংখ্যা লিখুন!")
                return STEP_EDIT_VALUE
        else:
            projects[idx][field] = val_txt

        db_save_user(u_data)
        context.user_data.pop('edit_target', None)
        await update.message.reply_text("🎉 **সফলভাবে আপডেট করা হয়েছে!**", reply_markup=get_user_keyboard())
    
    return ConversationHandler.END

# 📂 Display Projects function
async def show_my_projects(message_obj, user_id):
    u_data = db_get_user(user_id)
    projects = u_data.get('projects', [])

    if not projects:
        await message_obj.reply_text("❌ আপনার কোনো সক্রিয় প্রজেক্ট নেই।")
        return

    for idx, p in enumerate(projects):
        r_st = p.get('react_status', 'ON')
        v_st = p.get('view_status', 'ON')
        
        btn_react_text = "👍 React: ON ✅" if r_st == "ON" else "👍 React: OFF ❌"
        btn_view_text = "👁️ Views: ON ✅" if v_st == "ON" else "👁️ Views: OFF ❌"
        
        kb = [
            [InlineKeyboardButton(btn_react_text, callback_data=f"p_togreact_{idx}"), InlineKeyboardButton(btn_view_text, callback_data=f"p_togview_{idx}")],
            [InlineKeyboardButton("✏️ Edit Settings", callback_data=f"p_edit_{idx}")]
        ]
        p_text = (
            f"🛠️ **প্রজেক্ট সেটিংস #{idx+1}: {p.get('channel_name', 'চ্যানেল')}**\n"
            f"───────────────────\n"
            f"🔗 লিংক: {p.get('target_url')}\n"
            f"👍 রিয়্যাকশন সার্ভিস: **{r_st}**\n"
            f"👁️ ভিডিও ভিউ সার্ভিস: **{v_st}**\n"
            f"🚀 রিয়্যাকশন সংখ্যা: **{p.get('count', 100)}**\n"
            f"👁️ ভিউ সংখ্যা: **{p.get('views', 0)}**\n"
            f"😊 ইমোজি: **{p.get('emojis', 'POSITIVE')}**"
        )
        await message_obj.reply_text(p_text, reply_markup=InlineKeyboardMarkup(kb))

# 📋 Display Completed Orders List
async def show_order_list(message_obj, user_id):
    orders = db_get_user_orders(user_id)
    if not orders:
        await message_obj.reply_text("📋 **অর্ডার তালিকা**\n───────────────────\n❌ কোনো সমাপ্ত অর্ডার পাওয়া যায়নি।")
        return

    text = "📋 **সম্পন্ন অর্ডার তালিকা**\n───────────────────\n\n"
    for o in orders:
        order_id, channel_name, count, post_link, created_at = o
        text += (
            f"🆔 **অর্ডার আইডি:** `{order_id}`\n"
            f"📢 **চ্যানেল:** {channel_name}\n"
            f"✨ **রিয়্যাকশন:** {count}\n"
            f"📅 **তারিখ:** {created_at}\n"
            f"🔗 **পোস্ট:** [পোস্ট দেখুন]({post_link})\n"
            f"───────────────\n"
        )
    await message_obj.reply_text(text, disable_web_page_preview=True)

# 🚀 Core Auto-Reaction Post Monitor
async def auto_react_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.channel_post or update.edited_channel_post
    if not msg or not msg.chat:
        return

    media_group_id = msg.media_group_id
    if media_group_id:
        if media_group_id in PROCESSED_MEDIA_GROUPS:
            logger.info(f"⏩ Media group {media_group_id} already processed. Skipping duplicate image.")
            return
        PROCESSED_MEDIA_GROUPS.add(media_group_id)
        if len(PROCESSED_MEDIA_GROUPS) > 1000:
            PROCESSED_MEDIA_GROUPS.clear()
        
        await asyncio.sleep(2)

    raw_channel_id = str(msg.chat.id)
    chat_username = (msg.chat.username or "").lower()
    post_id = msg.message_id

    logger.info(f"📢 [POST DETECTED] Channel ID: {raw_channel_id} | Username: @{chat_username} | Message ID: {post_id}")

    matched_projects = []
    all_users = db_get_all_users()

    for uid, uinfo in all_users.items():
        for proj in uinfo.get("projects", []):
            proj_cid = str(proj.get("channel_id", ""))
            proj_uname = str(proj.get("username", "")).lower().replace("@", "")

            if (proj_cid and proj_cid == raw_channel_id) or \
               (chat_username and proj_uname == chat_username) or \
               (proj_cid.replace("-100", "") == raw_channel_id.replace("-100", "")):
                matched_projects.append((uid, uinfo, proj))

    if not matched_projects:
        return

    coin_rate = float(db_get_setting("coin_rate", "1"))
    view_service_id = db_get_setting("smm_view_service_id", "7294")

    for uid, uinfo, proj in matched_projects:
        user_chat_id = int(uid)
        ch_name = proj.get("channel_name", "Channel")
        reaction_count = proj.get("count", 100)
        views_count = proj.get("views", 0)
        
        react_status = proj.get("react_status", "ON")
        view_status = proj.get("view_status", "ON")

        if react_status == "OFF" and view_status == "OFF":
            logger.info(f"⏸️ Reaction & Views both OFF for Channel {ch_name}. Skipping order.")
            continue

        needed_coins = int(reaction_count * coin_rate) if react_status == "ON" else 0

        if chat_username:
            post_link = f"https://t.me/{chat_username}/{post_id}"
        elif proj.get("username"):
            post_link = f"https://t.me/{proj.get('username')}/{post_id}"
        else:
            clean_cid = raw_channel_id.replace("-100", "")
            post_link = f"https://t.me/c/{clean_cid}/{post_id}"

        if react_status == "ON" and uinfo.get("credit", 0) < needed_coins:
            try:
                await context.bot.send_message(
                    chat_id=user_chat_id,
                    text=f"⚠️ **পর্যাপ্ত ব্যালেন্স নেই!**\n\n"
                         f"📢 **চ্যানেল:** {ch_name}\n"
                         f"📌 **পোস্ট লিংক:** {post_link}\n"
                         f"প্রয়োজনীয় কয়েন: {needed_coins}\n"
                         f"অবশিষ্ট কয়েন: {uinfo.get('credit', 0)}\n\n"
                         f"দয়া করে আপনার অ্যাকাউন্ট ব্যালেন্স রিচার্জ করুন।"
                )
            except Exception as e:
                logger.error(f"Error sending low balance msg: {e}")
            continue

        # Send Reaction Order if Reaction is ON
        if react_status == "ON":
            smm_res = send_smm_order(post_link, reaction_count)

            if smm_res and "order" in smm_res:
                order_id = smm_res["order"]
                uinfo["credit"] -= needed_coins
                db_save_user(uinfo)
                db_add_order(uid, order_id, ch_name, reaction_count, post_link, order_type="Reacts", status="completed")

                log_message = (
                    f" ORDER UPDATE\n"
                    f"#{order_id}\n"
                    f"Reacts|{reaction_count}\n"
                    f"PENDING"
                )

                try:
                    await context.bot.send_message(
                        chat_id=LOG_CHANNEL,
                        text=log_message
                    )
                except Exception as e:
                    logger.error(f"Failed to send order success alert to {LOG_CHANNEL}: {e}")
            else:
                err_msg = smm_res.get("error") or smm_res.get("message") or "SMM Server Response Error"
                post_btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 View Post", url=post_link)]])
                try:
                    await context.bot.send_message(
                        chat_id=user_chat_id,
                        text=f"❌ **রিয়্যাকশন অর্ডার প্রদান ব্যর্থ হয়েছে!**\n\n"
                             f"📢 **চ্যানেল:** {ch_name}\n"
                             f"⚠️ **কারণ:** `{err_msg}`\n\n"
                             f"📌 **পোস্ট লিংক:** {post_link}",
                        reply_markup=post_btn
                    )
                except Exception as e:
                    logger.error(f"Failed to send order fail alert: {e}")

        # Send Video Views Order if Views is ON & views_count > 0
        if view_status == "ON" and views_count > 0:
            view_res = send_smm_order(post_link, views_count, service_id_override=view_service_id)
            logger.info(f"📹 Video View Order Response: {view_res}")
            if view_res and "order" in view_res:
                db_add_order(uid, view_res["order"], ch_name, views_count, post_link, order_type="Views", status="completed")

# 👑 Admin Handlers: Search User & Actions (Image replica)
def build_user_card_text_and_markup(uid):
    u_data = db_get_user(uid)
    if not u_data:
        return None, None

    coins = u_data.get('credit', 0)
    spent = db_get_user_spent_coins(uid)
    total_orders = db_get_user_orders_count(uid)

    projects = u_data.get('projects', [])
    if projects:
        channels_str = ", ".join([p.get('channel_name', 'Channel') for p in projects])
    else:
        channels_str = "None"

    is_b = u_data.get("is_blocked", 0) == 1
    status_str = "Banned 🔴" if is_b else "Active 🟢"
    ban_btn_text = "🟢 Unban" if is_b else "🔴 Ban"

    text = (
        f"👤 User: `{uid}`\n"
        f"💰 {coins} | 💸 {spent}\n"
        f"✅ Orders: {total_orders}\n"
        f"🔗 {channels_str}\n"
        f"🚫 {status_str}"
    )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add", callback_data=f"uact_add_{uid}"),
            InlineKeyboardButton("➖ Deduct", callback_data=f"uact_deduct_{uid}")
        ],
        [
            InlineKeyboardButton(f"{ban_btn_text}", callback_data=f"uact_ban_{uid}"),
            InlineKeyboardButton("📋 Orders", callback_data=f"uact_orders_{uid}")
        ]
    ])

    return text, kb

async def start_search_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return ConversationHandler.END
    await update.message.reply_text("🔍 **ইউজার ID লিখুন:**", reply_markup=cancel_keyboard())
    return STEP_ADMIN_SEARCH_USER

async def process_admin_search_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt in ["❌ Cancel", "Cancel", "❌ বাতিল করুন", "বাতিল করুন"]:
        await update.message.reply_text("অনুসন্ধান বাতিল করা হয়েছে।", reply_markup=get_admin_keyboard())
        return ConversationHandler.END

    u_data = db_get_user(txt)
    if u_data:
        card_text, card_kb = build_user_card_text_and_markup(txt)
        await update.message.reply_text(card_text, reply_markup=card_kb, parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ ডাটাবেজে এই ইউজার আইডিটি পাওয়া যায়নি!", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

# Admin Inline Action Callback (Add, Deduct, Ban, Orders)
async def admin_user_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id not in ADMIN_IDS:
        return

    data = query.data
    parts = data.split("_")
    action = parts[1]
    target_uid = parts[2]

    if action == "add":
        context.user_data['admin_action_target'] = target_uid
        await query.message.reply_text(
            f"➕ **ইউজার ID `{target_uid}` এর সাথে কত কয়েন যোগ করতে চান লিখুন:**",
            reply_markup=cancel_keyboard()
        )
        return STEP_ADMIN_ADD_COINS

    elif action == "deduct":
        context.user_data['admin_action_target'] = target_uid
        await query.message.reply_text(
            f"➖ **ইউজার ID `{target_uid}` এর অ্যাকাউন্ট থেকে কত কয়েন কাটতে চান লিখুন:**",
            reply_markup=cancel_keyboard()
        )
        return STEP_ADMIN_DEDUCT_COINS

    elif action == "ban":
        u_data = db_get_user(target_uid)
        if u_data:
            current_block = u_data.get("is_blocked", 0)
            u_data["is_blocked"] = 0 if current_block == 1 else 1
            db_save_user(u_data)

            card_text, card_kb = build_user_card_text_and_markup(target_uid)
            try:
                await query.edit_message_text(card_text, reply_markup=card_kb, parse_mode="Markdown")
            except Exception:
                await query.message.reply_text(card_text, reply_markup=card_kb, parse_mode="Markdown")

    elif action == "orders":
        orders = db_get_user_orders(target_uid, limit=50)
        if not orders:
            await query.message.reply_text(f"📋 **ইউজার `{target_uid}` এর কোনো অর্ডার হিস্ট্রি পাওয়া যায়নি।**")
            return

        orders_text = f"📋 **ইউজার `{target_uid}` এর শেষ ৫০টি অর্ডার:**\n───────────────────\n"
        for o in orders:
            oid, ch_name, count, link, created_at = o
            orders_text += f"🆔 #{oid} | 📢 {ch_name} | 🚀 {count} | 📅 {created_at}\n"

        if len(orders_text) > 4000:
            for chunk in [orders_text[i:i+4000] for i in range(0, len(orders_text), 4000)]:
                await query.message.reply_text(chunk)
        else:
            await query.message.reply_text(orders_text)

async def process_admin_add_coins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt in ["❌ Cancel", "Cancel", "❌ বাতিল করুন", "বাতিল করুন"]:
        context.user_data.pop('admin_action_target', None)
        await update.message.reply_text("বাতিল করা হয়েছে।", reply_markup=get_admin_keyboard())
        return ConversationHandler.END

    target_uid = context.user_data.get('admin_action_target')
    if not target_uid or not txt.isdigit():
        await update.message.reply_text("❌ দয়া করে একটি সঠিক ধনাত্মক সংখ্যা লিখুন!")
        return STEP_ADMIN_ADD_COINS

    amount = int(txt)
    u_data = db_get_user(target_uid)
    u_data['credit'] += amount
    db_save_user(u_data)

    context.user_data.pop('admin_action_target', None)
    await update.message.reply_text(f"✅ ইউজার `{target_uid}` কে সফলভাবে **{amount} Coins** প্রদান করা হয়েছে!", reply_markup=get_admin_keyboard())

    card_text, card_kb = build_user_card_text_and_markup(target_uid)
    await update.message.reply_text(card_text, reply_markup=card_kb, parse_mode="Markdown")
    return ConversationHandler.END

async def process_admin_deduct_coins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt in ["❌ Cancel", "Cancel", "❌ বাতিল করুন", "বাতিল করুন"]:
        context.user_data.pop('admin_action_target', None)
        await update.message.reply_text("বাতিল করা হয়েছে।", reply_markup=get_admin_keyboard())
        return ConversationHandler.END

    target_uid = context.user_data.get('admin_action_target')
    if not target_uid or not txt.isdigit():
        await update.message.reply_text("❌ দয়া করে একটি সঠিক ধনাত্মক সংখ্যা লিখুন!")
        return STEP_ADMIN_DEDUCT_COINS

    amount = int(txt)
    u_data = db_get_user(target_uid)
    u_data['credit'] = max(0, u_data['credit'] - amount)
    db_save_user(u_data)

    context.user_data.pop('admin_action_target', None)
    await update.message.reply_text(f"✅ ইউজার `{target_uid}` এর অ্যাকাউন্ট থেকে **{amount} Coins** কেটে নেওয়া হয়েছে!", reply_markup=get_admin_keyboard())

    card_text, card_kb = build_user_card_text_and_markup(target_uid)
    await update.message.reply_text(card_text, reply_markup=card_kb, parse_mode="Markdown")
    return ConversationHandler.END

async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return ConversationHandler.END
    await update.message.reply_text("📢 **সব ইউজারের কাছে পাঠানোর জন্য বার্তাটি (SMS) পাঠান:**", reply_markup=cancel_keyboard())
    return STEP_ADMIN_BROADCAST

async def process_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_text = update.message.text
    if msg_text in ["❌ Cancel", "Cancel", "❌ বাতিল করুন", "বাতিল করুন"]:
        await update.message.reply_text("ব্রডকাস্ট বাতিল করা হয়েছে।", reply_markup=get_admin_keyboard())
        return ConversationHandler.END

    count = 0
    all_users = db_get_all_users()
    for uid in all_users:
        try:
            await context.bot.send_message(chat_id=int(uid), text=f"📢 **নোটিশ:**\n\n{msg_text}")
            count += 1
            await asyncio.sleep(0.05)
        except Exception: pass
    await update.message.reply_text(f"🎉 বার্তাটি সফলভাবে {count} জন ইউজারের কাছে পাঠানো হয়েছে!", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

# ⚙️ Dynamic Settings Edit Handlers
async def admin_settings_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("edit_setting_"):
        key = data.replace("edit_setting_", "")
        context.user_data['admin_edit_key'] = key
        
        prompts = {
            "smm_api_key": "🔑 **নতুন SMM Panel API Key পাঠান:**",
            "smm_service_id": "🧪 **নতুন SMM Reaction Service ID পাঠান:**",
            "smm_view_service_id": "👁️ **নতুন SMM View Service ID পাঠান:**",
            "coin_rate": "💡 **নতুন Reaction Coin Rate লিখুন:**\n(যেমন: `1` মানে ১ কয়েন = ১টি রিয়েকশন, `0.5` মানে ১ কয়েন = ২টি রিয়েকশন)",
            "dollar_rate": "💵 **নতুন Dollar Rate ($1 = ? Coins) লিখুন:**\n(যেমন: `1000` মানে $1 = 1000 Coins)",
            "referral_bonus": "👥 **রেফারেল বোনাসের নতুন Coins সংখ্যা লিখুন:**\n(যেমন: `100`, `200`)"
        }
        await query.message.reply_text(prompts.get(key, "✍️ নতুন মান লিখে পাঠান:"), reply_markup=cancel_keyboard())
        return STEP_ADMIN_EDIT_SETTING

async def process_admin_edit_setting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt in ["❌ Cancel", "Cancel", "❌ বাতিল করুন", "বাতিল করুন"]:
        context.user_data.pop('admin_edit_key', None)
        await update.message.reply_text("এডিট বাতিল করা হয়েছে।", reply_markup=get_admin_dashboard_keyboard())
        return ConversationHandler.END

    key = context.user_data.get('admin_edit_key')
    if not key:
        await update.message.reply_text("❌ কিছু ভুল হয়েছে!", reply_markup=get_admin_dashboard_keyboard())
        return ConversationHandler.END

    db_set_setting(key, txt)
    context.user_data.pop('admin_edit_key', None)
    await update.message.reply_text(f"🎉 **{key.upper()} সফলভাবে আপডেট করা হয়েছে:** `{txt}`", reply_markup=get_admin_dashboard_keyboard())
    return ConversationHandler.END

# Menu Handlers
async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    str_id = str(user_id)
    username = update.effective_user.username or ""
    text = (update.message.text or "").strip()
    
    u_data = db_get_user(str_id, username_val=username)

    if text and text.lower() in ["admin", "অ্যাডমিন"]:
        return await admin_panel_command(update, context)

    # Check for direct Admin Credit addition format: "USER_ID AMOUNT"
    if user_id in ADMIN_IDS and len(text.split()) == 2:
        parts = text.split()
        if parts[0].isdigit() and (parts[1].isdigit() or (parts[1].startswith('-') and parts[1][1:].isdigit())):
            target_id, amount = parts[0], int(parts[1])
            target_u = db_get_user(target_id)
            if target_u:
                target_u['credit'] += amount
                db_save_user(target_u)
                await update.message.reply_text(f"✅ ইউজার `{target_id}` এর নতুন ব্যালেন্স: {target_u['credit']} Coins", reply_markup=get_admin_keyboard())
                return

    # 👑 Admin Actions
    if user_id in ADMIN_IDS:
        if text == "📊 Admin Dashboard":
            return await update.message.reply_text("📊 **অ্যাডমিন ড্যাশবোর্ড সেটিংস:**", reply_markup=get_admin_dashboard_keyboard())
        
        elif text == "🤖 Bot Orders":
            bot_orders = db_get_all_bot_orders(50)
            if not bot_orders:
                return await update.message.reply_text("🤖 **Bot Orders**\n\n❌ কোন অর্ডার পাওয়া যায়নি।", reply_markup=get_admin_dashboard_keyboard())
            
            res_text = "Bot Orders\n\n"
            for order in bot_orders:
                oid, otype, ostatus = order
                res_text += f"#{oid}|{otype}|{ostatus}\n"
            
            return await update.message.reply_text(res_text, reply_markup=get_admin_dashboard_keyboard())

        elif text == "📋 All Orders":
            pending_topups = db_get_pending_topups()
            if not pending_topups:
                return await update.message.reply_text("📋 **সকল পেমেন্ট আবেদন**\n───────────────────\n❌ বর্তমানে কোনো পেন্ডিং টপ-আপ আবেদন নেই।", reply_markup=get_admin_dashboard_keyboard())
            
            await update.message.reply_text(f"📋 **মোট {len(pending_topups)} টি পেন্ডিং টপ-আপ আবেদন রয়েছে:**")
            
            for req in pending_topups:
                rid, uid, txid, photo_id, amount, created_at = req
                caption_text = (
                    f"💳 **পেন্ডিং টপ-আপ আবেদন #{rid}**\n"
                    f"───────────────────\n"
                    f"👤 **ইউজার আইডি:** `{uid}`\n"
                    f"💰 **আবেদনের কয়েন:** {amount}\n"
                    f"📅 **তারিখ:** {created_at}"
                )
                kb = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Approve", callback_data=f"topup_approve_{rid}"),
                        InlineKeyboardButton("❌ Reject", callback_data=f"topup_reject_{rid}")
                    ]
                ])
                try:
                    await update.message.reply_photo(photo=photo_id, caption=caption_text, reply_markup=kb)
                except Exception as e:
                    await update.message.reply_text(f"{caption_text}\n\n⚠️ ছবি দেখতে সমস্যা হচ্ছে।", reply_markup=kb)
            return

        elif text == "🌐 API Orders":
            curr_key = db_get_setting("smm_api_key", "792d092f1f7fdcebcb9233107b2f1f33")
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("✏️ Edit API Key", callback_data="edit_setting_smm_api_key")]])
            return await update.message.reply_text(f"🌐 **SMM Panel API Key:**\n\n`{curr_key}`", reply_markup=kb)

        elif text in ["💳 Panel Balance", "panel balance"]:
            bal_res = get_smm_balance()
            if bal_res and "balance" in bal_res:
                bal = bal_res.get("balance", "0")
                currency = bal_res.get("currency", "USD")
                await update.message.reply_text(
                    f"💳 **SMM Panel Balance:**\n───────────────────\n"
                    f"💰 Current Balance: **{bal} {currency}**",
                    reply_markup=get_admin_dashboard_keyboard()
                )
            else:
                err = bal_res.get("error") or bal_res.get("message") or "Unknown error"
                await update.message.reply_text(
                    f"❌ **Panel Balance Fetch Failed!**\n\nReason: `{err}`",
                    reply_markup=get_admin_dashboard_keyboard()
                )
            return

        elif text == "🧪 Services":
            curr_svc = db_get_setting("smm_service_id", "1936")
            curr_view_svc = db_get_setting("smm_view_service_id", "7294")
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Edit Reaction Service ID", callback_data="edit_setting_smm_service_id")],
                [InlineKeyboardButton("✏️ Edit View Service ID", callback_data="edit_setting_smm_view_service_id")]
            ])
            return await update.message.reply_text(
                f"🧪 **SMM Services ID:**\n───────────────────\n"
                f"👍 **Reaction Service ID:** `{curr_svc}`\n"
                f"👁️ **Video View Service ID:** `{curr_view_svc}`", 
                reply_markup=kb
            )

        elif text == "💡 Coin Rate Settings":
            curr_rate = db_get_setting("coin_rate", "1")
            curr_dollar = db_get_setting("dollar_rate", "1000")
            
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Edit Reaction Coin Rate", callback_data="edit_setting_coin_rate")],
                [InlineKeyboardButton("✏️ Edit Dollar Rate ($1 = ? Coins)", callback_data="edit_setting_dollar_rate")]
            ])
            return await update.message.reply_text(
                f"💡 **কয়েন রেট সেটিংস:**\n───────────────────\n"
                f"📌 প্রতি রিয়্যাকশনে কয়েন: **{curr_rate} Coins**\n"
                f"💵 ডলারে কয়েন রেট: **$1 = {curr_dollar} Coins**\n\n"
                f"যেকোনো রেট পরিবর্তন করতে নিচের অপশন বেছে নিন:", 
                reply_markup=kb
            )

        elif text == "👥 Referral Settings":
            curr_ref = db_get_setting("referral_bonus", "100")
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("✏️ Edit Ref Bonus", callback_data="edit_setting_referral_bonus")]])
            return await update.message.reply_text(
                f"👥 **রেফারেল সেটিংস:**\n───────────────────\n"
                f"বর্তমান বোনাস: **প্রতি রেফারে {curr_ref} কয়েন**\n\n"
                f"রেফারেল বোনাস কয়েন পরিবর্তন করতে নিচের বাটনে ক্লিক করুন।", 
                reply_markup=kb
            )

        elif text in ["💰 Telegram Super Service", 
                      "🔄 Replace OFF ❌", "♻️ Refill OFF ❌", "❌ Canceled", 
                      "⚠️ Failed/Partial"]:
            return await update.message.reply_text(f"⚙️ **{text}** অপশনটি সিলেক্ট করা হয়েছে।", reply_markup=get_admin_dashboard_keyboard())

        elif text == "👥 Users Report":
            all_u = db_get_all_users()
            u_list = "👥 **ইউজার রিপোর্ট:**\n───────────────────\n\n"
            for uid, uinfo in list(all_u.items())[:30]:
                uname = f"@{uinfo['username']}" if uinfo.get('username') else "N/A"
                projects = uinfo.get('projects', [])
                if projects:
                    ch_names = ", ".join([p.get('channel_name', 'Channel') for p in projects])
                else:
                    ch_names = "None"
                
                spent_coins = db_get_user_spent_coins(uid)

                u_list += (
                    f"👤 **Username:** {uname}\n"
                    f"🆔 **ID:** `{uid}`\n"
                    f"📢 **Channel:** {ch_names}\n"
                    f"💰 **Coins:** {uinfo.get('credit', 0)} | 💸 **Spent:** {spent_coins}\n"
                    f"───────────────\n"
                )
            
            if len(u_list) > 4000:
                for chunk in [u_list[i:i+4000] for i in range(0, len(u_list), 4000)]:
                    await update.message.reply_text(chunk, reply_markup=get_admin_keyboard())
            else:
                await update.message.reply_text(u_list, reply_markup=get_admin_keyboard())
            return

        elif text == "🏠 Main Menu":
            return await update.message.reply_text("🏠 মেইন মেনু:", reply_markup=get_user_keyboard())

    # 👤 Regular User Actions
    if text == "👤 Profile":
        profile_text = (
            f"👤 **ইউজার প্রোফাইল**\n───────────────────\n"
            f"🆔 ইউজার আইডি: `{str_id}`\n"
            f"💰 কয়েন ব্যালেন্স: {u_data['credit']}\n"
            f"📁 সক্রিয় প্রজেক্ট: {len(u_data['projects'])}\n"
            f"👥 মোট রেফারেল: {u_data['ref_count']}\n"
            f"🎁 রেফারেল ইনকাম: {u_data['ref_credit']} coins"
        )
        await update.message.reply_text(profile_text)

    elif text == "🛠️ Settings":
        await show_my_projects(update.message, str_id)

    elif text == "📋 Order List":
        await show_order_list(update.message, str_id)

    elif text in ["🎧 Support", "Support"]:
        inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton("💬 Contact Support", url="https://t.me/ARIYAN_VAI_BOSS")]])
        await update.message.reply_text(
            "🎧 **সাহায্য প্রয়োজন?**\n\nআমাদের সাপোর্ট টিমকে সরাসরি বার্তা পাঠাতে নিচের বাটনে ক্লিক করুন:",
            reply_markup=inline_kb
        )

    elif text == "👥 Refer & Earn":
        ref_link = f"https://t.me/{BOT_USERNAME}?start={str_id}"
        ref_bonus = db_get_setting("referral_bonus", "100")
        await update.message.reply_text(
            f"👥 **রেফার এবং ইনকাম প্রোগ্রাম**\n───────────────────\n"
            f"🔗 **আপনার রেফারেল লিংক:**\n{ref_link}\n\n"
            f"🎁 প্রতি সফল রেফারে {ref_bonus} ফ্রী কয়েন অর্জন করুন!"
        )

if __name__ == '__main__':
    keep_alive()
    
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .read_timeout(30)
        .connect_timeout(30)
        .get_updates_read_timeout(30)
        .build()
    )

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^⚙️ Setup$"), start_project),
            MessageHandler(filters.Regex("^💰 Top-up$"), start_topup),
            MessageHandler(filters.Regex("^👤 Search User$"), start_search_user),
            MessageHandler(filters.Regex("^📢 Send SMS$"), start_broadcast),
            CallbackQueryHandler(project_action_callback, pattern="^(fe_|p_)"),
            CallbackQueryHandler(admin_settings_edit_callback, pattern="^edit_setting_"),
            CallbackQueryHandler(admin_user_action_callback, pattern="^uact_")
        ],
        states={
            STEP_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_channel)],
            STEP_COUNT: [CallbackQueryHandler(count_callback, pattern="^cnt_")],
            STEP_VIEWS: [CallbackQueryHandler(views_callback, pattern="^vw_")],
            STEP_REVIEW: [
                CallbackQueryHandler(finalize_project, pattern="^create_final$"),
                CallbackQueryHandler(cancel_flow, pattern="^cancel_flow$")
            ],
            STEP_EDIT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_edited_value)],
            STEP_ADMIN_SEARCH_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_search_user)],
            STEP_ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_broadcast)],
            STEP_ADMIN_EDIT_SETTING: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_edit_setting)],
            STEP_TOPUP_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_topup_amount)],
            STEP_TOPUP_PHOTO: [
                MessageHandler(filters.PHOTO, save_topup_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_topup_photo)
            ],
            STEP_ADMIN_ADD_COINS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_add_coins)],
            STEP_ADMIN_DEDUCT_COINS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_deduct_coins)]
        },
        fallbacks=[
            CommandHandler('start', start), 
            MessageHandler(filters.Regex("^(❌ Cancel|Cancel|❌ বাতিল করুন|বাতিল করুন)$"), cancel_flow),
            CallbackQueryHandler(cancel_flow, pattern="^cancel_flow$")
        ],
        per_message=False
    )

    channel_handler = MessageHandler(filters.ChatType.CHANNEL, auto_react_channel_post)
    
    app.add_handler(channel_handler)
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(topup_action_callback, pattern="^topup_"))
    app.add_handler(CallbackQueryHandler(admin_user_action_callback, pattern="^uact_"))
    app.add_handler(CallbackQueryHandler(project_action_callback, pattern="^(p_|fe_)"))
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('admin', admin_panel_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu))

    logger.info("🤖 Reaction SMM Engine Active...")
    
    app.run_polling(allowed_updates=["message", "edited_message", "channel_post", "edited_channel_post", "callback_query"])
