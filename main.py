import logging
import random
import os
from datetime import datetime, date
from threading import Thread
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, ReactionTypeEmoji
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# 🌐 Web Server for Render
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

BOT_TOKEN = "8895135409:AAHpo18y1o74_g1XBeTMO7CCpjj0NYfjWHA"

# Data store
user_data_store = {}

# Conversation States
(STEP_CHANNEL, STEP_EMOJI, STEP_COUNT, STEP_DISTRIBUTION, 
 STEP_SPEED, STEP_VIEWS, STEP_REVIEW) = range(7)

logging.basicConfig(level=logging.INFO)

def get_user_data(user_id):
    if user_id not in user_data_store:
        user_data_store[user_id] = {
            "credit": 100,
            "cost": 0,
            "ref_count": 0,
            "channel_name": None,
            "channel_id": None,
            "temp_emojis": [],
            "selected_count": 20,
            "selected_dist": "এলোমেলো",
            "selected_speed": "তাৎক্ষণিক",
            "selected_views": 0,
            "last_daily_bonus": None
        }
    return user_data_store[user_id]

# Keyboards
def get_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ অটো রিয়্যাকশন প্রজেক্ট যোগ করুন")],
        [KeyboardButton("📁 আমার প্রকল্প"), KeyboardButton("⚙️ আরও")],
        [KeyboardButton("🌟 পরিকল্পনা এবং ভারসাম্য"), KeyboardButton("💰 রিচার্জ করুন")]
    ], resize_keyboard=True)

def cancel_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("বাতিল করুন")]], resize_keyboard=True)

# --- Start Command ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    await update.message.reply_text(
        "👋 স্বাগতম! আপনার অটো রিয়্যাকশন প্রজেক্ট ম্যানেজ করতে নিচের মেনু ব্যবহার করুন।",
        reply_markup=get_main_keyboard()
    )

# --- Project Creation Flow ---

async def start_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u_data = get_user_data(user_id)
    
    # Reset temp data
    u_data['temp_emojis'] = []
    
    text = (
        "🛰 **ধাপ 0 • চ্যানেল সেটআপ**\n"
        "───────────────────\n\n"
        "1) 👤 @multi_reaction_bot কে প্রশাসক বানান\n"
        "2) 🆔 **পাঠান** চ্যানেল লিঙ্ক বা @username অথবা ID।\n"
        "🔄 **OR আপনার চ্যানেল থেকে একটি বার্তা ফরোয়ার্ড করুন**\n"
        "(ফরোয়ার্ডিং ট্যাগ চালু)\n\n👇 👇"
    )
    # ছবির মতো উপরের ব্যানার টেক্সট (আপনি চাইলে ছবি পাঠাতে পারেন)
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=cancel_keyboard())
    return STEP_CHANNEL

async def save_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    
    if update.message.forward_from_chat:
        u_data['channel_name'] = update.message.forward_from_chat.title
        u_data['channel_id'] = update.message.forward_from_chat.id
    else:
        u_data['channel_name'] = update.message.text
        u_data['channel_id'] = update.message.text

    text = (
        f"👍 চ্যানেল সফলভাবে যোগ করা হয়েছে! সনাক্ত করা প্রকার: PUBLIC\n\n"
        f"📋 চ্যানেলের বিবরণ:\n"
        f"───────────────────\n"
        f"📺 চ্যানেলের নাম: {u_data['channel_name']}\n"
        f"🆔 চ্যানেল আইডি: {u_data['channel_id']}\n"
        f"───────────────────"
    )
    await update.message.reply_text(text, reply_markup=cancel_keyboard())
    
    # Next Step: Emoji selection
    return await ask_emoji(update, context)

async def ask_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    selected = ", ".join(u_data['temp_emojis']) if u_data['temp_emojis'] else "(none)"
    
    text = (
        "📝 **ধাপ 1 • ইমোজি নির্বাচন করুন**\n"
        "───────────────────\n\n"
        "আপনার পোস্টের জন্য প্রতিক্রিয়া চয়ন করুন।\n\n"
        f"**নির্বাচিত ({len(u_data['temp_emojis'])}):** {selected}\n\n"
        "🌟 ইমোজিতে আলতো চাপুন/remove যোগ করতে। ✅ সম্পন্ন হলে ট্যাপ করুন।"
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
            u_data['temp_emojis'] = ["👍"] # Default
        return await ask_count(update, context)
    
    emoji = data.split("_")[1]
    if emoji in u_data['temp_emojis']:
        u_data['temp_emojis'].remove(emoji)
    else:
        u_data['temp_emojis'].append(emoji)
    
    return await ask_emoji(update, context)

async def ask_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    text = (
        "📊 **ধাপ 2 • মোট প্রতিক্রিয়া**\n"
        "───────────────────\n\n"
        "প্রতি পোস্টে কত প্রতিক্রিয়া?\n\n"
        f"🌟 একটি প্রিসেট চয়ন করুন। 👉 **বর্তমান নির্বাচন: {u_data['selected_count']} প্রতিক্রিয়া**"
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
    await query.answer(f"সেট করা হয়েছে: {u_data['selected_count']}")
    return await ask_count(update, context)

async def ask_distribution(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "⚙️ **ধাপ 3 • বিতরণের ধরন**\n"
        "───────────────────\n\n"
        "প্রতিক্রিয়া কি প্যাটার্ন অনুসরণ করা উচিত?\n"
        "🎲 **এলোমেলো** - প্রতিটি ইমোজি পায় ভিন্ন ভিন্ন সংখ্যা\n"
        "⚖️ **সকাল সমান** - প্রতিটি ইমোজি ঠিক সমান সংখ্যা পায়"
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
    await query.answer(f"মোড: {u_data['selected_dist']}")
    return await ask_distribution(update, context)

async def ask_speed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    text = (
        "⚡ **STEP 4 • গতি নির্বাচন**\n"
        "───────────────────\n\n"
        "🚀 ডেলিভারি গতি নির্বাচন করুন:\n\n"
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
    await query.answer(f"গতি: {u_data['selected_speed']}")
    return await ask_speed(update, context)

async def ask_views(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    text = (
        "👁 **STEP 5 • ভিউ কনফিগারেশন**\n"
        "───────────────────\n\n"
        "প্রতি পোস্টে কত ভিউ?\n\n"
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
    await query.answer(f"ভিউ: {u_data['selected_views']}")
    return await ask_views(update, context)

async def show_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    emojis = " ".join(u_data['temp_emojis'])
    
    text = (
        "✨ **FINAL REVIEW** ✨\n\n"
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
    u_data = get_user_data(query.from_user.id)
    
    # Success Message
    await query.message.reply_text(
        "🎉 **PROJECT CREATED SUCCESSFULLY!**\n\n"
        f"📁 চ্যানেল: {u_data['channel_name']}\n"
        f"😊 ইমোজি: {' '.join(u_data['temp_emojis'])}\n"
        f"🎯 প্রতিক্রিয়া: {u_data['selected_count']}\n"
        f"👁 ভিউ: {u_data['selected_views']}\n\n"
        "🏠 প্রধান মেনু",
        reply_markup=get_main_keyboard(), parse_mode='Markdown'
    )
    return ConversationHandler.END

async def cancel_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("প্রক্রিয়া বাতিল করা হয়েছে।", reply_markup=get_main_keyboard())
    return ConversationHandler.END

if __name__ == '__main__':
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ অটো রিয়্যাকশন প্রজেক্ট যোগ করুন$"), start_project)],
        states={
            STEP_CHANNEL: [MessageHandler(filters.TEXT & ~filters.Regex("^বাতিল করুন$"), save_channel), MessageHandler(filters.FORWARDED, save_channel)],
            STEP_EMOJI: [CallbackQueryHandler(emoji_callback, pattern="^em_")],
            STEP_COUNT: [CallbackQueryHandler(count_callback, pattern="^(cnt_|back_emoji|locked)")],
            STEP_DISTRIBUTION: [CallbackQueryHandler(distribution_callback, pattern="^(dist_|back_count)")],
            STEP_SPEED: [CallbackQueryHandler(speed_callback, pattern="^(spd_|back_dist)")],
            STEP_VIEWS: [CallbackQueryHandler(views_callback, pattern="^(vw_|back_speed)")],
            STEP_REVIEW: [CallbackQueryHandler(finalize_project, pattern="^create_final"), CallbackQueryHandler(ask_views, pattern="^back_views"), CallbackQueryHandler(cancel_flow, pattern="^cancel_flow")]
        },
        fallbacks=[MessageHandler(filters.Regex("^বাতিল করুন$"), cancel_flow)]
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler('start', start))
    # handle other menu buttons as before
    # app.add_handler(MessageHandler(filters.TEXT, handle_other_menu)) 

    print("🤖 Bot Ready with Step-by-Step Flow...")
    app.run_polling()
