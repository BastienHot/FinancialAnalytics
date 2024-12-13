import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime, timedelta

# ---------------------
# Configuration
# ---------------------
st.set_page_config(page_title="Financial Analysis App", layout="wide")

# ---------------------
# Constants & Mappings
# ---------------------
ASSETS_DICT = {
    "Currencies": {
        "Currencies_EUR_USD": "EUR/USD",
        "Currencies_EUR_CNY": "EUR/CNY",
        "Currencies_USD_CNY": "USD/CNY"  # Added USD/CNY pair
    },
    "Index Funds": {  # Renamed from ETFs
        "ETF_SP_500": "S&P 500",
        "ETF_STOXX_600": "Stoxx 600",
        "ETF_CSI_300": "CSI 300"
    },
    "Rare Materials": {
        "Rare_Materials_Gold": "Gold",
        "Rare_Materials_Silver": "Silver"
    },
    "Crypto": {
        "Crypto_Bitcoin": "Bitcoin",
        "Crypto_Ethereum": "Ethereum"
    }
}

CURRENCY_DICT = {
    "Currencies_EUR_USD": "$",
    "Currencies_EUR_CNY": "¥",
    "Currencies_USD_CNY": "¥",  # Added USD/CNY currency symbol
    "ETF_SP_500": "$",
    "ETF_STOXX_600": "€",
    "ETF_CSI_300": "¥",
    "Rare_Materials_Gold": "$",
    "Rare_Materials_Silver": "$",
    "Crypto_Bitcoin": "$",
    "Crypto_Ethereum": "$"
}

ALL_ASSETS_TABLES = []
for cat_assets in ASSETS_DICT.values():
    ALL_ASSETS_TABLES.extend(list(cat_assets.keys()))

reverse_lookup = {tbl: name for cat_dict in ASSETS_DICT.values() for tbl, name in cat_dict.items()}

ALL_ASSETS_DISPLAY = [reverse_lookup[tbl] for tbl in ALL_ASSETS_TABLES]
display_to_table = {name: tbl for tbl, name in reverse_lookup.items()}

PERIOD_OPTIONS = ["1 Week", "1 Month", "3 Months", "6 Months", "1 Year", "3 Years", "5 Years"]

# ---------------------
# Utility Functions
# ---------------------

def get_period_delta(period_str: str) -> datetime:
    now = datetime.now()
    if period_str == "1 Week":
        return now - timedelta(weeks=1)
    elif period_str == "1 Month":
        return now - timedelta(days=30)
    elif period_str == "3 Months":
        return now - timedelta(days=90)
    elif period_str == "6 Months":
        return now - timedelta(days=180)
    elif period_str == "1 Year":
        return now - timedelta(days=365)
    elif period_str == "3 Years":
        return now - timedelta(days=3*365)
    elif period_str == "5 Years":
        return now - timedelta(days=5*365)
    return now - timedelta(days=365)

@st.cache_data(show_spinner=False)
def fetch_data_from_db(table_name: str, start_date: str, db_name: str = "./assets/data/historical_data.db") -> pd.DataFrame:
    try:
        conn = sqlite3.connect(db_name)
        query = f"""
            SELECT date, price
            FROM {table_name}
            WHERE date >= '{start_date}'
            ORDER BY date ASC;
        """
        df = pd.read_sql(query, conn)
        conn.close()
        if df.empty:
            return pd.DataFrame()
        df['date'] = pd.to_datetime(df['date'])
        df['price'] = pd.to_numeric(df['price'], errors='coerce')
        df = df.dropna(subset=['price'])
        return df
    except Exception as e:
        print(f"Error fetching data for {table_name}: {e}")
        return pd.DataFrame()

def calculate_metrics(df: pd.DataFrame):
    if df.empty or 'price' not in df.columns or df['price'].empty:
        return None, None, None
    start_price = df['price'].iloc[0]
    end_price = df['price'].iloc[-1]
    diff = end_price - start_price
    pct_change = (diff / start_price) * 100 if start_price != 0 else None
    return end_price, diff, pct_change

def create_normal_plot(df: pd.DataFrame, asset_name: str):
    if df.empty:
        return None
    fig = px.line(df, x='date', y='price', title=f"{asset_name} - Price Over Time")
    fig.update_layout(xaxis_title="Date", yaxis_title="Price")
    return fig

def create_scaled_plot(df_dict: dict):
    fig = px.line()
    any_data = False
    for asset_name, df in df_dict.items():
        if df.empty:
            continue
        any_data = True
        start_price = df['price'].iloc[0]
        if start_price == 0:
            df['scaled'] = 0
        else:
            df['scaled'] = ((df['price'] - start_price) / start_price) * 100
        fig.add_scatter(x=df['date'], y=df['scaled'], mode='lines', name=asset_name)
    if not any_data:
        return None
    fig.update_layout(title="Percentage Change Over Time", xaxis_title="Date", yaxis_title="% Change from Start")
    return fig

def format_price(value: float, currency: str) -> str:
    if value is None:
        return "-"
    abs_val = abs(value)
    formatted = f"{value:,.2f}"
    if abs_val >= 1_000_000:
        formatted = f"{value / 1_000_000:.1f}M"
    elif abs_val >= 1_000:
        formatted = f"{value / 1_000:.1f}K"
    return f"{formatted} {currency}"

# ---------------------
# UI: Sidebar
# ---------------------
st.sidebar.image("./assets/img/logo.png", use_container_width=True)
st.sidebar.title("Controls")
category = st.sidebar.radio("Category", ["Currencies", "Index Funds", "Rare Materials", "Crypto", "All Assets"])
period = st.sidebar.selectbox("Period", PERIOD_OPTIONS, index=4)
start_date_dt = get_period_delta(period)
start_date = start_date_dt.strftime("%Y-%m-%d")

if category == "All Assets":
    chosen_display_assets = st.sidebar.multiselect(
        "Select Assets to Compare",
        ALL_ASSETS_DISPLAY,
        default=["S&P 500", "Gold"]
    )
    chosen_assets = [display_to_table[name] for name in chosen_display_assets]
else:
    chosen_assets = list(ASSETS_DICT[category].keys())

# ---------------------
# Main Content
# ---------------------
st.title("Financial Assets Analysis")

if category == "Index Funds":
    st.markdown(
        """
        **Disclaimer:** The displayed values are approximate and based on ETFs tracking the indices:
        - **S&P 500**: SPY
        - **Stoxx 600**: EXSA.DE
        - **CSI 300**: ASHR
        """
    )

if category != "All Assets":
    st.header(f"{category} Overview")

    metrics_cols = st.columns(len(chosen_assets))
    df_dict = {}

    for i, asset_table in enumerate(chosen_assets):
        asset_name_display = reverse_lookup[asset_table]
        currency_symbol = CURRENCY_DICT[asset_table]
        df = fetch_data_from_db(asset_table, start_date)
        df_dict[asset_name_display] = df
        latest_price, diff, pct_change = calculate_metrics(df)

        with metrics_cols[i]:
            st.markdown(f"<h3 class='asset-title'>{asset_name_display}</h3>", unsafe_allow_html=True)
            if latest_price is not None:
                formatted_price = format_price(latest_price, currency_symbol)
                if diff is not None and pct_change is not None:
                    delta_str = f"{round(diff,2)} ({round(pct_change,2)}%)"
                    st.metric(label=f"Latest Price ({currency_symbol})", value=formatted_price, delta=delta_str, label_visibility="collapsed")
                else:
                    st.metric(label=f"Latest Price ({currency_symbol})", value=formatted_price, label_visibility="collapsed")

                normal_fig = create_normal_plot(df, asset_name_display)
                if normal_fig:
                    st.plotly_chart(normal_fig, use_container_width=True)
                else:
                    st.write("No chart data available.")
            else:
                st.write("No data for selected period.")

    if len(chosen_assets) > 1:
        st.subheader("Comparative Analysis (Scaled Plot)")
        scaled_fig = create_scaled_plot(df_dict)
        if scaled_fig:
            st.plotly_chart(scaled_fig, use_container_width=True)
        else:
            st.write("No comparative data available for the selected period.")

else:
    st.header("Compare Assets Across All Categories")
    if chosen_assets:
        df_dict = {}
        for asset_table in chosen_assets:
            asset_name_display = reverse_lookup.get(asset_table, asset_table)
            currency_symbol = CURRENCY_DICT[asset_table]
            df = fetch_data_from_db(asset_table, start_date)
            df_dict[asset_name_display] = df

        metrics_cols = st.columns(len(chosen_assets))

        for i, asset_table in enumerate(chosen_assets):
            asset_name_display = reverse_lookup.get(asset_table, asset_table)
            with metrics_cols[i]:
                st.markdown(f"<h3 class='asset-title'>{asset_name_display}</h3>", unsafe_allow_html=True)
                df = df_dict[asset_name_display]
                latest_price, diff, pct_change = calculate_metrics(df)
                if latest_price is not None:
                    formatted_price = format_price(latest_price, CURRENCY_DICT[asset_table])
                    if diff is not None and pct_change is not None:
                        delta_str = f"{round(diff,2)} ({round(pct_change,2)}%)"
                        st.metric(label=f"Latest Price ({CURRENCY_DICT[asset_table]})", value=formatted_price, delta=delta_str, label_visibility="collapsed")
                    else:
                        st.metric(label=f"Latest Price ({CURRENCY_DICT[asset_table]})", value=formatted_price, label_visibility="collapsed")

                    normal_fig = create_normal_plot(df, asset_name_display)
                    if normal_fig:
                        st.plotly_chart(normal_fig, use_container_width=True)
                    else:
                        st.write("No chart data available.")
                else:
                    st.write("No data for selected period.")

        if len(chosen_assets) > 1:
            st.subheader("Comparative Analysis (Scaled Plot)")
            scaled_fig = create_scaled_plot(df_dict)
            if scaled_fig:
                st.plotly_chart(scaled_fig, use_container_width=True)
            else:
                st.write("No comparative data available for the selected period.")
    else:
        st.info("Please select at least one asset for comparison.")
