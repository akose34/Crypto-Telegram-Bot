import asyncio
import requests
from typing import Dict
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ───────── CONFIG ─────────
TELEGRAM_TOKEN = "7886615519:AAGlUXVxWw9lYRmk_P6sI3XfC__BOoBUMNw"
BINANCE_URL = "https://api.binance.com/api/v3/ticker/price"

MIN_PERIOD = 0.1      # dakika
MIN_PERCENT = 0.01
MAX_RESULTS = 20
MSG_LIMIT = 4000

user_state: Dict[int, dict] = {}

# ───────── BINANCE ─────────
def get_prices():
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; CryptoTelegramBot/1.0)"
    }

    r = requests.get(
        BINANCE_URL,
        headers=headers,
        timeout=10
    )
    r.raise_for_status()

    return {x["symbol"]: float(x["price"]) for x in r.json()}


# ───────── UTILS ─────────
async def send_long(bot, chat_id, text):
    for i in range(0, len(text), MSG_LIMIT):
        await bot.send_message(chat_id, text[i:i+MSG_LIMIT])

# ───────── COMMANDS ─────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_state[chat_id] = {"step": "period"}
    await update.message.reply_text(
        "⏱ Periyot gir (dk)\nÖrnek: 1 | 0.5 | 0.3"
    )

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_state.pop(update.effective_chat.id, None)
    await update.message.reply_text("🛑 Takip durduruldu")

# ───────── MESSAGE FLOW ─────────
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in user_state:
        return

    state = user_state[chat_id]
    text = update.message.text.strip()

    try:
        value = float(text)
    except:
        await update.message.reply_text("❌ Sayı gir")
        return

    if state["step"] == "period":
        if value < MIN_PERIOD:
            await update.message.reply_text("❌ Çok küçük")
            return
        state["period"] = value
        state["step"] = "percent"
        await update.message.reply_text("📈 Yüzde gir (örn: 0.5 | 1)")

    elif state["step"] == "percent":
        if value < MIN_PERCENT:
            await update.message.reply_text("❌ Çok küçük")
            return
        state["percent"] = value
        state["step"] = "running"

        await update.message.reply_text("🚀 Takip başladı")
        context.application.create_task(monitor(context, chat_id))

# ───────── CORE ─────────
async def monitor(context, chat_id):
    period = user_state[chat_id]["period"]
    percent = user_state[chat_id]["percent"]

    while chat_id in user_state:
        try:
            start = get_prices()
            await asyncio.sleep(period * 60)
            end = get_prices()

            changes = []
            for s, old in start.items():
                new = end.get(s)
                if not new or old <= 0:
                    continue
                diff = ((new - old) / old) * 100
                if abs(diff) >= percent:
                    changes.append((s, diff))

            if changes:
                changes.sort(key=lambda x: abs(x[1]), reverse=True)
                msg = "🔥 Değişim:\n\n" + "\n".join(
                    f"{'📈' if c>0 else '📉'} {s}: %{c:.2f}"
                    for s, c in changes[:MAX_RESULTS]
                )
                await send_long(context.bot, chat_id, msg)
                user_state.pop(chat_id, None)
                return
            else:
                await context.bot.send_message(chat_id, "😴 Değişim yok")

        except Exception as e:
            await context.bot.send_message(chat_id, f"⚠️ Hata: {e}")
            await asyncio.sleep(5)

# ───────── MAIN ─────────
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    print("🤖 Bot çalışıyor")
    app.run_polling()

if __name__ == "__main__":
    main()
