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

# 🌐 Web Server for Render 24/7
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
BOT_TOKEN = "8895135409:AAHpo18y1o74_g1XBeTMO7CCpjj0NYfjWHA"
BOT_USERNAME = "Sahadot_reaction123_bot"
ADMIN_IDS = [7973059882]  # 👈 আপনার টেলিগ্রাম আসল আইডি সেট করা হয়েছে

# 💾 স্থায়ী ডাটাবেজ সিস্টেম (Json Storage)
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
            "channel_name": None,
            "channel_id": None,
            "temp_emojis": [],
            "selected_count": 20,
            "selected_dist": "এলোমেলো",
            "selected_speed": "তাৎক্ষণিক",
            "selected_views": 0,
            "last_daily_bonus": None
        }
        save_data(db)
    return db["users"][str_id]

# 📱 ১. সাধারণ ইউজার প্যানেল কিবোর্ড
def get_user_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ অটো রিয়্যাকশন প্রজেক্ট যোগ করুন")],
        [KeyboardButton("📁 আমার প্রকল্প"), KeyboardButton("⚙️ আরও")],
        [KeyboardButton("🌟 পরিকল্পনা এবং ভারসাম্য"), KeyboardButton("💰 রিচার্জ করুন")]
    ], resize_keyboard=True)

def get_more_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🔗 রেফার করুন এবং আয় করুন"), KeyboardButton("🎁 দৈনিক উপহার")],
        [KeyboardButton("⚡ তাৎক্ষণিক প্রতিক্রিয়া"), KeyboardButton("🤖 দারুণ বটসে")],
        [KeyboardButton("🔙 ব্যাক")]
    ], resize_keyboard=True)

# 👑 ২. অ্যাডমিন প্যানেল কিবোর্ড (সম্পূর্ণ আলাদা)
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

    # অ্যাডমিন নোটিফিকেশন
    if user.id in ADMIN_IDS:
        await update.message.reply_text(
            f"👑 **স্বাগতম অ্যাডমিন {user.first_name}!**\n\nআপনি অ্যাডমিন মোডে আছেন। অ্যাডমিন প্যানেলে যেতে টাইপ করুন: `/admin`",
            reply_markup=get_user_keyboard(),
            parse_mode='Markdown'
        )
        return

    await update.message.reply_text(
        f"👋 স্বাগতম {user.first_name}!\n\nআপনার অটো রিয়্যাকশন প্রজেক্ট ম্যানেজ করতে নিচের মেনু ব্যবহার করুন:",
        reply_markup=get_user_keyboard()
    )

# 👑 ───────────────────── 👑 সিকিউরড অ্যাডমিন ড্যাশবোর্ড 👑 ───────────────────── 👑
async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ আপনি অ্যাডমিন নন!")
        return

    text = (
        f"👑 **ADMIN CONTROL PANEL**\n"
        f"═══════════════════════\n"
        f"এখানে সম্পূর্ণ আলাদা অ্যাডমিন কন্ট্রোল সিস্টেম সক্রিয় রয়েছে।\n\n"
        f"👥 মোট ইউজার: `{len(db['users'])}` জন\n"
        f"🚫 ব্লক করা ইউজার: `{len(db['blocked'])}` জন\n"
        f"═══════════════════════"
    )
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=get_admin_keyboard())

# --- Project Creation Flow (User Panel) ---
async def start_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if str(user_id) in db["blocked"]:
        return ConversationHandler.END

    u_data = get_user_data(user_id)
    u_data['temp_emojis'] = []
    save_data(db)
    
    text = (
        f"🛰 **ধাপ 0 • চ্যানেল সেটআপ**\n"
        f"───────────────────\n\n"
        f"1) 👤 @{BOT_USERNAME} কে আপনার চ্যানেলে প্রশাসক (Admin) বানান।\n"
        f"2) 🆔 আপনার চ্যানেলের **লিঙ্ক / ইউজারনেম** লিখে পাঠান অথবা চ্যানেল থেকে পোস্ট **ফরোয়ার্ড করুন**।\n\n👇 👇"
    )
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=cancel_keyboard())
    return STEP_CHANNEL

async def save_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    txt = update.message.text or ""

    if txt in ["বাতিল করুন", "🔙 ব্যাক"]:
        return await cancel_flow(update, context)

    if update.message.forward_from_chat:
        u_data['channel_name'] = update.message.forward_from_chat.title
        u_data['channel_id'] = str(update.message.forward_from_chat.id)
    else:
        u_data['channel_name'] = txt
        u_data['channel_id'] = txt

    save_data(db)

    text = (
        f"👍 **চ্যানেল সফলভাবে সেভ করা হয়েছে!**\n\n"
        f"📋 **চ্যানেলের বিবরণ:**\n"
        f"───────────────────\n"
        f"📺 **নাম/লিংক:** {u_data['channel_name']}\n"
        f"───────────────────"
    )
    await update.message.reply_text(text, parse_mode='Markdown')
    return await ask_emoji(update, context)

async def ask_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    selected = ", ".join(u_data['temp_emojis']) if u_data['temp_emojis'] else "(কোনোটিই নয়)"
    
    text = (
        f"📝 **ধাপ 1 • ইমোজি নির্বাচন করুন**\n"
        f"───────────────────\n\n"
        f"আপনার পোস্টের জন্য প্রতিক্রিয়া চয়ন করুন।\n\n"
        f"**নির্বাচিত ({len(u_data['temp_emojis'])}):** {selected}\n\n"
        f"🌟 যেকোনো ইমোজিতে চাপ দিলে যোগ বা রিমুভ হবে। ✅ সম্পন্ন হলে নিচে 'সম্পন্ন' চাপুন।"
    )
    
    keyboard = [
        [InlineKeyboardButton("❤️", callback_data="em_❤️"), InlineKeyboardButton("👍", callback_data="em_👍"), InlineKeyboardButton("🔥", callback_data="em_🔥")],
        [InlineKeyboardButton("🙏", callback_data="em_🙏"), InlineKeyboardButton("🎉", callback_data="em_🎉"), InlineKeyboardButton("🏆", callback_data="em_🏆")],
        [InlineKeyboardButton("💯", callback_data="em_💯"), InlineKeyboardButton("😍", callback_data="em_😍"), InlineKeyboardButton("⚡", callback_data="em_⚡")],
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
    
    data = query.data
    if data == "em_done":
        if not u_data['temp_emojis']:
            u_data['temp_emojis'] = ["👍"]
        save_data(db)
        return await ask_count(update, context)
    
    emoji = data.split("_")[1]
    if emoji in u_data['temp_emojis']:
        u_data['temp_emojis'].remove(emoji)
    else:
        u_data['temp_emojis'].append(emoji)
    
    save_data(db)
    return await ask_emoji(update, context)

async def ask_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    text = (
        f"📊 **ধাপ 2 • মোট প্রতিক্রিয়া**\n"
        f"───────────────────\n\n"
        f"প্রতি পোস্টে কত প্রতিক্রিয়া দিতে চান?\n\n"
        f"👉 **বর্তমান নির্বাচন:** {u_data['selected_count']} প্রতিক্রিয়া"
    )
    keyboard = [
        [InlineKeyboardButton("10", callback_data="cnt_10"), InlineKeyboardButton("20", callback_data="cnt_20"), InlineKeyboardButton("30", callback_data="cnt_30")],
        [InlineKeyboardButton("🔒 50", callback_data="locked"), InlineKeyboardButton("🔒 100", callback_data="locked")],
        [InlineKeyboardButton("🔙 ব্যাক", callback_data="back_emoji"), InlineKeyboardButton("চালিয়ে যান ✅", callback_data="cnt_done")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return STEP_COUNT

async def count_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u_data = get_user_data(query.from_user.id)
    
    if query.data == "cnt_done":
        return await ask_distribution(update, context)
    if query.data == "back_emoji":
        return await ask_emoji(update, context)
    if query.data == "locked":
        await query.answer("এটি প্রো প্ল্যানের জন্য।", show_alert=True)
        return STEP_COUNT
    
    u_data['selected_count'] = int(query.data.split("_")[1])
    save_data(db)
    await query.answer(f"সেট করা হয়েছে: {u_data['selected_count']}")
    return await ask_count(update, context)

async def ask_distribution(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"⚙️ **ধাপ 3 • বিতরণের ধরন**\n"
        f"───────────────────\n\n"
        f"প্রতিক্রিয়া কি প্যাটার্ন অনুসরণ করা উচিত?\n\n"
        f"🎲 **এলোমেলো** - প্রতিটি ইমোজি পাবে ভিন্ন ভিন্ন সংখ্যা\n"
        f"⚖️ **সব সমানভাবে** - প্রতিটি ইমোজি পাবে সমান সংখ্যা"
    )
    keyboard = [
        [InlineKeyboardButton("🎲 এলোমেলো", callback_data="dist_এলোমেলো")],
        [InlineKeyboardButton("⚖️ সব সমানভাবে", callback_data="dist_সমান")],
        [InlineKeyboardButton("🔙 ব্যাক", callback_data="back_count"), InlineKeyboardButton("চালিয়ে যান ✅", callback_data="dist_done")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return STEP_DISTRIBUTION

async def distribution_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u_data = get_user_data(query.from_user.id)
    
    if query.data == "dist_done":
        return await ask_speed(update, context)
    if query.data == "back_count":
        return await ask_count(update, context)
    
    u_data['selected_dist'] = query.data.split("_")[1]
    save_data(db)
    await query.answer(f"মোড: {u_data['selected_dist']}")
    return await ask_distribution(update, context)

async def ask_speed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    text = (
        f"⚡ **ধাপ 4 • গতি নির্বাচন**\n"
        f"───────────────────\n\n"
        f"🚀 ডেলিভারি গতি নির্বাচন করুন:\n\n"
        f"👉 **নির্বাচিত:** ⚡ {u_data['selected_speed']} ডেলিভারি"
    )
    keyboard = [
        [InlineKeyboardButton("দ্রুত", callback_data="spd_দ্রুত"), InlineKeyboardButton("মাঝারি", callback_data="spd_মাঝারি"), InlineKeyboardButton("ধীর", callback_data="spd_ধীর")],
        [InlineKeyboardButton("🔙 ব্যাক", callback_data="back_dist"), InlineKeyboardButton("চালিয়ে যান ✅", callback_data="spd_done")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return STEP_SPEED

async def speed_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u_data = get_user_data(query.from_user.id)
    
    if query.data == "spd_done":
        return await ask_views(update, context)
    if query.data == "back_dist":
        return await ask_distribution(update, context)
    
    u_data['selected_speed'] = query.data.split("_")[1]
    save_data(db)
    await query.answer(f"গতি: {u_data['selected_speed']}")
    return await ask_speed(update, context)

async def ask_views(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    text = (
        f"👁 **ধাপ 5 • ভিউ কনফিগারেশন**\n"
        f"───────────────────\n\n"
        f"প্রতি পোস্টে কত ভিউ দিতে চান?\n\n"
        f"👉 **নির্বাচিত:** {u_data['selected_views'] if u_data['selected_views'] > 0 else 'কোনো ভিউ নেই'}"
    )
    keyboard = [
        [InlineKeyboardButton("0", callback_data="vw_0"), InlineKeyboardButton("10", callback_data="vw_10"), InlineKeyboardButton("30", callback_data="vw_30")],
        [InlineKeyboardButton("🔙 ব্যাক", callback_data="back_speed"), InlineKeyboardButton("চালিয়ে যান ✅", callback_data="vw_done")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return STEP_VIEWS

async def views_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u_data = get_user_data(query.from_user.id)
    
    if query.data == "vw_done":
        return await show_review(update, context)
    if query.data == "back_speed":
        return await ask_speed(update, context)
    
    u_data['selected_views'] = int(query.data.split("_")[1])
    save_data(db)
    await query.answer(f"ভিউ: {u_data['selected_views']}")
    return await ask_views(update, context)

async def show_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    emojis = " ".join(u_data['temp_emojis'])
    
    text = (
        f"✨ **FINAL REVIEW** ✨\n\n"
        f"📺 **চ্যানেল:** {u_data['channel_name']} \n\n"
        f"┌────────────────────\n"
        f"│ 😊 ইমোজি: {emojis}\n"
        f"│ 🎯 মোড: {u_data['selected_dist']}\n"
        f"│ 🚀 প্রতিক্রিয়া: {u_data['selected_count']}\n"
        f"│ 👁 ভিউ: {u_data['selected_views']}\n"
        f"│ ⚡ গতি: {u_data['selected_speed']}\n"
        f"└────────────────────"
    )
    keyboard = [
        [InlineKeyboardButton("✅ প্রকল্প তৈরি করুন", callback_data="create_final")],
        [InlineKeyboardButton("✏️ সম্পাদনা করুন", callback_data="back_views"), InlineKeyboardButton("❌ বাতিল", callback_data="cancel_flow")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return STEP_REVIEW

async def finalize_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    u_data = get_user_data(query.from_user.id)
    save_data(db)
    
    await query.message.reply_text(
        f"🎉 **PROJECT CREATED SUCCESSFULLY!**\n\n"
        f"📁 চ্যানেল: {u_data['channel_name']}\n"
        f"😊 ইমোজি: {' '.join(u_data['temp_emojis'])}\n"
        f"🎯 প্রতিক্রিয়া: {u_data['selected_count']}\n"
        f"👁 ভিউ: {u_data['selected_views']}\n\n"
        f"🏠 প্রধান মেনু",
        reply_markup=get_user_keyboard(), parse_mode='Markdown'
    )
    return ConversationHandler.END

async def cancel_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("প্রক্রিয়া বাতিল করা হয়েছে।", reply_markup=get_user_keyboard())
    return ConversationHandler.END

# 👑 --- Admin Actions Handlers ---
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

# --- Message Handler ---
async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id in db["blocked"]:
        return

    text = update.message.text
    u_data = get_user_data(user_id)

    # 👑 Admin Navigation Control
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

    # 📱 Standard User Navigation
    if text == "🌟 পরিকল্পনা এবং ভারসাম্য":
        project_count = 1 if u_data['channel_name'] else 0
        response_text = (
            f"🌟 **PLAN এবং BALANCE**\n"
            f"───────────────────\n\n"
            f"🆓 **FREE**\n"
            f"মেয়াদ: ∞\n\n"
            f"  **প্রতিক্রিয়া:** 30/post\n"
            f"👀 **ভিউ:** 30/post\n\n"
            f"💎 **ক্রেডিট:** {u_data['credit']}\n"
            f"📊 **ব্যয়:** {u_data['cost']}\n"
            f"📁 **প্রকল্প:** {project_count}"
        )
        await update.message.reply_text(response_text, parse_mode='Markdown', reply_markup=get_user_keyboard())

    elif text == "📁 আমার প্রকল্প":
        if u_data['channel_name']:
            ch_name = u_data['channel_name']
            emojis_str = ", ".join(u_data['temp_emojis']) if u_data['temp_emojis'] else "👍"
            response_text = (
                f"📁 **YOUR PROJECTS**\n"
                f"───────────────────\n"
                f"◆ 1. **{ch_name}** 🌍\n"
                f"Rxn: {u_data['selected_count']} | {emojis_str}\n\n"
                f"🌟 **বিশদ বিবরণ দেখতে একটি প্রকল্পের নাম আলতো চাপুন।**"
            )
            inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"📁 {ch_name}", callback_data="proj_details")]])
            await update.message.reply_text(response_text, parse_mode='Markdown', reply_markup=inline_kb)
        else:
            await update.message.reply_text("❌ আপনার কোনো সক্রিয় প্রকল্প/চ্যানেল নেই।", reply_markup=get_user_keyboard())

    elif text == "💰 রিচার্জ করুন":
        inline_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 এখনই রিচার্জ করুন", callback_data="recharge_now")],
            [InlineKeyboardButton("📞 অ্যাডমিনের সাথে যোগাযোগ করুন", url="https://t.me/telegram")]
        ])
        await update.message.reply_text(
            "**এখনই রিচার্জ করুন**\n───────────────────\n\nএকটি প্ল্যান নির্বাচন এবং রিচার্জ করতে অনুগ্রহ করে নিচের বোতামে ক্লিক করুন। 👇👇👇",
            parse_mode='Markdown',
            reply_markup=inline_kb
        )

    elif text == "⚙️ আরও":
        await update.message.reply_text("একটি বিকল্প বেছে নিন:", reply_markup=get_more_keyboard())

    elif text == "🔙 ব্যাক":
        await update.message.reply_text("প্রধান মেনু:", reply_markup=get_user_keyboard())

    elif text == "🔗 রেফার করুন এবং আয় করুন":
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
        msg = (
            f"🎁 **বন্ধুদের আমন্ত্রণ জানান এবং ক্রেডিট অর্জন করুন!**\n\n"
            f"**আপনার রেফারেল লিঙ্ক:**\n`{ref_link}`\n"
            f"───────────────────\n\n"
            f"📊 **আপনার পরিসংখ্যান:**\n"
            f"• মোট রেফারেল: {u_data['ref_count']}\n"
            f"• অর্জিত ক্রেডিট: {u_data['ref_credit']}\n"
            f"───────────────────\n\n"
            f"• কেউ আপনার লিঙ্কের মাধ্যমে যোগদান করলে, আপনি **+50 ক্রেডিট** পাবেন"
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
            await update.message.reply_text(
                f"🎉 **অভিনন্দন!**\n\n> আপনি দৈনিক উপহার হিসেবে **{bonus} ক্রেডিট** পেয়েছেন! 🎁\n\nআরেকটি উপহারের জন্য আগামীকাল আসুন।",
                parse_mode='Markdown',
                reply_markup=get_more_keyboard()
            )

# 📢 Auto reaction on channel post
async def auto_react_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.channel_post
        if not message: return
        all_emojis = ["👍", "❤️", "🔥", "🎉", "👏", "😍", "🤝", "🤗", "😘"]
        chosen_emoji = random.choice(all_emojis)
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
            STEP_VIEWS: [CallbackQueryHandler(views_callback, pattern="^(vw_|back_speed)")],
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
