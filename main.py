import logging
import random
import os
from datetime import date
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

# ⚠️ আপনার বটের Token ও Username
BOT_TOKEN = "8895135409:AAHpo18y1o74_g1XBeTMO7CCpjj0NYfjWHA"
BOT_USERNAME = "Sahadot_reaction123_bot"

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
    return user_data_store[user_id]

# Keyboards
def get_main_keyboard():
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

def cancel_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("বাতিল করুন")]], resize_keyboard=True)

# --- Start Command ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u_data = get_user_data(user.id)

    # Referral Check
    if context.args:
        try:
            ref_str = context.args[0]
            if ref_str.startswith("ref_"):
                referrer_id = int(ref_str.replace("ref_", ""))
                if referrer_id != user.id and referrer_id in user_data_store:
                    user_data_store[referrer_id]["credit"] += 50
                    user_data_store[referrer_id]["ref_credit"] += 50
                    user_data_store[referrer_id]["ref_count"] += 1
                    try:
                        await context.bot.send_message(
                            chat_id=referrer_id, 
                            text="🎉 আপনার রেফারেল লিংকের মাধ্যমে একজন নতুন সদস্য যোগ দিয়েছেন! আপনি +৫০ ক্রেডিট পেয়েছেন।"
                        )
                    except Exception:
                        pass
        except Exception:
            pass

    await update.message.reply_text(
        f"👋 স্বাগতম {user.first_name}!\n\nআপনার অটো রিয়্যাকশন প্রজেক্ট ম্যানেজ করতে নিচের মেনু ব্যবহার করুন:",
        reply_markup=get_main_keyboard()
    )

# --- Project Creation Flow ---
async def start_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u_data = get_user_data(user_id)
    
    u_data['temp_emojis'] = []
    
    text = (
        f"🛰 **ধাপ 0 • চ্যানেল সেটআপ**\n"
        f"───────────────────\n\n"
        f"1) 👤 @{BOT_USERNAME} কে প্রশাসক বানান\n"
        f"2) 🆔 **পাঠান** চ্যানেল লিঙ্ক বা @username অথবা ID।\n"
        f"🔄 **OR আপনার চ্যানেল থেকে একটি বার্তা ফরোয়ার্ড করুন**\n"
        f"(ফরোয়ার্ডিং ট্যাগ চালু)\n\n👇 👇"
    )
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
    return await ask_emoji(update, context)

async def ask_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    selected = ", ".join(u_data['temp_emojis']) if u_data['temp_emojis'] else "(none)"
    
    text = (
        f"📝 **ধাপ 1 • ইমোজি নির্বাচন করুন**\n"
        f"───────────────────\n\n"
        f"আপনার পোস্টের জন্য প্রতিক্রিয়া চয়ন করুন।\n\n"
        f"**নির্বাচিত ({len(u_data['temp_emojis'])}):** {selected}\n\n"
        f"🌟 ইমোজিতে আলতো চাপুন/remove যোগ করতে। ✅ সম্পন্ন হলে ট্যাপ করুন।"
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
        f"📊 **ধাপ 2 • মোট প্রতিক্রিয়া**\n"
        f"───────────────────\n\n"
        f"প্রতি পোস্টে কত প্রতিক্রিয়া?\n\n"
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
        f"⚙️ **ধাপ 3 • বিতরণের ধরন**\n"
        f"───────────────────\n\n"
        f"প্রতিক্রিয়া কি প্যাটার্ন অনুসরণ করা উচিত?\n"
        f"🎲 **এলোমেলো** - প্রতিটি ইমোজি পায় ভিন্ন ভিন্ন সংখ্যা\n"
        f"⚖️ **সব সমানভাবে** - প্রতিটি ইমোজি ঠিক সমান সংখ্যা পায়"
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
        f"⚡ **STEP 4 • গতি নির্বাচন**\n"
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
    await query.answer(f"গতি: {u_data['selected_speed']}")
    return await ask_speed(update, context)

async def ask_views(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    text = (
        f"👁 **STEP 5 • ভিউ কনফিগারেশন**\n"
        f"───────────────────\n\n"
        f"প্রতি পোস্টে কত ভিউ?\n\n"
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
    
    await query.message.reply_text(
        f"🎉 **PROJECT CREATED SUCCESSFULLY!**\n\n"
        f"📁 চ্যানেল: {u_data['channel_name']}\n"
        f"😊 ইমোজি: {' '.join(u_data['temp_emojis'])}\n"
        f"🎯 প্রতিক্রিয়া: {u_data['selected_count']}\n"
        f"👁 ভিউ: {u_data['selected_views']}\n\n"
        f"🏠 প্রধান মেনু",
        reply_markup=get_main_keyboard(), parse_mode='Markdown'
    )
    return ConversationHandler.END

async def cancel_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("প্রক্রিয়া বাতিল করা হয়েছে।", reply_markup=get_main_keyboard())
    return ConversationHandler.END

# --- General Message Handler for Menu Buttons ---
async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    u_data = get_user_data(user_id)

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
        await update.message.reply_text(response_text, parse_mode='Markdown', reply_markup=get_main_keyboard())

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
            await update.message.reply_text("❌ আপনার কোনো সক্রিয় প্রকল্প/চ্যানেল নেই।", reply_markup=get_main_keyboard())

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
        await update.message.reply_text("প্রধান মেনু:", reply_markup=get_main_keyboard())

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
            await update.message.reply_text(
                f"🎉 **অভিনন্দন!**\n\n> আপনি দৈনিক উপহার হিসেবে **{bonus} ক্রেডিট** পেয়েছেন! 🎁\n\nআরেকটি উপহারের জন্য আগামীকাল আসুন।",
                parse_mode='Markdown',
                reply_markup=get_more_keyboard()
            )

# 📢 Auto reaction on channel post
async def auto_react_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.channel_post
        if not message:
            return

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
        entry_points=[MessageHandler(filters.Regex("^➕ অটো রিয়্যাকশন প্রজেক্ট যোগ করুন$"), start_project)],
        states={
            STEP_CHANNEL: [MessageHandler(filters.TEXT & ~filters.Regex("^(বাতিল করুন|🔙 ব্যাক)$"), save_channel), MessageHandler(filters.FORWARDED, save_channel)],
            STEP_EMOJI: [CallbackQueryHandler(emoji_callback, pattern="^em_")],
            STEP_COUNT: [CallbackQueryHandler(count_callback, pattern="^(cnt_|back_emoji|locked)")],
            STEP_DISTRIBUTION: [CallbackQueryHandler(distribution_callback, pattern="^(dist_|back_count)")],
            STEP_SPEED: [CallbackQueryHandler(speed_callback, pattern="^(spd_|back_dist)")],
            STEP_VIEWS: [CallbackQueryHandler(views_callback, pattern="^(vw_|back_speed)")],
            STEP_REVIEW: [CallbackQueryHandler(finalize_project, pattern="^create_final"), CallbackQueryHandler(ask_views, pattern="^back_views"), CallbackQueryHandler(cancel_flow, pattern="^cancel_flow")]
        },
        fallbacks=[MessageHandler(filters.Regex("^(বাতিল করুন|🔙 ব্যাক)$"), cancel_flow)]
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu))
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL, auto_react_channel_post))

    print("🤖 Bot Ready...")
    app.run_polling()
