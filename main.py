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
OWNER_ID = 6609362058

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
        try:
            with open(DATA_FILE, "r") as f:
                group_data.update(json.load(f))
        except:
            group_data = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(group_data, f, indent=2)

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

    if title:
        group_data[chat_id]["title"] = title

    return group_data[chat_id]

def is_allowed(user_id, data):
    return user_id in data["allowed_users"]

# ================= PANEL =================

async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📣 Broadcast", callback_data="broadcast")],
        [InlineKeyboardButton("📊 Groups", callback_data="groups")]
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

    if query.data == "broadcast":
        broadcast_state[user_id] = {"step": 1}

        keyboard = []
        for gid, g in group_data.items():
            keyboard.append([
                InlineKeyboardButton(g["title"], callback_data=f"grp_{gid}")
            ])

        keyboard.append([InlineKeyboardButton("🌍 ALL GROUPS", callback_data="grp_ALL")])

        await query.edit_message_text(
            "📣 Select Group:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data.startswith("grp_"):
        target = query.data.replace("grp_", "")
        broadcast_state[user_id]["target"] = target
        broadcast_state[user_id]["step"] = 2

        await query.edit_message_text("✍️ Send message to broadcast")

    elif query.data == "groups":
        msg = "📊 GROUP LIST\n\n"
        for gid, g in group_data.items():
            msg += f"👉 {g['title']}\nID: {gid}\n\n"

        await query.edit_message_text(msg)

# ================= TRACK GROUP =================

async def track_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if chat.type in ["group", "supergroup"]:
        chat_id = str(chat.id)
        chat_title = chat.title

        is_new = chat_id not in group_data

        get_group(chat.id, chat.title)
        save_data()

        if is_new:
            try:
                await context.bot.send_message(
                    chat_id=OWNER_ID,
                    text=f"""🚀 Bot added in new group!

📌 {chat_title}
🆔 {chat_id}"""
                )
            except Exception as e:
                print("Notify error:", e)

# ================= START =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Your ID: " + str(update.effective_user.id))

# ================= ADD USER =================

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    user_id = update.effective_user.id
    data = get_group(chat_id, update.effective_chat.title)

    if not data["allowed_users"]:
        data["allowed_users"].append(user_id)
        save_data()
        await update.message.reply_text("✅ You are OWNER now")
        return

    if not is_allowed(user_id, data):
        await update.message.reply_text("❌ Not allowed")
        return

    try:
        new_user = int(context.args[0])
        if new_user not in data["allowed_users"]:
            data["allowed_users"].append(new_user)
            save_data()
            await update.message.reply_text("✅ User added")
    except:
        await update.message.reply_text("Usage: /adduser USER_ID")

# ================= SETTINGS =================

async def set_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_group(update.effective_chat.id, update.effective_chat.title)

    if update.effective_user.id not in data["allowed_users"]:
        return

    try:
        data["target_currency"] = context.args[0].upper()
        save_data()
        await update.message.reply_text(f"✅ Currency set to {data['target_currency']}")
    except:
        await update.message.reply_text("Usage: /setcurrency USD")

async def set_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_group(update.effective_chat.id, update.effective_chat.title)

    if update.effective_user.id not in data["allowed_users"]:
        return

    try:
        data["rate"] = float(context.args[0])
        save_data()
        await update.message.reply_text(f"✅ Rate set to {data['rate']}")
    except:
        await update.message.reply_text("❌ Invalid rate")

# ================= MAIN LOGIC =================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global broadcast_state

    text = update.message.text.strip()
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    data = get_group(chat_id, update.effective_chat.title)

    # ===== BROADCAST =====
    if user_id in broadcast_state and broadcast_state[user_id].get("step") == 2:

        msg = text
        target = broadcast_state[user_id]["target"]

        if target == "ALL":
            success = 0
            for gid in group_data.keys():
                try:
                    await context.bot.send_message(chat_id=int(gid), text=msg)
                    success += 1
                except Exception as e:
                    print(f"Failed {gid}:", e)

            await update.message.reply_text(f"✅ Sent to {success} groups")
        else:
            try:
                await context.bot.send_message(chat_id=int(target), text=msg)
                await update.message.reply_text("✅ Broadcast sent")
            except Exception as e:
                await update.message.reply_text(f"❌ Failed: {e}")

        del broadcast_state[user_id]
        return

    # ===== TRANSACTION =====
    if not is_allowed(user_id, data):
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
        action = "Received"
    else:
        data["balance"] -= amount
        data["withdraw"] += amount
        data["withdraw_count"] += 1
        action = "Paid"

    rate = data.get("rate", 90.0)
    converted = amount / rate
    balance_converted = data["balance"] / rate

    save_data()

    await update.message.reply_text(f"""
📊 Overseas Customer Service

{action}: {amount:,.2f} INR
Converted: {converted:,.2f} {data['target_currency']}

------------------------------
Balance: {data['balance']:,.2f} INR
Balance: {balance_converted:,.2f} {data['target_currency']}

Total Deposit: {data['deposit']:,.2f}
Total Withdraw: {data['withdraw']:,.2f}

Total deposit count: {data['deposit_count']}
Total withdrawal count: {data['withdraw_count']}
Total count: {data['deposit_count'] + data['withdraw_count']}

Rate: 1 {data['target_currency']} = {rate} INR
""")

# ================= MAIN =================

def main():
    load_data()

    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("panel", panel))
    app_bot.add_handler(CommandHandler("adduser", add_user))
    app_bot.add_handler(CommandHandler("setcurrency", set_currency))
    app_bot.add_handler(CommandHandler("setrate", set_rate))

    app_bot.add_handler(CallbackQueryHandler(button_handler))

    # FIXED (no conflict now)
    app_bot.add_handler(MessageHandler(filters.ChatType.GROUPS, track_group))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    Thread(target=run_flask).start()
    app_bot.run_polling()

if __name__ == "__main__":
    main()
