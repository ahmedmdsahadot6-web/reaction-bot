import logging
import random
import os
import json
from datetime import date
from threading import Thread
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, ReactionTypeEmoji
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# 🌐 Web Server for Render 24/7 Keep-Alive
web_app = Flask('')

@web_app.route('/')
def home():
    return "Bot is active 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# ⚠️ বটের কনফিগারেশন
BOT_TOKEN = "8895135409:AAFcEL-TULxTbjil0BNO_hX38oddGlEdlIw"
BOT_USERNAME = "Sahadot_reaction123_bot"
ADMIN_IDS = [7973059882, 8454401183]
ADMIN_USERNAME = "@SAHADOT_VAI" # আপনার এডমিন ইউজারনেম

# 💾 ডাটাবেজ
DB_FILE = "database.json"

def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"users": {}, "blocked": []}
    return {"users": {}, "blocked": []}

def save_data(data):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Save error: {e}")

db = load_data()
if "users" not in db: db["users"] = {}
if "blocked" not in db: db["blocked"] = []

# Conversation States
(STEP_CHANNEL, STEP_EMOJI, STEP_COUNT, STEP_DISTRIBUTION, 
 STEP_SPEED, STEP_VIEWS, STEP_REVIEW, STEP_ADMIN_ADD_CREDIT, 
 STEP_ADMIN_BLOCK_USER, STEP_ADMIN_BROADCAST) = range(10)

logging.basicConfig(level=logging.INFO)

def get_user_data(user_id):
    str_id = str(user_id)
    if str_id not in db["users"]:
        db["users"][str_id] = {
            "credit": 100,
            "cost": 0,
            "ref_count": 0,
            "ref_credit": 0,
            "projects": [], # সেভ হওয়া প্রজেক্টসমূহ
            "temp_project": {
                "channel_name": None,
                "channel_id": None,
                "emojis": ["❤️", "👍", "🔥", "💯"],
                "count": 20,
                "dist": "এলোমেলো",
                "speed": "তাৎক্ষণিক",
                "views": 0
            },
            "last_daily_bonus": None
        }
        save_data(db)
    return db["users"][str_id]

# 📱 সাধারণ ইউজার প্যানেল কিবোর্ড
def get_user_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ অটো রিয়্যাকশন প্রজেক্ট যোগ করুন")],
        [KeyboardButton("📁 আমার প্রকল্প"), KeyboardButton("⚙️ আরও")],
        [KeyboardButton("🌟 পরিকল্পনা এবং ভারসাম্য"), KeyboardButton("💰 রিচার্জ করুন")]
    ], resize_keyboard=True)

def get_more_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🔗 রেফার করুন এবং আয় করুন"), KeyboardButton("🎁 দৈনিক উপহার")],
        [KeyboardButton("⚡ তাৎক্ষণিক প্রতিক্রিয়া")],
        [KeyboardButton("🔙 ব্যাক")]
    ], resize_keyboard=True)

# 👑 অ্যাডমিন প্যানেল কিবোর্ড
def get_admin_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📊 বট স্ট্যাটাস"), KeyboardButton("📋 ইউজার লিস্ট")],
        [KeyboardButton("💳 ক্রেডিট কন্ট্রোল"), KeyboardButton("🚫 ইউজার ব্লক/রিমুভ")],
        [KeyboardButton("📢 অল ইউজার ব্রডকাস্ট"), KeyboardButton("🔙 ইউজার প্যানেলে যান")]
    ], resize_keyboard=True)

def cancel_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("বাতিল করুন")]], resize_keyboard=True)

# --- Start Command ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    str_id = str(user.id)
    
    if str_id in db["blocked"]:
        await update.message.reply_text("🚫 দুঃখিত! আপনাকে বট থেকে ব্লক করা হয়েছে।")
        return

    get_user_data(user.id)

    # রেফারেল ট্র্যাকিং
    if context.args:
        try:
            ref_str = context.args[0]
            if ref_str.startswith("ref_"):
                referrer_id = str(ref_str.replace("ref_", ""))
                if referrer_id != str_id and referrer_id in db["users"]:
                    db["users"][referrer_id]["credit"] += 50
                    db["users"][referrer_id]["ref_credit"] += 50
                    db["users"][referrer_id]["ref_count"] += 1
                    save_data(db)
                    try:
                        await context.bot.send_message(
                            chat_id=int(referrer_id), 
                            text="🎉 আপনার রেফারেল লিংকের মাধ্যমে একজন নতুন সদস্য যোগ দিয়েছেন! আপনি +৫০ ক্রেডিট পেয়েছেন।"
                        )
                    except Exception:
                        pass
        except Exception:
            pass

    await update.message.reply_text(
        f"👋 **স্বাগতম {user.first_name}!**\n\nআপনার অটো রিয়্যাকশন প্রজেক্ট ম্যানেজ করতে নিচের মেনু ব্যবহার করুন:",
        reply_markup=get_user_keyboard(),
        parse_mode='Markdown'
    )

# 👑 অ্যাডমিন কন্ট্রোল প্যানেল
async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ আপনি অ্যাডমিন নন!")
        return

    text = (
        f"👑 **ADMIN CONTROL PANEL**\n"
        f"═══════════════════════\n\n"
        f"👥 মোট ইউজার: `{len(db['users'])}` জন\n"
        f"🚫 ব্লক করা ইউজার: `{len(db['blocked'])}` জন\n"
        f"═══════════════════════"
    )
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=get_admin_keyboard())

# --- Project Creation Flow ---
async def start_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if str(user_id) in db["blocked"]: return ConversationHandler.END

    u_data = get_user_data(user_id)
    u_data['temp_project'] = {
        "channel_name": None,
        "channel_id": None,
        "emojis": ["❤️", "👍", "🔥", "💯"],
        "count": 20,
        "dist": "এলোমেলো",
        "speed": "তাৎক্ষণিক",
        "views": 0
    }
    save_data(db)
    
    text = (
        f"🛰 **ধাপ 0 • চ্যানেল সেটআপ**\n"
        f"───────────────────\n\n"
        f"1) 👤 @{BOT_USERNAME} কে আপনার চ্যানেলে প্রশাসক (Admin) বানান।\n"
        f"2) 🆔 আপনার চ্যানেলের **লিঙ্ক / ইউজারনেম** লিখে পাঠান অথবা চ্যানেল থেকে যেকোনো একটি পোস্ট **ফরোয়ার্ড করুন**।\n\n👇 👇"
    )
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=cancel_keyboard())
    return STEP_CHANNEL

async def save_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    msg = update.message
    txt = msg.text or ""

    if txt in ["বাতিল করুন", "🔙 ব্যাক"]:
        return await cancel_flow(update, context)

    channel_title = None
    channel_id = None

    # ১. ফরোয়ার্ড করা পোস্ট থেকে আইডি বের করা
    if msg.forward_from_chat:
        channel_title = msg.forward_from_chat.title or "Channel"
        channel_id = str(msg.forward_from_chat.id)
    elif msg.forward_origin and hasattr(msg.forward_origin, 'chat'):
        channel_title = msg.forward_origin.chat.title or "Channel"
        channel_id = str(msg.forward_origin.chat.id)
    # ২. চ্যানেল লিংক বা ইউজারনেম থাকলে বের করা
    elif txt:
        clean_txt = txt.strip()
        if "t.me/" in clean_txt:
            parts = clean_txt.split("t.me/")
            username = parts[-1].replace("/", "")
            channel_title = username
            channel_id = f"@{username}"
        elif clean_txt.startswith("@"):
            channel_title = clean_txt[1:]
            channel_id = clean_txt
        else:
            channel_title = clean_txt
            channel_id = clean_txt

    if not channel_id:
        await msg.reply_text("❌ চ্যানেল শনাক্ত করা যায়নি! অনুগ্রহ করে সঠিক চ্যানেল লিংক পাঠান অথবা চ্যানেল থেকে একটি পোস্ট ফরোয়ার্ড করুন।")
        return STEP_CHANNEL

    u_data['temp_project']['channel_name'] = channel_title
    u_data['temp_project']['channel_id'] = channel_id
    save_data(db)

    confirm_text = (
        f"👍 **চ্যানেল সফলভাবে যোগ করা হয়েছে!** সনাক্ত করা প্রকার: PUBLIC\n\n"
        f"📋 **চ্যানেলের বিবরণ:**\n"
        f"───────────────────\n"
        f"📺 **চ্যানেলের নাম:** {channel_title}\n"
        f"🆔 **চ্যানেল আইডি:** `{channel_id}`\n"
        f"───────────────────"
    )
    await msg.reply_text(confirm_text, parse_mode='Markdown')

    return await ask_emoji(update, context)

async def ask_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    temp = u_data['temp_project']
    selected = " ".join(temp['emojis']) if temp['emojis'] else "(none)"
    
    text = (
        f"📝 **ধাপ 1 • ইমোজি নির্বাচন করুন**\n"
        f"───────────────────\n\n"
        f"আপনার পোস্টের জন্য প্রতিক্রিয়া চয়ন করুন।\n\n"
        f"**নির্বাচিত ({len(temp['emojis'])}):** {selected}\n\n"
        f"🌟 **ইমোজিতে আলতো চাপুন/remove যোগ করতে।** ✅ **সম্পন্ন হলে ট্যাপ করুন।**"
    )
    
    keyboard = [
        [InlineKeyboardButton("✓ সব (4)", callback_data="em_all"), InlineKeyboardButton("কাস্টম", callback_data="em_custom")],
        [InlineKeyboardButton("❤️", callback_data="em_❤️"), InlineKeyboardButton("👍", callback_data="em_👍"), InlineKeyboardButton("🔥", callback_data="em_🔥")],
        [InlineKeyboardButton("🙏", callback_data="em_🙏"), InlineKeyboardButton("🎉", callback_data="em_🎉"), InlineKeyboardButton("🏆", callback_data="em_🏆")],
        [InlineKeyboardButton("😍", callback_data="em_😍"), InlineKeyboardButton("💯", callback_data="em_💯"), InlineKeyboardButton("😭", callback_data="em_😭"), InlineKeyboardButton("⚡", callback_data="em_⚡")],
        [InlineKeyboardButton("✅ সম্পন্ন", callback_data="em_done")]
    ]
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return STEP_EMOJI

async def emoji_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    u_data = get_user_data(query.from_user.id)
    temp = u_data['temp_project']
    
    data = query.data
    if data == "em_done":
        if not temp['emojis']: temp['emojis'] = ["👍"]
        save_data(db)
        return await ask_count(update, context)
    elif data == "em_all":
        temp['emojis'] = ["❤️", "👍", "🔥", "💯"]
    elif data == "em_custom":
        pass
    else:
        emoji = data.split("_")[1]
        if emoji in temp['emojis']:
            temp['emojis'].remove(emoji)
        else:
            temp['emojis'].append(emoji)
    
    save_data(db)
    return await ask_emoji(update, context)

async def ask_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    temp = u_data['temp_project']
    text = (
        f"📊 **ধাপ 2 • মোট প্রতিক্রিয়া**\n"
        f"───────────────────\n\n"
        f"প্রতি পোস্টে কত প্রতিক্রিয়া?\n\n"
        f"🌟 *একটি প্রিসেট চয়ন করুন বা আপনার নিজের নম্বর লিখতে কাস্টম আলতো চাপুন।*\n"
        f"👉 **বর্তমান নির্বাচন:** {temp['count']} প্রতিক্রিয়া"
    )
    keyboard = [
        [InlineKeyboardButton("10", callback_data="cnt_10"), InlineKeyboardButton("20", callback_data="cnt_20"), InlineKeyboardButton("30", callback_data="cnt_30")],
        [InlineKeyboardButton("🔒 50", callback_data="locked"), InlineKeyboardButton("🔒 70", callback_data="locked"), InlineKeyboardButton("🔒 100", callback_data="locked")],
        [InlineKeyboardButton("🔒 200", callback_data="locked"), InlineKeyboardButton("🔒 300", callback_data="locked"), InlineKeyboardButton("🔒 MAX (1000)", callback_data="locked")],
        [InlineKeyboardButton("⛩️ কাস্টম ⛩️", callback_data="locked")],
        [InlineKeyboardButton("🔀 Vary per post", callback_data="locked")],
        [InlineKeyboardButton("↩ ব্যাক", callback_data="back_emoji"), InlineKeyboardButton("চালিয়ে যান ✅", callback_data="cnt_done")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return STEP_COUNT

async def count_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u_data = get_user_data(query.from_user.id)
    temp = u_data['temp_project']
    
    if query.data == "cnt_done": return await ask_distribution(update, context)
    if query.data == "back_emoji": return await ask_emoji(update, context)
    if query.data == "locked":
        await query.answer("এটি প্রিমিয়াম প্ল্যানের জন্য প্রিসেট।", show_alert=True)
        return STEP_COUNT
    
    temp['count'] = int(query.data.split("_")[1])
    save_data(db)
    await query.answer(f"সেট করা হয়েছে: {temp['count']}")
    return await ask_count(update, context)

async def ask_distribution(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"⚙️ **ধাপ 3 • বিতরণের ধরন**\n"
        f"───────────────────\n\n"
        f"প্রতিক্রিয়া কি প্যাটার্ন অনুসরণ করা উচিত?\n"
        f"🎲 **এলোমেলো** - প্রতিটি ইমোজি পায় 7-8 reactions\n"
        f"⚖️ **সকল সমান** - প্রতিটি ইমোজি ঠিক 7 প্রতিক্রিয়া পায়\n"
        f"⚙️ **Advanced** - ইমোজি প্রতি কাস্টম ওজন সেট করুন"
    )
    keyboard = [
        [InlineKeyboardButton("🎲 এলোমেলো", callback_data="dist_এলোমেলো")],
        [InlineKeyboardButton("⚖️ সব সমানভাবে", callback_data="dist_সমান")],
        [InlineKeyboardButton("⚙️ উন্নত কাস্টমাইজেশন", callback_data="dist_উন্নত")],
        [InlineKeyboardButton("↩ ব্যাক", callback_data="back_count"), InlineKeyboardButton("চালিয়ে যান ✅", callback_data="dist_done")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return STEP_DISTRIBUTION

async def distribution_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u_data = get_user_data(query.from_user.id)
    temp = u_data['temp_project']
    
    if query.data == "dist_done": return await ask_speed(update, context)
    if query.data == "back_count": return await ask_count(update, context)
    if query.data == "dist_উন্নত":
        await query.answer("উন্নত কাস্টমাইজেশন বর্তমানে সক্রিয় আছে।", show_alert=True)
        return STEP_DISTRIBUTION

    temp['dist'] = query.data.split("_")[1]
    save_data(db)
    await query.answer(f"মোড: {temp['dist']}")
    return await ask_distribution(update, context)

async def ask_speed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    temp = u_data['temp_project']
    text = (
        f"⚡ **STEP 4 • গতি নির্বাচন**\n"
        f"───────────────────\n\n"
        f"🔝 **ডেলিভারি গতি নির্বাচন করুন:**\n\n"
        f"👉 **নির্বাচিত:** ⚡ {temp['speed']} ডেলিভারি"
    )
    keyboard = [
        [InlineKeyboardButton("দ্রুত", callback_data="spd_দ্রুত"), InlineKeyboardButton("মাঝারি", callback_data="spd_মাঝারি"), InlineKeyboardButton("ধীর", callback_data="spd_ধীর")],
        [InlineKeyboardButton("কাস্টমাইজ", callback_data="spd_কাস্টমাইজ")],
        [InlineKeyboardButton("↩ ব্যাক", callback_data="back_dist"), InlineKeyboardButton("চালিয়ে যান ✅", callback_data="spd_done")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return STEP_SPEED

async def speed_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u_data = get_user_data(query.from_user.id)
    temp = u_data['temp_project']
    
    if query.data == "spd_done": return await ask_views(update, context)
    if query.data == "back_dist": return await ask_distribution(update, context)
    if query.data == "spd_কাস্টমাইজ":
        await query.answer("তাৎক্ষণিক ডেলিভারি মোড সক্রিয়।", show_alert=True)
        return STEP_SPEED

    temp['speed'] = query.data.split("_")[1]
    save_data(db)
    await query.answer(f"গতি: {temp['speed']}")
    return await ask_speed(update, context)

async def ask_views(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    temp = u_data['temp_project']
    vw_str = f"{temp['views']} ভিউ(তাৎক্ষণিক)" if temp['views'] > 0 else "কোনো ভিউ নেই"
    text = (
        f"👁 **STEP 5 • ভিউ কনফিগারেশন**\n"
        f"───────────────────\n\n"
        f"প্রতি পোস্টে কত ভিউ?\n"
        f"👉 **নির্বাচিত:** {vw_str}"
    )
    keyboard = [
        [InlineKeyboardButton("0", callback_data="vw_0"), InlineKeyboardButton("10", callback_data="vw_10"), InlineKeyboardButton("30", callback_data="vw_30")],
        [InlineKeyboardButton("🔒 50", callback_data="locked_vw"), InlineKeyboardButton("🔒 80", callback_data="locked_vw"), InlineKeyboardButton("🔒 100", callback_data="locked_vw")],
        [InlineKeyboardButton("🔒 200", callback_data="locked_vw"), InlineKeyboardButton("🔒 300", callback_data="locked_vw"), InlineKeyboardButton("কাস্টম", callback_data="locked_vw")],
        [InlineKeyboardButton("⚡ Speed (Fast ⚡)", callback_data="spd_info")],
        [InlineKeyboardButton("↩ ব্যাক", callback_data="back_speed"), InlineKeyboardButton("চালিয়ে যান ✅", callback_data="vw_done")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return STEP_VIEWS

async def views_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u_data = get_user_data(query.from_user.id)
    temp = u_data['temp_project']
    
    if query.data == "vw_done": return await show_review(update, context)
    if query.data == "back_speed": return await ask_speed(update, context)
    if query.data in ["locked_vw", "spd_info"]:
        await query.answer("ভিউ নির্বাচন সম্পন্ন হয়েছে।", show_alert=True)
        return STEP_VIEWS

    temp['views'] = int(query.data.split("_")[1])
    save_data(db)
    await query.answer(f"ভিউ: {temp['views']}")
    return await ask_views(update, context)

async def show_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    temp = u_data['temp_project']
    emojis = " ".join(temp['emojis'])
    
    text = (
        f"✨ **FINAL REVIEW** ✨\n"
        f"───────────────────\n\n"
        f"📺 **চ্যানেল:** {temp['channel_name']} (`{temp['channel_id']}`)\n\n"
        f"┌────────────────────\n"
        f"│ 😊 ইমোজি: {emojis}\n"
        f"│ 🎯 মোড: সমস্ত\n"
        f"│ 🚀 প্রতিক্রিয়া: {temp['count']}\n"
        f"│ 👁 ভিউ: 👁 {temp['views']} (⚡ তাৎক্ষণিক)\n"
        f"│ ⚡ প্রতিক্রিয়া বিতরণ: ⚡ {temp['speed']}\n"
        f"│ ⚙️ বিতরণ: {temp['dist']}\n"
        f"│ 🔀 এলোমেলো করুন: বন্ধ\n"
        f"└────────────────────"
    )
    keyboard = [
        [InlineKeyboardButton("✅ প্রকল্প তৈরি করুন", callback_data="create_final")],
        [InlineKeyboardButton("✏️ সম্পাদনা করুন", callback_data="back_views"), InlineKeyboardButton("❌ বাতিল করুন", callback_data="cancel_flow")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return STEP_REVIEW

# 💾 'প্রকল্প তৈরি করুন' এ ক্লিক করলে ফাইনাল সেভ হওয়া
async def finalize_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    u_data = get_user_data(query.from_user.id)
    temp = u_data['temp_project']

    # ইউজার প্রজেক্ট লিস্টে সেভ করা
    new_proj = {
        "channel_name": temp['channel_name'],
        "channel_id": temp['channel_id'],
        "emojis": temp['emojis'],
        "count": temp['count'],
        "dist": temp['dist'],
        "speed": temp['speed'],
        "views": temp['views']
    }
    
    u_data['projects'].append(new_proj)
    save_data(db)
    
    await query.message.reply_text(
        f"🎉 **প্রকল্প সফলভাবে তৈরি এবং সেভ করা হয়েছে!**\n\n"
        f"📁 **চ্যানেল:** {temp['channel_name']}\n"
        f"😊 **ইমোজি:** {' '.join(temp['emojis'])}\n"
        f"🚀 **প্রতিক্রিয়া:** {temp['count']}\n\n"
        f"এখন এই চ্যানেলে কোনো নতুন পোস্ট দেওয়া হলে স্বয়ংক্রিয়ভাবে প্রতিক্রিয়া পাঠানো হবে।",
        reply_markup=get_user_keyboard(), parse_mode='Markdown'
    )
    return ConversationHandler.END

async def cancel_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.message.reply_text("প্রক্রিয়া বাতিল করা হয়েছে।", reply_markup=get_user_keyboard())
    else:
        await update.message.reply_text("প্রক্রিয়া বাতিল করা হয়েছে।", reply_markup=get_user_keyboard())
    return ConversationHandler.END

# 👑 --- Admin Handlers ---
async def start_add_credit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return ConversationHandler.END
    await update.message.reply_text("➕ **ফরম্যাট লিখে পাঠান:** `User_ID Amount`\nযেমন: `12345678 100`", parse_mode='Markdown')
    return STEP_ADMIN_ADD_CREDIT

async def process_admin_credit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        parts = update.message.text.split()
        target_id, amount = parts[0], int(parts[1])
        if target_id in db['users']:
            db['users'][target_id]['credit'] += amount
            save_data(db)
            await update.message.reply_text(f"✅ ইউজার `{target_id}` এর নতুন ক্রেডিট: {db['users'][target_id]['credit']}", parse_mode='Markdown', reply_markup=get_admin_keyboard())
        else:
            await update.message.reply_text("❌ ইউজার পাওয়া যায়নি!", reply_markup=get_admin_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ ভুল ফরম্যাট! Error: {e}", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

async def start_block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return ConversationHandler.END
    await update.message.reply_text("🚫 **ব্লক করার জন্য ইউজার আইডি লিখে পাঠান:**", parse_mode='Markdown')
    return STEP_ADMIN_BLOCK_USER

async def process_admin_block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_id = update.message.text.strip()
    if target_id not in db['blocked']:
        db['blocked'].append(target_id)
        save_data(db)
        await update.message.reply_text(f"🚫 ইউজার `{target_id}` কে ব্লক করা হয়েছে।", parse_mode='Markdown', reply_markup=get_admin_keyboard())
    else:
        await update.message.reply_text("⚠️ ইউজার আগেই ব্লক করা আছে।", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return ConversationHandler.END
    await update.message.reply_text("📢 **সবাইকে পাঠানোর মেসেজটি লিখুন:**", parse_mode='Markdown')
    return STEP_ADMIN_BROADCAST

async def process_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_text = update.message.text
    count = 0
    for uid in db['users']:
        try:
            await context.bot.send_message(chat_id=int(uid), text=f"📢 **অ্যাডমিন বার্তা:**\n\n{msg_text}", parse_mode='Markdown')
            count += 1
        except Exception:
            pass
    await update.message.reply_text(f"🎉 মোট `{count}` জনের কাছে মেসেজ পাঠানো হয়েছে!", parse_mode='Markdown', reply_markup=get_admin_keyboard())
    return ConversationHandler.END

# --- Main Navigation Handler ---
async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id in db["blocked"]: return

    text = update.message.text
    u_data = get_user_data(user_id)

    # 👑 Admin Navigation
    if update.effective_user.id in ADMIN_IDS:
        if text == "📊 বট স্ট্যাটাস":
            return await admin_panel_command(update, context)
        elif text == "📋 ইউজার লিস্ট":
            user_list_text = "📋 **ইউজার তালিকা:**\n───────────────────\n"
            for uid, uinfo in list(db['users'].items())[:20]:
                user_list_text += f"🆔 `{uid}` | 💎 ক্রেডিট: {uinfo.get('credit', 0)}\n"
            return await update.message.reply_text(user_list_text, parse_mode='Markdown', reply_markup=get_admin_keyboard())
        elif text == "🔙 ইউজার প্যানেলে যান":
            return await update.message.reply_text("🏠 সাধারণ ইউজার মেনু:", reply_markup=get_user_keyboard())

    # 📱 Standard Navigation
    if text == "🌟 পরিকল্পনা এবং ভারসাম্য":
        p_count = len(u_data.get('projects', []))
        response_text = (
            f"🌟 **PLAN এবং BALANCE**\n"
            f"───────────────────\n\n"
            f"💎 **ক্রেডিট:** {u_data['credit']}\n"
            f"📊 **ব্যয়:** {u_data['cost']}\n"
            f"📁 **প্রকল্প:** {p_count}"
        )
        await update.message.reply_text(response_text, parse_mode='Markdown', reply_markup=get_user_keyboard())

    elif text == "📁 আমার প্রকল্প":
        projects = u_data.get('projects', [])
        if projects:
            p_text = "📁 **YOUR PROJECTS**\n───────────────────\n"
            for idx, p in enumerate(projects, 1):
                em_str = " ".join(p['emojis'])
                p_text += f"◆ {idx}. **{p['channel_name']}** 🌍\nRxn: {p['count']} | {em_str}\n\n"
            await update.message.reply_text(p_text, parse_mode='Markdown', reply_markup=get_user_keyboard())
        else:
            await update.message.reply_text("❌ আপনার কোনো সক্রিয় প্রকল্প/চ্যানেল নেই।", reply_markup=get_user_keyboard())

    # 💳 রিচার্জ সেকশনে ইউজারনেম যুক্তকরণ
    elif text == "💰 রিচার্জ করুন":
        clean_admin = ADMIN_USERNAME.replace("@", "")
        recharge_text = (
            f"💳 **অ্যাকাউন্ট রিচার্জ করুণ**\n"
            f"───────────────────\n\n"
            f"👤 **আপনার আইডি:** `{user_id}`\n"
            f"💎 **বর্তমান ক্রেডিট:** {u_data['credit']}\n\n"
            f"রিচার্জ করতে নিচের অ্যাডমিনের সাথে সরাসরি যোগাযোগ করুন:"
        )
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 অ্যাডমিনের সাথে যোগাযোগ করুন", url=f"https://t.me/{clean_admin}")]
        ])
        await update.message.reply_text(recharge_text, parse_mode='Markdown', reply_markup=inline_kb)

    elif text == "⚙️ আরও":
        await update.message.reply_text("একটি বিকল্প বেছে নিন:", reply_markup=get_more_keyboard())

    elif text == "🔙 ব্যাক":
        await update.message.reply_text("প্রধান মেনু:", reply_markup=get_user_keyboard())

    elif text == "🔗 রেফার করুন এবং আয় করুন":
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
        msg = (
            f"🎁 **বন্ধুদের আমন্ত্রণ জানান এবং ক্রেডিট অর্জন করুন!**\n\n"
            f"**আপনার রেফারেল লিঙ্ক:**\n`{ref_link}`\n\n"
            f"📊 **আপনার পরিসংখ্যান:**\n"
            f"• মোট রেফারেল: {u_data['ref_count']}\n"
            f"• অর্জিত ক্রেডিট: {u_data['ref_credit']}\n\n"
            f"• কেউ আপনার লিঙ্কের মাধ্যমে যোগদান করলে, আপনি +50 ক্রেডিট পাবেন।"
        )
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=get_more_keyboard())

    elif text == "🎁 দৈনিক উপহার":
        today = date.today().isoformat()
        if u_data['last_daily_bonus'] == today:
            await update.message.reply_text("❌ আপনি আজকের দৈনিক উপহার ইতোমধ্যে নিয়ে নিয়েছেন! আগামীকাল আবার আসুন।", reply_markup=get_more_keyboard())
        else:
            bonus = 24
            u_data['credit'] += bonus
            u_data['last_daily_bonus'] = today
            save_data(db)
            await update.message.reply_text(f"🎉 আপনি দৈনিক উপহার হিসেবে **{bonus} ক্রেডিট** পেয়েছেন! 🎁", parse_mode='Markdown', reply_markup=get_more_keyboard())

# ⚡ চ্যানেলে নতুন পোস্ট এলে স্বয়ংক্রিয় রিয়্যাকশন দেয়া
async def auto_react_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.channel_post
        if not message: return
        channel_id = str(message.chat_id)
        channel_username = f"@{message.chat.username}" if message.chat.username else ""

        target_emojis = ["👍", "❤️", "🔥"]

        # ডাটাবেস থেকে সেভ হওয়া চ্যানেল ম্যাচ করা
        for uid, uinfo in db["users"].items():
            for proj in uinfo.get("projects", []):
                if proj["channel_id"] == channel_id or (channel_username and proj["channel_id"] == channel_username):
                    target_emojis = proj["emojis"]
                    break

        chosen_emoji = random.choice(target_emojis) if target_emojis else "👍"
        await context.bot.set_message_reaction(
            chat_id=message.chat_id,
            message_id=message.message_id,
            reaction=[ReactionTypeEmoji(emoji=chosen_emoji)]
        )
    except Exception as e:
        logging.error(f"Failed reaction: {e}")

if __name__ == '__main__':
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^➕ অটো রিয়্যাকশন প্রজেক্ট যোগ করুন$"), start_project),
            MessageHandler(filters.Regex("^💳 ক্রেডিট কন্ট্রোল$"), start_add_credit),
            MessageHandler(filters.Regex("^🚫 ইউজার ব্লক/রিমুভ$"), start_block_user),
            MessageHandler(filters.Regex("^📢 অল ইউজার ব্রডকাস্ট$"), start_broadcast),
        ],
        states={
            STEP_CHANNEL: [MessageHandler(filters.ALL & ~filters.COMMAND, save_channel)],
            STEP_EMOJI: [CallbackQueryHandler(emoji_callback, pattern="^em_")],
            STEP_COUNT: [CallbackQueryHandler(count_callback, pattern="^(cnt_|back_emoji|locked)")],
            STEP_DISTRIBUTION: [CallbackQueryHandler(distribution_callback, pattern="^(dist_|back_count)")],
            STEP_SPEED: [CallbackQueryHandler(speed_callback, pattern="^(spd_|back_dist)")],
            STEP_VIEWS: [CallbackQueryHandler(views_callback, pattern="^(vw_|back_speed|locked_vw|spd_info)")],
            STEP_REVIEW: [
                CallbackQueryHandler(finalize_project, pattern="^create_final"),
                CallbackQueryHandler(ask_views, pattern="^back_views"),
                CallbackQueryHandler(cancel_flow, pattern="^cancel_flow")
            ],
            STEP_ADMIN_ADD_CREDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_credit)],
            STEP_ADMIN_BLOCK_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_block)],
            STEP_ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_broadcast)]
        },
        fallbacks=[
            CommandHandler('start', start),
            MessageHandler(filters.Regex("^(বাতিল করুন|🔙 ব্যাক)$"), cancel_flow)
        ]
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('admin', admin_panel_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu))
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL, auto_react_channel_post))

    print("🤖 Bot Ready...")
    app.run_polling()
