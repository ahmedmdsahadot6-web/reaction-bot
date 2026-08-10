import logging
import os
import re
import sqlite3
import asyncio
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
            asyncio.run(asyncio.sleep(280))
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

# 🔑 Config
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8895135409:AAFcEL-TULxTbjil0BNO_hX38oddGlEdlIw")
BOT_USERNAME = "@Sahadot_reaction123_bot"
ADMIN_IDS = [8454401183, 7871224176]
ADMIN_USERNAME = "@SOYABUR_AS_LEADER"

# 🌐 SMM Panel API Config
SMM_API_URL = "https://1xpanel.com/api/v2"
SMM_API_KEY = "792d092f1f7fdcebcb9233107b2f1f33"
SMM_REACTION_SERVICE_ID = 1936 
SMM_VIEW_SERVICE_ID = 1937 

DB_FILE = "bot_database.db"

# 📝 Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 💾 Database System
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    credit INTEGER DEFAULT 500,
                    ref_count INTEGER DEFAULT 0,
                    ref_credit INTEGER DEFAULT 0,
                    last_daily_bonus TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    channel_id TEXT,
                    channel_name TEXT,
                    username TEXT,
                    target_url TEXT,
                    status TEXT DEFAULT 'ON',
                    distribution TEXT,
                    speed TEXT,
                    count INTEGER,
                    views INTEGER
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS blocked (
                    user_id TEXT PRIMARY KEY
                )''')
    conn.commit()
    conn.close()

init_db()

def db_execute(query, params=(), fetchone=False, fetchall=False, commit=False):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(query, params)
    res = None
    if fetchone:
        res = c.fetchone()
    elif fetchall:
        res = c.fetchall()
    if commit:
        conn.commit()
    conn.close()
    return res

def get_user_data(user_id):
    str_id = str(user_id)
    user = db_execute("SELECT credit, ref_count, ref_credit, last_daily_bonus FROM users WHERE user_id = ?", (str_id,), fetchone=True)
    if not user:
        db_execute("INSERT INTO users (user_id, credit, ref_count, ref_credit) VALUES (?, 500, 0, 0)", (str_id,), commit=True)
        return {"credit": 500, "ref_count": 0, "ref_credit": 0, "last_daily_bonus": None}
    return {"credit": user[0], "ref_count": user[1], "ref_credit": user[2], "last_daily_bonus": user[3]}

def is_blocked(user_id):
    res = db_execute("SELECT user_id FROM blocked WHERE user_id = ?", (str(user_id),), fetchone=True)
    return res is not None

# 🛒 SMM Order Sender
def send_smm_order(service_id, link, quantity):
    payload = {
        'key': SMM_API_KEY,
        'action': 'add',
        'service': service_id,
        'link': link,
        'quantity': quantity
    }
    try:
        response = requests.post(SMM_API_URL, data=payload, timeout=15)
        res_data = response.json()
        logger.info(f"SMM Panel Response ({service_id}): {res_data}")
        return res_data
    except Exception as e:
        logger.error(f"SMM API Error: {e}")
        return {"error": str(e)}

# States
(STEP_CHANNEL, STEP_DISTRIBUTION, STEP_SPEED, STEP_COUNT, STEP_VIEWS, 
 STEP_REVIEW, STEP_EDIT_VALUE,
 STEP_ADMIN_ADD_CREDIT, STEP_ADMIN_BLOCK_USER, STEP_ADMIN_BROADCAST) = range(10)

# 📱 ✨ NEW USER PANEL KEYBOARD MATCHING SCREENSHOT
def get_user_keyboard():
    kb = [
        [KeyboardButton("⚙️ Setup"), KeyboardButton("👤 Profile")],
        [KeyboardButton("🛠️ Settings"), KeyboardButton("💰 Top-up")],
        [KeyboardButton("📋 Order List"), KeyboardButton("📜 History")],
        [KeyboardButton("👥 Refer & Earn")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def get_admin_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📊 Bot Status"), KeyboardButton("📋 User List")],
        [KeyboardButton("💳 Credit Control"), KeyboardButton("🚫 Block/Unblock User")],
        [KeyboardButton("📢 Broadcast All"), KeyboardButton("🏠 Main Menu")]
    ], resize_keyboard=True)

def cancel_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("❌ Cancel")]], resize_keyboard=True)

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    str_id = str(user.id)

    if is_blocked(str_id):
        await update.message.reply_text("🚫 You are blocked from using this bot.")
        return

    if context.args and len(context.args) > 0:
        referrer_id = context.args[0]
        if referrer_id != str_id:
            ref_user = db_execute("SELECT user_id FROM users WHERE user_id = ?", (referrer_id,), fetchone=True)
            curr_user = db_execute("SELECT user_id FROM users WHERE user_id = ?", (str_id,), fetchone=True)
            if ref_user and not curr_user:
                db_execute("UPDATE users SET credit = credit + 100, ref_count = ref_count + 1, ref_credit = ref_credit + 100 WHERE user_id = ?", (referrer_id,), commit=True)

    get_user_data(user.id)
    await update.message.reply_text(
        f"👋 Welcome {user.first_name}!\n\n"
        f"🚀 **Multi-Reaction & Views SMM Engine Active**\n"
        f"Select an option from the menu below to get started.",
        reply_markup=get_user_keyboard()
    )

async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ You are not an admin!")
        return

    users_count = db_execute("SELECT COUNT(*) FROM users", fetchone=True)[0]
    blocked_count = db_execute("SELECT COUNT(*) FROM blocked", fetchone=True)[0]

    text = (
        f"👑 **ADMIN CONTROL PANEL**\n"
        f"───────────────────\n"
        f"👥 Total Users: {users_count}\n"
        f"🚫 Blocked Users: {blocked_count}\n"
        f"───────────────────"
    )
    await update.message.reply_text(text, reply_markup=get_admin_keyboard())

# --- ⚙️ Setup Flow (Project Creation) ---
async def start_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u_data = get_user_data(user_id)

    if u_data['credit'] <= 0:
        clean_admin = ADMIN_USERNAME.replace("@", "")
        inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton("💬 Contact Admin", url=f"https://t.me/{clean_admin}")]])
        await update.message.reply_text("⚠️ Insufficient coins! Please top-up to setup a project.", reply_markup=inline_kb)
        return ConversationHandler.END

    context.user_data['draft_project'] = {
        "status": "ON",
        "target_url": None,
        "username": None,
        "distribution": "Random",
        "speed": "Instant (Fast)",
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

    if txt in ["❌ Cancel", "Cancel"]:
        context.user_data.pop('draft_project', None)
        await msg.reply_text("Process cancelled.", reply_markup=get_user_keyboard())
        return ConversationHandler.END

    if "https://t.me/" not in txt:
        await msg.reply_text("❌ Invalid Link! Link must start with 'https://t.me/'. Send again:")
        return STEP_CHANNEL

    match = re.search(r'https://t\.me/([^\s/]+)', txt)
    if not match:
        await msg.reply_text("❌ Invalid username extracted! Send link again:")
        return STEP_CHANNEL

    ch_username = match.group(1).replace("@", "")
    context.user_data['draft_project']['target_url'] = f"https://t.me/{ch_username}"
    context.user_data['draft_project']['username'] = ch_username

    return await render_distribution_menu(update, context)

async def render_distribution_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get('draft_project', {})
    text = f"⚙️ **Step 2 • Distribution Type**\n───────────────────\n\n👉 Current: **{draft.get('distribution', 'Random')}**"
    keyboard = [
        [InlineKeyboardButton("🎲 Random", callback_data="dist_random")],
        [InlineKeyboardButton("⚖️ Evenly", callback_data="dist_equal")],
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

    dist_map = {"dist_random": "Random", "dist_equal": "Evenly"}
    draft['distribution'] = dist_map.get(query.data, "Random")
    return await render_distribution_menu(update, context)

async def render_speed_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get('draft_project', {})
    text = f"⚡ **Step 3 • Speed Selection**\n───────────────────\n\n👉 Current: **{draft.get('speed', 'Fast')}**"
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

    speed_map = {"spd_fast": "Fast", "spd_medium": "Medium"}
    draft['speed'] = speed_map.get(query.data, "Fast")
    return await render_speed_menu(update, context)

async def render_count_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get('draft_project', {})
    text = f"📊 **Step 4 • Reaction Count**\n───────────────────\n👉 Current: **{draft.get('count', 100)}**"
    keyboard = [
        [InlineKeyboardButton("50", callback_data="cnt_50"), InlineKeyboardButton("100", callback_data="cnt_100"), InlineKeyboardButton("200", callback_data="cnt_200")],
        [InlineKeyboardButton("500", callback_data="cnt_500"), InlineKeyboardButton("1000", callback_data="cnt_1000")],
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

async def render_views_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get('draft_project', {})
    text = f"👁️ **Step 5 • Video Views Selection**\n───────────────────\n👉 Current Views: **{draft.get('views', 0)}**"
    keyboard = [
        [InlineKeyboardButton("0 (OFF)", callback_data="vw_0"), InlineKeyboardButton("100", callback_data="vw_100"), InlineKeyboardButton("500", callback_data="vw_500")],
        [InlineKeyboardButton("1000", callback_data="vw_1000"), InlineKeyboardButton("5000", callback_data="vw_5000")],
        [InlineKeyboardButton("Continue ✅", callback_data="vw_done")]
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

async def render_review_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get('draft_project', {})
    text = (
        f"✨ **Final Summary** ✨\n───────────────────\n"
        f"🔗 Channel Link: {draft.get('target_url')}\n"
        f"⚙️ Distribution: {draft.get('distribution')}\n"
        f"⚡ Delivery Speed: {draft.get('speed')}\n"
        f"🚀 Reaction Count: {draft.get('count')}\n"
        f"👁️ Video Views: {draft.get('views')}\n\n"
        f"Click '✅ Create Project' to confirm."
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
    user_id = str(query.from_user.id)

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
                text=f"🤖 **Bot Connected Successfully!**\n\n✅ @{BOT_USERNAME} is active in this channel."
            )
        except Exception as e:
            logger.warning(f"Could not send channel msg: {e}")

    except Exception as e:
        logger.error(f"Failed chat check @{ch_username}: {e}")
        await query.message.reply_text("❌ Bot is not an **Admin** in the channel. Please promote it and try again.", reply_markup=get_user_keyboard())
        context.user_data.pop('draft_project', None)
        return ConversationHandler.END

    db_execute("DELETE FROM projects WHERE user_id = ? AND channel_id = ?", (user_id, channel_id), commit=True)
    db_execute(
        "INSERT INTO projects (user_id, channel_id, channel_name, username, target_url, status, distribution, speed, count, views) "
        "VALUES (?, ?, ?, ?, ?, 'ON', ?, ?, ?, ?)",
        (user_id, channel_id, channel_title, ch_username, draft['target_url'], draft['distribution'], draft['speed'], draft['count'], draft['views']),
        commit=True
    )

    context.user_data.pop('draft_project', None)

    await query.message.reply_text(
        f"🎉 **Project Created Successfully!**\n\n"
        f"📁 Channel: {channel_title}\n"
        f"🚀 Reactions: {draft['count']}\n"
        f"👁️ Views: {draft['views']}\n\n"
        f"✅ Active! New posts will trigger orders.",
        reply_markup=get_user_keyboard()
    )
    return ConversationHandler.END

async def cancel_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('draft_project', None)
    msg = "Process cancelled."
    if update.callback_query:
        await update.callback_query.message.reply_text(msg, reply_markup=get_user_keyboard())
    else:
        await update.message.reply_text(msg, reply_markup=get_user_keyboard())
    return ConversationHandler.END

# 📁 Projects Viewer (Order List & Settings)
async def show_my_projects(message_obj, user_id):
    projects = db_execute("SELECT id, channel_name, target_url, status, count, views FROM projects WHERE user_id = ?", (str(user_id),), fetchall=True)

    if not projects:
        await message_obj.reply_text("❌ You have no active projects.")
        return

    for p in projects:
        p_id, ch_name, url, st, count, views = p
        btn_st_text = "🔴 Turn OFF" if st == "ON" else "🟢 Turn ON"
        kb = [[InlineKeyboardButton(btn_st_text, callback_data=f"p_toggle_{p_id}")]]
        p_text = (
            f"📁 **Project: {ch_name}**\n───────────────────\n"
            f"🔗 Link: {url}\n⚙️ Status: **{st}**\n"
            f"🚀 Reactions: **{count}**\n👁️ Views: **{views}**"
        )
        await message_obj.reply_text(p_text, reply_markup=InlineKeyboardMarkup(kb))

async def project_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    p_id = query.data.split("_")[2]

    curr_st = db_execute("SELECT status FROM projects WHERE id = ?", (p_id,), fetchone=True)
    if curr_st:
        new_st = "OFF" if curr_st[0] == "ON" else "ON"
        db_execute("UPDATE projects SET status = ? WHERE id = ?", (new_st, p_id), commit=True)
        await query.message.reply_text(f"✅ Status updated to **{new_st}**!")
        await show_my_projects(query.message, query.from_user.id)

# 🚀 📌 Auto Reaction & Views Order Engine
async def auto_react_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.channel_post or update.edited_channel_post
    if not msg or not msg.chat:
        return

    raw_channel_id = str(msg.chat.id)
    chat_username = (msg.chat.username or "").lower()
    post_id = msg.message_id

    projects = db_execute("SELECT id, user_id, channel_name, username, count, views FROM projects WHERE (channel_id = ? OR LOWER(username) = ?) AND status = 'ON'", (raw_channel_id, chat_username), fetchall=True)

    if not projects:
        return

    for proj in projects:
        p_id, uid, ch_name, uname, reaction_count, views_count = proj
        uinfo = get_user_data(uid)

        total_cost = reaction_count + (views_count if views_count > 0 else 0)

        post_link = f"https://t.me/{chat_username}/{post_id}" if chat_username else f"https://t.me/c/{raw_channel_id.replace('-100', '')}/{post_id}"

        if uinfo['credit'] < total_cost:
            try:
                await context.bot.send_message(
                    chat_id=int(uid),
                    text=f"⚠️ **Insufficient Balance!**\n\n📢 Channel: {ch_name}\nRequired: {total_cost} Coins\nYour Balance: {uinfo['credit']} Coins"
                )
            except Exception: pass
            continue

        react_res = send_smm_order(SMM_REACTION_SERVICE_ID, post_link, reaction_count)
        if views_count > 0:
            send_smm_order(SMM_VIEW_SERVICE_ID, post_link, views_count)

        if react_res and "order" in react_res:
            db_execute("UPDATE users SET credit = credit - ? WHERE user_id = ?", (total_cost, str(uid)), commit=True)
            new_bal = uinfo['credit'] - total_cost

            post_btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 View Post", url=post_link)]])
            try:
                await context.bot.send_message(
                    chat_id=int(uid),
                    text=f"🚀 **Order Placed Successfully!**\n\n📢 Channel: {ch_name}\n✨ Reactions: {reaction_count}\n👁️ Views: {views_count}\n💎 Remaining Balance: {new_bal}",
                    reply_markup=post_btn
                )
            except Exception as e:
                logger.error(f"Error notifying user: {e}")

# 📱 User Buttons Handler
async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    str_id = str(user_id)
    text = update.message.text or ""
    u_data = get_user_data(str_id)

    if text.lower() == "admin":
        return await admin_panel_command(update, context)

    if text == "🏠 Main Menu":
        await update.message.reply_text("🏠 Main Menu:", reply_markup=get_user_keyboard())

    elif text == "👤 Profile":
        p_cnt = db_execute("SELECT COUNT(*) FROM projects WHERE user_id = ?", (str_id,), fetchone=True)[0]
        profile_text = (
            f"👤 **User Profile**\n───────────────────\n"
            f"🆔 User ID: `{str_id}`\n💰 Coins Balance: {u_data['credit']}\n"
            f"📁 Active Projects: {p_cnt}\n👥 Total Referrals: {u_data['ref_count']}"
        )
        await update.message.reply_text(profile_text)

    elif text in ["🛠️ Settings", "📋 Order List"]:
        await show_my_projects(update.message, str_id)

    elif text == "💰 Top-up":
        clean_admin = ADMIN_USERNAME.replace("@", "")
        inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton("💬 Buy Coins from Admin", url=f"https://t.me/{clean_admin}")]])
        await update.message.reply_text(f"💎 Current Balance: {u_data['credit']} Coins\n\nClick below to purchase coins:", reply_markup=inline_kb)

    elif text == "📜 History":
        await update.message.reply_text("📜 **Order History:**\n\nYour previous automatic orders are processed directly through your active setup.")

    elif text == "👥 Refer & Earn":
        ref_link = f"https://t.me/{BOT_USERNAME}?start={str_id}"
        await update.message.reply_text(f"🔗 **Your Referral Link:**\n{ref_link}\n\nEarn 100 free coins for every user that joins via your link!")

if __name__ == '__main__':
    keep_alive()
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^⚙️ Setup$"), start_project)],
        states={
            STEP_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_channel)],
            STEP_DISTRIBUTION: [CallbackQueryHandler(distribution_callback, pattern="^(dist_)")],
            STEP_SPEED: [CallbackQueryHandler(speed_callback, pattern="^(spd_)")],
            STEP_COUNT: [CallbackQueryHandler(count_callback, pattern="^cnt_")],
            STEP_VIEWS: [CallbackQueryHandler(views_callback, pattern="^vw_")],
            STEP_REVIEW: [
                CallbackQueryHandler(finalize_project, pattern="^create_final$"),
                CallbackQueryHandler(cancel_flow, pattern="^cancel_flow$")
            ]
        },
        fallbacks=[CommandHandler('start', start), MessageHandler(filters.Regex("^(❌ Cancel|Cancel)$"), cancel_flow)]
    )

    app.add_handler(MessageHandler(filters.ChatType.CHANNEL, auto_react_channel_post))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(project_toggle_callback, pattern="^p_toggle_"))
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('admin', admin_panel_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu))

    logger.info("🤖 Reaction & Views Bot Online...")
    app.run_polling(allowed_updates=["message", "edited_message", "channel_post", "edited_channel_post", "callback_query"])
