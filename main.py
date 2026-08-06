import logging
import random
import os
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReactionTypeEmoji
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# 🌐 Render-কে লাইভ রাখার জন্য ছোট ওয়েব সার্ভার
web_app = Flask('')

@web_app.route('/')
def home():
    return "Bot is alive and running 24/7!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# ⚠️ আপনার বটের Token
BOT_TOKEN = "8895135409:AAHpo18y1o74_g1XBeTMO7CCpjj0NYfjWHA"

# ইউজারদের ডাটা চিরস্থায়ী রাখার জন্য স্থায়ী ডিকশনারি
user_data_store = {}

WAITING_FOR_CHANNEL = 1
WAITING_FOR_EMOJIS = 2
WAITING_FOR_COUNT = 3

logging.basicConfig(level=logging.INFO)

def get_user_data(user_id):
    if user_id not in user_data_store:
        user_data_store[user_id] = {
            "balance": 100,
            "ref_count": 0,
            "channel": None,  # প্রথমে কোনো চ্যানেল থাকে না
            "emojis": ["👍", "❤️", "🔥", "🎉"],
            "count": 5,
            "speed": "মাঝারি"
        }
    return user_data_store[user_id]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u_data = get_user_data(user.id)
    
    if context.args:
        try:
            referrer_id = int(context.args[0])
            if referrer_id != user.id and referrer_id in user_data_store:
                user_data_store[referrer_id]["balance"] += 200
                user_data_store[referrer_id]["ref_count"] += 1
                try:
                    await context.bot.send_message(
                        chat_id=referrer_id, 
                        text="🎉 আপনার রেফারাল লিংকের মাধ্যমে একজন নতুন ইউজার যুক্ত হয়েছেন! আপনি ২০০ কয়েন পেয়েছেন।"
                    )
                except Exception:
                    pass
        except ValueError:
            pass

    keyboard = [
        [InlineKeyboardButton("📢 চ্যানেল যুক্ত করুন", callback_data='menu_add_channel')],
        [InlineKeyboardButton("👤 অ্যাকাউন্ট", callback_data='menu_account'), InlineKeyboardButton("🔗 রেফার করুন", callback_data='menu_refer')],
        [InlineKeyboardButton("⚙️ অটো রিয়্যাকশন প্ল্যান", callback_data='menu_plan')]
    ]
    
    await update.message.reply_text(
        f"👋 হে {user.first_name}, স্বাগতম!\n\nনিচের মেনু থেকে অপশন নির্বাচন করুন:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    u_data = get_user_data(user_id)

    try:
        if query.data == 'menu_account':
            channel_display = u_data['channel'] if u_data['channel'] else "কোনো চ্যানেল যুক্ত করা হয়নি"
            text = (
                f"👤 **অ্যাাকাউন্ট তথ্য**\n\n"
                f"💰 ব্যালেন্স: {u_data['balance']} কয়েন\n"
                f"📢 চ্যানেল: {channel_display}"
            )
            keyboard = [[InlineKeyboardButton("🔙 প্রধান মেনু", callback_data='main_menu')]]
            await query.message.edit_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

        elif query.data == 'menu_refer':
            bot_info = await context.bot.get_me()
            ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
            text = (
                f"🎁 **১ জন কে রেফার করলে পাবেন: ২০০ কয়েন**\n\n"
                f"আপনার রেফার লিংক:\n`{ref_link}`\n\n"
                f"📊 মোট রেফার করেছেন: {u_data['ref_count']} জন"
            )
            keyboard = [[InlineKeyboardButton("🔙 প্রধান মেনু", callback_data='main_menu')]]
            await query.message.edit_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

        elif query.data == 'menu_plan':
            emoji_str = " ".join(u_data['emojis']) if isinstance(u_data['emojis'], list) else str(u_data['emojis'])
            text = (
                f"⚙️ **অটো রিয়্যাকশন প্ল্যান সেটিং**\n\n"
                f"১. ইমোজি: {emoji_str}\n"
                f"২. প্রতি পোস্টে রিয়্যাকশন: {u_data['count']} টি\n"
                f"৩. স্পিড: {u_data['speed']}\n\n"
                f"নিচের বোতামগুলো দিয়ে পরিবর্তন করুন:"
            )
            keyboard = [
                [InlineKeyboardButton("১. ইমোজি নির্বাচন", callback_data='plan_emoji')],
                [InlineKeyboardButton("২. রিয়্যাকশন সংখ্যা", callback_data='plan_count')],
                [InlineKeyboardButton("৩. স্পিড সিলেক্ট", callback_data='plan_speed')],
                [InlineKeyboardButton("💾 সেভ রাখুন", callback_data='plan_submit')],
                [InlineKeyboardButton("🔙 প্রধান মেনু", callback_data='main_menu')]
            ]
            await query.message.edit_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

        elif query.data == 'plan_speed':
            keyboard = [
                [InlineKeyboardButton("⚡ দ্রুত (Fast)", callback_data='speed_fast')],
                [InlineKeyboardButton("🚶 মাঝারি (Medium)", callback_data='speed_medium')],
                [InlineKeyboardButton("🐢 স্লো (Slow)", callback_data='speed_slow')],
                [InlineKeyboardButton("🔙 ব্যাকে যান", callback_data='menu_plan')]
            ]
            await query.message.edit_text("রিয়্যাকশনের গতি নির্বাচন করুন:", reply_markup=InlineKeyboardMarkup(keyboard))

        elif query.data.startswith('speed_'):
            speed_map = {'speed_fast': 'দ্রুত', 'speed_medium': 'মাঝারি', 'speed_slow': 'স্লো'}
            u_data['speed'] = speed_map[query.data]
            keyboard = [[InlineKeyboardButton("🔙 অটো রিয়্যাকশন প্ল্যান", callback_data='menu_plan')]]
            await query.message.edit_text(f"✅ স্পিড সেট করা হয়েছে: {u_data['speed']}", reply_markup=InlineKeyboardMarkup(keyboard))

        elif query.data == 'plan_submit':
            keyboard = [[InlineKeyboardButton("🔙 প্রধান মেনু", callback_data='main_menu')]]
            await query.message.edit_text("✅ আপনার অটো রিয়্যাকশন প্ল্যান ও সমস্ত সেটিংস সফলভাবে সেভ করা হয়েছে!", reply_markup=InlineKeyboardMarkup(keyboard))

        elif query.data == 'main_menu':
            keyboard = [
                [InlineKeyboardButton("📢 চ্যানেল যুক্ত করুন", callback_data='menu_add_channel')],
                [InlineKeyboardButton("👤 অ্যাকাউন্ট", callback_data='menu_account'), InlineKeyboardButton("🔗 রেফার করুন", callback_data='menu_refer')],
                [InlineKeyboardButton("⚙️ অটো রিয়্যাকশন প্ল্যান", callback_data='menu_plan')]
            ]
            await query.message.edit_text("প্রধান মেনু:", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logging.error(f"Error handling button: {e}")

# 📢 চ্যানেল পোস্টে অটোমেটিক রিয়্যাকশন দেওয়ার ফাংশন
async def auto_react_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.channel_post
        if not message:
            return

        # যেকোনো ইউজারের সেট করা ইমোজি তালিকা থেকে র্যান্ডম একটি নির্বাচন করা
        all_emojis = ["👍", "❤️", "🔥", "🎉", "👏", "😍"]
        chosen_emoji = random.choice(all_emojis)

        await context.bot.set_message_reaction(
            chat_id=message.chat_id,
            message_id=message.message_id,
            reaction=[ReactionTypeEmoji(emoji=chosen_emoji)]
        )
        logging.info(f"Reacted {chosen_emoji} to channel post {message.message_id}")
    except Exception as e:
        logging.error(f"Failed to set reaction in channel: {e}")

# 📢 ১টির বেশি চ্যানেল যাতে অ্যাড না হয় তার লজিক
async def add_channel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    u_data = get_user_data(query.from_user.id)

    if u_data['channel']:
        text = (
            f"⚠️ **আপনার ইতোমধ্যে একটি চ্যানেল যুক্ত করা আছে!**\n\n"
            f"বর্তমান চ্যানেল: `{u_data['channel']}`\n\n"
            f"একটি অ্যাকাউন্টে একটার বেশি চ্যানেল যুক্ত করা যাবে না। নতুন চ্যানেল যুক্ত করতে চাইলে নতুন লিংকটি লিখে পাঠান (এটি আগেরটিকে পরিবর্তন করবে):"
        )
    else:
        text = "আপনার চ্যানেলের ইউজারনেম বা লিংক সেন্ড করুন (যেমন: `@mychannel`):"

    await query.message.reply_text(text, parse_mode='Markdown')
    return WAITING_FOR_CHANNEL

async def add_channel_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel_link = update.message.text
    u_data = get_user_data(update.effective_user.id)
    u_data['channel'] = channel_link
    await update.message.reply_text(f"✅ আপনার চ্যানেল সফলভাবে সেট/পরিবর্তন করা হয়েছে: `{channel_link}`", parse_mode='Markdown')
    return ConversationHandler.END

async def set_emoji_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("রিয়্যাকশন ইমোজিগুলো স্পেস দিয়ে লিখুন (যেমন: 👍 ❤️ 🔥):")
    return WAITING_FOR_EMOJIS

async def set_emoji_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u_data = get_user_data(update.effective_user.id)
    u_data['emojis'] = update.message.text.split()
    await update.message.reply_text(f"✅ আপনার পছন্দের ইমোজি সেভ হয়েছে: {update.message.text}")
    return ConversationHandler.END

async def set_count_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("একটি পোস্টে কতগুলো রিয়্যাকশন চান সংখ্যা লিখুন:")
    return WAITING_FOR_COUNT

async def set_count_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = int(update.message.text)
        u_data = get_user_data(update.effective_user.id)
        u_data['count'] = count
        await update.message.reply_text(f"✅ রিয়্যাকশন সংখ্যা সেভ করা হয়েছে: {count} টি।")
    except ValueError:
        await update.message.reply_text("❌ শুধু একটি সংখ্যা লিখুন।")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return ConversationHandler.END

if __name__ == '__main__':
    keep_alive()
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(add_channel_start, pattern='^menu_add_channel$'),
            CallbackQueryHandler(set_emoji_start, pattern='^plan_emoji$'),
            CallbackQueryHandler(set_count_start, pattern='^plan_count$')
        ],
        states={
            WAITING_FOR_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel_save)],
            WAITING_FOR_EMOJIS: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_emoji_save)],
            WAITING_FOR_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_count_save)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL, auto_react_channel_post))

    print("🤖 বট সফলভাবে চালু হয়েছে...")
    app.run_polling()
