import os
import json

API_KEY = "hRCKAlC4UbJvIrPUZ7XBX7aS6BajBfzumN5WRUnsfh6T8spehtGkuB4JDNiD7eCG"
API_SECRET = "lBzb7KCa9iUxWinn1zjUnkuvo9nIScQ6im1OKcTeZDvrlX3gfyzHGgDrtzBlalyx"

TELEGRAM_TOKEN = "7937694627:AAGnQsGktQwqZJn71meatf0bZPa-DJxTmgo"
TELEGRAM_CHAT_ID = "785878245"

SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

# Параметры риск-менеджмента
STOP_LOSS_PERCENT = 2      # 2%
TAKE_PROFIT_PERCENT = 6    # 6%

# Файлы хранения данных
BALANCE_FILE = "balance.txt"
SIGNALS_FILE = "signals.txt"
TRADES_FILE = "trades.txt"
SIGNALS_ENABLED_FILE = "signals_enabled.txt"  # Файл-флаг активации сигналов
OPEN_POSITIONS_FILE = "open_positions.json"

def get_balance():
    """Загружает баланс из файла (float)"""
    if os.path.exists(BALANCE_FILE):
        with open(BALANCE_FILE, "r") as f:
            try:
                return float(f.read().strip())
            except ValueError:
                return None
    return None

def set_balance(amount):
    """Сохраняет баланс в файл"""
    with open(BALANCE_FILE, "w") as f:
        f.write(str(amount))

def save_signal(signal):
    """Сохраняет сигнал в файл сигналов"""
    with open(SIGNALS_FILE, "a") as f:
        f.write(signal + "\n")

def save_trade(trade):
    """Сохраняет сделку в файл сделок"""
    with open(TRADES_FILE, "a") as f:
        f.write(trade + "\n")

def get_signals_history():
    """Читает историю сигналов (последние 10)"""
    if os.path.exists(SIGNALS_FILE):
        with open(SIGNALS_FILE, "r") as f:
            lines = f.readlines()
        if lines:
            return "".join(lines[-10:])
    return "История сигналов пуста."

def get_trades_history():
    """Читает историю сделок (последние 10)"""
    if os.path.exists(TRADES_FILE):
        with open(TRADES_FILE, "r") as f:
            lines = f.readlines()
        if lines:
            return "".join(lines[-10:])
    return "История сделок пуста."

def enable_signals():
    """Активирует выдачу сигналов, создавая файл-флаг"""
    with open(SIGNALS_ENABLED_FILE, "w") as f:
        f.write("1")

def is_signals_enabled():
    """Проверяет, активированы ли сигналы"""
    return os.path.exists(SIGNALS_ENABLED_FILE)

def load_positions():
    """Загружает открытые позиции из JSON-файла как список"""
    if os.path.exists(OPEN_POSITIONS_FILE):
        with open(OPEN_POSITIONS_FILE, "r") as f:
            try:
                positions = json.load(f)
                if isinstance(positions, list):
                    return positions
                else:
                    return []
            except:
                return []
    return []

def save_positions(positions):
    """Сохраняет список позиций в JSON-файл"""
    with open(OPEN_POSITIONS_FILE, "w") as f:
        json.dump(positions, f, indent=2)

def calc_sl_tp(side, entry):
    """Вычисляет стоп‑лосс и тейк‑профит на основе направления (BUY/SELL) и цены входа"""
    if side.upper() == "BUY":
        stop_loss = entry * (1 - STOP_LOSS_PERCENT / 100)
        take_profit = entry * (1 + TAKE_PROFIT_PERCENT / 100)
    else:  # SELL
        stop_loss = entry * (1 + STOP_LOSS_PERCENT / 100)
        take_profit = entry * (1 - TAKE_PROFIT_PERCENT / 100)
    return stop_loss, take_profit
