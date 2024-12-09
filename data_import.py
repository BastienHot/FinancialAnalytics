#!/usr/bin/env python3
import os
import sys
import pandas as pd
from pymongo import MongoClient, UpdateOne
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/finance_db")

logger.add("data_import.log", level="INFO", rotation="1 week")

def import_data(csv_file, collection_name="historical_data"):
    client = MongoClient(MONGODB_URI)
    db = client.get_default_database()
    collection = db[collection_name]

    try:
        data = pd.read_csv(csv_file)
        # Expected columns: symbol, date, open, high, low, close, volume
        # Format date if necessary:
        data['date'] = pd.to_datetime(data['date']).dt.date

        operations = []
        for _, row in data.iterrows():
            doc = {
                "symbol": row["symbol"],
                "date": str(row["date"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"])
            }
            operations.append(
                UpdateOne(
                    {"symbol": doc["symbol"], "date": doc["date"]},
                    {"$set": doc},
                    upsert=True
                )
            )

        if operations:
            result = collection.bulk_write(operations, ordered=False)
            logger.info(f"Data import completed: {result.upserted_count} new/updated records.")
        else:
            logger.info("No data to import.")

    except Exception as e:
        logger.error(f"Failed to import data: {e}")
        sys.exit(1)
    finally:
        client.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error("Please provide a CSV file path.")
        sys.exit(1)

    csv_file = sys.argv[1]
    import_data(csv_file)
