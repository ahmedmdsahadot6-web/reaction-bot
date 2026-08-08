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

# 🌐 Render Keep-Alive Web Server
web_app = Flask('')

@web_app.route('/')
def home():
    return "SMM Reaction Bot Engine: ACTIVE 24/7"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# 🔑 বোট ও SMM কনফিগারেশন
BOT_TOKEN = "8320025447:AAFWnP_asWXs6WXS-h_gPAy6Baikd6-4jMc"
BOT_USERNAME = "TGSUPER_SERVICE_BOT"
ADMIN_IDS = [8454401183, 8457454660]
ADMIN_USERNAME = "@SOYABUR_AS_LEADER"

# 🌐 SMM Panel API settings
SMM_API_URL = "https://1xpanel.com/api/v2"
SMM_API_KEY = "0b2fbfd793c2cc3cec163c1faaaa318c"
REACTION_SERVICE_ID = "1936"

DB_FILE = "database.json"
logging.basicConfig(level=logging.INFO)

# 💾 ডাটাবেজ ফাংশনসমূহ
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
(STEP_CHANNEL, STEP_EMOJI, STEP_COUNT, STEP_REVIEW, 
 STEP_ADMIN_ADD_CREDIT, STEP_ADMIN_BLOCK_USER, STEP_ADMIN_BROADCAST) = range(7)

def get_user_data(user_id):
    str_id = str(user_id)
    if str_id not in db["users"]:
        db["users"][str_id] = {
            "credit": 150,
            "ref_count": 0,
            "ref_credit": 0,
            "projects": [],
            "last_daily_bonus": None
        }
        save_data(db)
    return db["users"][str_id]

# 📱 কিবোর্ড মেনু
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
        f"এখান থেকে আপনি আপনার চ্যানেলের নতুন পোস্টে ইনস্ট্যান্ট রিয়্যাকশন নিতে পারবেন।\n\n"
        f"নিচের মেনু থেকে প্রজেক্ট যোগ করুন:",
        reply_markup=get_user_keyboard()
    )

# 👑 অ্যাডমিন প্যানেল কমান্ড
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
        f"🌐 এপিআই স্ট্যাটাস: SMM Connected\n"
        f"───────────────────"
    )
    await update.message.reply_text(text, reply_markup=get_admin_keyboard())

# --- ➕ প্রজেক্ট তৈরির ধাপসমূহ ---
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
        "emojis": ["❤️", "👍", "🔥"],
        "count": 10
    }

    text = (
        f"🛰 **ধাপ ১ • চ্যানেল সেটআপ**\n"
        f"───────────────────\n\n"
        f"১) @{BOT_USERNAME} কে আপনার চ্যানেলে Admin বানান।\n\n"
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
        await msg.reply_text("❌ লিঙ্কটি সঠিক নয়! লিঙ্কের শুরুতে 'https://t.me/' থাকতে হবে। আবার চেষ্টা করুন:")
        return STEP_CHANNEL

    match = re.search(r'https://t\.me/[^\s]+', txt)
    if not match:
        await msg.reply_text("❌ সঠিক লিঙ্ক পাওয়া যায়নি! আবার লিঙ্ক পাঠান:")
        return STEP_CHANNEL

    extracted_url = match.group(0)
    context.user_data['draft_project']['target_url'] = extracted_url

    return await render_emoji_menu(update, context)

async def render_emoji_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get('draft_project', {})
    em_list = draft.get('emojis', ["❤️", "👍", "🔥"])
    selected = " ".join(em_list) if em_list else "(কোনোটি নয়)"

    text = (
        f"📝 **ধাপ ২ • ইমোজি নির্বাচন**\n"
        f"───────────────────\n\n"
        f"👉 বর্তমান সিলেক্টেড ইমোজি: {selected}\n\n"
        f"নিচ থেকে ইমোজি নির্বাচন করে '✅ সম্পন্ন' বাটনে চাপুন:"
    )

    keyboard = [
        [InlineKeyboardButton("❤️", callback_data="em_❤️"), InlineKeyboardButton("👍", callback_data="em_👍"), InlineKeyboardButton("🔥", callback_data="em_🔥")],
        [InlineKeyboardButton("🎉", callback_data="em_🎉"), InlineKeyboardButton("💯", callback_data="em_💯"), InlineKeyboardButton("😍", callback_data="em_😍")],
        [InlineKeyboardButton("✅ সম্পন্ন", callback_data="em_done")]
    ]

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await context.bot.send_message(chat_id=update.effective_user.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    return STEP_EMOJI

async def emoji_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get('draft_project', {})
    if 'emojis' not in draft: draft['emojis'] = ["👍"]

    data = query.data
    if data == "em_done":
        return await render_count_menu(update, context)
    else:
        emoji = data.split("_")[1]
        if emoji in draft['emojis']: draft['emojis'].remove(emoji)
        else: draft['emojis'].append(emoji)

    return await render_emoji_menu(update, context)

async def render_count_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get('draft_project', {})
    text = (
        f"📊 **ধাপ ৩ • রিয়্যাকশন সংখ্যা**\n"
        f"───────────────────\n\n"
        f"👉 বর্তমান রিয়্যাকশন সংখ্যা: {draft.get('count', 10)}"
    )
    keyboard = [
        [InlineKeyboardButton("10", callback_data="cnt_10"), InlineKeyboardButton("20", callback_data="cnt_20"), InlineKeyboardButton("30", callback_data="cnt_30")],
        [InlineKeyboardButton("50", callback_data="cnt_50"), InlineKeyboardButton("100", callback_data="cnt_100"), InlineKeyboardButton("200", callback_data="cnt_200")],
        [InlineKeyboardButton("500", callback_data="cnt_500"), InlineKeyboardButton("1000", callback_data="cnt_1000"), InlineKeyboardButton("2000", callback_data="cnt_2000")],
        [InlineKeyboardButton("5000", callback_data="cnt_5000")],
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
    emojis = " ".join(draft.get('emojis', []))

    text = (
        f"✨ **চূড়ান্ত তথ্য যাচাই** ✨\n"
        f"───────────────────\n\n"
        f"🔗 চ্যানেল লিঙ্ক: {draft.get('target_url')}\n"
        f"😊 নির্বাচিত ইমোজি: {emojis}\n"
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
        await query.message.reply_text("❌ সমস্যা হয়েছে, আবার চেষ্টা করুন!", reply_markup=get_user_keyboard())
        return ConversationHandler.END

    target_url = draft.get('target_url')
    clean_handle = target_url.strip().split("/")[-1]
    if not clean_handle.startswith("@") and not clean_handle.lstrip('-').isdigit():
        clean_handle = "@" + clean_handle

    try:
        chat_info = await context.bot.get_chat(clean_handle)
        channel_id = str(chat_info.id)
        channel_title = chat_info.title or clean_handle
    except Exception as e:
        await query.message.reply_text(f"❌ চ্যানেলটি পাওয়া যায়নি! নিশ্চিত করুন বট চ্যানেলে Admin আছে। Error: {e}", reply_markup=get_user_keyboard())
        context.user_data.pop('draft_project', None)
        return ConversationHandler.END

    u_data = get_user_data(user_id)
    draft['channel_id'] = channel_id
    draft['channel_name'] = channel_title

    u_data['projects'].append(draft)
    save_data(db)

    context.user_data.pop('draft_project', None)

    await query.message.reply_text(
        f"🎉 **প্রকল্প সফলভাবে তৈরি হয়েছে!**\n\n"
        f"📁 চ্যানেল: {channel_title}\n"
        f"🚀 রিয়্যাকশন: {draft['count']} টি\n\n"
        f"এখন চ্যানেলে নতুন পোস্ট করার সাথে সাথেই অটো রিয়্যাকশন চলে যাবে!",
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

# 🌐 SMM API Order Function
def send_smm_reaction_order(post_link, count):
    try:
        payload = {
            'key': SMM_API_KEY,
            'action': 'add',
            'service': REACTION_SERVICE_ID,
            'link': post_link,
            'quantity': count
        }
        response = requests.post(SMM_API_URL, data=payload, timeout=10)
        res_json = response.json()
        
        if "order" in res_json:
            return True, res_json["order"]
        else:
            logging.error(f"SMM API Error Response: {res_json}")
            return False, res_json.get("error", "Unknown API error")
    except Exception as e:
        logging.error(f"SMM API Request Failed: {e}")
        return False, str(e)

# 📢 অটো পোস্ট ট্রিগার (সম্পূর্ণ ফিক্সড পোস্ট হ্যান্ডলার)
async def auto_react_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # চ্যানেল পোস্ট ক্যাচ করা
        message = update.channel_post or update.effective_message
        if not message or not message.chat:
            return

        channel_id = str(message.chat.id)
        chat = message.chat
        
        # পোস্ট লিংক তৈরি
        if chat.username:
            post_link = f"https://t.me/{chat.username}/{message.message_id}"
        else:
            # প্রাইভেট চ্যানেলের ক্ষেত্রে লিংক গঠন
            clean_cid = str(chat.id).replace("-100", "")
            post_link = f"https://t.me/c/{clean_cid}/{message.message_id}"

        clean_admin = ADMIN_USERNAME.replace("@", "")
        admin_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("💬 অ্যাডমিনের সাথে যোগাযোগ করুন", url=f"https://t.me/{clean_admin}")]])

        # ডাটাবেজ ফিল্টারিং ও অর্ডার পাঠানো
        for uid, uinfo in db["users"].items():
            for proj in uinfo.get("projects", []):
                if str(proj.get("channel_id")) == channel_id:
                    
                    # শর্ত ১: কয়েন চেক
                    if uinfo.get("credit", 0) <= 0:
                        try:
                            await context.bot.send_message(
                                chat_id=int(uid),
                                text=f"⚠️ **আপনার ব্যালেন্স শেষ!**\n\n"
                                     f"আপনার `{proj.get('channel_name', 'চ্যানেলে')}` নতুন পোস্ট করা হলেও কয়েন না থাকায় রিয়্যাকশন পাঠানো যায়নি।\n"
                                     f"নতুন পোস্টে অটো রিয়্যাকশন পেতে রিচার্জ করুন।",
                                reply_markup=admin_keyboard
                            )
                        except Exception:
                            pass
                        return

                    target_count = proj.get("count", 10)

                    # API রিকোয়েস্ট পাঠানো
                    success, result = await asyncio.to_thread(send_smm_reaction_order, post_link, target_count)

                    if success:
                        uinfo["credit"] -= 10
                        if uinfo["credit"] < 0: uinfo["credit"] = 0
                        save_data(db)

                        # 🎉 নোটিফিকেশন মেসেজ
                        try:
                            await context.bot.send_message(
                                chat_id=int(uid),
                                text=f"🎉 **সফলভাবে রিয়্যাকশন পাঠানো হয়েছে!**\n\n"
                                     f"📢 **চ্যানেল:** {proj.get('channel_name')}\n"
                                     f"📌 **পোস্ট লিঙ্ক:** {post_link}\n"
                                     f"🚀 **রিয়্যাকশন সংখ্যা:** {target_count} টি\n"
                                     f"💰 **অবশিষ্ট ব্যালেন্স:** {uinfo['credit']} কয়েন"
                            )
                        except Exception:
                            pass
                    else:
                        try:
                            await context.bot.send_message(
                                chat_id=int(uid),
                                text=f"⚠️ **অ্যাডমিনের সাথে যোগাযোগ করুন!**\n\n"
                                     f"প্যানেলে সমস্যা থাকার কারণে পোস্টটিতে রিয়্যাকশন দেওয়া সম্ভব হয়নি।\n"
                                     f"Error: `{result}`",
                                reply_markup=admin_keyboard
                            )
                        except Exception:
                            pass
                    return
    except Exception as e:
        logging.error(f"Channel Trigger Error: {e}")

# 👑 অ্যাডমিন একশনস
async def start_add_credit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return ConversationHandler.END
    await update.message.reply_text("💳 কয়েন বাড়াতে/কমাতে লিখুন: `User_ID Amount`\nযেমন: `8454401183 500`", reply_markup=cancel_keyboard())
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
            await update.message.reply_text("❌ ইউজার আইডি পাওয়া যায়নি!", reply_markup=get_admin_keyboard())
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
        except Exception:
            pass
    await update.message.reply_text(f"🎉 মোট {count} জন ইউজারের কাছে মেসেজ পাঠানো হয়েছে!", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

# 📌 মেনু হ্যান্ডলার
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
                u_list += f"🆔 `{uid}` | 💎 কয়েন: {uinfo.get('credit', 0)}\n"
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
            f"💰 কয়েন ব্যালেন্স: {u_data['credit']}\n"
            f"📁 প্রজেক্ট সংখ্যা: {len(u_data['projects'])}\n"
            f"👥 মোট রেফার: {u_data['ref_count']}\n"
            f"🎁 রেফার আয়: {u_data['ref_credit']} কয়েন"
        )
        await update.message.reply_text(profile_text)

    elif text == "🎁 দৈনিক বোনাস":
        today = datetime.now().strftime("%Y-%m-%d")
        if u_data.get("last_daily_bonus") == today:
            await update.message.reply_text("⚠️ **আপনি আজকের দৈনিক বোনাস ইতোমধ্যেই ক্লেইম করেছেন!**\nআগামীকাল আবার চেষ্টা করুন।")
        else:
            u_data["credit"] += 25
            u_data["last_daily_bonus"] = today
            save_data(db)
            await update.message.reply_text(f"🎉 **দৈনিক বোনাস সফল!**\n\nআপনি ২৫ কয়েন ফ্রি পেয়েছেন।")

    elif text in ["💰 রিচার্জ করুন", "🌟 পরিকল্পনা এবং ভারসাম্য"]:
        clean_admin = ADMIN_USERNAME.replace("@", "")
        inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton("💬 কয়েন কিনতে অ্যাডমিনকে মেসেজ দিন", url=f"https://t.me/{clean_admin}")]])
        await update.message.reply_text(
            f"💎 **আপনার ব্যালেন্স:** {u_data['credit']} কয়েন\n\n"
            f"💳 কয়েন রিচার্জ করতে নিচের বাটনে চাপ দিয়ে অ্যাডমিনের সাথে যোগাযোগ করুন:",
            reply_markup=inline_kb
        )

    elif text == "🔗 রেফারেল লিংক":
        ref_link = f"https://t.me/{BOT_USERNAME}?start={str_id}"
        await update.message.reply_text(f"🔗 **আপনার রেফারেল লিংক:**\n{ref_link}\n\nপ্রতি সফল রেফারে পাবেন ১০০ কয়েন ফ্রি!")

    elif text == "🆘 সহায়তা":
        clean_admin = ADMIN_USERNAME.replace("@", "")
        inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton("💬 অ্যাডমিনকে মেসেজ দিন", url=f"https://t.me/{clean_admin}")]])
        await update.message.reply_text("🆘 যেকোনো সহায়তার জন্য যোগাযোগ করুন:", reply_markup=inline_kb)

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
    app = ApplicationBuilder().token(BOT_TOKEN).build()

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
    
    # চ্যানেল পোস্ট ডিটেক্টর হ্যান্ডলার (অল টাইপ মেসেজ ফিল্টার অন)
    app.add_handler(MessageHandler(filters.ALL, auto_react_channel_post))

    print("🤖 SMM Reaction Bot Operational...")
    app.run_polling(drop_pending_updates=True)
