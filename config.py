import os
import json

API_KEY = "hRCKAlC4UbJvIrPUZ7XBX7aS6BajBfzumN5WRUnsfh6T8spehtGkuB4JDNiD7eCG"
API_SECRET = "lBzb7KCa9iUxWinn1zjUnkuvo9nIScQ6im1OKcTeZDvrlX3gfyzHGgDrtzBlalyx"

TELEGRAM_TOKEN = "7937694627:AAGnQsGktQwqZJn71meatf0bZPa-DJxTmgo"
TELEGRAM_CHAT_ID = "785878245"

# Добавлены монеты, по которым можно торговать
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "LTCUSDT"]

# Параметры риск-менеджмента
STOP_LOSS_PERCENT = 2      # 2%
TAKE_PROFIT_PERCENT = 6    # 6%

# Файлы хранения данных
BALANCE_FILE = "balance.txt"
SIGNALS_FILE = "signals.txt"
TRADES_FILE = "trades.txt"
SIGNALS_ENABLED_FILE = "signals_enabled.txt"  # Флаг активации сигналов
OPEN_POSITIONS_FILE = "open_positions.json"

def get_balance():
    if os.path.exists(BALANCE_FILE):
        with open(BALANCE_FILE, "r") as f:
            try:
                return float(f.read().strip())
            except ValueError:
                return None
    return None

def set_balance(amount):
    with open(BALANCE_FILE, "w") as f:
        f.write(str(amount))

def save_signal(signal):
    with open(SIGNALS_FILE, "a") as f:
        f.write(signal + "\n")

def save_trade(trade):
    with open(TRADES_FILE, "a") as f:
        f.write(trade + "\n")

def get_signals_history():
    if os.path.exists(SIGNALS_FILE):
        with open(SIGNALS_FILE, "r") as f:
            lines = f.readlines()
        if lines:
            return "".join(lines[-10:])
    return "История сигналов пуста."

def get_trades_history():
    if os.path.exists(TRADES_FILE):
        with open(TRADES_FILE, "r") as f:
            lines = f.readlines()
        if lines:
            return "".join(lines[-10:])
    return "История сделок пуста."

def enable_signals():
    with open(SIGNALS_ENABLED_FILE, "w") as f:
        f.write("1")

def is_signals_enabled():
    return os.path.exists(SIGNALS_ENABLED_FILE)

def load_positions():
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
    with open(OPEN_POSITIONS_FILE, "w") as f:
        json.dump(positions, f, indent=2)

def calc_sl_tp(side, entry):
    if side.upper() == "BUY":
        stop_loss = entry * (1 - STOP_LOSS_PERCENT / 100)
        take_profit = entry * (1 + TAKE_PROFIT_PERCENT / 100)
    else:
        stop_loss = entry * (1 + STOP_LOSS_PERCENT / 100)
        take_profit = entry * (1 - TAKE_PROFIT_PERCENT / 100)
    return stop_loss, take_profit

# --- Новая функциональность: выбор торгового режима ---
TRADING_MODE_FILE = "trading_mode.txt"

def get_trading_mode():
    if os.path.exists(TRADING_MODE_FILE):
        with open(TRADING_MODE_FILE, "r") as f:
            mode = f.read().strip()
        if mode in ["long", "scalp"]:
            return mode
    return "long"

def set_trading_mode(mode):
    if mode in ["long", "scalp"]:
        with open(TRADING_MODE_FILE, "w") as f:
            f.write(mode)
