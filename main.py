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

WAITING_FOR_CHANNEL = 1

logging.basicConfig(level=logging.INFO)

def get_user_data(user_id):
    if user_id not in user_data_store:
        user_data_store[user_id] = {
            "credit": 27,
            "cost": 0,
            "ref_count": 0,
            "ref_credit": 0,
            "channel": None,
            "channel_id": None,
            "emojis": ["❤️", "🤝", "🤗", "😘", "👍"],
            "last_daily_bonus": None
        }
    return user_data_store[user_id]

# Main Permanent Keyboard
def get_main_keyboard():
    keyboard = [
        [KeyboardButton("➕ অটো রিয়্যাকশন প্রজেক্ট যোগ করুন")],
        [KeyboardButton("📁 আমার প্রকল্প"), KeyboardButton("⚙️ আরও")],
        [KeyboardButton("🌟 পরিকল্পনা এবং ভারসাম্য"), KeyboardButton("💰 রিচার্জ করুন")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_more_keyboard():
    keyboard = [
        [KeyboardButton("🔗 রেফার করুন এবং আয় করুন"), KeyboardButton("🎁 দৈনিক উপহার")],
        [KeyboardButton("⚡ তাৎক্ষণিক প্রতিক্রিয়া"), KeyboardButton("🤖 দারুণ বটসে")],
        [KeyboardButton("🔙 ব্যাক")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

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
        f"👋 স্বাগতম {user.first_name}!\n\nনিচের মেনু থেকে আপনার পছন্দমতো অপশন বেছে নিন:",
        reply_markup=get_main_keyboard()
    )

# Handle Permanent Reply Keyboard Clicks
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    u_data = get_user_data(user_id)

    if text == "🌟 পরিকল্পনা এবং ভারসাম্য":
        project_count = 1 if u_data['channel'] else 0
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
        if u_data['channel']:
            ch_name = u_data['channel']
            emojis_str = ", ".join(u_data['emojis'])
            response_text = (
                f"📁 **YOUR PROJECTS**\n"
                f"───────────────────◆ 1. **{ch_name}** 🌍\n"
                f"Rxn: 30 | {emojis_str}\n\n"
                f"🌟 **বিশদ বিবরণ দেখতে একটি প্রকল্পের নাম আলতো চাপুন।**"
            )
            inline_kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"📁 {ch_name}", callback_data="proj_details")]])
            await update.message.reply_text(response_text, parse_mode='Markdown', reply_markup=inline_kb)
        else:
            await update.message.reply_text("❌ আপনার কোনো সক্রিয় প্রকল্প/চ্যানেল নেই।", reply_markup=get_main_keyboard())

    elif text == "➕ অটো রিয়্যাকশন প্রজেক্ট যোগ করুন":
        if u_data['channel']:
            await update.message.reply_text(
                "🚫 **প্রকল্প তৈরির সীমা পৌঁছেছে**\n\n"
                "আপনার বর্তমান পরিকল্পনা সর্বাধিক _1 প্রকল্পের অনুমতি দেয় এবং আপনি এই সীমাতে পৌঁছেছেন।\n\n"
                "আরও প্রকল্প তৈরি করতে:\n"
                "• উচ্চ সীমার জন্য আপনার পরিকল্পনা আপগ্রেড করুন\n"
                "• আপনার প্রকল্পের কোটা বাড়াতে অ্যাডমিনের সাথে যোগাযোগ করুন",
                parse_mode='Markdown',
                reply_markup=get_main_keyboard()
            )
        else:
            await update.message.reply_text("আপনার চ্যানেলের ইউজারনেম বা লিংক পাঠাবে (যেমন: `@mychannel`):")
            return WAITING_FOR_CHANNEL

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
        bot_info = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
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

async def add_channel_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel_link = update.message.text
    u_data = get_user_data(update.effective_user.id)
    u_data['channel'] = channel_link
    await update.message.reply_text(f"✅ আপনার চ্যানেল সফলভাবে যুক্ত করা হয়েছে: `{channel_link}`", parse_mode='Markdown', reply_markup=get_main_keyboard())
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return ConversationHandler.END

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
        entry_points=[MessageHandler(filters.Regex("^➕ অটো রিয়্যাকশন প্রজেক্ট যোগ করুন$"), handle_message)],
        states={
            WAITING_FOR_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel_save)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL, auto_react_channel_post))

    print("🤖 Bot updated and running...")
    app.run_polling()
