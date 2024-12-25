#!/home/debian/FinancialAnalytics/venv/bin/python

import os
import sqlite3
import requests
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get the directory of the current script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Load API keys
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
EXCHANGE_RATE_API_KEY = os.getenv("EXCHANGE_RATE_API_KEY")

# Directories for logs and data
LOG_DIR = os.path.join(script_dir, 'assets/logs')
DATA_DIR = os.path.join(script_dir, 'assets/data')
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# Set up logging
logger = logging.getLogger('FinancialAnalyticsLogger')
logger.setLevel(logging.DEBUG)  # Capture all levels of logs

# Formatter for logs
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

# Console Handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Info File Handler with rotation
info_file_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, 'automation.log'),
    maxBytes=5*1024*1024,  # 5 MB
    backupCount=5
)
info_file_handler.setLevel(logging.INFO)
info_file_handler.setFormatter(formatter)
logger.addHandler(info_file_handler)

# Error File Handler with rotation
error_file_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, 'automation_error.log'),
    maxBytes=5*1024*1024,  # 5 MB
    backupCount=5
)
error_file_handler.setLevel(logging.ERROR)
error_file_handler.setFormatter(formatter)
logger.addHandler(error_file_handler)

def log_and_print(message, level="info"):
    """
    Logs the message at the specified level and prints it to the console.
    """
    if level == "info":
        logger.info(message)
    elif level == "error":
        logger.error(message)
    else:
        logger.debug(message)

def fetch_data(url):
    """
    Fetches data from the given URL and returns the JSON response.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()
        logger.debug(f"Successfully fetched data from {url}")
        return response.json()
    except requests.exceptions.RequestException as e:
        log_and_print(f"Error fetching data from {url}: {e}", "error")
        return None

def fetch_gold_api_price(symbol):
    """
    Fetches the price for the given symbol from the Gold API.
    """
    base_url = "https://api.gold-api.com/price"
    url = f"{base_url}/{symbol}"
    data = fetch_data(url)
    if data and "price" in data:
        try:
            price = round(float(data["price"]), 2)
            logger.debug(f"Fetched price for {symbol}: {price}")
            return price
        except (ValueError, TypeError) as e:
            log_and_print(f"Invalid price format for {symbol}: {e}", "error")
    log_and_print(f"Failed to fetch price for {symbol}.", "error")
    return None

def fetch_alphavantage_latest_close(symbol, api_key, multiplier=1.0, offset=0.0):
    """
    Fetches the latest closing price for the given symbol from Alpha Vantage.
    Applies multiplier and offset to adjust the price.
    """
    base_url = "https://www.alphavantage.co/query"
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "apikey": api_key,
    }
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        response_data = response.json()
    except requests.exceptions.RequestException as e:
        log_and_print(f"Error fetching data for {symbol} from Alpha Vantage: {e}", "error")
        return None, None

    if "Time Series (Daily)" not in response_data:
        log_and_print(f"Time Series data not found for {symbol} from Alpha Vantage.", "error")
        return None, None

    time_series = response_data["Time Series (Daily)"]
    sorted_time_series = sorted(time_series.items(), key=lambda x: x[0], reverse=True)
    
    if not sorted_time_series:
        log_and_print(f"No time series data available for {symbol}.", "error")
        return None, None

    most_recent_date, most_recent_data = sorted_time_series[0]
    try:
        closing_price = float(most_recent_data["4. close"])
        adjusted_price = round((closing_price * multiplier) + offset, 2)
        logger.debug(f"{symbol} - Date: {most_recent_date}, Closing Price: {closing_price}, Adjusted Price: {adjusted_price}")
        return most_recent_date, adjusted_price
    except (ValueError, KeyError) as e:
        log_and_print(f"Error processing closing price for {symbol}: {e}", "error")
        return None, None

def fetch_exchange_rates(api_key):
    """
    Fetches the latest exchange rates from Exchange Rate API.
    Normalizes rates to EUR base.
    """
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
        rate = data["conversion_rates"].get(currency)
        if rate:
            # Normalize to EUR base: rate(EUR->CURRENCY) = rate(USD->CURRENCY) / rate(USD->EUR)
            normalized_rate = round(rate / eur_rate, 5)
            exchange_rates[currency] = normalized_rate
            logger.debug(f"Exchange rate EUR->{currency}: {normalized_rate}")
        else:
            log_and_print(f"{currency} rate not found in exchange rates.", "error")
    return exchange_rates

def store_data(table_name, date, price):
    """
    Stores the given price data into the specified SQLite table.
    """
    try:
        conn = sqlite3.connect(os.path.join(DATA_DIR, "historical_data.db"))
        cursor = conn.cursor()

        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                date TEXT PRIMARY KEY,
                price REAL
            )
            """
        )

        cursor.execute(
            f"INSERT INTO {table_name} (date, price) VALUES (?, ?)",
            (date, price)
        )
        conn.commit()
        log_and_print(f"Data inserted into {table_name}: date={date}, price={price}")
    except sqlite3.IntegrityError:
        log_and_print(f"Data for date {date} already exists in {table_name}", "info")
    except sqlite3.Error as e:
        log_and_print(f"SQLite error for table {table_name}: {e}", "error")
    finally:
        if conn:
            conn.close()

def cleanup_old_data(table_name, years=5):
    """
    Removes data older than the specified number of years from the given table.
    """
    cutoff_date = (datetime.now() - timedelta(days=years*365)).strftime("%Y-%m-%d")
    try:
        conn = sqlite3.connect(os.path.join(DATA_DIR, "historical_data.db"))
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {table_name} WHERE date < ?", (cutoff_date,))
        deleted_rows = cursor.rowcount
        conn.commit()
        log_and_print(f"Old data (older than {years} years) removed from {table_name}: {deleted_rows} records deleted.")
    except sqlite3.Error as e:
        log_and_print(f"Error cleaning up table {table_name}: {e}", "error")
    finally:
        if conn:
            conn.close()

def main():
    # Calculate yesterday's date
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    logger.info(f"Starting data fetch for date: {yesterday}")

    try:
        # Fetch prices
        gold_price = fetch_gold_api_price("XAU")
        silver_price = fetch_gold_api_price("XAG")
        bitcoin_price = fetch_gold_api_price("BTC")
        ethereum_price = fetch_gold_api_price("ETH")

        # Store rare materials and crypto prices
        if gold_price is not None:
            store_data("Rare_Materials_Gold", yesterday, gold_price)
        if silver_price is not None:
            store_data("Rare_Materials_Silver", yesterday, silver_price)
        if bitcoin_price is not None:
            store_data("Crypto_Bitcoin", yesterday, bitcoin_price)
        if ethereum_price is not None:
            store_data("Crypto_Ethereum", yesterday, ethereum_price)
        
        # Fetch exchange rates
        exchange_rates = fetch_exchange_rates(EXCHANGE_RATE_API_KEY)
        if exchange_rates:
            store_data("Currencies_EUR_USD", yesterday, exchange_rates["USD"])
            store_data("Currencies_EUR_CNY", yesterday, exchange_rates["CNY"])

            EUR_USD = exchange_rates["USD"]
            EUR_CNY = exchange_rates["CNY"]
            USD_CNY = round(EUR_CNY / EUR_USD, 5)

            # Store the USD→CNY exchange rate
            store_data("Currencies_USD_CNY", yesterday, USD_CNY)

            # Fetch and store ETF prices
            sp500_date, sp500_price = fetch_alphavantage_latest_close("SPY", ALPHA_VANTAGE_API_KEY, multiplier=10, offset=10)
            stoxx600_date, stoxx600_price = fetch_alphavantage_latest_close("EXSA.DE", ALPHA_VANTAGE_API_KEY, multiplier=10, offset=5)
            csi300_date, csi300_price = fetch_alphavantage_latest_close("ASHR", ALPHA_VANTAGE_API_KEY, multiplier=20 * USD_CNY, offset=0)

            # Validate dates and store ETF data
            if sp500_date != yesterday:
                log_and_print(f"S&P500 data is outdated. Expected: {yesterday}, Got: {sp500_date}", "error")
            elif sp500_price is not None:
                store_data("ETF_SP_500", sp500_date, sp500_price)

            if stoxx600_date != yesterday:
                log_and_print(f"Stoxx 600 data is outdated. Expected: {yesterday}, Got: {stoxx600_date}", "error")
            elif stoxx600_price is not None:
                store_data("ETF_STOXX_600", stoxx600_date, stoxx600_price)

            if csi300_date != yesterday:
                log_and_print(f"CSI 300 data is outdated. Expected: {yesterday}, Got: {csi300_date}", "error")
            elif csi300_price is not None:
                store_data("ETF_CSI_300", csi300_date, csi300_price)
    except Exception as e:
        logger.exception(f"Unexpected error in main execution: {e}")
    
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

    logger.info("Data fetch and cleanup completed.")

if __name__ == "__main__":
    main()
