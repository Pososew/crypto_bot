import os
import json
from dotenv import load_dotenv

load_dotenv()  # Загружает переменные из .env, если он существует

# Загружаем секреты из окружения
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
# В многопользовательском режиме TELEGRAM_CHAT_ID не используется

# Список монет для торговли
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "LTCUSDT", "DOTUSDT", "AAVEUSDT", "LINKUSDT"]

# Параметры риск-менеджмента
STOP_LOSS_PERCENT = 2      # 2%
TAKE_PROFIT_PERCENT = 6    # 6%

# Файл для хранения данных пользователей
USER_DATA_FILE = "user_data.json"

def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, "r") as f:
            try:
                data = json.load(f)
            except Exception:
                data = {}
    else:
        data = {}
    # Обеспечиваем наличие необходимых разделов
    if "balances" not in data:
        data["balances"] = {}
    if "positions" not in data:
        data["positions"] = {}
    if "trades" not in data:
        data["trades"] = {}
    if "trading_modes" not in data:
        data["trading_modes"] = {}
    return data

def save_user_data(data):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_balance(chat_id):
    data = load_user_data()
    return data["balances"].get(str(chat_id), 0)

def set_balance(chat_id, amount):
    data = load_user_data()
    data["balances"][str(chat_id)] = amount
    save_user_data(data)

def load_positions(chat_id):
    data = load_user_data()
    return data["positions"].get(str(chat_id), [])

def save_positions(chat_id, positions):
    data = load_user_data()
    data["positions"][str(chat_id)] = positions
    save_user_data(data)

def load_trades(chat_id):
    data = load_user_data()
    return data["trades"].get(str(chat_id), [])

def save_trade(chat_id, trade):
    data = load_user_data()
    if str(chat_id) not in data["trades"]:
        data["trades"][str(chat_id)] = []
    data["trades"][str(chat_id)].append(trade)
    save_user_data(data)

def get_signals_history():
    SIGNALS_FILE = "signals.txt"
    if os.path.exists(SIGNALS_FILE):
        with open(SIGNALS_FILE, "r") as f:
            lines = f.readlines()
        if lines:
            return "".join(lines[-10:])
    return "История сигналов пуста."

def get_trades_history(chat_id):
    trades = load_trades(chat_id)
    if trades:
        return "\n".join(trades[-10:])
    return "История сделок пуста."

def enable_signals():
    SIGNALS_ENABLED_FILE = "signals_enabled.txt"
    with open(SIGNALS_ENABLED_FILE, "w") as f:
        f.write("1")

def is_signals_enabled():
    SIGNALS_ENABLED_FILE = "signals_enabled.txt"
    return os.path.exists(SIGNALS_ENABLED_FILE)

def calc_sl_tp(side, entry):
    if side.upper() == "BUY":
        stop_loss = entry * (1 - STOP_LOSS_PERCENT / 100)
        take_profit = entry * (1 + TAKE_PROFIT_PERCENT / 100)
    else:
        stop_loss = entry * (1 + STOP_LOSS_PERCENT / 100)
        take_profit = entry * (1 - TAKE_PROFIT_PERCENT / 100)
    return stop_loss, take_profit

def get_trading_mode(chat_id):
    data = load_user_data()
    return data["trading_modes"].get(str(chat_id), "long")

def set_trading_mode(chat_id, mode):
    if mode not in ["long", "scalp"]:
        return
    data = load_user_data()
    data["trading_modes"][str(chat_id)] = mode
    save_user_data(data)
