import logging
import random
import os
import json
import re
import asyncio
from datetime import datetime
from threading import Thread
from flask import Flask

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes, ConversationHandler
)

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import SendReactionRequest
from telethon.tl.types import ReactionEmoji

# 🌐 Web Server (24/7 Active রাখার জন্য)
web_app = Flask('')

@web_app.route('/')
def home():
    return "Bot Status: ACTIVE 24/7"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# 🔑 কনফিগারেশন
BOT_TOKEN = "8895135409:AAFcEL-TULxTbjil0BNO_hX38oddGlEdlIw"
BOT_USERNAME = "Sahadot_reaction123_bot"
ADMIN_IDS = [7973059882, 8454401183]
ADMIN_USERNAME = "@SAHADOT_VAI"

# Telethon API Key
API_ID = 37903178
API_HASH = "b4d288715cf8dee6c2b048d5c94881e3"

# 💾 ডাটাবেজ ফাইলসমূহ
DB_FILE = "database.json"
SESSIONS_FILE = "sessions.json"

def load_json(filename, default):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json(filename, data):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Save error ({filename}): {e}")

db = load_json(DB_FILE, {"users": {}, "blocked": []})
if "users" not in db: db["users"] = {}
if "blocked" not in db: db["blocked"] = []

(STEP_CHANNEL, STEP_EMOJI, STEP_COUNT) = range(3)

logging.basicConfig(level=logging.INFO)

def get_user_data(user_id):
    str_id = str(user_id)
    if str_id not in db["users"]:
        db["users"][str_id] = {
            "credit": 100,
            "projects": []
        }
        save_json(DB_FILE, db)
    return db["users"][str_id]

def get_user_keyboard():
    kb = [
        [KeyboardButton("➕ অটো রিয়্যাকশন প্রজেক্ট যোগ করুন")],
        [KeyboardButton("📁 আমার প্রকল্প"), KeyboardButton("⚙️ আরও")],
        [KeyboardButton("🌟 পরিকল্পনা এবং ভারসাম্য"), KeyboardButton("💰 রিচার্জ করুন")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def cancel_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("❌ বাতিল করুন")]], resize_keyboard=True)

# 🚀 /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    str_id = str(user.id)
    
    if str_id in db["blocked"]:
        await update.message.reply_text("🚫 আপনাকে এই বট থেকে ব্লক করা হয়েছে।")
        return

    get_user_data(user.id)
    await update.message.reply_text(
        f"👋 স্বাগতম {user.first_name}!\n\nমাল্টি-রিয়্যাকশন প্রজেক্ট তৈরি করতে নিচের বাটনে চাপুন:",
        reply_markup=get_user_keyboard()
    )

# --- Step 0: Channel Setup ---
async def start_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u_data = get_user_data(user_id)
    
    if u_data['credit'] <= 0:
        clean_admin = ADMIN_USERNAME.replace("@", "")
        inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton("💬 রিচার্জ করুন", url=f"https://t.me/{clean_admin}")]])
        await update.message.reply_text("⚠️ পর্যাপ্ত ক্রেডিট নেই!", reply_markup=inline_kb)
        return ConversationHandler.END

    context.user_data['draft_project'] = {
        "target_url": None,
        "emojis": ["❤️", "👍", "🔥", "💯"],
        "count": 20
    }
    
    text = "🛰 চ্যানেলের লিঙ্ক পাঠান (যেমন: https://t.me/your_channel):"
    await update.message.reply_text(text, reply_markup=cancel_keyboard())
    return STEP_CHANNEL

async def save_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    txt = (msg.text or "").strip()

    if txt in ["❌ বাতিল করুন", "বাতিল করুন"]:
        context.user_data.pop('draft_project', None)
        await msg.reply_text("বাতিল করা হয়েছে।", reply_markup=get_user_keyboard())
        return ConversationHandler.END

    if "https://t.me/" not in txt:
        await msg.reply_text("❌ লিঙ্কের শুরুতে অবশ্যই 'https://t.me/' থাকতে হবে। আবার পাঠান:")
        return STEP_CHANNEL

    match = re.search(r'https://t\.me/[^\s]+', txt)
    if not match:
        await msg.reply_text("❌ সঠিক লিঙ্ক পাঠান:")
        return STEP_CHANNEL

    context.user_data['draft_project']['target_url'] = match.group(0)
    await msg.reply_text(f"✅ লিঙ্ক সেভ হয়েছে:\n🔗 {match.group(0)}")
    return await render_emoji_menu(update, context)

# --- Step 1: Emoji Choice ---
async def render_emoji_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get('draft_project', {})
    em_list = draft.get('emojis', ["❤️", "👍", "🔥", "💯"])
    selected = " ".join(em_list) if em_list else "(খালি)"
    
    text = f"📝 ইমোজি নির্বাচন করুন:\n👉 বর্তমান: {selected}"
    keyboard = [
        [InlineKeyboardButton("❤️", callback_data="em_❤️"), InlineKeyboardButton("👍", callback_data="em_👍"), InlineKeyboardButton("🔥", callback_data="em_🔥")],
        [InlineKeyboardButton("💯", callback_data="em_💯"), InlineKeyboardButton("🎉", callback_data="em_🎉"), InlineKeyboardButton("⚡", callback_data="em_⚡")],
        [InlineKeyboardButton("✅ সম্পন্ন", callback_data="em_done")]
    ]
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return STEP_EMOJI

async def emoji_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get('draft_project', {})
    if 'emojis' not in draft: draft['emojis'] = ["❤️", "👍", "🔥", "💯"]

    data = query.data
    if data == "em_done":
        return await render_count_menu(update, context)
    
    emoji = data.split("_")[1]
    if emoji in draft['emojis']: draft['emojis'].remove(emoji)
    else: draft['emojis'].append(emoji)
    
    return await render_emoji_menu(update, context)

# --- Step 2: Reaction Count ---
async def render_count_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get('draft_project', {})
    text = f"📊 মোট কতটি রিয়্যাকশন চান?\n👉 বর্তমান: {draft.get('count', 20)}"
    keyboard = [
        [InlineKeyboardButton("10", callback_data="cnt_10"), InlineKeyboardButton("20", callback_data="cnt_20"), InlineKeyboardButton("50", callback_data="cnt_50")],
        [InlineKeyboardButton("চালিয়ে যান ✅", callback_data="cnt_done")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return STEP_COUNT

async def count_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get('draft_project', {})
    
    if query.data == "cnt_done":
        return await finalize_project(update, context)
    
    draft['count'] = int(query.data.split("_")[1])
    return await render_count_menu(update, context)

# 💾 Finalize Project
async def finalize_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    draft = context.user_data.get('draft_project')

    target_url = draft.get('target_url')
    clean_handle = target_url.strip().split("/")[-1]
    if not clean_handle.startswith("@"): clean_handle = "@" + clean_handle

    try:
        chat_info = await context.bot.get_chat(clean_handle)
        draft['channel_id'] = str(chat_info.id)
        draft['channel_name'] = chat_info.title or clean_handle
    except Exception as e:
        await query.message.reply_text(f"❌ চ্যানেল কানেক্ট করা যায়নি! বটকে চ্যানেলে Admin বানিয়ে চেষ্টা করুন।", reply_markup=get_user_keyboard())
        return ConversationHandler.END

    u_data = get_user_data(user_id)
    u_data['projects'].append(draft)
    save_json(DB_FILE, db)

    await query.message.reply_text(
        f"🎉 **প্রকল্প সফলভাবে সেভ হয়েছে!**\n\n"
        f"📁 চ্যানেল: {draft['channel_name']}\n"
        f"😊 ইমোজি: {' '.join(draft['emojis'])}\n"
        f"🚀 টার্গেট রিয়্যাকশন: {draft['count']} টি",
        reply_markup=get_user_keyboard()
    )
    return ConversationHandler.END

async def cancel_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('draft_project', None)
    await update.message.reply_text("বাতিল করা হয়েছে।", reply_markup=get_user_keyboard())
    return ConversationHandler.END

# 📁 ইউজার বাটন হ্যান্ডলার
async def my_projects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u_data = get_user_data(user_id)
    projects = u_data.get("projects", [])
    
    if not projects:
        await update.message.reply_text("📂 আপনার কোনো প্রজেক্ট চালু নেই।", reply_markup=get_user_keyboard())
        return
        
    msg = "📁 **আপনার প্রজেক্ট সমূহ:**\n\n"
    for i, p in enumerate(projects, 1):
        msg += f"{i}. {p.get('channel_name')}\n   🔗 {p.get('target_url')}\n   😊 {' '.join(p.get('emojis', []))}\n\n"
    await update.message.reply_text(msg, reply_markup=get_user_keyboard())

async def user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u_data = get_user_data(user_id)
    await update.message.reply_text(
        f"👤 **ইউজার প্রোফাইল:**\n\n"
        f"🆔 ID: `{user_id}`\n"
        f"💰 অবশিষ্ট ক্রেডিট: {u_data.get('credit', 0)}",
        reply_markup=get_user_keyboard(),
        parse_mode="Markdown"
    )

async def recharge_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clean_admin = ADMIN_USERNAME.replace("@", "")
    inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton("💬 এডমিন সাপোর্ট", url=f"https://t.me/{clean_admin}")]])
    await update.message.reply_text("💳 ক্রেডিট রিচার্জ করতে এডমিনের সাথে যোগাযোগ করুন:", reply_markup=inline_kb)

# 👑 ================= ADMiN PANEL (নতুন যুক্ত করা হয়েছে) ================= 👑

def is_admin(user_id):
    return user_id in ADMIN_IDS

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    
    sessions = load_json(SESSIONS_FILE, [])
    total_users = len(db["users"])
    
    msg = (
        "👑 **এডমিন প্যানেল (Admin Commands)**\n\n"
        f"👥 মোট ইউজার: {total_users}\n"
        f"📱 একটিভ সেশন সংখ্যা: {len(sessions)}\n\n"
        "**উপলব্ধ কমান্ডসমূহ:**\n"
        "• `/admin` - প্যানেল দেখুন\n"
        "• `/addcredit <user_id> <amount>` - ক্রেডিট যোগ করুন\n"
        "• `/setcredit <user_id> <amount>` - ক্রেডিট সেট করুন\n"
        "• `/block <user_id>` - ইউজার ব্লক করুন\n"
        "• `/unblock <user_id>` - ইউজার আনব্লক করুন\n"
        "• `/broadcast <মেসেজ>` - সবাইকে মেসেজ পাঠান\n"
        "• `/stats` - ডাটাবেজ তথ্য দেখুন"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def admin_add_credit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        target_id = str(context.args[0])
        amount = int(context.args[1])
        
        if target_id not in db["users"]:
            get_user_data(target_id)
            
        db["users"][target_id]["credit"] += amount
        save_json(DB_FILE, db)
        
        await update.message.reply_text(f"✅ User `{target_id}`-এর সাথে {amount} ক্রেডিট যোগ করা হয়েছে। বর্তমান ক্রেডিট: {db['users'][target_id]['credit']}", parse_mode="Markdown")
    except Exception:
        await update.message.reply_text("❌ ভুল ফরম্যাট! সঠিক নিয়ম: `/addcredit <user_id> <amount>`", parse_mode="Markdown")

async def admin_block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        target_id = str(context.args[0])
        if target_id not in db["blocked"]:
            db["blocked"].append(target_id)
            save_json(DB_FILE, db)
        await update.message.reply_text(f"🚫 User `{target_id}` কে ব্লক করা হয়েছে।", parse_mode="Markdown")
    except Exception:
        await update.message.reply_text("❌ সঠিক নিয়ম: `/block <user_id>`", parse_mode="Markdown")

async def admin_unblock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        target_id = str(context.args[0])
        if target_id in db["blocked"]:
            db["blocked"].remove(target_id)
            save_json(DB_FILE, db)
        await update.message.reply_text(f"✅ User `{target_id}` কে আনব্লক করা হয়েছে।", parse_mode="Markdown")
    except Exception:
        await update.message.reply_text("❌ সঠিক নিয়ম: `/unblock <user_id>`", parse_mode="Markdown")

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    msg_text = " ".join(context.args)
    if not msg_text:
        await update.message.reply_text("❌ লিখুন: `/broadcast আপনার মেসেজ`", parse_mode="Markdown")
        return
        
    count = 0
    for uid in db["users"].keys():
        try:
            await context.bot.send_message(chat_id=int(uid), text=f"📢 **এডমিন ঘোষণা:**\n\n{msg_text}", parse_mode="Markdown")
            count += 1
            await asyncio.sleep(0.1)
        except Exception:
            pass
    await update.message.reply_text(f"✅ মোট {count} জন ইউজারের কাছে মেসেজ পাঠানো হয়েছে।")

# ⚡ Multi-Reaction Dispatcher (Telethon UserBot)
async def trigger_multi_reactions(channel_id, message_id, emojis, target_count):
    sessions = load_json(SESSIONS_FILE, [])
    if not sessions:
        logging.warning("No Telethon user sessions found in sessions.json!")
        return

    needed_count = min(target_count, len(sessions))
    selected_sessions = sessions[:needed_count]

    for session_str in selected_sessions:
        try:
            client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
            await client.connect()
            if await client.is_user_authorized():
                chosen_emoji = random.choice(emojis)
                await client(SendReactionRequest(
                    peer=channel_id,
                    msg_id=message_id,
                    reaction=[ReactionEmoji(emoticon=chosen_emoji)]
                ))
            await client.disconnect()
            await asyncio.sleep(0.5)
        except Exception as e:
            logging.error(f"Telethon Reaction Failed: {e}")

# 📢 Auto Trigger Channel Post
async def auto_react_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.channel_post
        if not message: return
        
        channel_id = str(message.chat_id)

        for uid, uinfo in db["users"].items():
            for proj in uinfo.get("projects", []):
                if str(proj.get("channel_id")) == channel_id:
                    if uinfo.get("credit", 0) <= 0: return

                    emojis = proj.get("emojis", ["👍"])
                    target_count = proj.get("count", 20)

                    asyncio.create_task(
                        trigger_multi_reactions(message.chat_id, message.message_id, emojis, target_count)
                    )

                    uinfo["credit"] -= 1
                    save_json(DB_FILE, db)
                    return
    except Exception as e:
        logging.error(f"Auto Reaction Error: {e}")

if __name__ == '__main__':
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ অটো রিয়্যাকশন প্রজেক্ট যোগ করুন$"), start_project)],
        states={
            STEP_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_channel)],
            STEP_EMOJI: [CallbackQueryHandler(emoji_callback, pattern="^(em_|em_done)")],
            STEP_COUNT: [CallbackQueryHandler(count_callback, pattern="^(cnt_|cnt_done)")]
        },
        fallbacks=[CommandHandler('start', start), MessageHandler(filters.Regex("^(❌ বাতিল করুন|বাতিল করুন)$"), cancel_flow)]
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler('start', start))
    
    # 👑 Admin Handlers
    app.add_handler(CommandHandler('admin', admin_panel))
    app.add_handler(CommandHandler('addcredit', admin_add_credit))
    app.add_handler(CommandHandler('block', admin_block))
    app.add_handler(CommandHandler('unblock', admin_unblock))
    app.add_handler(CommandHandler('broadcast', admin_broadcast))

    # User Handlers
    app.add_handler(MessageHandler(filters.Regex("^📁 আমার প্রকল্প$"), my_projects))
    app.add_handler(MessageHandler(filters.Regex("^🌟 পরিকল্পনা এবং ভারসাম্য$"), user_info))
    app.add_handler(MessageHandler(filters.Regex("^💰 রিচার্জ করুন$"), recharge_info))
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL, auto_react_channel_post))

    print("🤖 Bot Active with Telethon Cluster...")
    app.run_polling(drop_pending_updates=True)
