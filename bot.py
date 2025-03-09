import time
import multiprocessing
import pandas as pd
import ta
from binance.client import Client
from config import (
    API_KEY, API_SECRET, SYMBOLS,
    save_signal, is_signals_enabled,
    STOP_LOSS_PERCENT, TAKE_PROFIT_PERCENT
)
from telegram_bot import send_telegram_message
from telegram_commands import run_telegram_bot

client = Client(API_KEY, API_SECRET)

def get_data(symbol, interval="1h", lookback=100):
    klines = client.get_klines(symbol=symbol, interval=interval, limit=lookback)
    df = pd.DataFrame(klines, columns=[
        'timestamp',              
        'open',                   
        'high',                   
        'low',                    
        'close',                  
        'volume',                 
        'close_time',             
        'quote_asset_volume',     
        'number_of_trades',       
        'taker_buy_base_volume',  
        'taker_buy_quote_volume', 
        'ignore'                  
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
    """
    Расширенная логика проверки сигналов:
      1. RSI: <30 для покупки, >70 для продажи.
      2. SMA_50: цена выше SMA_50 для покупки, ниже для продажи.
      3. SMA_200: цена выше SMA_200 для покупки, ниже для продажи.
      4. Объёмы: текущий объём >1.5 * среднего объёма за 20 свечей.
      5. Уровень сопротивления: для покупки цена < 0.98 * недавнего макс, для продажи > 0.98 * недавнего макс.
      6. ATR: (ATR/close) > 1% для достаточной волатильности.
      
    Сигнал, если минимум 3 из 6 условий совпадают.
    """
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
    atr_threshold = 0.01  # 1%
    atr_condition = (atr_ratio > atr_threshold)

    buy_conditions = sum([
        rsi_buy,
        sma50_buy,
        sma200_buy,
        volume_buy,
        resistance_buy,
        atr_condition
    ])
    sell_conditions = sum([
        rsi_sell,
        sma50_sell,
        sma200_sell,
        volume_sell,
        resistance_sell,
        atr_condition
    ])

    required_confirmations = 3

    if buy_conditions >= required_confirmations:
        return "BUY"
    elif sell_conditions >= required_confirmations:
        return "SELL"
    else:
        return None

def start_telegram_bot_in_process():
    """Запускает Telegram-бот в отдельном процессе."""
    run_telegram_bot()

if __name__ == "__main__":
    print("DEBUG: bot.py запущен...")
    try:
        print("Ping to Binance:", client.ping())
    except Exception as e:
        print("Ошибка при ping:", e)
    
    telegram_process = multiprocessing.Process(target=start_telegram_bot_in_process)
    telegram_process.start()
    
    print("DEBUG: Перед while True. Сейчас запустим цикл...")
    interval_seconds = 300  # Каждые 5 минут
    while True:
        print("DEBUG: Начало цикла while True...")
        if not is_signals_enabled():
            print("Сигналы не активированы. Ожидайте нажатия /start в Telegram...")
        else:
            signals_found = False
            for symbol in SYMBOLS:
                df = get_data(symbol)
                df = apply_indicators(df)
                signal = check_trade_signal_extended(df)
                if signal:
                    signals_found = True
                    entry_price = df.iloc[-1]['close']
                    if signal == "BUY":
                        stop_loss = entry_price * (1 - STOP_LOSS_PERCENT / 100)
                        take_profit = entry_price * (1 + TAKE_PROFIT_PERCENT / 100)
                    else:  # SELL
                        stop_loss = entry_price * (1 + STOP_LOSS_PERCENT / 100)
                        take_profit = entry_price * (1 - TAKE_PROFIT_PERCENT / 100)
                    
                    save_signal(f"{symbol}: {signal}")
                    message = (
                        f"📊 {symbol}: {signal}\n"
                        f"Цена входа: {entry_price:.2f}\n"
                        f"Стоп‑лосс ({STOP_LOSS_PERCENT}%): {stop_loss:.2f}\n"
                        f"Тейк‑профит ({TAKE_PROFIT_PERCENT}%): {take_profit:.2f}"
                    )
                    send_telegram_message(message)
                    print(f"Сигнал для {symbol}: {signal}")
                else:
                    print(f"Нет сигнала для {symbol}")
            if not signals_found:
                send_telegram_message("⏳ Сигналов пока нет")
                print("⏳ Сигналов пока нет")
        time.sleep(interval_seconds)
        print("Ping:", client.ping())
