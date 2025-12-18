import asyncio
import requests
from typing import Dict

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ─────────── CONFIG ───────────
TELEGRAM_TOKEN = "7886615519:AAGlUXVxWw9lYRmk_P6sI3XfC__BOoBUMNw"
BINANCE_PRICE_URL = "https://api.binance.com/api/v3/ticker/price"

MAX_RESULTS = 20
MESSAGE_LIMIT = 4000
MIN_PERIOD = 0.1     # dakika
MIN_PERCENT = 0.01  # %

# ─────────── STATE ───────────
user_state: Dict[int, dict] = {}

# ─────────── BINANCE API ───────────
def get_binance_prices() -> Dict[str, float]:
    r = requests.get(BINANCE_PRICE_URL, timeout=10)
    r.raise_for_status()
    data = r.json()
    return {item["symbol"]: float(item["price"]) for item in data}

# ─────────── UTILS ───────────
async def send_long_message(bot, chat_id: int, text: str):
    for i in range(0, len(text), MESSAGE_LIMIT):
        await bot.send_message(chat_id, text[i:i + MESSAGE_LIMIT])

# ─────────── COMMANDS ───────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_state[chat_id] = {"step": "period"}

    await update.message.reply_text(
        "⏱ Periyot (dakika) giriniz\n"
        "Örnek: 1 | 0.5 | 0.3"
    )

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_state.pop(chat_id, None)
    await update.message.reply_text("🛑 Takip durduruldu.")

# ─────────── INPUT HANDLER ───────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    if chat_id not in user_state:
        return

    state = user_state[chat_id]

    # ⏱ PERIOD
    if state["step"] == "period":
        try:
            period = float(text)
            if period < MIN_PERIOD:
                raise ValueError

            state["period"] = period
            state["step"] = "percent"

            await update.message.reply_text(
                "📊 Yüzdelik değişim giriniz\n"
                "Örnek: 2 | 0.5 | 0.1"
            )
        except:
            await update.message.reply_text("❌ Geçerli bir periyot giriniz.")

    # 📈 PERCENT
    elif state["step"] == "percent":
        try:
            percent = float(text)
            if percent < MIN_PERCENT:
                raise ValueError

            state["percent"] = percent
            state["step"] = "running"

            await update.message.reply_text(
                f"🚀 Takip başladı\n"
                f"⏱ {state['period']} dk\n"
                f"📈 %{state['percent']}"
            )

            context.application.create_task(
                price_monitor(context, chat_id)
            )

        except:
            await update.message.reply_text("❌ Geçerli bir yüzde giriniz.")

# ─────────── CORE LOGIC ───────────
async def price_monitor(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    period = user_state[chat_id]["period"]
    percent = user_state[chat_id]["percent"]

    while chat_id in user_state:
        try:
            start_prices = get_binance_prices()
            await asyncio.sleep(period * 60)
            end_prices = get_binance_prices()

            changes = []

            for symbol, old in start_prices.items():
                new = end_prices.get(symbol)
                if not new or old <= 0:
                    continue

                change = ((new - old) / old) * 100
                if abs(change) >= percent:
                    changes.append((symbol, change))

            if changes:
                changes.sort(key=lambda x: abs(x[1]), reverse=True)
                changes = changes[:MAX_RESULTS]

                lines = [
                    f"{'📈' if c > 0 else '📉'} {s}: %{c:.2f}"
                    for s, c in changes
                ]

                message = "🔥 Değişim olan coinler:\n\n" + "\n".join(lines)
                await send_long_message(context.bot, chat_id, message)

                user_state.pop(chat_id, None)
                break

            else:
                await context.bot.send_message(
                    chat_id,
                    "😴 Değişim yok, tekrar kontrol ediliyor..."
                )

        except Exception as e:
            await context.bot.send_message(
                chat_id,
                f"⚠️ Geçici hata oluştu:\n{e}"
            )
            await asyncio.sleep(5)

# ─────────── MAIN (ASYNC ŞART) ───────────
async def main():
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot çalışıyor")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
