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

# 🌐 Render 24/7 Web Server
web_app = Flask('')

@web_app.route('/')
def home():
    return "Reaction Bot is Alive!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# ⚠️ বটের তথ্য
BOT_TOKEN = "8895135409:AAFcEL-TULxTbjil0BNO_hX38oddGlEdlIw"
BOT_USERNAME = "Sahadot_reaction123_bot"
ADMIN_IDS = [7973059882, 8454401183]
ADMIN_USERNAME = "@SAHADOT_VAI"

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

# State Steps
(STEP_CHANNEL, STEP_EMOJI, STEP_COUNT, STEP_DISTRIBUTION, 
 STEP_SPEED, STEP_VIEWS, STEP_REVIEW) = range(7)

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
            "temp_project": {},
            "last_daily_bonus": None
        }
        save_data(db)
    return db["users"][str_id]

# Keyboards
def get_user_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ অটো রিয়্যাকশন প্রজেক্ট যোগ করুন")],
        [KeyboardButton("📁 আমার প্রকল্প"), KeyboardButton("⚙️ আরও")],
        [KeyboardButton("🌟 পরিকল্পনা এবং ভারসাম্য"), KeyboardButton("💰 রিচার্জ করুন")]
    ], resize_keyboard=True)

def cancel_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("বাতিল করুন")]], resize_keyboard=True)

# --- Start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user_data(user.id)
    await update.message.reply_text(
        f"👋 **স্বাগতম {user.first_name}!**\n\nপ্রজেক্ট শুরু করতে **'➕ অটো রিয়্যাকশন প্রজেক্ট যোগ করুন'** বাটনে চাপ দিন।",
        reply_markup=get_user_keyboard(),
        parse_mode='Markdown'
    )

# --- Conversation Flow ---
async def start_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
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
        f"1) 👤 @{BOT_USERNAME} কে আপনার চ্যানেলে এডমিন (Admin) বানান।\n"
        f"2) 🆔 আপনার চ্যানেলের **লিঙ্ক / ইউজারনেম** (যেমন: `@Sahadot_Reaction_Vip`) লিখে পাঠান অথবা চ্যানেল থেকে একটি পোস্ট **ফরোয়ার্ড করুন**।\n\n👇 নিচে ইউজারনেম লিখে পাঠান:"
    )
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=cancel_keyboard())
    return STEP_CHANNEL

async def save_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    txt = msg.text or ""
    u_data = get_user_data(update.effective_user.id)

    if txt in ["বাতিল করুন", "🔙 ব্যাক"]:
        await msg.reply_text("প্রক্রিয়া বাতিল করা হয়েছে।", reply_markup=get_user_keyboard())
        return ConversationHandler.END

    target_chat = None

    # ১. ফরোয়ার্ড পোস্ট চেক
    if msg.forward_from_chat:
        target_chat = msg.forward_from_chat
    # ২. টেক্সট লিংক/ইউজারনেম চেক
    elif txt:
        clean_text = txt.strip()
        if "t.me/" in clean_text:
            clean_text = "@" + clean_text.split("t.me/")[-1].replace("/", "").replace("@", "")
        elif not clean_text.startswith("@") and not clean_text.startswith("-100"):
            clean_text = "@" + clean_text

        try:
            target_chat = await context.bot.get_chat(clean_text)
        except Exception as e:
            await msg.reply_text(
                f"❌ চ্যানেলটি পাওয়ার যায়নি!\n\n"
                f"⚠️ **নিশ্চিত করুন:**\n"
                f"১. বটটি `{clean_text}` চ্যানেলে **Admin** আছে।\n"
                f"২. চ্যানেলের সঠিক ইউজারনেম দিয়েছেন।"
            )
            return STEP_CHANNEL

    if target_chat:
        u_data['temp_project']['channel_name'] = target_chat.title or "Channel"
        u_data['temp_project']['channel_id'] = str(target_chat.id)
        save_data(db)

        confirm_text = (
            f"👍 **চ্যানেল সফলভাবে যোগ করা হয়েছে!**\n\n"
            f"📋 **চ্যানেলের বিবরণ:**\n"
            f"───────────────────\n"
            f"📺 **চ্যানেলের নাম:** {target_chat.title}\n"
            f"🆔 **চ্যানেল আইডি:** `{target_chat.id}`\n"
            f"───────────────────"
        )
        await msg.reply_text(confirm_text, parse_mode='Markdown')
        return await ask_emoji(update, context)

    await msg.reply_text("❌ অকার্যকর ইনপুট! অনুগ্রহ করে সঠিক ইউজারনেম দিন।")
    return STEP_CHANNEL

async def ask_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    temp = u_data['temp_project']
    selected = " ".join(temp['emojis']) if temp['emojis'] else "(none)"
    
    text = (
        f"📝 **ধাপ 1 • ইমোজি নির্বাচন করুন**\n"
        f"───────────────────\n\n"
        f"আপনার পোস্টের জন্য প্রতিক্রিয়া চয়ন করুন।\n\n"
        f"**নির্বাচিত ({len(temp['emojis'])}):** {selected}\n\n"
        f"🌟 **ইমোজিতে চাপ দিয়ে সিলেক্ট/রিমুভ করুন।** ✅ **সম্পন্ন হলে সম্পন্ন বাটনে চাপুন।**"
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
    elif data != "em_custom":
        emoji = data.split("_")[1]
        if emoji in temp['emojis']: temp['emojis'].remove(emoji)
        else: temp['emojis'].append(emoji)
    
    save_data(db)
    return await ask_emoji(update, context)

async def ask_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    temp = u_data['temp_project']
    text = (
        f"📊 **ধাপ 2 • মোট প্রতিক্রিয়া**\n"
        f"───────────────────\n\n"
        f"প্রতি পোস্টে কত প্রতিক্রিয়া পাঠানো হবে?\n\n"
        f"👉 **বর্তমান নির্বাচন:** {temp['count']} প্রতিক্রিয়া"
    )
    keyboard = [
        [InlineKeyboardButton("10", callback_data="cnt_10"), InlineKeyboardButton("20", callback_data="cnt_20"), InlineKeyboardButton("30", callback_data="cnt_30")],
        [InlineKeyboardButton("🔒 50", callback_data="locked"), InlineKeyboardButton("🔒 100", callback_data="locked")],
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
        await query.answer("এটি প্রিমিয়াম ইউজারদের জন্য!", show_alert=True)
        return STEP_COUNT
    
    temp['count'] = int(query.data.split("_")[1])
    save_data(db)
    return await ask_count(update, context)

async def ask_distribution(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"⚙️ **ধাপ 3 • বিতরণের ধরন**\n"
        f"───────────────────\n\n"
        f"প্রতিক্রিয়া কি প্যাটার্ন অনুসরণ করবে?\n"
        f"🎲 **এলোমেলো** - প্রতিটি ইমোজিতে র‍্যান্ডম সংখ্যায় রিয়্যাকশন পড়বে\n"
        f"⚖️ **সকল সমান** - প্রতিটি ইমোজিতে সমান সংখ্যায় রিয়্যাকশন পড়বে"
    )
    keyboard = [
        [InlineKeyboardButton("🎲 এলোমেলো", callback_data="dist_এলোমেলো")],
        [InlineKeyboardButton("⚖️ সব সমানভাবে", callback_data="dist_সমান")],
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

    temp['dist'] = query.data.split("_")[1]
    save_data(db)
    return await ask_distribution(update, context)

async def ask_speed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    temp = u_data['temp_project']
    text = (
        f"⚡ **ধাপ 4 • গতি নির্বাচন**\n"
        f"───────────────────\n\n"
        f"👉 **নির্বাচিত:** ⚡ {temp['speed']} ডেলিভারি"
    )
    keyboard = [
        [InlineKeyboardButton("তাৎক্ষণিক", callback_data="spd_তাৎক্ষণিক"), InlineKeyboardButton("ধীর", callback_data="spd_ধীর")],
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

    temp['speed'] = query.data.split("_")[1]
    save_data(db)
    return await ask_speed(update, context)

async def ask_views(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    temp = u_data['temp_project']
    text = (
        f"👁 **ধাপ 5 • ভিউ কনফিগারেশন**\n"
        f"───────────────────\n\n"
        f"👉 **নির্বাচিত:** {temp['views']} ভিউ"
    )
    keyboard = [
        [InlineKeyboardButton("0 ভিউ", callback_data="vw_0"), InlineKeyboardButton("10 ভিউ", callback_data="vw_10"), InlineKeyboardButton("30 ভিউ", callback_data="vw_30")],
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

    temp['views'] = int(query.data.split("_")[1])
    save_data(db)
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
        f"│ 🚀 প্রতিক্রিয়া: {temp['count']}\n"
        f"│ 👁 ভিউ: {temp['views']} (তাৎক্ষণিক)\n"
        f"│ ⚡ গতি: {temp['speed']}\n"
        f"│ ⚙️ বিতরণ: {temp['dist']}\n"
        f"└────────────────────"
    )
    keyboard = [
        [InlineKeyboardButton("✅ প্রকল্প তৈরি করুন", callback_data="create_final")],
        [InlineKeyboardButton("❌ বাতিল করুন", callback_data="cancel_flow")]
    ]
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return STEP_REVIEW

# 💾 'প্রকল্প তৈরি করুন' ফাইনাল সেভ
async def finalize_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    u_data = get_user_data(query.from_user.id)
    temp = u_data['temp_project']

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
        f"এখন এই চ্যানেলে নতুন কোনো পোস্ট দিলে সাথে সাথে স্বয়ংক্রিয়ভাবে রিয়্যাকশন চলে যাবে।",
        reply_markup=get_user_keyboard(), parse_mode='Markdown'
    )
    return ConversationHandler.END

async def cancel_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.message.reply_text("প্রক্রিয়া বাতিল করা হয়েছে।", reply_markup=get_user_keyboard())
    else:
        await update.message.reply_text("প্রক্রিয়া বাতিল করা হয়েছে।", reply_markup=get_user_keyboard())
    return ConversationHandler.END

# ⚡ চ্যানেলে নতুন পোস্ট এলে অটো-রিয়্যাকশন
async def auto_react_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.channel_post
        if not message: return
        
        channel_id = str(message.chat_id)
        target_emojis = ["👍", "❤️", "🔥"]

        # ডাটাবেসে সেভ থাকা প্রজেক্ট মিলানো
        for uid, uinfo in db["users"].items():
            for proj in uinfo.get("projects", []):
                if str(proj["channel_id"]) == channel_id:
                    target_emojis = proj["emojis"]
                    break

        chosen_emoji = random.choice(target_emojis) if target_emojis else "👍"
        
        # টেলিগ্রাম এপিআই মারফত পোস্ট রিয়্যাকশন দেয়া
        await context.bot.set_message_reaction(
            chat_id=message.chat_id,
            message_id=message.message_id,
            reaction=[ReactionTypeEmoji(emoji=chosen_emoji)]
        )
    except Exception as e:
        logging.error(f"Auto Reaction Error: {e}")

# Main Navigation
async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = update.message.text
    u_data = get_user_data(user_id)

    if text == "🌟 পরিকল্পনা এবং ভারসাম্য":
        p_count = len(u_data.get('projects', []))
        await update.message.reply_text(f"💎 **ক্রেডিট:** {u_data['credit']}\n📁 **প্রকল্প সংখ্যা:** {p_count}", parse_mode='Markdown')
    
    elif text == "📁 আমার প্রকল্প":
        projects = u_data.get('projects', [])
        if projects:
            p_text = "📁 **আপনার প্রকল্পসমূহ:**\n───────────────────\n"
            for idx, p in enumerate(projects, 1):
                p_text += f"{idx}. **{p['channel_name']}**\nইমোজি: {' '.join(p['emojis'])}\nরিঅ্যাকশন: {p['count']}\n\n"
            await update.message.reply_text(p_text, parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ আপনার কোনো সেভ করা প্রকল্প নেই।")

    elif text == "💰 রিচার্জ করুন":
        clean_admin = ADMIN_USERNAME.replace("@", "")
        inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton("💬 অ্যাডমিনকে মেসেজ দিন", url=f"https://t.me/{clean_admin}")]])
        await update.message.reply_text(f"💳 **রিচার্জ করতে নিচের অ্যাডমিনের সাথে কথা বলুন:**\n\n🆔 আপনার আইডি: `{user_id}`", parse_mode='Markdown', reply_markup=inline_kb)

if __name__ == '__main__':
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ অটো রিয়্যাকশন প্রজেক্ট যোগ করুন$"), start_project)],
        states={
            STEP_CHANNEL: [MessageHandler(filters.TEXT | filters.FORWARDED, save_channel)],
            STEP_EMOJI: [CallbackQueryHandler(emoji_callback, pattern="^em_")],
            STEP_COUNT: [CallbackQueryHandler(count_callback, pattern="^(cnt_|back_emoji|locked)")],
            STEP_DISTRIBUTION: [CallbackQueryHandler(distribution_callback, pattern="^(dist_|back_count)")],
            STEP_SPEED: [CallbackQueryHandler(speed_callback, pattern="^(spd_|back_dist)")],
            STEP_VIEWS: [CallbackQueryHandler(views_callback, pattern="^(vw_|back_speed)")],
            STEP_REVIEW: [
                CallbackQueryHandler(finalize_project, pattern="^create_final"),
                CallbackQueryHandler(cancel_flow, pattern="^cancel_flow")
            ]
        },
        fallbacks=[CommandHandler('start', start), MessageHandler(filters.Regex("^বাতিল করুন$"), cancel_flow)]
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu))
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL, auto_react_channel_post))

    print("🤖 Bot Running...")
    app.run_polling()
