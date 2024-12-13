# Financial Assets Comparison Dashboard

## Table of Contents
1. [Project Overview](#project-overview)
2. [Context & Requirements](#context--requirements)
3. [Data Sources & Assets](#data-sources--assets)
4. [Data Ingestion & Processing Workflow](#data-ingestion--processing-workflow)
5. [Database Structure](#database-structure)
6. [Application Features](#application-features)
7. [Plots & Visualizations](#plots--visualizations)
8. [Installation & Setup](#installation--setup)

---

## Project Overview

This project is a Proof of Concept (PoC) for building a real-time dashboard that helps users analyze and compare the performance of various financial assets over different time periods. The application focuses on retrieving, processing, and visualizing financial data (such as currencies, index funds, rare materials, and cryptocurrencies).

The main goal is to allow users to:
- Compare multiple financial assets across different categories.
- Visualize both absolute (raw price) and relative (scaled percentage change) growth over selected periods.
- Interactively select categories and specific assets.
- Adjust the analysis timeframe (from 1 week to 5 years) to understand short-term vs. long-term trends.

This PoC demonstrates how a combination of scheduling (cron), Python scripts, a SQLite database, and an interactive web interface (Streamlit) can work together to provide up-to-date, insightful financial analysis.

---

## Context & Requirements

**Educational Context:**  
This project was created as part of an academic assignment where the requirements were:
- To fetch data from multiple real-time sources using scheduled tasks (cron jobs).
- Pre-process the data and store it in a structured manner.
- Produce a final analysis tool (web dashboard) that displays visualizations and key metrics.
- Include multiple data sources related to each others (here financial markets - currencies, indexes, commodities, crypto).

**Instructor's Requirements Recap:**  
1. Create a script that periodically downloads data from APIs and stores it locally.  
2. Use a cron job to schedule this retrieval process.  
3. Create another script that periodically summarizes the collected data and stores the results in a database (e.g., MongoDB or SQLite). This script also manages housekeeping tasks such as removing old raw files.  
4. Finally, create an analysis script that runs periodically, generating a PDF report or a web application (like Streamlit) to visualize the processed data. A cron job schedules this step as well.

---

## Data Sources & Assets

**Assets Included:**
- **Currencies:** EUR/USD, EUR/CNY, USD/CNY
- **Index Funds (ETFs):** S&P 500, Stoxx 600, CSI 300
- **Rare Materials:** Gold, Silver
- **Crypto:** Bitcoin, Ethereum

All these assets can be compared inside the dashboard view in their respective categories but there will also be a category called "All Assets" allowing for cross-category comparisons, letting users select multiple assets and view their relative performance.

---

## Data Ingestion & Processing Workflow

1. **Data Retrieval & Processing (Cron Job + Python Script):**
   - Every day at 11:55pm, a python script queries external APIs to fetch updated financial asset prices.
   - The script pre-process this data to extract only the information we want and apply standardization so all of our sources can have the same format. 
   - It then stores the data into a SQLite database (`assets/data/historical_data.db`) and clean the data that is more than 5 years old.

3. **Analysis & Visualization (Streamlit App):**
   - Then the StreamLit app (`app.py`) is running all the time on a dedicated server to be able to access the visual dashboard at any time, the data will be refreshed in the database once a day and users can press `F5`at the time of refresh to see the new data.

This pipeline ensures:
- **Real-time Data:** Frequent updates via API.
- **Historical Context:** Data stored in SQLite for trend analysis.
- **User-Friendly Interface:** Streamlit front-end for intuitive exploration.

---

## Database Structure

The SQLite database (`assets/data/historical_data.db`) contains one table per asset:
- `Currencies_EUR_USD`
- `Currencies_EUR_CNY`
- `Currencies_USD_CNY`
- `ETF_SP_500`
- `ETF_STOXX_600`
- `ETF_CSI_300`
- `Rare_Materials_Gold`
- `Rare_Materials_Silver`
- `Crypto_Bitcoin`
- `Crypto_Ethereum`

Each table includes:
- `date`: A timestamp or date (YYYY-MM-DD) of the recorded price.
- `price`: The asset price at that date.

---

## Application Features

1. **Sidebar Controls:**
   - Category Selection: Choose between Currencies, Index Funds, Rare Materials, Crypto, or All Assets.
   - Period Selector: Select from 1 Week, 1 Month, 3 Months, 6 Months, 1 Year, 3 Years, 5 Years.

2. **Dynamic Content:**
   - For a single category: Displays each asset’s latest price, price difference since the start of the chosen period, and percentage change.
   - **Normal Plot:** Shows the raw price evolution over time.
   - **Scaled Plot:** Shows percentage changes relative to the first recorded price in the selected period, allowing for easy comparisons between assets with different price scales.

3. **All Assets Comparison:**
   - Allows the user to select multiple assets from all categories and compare them together.
   - Provides both individual normal plots and a combined scaled plot.

---

## Plots & Visualizations

**Normal Plot (Raw Price):**  
- A line chart of the asset's price over time.

**Scaled Plot (Percentage Change):**  
- A line chart representing relative performance.  
- If an asset's price started at X and ended at Y, the percentage change is ((Y - X) / X) * 100%.  
- Multiple assets can be overlaid to compare their relative growth or decline.

These visualizations are made with **Plotly**, ensuring interactive tooltips, zooming, and panning functionality.

---

## Installation & Setup

**Prerequisites:**
- Python 3.8+ (recommended)
- `pip` or `conda` for Python dependency management

**Dependencies:**
- [Streamlit](https://streamlit.io/) for the web interface.
- [Plotly](https://plotly.com/) for interactive charts.
- [pandas](https://pandas.pydata.org/) for data manipulation.
- [sqlite3](https://www.sqlite.org/index.html) for database interaction.
- [Cron](https://en.wikipedia.org/wiki/Cron) for scheduling data retrieval and processing tasks (on Unix-like systems).

**Recommended Installation Steps:**
1. **Clone** the **repository**:
   ```bash
   git clone https://github.com/BastienHot/FinancialAnalytics.git
   cd FinancialAnalytics
2. **Create** a **Virtual Environment**:
   Create the Environment:
   ```bash
   python -m venv venv
   ```
   Enter the Environment:
   ```bash
   source ./venv/bin/activate
   ```
3. **Install** the **dependencies**
4. **Create SQLite database** respecting the details above and **import the data**.
5. Ensure the Python script has **execution rights**:
   ```bash
   chmod +x fetch_data.py
   ```
6. **Change Shebang** in `fetch_data.py`:
   Replace with the actual path on your system:
   ```bash
   #!/home/debian/FinancialAnalytics/venv/bin/python
   ```

   (On this example we run a debian server with a user called debian.)
7. **Create** a **Cron Job** for **data fetching**:
    
    Enter the Crontab file:
    ```bash
    crontab -e
    ```
    Then add:

    ```bash
    55 23 * * * /path/to/your/script.sh
    ```
    
    **Save** and exit.