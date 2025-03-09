import asyncio
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from config import (
    TELEGRAM_TOKEN,
    get_balance, set_balance,
    get_signals_history, get_trades_history,
    save_trade, enable_signals,
    load_positions, save_positions, calc_sl_tp
)
from binance.client import Client
import pandas as pd
import ta

# Словари для отслеживания состояний
user_trade_mode = {}         # Для сделок (прибыль/убыток)
position_creation = {}       # Для создания позиции

# Функция для получения RSI для монеты (использует последние 100 свечей)
def get_rsi_for_coin(coin):
    from config import API_KEY, API_SECRET
    client = Client(API_KEY, API_SECRET)
    candles = client.get_klines(symbol=coin, interval="1m", limit=100)
    df = pd.DataFrame(candles, columns=[
        'timestamp','open','high','low','close','volume','close_time',
        'quote_asset_volume','number_of_trades','taker_buy_base_volume',
        'taker_buy_quote_volume','ignore'
    ])
    df['close'] = pd.to_numeric(df['close'])
    rsi = ta.momentum.RSIIndicator(df['close'], window=14).rsi().iloc[-1]
    return rsi

async def start(update: Update, context: CallbackContext):
    """Команда /start: приветствие, активация сигналов и инструкции"""
    enable_signals()  # Активируем сигналы
    instructions = (
        "Привет! Я криптобот для поиска торговых сигналов.\n\n"
        "Доступные действия:\n"
        " • 🚀 'Установить баланс' – введите сумму в USDT.\n"
        " • 💰 'Посмотреть баланс' – узнайте текущий баланс.\n"
        " • 📊 'История сигналов' – последние 10 сигналов.\n"
        " • 📜 'История сделок' – последние 10 сделок.\n"
        " • ✅ 'Добавить прибыльную сделку' или ❌ 'Добавить убыточную сделку' – обновите баланс сделкой.\n"
        " • ➕ 'Добавить позицию' – сообщите о входе в сделку (монета, BUY/SELL, плечо, цена входа).\n"
        " • 📈 'Мои позиции' – список всех позиций с процентным изменением от цены входа.\n"
        " • ❌ 'Удалить позицию' – удалите позицию по номеру.\n\n"
        "Следуйте подсказкам, удачи!"
    )
    keyboard = [
        ["🚀 Установить баланс", "💰 Посмотреть баланс"],
        ["📊 История сигналов", "📜 История сделок"],
        ["✅ Добавить прибыльную сделку", "❌ Добавить убыточную сделку"],
        ["➕ Добавить позицию", "📈 Мои позиции"],
        ["❌ Удалить позицию"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(instructions, reply_markup=reply_markup)

async def ask_balance(update: Update, context: CallbackContext):
    context.user_data["awaiting_balance"] = True
    await update.message.reply_text("💵 Введите сумму баланса на сегодня (в USDT):")

async def set_user_balance(update: Update, context: CallbackContext):
    try:
        amount = float(update.message.text)
        set_balance(amount)
        context.user_data["awaiting_balance"] = False
        await update.message.reply_text(f"✅ Баланс установлен: {amount:.2f} USDT")
    except ValueError:
        await update.message.reply_text("⚠️ Введите корректную сумму!")

async def show_balance(update: Update, context: CallbackContext):
    balance = get_balance()
    if balance is not None:
        await update.message.reply_text(f"💰 Текущий баланс: {balance:.2f} USDT")
    else:
        await update.message.reply_text("⚠️ Баланс не установлен.")

async def show_signals(update: Update, context: CallbackContext):
    history = get_signals_history()
    await update.message.reply_text(f"📊 История сигналов:\n{history}")

async def show_trades(update: Update, context: CallbackContext):
    history = get_trades_history()
    await update.message.reply_text(f"📜 История сделок:\n{history}")

async def ask_trade(update: Update, context: CallbackContext):
    global user_trade_mode
    chat_id = update.message.chat_id
    text = update.message.text.lower()
    if "прибы" in text:
        user_trade_mode[chat_id] = "profit"
        await update.message.reply_text("Введите сумму прибыли (например: 50):")
    elif "убыт" in text:
        user_trade_mode[chat_id] = "loss"
        await update.message.reply_text("Введите сумму убытка (например: 30):")

async def save_user_trade(update: Update, context: CallbackContext):
    global user_trade_mode
    chat_id = update.message.chat_id
    if chat_id not in user_trade_mode:
        return
    try:
        trade_amount = float(update.message.text.strip())
        current_balance = get_balance()
        if current_balance is None:
            await update.message.reply_text("⚠️ Баланс не установлен!")
            del user_trade_mode[chat_id]
            return
        if user_trade_mode[chat_id] == "profit":
            new_balance = current_balance + trade_amount
            trade_type = "ПРИБЫЛЬ"
        else:
            new_balance = current_balance - trade_amount
            trade_type = "УБЫТОК"
        save_trade(f"{trade_type}: {trade_amount:.2f} USDT")
        set_balance(new_balance)
        del user_trade_mode[chat_id]
        await update.message.reply_text(
            f"✅ Сделка записана: {trade_type} {trade_amount:.2f} USDT\nНовый баланс: {new_balance:.2f} USDT"
        )
    except ValueError:
        await update.message.reply_text("⚠️ Введите корректную сумму!")

# ==== Работа с позициями ====
# При добавлении позиции проверяем, если по монете уже есть открытая позиция
async def add_position(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    position_creation[chat_id] = {"step": 1}
    await update.message.reply_text("Укажите монету для новой позиции (например: BTCUSDT):")

async def set_position_coin(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    coin = update.message.text.strip().upper()
    # Проверяем, есть ли уже открытая позиция по этой монете
    from config import load_positions
    positions = load_positions()
    for pos in positions:
        if pos.get("coin", "").upper() == coin:
            await update.message.reply_text(f"По монете {coin} у вас уже открыта позиция.")
            if chat_id in position_creation:
                del position_creation[chat_id]
            return
    # Если позиции нет, продолжаем процесс создания
    position_creation[chat_id] = {"step": 2, "coin": coin}
    await update.message.reply_text("Введите направление (BUY или SELL):")

async def set_position_side(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    side = update.message.text.strip().upper()
    if side not in ["BUY", "SELL"]:
        await update.message.reply_text("⚠️ Укажите BUY или SELL!")
        return
    position_creation[chat_id]["side"] = side
    position_creation[chat_id]["step"] = 3
    await update.message.reply_text("Введите плечо (0 если без плеча, или 2, 3, 5, 10):")

async def set_position_leverage(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    try:
        leverage = float(update.message.text.strip())
        allowed_leverages = [0, 2, 3, 5, 10]
        if leverage not in allowed_leverages:
            await update.message.reply_text("⚠️ Введите корректное плечо (0, 2, 3, 5, 10):")
            return
        position_creation[chat_id]["leverage"] = leverage
        position_creation[chat_id]["step"] = 4
        await update.message.reply_text("Введите цену входа (например: 100):")
    except ValueError:
        await update.message.reply_text("⚠️ Введите корректное число для плеча!")

async def set_position_entry(update: Update, context: CallbackContext):
    from config import load_positions, save_positions
    chat_id = update.message.chat_id
    try:
        entry_price = float(update.message.text)
        coin = position_creation[chat_id]["coin"]
        side = position_creation[chat_id]["side"]
        leverage = position_creation[chat_id].get("leverage", 0)
        stop_loss, take_profit = calc_sl_tp(side, entry_price)
        positions = load_positions()
        new_pos = {
            "coin": coin,
            "side": side,
            "entry": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "leverage": leverage
        }
        positions.append(new_pos)
        save_positions(positions)
        msg = (
            f"✅ Позиция добавлена:\nМонета: {coin}\nНаправление: {side}\nЦена входа: {entry_price:.2f}\n"
            f"Плечо: {leverage}x\nСтоп‑лосс: {stop_loss:.2f}\nТейк‑профит: {take_profit:.2f}"
        )
        await update.message.reply_text(msg)
    except ValueError:
        await update.message.reply_text("⚠️ Введите корректную цену входа!")
    if chat_id in position_creation:
        del position_creation[chat_id]

async def show_positions(update: Update, context: CallbackContext):
    from config import load_positions
    positions = load_positions()
    if not positions:
        await update.message.reply_text("Нет открытых позиций.")
        return
    from config import API_KEY, API_SECRET
    from binance.client import Client
    client = Client(API_KEY, API_SECRET)
    msg = "📈 Мои позиции:\n"
    for i, pos in enumerate(positions, start=1):
        coin = pos["coin"]
        side = pos["side"].upper()
        entry = pos["entry"]
        try:
            ticker = client.get_symbol_ticker(symbol=coin)
            current_price = float(ticker["price"])
        except Exception as e:
            msg += f"{i}. {coin}: Ошибка получения цены\n"
            continue
        if side == "BUY":
            percent_change = ((current_price - entry) / entry) * 100
        else:
            percent_change = ((entry - current_price) / entry) * 100
        status = f"{percent_change:+.1f}%"
        msg += (
            f"{i}. {coin} ({side})\n"
            f"   Цена входа: {entry:.2f}\n"
            f"   Текущая цена: {current_price:.2f}\n"
            f"   Изменение от входа: {status}\n"
            f"   (Плечо: {pos.get('leverage', 0)}x, SL = {pos['stop_loss']:.2f}, TP = {pos['take_profit']:.2f})\n"
        )
    await update.message.reply_text(msg)

async def delete_position(update: Update, context: CallbackContext):
    from config import load_positions
    positions = load_positions()
    if not positions:
        await update.message.reply_text("Нет открытых позиций для удаления.")
        return
    msg = "Введите номер позиции для удаления:\n"
    for i, pos in enumerate(positions, start=1):
        msg += f"{i}. {pos['coin']} {pos['side']} по {pos['entry']:.2f}\n"
    context.user_data["awaiting_delete"] = True
    await update.message.reply_text(msg)

async def confirm_delete_position(update: Update, context: CallbackContext):
    from config import load_positions, save_positions
    try:
        index = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("⚠️ Введите корректный номер позиции!")
        return
    positions = load_positions()
    if index < 1 or index > len(positions):
        await update.message.reply_text("⚠️ Позиция с таким номером не найдена!")
    else:
        pos = positions.pop(index - 1)
        save_positions(positions)
        await update.message.reply_text(f"✅ Позиция {pos['coin']} {pos['side']} по {pos['entry']:.2f} удалена.")
    context.user_data["awaiting_delete"] = False

async def handle_text(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    if context.user_data.get("awaiting_balance"):
        await set_user_balance(update, context)
    elif context.user_data.get("awaiting_delete"):
        await confirm_delete_position(update, context)
    elif chat_id in user_trade_mode:
        await save_user_trade(update, context)
    elif chat_id in position_creation:
        step = position_creation[chat_id]["step"]
        if step == 1:
            await set_position_coin(update, context)
        elif step == 2:
            await set_position_side(update, context)
        elif step == 3:
            await set_position_leverage(update, context)
        elif step == 4:
            await set_position_entry(update, context)

def run_telegram_bot():
    from telegram.ext import Application
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("🚀 Установить баланс"), ask_balance))
    app.add_handler(MessageHandler(filters.Regex("💰 Посмотреть баланс"), show_balance))
    app.add_handler(MessageHandler(filters.Regex("📊 История сигналов"), show_signals))
    app.add_handler(MessageHandler(filters.Regex("📜 История сделок"), show_trades))
    app.add_handler(MessageHandler(filters.Regex("✅ Добавить прибыльную сделку"), ask_trade))
    app.add_handler(MessageHandler(filters.Regex("❌ Добавить убыточную сделку"), ask_trade))
    app.add_handler(MessageHandler(filters.Regex("➕ Добавить позицию"), add_position))
    app.add_handler(MessageHandler(filters.Regex("📈 Мои позиции"), show_positions))
    app.add_handler(MessageHandler(filters.Regex("❌ Удалить позицию"), delete_position))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    print("Telegram-бот запущен...")
    app.run_polling()
