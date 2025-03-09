import time
import multiprocessing
import pandas as pd
import ta
from binance.client import Client
from config import (
    API_KEY, API_SECRET, SYMBOLS,
    save_signal, is_signals_enabled,
    STOP_LOSS_PERCENT, TAKE_PROFIT_PERCENT,
    load_positions
)
from telegram_bot import send_telegram_message
from telegram_commands import run_telegram_bot

client = Client(API_KEY, API_SECRET)

def get_data(symbol, interval="1m", lookback=100):
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
    Логика для новых сделок (не для открытых позиций):
      - Проверяем условия по RSI, SMA, объёму, уровню сопротивления и ATR.
      - Если минимум 3 из 6 условий совпадают, возвращаем сигнал BUY или SELL.
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

def get_hourly_data(symbol, interval="1h", lookback=6):
    """Получаем последние 'lookback' 1h свечей для анализа максимума/минимума"""
    klines = client.get_klines(symbol=symbol, interval=interval, limit=lookback)
    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time','quote_asset_volume','number_of_trades',
        'taker_buy_base_volume','taker_buy_quote_volume','ignore'
    ])
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
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
    
    print("DEBUG: Перед основным циклом проверки позиций...")
    # Анализируем позиции на 1h таймфрейме, запускаем каждые 5 минут.
    interval_seconds = 300
    while True:
        print("DEBUG: Начало цикла проверки позиций...")
        if not is_signals_enabled():
            print("Сигналы не активированы. Ожидаем /start в Telegram...")
        else:
            positions = load_positions()
            for symbol in SYMBOLS:
                # Проверяем, есть ли открытая позиция для данного символа
                open_pos = None
                for pos in positions:
                    if pos["coin"].upper() == symbol.upper():
                        open_pos = pos
                        break
                if open_pos is None:
                    send_telegram_message(f"Сейчас на монету {symbol} нет открытых позиций.")
                    print(f"Нет открытой позиции для {symbol}")
                else:
                    side = open_pos["side"].upper()
                    # Получаем 1h свечи для анализа разворота (последняя свеча)
                    df_hour = get_hourly_data(symbol, interval="1h", lookback=2)
                    last_candle = df_hour.iloc[-1]
                    open_price = last_candle['open']
                    close_price = last_candle['close']
                    diff = (close_price - open_price) / open_price
                    reversal = False
                    if side == "SELL" and diff > 0.003:
                        reversal = True
                        msg = f"Сейчас лучше закрыть позицию, так как цена развернулась вверх на монете {symbol}."
                    elif side == "BUY" and diff < -0.003:
                        reversal = True
                        msg = f"Сейчас лучше закрыть позицию, так как цена развернулась вниз на монете {symbol}."
                    
                    # Дополнительно анализируем максимальное/минимальное значение за последние 6 часов
                    df_recent = get_hourly_data(symbol, interval="1h", lookback=6)
                    if side == "BUY":
                        max_high = df_recent['high'].max()
                        # Если текущая цена значительно ниже максимума (например, более 0.3% ниже)
                        if (max_high - close_price) / max_high >= 0.003:
                            reversal = True
                            msg = f"Ваша открытая позиция на монете {symbol} достигла своего максимума. Советую закрыть позицию."
                    else:  # SELL
                        min_low = df_recent['low'].min()
                        if (close_price - min_low) / min_low >= 0.003:
                            reversal = True
                            msg = f"Ваша открытая позиция на монете {symbol} достигла своего минимума. Советую закрыть позицию."
                    
                    if reversal:
                        send_telegram_message(msg)
                        print(msg)
                    else:
                        print(f"Позиция по {symbol} стабильна.")
        time.sleep(interval_seconds)
        print("Ping:", client.ping())
