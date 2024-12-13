import os
import sqlite3
import requests
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Load API keys
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
EXCHANGE_RATE_API_KEY = os.getenv("EXCHANGE_RATE_API_KEY")

# Set up logging
LOG_DIR = "./assets/logs"
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=f"{LOG_DIR}/automation.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

def log_and_print(message, level="info"):
    print(message)
    if level == "info":
        logging.info(message)
    elif level == "error":
        logging.error(message)

def fetch_data(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        log_and_print(f"Error fetching data from {url}: {e}", "error")
        return None

def fetch_gold_api_price(symbol):
    base_url = "https://api.gold-api.com/price"
    url = f"{base_url}/{symbol}"
    data = fetch_data(url)
    if data and "price" in data:
        return round(float(data["price"]), 2)
    log_and_print(f"Failed to fetch price for {symbol}.", "error")
    return None

def fetch_alphavantage_latest_close(symbol, api_key, multiplier=1.0, offset=0.0):
    base_url = "https://www.alphavantage.co/query"
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "apikey": api_key,
    }
    response_data = fetch_data(base_url + "?" + "&".join(f"{k}={v}" for k, v in params.items()))
    if not response_data or "Time Series (Daily)" not in response_data:
        log_and_print(f"Failed to fetch data for {symbol} from Alpha Vantage.", "error")
        return None, None

    time_series = response_data["Time Series (Daily)"]
    sorted_time_series = sorted(time_series.items(), key=lambda x: x[0], reverse=True)
    most_recent_date, most_recent_data = sorted_time_series[0]
    closing_price = float(most_recent_data["4. close"])
    adjusted_price = round((closing_price * multiplier) + offset, 2)
    return most_recent_date, adjusted_price

def fetch_exchange_rates(api_key):
    url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/USD"
    data = fetch_data(url)
    if not data or "conversion_rates" not in data:
        log_and_print("Failed to fetch exchange rates.", "error")
        return None

    eur_rate = data["conversion_rates"].get("EUR", None)
    if eur_rate is None:
        log_and_print("EUR rate not found in exchange rates.", "error")
        return None

    exchange_rates = {}
    for currency in ["USD", "EUR", "CNY"]:
        if currency in data["conversion_rates"]:
            # Normalize to EUR base: rate(EUR->CURRENCY) = rate(USD->CURRENCY) / rate(USD->EUR)
            exchange_rates[currency] = round(data["conversion_rates"][currency] / eur_rate, 5)
    return exchange_rates

def store_data(table_name, date, price):
    conn = sqlite3.connect("./assets/data/historical_data.db")
    cursor = conn.cursor()

    cursor.execute(
        f"CREATE TABLE IF NOT EXISTS {table_name} (date TEXT PRIMARY KEY, price REAL)"
    )

    try:
        cursor.execute(f"INSERT INTO {table_name} (date, price) VALUES (?, ?)", (date, price))
        conn.commit()
        log_and_print(f"Data inserted into {table_name}: date={date}, price={price}")
    except sqlite3.IntegrityError:
        log_and_print(f"Data for date {date} already exists in {table_name}", "info")
    finally:
        conn.close()

def cleanup_old_data(table_name, years=5):
    cutoff_date = (datetime.now() - timedelta(days=years*365)).strftime("%Y-%m-%d")
    conn = sqlite3.connect("./assets/data/historical_data.db")
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM {table_name} WHERE date < ?", (cutoff_date,))
    conn.commit()
    conn.close()
    log_and_print(f"Old data older than {years} years removed from {table_name}")

def main():
    today = datetime.now().strftime("%Y-%m-%d")

    try:
        # Fetch prices
        gold_price = fetch_gold_api_price("XAU")
        silver_price = fetch_gold_api_price("XAG")
        bitcoin_price = fetch_gold_api_price("BTC")
        ethereum_price = fetch_gold_api_price("ETH")

        # Store rare materials and crypto prices
        if gold_price is not None:
            store_data("Rare_Materials_Gold", today, gold_price)
        if silver_price is not None:
            store_data("Rare_Materials_Silver", today, silver_price)
        if bitcoin_price is not None:
            store_data("Crypto_Bitcoin", today, bitcoin_price)
        if ethereum_price is not None:
            store_data("Crypto_Ethereum", today, ethereum_price)
        
        # Fetch exchange rates
        exchange_rates = fetch_exchange_rates(EXCHANGE_RATE_API_KEY)
        if exchange_rates:
            store_data("Currencies_EUR_USD", today, exchange_rates["USD"])
            store_data("Currencies_EUR_CNY", today, exchange_rates["CNY"])

            EUR_USD = exchange_rates["USD"]
            EUR_CNY = exchange_rates["CNY"]
            USD_CNY = round(EUR_CNY / EUR_USD, 5)

            # Store the USD→CNY exchange rate
            store_data("Currencies_USD_CNY", today, USD_CNY)

            # Fetch and store ETF prices
            sp500_date, sp500_price = fetch_alphavantage_latest_close("SPY", ALPHA_VANTAGE_API_KEY, multiplier=10, offset=10)
            stoxx600_date, stoxx600_price = fetch_alphavantage_latest_close("EXSA.DE", ALPHA_VANTAGE_API_KEY, multiplier=10, offset=5)
            csi300_date, csi300_price = fetch_alphavantage_latest_close("ASHR", ALPHA_VANTAGE_API_KEY, multiplier=20 * USD_CNY, offset=0)

            if sp500_date != today:
                log_and_print(f"S&P500 data is outdated. Expected: {today}, Got: {sp500_date}", "error")
            elif sp500_price is not None:
                store_data("ETF_SP_500", sp500_date, sp500_price)

            if stoxx600_date != today:
                log_and_print(f"Stoxx 600 data is outdated. Expected: {today}, Got: {stoxx600_date}", "error")
            elif stoxx600_price is not None:
                store_data("ETF_STOXX_600", stoxx600_date, stoxx600_price)

            if csi300_date != today:
                log_and_print(f"CSI 300 data is outdated. Expected: {today}, Got: {csi300_date}", "error")
            elif csi300_price is not None:
                store_data("ETF_CSI_300", csi300_date, csi300_price)
    except Exception as e:
        log_and_print(f"Unexpected error: {e}", "error")

    # Cleanup old data from all tables (older than 5 years)
    tables = [
        "Rare_Materials_Gold",
        "Rare_Materials_Silver",
        "Crypto_Bitcoin",
        "Crypto_Ethereum",
        "Currencies_EUR_USD",
        "Currencies_EUR_CNY",
        "Currencies_USD_CNY",
        "ETF_SP_500",
        "ETF_STOXX_600",
        "ETF_CSI_300"
    ]

    for table in tables:
        cleanup_old_data(table, 5)

if __name__ == "__main__":
    main()
