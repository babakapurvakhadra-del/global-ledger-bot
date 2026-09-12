import logging
import re
import json
import os
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = "8728458795:AAGSXrt0g7rRIaKhJEhepcV_m4rDUE9AaZk"

DATA_FILE = "data.json"
group_data = {}

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot running"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# ================= STORAGE =================

def load_data():
    global group_data
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            group_data.update(json.load(f))

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(group_data, f)

# ================= CORE =================

def safe_eval(expr):
    try:
        return eval(expr, {"__builtins__": {}})
    except:
        return None

def get_group(chat_id):
    chat_id = str(chat_id)

    if chat_id not in group_data:
        group_data[chat_id] = {
            "base_currency": "INR",
            "target_currency": "USD",
            "rate": 90.0,
            "balance": 0.0,
            "deposit": 0.0,
            "withdraw": 0.0,
            "deposit_count": 0,
            "withdraw_count": 0,
            "allowed_users": []
        }
    return group_data[chat_id]

def is_allowed(user_id, data):
    return user_id in data["allowed_users"]

# ================= COMMANDS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(f"Your ID: {user_id}")

# ---- PERMISSIONS ----

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    user_id = update.effective_user.id
    data = get_group(chat_id)

    if not data["allowed_users"]:
        data["allowed_users"].append(user_id)
        save_data()
        await update.message.reply_text("✅ You are now owner")
        return

    if not is_allowed(user_id, data):
        return

    try:
        new_user = int(context.args[0])
        if new_user not in data["allowed_users"]:
            data["allowed_users"].append(new_user)
            save_data()
            await update.message.reply_text("✅ User added")
    except:
        await update.message.reply_text("Usage: /adduser USER_ID")

# ================= TRANSACTIONS =================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace(" ", "")
    chat_id = str(update.effective_chat.id)
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

    # ✅ FIXED INDENTATION + COUNT LOGIC
    if sign == "+":
        data["balance"] += amount
        data["deposit"] += amount
        data["deposit_count"] += 1
        action = "Received"
    else:
        data["balance"] -= amount
        data["withdraw"] += amount
        data["withdraw_count"] += 1
        action = "Paid"

    converted = amount / data["rate"]
    balance_converted = data["balance"] / data["rate"]

    save_data()

    response = f"""
📊 Overseas Customer Service

{action}: {amount:,.2f} {data['base_currency']}
Converted: {converted:,.2f} {data['target_currency']}

------------------------------
Balance: {data['balance']:,.2f} {data['base_currency']}
Balance: {balance_converted:,.2f} {data['target_currency']}

Total Deposit: {data['deposit']:,.2f}
Total Withdraw: {data['withdraw']:,.2f}

Total deposit count: {data.get('deposit_count', 0)}
Total withdrawal count: {data.get('withdraw_count', 0)}
Total count: {data.get('deposit_count', 0) + data.get('withdraw_count', 0)}

Rate: 1 {data['target_currency']} = {data['rate']} {data['base_currency']}
"""

    await update.message.reply_text(response)

# ================= MAIN =================

def main():
    load_data()

    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("adduser", add_user))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    Thread(target=run_flask).start()
    app_bot.run_polling()

if __name__ == "__main__":
    main()
