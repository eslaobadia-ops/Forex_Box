import os
import time
import requests
import pandas as pd
import pandas_ta as ta
import yfinance as yf
from datetime import datetime

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
SYMBOL = "EURUSD=X"       # Yahoo Finance symbol for EUR/USD
TIMEFRAME = "15m"         # 15-minute candles
SL_PIPS = 20              # Stop Loss in pips
TP_PIPS = 40              # Take Profit in pips
CHECK_INTERVAL = 60       # Check every 60 seconds

# Get Telegram Secrets from Replit environment
TG_TOKEN = os.environ.get('TG_TOKEN')
TG_CHAT_ID = os.environ.get('TG_CHAT_ID')

# Track last signal to avoid spamming
last_signal_time = None
last_signal_type = None

# ─────────────────────────────────────────────
# TELEGRAM ALERT FUNCTION
# ─────────────────────────────────────────────
def send_alert(message):
    """Send message to Telegram"""
    if not TG_TOKEN or not TG_CHAT_ID:
        print("❌ Error: Telegram secrets not found!")
        return

    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Alert sent to Telegram")
        else:
            print(f"❌ Telegram API Error: {response.text}")
    except Exception as e:
        print(f"❌ Telegram Error: {e}")

# ─────────────────────────────────────────────
# FETCH MARKET DATA
# ─────────────────────────────────────────────
def get_data(symbol, timeframe):
    """Download candlestick data from Yahoo Finance"""
    try:
        # Download 5 days of data to ensure enough candles for EMA 50
        df = yf.download(symbol, period="5d", interval=timeframe, progress=False)

        if len(df) == 0:
            return None

        # Fix column names for multi-index (common in yfinance)
        df.reset_index(inplace=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]

        return df
    except Exception as e:
        print(f"❌ Data Fetch Error: {e}")
        return None

# ─────────────────────────────────────────────
# TRADING STRATEGY (EMA + RSI)
# ─────────────────────────────────────────────
def check_signal(df):
    """Check for BUY/SELL signals based on EMA + RSI"""
    global last_signal_time, last_signal_type

    if df is None or len(df) < 50:
        return None

    # Calculate Indicators
    df['EMA_50'] = ta.ema(df['Close'], length=50)
    df['RSI_14'] = ta.rsi(df['Close'], length=14)

    last = df.iloc[-1]
    prev = df.iloc[-2]
    current_time = datetime.now()

    # Prevent multiple signals within the same 15-minute candle (900 seconds)
    if last_signal_time:
        time_diff = (current_time - last_signal_time).total_seconds()
        if time_diff < 900:
            return None

    signal = None
    price = float(last['Close'])
    ema50 = float(last['EMA_50'])
    rsi_last = float(last['RSI_14'])
    rsi_prev = float(prev['RSI_14'])

    # ─── BUY SIGNAL ───
    # Price above EMA 50 + RSI crosses above 30 (oversold recovery)
    if (price > ema50 and
            rsi_prev < 30 and
            rsi_last > 30 and
            last_signal_type != "BUY"):

        signal = "BUY"
        sl = price - (SL_PIPS * 0.0001)
        tp = price + (TP_PIPS * 0.0001)

    # ─── SELL SIGNAL ───
    # Price below EMA 50 + RSI crosses below 70 (overbought rejection)
    elif (price < ema50 and
          rsi_prev > 70 and
          rsi_last < 70 and
          last_signal_type != "SELL"):

        signal = "SELL"
        sl = price + (SL_PIPS * 0.0001)
        tp = price - (TP_PIPS * 0.0001)

    if signal:
        last_signal_time = current_time
        last_signal_type = signal
        return {
            "type": signal,
            "price": price,
            "sl": sl,
            "tp": tp
        }

    return None

# ─────────────────────────────────────────────
# FORMAT TELEGRAM MESSAGE
# ─────────────────────────────────────────────
def format_message(signal_data):
    """Create a formatted Telegram message"""
    emoji = "🟢" if signal_data['type'] == "BUY" else "🔴"

    message = (
        f"{emoji} <b>NEW FOREX SIGNAL</b> {emoji}\n\n"
        f"📈 <b>Pair:</b> EUR/USD\n"
        f"🔹 <b>Action:</b> <code>{signal_data['type']}</code>\n"
        f"💰 <b>Entry:</b> <code>{signal_data['price']:.5f}</code>\n\n"
        f"🛑 <b>Stop Loss:</b> <code>{signal_data['sl']:.5f}</code>\n"
        f"🎯 <b>Take Profit:</b> <code>{signal_data['tp']:.5f}</code>\n\n"
        f"⏰ <b>Time:</b> {datetime.now().strftime('%H:%M %d/%m/%Y')}\n"
        f"📱 <b>Execute on:</b> Headway App\n\n"
        f"⚠️ <i>This is a signal only. Trade at your own risk.</i>"
    )
    return message

# ─────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────
def main():
    print("🤖 Forex Signal Bot Starting...")
    print(f"📊 Monitoring: EUR/USD | Timeframe: {TIMEFRAME} | Interval: {CHECK_INTERVAL}s")
    send_alert("🚀 <b>Bot is ONLINE</b>\n\nMonitoring EUR/USD for signals...")

    while True:
        try:
            # Fetch data
            df = get_data(SYMBOL, TIMEFRAME)

            if df is not None:
                # Check for signal
                result = check_signal(df)

                if result:
                    print(f"📈 Signal Detected: {result['type']} @ {result['price']:.5f}")
                    message = format_message(result)
                    send_alert(message)
                else:
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    print(f"⏳ [{timestamp}] No signal — waiting {CHECK_INTERVAL}s...")
            else:
                print("⚠️ No data received from Yahoo Finance")

            # Wait before next check
            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("\n🛑 Bot stopped by user")
            send_alert("🛑 <b>Bot STOPPED</b>")
            break
        except Exception as e:
            print(f"❌ Loop Error: {e}")
            time.sleep(CHECK_INTERVAL)

# ─────────────────────────────────────────────
# RUN THE BOT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    main()
