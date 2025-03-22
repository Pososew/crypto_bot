import time
import multiprocessing
import pandas as pd
import ta
from binance.client import Client
from config import (
    API_KEY, API_SECRET, SYMBOLS,
    STOP_LOSS_PERCENT, TAKE_PROFIT_PERCENT,
    load_user_data, get_trading_mode, calc_sl_tp, set_balance, get_balance, load_positions, save_positions
)
from telegram_bot import send_telegram_message
from telegram_commands import run_telegram_bot

client = Client(API_KEY, API_SECRET)

def get_data(symbol, interval="1m", lookback=100):
    klines = client.get_klines(symbol=symbol, interval=interval, limit=lookback)
    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_volume', 'taker_buy_quote_volume', 'ignore'
    ])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)
    return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]

def apply_indicators(df):
    df['SMA_50'] = df['close'].rolling(window=50).mean()
    df['SMA_200'] = df['close'].rolling(window=200).mean()
    df['RSI'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
    df['ATR'] = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close'], window=14).average_true_range()
    return df

def check_trade_signal_extended(df):
    latest = df.iloc[-1]
    rsi_buy = latest['RSI'] < 30
    rsi_sell = latest['RSI'] > 70

    sma50_buy = latest['close'] > latest['SMA_50']
    sma50_sell = latest['close'] < latest['SMA_50']
    sma200_buy = latest['close'] > latest['SMA_200']
    sma200_sell = latest['close'] < latest['SMA_200']

    avg_volume = df['volume'].rolling(window=20).mean().iloc[-1]
    volume_buy = latest['volume'] > 1.5 * avg_volume
    volume_sell = latest['volume'] > 1.5 * avg_volume

    recent_max = df['close'].rolling(window=20).max().iloc[-1]
    resistance_buy = latest['close'] < 0.98 * recent_max
    resistance_sell = latest['close'] > 0.98 * recent_max

    atr = df['ATR'].iloc[-1]
    atr_ratio = atr / latest['close']
    atr_threshold = 0.01
    atr_condition = (atr_ratio > atr_threshold)

    buy_conditions = sum([rsi_buy, sma50_buy, sma200_buy, volume_buy, resistance_buy, atr_condition])
    sell_conditions = sum([rsi_sell, sma50_sell, sma200_sell, volume_sell, resistance_sell, atr_condition])
    required_confirmations = 3

    if buy_conditions >= required_confirmations:
        return "BUY"
    elif sell_conditions >= required_confirmations:
        return "SELL"
    else:
        return None

def get_timeframe_data(symbol, timeframe, lookback=2):
    klines = client.get_klines(symbol=symbol, interval=timeframe, limit=lookback)
    df = pd.DataFrame(klines, columns=[
        'timestamp','open','high','low','close','volume',
        'close_time','quote_asset_volume','number_of_trades',
        'taker_buy_base_volume','taker_buy_quote_volume','ignore'
    ])
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)
    return df

def start_telegram_bot_in_process():
    run_telegram_bot()

if __name__ == "__main__":
    print("DEBUG: bot.py запущен...")
    try:
        print("Ping to Binance:", client.ping())
    except Exception as e:
        print("Ошибка при ping:", e)
    
    telegram_process = multiprocessing.Process(target=start_telegram_bot_in_process)
    telegram_process.start()
    
    interval_seconds = 300  # 5 минут
    from config import get_trading_mode
    mode = get_trading_mode("dummy")  # В данном случае для глобального анализа можно передать dummy, или использовать индивидуальный режим в цикле ниже.
    if mode == "scalp":
        exit_timeframe = "15m"
    else:
        exit_timeframe = "1h"
    print(f"DEBUG: Торговый режим: {mode}. Для входа анализ по 1m, для выхода по {exit_timeframe}. Интервал: {interval_seconds} секунд.")
    
    while True:
        print("DEBUG: Начало цикла анализа рынка для всех пользователей...")
        data = load_user_data()
        chat_ids = set(data.get("balances", {}).keys())
        for chat_id in chat_ids:
            user_signals = []
            # Получаем торговый режим для пользователя
            user_mode = get_trading_mode(chat_id)
            if user_mode == "scalp":
                timeframe = "15m"
            else:
                timeframe = "1h"
            positions = load_positions(chat_id)
            for symbol in SYMBOLS:
                open_pos = None
                for pos in positions:
                    if pos["coin"].upper() == symbol.upper():
                        open_pos = pos
                        break
                if open_pos:
                    side = open_pos["side"].upper()
                    df_exit = get_timeframe_data(symbol, timeframe, lookback=2)
                    last_candle = df_exit.iloc[-1]
                    open_price = last_candle["open"]
                    close_price = last_candle["close"]
                    diff = (close_price - open_price) / open_price
                    reversal = False
                    if side == "SELL" and diff > 0.003:
                        reversal = True
                    elif side == "BUY" and diff < -0.003:
                        reversal = True
                    df_recent = get_timeframe_data(symbol, timeframe, lookback=6)
                    if side == "BUY":
                        max_high = df_recent["high"].max()
                        if (max_high - close_price) / max_high >= 0.003:
                            reversal = True
                    else:
                        min_low = df_recent["low"].min()
                        if (close_price - min_low) / min_low >= 0.003:
                            reversal = True
                    if reversal:
                        stake = open_pos.get("stake", 0)
                        entry = open_pos["entry"]
                        leverage = open_pos.get("leverage", 1)
                        if side == "BUY":
                            pct = (close_price - entry) / entry
                        else:
                            pct = (entry - close_price) / entry
                        profit_loss = stake * pct * leverage
                        current_balance = get_balance(chat_id)
                        new_balance = current_balance + profit_loss
                        set_balance(chat_id, new_balance)
                        positions = load_positions(chat_id)
                        positions = [p for p in positions if p["coin"].upper() != symbol.upper()]
                        save_positions(chat_id, positions)
                        user_signals.append(f"Позиция на {symbol} закрыта. Прибыль/убыток: {profit_loss:+.2f} USDT. Новый баланс: {new_balance:.2f} USDT.")
                    else:
                        user_signals.append(f"Позиция на {symbol} стабильна.")
                else:
                    df_entry = get_data(symbol, interval="1m", lookback=100)
                    df_entry = apply_indicators(df_entry)
                    signal = check_trade_signal_extended(df_entry)
                    if signal:
                        entry_price = df_entry.iloc[-1]["close"]
                        stop_loss, take_profit = calc_sl_tp(signal, entry_price)
                        user_signals.append(
                            f"Вход: {symbol} – {signal} сигнал.\nЦена входа: {entry_price:.2f}, SL: {stop_loss:.2f}, TP: {take_profit:.2f}."
                        )
                    else:
                        user_signals.append(f"На монету {symbol} нет хороших входов в сделку.")
            # Если все сигналы содержат "нет хороших входов" или "стабильна", отправляем одно агрегированное сообщение
            if all(("нет хороших входов" in s or "стабильна" in s) for s in user_signals):
                aggregated_message = "Сейчас нет хороших входов в сделку 😊"
            else:
                aggregated_message = "\n".join(user_signals)
            send_telegram_message(aggregated_message, chat_id)
            print(f"Отправлено сообщение для chat_id {chat_id}:")
            print(aggregated_message)
        time.sleep(interval_seconds)
        print("Ping:", client.ping())
