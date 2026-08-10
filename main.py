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

# 🌐 SMM Panel Config
SMM_API_URL = "https://1xpanel.com/api/v2"
SMM_API_KEY = "792d092f1f7fdcebcb9233107b2f1f33"
SMM_SERVICE_ID = 1936 

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
            credit INTEGER DEFAULT 500,
            ref_count INTEGER DEFAULT 0,
            ref_credit INTEGER DEFAULT 0,
            projects TEXT DEFAULT '[]',
            is_blocked INTEGER DEFAULT 0
        )
    ''')
    # Orders table (Completed Orders)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            order_id TEXT,
            channel_name TEXT,
            count INTEGER,
            post_link TEXT,
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def db_get_user(user_id):
    str_id = str(user_id)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT credit, ref_count, ref_credit, projects, is_blocked FROM users WHERE user_id = ?", (str_id,))
    row = cursor.fetchone()
    
    if not row:
        default_projects = json.dumps([])
        cursor.execute(
            "INSERT INTO users (user_id, credit, ref_count, ref_credit, projects, is_blocked) VALUES (?, ?, ?, ?, ?, ?)",
            (str_id, 500, 0, 0, default_projects, 0)
        )
        conn.commit()
        conn.close()
        return {
            "user_id": str_id,
            "credit": 500,
            "ref_count": 0,
            "ref_credit": 0,
            "projects": [],
            "is_blocked": 0
        }
    
    conn.close()
    return {
        "user_id": str_id,
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
        SET credit = ?, ref_count = ?, ref_credit = ?, projects = ?, is_blocked = ?
        WHERE user_id = ?
    ''', (
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
    cursor.execute("SELECT user_id, credit, ref_count, ref_credit, projects, is_blocked FROM users")
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
            "is_blocked": r[5]
        }
    return users

def db_add_order(user_id, order_id, channel_name, count, post_link):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO orders (user_id, order_id, channel_name, count, post_link, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (str(user_id), str(order_id), channel_name, count, post_link, now_str))
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

# States
(STEP_CHANNEL, STEP_DISTRIBUTION, STEP_SPEED, STEP_COUNT, STEP_VIEWS, 
 STEP_REVIEW, STEP_EDIT_FIELD, STEP_EDIT_VALUE,
 STEP_ADMIN_SEARCH_USER, STEP_ADMIN_BROADCAST) = range(10)

# 🛒 SMM Order Submit Function
def send_smm_order(link, quantity):
    payload = {
        'key': SMM_API_KEY,
        'action': 'add',
        'service': SMM_SERVICE_ID,
        'link': link,
        'quantity': quantity
    }
    try:
        response = requests.post(SMM_API_URL, data=payload, timeout=15)
        res_data = response.json()
        logger.info(f"SMM Panel Response: {res_data}")
        return res_data
    except Exception as e:
        logger.error(f"SMM API Error: {e}")
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
        [KeyboardButton("📋 All Orders")],
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

    u_data = db_get_user(str_id)

    if u_data.get("is_blocked", 0) == 1:
        await update.message.reply_text("🚫 You are blocked from using this bot.")
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
                ref_data["ref_count"] += 1
                ref_data["credit"] += 100
                ref_data["ref_credit"] += 100
                db_save_user(ref_data)

    await update.message.reply_text(
        f"👋 Welcome {user.first_name}!\n\n"
        f"🚀 **Multi-Reaction SMM Engine Active**\n"
        f"Use the menu options below to set up and manage your channel reaction automation.",
        reply_markup=get_user_keyboard()
    )

async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ You are not an Admin!")
        return

    all_users = db_get_all_users()
    blocked_count = sum(1 for u in all_users.values() if u.get("is_blocked", 0) == 1)

    text = (
        f"📊 **ADMIN PANEL**\n"
        f"───────────────────\n"
        f"👥 Total Users: {len(all_users)}\n"
        f"🚫 Blocked Users: {blocked_count}\n"
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
        await update.message.reply_text("⚠️ You don't have enough coins!\nPlease recharge to create a new project.", reply_markup=inline_kb)
        return ConversationHandler.END

    context.user_data['draft_project'] = {
        "status": "ON",
        "target_url": None,
        "username": None,
        "emojis": "POSITIVE 👍❤️🔥",
        "distribution": "Random",
        "speed": "Instant Delivery (Fast)",
        "count": 100,
        "views": 0
    }

    text = (
        f"🛰 **Step 1 • Channel Setup**\n"
        f"───────────────────\n\n"
        f"1) Make @{BOT_USERNAME} an **Admin** in your channel.\n"
        f"2) Send your channel public link (e.g., `https://t.me/your_channel`):"
    )
    await update.message.reply_text(text, reply_markup=cancel_keyboard())
    return STEP_CHANNEL

async def save_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    txt = (msg.text or "").strip()

    if txt in ["❌ Cancel", "Cancel", "❌ বাতিল করুন", "বাতিল করুন"]:
        context.user_data.pop('draft_project', None)
        await msg.reply_text("Process cancelled.", reply_markup=get_user_keyboard())
        return ConversationHandler.END

    if "https://t.me/" not in txt:
        await msg.reply_text("❌ Invalid link! Link must start with 'https://t.me/'. Please try again:")
        return STEP_CHANNEL

    match = re.search(r'https://t\.me/([^\s/]+)', txt)
    if not match:
        await msg.reply_text("❌ Channel link not found! Send the link again:")
        return STEP_CHANNEL

    ch_username = match.group(1).replace("@", "")
    context.user_data['draft_project']['target_url'] = f"https://t.me/{ch_username}"
    context.user_data['draft_project']['username'] = ch_username

    return await render_distribution_menu(update, context)

# 🎲 Step 2 • Distribution Type
async def render_distribution_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get('draft_project', {})
    current_dist = draft.get('distribution', 'Random')
    
    text = (
        f"⚙️ **Step 2 • Distribution Type**\n"
        f"───────────────────\n\n"
        f"👉 Currently Selected: **{current_dist}**"
    )
    keyboard = [
        [InlineKeyboardButton("🎲 Random", callback_data="dist_random")],
        [InlineKeyboardButton("⚖️ Equal Split", callback_data="dist_equal")],
        [InlineKeyboardButton("Continue ➔", callback_data="dist_done")]
    ]
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await context.bot.send_message(chat_id=update.effective_user.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    return STEP_DISTRIBUTION

async def distribution_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get('draft_project', {})

    if query.data == "dist_done":
        return await render_speed_menu(update, context)

    dist_map = {"dist_random": "Random", "dist_equal": "Equal Split"}
    draft['distribution'] = dist_map.get(query.data, "Random")
    return await render_distribution_menu(update, context)

# ⚡ Step 3 • Speed Selection
async def render_speed_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get('draft_project', {})
    current_speed = draft.get('speed', 'Instant Delivery (Fast)')

    text = (
        f"⚡ **Step 3 • Speed Selection**\n"
        f"───────────────────\n\n"
        f"👉 Currently Selected: **{current_speed}**"
    )
    keyboard = [
        [InlineKeyboardButton("⚡ Fast", callback_data="spd_fast"), InlineKeyboardButton("⚖️ Medium", callback_data="spd_medium")],
        [InlineKeyboardButton("Continue ➔", callback_data="spd_done")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return STEP_SPEED

async def speed_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get('draft_project', {})

    if query.data == "spd_done":
        return await render_count_menu(update, context)

    speed_map = {"spd_fast": "Instant Delivery (Fast)", "spd_medium": "Medium"}
    draft['speed'] = speed_map.get(query.data, "Instant Delivery (Fast)")
    return await render_speed_menu(update, context)

# 📊 Step 4 • Reaction Count
async def render_count_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get('draft_project', {})
    text = (
        f"📊 **Step 4 • Reaction Count Selection**\n"
        f"───────────────────\n"
        f"👉 Current Reaction Count: **{draft.get('count', 100)}**"
    )
    keyboard = [
        [InlineKeyboardButton("10", callback_data="cnt_10"), InlineKeyboardButton("20", callback_data="cnt_20"), InlineKeyboardButton("30", callback_data="cnt_30"), InlineKeyboardButton("50", callback_data="cnt_50")],
        [InlineKeyboardButton("100", callback_data="cnt_100"), InlineKeyboardButton("200", callback_data="cnt_200"), InlineKeyboardButton("300", callback_data="cnt_300"), InlineKeyboardButton("500", callback_data="cnt_500")],
        [InlineKeyboardButton("1000", callback_data="cnt_1000"), InlineKeyboardButton("2000", callback_data="cnt_2000"), InlineKeyboardButton("3000", callback_data="cnt_3000"), InlineKeyboardButton("5000", callback_data="cnt_5000")],
        [InlineKeyboardButton("Continue ➔", callback_data="cnt_done")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return STEP_COUNT

async def count_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get('draft_project', {})

    if query.data == "cnt_done":
        return await render_views_menu(update, context)

    draft['count'] = int(query.data.split("_")[1])
    return await render_count_menu(update, context)

# 👁️ Step 5 • Video Views Count
async def render_views_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get('draft_project', {})
    text = (
        f"👁️ **Step 5 • Video Views Selection**\n"
        f"───────────────────\n"
        f"👉 Current Video Views: **{draft.get('views', 0)}**\n"
        f"(Views will be added automatically whenever a video is posted)"
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
        f"✨ **Final Information Review** ✨\n"
        f"───────────────────\n\n"
        f"⚙️ Project Status: {draft.get('status', 'ON')}\n"
        f"🔗 Channel Link: {draft.get('target_url')}\n"
        f"😊 Reaction Emojis: {draft.get('emojis')}\n"
        f"⚙️ Distribution Type: {draft.get('distribution')}\n"
        f"⚡ Delivery Speed: {draft.get('speed')}\n"
        f"🚀 Reaction Count: {draft.get('count')}\n"
        f"👁️ Video Views: {draft.get('views')}\n\n"
        f"If everything looks good, click '✅ Create Project'."
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
        await query.message.reply_text("❌ Something went wrong, please try again!", reply_markup=get_user_keyboard())
        return ConversationHandler.END

    ch_username = draft.get('username')
    try:
        chat_info = await context.bot.get_chat(f"@{ch_username}")
        channel_id = str(chat_info.id)
        channel_title = chat_info.title or ch_username

        try:
            await context.bot.send_message(
                chat_id=chat_info.id,
                text=f"🤖 **Bot Connected Successfully!**\n\n"
                     f"✅ @{BOT_USERNAME} has been successfully connected to this channel.\n"
                     f"🚀 Automatic reaction orders will now be triggered for each new post."
            )
        except Exception as e:
            logger.warning(f"Failed to send confirmation message to channel: {e}")

    except Exception as e:
        logger.error(f"Failed to fetch channel @{ch_username}: {e}")
        await query.message.reply_text(
            f"❌ Could not connect to channel!\n\n"
            f"⚠️ Make sure the bot is added as an **Admin** in your channel.", 
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
        f"🎉 **Project Created Successfully!**\n\n"
        f"📁 Channel: {channel_title}\n"
        f"🆔 Channel ID: `{channel_id}`\n"
        f"⚙️ Status: {draft.get('status', 'ON')}\n"
        f"🚀 Reaction Count: {draft['count']}\n"
        f"👁️ Video Views: {draft['views']}\n\n"
        f"✅ Project activated! Now reaction orders will be automatically submitted whenever you post.",
        reply_markup=get_user_keyboard()
    )
    return ConversationHandler.END

async def cancel_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('draft_project', None)
    context.user_data.pop('edit_target', None)
    msg_text = "Process cancelled."
    if update.callback_query:
        await update.callback_query.message.reply_text(msg_text, reply_markup=get_user_keyboard())
    else:
        await update.message.reply_text(msg_text, reply_markup=get_user_keyboard())
    return ConversationHandler.END

# 🛠️ Project Action Callback
async def project_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    data = query.data

    u_data = db_get_user(user_id)
    projects = u_data.get('projects', [])

    if data.startswith("p_toggle_"):
        idx = int(data.split("_")[2])
        if 0 <= idx < len(projects):
            projects[idx]['status'] = "OFF" if projects[idx].get('status', 'ON') == "ON" else "ON"
            db_save_user(u_data)
            await query.message.reply_text(f"✅ Project status changed to **{projects[idx]['status']}**!")
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
                f"✏️ **Edit:** {proj.get('channel_name')}\n\n"
                f"Select which option you want to change:",
                reply_markup=InlineKeyboardMarkup(kb)
            )

    elif data.startswith("fe_"):
        parts = data.split("_")
        idx, field = int(parts[1]), parts[2]
        context.user_data['edit_target'] = {'idx': idx, 'field': field}
        
        prompt_messages = {
            "channel": "✍️ **Send new channel link:**\n(e.g., `https://t.me/your_channel`) \n\n⚠️ Ensure the bot is an admin in the new channel!",
            "count": "✍️ **Send new reaction count:**\n(e.g., `100`, `200`, `500`)",
            "views": "✍️ **Send new video views count:**\n(e.g., `0`, `100`, `500`)"
        }
        
        msg_to_send = prompt_messages.get(field, "✍️ **Send new value:**")
        await query.message.reply_text(msg_to_send, reply_markup=cancel_keyboard())
        return STEP_EDIT_VALUE

    elif data == "p_back":
        await show_my_projects(query.message, user_id)

async def save_edited_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val_txt = update.message.text.strip()
    if val_txt in ["❌ Cancel", "Cancel", "❌ বাতিল করুন", "বাতিল করুন"]:
        context.user_data.pop('edit_target', None)
        await update.message.reply_text("Edit cancelled.", reply_markup=get_user_keyboard())
        return ConversationHandler.END

    target = context.user_data.get('edit_target')
    if not target:
        await update.message.reply_text("❌ Something went wrong!", reply_markup=get_user_keyboard())
        return ConversationHandler.END

    user_id = str(update.effective_user.id)
    u_data = db_get_user(user_id)
    projects = u_data.get('projects', [])

    idx = target['idx']
    field = target['field']

    if 0 <= idx < len(projects):
        if field == 'channel':
            if "https://t.me/" not in val_txt:
                await update.message.reply_text("❌ Invalid link! Link must start with 'https://t.me/'. Try again:")
                return STEP_EDIT_VALUE

            match = re.search(r'https://t\.me/([^\s/]+)', val_txt)
            if not match:
                await update.message.reply_text("❌ Channel link not found! Send new link again:")
                return STEP_EDIT_VALUE

            ch_username = match.group(1).replace("@", "")
            try:
                chat_info = await context.bot.get_chat(f"@{ch_username}")
                projects[idx]['channel_id'] = str(chat_info.id)
                projects[idx]['channel_name'] = chat_info.title or ch_username
                projects[idx]['target_url'] = f"https://t.me/{ch_username}"
                projects[idx]['username'] = ch_username
            except Exception as e:
                await update.message.reply_text("❌ Bot could not access the channel! Make sure bot is an **Admin** in that channel. Send link again:")
                return STEP_EDIT_VALUE

        elif field in ['count', 'views']:
            try:
                projects[idx][field] = int(val_txt)
            except ValueError:
                await update.message.reply_text("❌ Please enter numbers only!")
                return STEP_EDIT_VALUE
        else:
            projects[idx][field] = val_txt

        db_save_user(u_data)
        context.user_data.pop('edit_target', None)
        await update.message.reply_text("🎉 **Successfully updated!**", reply_markup=get_user_keyboard())
    
    return ConversationHandler.END

# 📂 Display Projects function
async def show_my_projects(message_obj, user_id):
    u_data = db_get_user(user_id)
    projects = u_data.get('projects', [])

    if not projects:
        await message_obj.reply_text("❌ You don't have any active projects.")
        return

    for idx, p in enumerate(projects):
        st = p.get('status', 'ON')
        btn_st_text = "🔴 Turn OFF" if st == "ON" else "🟢 Turn ON"
        
        kb = [
            [InlineKeyboardButton(btn_st_text, callback_data=f"p_toggle_{idx}"), InlineKeyboardButton("✏️ Edit", callback_data=f"p_edit_{idx}")]
        ]
        p_text = (
            f"🛠️ **Project Settings #{idx+1}: {p.get('channel_name', 'Channel')}**\n"
            f"───────────────────\n"
            f"🔗 Link: {p.get('target_url')}\n"
            f"⚙️ Status: **{st}**\n"
            f"🚀 Reactions: **{p.get('count', 100)}**\n"
            f"👁️ Views: **{p.get('views', 0)}**\n"
            f"😊 Emojis: **{p.get('emojis', 'POSITIVE')}**"
        )
        await message_obj.reply_text(p_text, reply_markup=InlineKeyboardMarkup(kb))

# 📋 Display Completed Orders List
async def show_order_list(message_obj, user_id):
    orders = db_get_user_orders(user_id)
    if not orders:
        await message_obj.reply_text("📋 **Order List**\n───────────────────\n❌ No completed orders found.")
        return

    text = "📋 **Completed Order List**\n───────────────────\n\n"
    for o in orders:
        order_id, channel_name, count, post_link, created_at = o
        text += (
            f"🆔 **Order ID:** `{order_id}`\n"
            f"📢 **Channel:** {channel_name}\n"
            f"✨ **Reactions:** {count}\n"
            f"📅 **Date:** {created_at}\n"
            f"🔗 **Post:** [View Post]({post_link})\n"
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

            if proj.get("status", "ON") == "OFF":
                logger.info(f"⏸️ Project is OFF for Channel {proj_cid}. Skipping order.")
                continue

            if (proj_cid and proj_cid == raw_channel_id) or \
               (chat_username and proj_uname == chat_username) or \
               (proj_cid.replace("-100", "") == raw_channel_id.replace("-100", "")):
                matched_projects.append((uid, uinfo, proj))

    if not matched_projects:
        return

    for uid, uinfo, proj in matched_projects:
        user_chat_id = int(uid)
        ch_name = proj.get("channel_name", "Channel")
        reaction_count = proj.get("count", 100)

        if chat_username:
            post_link = f"https://t.me/{chat_username}/{post_id}"
        elif proj.get("username"):
            post_link = f"https://t.me/{proj.get('username')}/{post_id}"
        else:
            clean_cid = raw_channel_id.replace("-100", "")
            post_link = f"https://t.me/c/{clean_cid}/{post_id}"

        if uinfo.get("credit", 0) < reaction_count:
            try:
                await context.bot.send_message(
                    chat_id=user_chat_id,
                    text=f"⚠️ **Insufficient Balance!**\n\n"
                         f"📢 **Channel:** {ch_name}\n"
                         f"📌 **Post Link:** {post_link}\n"
                         f"Required Coins: {reaction_count}\n"
                         f"Remaining Coins: {uinfo.get('credit', 0)}\n\n"
                         f"Please recharge your account balance."
                )
            except Exception as e:
                logger.error(f"Error sending low balance msg: {e}")
            continue

        smm_res = send_smm_order(post_link, reaction_count)
        post_btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 View Post", url=post_link)]])

        if smm_res and "order" in smm_res:
            order_id = smm_res["order"]
            uinfo["credit"] -= reaction_count
            db_save_user(uinfo)
            db_add_order(uid, order_id, ch_name, reaction_count, post_link)

            try:
                await context.bot.send_message(
                    chat_id=user_chat_id,
                    text=f"🚀 **Auto Reaction Order Successful!**\n\n"
                         f"📢 **Channel:** {ch_name}\n"
                         f"🆔 **SMM Order ID:** `{order_id}`\n"
                         f"✨ **Reactions:** {reaction_count}\n"
                         f"💰 **Deducted Coins:** {reaction_count}\n"
                         f"💎 **Remaining Coins:** {uinfo.get('credit', 0)}\n\n"
                         f"📌 **Post Link:** {post_link}",
                    reply_markup=post_btn
                )
                logger.info(f"✅ SMM Order #{order_id} Success for User {uid}")
            except Exception as e:
                logger.error(f"Failed to send order success alert to user {uid}: {e}")
        else:
            err_msg = smm_res.get("error") or smm_res.get("message") or "SMM Server Response Error"
            try:
                await context.bot.send_message(
                    chat_id=user_chat_id,
                    text=f"❌ **Order Submission Failed!**\n\n"
                         f"📢 **Channel:** {ch_name}\n"
                         f"⚠️ **Reason:** `{err_msg}`\n\n"
                         f"📌 **Post Link:** {post_link}",
                    reply_markup=post_btn
                )
            except Exception as e:
                logger.error(f"Failed to send order fail alert: {e}")

# 👑 Admin Handlers
async def start_search_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return ConversationHandler.END
    await update.message.reply_text("👤 **Enter User ID to Search:**", reply_markup=cancel_keyboard())
    return STEP_ADMIN_SEARCH_USER

async def process_admin_search_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt in ["❌ Cancel", "Cancel", "❌ বাতিল করুন", "বাতিল করুন"]:
        await update.message.reply_text("Search cancelled.", reply_markup=get_admin_keyboard())
        return ConversationHandler.END

    u_data = db_get_user(txt)
    if u_data:
        is_b = "Yes 🚫" if u_data.get("is_blocked", 0) == 1 else "No ✅"
        text = (
            f"👤 **User Information**\n"
            f"───────────────────\n"
            f"🆔 **User ID:** `{u_data['user_id']}`\n"
            f"💰 **Balance:** {u_data['credit']} Coins\n"
            f"👥 **Referrals:** {u_data['ref_count']}\n"
            f"📁 **Projects:** {len(u_data.get('projects', []))}\n"
            f"🚫 **Blocked:** {is_b}\n"
            f"───────────────────\n"
            f"💡 To add/remove coins send: `{u_data['user_id']} Amount` (e.g. `{u_data['user_id']} 500`)"
        )
        await update.message.reply_text(text, reply_markup=get_admin_keyboard())
    else:
        await update.message.reply_text("❌ User ID not found in database!", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return ConversationHandler.END
    await update.message.reply_text("📢 **Send SMS / Message to Broadcast:**", reply_markup=cancel_keyboard())
    return STEP_ADMIN_BROADCAST

async def process_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_text = update.message.text
    if msg_text in ["❌ Cancel", "Cancel", "❌ বাতিল করুন", "বাতিল করুন"]:
        await update.message.reply_text("Broadcast cancelled.", reply_markup=get_admin_keyboard())
        return ConversationHandler.END

    count = 0
    all_users = db_get_all_users()
    for uid in all_users:
        try:
            await context.bot.send_message(chat_id=int(uid), text=f"📢 **Notice:**\n\n{msg_text}")
            count += 1
            await asyncio.sleep(0.05)
        except Exception: pass
    await update.message.reply_text(f"🎉 Message sent to {count} users!", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

# Menu Handlers
async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    str_id = str(user_id)
    text = (update.message.text or "").strip()
    u_data = db_get_user(str_id)

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
                await update.message.reply_text(f"✅ User `{target_id}` updated balance: {target_u['credit']} Coins", reply_markup=get_admin_keyboard())
                return

    # 👑 Admin Actions
    if user_id in ADMIN_IDS:
        if text == "📊 Admin Dashboard":
            return await update.message.reply_text("📊 **Admin Dashboard Settings:**", reply_markup=get_admin_dashboard_keyboard())
        
        elif text in ["🤖 Bot Orders", "🌐 API Orders", "📋 All Orders", "💰 Telegram Super Service", 
                      "🧪 Services", "🔄 Replace OFF ❌", "♻️ Refill OFF ❌", "❌ Canceled", 
                      "⚠️ Failed/Partial", "💡 Coin Rate Settings", "👥 Referral Settings"]:
            return await update.message.reply_text(f"⚙️ **{text}** option selected.", reply_markup=get_admin_dashboard_keyboard())

        elif text == "👥 Users Report":
            all_u = db_get_all_users()
            u_list = "👥 **Users Report:**\n───────────────────\n"
            for uid, uinfo in list(all_u.items())[:20]:
                u_list += f"🆔 `{uid}` | 💰 Coins: {uinfo.get('credit', 0)}\n"
            return await update.message.reply_text(u_list, reply_markup=get_admin_keyboard())

        elif text == "🏠 Main Menu":
            return await update.message.reply_text("🏠 Main Menu:", reply_markup=get_user_keyboard())

    # 👤 Regular User Actions
    if text == "👤 Profile":
        profile_text = (
            f"👤 **User Profile**\n───────────────────\n"
            f"🆔 User ID: `{str_id}`\n"
            f"💰 Coin Balance: {u_data['credit']}\n"
            f"📁 Active Projects: {len(u_data['projects'])}\n"
            f"👥 Total Referrals: {u_data['ref_count']}\n"
            f"🎁 Referral Income: {u_data['ref_credit']} coins"
        )
        await update.message.reply_text(profile_text)

    elif text == "🛠️ Settings":
        await show_my_projects(update.message, str_id)

    elif text == "💰 Top-up":
        clean_admin = ADMIN_USERNAME.replace("@", "")
        inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton("💬 Contact Admin to Buy Coins", url=f"https://t.me/{clean_admin}")]])
        await update.message.reply_text(
            f"💎 **Your Balance:** {u_data['credit']} coins\n\n"
            f"💳 To top-up or recharge coins, click the button below:",
            reply_markup=inline_kb
        )

    elif text == "📋 Order List":
        await show_order_list(update.message, str_id)

    elif text in ["🎧 Support", "Support"]:
        inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton("💬 Contact Support", url="https://t.me/ARIYAN_VAI_BOSS")]])
        await update.message.reply_text(
            "🎧 **Need Help?**\n\nClick the button below to message our support directly:",
            reply_markup=inline_kb
        )

    elif text == "👥 Refer & Earn":
        ref_link = f"https://t.me/{BOT_USERNAME}?start={str_id}"
        await update.message.reply_text(
            f"👥 **Refer & Earn Program**\n───────────────────\n"
            f"🔗 **Your Referral Link:**\n{ref_link}\n\n"
            f"🎁 Earn 100 free coins for every successful referral!"
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
            MessageHandler(filters.Regex("^👤 Search User$"), start_search_user),
            MessageHandler(filters.Regex("^📢 Send SMS$"), start_broadcast),
            CallbackQueryHandler(project_action_callback, pattern="^(fe_|p_)")
        ],
        states={
            STEP_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_channel)],
            STEP_DISTRIBUTION: [CallbackQueryHandler(distribution_callback, pattern="^(dist_)")],
            STEP_SPEED: [CallbackQueryHandler(speed_callback, pattern="^(spd_)")],
            STEP_COUNT: [CallbackQueryHandler(count_callback, pattern="^cnt_")],
            STEP_VIEWS: [CallbackQueryHandler(views_callback, pattern="^vw_")],
            STEP_REVIEW: [
                CallbackQueryHandler(finalize_project, pattern="^create_final$"),
                CallbackQueryHandler(cancel_flow, pattern="^cancel_flow$")
            ],
            STEP_EDIT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_edited_value)],
            STEP_ADMIN_SEARCH_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_search_user)],
            STEP_ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_broadcast)]
        },
        fallbacks=[
            CommandHandler('start', start), 
            MessageHandler(filters.Regex("^(❌ Cancel|Cancel|❌ বাতিল করুন|বাতিল করুন)$"), cancel_flow),
            CallbackQueryHandler(cancel_flow, pattern="^cancel_flow$")
        ]
    )

    channel_handler = MessageHandler(filters.ChatType.CHANNEL, auto_react_channel_post)
    
    app.add_handler(channel_handler)
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(project_action_callback, pattern="^(p_|fe_)"))
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('admin', admin_panel_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu))

    logger.info("🤖 Reaction SMM Engine Active...")
    
    app.run_polling(allowed_updates=["message", "edited_message", "channel_post", "edited_channel_post", "callback_query"])
