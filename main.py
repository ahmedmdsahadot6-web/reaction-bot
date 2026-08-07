import logging
import random
import os
import json
import re
from datetime import datetime
from threading import Thread
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, ReactionTypeEmoji
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# 🌐 Render Web Server Keep-Alive
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

# 💾 ডাটাবেজ ফাইল
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

# Conversational States
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
            "projects": [],
            "last_daily_bonus": None
        }
        save_data(db)
    return db["users"][str_id]

# 📱 কিবোর্ডসমূহ
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

# 🚀 /start Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    str_id = str(user.id)
    
    if str_id in db["blocked"]:
        await update.message.reply_text("🚫 আপনাকে এই বট থেকে ব্লক করা হয়েছে।")
        return

    if context.args and len(context.args) > 0:
        referrer_id = context.args[0]
        if referrer_id != str_id and referrer_id in db["users"] and str_id not in db["users"]:
            db["users"][referrer_id]["ref_count"] += 1
            db["users"][referrer_id]["credit"] += 20
            db["users"][referrer_id]["ref_credit"] += 20
            save_data(db)

    get_user_data(user.id)
    await update.message.reply_text(
        f"👋 স্বাগতম {user.first_name}!\n\nঅটো রিয়্যাকশন প্রজেক্ট তৈরি করতে নিচের '➕ অটো রিয়্যাকশন প্রজেক্ট যোগ করুন' বাটন চাপুন:",
        reply_markup=get_user_keyboard()
    )

# 👑 Admin Panel Access
async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ আপনি অ্যাডমিন নন!")
        return

    text = (
        f"👑 ADMIN CONTROL PANEL\n"
        f"═══════════════════════\n\n"
        f"👥 মোট ইউজার: {len(db['users'])}\n"
        f"🚫 ব্লককৃত ইউজার: {len(db['blocked'])}\n"
        f"═══════════════════════"
    )
    await update.message.reply_text(text, reply_markup=get_admin_keyboard())

# --- Step 0: Channel Setup ---
async def start_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u_data = get_user_data(user_id)
    
    if u_data['credit'] <= 0:
        clean_admin = ADMIN_USERNAME.replace("@", "")
        inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton("💬 অ্যাডমিনকে মেসেজ দিন", url=f"https://t.me/{clean_admin}")]])
        await update.message.reply_text("⚠️ আপনার পর্যাপ্ত ক্রেডিট নেই!\nনতুন প্রজেক্ট তৈরি করতে রিচার্জ করুন।", reply_markup=inline_kb)
        return ConversationHandler.END

    context.user_data['draft_project'] = {
        "channel_name": None,
        "channel_id": None,
        "raw_input": None,
        "emojis": ["❤️", "👍", "🔥", "💯"],
        "count": 20,
        "dist": "এলোমেলো",
        "speed": "তাৎক্ষণিক",
        "views": 0
    }
    
    text = (
        f"🛰 ধাপ 0 • চ্যানেল সেটআপ\n"
        f"───────────────────\n\n"
        f"১) @{BOT_USERNAME} কে আপনার চ্যানেলে Admin হিসেবে যোগ করুন।\n\n"
        f"২) এরপর চ্যানেলের যেকোনো ১টি পোস্ট ফরওয়ার্ড করে এখানে পাঠান\n"
        f"অথবা চ্যানেলের ইউজারনেম/লিংক লিখে পাঠান (যেমন: @Sahadot_Reaction_Vip বা https://t.me/...):"
    )
    await update.message.reply_text(text, reply_markup=cancel_keyboard())
    return STEP_CHANNEL

async def save_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    txt = (msg.text or "").strip()

    if txt in ["❌ বাতিল করুন", "বাতিল করুন", "🔙 ব্যাক"]:
        context.user_data.pop('draft_project', None)
        await msg.reply_text("প্রক্রিয়া বাতিল করা হয়েছে।", reply_markup=get_user_keyboard())
        return ConversationHandler.END

    channel_title = "Telegram Channel"
    channel_id = txt

    if msg.forward_from_chat:
        channel_title = msg.forward_from_chat.title or "Telegram Channel"
        channel_id = str(msg.forward_from_chat.id)
    elif hasattr(msg, 'forward_origin') and msg.forward_origin and hasattr(msg.forward_origin, 'chat'):
        channel_title = msg.forward_origin.chat.title or "Telegram Channel"
        channel_id = str(msg.forward_origin.chat.id)
    elif txt:
        if "t.me/" in txt:
            channel_title = txt.split("/")[-1]
        else:
            channel_title = txt

    context.user_data['draft_project']['channel_name'] = channel_title
    context.user_data['draft_project']['channel_id'] = channel_id
    context.user_data['draft_project']['raw_input'] = txt

    confirm_text = (
        f"✅ চ্যানেল ইনপুট গ্রহণ করা হয়েছে!\n\n"
        f"📺 চ্যানেল/লিঙ্ক: {channel_title}\n"
        f"📌 শেষ ধাপে 'প্রকল্প তৈরি করুন' চাপলে ডাটাবেজে যুক্ত হবে।"
    )
    await msg.reply_text(confirm_text)

    return await render_emoji_menu(update, context)

# --- Step 1: Emoji Choice ---
async def render_emoji_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    draft = context.user_data.get('draft_project', {})
    selected = " ".join(draft.get('emojis', [])) if draft.get('emojis') else "(কোনোটিই নয়)"
    
    text = (
        f"📝 ধাপ 1 • ইমোজি নির্বাচন করুন\n"
        f"───────────────────\n\n"
        f"📺 চ্যানেল: {draft.get('channel_name', 'অজ্ঞাত')}\n"
        f"👉 বর্তমান নির্বাচিত ইমোজি: {selected}\n\n"
        f"ইমোজি বেছে নিয়ে '✅ সম্পন্ন' চাপুন:"
    )
    
    keyboard = [
        [InlineKeyboardButton("✓ সব (4)", callback_data="em_all"), InlineKeyboardButton("কাস্টম", callback_data="em_custom")],
        [InlineKeyboardButton("❤️", callback_data="em_❤️"), InlineKeyboardButton("👍", callback_data="em_👍"), InlineKeyboardButton("🔥", callback_data="em_🔥")],
        [InlineKeyboardButton("🙏", callback_data="em_🙏"), InlineKeyboardButton("🎉", callback_data="em_🎉"), InlineKeyboardButton("🏆", callback_data="em_🏆")],
        [InlineKeyboardButton("😍", callback_data="em_😍"), InlineKeyboardButton("💯", callback_data="em_💯"), InlineKeyboardButton("😭", callback_data="em_😭"), InlineKeyboardButton("⚡", callback_data="em_⚡")],
        [InlineKeyboardButton("✅ সম্পন্ন", callback_data="em_done")]
    ]
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await context.bot.send_message(chat_id=user_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    return STEP_EMOJI

async def emoji_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get('draft_project', {})
    
    data = query.data
    if data == "em_done":
        if not draft.get('emojis'): draft['emojis'] = ["👍"]
        return await render_count_menu(update, context)
    elif data == "em_all":
        draft['emojis'] = ["❤️", "👍", "🔥", "💯"]
    elif data != "em_custom":
        emoji = data.split("_")[1]
        if emoji in draft['emojis']: draft['emojis'].remove(emoji)
        else: draft['emojis'].append(emoji)
    
    return await render_emoji_menu(update, context)

# --- Step 2: Reaction Count ---
async def render_count_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get('draft_project', {})
    text = (
        f"📊 ধাপ 2 • মোট প্রতিক্রিয়া\n"
        f"───────────────────\n\n"
        f"👉 বর্তমান নির্বাচিত সংখ্যা: {draft.get('count', 20)} রিয়্যাকশন"
    )
    keyboard = [
        [InlineKeyboardButton("10", callback_data="cnt_10"), InlineKeyboardButton("20", callback_data="cnt_20"), InlineKeyboardButton("30", callback_data="cnt_30")],
        [InlineKeyboardButton("🔒 50", callback_data="locked"), InlineKeyboardButton("🔒 100", callback_data="locked")],
        [InlineKeyboardButton("↩ ব্যাক", callback_data="back_emoji"), InlineKeyboardButton("চালিয়ে যান ✅", callback_data="cnt_done")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return STEP_COUNT

async def count_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get('draft_project', {})
    
    if query.data == "cnt_done": return await render_distribution_menu(update, context)
    if query.data == "back_emoji": return await render_emoji_menu(update, context)
    if query.data == "locked":
        await query.answer("এটি প্রিমিয়াম ফিচার!", show_alert=True)
        return STEP_COUNT
    
    draft['count'] = int(query.data.split("_")[1])
    return await render_count_menu(update, context)

# --- Step 3: Distribution ---
async def render_distribution_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get('draft_project', {})
    text = (
        f"⚙️ ধাপ 3 • বিতরণের ধরন\n"
        f"───────────────────\n\n"
        f"👉 বর্তমান পছন্দ: {draft.get('dist', 'এলোমেলো')}\n\n"
        f"🎲 এলোমেলো - প্রতিটি ইমোজিতে র‍্যান্ডম রিয়্যাকশন\n"
        f"⚖️ সকল সমান - ইমোজিগুলোতে সমান সংখ্যার বিতরণ"
    )
    keyboard = [
        [InlineKeyboardButton("🎲 এলোমেলো", callback_data="dist_এলোমেলো")],
        [InlineKeyboardButton("⚖️ সব সমানভাবে", callback_data="dist_সমান")],
        [InlineKeyboardButton("↩ ব্যাক", callback_data="back_count"), InlineKeyboardButton("চালিয়ে যান ✅", callback_data="dist_done")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return STEP_DISTRIBUTION

async def distribution_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get('draft_project', {})
    
    if query.data == "dist_done": return await render_speed_menu(update, context)
    if query.data == "back_count": return await render_count_menu(update, context)

    draft['dist'] = query.data.split("_")[1]
    return await render_distribution_menu(update, context)

# --- Step 4: Speed ---
async def render_speed_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get('draft_project', {})
    text = (
        f"⚡ ধাপ 4 • গতি নির্বাচন\n"
        f"───────────────────\n\n"
        f"👉 বর্তমান নির্বাচিত গতি: ⚡ {draft.get('speed', 'তাৎক্ষণিক')}"
    )
    keyboard = [
        [InlineKeyboardButton("তাৎক্ষণিক", callback_data="spd_তাৎক্ষণিক"), InlineKeyboardButton("ধীর", callback_data="spd_ধীর")],
        [InlineKeyboardButton("↩ ব্যাক", callback_data="back_dist"), InlineKeyboardButton("চালিয়ে যান ✅", callback_data="spd_done")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return STEP_SPEED

async def speed_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get('draft_project', {})
    
    if query.data == "spd_done": return await render_views_menu(update, context)
    if query.data == "back_dist": return await render_distribution_menu(update, context)

    draft['speed'] = query.data.split("_")[1]
    return await render_speed_menu(update, context)

# --- Step 5: Views ---
async def render_views_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get('draft_project', {})
    text = (
        f"👁 ধাপ 5 • ভিউ কনফিগারেশন\n"
        f"───────────────────\n\n"
        f"👉 বর্তমান নির্বাচিত ভিউ: {draft.get('views', 0)} ভিউ"
    )
    keyboard = [
        [InlineKeyboardButton("0 ভিউ", callback_data="vw_0"), InlineKeyboardButton("10 ভিউ", callback_data="vw_10"), InlineKeyboardButton("30 ভিউ", callback_data="vw_30")],
        [InlineKeyboardButton("↩ ব্যাক", callback_data="back_speed"), InlineKeyboardButton("চালিয়ে যান ✅", callback_data="vw_done")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return STEP_VIEWS

async def views_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get('draft_project', {})
    
    if query.data == "vw_done": return await render_review_menu(update, context)
    if query.data == "back_speed": return await render_speed_menu(update, context)

    draft['views'] = int(query.data.split("_")[1])
    return await render_views_menu(update, context)

# --- Final Review Menu ---
async def render_review_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get('draft_project', {})
    emojis = " ".join(draft.get('emojis', []))
    
    text = (
        f"✨ FINAL REVIEW (চূড়ান্ত পর্যালোচনা) ✨\n"
        f"───────────────────\n\n"
        f"📺 চ্যানেল: {draft.get('channel_name')}\n\n"
        f"┌────────────────────\n"
        f"│ 😊 ইমোজি: {emojis}\n"
        f"│ 🚀 প্রতিক্রিয়া: {draft.get('count')}\n"
        f"│ 👁 ভিউ: {draft.get('views')}\n"
        f"│ ⚡ গতি: {draft.get('speed')}\n"
        f"│ ⚙️ বিতরণ: {draft.get('dist')}\n"
        f"└────────────────────\n\n"
        f"⚠️ '✅ প্রকল্প তৈরি করুন' বাটনে চাপ দিলেই ডাটাবেজে সেভ হবে ও চ্যানেলের সাথে কানেক্ট হবে।"
    )
    keyboard = [
        [InlineKeyboardButton("✅ প্রকল্প তৈরি করুন", callback_data="create_final")],
        [InlineKeyboardButton("❌ বাতিল করুন", callback_data="cancel_flow")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return STEP_REVIEW

# 💾 Final Save & Database Connection
async def finalize_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    u_data = get_user_data(user_id)
    
    draft = context.user_data.get('draft_project')
    if not draft:
        await query.message.reply_text("❌ কোনো তথ্য পাওয়া যায়নি! নতুন করে চেষ্টা করুন।", reply_markup=get_user_keyboard())
        return ConversationHandler.END

    raw_inp = draft.get('raw_input') or draft.get('channel_id')
    final_channel_id = draft.get('channel_id')
    final_channel_name = draft.get('channel_name')

    try:
        chat_info = await context.bot.get_chat(raw_inp)
        final_channel_id = str(chat_info.id)
        final_channel_name = chat_info.title or final_channel_name
    except Exception:
        pass

    draft['channel_id'] = final_channel_id
    draft['channel_name'] = final_channel_name

    u_data['projects'] = [p for p in u_data.get('projects', []) if str(p.get('channel_id')) != str(final_channel_id)]
    u_data['projects'].append(draft)
    save_data(db)

    context.user_data.pop('draft_project', None)

    await query.message.reply_text(
        f"🎉 প্রকল্প সফলভাবে তৈরি ও ডাটাবেজে সেভ হয়েছে!\n\n"
        f"📁 চ্যানেল: {final_channel_name}\n"
        f"🆔 আইডি: {final_channel_id}\n"
        f"😊 ইমোজি: {' '.join(draft['emojis'])}\n"
        f"🚀 প্রতিক্রিয়া: {draft['count']}\n\n"
        f"এখন চ্যানেলে নতুন পোস্ট করার সাথে সাথে অটো রিয়্যাকশন চলে যাবে।",
        reply_markup=get_user_keyboard()
    )
    return ConversationHandler.END

async def cancel_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('draft_project', None)
    if update.callback_query:
        await update.callback_query.message.reply_text("প্রক্রিয়া বাতিল করা হয়েছে।", reply_markup=get_user_keyboard())
    else:
        await update.message.reply_text("প্রক্রিয়া বাতিল করা হয়েছে।", reply_markup=get_user_keyboard())
    return ConversationHandler.END

# 👑 Admin Actions
async def start_add_credit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return ConversationHandler.END
    await update.message.reply_text("➕ ক্রেডিট দিতে লিখে পাঠান: User_ID Amount\nযেমন: 7973059882 100")
    return STEP_ADMIN_ADD_CREDIT

async def process_admin_credit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        parts = update.message.text.split()
        target_id, amount = parts[0], int(parts[1])
        if target_id in db['users']:
            db['users'][target_id]['credit'] += amount
            save_data(db)
            await update.message.reply_text(f"✅ ইউজার {target_id} এর বর্তমান ক্রেডিট: {db['users'][target_id]['credit']}", reply_markup=get_admin_keyboard())
        else:
            await update.message.reply_text("❌ আইডি পাওয়া যায়নি!", reply_markup=get_admin_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ ভুল ইনপুট! Error: {e}", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

async def start_block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return ConversationHandler.END
    await update.message.reply_text("🚫 ব্লক করতে আইডি লিখে পাঠান:")
    return STEP_ADMIN_BLOCK_USER

async def process_admin_block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_id = update.message.text.strip()
    if target_id not in db['blocked']:
        db['blocked'].append(target_id)
        save_data(db)
        await update.message.reply_text(f"🚫 ইউজার {target_id} কে ব্লক করা হয়েছে।", reply_markup=get_admin_keyboard())
    else:
        await update.message.reply_text("⚠️ ইউজার আগের থেকেই ব্লকড!", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return ConversationHandler.END
    await update.message.reply_text("📢 ব্রডকাস্ট করার মেসেজটি পাঠোন:")
    return STEP_ADMIN_BROADCAST

async def process_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_text = update.message.text
    count = 0
    for uid in db['users']:
        try:
            await context.bot.send_message(chat_id=int(uid), text=f"📢 বিজ্ঞপ্তি:\n\n{msg_text}")
            count += 1
        except Exception:
            pass
    await update.message.reply_text(f"🎉 মোট {count} জন ইউজারের কাছে মেসেজ চলে গেছে!", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

# ⚡ Auto Reaction Trigger on Channel Post
async def auto_react_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.channel_post
        if not message: return
        
        channel_id = str(message.chat_id)

        for uid, uinfo in db["users"].items():
            for proj in uinfo.get("projects", []):
                if str(proj.get("channel_id")) == channel_id:
                    if uinfo.get("credit", 0) <= 0:
                        try:
                            clean_admin = ADMIN_USERNAME.replace("@", "")
                            inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton("💬 রিচার্জ করুন", url=f"https://t.me/{clean_admin}")]])
                            await context.bot.send_message(
                                chat_id=int(uid),
                                text=f"⚠️ ক্রেডিট শেষ!\nআপনার {proj['channel_name']} চ্যানেলে রিয়্যাকশন পাঠানোর পর্যাপ্ত ক্রেডিট নেই।",
                                reply_markup=inline_kb
                            )
                        except Exception:
                            pass
                        return

                    target_emojis = proj.get("emojis", ["👍"])
                    chosen_emoji = random.choice(target_emojis) if target_emojis else "👍"
                    
                    await context.bot.set_message_reaction(
                        chat_id=message.chat_id,
                        message_id=message.message_id,
                        reaction=[ReactionTypeEmoji(emoji=chosen_emoji)]
                    )

                    uinfo["credit"] -= 1
                    save_data(db)
                    return
    except Exception as e:
        logging.error(f"Auto Reaction Error: {e}")

# 📌 Main Menu Handler
async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    str_id = str(user_id)
    text = update.message.text
    u_data = get_user_data(str_id)

    if text and text.strip().lower() in ["অ্যাডমিন", "admin"]:
        return await admin_panel_command(update, context)

    if user_id in ADMIN_IDS:
        if text == "📊 বট স্ট্যাটাস":
            return await admin_panel_command(update, context)
        elif text == "📋 ইউজার লিস্ট":
            u_list = "📋 ইউজার তালিকা:\n───────────────────\n"
            for uid, uinfo in list(db['users'].items())[:15]:
                u_list += f"🆔 {uid} | 💎 ক্রেডিট: {uinfo.get('credit', 0)}\n"
            return await update.message.reply_text(u_list, reply_markup=get_admin_keyboard())
        elif text == "🏠 প্রধান মেনু":
            return await update.message.reply_text("🏠 প্রধান মেনু:", reply_markup=get_user_keyboard())

    if text == "⚙️ আরও":
        await update.message.reply_text("⚙️ অতিরিক্ত অপশনসমূহ:\nনিচের অপশনগুলো থেকে বেছে নিন:", reply_markup=get_more_keyboard())

    elif text == "🔙 ব্যাক":
        await update.message.reply_text("🏠 প্রধান মেনু:", reply_markup=get_user_keyboard())

    elif text == "👤 প্রোফাইল":
        profile_text = (
            f"👤 ইউজার প্রোফাইল\n───────────────────\n"
            f"🆔 আইডি: {str_id}\n"
            f"💎 ক্রেডিট: {u_data['credit']}\n"
            f"📁 প্রকল্প সংখ্যা: {len(u_data['projects'])}\n"
            f"👥 মোট রেফার: {u_data['ref_count']}\n"
            f"💰 রেফার আয়: {u_data['ref_credit']} ক্রেডিট"
        )
        await update.message.reply_text(profile_text)

    elif text == "🎁 দৈনিক বোনাস":
        today = datetime.now().strftime("%Y-%m-%d")
        if u_data.get("last_daily_bonus") == today:
            await update.message.reply_text("⚠️ আপনি আজকের দৈনিক বোনাস ইতোমধ্যেই গ্রহণ করেছেন!")
        else:
            u_data["credit"] += 10
            u_data["last_daily_bonus"] = today
            save_data(db)
            await update.message.reply_text(f"🎉 দৈনিক বোনাস সফল!\n\nআপনি ১০ ফ্রি ক্রেডিট পেয়েছেন।\nবর্তমান ক্রেডিট: {u_data['credit']}")

    elif text == "🔗 রেফারেল লিংক":
        ref_link = f"https://t.me/{BOT_USERNAME}?start={str_id}"
        refer_text = (
            f"🔗 রেফারেল প্রোগ্রাম\n───────────────────\n"
            f"আপনার বন্ধুদের রেফারেল লিংক ব্যবহার করে যুক্ত হতে বলুন এবং প্রতি সফল রেফারে ২০ ফ্রি ক্রেডিট পান!\n\n"
            f"📌 আপনার লিঙ্ক:\n{ref_link}"
        )
        await update.message.reply_text(refer_text)

    elif text == "🆘 সহায়তা":
        clean_admin = ADMIN_USERNAME.replace("@", "")
        inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton("💬 অ্যাডমিনকে মেসেজ দিন", url=f"https://t.me/{clean_admin}")]])
        await update.message.reply_text(f"🆘 সহায়তা ও সাপোর্ট\n───────────────────\nআপনার কোনো প্রশ্ন থাকলে সরাসরি আমাদের অ্যাডমিনের সাথে যোগাযোগ করুন।", reply_markup=inline_kb)

    elif text == "🌟 পরিকল্পনা এবং ভারসাম্য":
        p_count = len(u_data.get('projects', []))
        await update.message.reply_text(f"💎 বর্তমান ক্রেডিট: {u_data['credit']}\n📁 সক্রিয় প্রকল্প: {p_count}")
    
    elif text == "📁 আমার প্রকল্প":
        projects = u_data.get('projects', [])
        if projects:
            p_text = "📁 আপনার সেভ করা প্রকল্পসমূহ:\n───────────────────\n"
            for idx, p in enumerate(projects, 1):
                p_text += f"{idx}. {p['channel_name']}\nইমোজি: {' '.join(p['emojis'])}\nরিঅ্যাকশন: {p['count']}\n\n"
            await update.message.reply_text(p_text)
        else:
            await update.message.reply_text("❌ আপনার কোনো সেভ করা প্রকল্প নেই।")

    elif text == "💰 রিচার্জ করুন":
        clean_admin = ADMIN_USERNAME.replace("@", "")
        inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton("💬 অ্যাডমিনকে মেসেজ দিন", url=f"https://t.me/{clean_admin}")]])
        await update.message.reply_text(f"💳 রিচার্জ করতে অ্যাডমিনের সাথে যোগাযোগ করুন:\n\n🆔 আপনার আইডি: {str_id}", reply_markup=inline_kb)

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
            STEP_EMOJI: [CallbackQueryHandler(emoji_callback, pattern="^(em_|em_done)")],
            STEP_COUNT: [CallbackQueryHandler(count_callback, pattern="^(cnt_|back_emoji|locked)")],
            STEP_DISTRIBUTION: [CallbackQueryHandler(distribution_callback, pattern="^(dist_|back_count)")],
            STEP_SPEED: [CallbackQueryHandler(speed_callback, pattern="^(spd_|back_dist)")],
            STEP_VIEWS: [CallbackQueryHandler(views_callback, pattern="^(vw_|back_speed)")],
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

    print("🤖 Bot Active...")
    app.run_polling(drop_pending_updates=True)
