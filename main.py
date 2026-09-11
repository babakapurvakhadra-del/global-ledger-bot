import logging
import re
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = "8728458795:AAGSXrt0g7rRIaKhJEhepcV_m4rDUE9AaZk"

group_data = {}

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot running"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# ==========================

def safe_eval(expr):
    try:
        return eval(expr, {"__builtins__": {}})
    except:
        return None

def get_group(chat_id):
    if chat_id not in group_data:
        group_data[chat_id] = {
            "base_currency": "INR",
            "target_currency": "USD",
            "rate": 90,
            "balance": 0,
            "deposit": 0,
            "withdraw": 0,
            "allowed_users": []
        }
    return group_data[chat_id]

def is_allowed(user_id, data):
    return user_id in data["allowed_users"]

# ==========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(f"Your ID: {user_id}")

# ==========================

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    data = get_group(chat_id)

    # First user becomes owner
    if not data["allowed_users"]:
        data["allowed_users"].append(user_id)
        await update.message.reply_text("✅ You are now owner")
        return

    if not is_allowed(user_id, data):
        return

    try:
        new_user = int(context.args[0])
        if new_user not in data["allowed_users"]:
            data["allowed_users"].append(new_user)
            await update.message.reply_text("✅ User added")
    except:
        await update.message.reply_text("Usage: /adduser USER_ID")

# ==========================

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    data = get_group(chat_id)

    if not is_allowed(user_id, data):
        return

    try:
        rem_user = int(context.args[0])
        if rem_user in data["allowed_users"]:
            data["allowed_users"].remove(rem_user)
            await update.message.reply_text("❌ User removed")
    except:
        await update.message.reply_text("Usage: /removeuser USER_ID")

# ==========================

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_group(update.effective_chat.id)
    await update.message.reply_text(f"Allowed Users:\n{data['allowed_users']}")

# ==========================

async def set_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    data = get_group(chat_id)

    if not is_allowed(user_id, data):
        return

    if not context.args:
        return

    data["target_currency"] = context.args[0].upper()
    await update.message.reply_text("✅ Currency updated")

async def set_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    data = get_group(chat_id)

    if not is_allowed(user_id, data):
        return

    try:
        data["rate"] = float(context.args[0])
        await update.message.reply_text("✅ Rate updated")
    except:
        pass

# ==========================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace(" ", "")
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    data = get_group(chat_id)

    if not is_allowed(user_id, data):
        return

    match = re.match(r'^([+-])\(?(.+?)\)?$', text)
    if not match:
        return

    sign = match.group(1)
    expr = match.group(2)

    amount = safe_eval(expr)
    if amount is None:
        return

    amount = float(amount)

    if sign == "+":
        data["balance"] += amount
        data["deposit"] += amount
        action = "Received"
    else:
        data["balance"] -= amount
        data["withdraw"] += amount
        action = "Paid"

    converted = amount / data["rate"]
    balance_converted = data["balance"] / data["rate"]

    msg = f"""
{action}: {amount:.2f} INR
Converted: {converted:.2f} {data['target_currency']}

Balance: {data['balance']:.2f} INR
Balance: {balance_converted:.2f} {data['target_currency']}
"""
    await update.message.reply_text(msg)

# ==========================

def main():
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("adduser", add_user))
    app_bot.add_handler(CommandHandler("removeuser", remove_user))
    app_bot.add_handler(CommandHandler("users", list_users))
    app_bot.add_handler(CommandHandler("setcurrency", set_currency))
    app_bot.add_handler(CommandHandler("setrate", set_rate))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    Thread(target=run_flask).start()
    app_bot.run_polling()

if __name__ == "__main__":
    main()
