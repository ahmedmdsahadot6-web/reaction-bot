import logging
import os
import json
import re
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

# 🌐 Keep-Alive Web Server
web_app = Flask('')

@web_app.route('/')
def home():
    return "SMM Auto Reaction Bot Engine: ACTIVE 24/7"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# 🔑 কনফিগারেশন
BOT_TOKEN = "8320025447:AAFWnP_asWXs6WXS-h_gPAy6Baikd6-4jMc"
BOT_USERNAME = "TGSUPER_SERVICE_BOT"
ADMIN_IDS = [8454401183, 8457454660]
ADMIN_USERNAME = "@SOYABUR_AS_LEADER"

# 🌐 1xpanel SMM Config (Service #1936)
SMM_API_URL = "https://1xpanel.com/api/v2"
SMM_API_KEY = "0b2fbfd793c2cc3cec163c1faaaa318c"
REACTION_SERVICE_ID = "1936"

DB_FILE = "database.json"

# 📝 Logging সিস্টেম
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 💾 ডাটাবেজ
def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load DB: {e}")
            return {"users": {}, "blocked": []}
    return {"users": {}, "blocked": []}

def save_data(data):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save DB: {e}")

db = load_data()
if "users" not in db: db["users"] = {}
if "blocked" not in db: db["blocked"] = []

# States
(STEP_CHANNEL, STEP_EMOJI, STEP_DISTRIBUTION, STEP_SPEED, STEP_COUNT, STEP_REVIEW, 
 STEP_ADMIN_ADD_CREDIT, STEP_ADMIN_BLOCK_USER, STEP_ADMIN_BROADCAST) = range(9)

def get_user_data(user_id):
    str_id = str(user_id)
    if str_id not in db["users"]:
        db["users"][str_id] = {
            "credit": 500,
            "ref_count": 0,
            "ref_credit": 0,
            "projects": [],
            "last_daily_bonus": None
        }
        save_data(db)
    return db["users"][str_id]

# 📱 Keyboards
def get_user_keyboard():
    kb = [
        [KeyboardButton("➕ অটো রিয়্যাকশন প্রজেক্ট যোগ করুন")],
        [KeyboardButton("📁 আমার প্রকল্প"), KeyboardButton("⚙️ আরও")],
        [KeyboardButton("🌟 পরিকল্পনা এবং ভারসাম্য"), KeyboardButton("💰 রিচার্জ করুন")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def get_more_keyboard():
    kb = [
        [KeyboardButton("👤 প্রোফাইল"), KeyboardButton("🎁 দৈনিক বোনাস")],
        [KeyboardButton("🔗 রেফারেল লিংক"), KeyboardButton("🆘 সহায়তা")],
        [KeyboardButton("🔙 ব্যাক")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def get_admin_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📊 বট স্ট্যাটাস"), KeyboardButton("📋 ইউজার লিস্ট")],
        [KeyboardButton("💳 ক্রেডিট কন্ট্রোল"), KeyboardButton("🚫 ইউজার ব্লক/রিমুভ")],
        [KeyboardButton("📢 অল ইউজার ব্রডকাস্ট"), KeyboardButton("🏠 প্রধান মেনু")]
    ], resize_keyboard=True)

def cancel_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("❌ বাতিল করুন")]], resize_keyboard=True)

# 🚀 /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    str_id = str(user.id)

    if str_id in db["blocked"]:
        await update.message.reply_text("🚫 আপনাকে এই বট থেকে ব্লক করা হয়েছে।")
        return

    if context.args and len(context.args) > 0:
        referrer_id = context.args[0]
        if referrer_id != str_id and referrer_id in db["users"] and str_id not in db["users"]:
            db["users"][referrer_id]["ref_count"] += 1
            db["users"][referrer_id]["credit"] += 100
            db["users"][referrer_id]["ref_credit"] += 100
            save_data(db)

    get_user_data(user.id)
    await update.message.reply_text(
        f"👋 স্বাগতম {user.first_name}!\n\n"
        f"🚀 **Multi-Reaction SMM Engine Active**\n"
        f"চ্যানেলে নতুন পোস্ট করার সাথে সাথে স্বয়ংক্রিয় রিয়্যাকশন পেতে প্রজেক্ট যোগ করুন।",
        reply_markup=get_user_keyboard()
    )

async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ আপনি অ্যাডমিন নন!")
        return

    text = (
        f"👑 **ADMIN CONTROL PANEL**\n"
        f"───────────────────\n"
        f"👥 মোট ইউজার: {len(db['users'])}\n"
        f"🚫 ব্লককৃত ইউজার: {len(db['blocked'])}\n"
        f"───────────────────"
    )
    await update.message.reply_text(text, reply_markup=get_admin_keyboard())

# --- ➕ প্রজেক্ট তৈরি ---
async def start_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u_data = get_user_data(user_id)

    if u_data['credit'] <= 0:
        clean_admin = ADMIN_USERNAME.replace("@", "")
        inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton("💬 অ্যাডমিনকে মেসেজ দিন", url=f"https://t.me/{clean_admin}")]])
        await update.message.reply_text("⚠️ আপনার পর্যাপ্ত কয়েন নেই!\nনতুন প্রজেক্ট তৈরি করতে রিচার্জ করুন।", reply_markup=inline_kb)
        return ConversationHandler.END

    context.user_data['draft_project'] = {
        "target_url": None,
        "username": None,
        "emojis": ["POSITIVE"],
        "distribution": "এলোমেলো",
        "speed": "তাৎক্ষণিক ডেলিভারি (দ্রুত)",
        "count": 100
    }

    text = (
        f"🛰 **ধাপ ১ • চ্যানেল সেটআপ**\n"
        f"───────────────────\n\n"
        f"১) @{BOT_USERNAME} কে আপনার চ্যানেলে **Admin** বানান।\n"
        f"২) আপনার চ্যানেলের পাবলিক লিঙ্কটি পাঠান (যেমন: `https://t.me/your_channel`):"
    )
    await update.message.reply_text(text, reply_markup=cancel_keyboard())
    return STEP_CHANNEL

async def save_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    txt = (msg.text or "").strip()

    if txt in ["❌ বাতিল করুন", "বাতিল করুন"]:
        context.user_data.pop('draft_project', None)
        await msg.reply_text("প্রক্রিয়া বাতিল করা হলো।", reply_markup=get_user_keyboard())
        return ConversationHandler.END

    if "https://t.me/" not in txt:
        await msg.reply_text("❌ লিঙ্কটি সঠিক নয়! লিঙ্কের শুরুতে 'https://t.me/' থাকতে হবে। আবার চেষ্টা করুন:")
        return STEP_CHANNEL

    match = re.search(r'https://t\.me/([^\s/]+)', txt)
    if not match:
        await msg.reply_text("❌ সঠিক চ্যানেল লিংক পাওয়া যায়নি! আবার লিংক পাঠান:")
        return STEP_CHANNEL

    ch_username = match.group(1).replace("@", "")
    context.user_data['draft_project']['target_url'] = f"https://t.me/{ch_username}"
    context.user_data['draft_project']['username'] = ch_username

    return await render_emoji_menu(update, context)

async def render_emoji_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"📝 **ধাপ ২ • ইমোজি প্রকার**\n"
        f"───────────────────\n\n"
        f"👉 এই সার্ভিসের জন্য পজিটিভ ( Positive 👍❤️🔥 ) রিয়্যাকশন সেট করা রয়েছে।\n\n"
        f"'চালিয়ে যান ➔' বাটনে চাপুন:"
    )

    keyboard = [
        [InlineKeyboardButton("চালিয়ে যান ➔", callback_data="em_done")]
    ]

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await context.bot.send_message(chat_id=update.effective_user.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    return STEP_EMOJI

async def emoji_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await render_distribution_menu(update, context)

async def render_distribution_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get('draft_project', {})
    current_dist = draft.get('distribution', 'এলোমেলো')
    
    text = (
        f"⚙️ **ধাপ ৩ • বিতরণের ধরন**\n"
        f"───────────────────\n\n"
        f"👉 বর্তমান সিলেক্টেড: **{current_dist}**"
    )
    keyboard = [
        [InlineKeyboardButton("🎲 এলোমেলো", callback_data="dist_random")],
        [InlineKeyboardButton("⚖️ সব সমানভাবে", callback_data="dist_equal")],
        [InlineKeyboardButton("চালিয়ে যান ➔", callback_data="dist_done")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return STEP_DISTRIBUTION

async def distribution_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get('draft_project', {})

    if query.data == "dist_done":
        return await render_speed_menu(update, context)

    dist_map = {"dist_random": "এলোমেলো", "dist_equal": "সব সমানভাবে"}
    draft['distribution'] = dist_map.get(query.data, "এলোমেলো")
    return await render_distribution_menu(update, context)

async def render_speed_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get('draft_project', {})
    current_speed = draft.get('speed', 'তাৎক্ষণিক ডেলিভারি (দ্রুত)')

    text = (
        f"⚡ **ধাপ ৪ • গতি নির্বাচন**\n"
        f"───────────────────\n\n"
        f"👉 বর্তমান সিলেক্টেড: **{current_speed}**"
    )
    keyboard = [
        [InlineKeyboardButton("⚡ দ্রুত", callback_data="spd_fast"), InlineKeyboardButton("⚖️ মাঝারি", callback_data="spd_medium")],
        [InlineKeyboardButton("চালিয়ে যান ➔", callback_data="spd_done")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return STEP_SPEED

async def speed_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get('draft_project', {})

    if query.data == "spd_done":
        return await render_count_menu(update, context)

    speed_map = {"spd_fast": "তাৎক্ষণিক ডেলিভারি (দ্রুত)", "spd_medium": "মাঝারি"}
    draft['speed'] = speed_map.get(query.data, "তাৎক্ষণিক ডেলিভারি (দ্রুত)")
    return await render_speed_menu(update, context)

async def render_count_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get('draft_project', {})
    text = (
        f"📊 **ধাপ ৫ • রিয়্যাকশন সংখ্যা**\n"
        f"───────────────────\n"
        f"⚠️ **নোট:** মিনিমাম ১০০ টি রিয়্যাকশন প্রয়োজন।\n\n"
        f"👉 বর্তমান রিয়্যাকশন সংখ্যা: {draft.get('count', 100)}"
    )
    keyboard = [
        [InlineKeyboardButton("100", callback_data="cnt_100"), InlineKeyboardButton("200", callback_data="cnt_200"), InlineKeyboardButton("300", callback_data="cnt_300")],
        [InlineKeyboardButton("500", callback_data="cnt_500"), InlineKeyboardButton("1000", callback_data="cnt_1000")],
        [InlineKeyboardButton("চালিয়ে যান ✅", callback_data="cnt_done")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return STEP_COUNT

async def count_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get('draft_project', {})

    if query.data == "cnt_done": return await render_review_menu(update, context)

    draft['count'] = int(query.data.split("_")[1])
    return await render_count_menu(update, context)

async def render_review_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get('draft_project', {})

    text = (
        f"✨ **চূড়ান্ত তথ্য যাচাই** ✨\n"
        f"───────────────────\n\n"
        f"🔗 চ্যানেল লিঙ্ক: {draft.get('target_url')}\n"
        f"😊 রিয়্যাকশন টাইপ: POSITIVE (পজিটিভ)\n"
        f"⚙️ বিতরণের ধরন: {draft.get('distribution')}\n"
        f"⚡ ডেলিভারি গতি: {draft.get('speed')}\n"
        f"🚀 রিয়্যাকশন সংখ্যা: {draft.get('count')}\n\n"
        f"সবকিছু ঠিক থাকলে '✅ প্রকল্প তৈরি করুন' বাটনে চাপ দিন।"
    )
    keyboard = [
        [InlineKeyboardButton("✅ প্রকল্প তৈরি করুন", callback_data="create_final")],
        [InlineKeyboardButton("❌ বাতিল করুন", callback_data="cancel_flow")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return STEP_REVIEW

async def finalize_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    draft = context.user_data.get('draft_project')
    if not draft or not draft.get('target_url'):
        await query.message.reply_text("❌ সমস্যা হয়েছে, আবার চেষ্টা করুন!", reply_markup=get_user_keyboard())
        return ConversationHandler.END

    ch_username = draft.get('username')
    try:
        chat_info = await context.bot.get_chat(f"@{ch_username}")
        channel_id = str(chat_info.id)
        channel_title = chat_info.title or ch_username
        logger.info(f"Project Channel Resolved: Name='{channel_title}', ID='{channel_id}'")

        # 📢 কানেক্টেড মেসেজ শুধু চ্যানেলে যাবে
        channel_post_text = (
            f"🎉 **Bot Connected Successfully!**\n\n"
            f"✅ এই চ্যানেলের সাথে অটো রিয়্যাকশন বট সফলভাবে যুক্ত করা হয়েছে।\n"
            f"🚀 এখন থেকে প্রতিটি নতুন পোস্টে অটোমেটিক রিয়্যাকশন সার্ভিস সক্রিয় থাকবে।"
        )
        await context.bot.send_message(chat_id=chat_info.id, text=channel_post_text)

    except Exception as e:
        logger.error(f"Failed to fetch or send message to channel @{ch_username}: {e}")
        await query.message.reply_text(
            f"❌ চ্যানেলে কানেক্ট করা সম্ভব হয়নি!\n\n"
            f"⚠️ নিশ্চিত করুন বটকে চ্যানেলে **Admin** করা হয়েছে এবং **Post Messages** পারমিশন অন রাখা আছে।\n\n"
            f"Error: {e}", 
            reply_markup=get_user_keyboard()
        )
        context.user_data.pop('draft_project', None)
        return ConversationHandler.END

    u_data = get_user_data(user_id)
    draft['channel_id'] = channel_id
    draft['channel_name'] = channel_title

    u_data['projects'] = [p for p in u_data.get('projects', []) if str(p.get('channel_id')) != channel_id]
    u_data['projects'].append(draft)
    save_data(db)

    context.user_data.pop('draft_project', None)

    await query.message.reply_text(
        f"🎉 **প্রকল্প সফলভাবে তৈরি হয়েছে!**\n\n"
        f"📁 চ্যানেল: {channel_title}\n"
        f"🆔 চ্যানেল আইডি: `{channel_id}`\n"
        f"🚀 রিয়্যাকশন সংখ্যা: {draft['count']} টি\n\n"
        f"✅ চ্যানেলেও নোটিফিকেশন পাঠানো হয়েছে!",
        reply_markup=get_user_keyboard()
    )
    return ConversationHandler.END

async def cancel_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('draft_project', None)
    msg_text = "প্রক্রিয়া বাতিল করা হলো।"
    if update.callback_query:
        await update.callback_query.message.reply_text(msg_text, reply_markup=get_user_keyboard())
    else:
        await update.message.reply_text(msg_text, reply_markup=get_user_keyboard())
    return ConversationHandler.END

# 🌐 1xpanel API Engine
def send_smm_reaction_order(post_link, count):
    payload = {
        'key': SMM_API_KEY,
        'action': 'add',
        'service': REACTION_SERVICE_ID,
        'link': post_link,
        'quantity': max(100, count),
        'reactions': 'POSITIVE'
    }
    
    logger.info(f"[SMM-API] Sending Request -> URL: {post_link} | Quantity: {payload['quantity']}")
    
    try:
        response = requests.post(SMM_API_URL, data=payload, timeout=20)
        try:
            res_json = response.json()
            logger.info(f"[SMM-API] Response: {res_json}")
        except Exception:
            return False, None, "Non-JSON response from SMM server"
        
        if "order" in res_json:
            return True, str(res_json["order"]), None
        elif "orders" in res_json:
            return True, str(res_json["orders"]), None
        else:
            err_msg = res_json.get("error", "Unknown API Error")
            return False, None, err_msg
            
    except requests.exceptions.Timeout:
        return False, None, "SMM Server Timeout"
    except Exception as e:
        return False, None, f"Server Error: {str(e)}"

# 🔔 চ্যানেলে নতুন পোস্ট হলেই ইউজারের ইনবক্সে (বটে) নোটিফিকেশন পাঠাবে
async def auto_react_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.channel_post or update.edited_channel_post
    if not msg or not msg.chat:
        return

    raw_channel_id = str(msg.chat.id)
    chat_username = (msg.chat.username or "").lower()
    post_id = msg.message_id

    logger.info(f"📢 [POST DETECTED] ID: {raw_channel_id} | Username: @{chat_username} | Message ID: {post_id}")

    clean_admin = ADMIN_USERNAME.replace("@", "")
    admin_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("💬 অ্যাডমিনকে জানান", url=f"https://t.me/{clean_admin}")]])

    matched_projects = []

    for uid, uinfo in db["users"].items():
        for proj in uinfo.get("projects", []):
            proj_cid = str(proj.get("channel_id", ""))
            proj_uname = str(proj.get("username", "")).lower().replace("@", "")

            if (proj_cid and proj_cid == raw_channel_id) or \
               (chat_username and proj_uname == chat_username) or \
               (proj_cid.replace("-100", "") == raw_channel_id.replace("-100", "")):
                matched_projects.append((uid, uinfo, proj))

    if not matched_projects:
        logger.info(f"⚠️ No active project found for post in channel {raw_channel_id}")
        return

    for uid, uinfo, proj in matched_projects:
        user_chat_id = int(uid)
        ch_name = proj.get("channel_name", "চ্যানেল")

        if chat_username:
            post_link = f"https://t.me/{chat_username}/{post_id}"
        elif proj.get("username"):
            post_link = f"https://t.me/{proj.get('username')}/{post_id}"
        else:
            clean_cid = raw_channel_id.replace("-100", "")
            post_link = f"https://t.me/c/{clean_cid}/{post_id}"

        # 📨 ইউজারের ইনবক্সে (বটে) নতুন পোস্টের নোটিফিকেশন ও লিংক পাঠানো
        post_btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 পোস্টে যান", url=post_link)]])
        try:
            await context.bot.send_message(
                chat_id=user_chat_id,
                text=f"🔔 **চ্যানেলে একটি নতুন পোস্ট করা হয়েছে!**\n\n"
                     f"📢 **চ্যানেল:** {ch_name}\n"
                     f"🔗 **পোস্ট লিঙ্ক:** {post_link}\n\n"
                     f"⏳ অটো-রিয়্যাকশন প্রসেস করা হচ্ছে...",
                reply_markup=post_btn
            )
        except Exception as e:
            logger.error(f"Failed to send post notification to user {uid}: {e}")

        # কয়েন চেক
        if uinfo.get("credit", 0) <= 0:
            try:
                await context.bot.send_message(
                    chat_id=user_chat_id,
                    text=f"🚨 **রিঅ্যাকশন পাঠানো সম্ভব হয়নি!**\n\n"
                         f"📢 **চ্যানেল:** {ch_name}\n"
                         f"❌ **কারণ:** আপনার একাউন্টে পর্যাপ্ত কয়েন নেই!",
                    reply_markup=admin_keyboard
                )
            except Exception as e:
                logger.error(f"Failed to send low balance notice: {e}")
            continue

        target_count = max(100, proj.get("count", 100))

        # API রিকোয়েস্ট পাঠানো
        success, order_id, error_reason = await asyncio.to_thread(
            send_smm_reaction_order, post_link, target_count
        )

        if success:
            uinfo["credit"] -= 10
            if uinfo["credit"] < 0: uinfo["credit"] = 0
            save_data(db)

            try:
                await context.bot.send_message(
                    chat_id=user_chat_id,
                    text=f"🎉 **রিয়্যাকশন অর্ডার সফল হয়েছে!**\n\n"
                         f"📢 **চ্যানেল:** {ch_name}\n"
                         f"🚀 **পরিমাণ:** {target_count} টি (POSITIVE)\n"
                         f"🆔 **অর্ডার আইডি:** `{order_id}`\n"
                         f"💰 **অবশিষ্ট কয়েন:** {uinfo['credit']}"
                )
            except Exception as e:
                logger.error(f"Failed to send success notice: {e}")
        else:
            try:
                await context.bot.send_message(
                    chat_id=user_chat_id,
                    text=f"🚨 **অর্ডার ব্যর্থ হয়েছে!**\n\n"
                         f"📢 **চ্যানেল:** {ch_name}\n"
                         f"📌 **পোস্ট লিঙ্ক:** {post_link}\n"
                         f"❌ **এরর কারণ:** `{error_reason}`\n\n"
                         f"💡 আপনার কয়েন কাটা হয়নি।",
                    reply_markup=admin_keyboard
                )
            except Exception as e:
                logger.error(f"Failed to send failure notice: {e}")

# 👑 Admin commands
async def start_add_credit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return ConversationHandler.END
    await update.message.reply_text("💳 কয়েন যোগ করতে লিখুন: `User_ID Amount`\nযেমন: `8454401183 500`", reply_markup=cancel_keyboard())
    return STEP_ADMIN_ADD_CREDIT

async def process_admin_credit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        parts = update.message.text.split()
        target_id, amount = parts[0], int(parts[1])
        if target_id in db['users']:
            db['users'][target_id]['credit'] += amount
            save_data(db)
            await update.message.reply_text(f"✅ ইউজার {target_id} এর বর্তমান ব্যালেন্স: {db['users'][target_id]['credit']}", reply_markup=get_admin_keyboard())
        else:
            await update.message.reply_text("❌ ইউজার আইডি পাওয়া যায়নি!", reply_markup=get_admin_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ এরর: {e}", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

async def start_block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return ConversationHandler.END
    await update.message.reply_text("🚫 ব্লক/আনব্লক করতে ইউজার আইডি লিখুন:", reply_markup=cancel_keyboard())
    return STEP_ADMIN_BLOCK_USER

async def process_admin_block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_id = update.message.text.strip()
    if target_id not in db['blocked']:
        db['blocked'].append(target_id)
        save_data(db)
        await update.message.reply_text(f"🚫 ইউজার {target_id} কে ব্লক করা হয়েছে।", reply_markup=get_admin_keyboard())
    else:
        db['blocked'].remove(target_id)
        save_data(db)
        await update.message.reply_text(f"✅ ইউজার {target_id} কে আনব্লক করা হয়েছে।", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return ConversationHandler.END
    await update.message.reply_text("📢 ব্রডকাস্ট করার মেসেজটি পাঠান:", reply_markup=cancel_keyboard())
    return STEP_ADMIN_BROADCAST

async def process_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_text = update.message.text
    count = 0
    for uid in db['users']:
        try:
            await context.bot.send_message(chat_id=int(uid), text=f"📢 **বিজ্ঞপ্তি:**\n\n{msg_text}")
            count += 1
            await asyncio.sleep(0.05)
        except Exception: pass
    await update.message.reply_text(f"🎉 মোট {count} জন ইউজারের কাছে মেসেজ পাঠানো হয়েছে!", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

# Menu
async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    str_id = str(user_id)
    text = update.message.text or ""
    u_data = get_user_data(str_id)

    if text and text.strip().lower() in ["অ্যাডমিন", "admin"]:
        return await admin_panel_command(update, context)

    if user_id in ADMIN_IDS:
        if text == "📊 বট স্ট্যাটাস":
            return await admin_panel_command(update, context)
        elif text == "📋 ইউজার লিস্ট":
            u_list = "📋 **ইউজার তালিকা:**\n───────────────────\n"
            for uid, uinfo in list(db['users'].items())[:15]:
                u_list += f"🆔 `{uid}` | 💎 কয়েন: {uinfo.get('credit', 0)}\n"
            return await update.message.reply_text(u_list, reply_markup=get_admin_keyboard())
        elif text == "🏠 প্রধান মেনু":
            return await update.message.reply_text("🏠 প্রধান মেনু:", reply_markup=get_user_keyboard())

    if text == "⚙️ আরও":
        await update.message.reply_text("⚙️ অতিরিক্ত অপশনসমূহ:", reply_markup=get_more_keyboard())

    elif text == "🔙 ব্যাক":
        await update.message.reply_text("🏠 প্রধান মেনু:", reply_markup=get_user_keyboard())

    elif text == "👤 প্রোফাইল":
        profile_text = (
            f"👤 **ইউজার প্রোফাইল**\n───────────────────\n"
            f"🆔 আইডি: `{str_id}`\n"
            f"💰 কয়েন ব্যালেন্স: {u_data['credit']}\n"
            f"📁 প্রজেক্ট সংখ্যা: {len(u_data['projects'])}\n"
            f"👥 মোট রেফার: {u_data['ref_count']}\n"
            f"🎁 রেফার আয়: {u_data['ref_credit']} কয়েন"
        )
        await update.message.reply_text(profile_text)

    elif text == "🎁 দৈনিক বোনাস":
        today = datetime.now().strftime("%Y-%m-%d")
        if u_data.get("last_daily_bonus") == today:
            await update.message.reply_text("⚠️ **আপনি আজকের দৈনিক বোনাস ইতোমধ্যেই ক্লেইম করেছেন!**")
        else:
            u_data["credit"] += 25
            u_data["last_daily_bonus"] = today
            save_data(db)
            await update.message.reply_text(f"🎉 **দৈনিক বোনাস সফল!**\n\nআপনি ২৫ কয়েন ফ্রি পেয়েছেন।")

    elif text in ["💰 রিচার্জ করুন", "🌟 পরিকল্পনা এবং ভারসাম্য"]:
        clean_admin = ADMIN_USERNAME.replace("@", "")
        inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton("💬 কয়েন কিনতে অ্যাডমিনকে মেসেজ দিন", url=f"https://t.me/{clean_admin}")]])
        await update.message.reply_text(
            f"💎 **আপনার ব্যালেন্স:** {u_data['credit']} কয়েন\n\n"
            f"💳 কয়েন রিচার্জ করতে নিচের বাটনে চাপ দিয়ে যোগাযোগ করুন:",
            reply_markup=inline_kb
        )

    elif text == "🔗 রেফারেল লিংক":
        ref_link = f"https://t.me/{BOT_USERNAME}?start={str_id}"
        await update.message.reply_text(f"🔗 **আপনার রেফারেল লিংক:**\n{ref_link}\n\nপ্রতি সফল রেফারে পাবেন ১০০ কয়েন ফ্রি!")

    elif text == "🆘 সহায়তা":
        clean_admin = ADMIN_USERNAME.replace("@", "")
        inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton("💬 অ্যাডমিনকে মেসেজ দিন", url=f"https://t.me/{clean_admin}")]])
        await update.message.reply_text("🆘 যেকোনো সহায়তার জন্য যোগাযোগ করুন:", reply_markup=inline_kb)

    elif text == "📁 আমার প্রকল্প":
        projects = u_data.get('projects', [])
        if projects:
            p_text = "📁 **আপনার সেভ করা প্রজেক্টসমূহ:**\n───────────────────\n"
            for idx, p in enumerate(projects, 1):
                p_text += f"{idx}. {p.get('channel_name', 'চ্যানেল')}\nরিঅ্যাকশন সীমা: {p['count']}\n\n"
            await update.message.reply_text(p_text)
        else:
            await update.message.reply_text("❌ আপনার কোনো প্রজেক্ট নেই।")

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
            MessageHandler(filters.Regex("^➕ অটো রিয়্যাকশন প্রজেক্ট যোগ করুন$"), start_project),
            MessageHandler(filters.Regex("^💳 ক্রেডিট কন্ট্রোল$"), start_add_credit),
            MessageHandler(filters.Regex("^🚫 ইউজার ব্লক/রিমুভ$"), start_block_user),
            MessageHandler(filters.Regex("^📢 অল ইউজার ব্রডকাস্ট$"), start_broadcast),
        ],
        states={
            STEP_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_channel)],
            STEP_EMOJI: [CallbackQueryHandler(emoji_callback, pattern="^(em_|em_done)")],
            STEP_DISTRIBUTION: [CallbackQueryHandler(distribution_callback, pattern="^(dist_)")],
            STEP_SPEED: [CallbackQueryHandler(speed_callback, pattern="^(spd_)")],
            STEP_COUNT: [CallbackQueryHandler(count_callback, pattern="^cnt_")],
            STEP_REVIEW: [
                CallbackQueryHandler(finalize_project, pattern="^create_final$"),
                CallbackQueryHandler(cancel_flow, pattern="^cancel_flow$")
            ],
            STEP_ADMIN_ADD_CREDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_credit)],
            STEP_ADMIN_BLOCK_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_block)],
            STEP_ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_broadcast)]
        },
        fallbacks=[CommandHandler('start', start), MessageHandler(filters.Regex("^(❌ বাতিল করুন|বাতিল করুন)$"), cancel_flow)]
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('admin', admin_panel_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu))
    
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL, auto_react_channel_post))

    logger.info("🤖 SMM Reaction Bot Engine Active...")
    
    app.run_polling(allowed_updates=["message", "edited_message", "channel_post", "edited_channel_post", "callback_query"])
