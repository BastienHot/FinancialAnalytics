#!/usr/bin/env python3
import os
import sys
import pandas as pd
from pymongo import MongoClient, UpdateOne
from dotenv import load_dotenv
from loguru import logger

load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/finance_db")

logger.add("data_import.log", level="INFO", rotation="1 week")

# Define data sources. Keys = category, inner keys = symbol/dataset name, values = path to CSV.
data_sources = {
    "Currencies": {
        "EUR_USD": "./Historical_Data/Currencies/eur_usd.csv",
        "EUR_CNY": "./Historical_Data/Currencies/eur_cny.csv",
    },
    "ETF": {
        "S&P 500": "./Historical_Data/ETF/sp.csv",
        "STOXX 600": "./Historical_Data/ETF/stoxx.csv",
        "CSI 300": "./Historical_Data/ETF/csi.csv",
    },
    "Rare Materials": {
        "Gold": "./Historical_Data/Materials/gold.csv",
        "Silver": "./Historical_Data/Materials/silver.csv",
    },
    "Crypto": {
        "Bitcoin": "./Historical_Data/Crypto/bitcoin.csv",
        "Ethereum": "./Historical_Data/Crypto/ethereum.csv",
    },
}

def normalize_data(category, symbol, df):
    # Normalize date column name to 'date' and convert to consistent datetime format
    if 'DATE' in df.columns:
        df.rename(columns={'DATE': 'Date'}, inplace=True)

    # Ensure 'Date' column exists
    if 'Date' not in df.columns:
        raise ValueError(f"DataFrame for {symbol} in {category} does not contain a 'Date' column.")

    df['Date'] = pd.to_datetime(df['Date'], errors='coerce', utc=True).dt.date
    df.dropna(subset=['Date'], inplace=True)

    # Handle the price column. For currencies, the price column might be the symbol name (e.g., EUR_USD, EUR_CNY).
    # For others (ETF, Rare Materials, Crypto), the column name is 'Price'.
    price_col = None
    if symbol in df.columns and symbol != "Price":
        # This is likely the currencies dataset (e.g., EUR_USD).
        price_col = symbol
    else:
        # Otherwise, we assume the column is named 'Price'.
        price_col = 'Price'

    if price_col not in df.columns:
        raise ValueError(f"Price column not found in dataset for {symbol} in {category}.")

    # Convert price to float (remove commas if present)
    df[price_col] = df[price_col].astype(str).str.replace(',', '', regex=False).astype(float)

    # Return a standardized DataFrame with columns: date, price
    return df[['Date', price_col]].rename(columns={'Date': 'date', price_col: 'price'})

def import_data():
    client = MongoClient(MONGODB_URI)
    db = client.get_default_database()
    collection = db["historical_data"]

    try:
        operations = []
        for category, datasets in data_sources.items():
            for symbol, csv_path in datasets.items():
                logger.info(f"Processing {category} - {symbol} from {csv_path}")

                df = pd.read_csv(csv_path)
                df = normalize_data(category, symbol, df)

                for _, row in df.iterrows():
                    doc = {
                        "category": category,
                        "symbol": symbol,
                        "date": str(row["date"]),
                        "price": float(row["price"])
                    }
                    operations.append(
                        UpdateOne(
                            {"category": category, "symbol": symbol, "date": doc["date"]},
                            {"$set": doc},
                            upsert=True
                        )
                    )

        if operations:
            result = collection.bulk_write(operations, ordered=False)
            logger.info(f"Data import completed: {result.upserted_count + result.modified_count} records processed.")
        else:
            logger.info("No data to import.")
    except Exception as e:
        logger.error(f"Failed to import data: {e}")
        sys.exit(1)
    finally:
        client.close()

if __name__ == "__main__":
    import_data()
