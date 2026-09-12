import logging
import re
import json
import os
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

BOT_TOKEN = "8728458795:AAGSXrt0g7rRIaKhJEhepcV_m4rDUE9AaZk"

DATA_FILE = "data.json"
group_data = {}

broadcast_state = {}

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

def get_group(chat_id, title=None):
    chat_id = str(chat_id)

    if chat_id not in group_data:
        group_data[chat_id] = {
            "title": title or f"Group {chat_id}",
            "balance": 0.0,
            "deposit": 0.0,
            "withdraw": 0.0,
            "deposit_count": 0,
            "withdraw_count": 0,
            "allowed_users": []
        }

    if title:
        group_data[chat_id]["title"] = title

    return group_data[chat_id]

# ================= PANEL =================

async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📣 Broadcast Message", callback_data="broadcast")],
        [InlineKeyboardButton("📊 View Groups", callback_data="groups")]
    ]

    await update.message.reply_text(
        "🛠 ADMIN PANEL",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================= BUTTON HANDLER =================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    # START BROADCAST
    if query.data == "broadcast":
        broadcast_state[user_id] = {"step": 1}

        keyboard = []

        for gid, gdata in group_data.items():
            keyboard.append([
                InlineKeyboardButton(gdata["title"], callback_data=f"grp_{gid}")
            ])

        keyboard.append([InlineKeyboardButton("🌍 ALL GROUPS", callback_data="grp_ALL")])

        await query.edit_message_text(
            "📣 Select Group:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # GROUP SELECTED
    elif query.data.startswith("grp_"):
        target = query.data.replace("grp_", "")
        broadcast_state[user_id]["target"] = target
        broadcast_state[user_id]["step"] = 2

        await query.edit_message_text("✍️ Now send broadcast message in chat")

    # VIEW GROUPS
    elif query.data == "groups":
        msg = "📊 GROUP LIST\n\n"
        for gid, gdata in group_data.items():
            msg += f"👉 {gdata['title']}\nID: {gid}\n\n"

        await query.edit_message_text(msg)

# ================= TRACK GROUP =================

async def track_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if chat.type in ["group", "supergroup"]:
        get_group(chat.id, chat.title)
        save_data()

# ================= START =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Your ID: " + str(update.effective_user.id))

# ================= BROADCAST FLOW =================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global broadcast_state

    text = update.message.text.strip()
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    data = get_group(chat_id, update.effective_chat.title)

    # ================= BROADCAST STEP 2 =================
    if user_id in broadcast_state:
        state = broadcast_state[user_id]

        if state["step"] == 2:
            msg = text
            target = state["target"]

            # ALL GROUPS
            if target == "ALL":
                for gid in group_data.keys():
                    try:
                        await context.bot.send_message(chat_id=int(gid), text=msg)
                    except:
                        pass

            else:
                try:
                    await context.bot.send_message(chat_id=int(target), text=msg)
                except:
                    pass

            await update.message.reply_text("✅ Broadcast sent")
            del broadcast_state[user_id]
            return

    # ================= TRANSACTIONS =================

    if user_id not in data["allowed_users"]:
        return

    text = text.replace(" ", "")

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
        data["deposit_count"] += 1
    else:
        data["balance"] -= amount
        data["withdraw"] += amount
        data["withdraw_count"] += 1

    save_data()

    await update.message.reply_text(f"""
📊 Updated

Balance: {data['balance']}
Deposit: {data['deposit_count']}
Withdraw: {data['withdraw_count']}
""")

# ================= MAIN =================

def main():
    load_data()

    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("panel", panel))

    app_bot.add_handler(CallbackQueryHandler(button_handler))

    app_bot.add_handler(MessageHandler(filters.ALL, track_group))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    Thread(target=run_flask).start()
    app_bot.run_polling()

if __name__ == "__main__":
    main()
