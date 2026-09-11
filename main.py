import logging
import re
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# ================= CONFIG =================
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

# Store per group data
group_data = {}

# ==========================================

logging.basicConfig(level=logging.INFO)

# Flask keep alive
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# ==========================================

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
            "rate": 90.0,
            "balance": 0.0,
            "deposit": 0.0,
            "withdraw": 0.0
        }
    return group_data[chat_id]

# ==========================================

async def set_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data = get_group(chat_id)

    if not context.args:
        await update.message.reply_text("Usage: /setcurrency USD")
        return

    currency = context.args[0].upper()
    data["target_currency"] = currency

    await update.message.reply_text(f"✅ Currency set to {currency}")

async def set_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    data = get_group(chat_id)

    if not context.args:
        await update.message.reply_text("Usage: /setrate 95")
        return

    try:
        rate = float(context.args[0])
        data["rate"] = rate
        await update.message.reply_text(f"✅ Rate set to {rate}")
    except:
        await update.message.reply_text("❌ Invalid rate")

# ==========================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace(" ", "")
    chat_id = update.effective_chat.id
    data = get_group(chat_id)

    match = re.match(r'^([+-])\(?(.+?)\)?$', text)

    if not match:
        return

    sign = match.group(1)
    expr = match.group(2)

    amount = safe_eval(expr)

    if amount is None:
        await update.message.reply_text("❌ Invalid calculation")
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

    response = f"""
📊 Overseas Customer Service

{action}: {amount:,.2f} {data['base_currency']}
Converted: {converted:,.2f} {data['target_currency']}

------------------------------
Balance: {data['balance']:,.2f} {data['base_currency']}
Balance: {balance_converted:,.2f} {data['target_currency']}

Total Deposit: {data['deposit']:,.2f}
Total Withdraw: {data['withdraw']:,.2f}

Rate: 1 {data['target_currency']} = {data['rate']} {data['base_currency']}
"""

    await update.message.reply_text(response)

# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 Use:\n+500\n-200\n+(100*2)\n\nCommands:\n/setcurrency USD\n/setrate 95"
    )

# ==========================================

def main():
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("setcurrency", set_currency))
    app_bot.add_handler(CommandHandler("setrate", set_rate))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    Thread(target=run_flask).start()

    app_bot.run_polling()

# ==========================================

if __name__ == "__main__":
    main()
