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
        "Currencies_EUR_CNY": "EUR/CNY"
    },
    "ETFs": {
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

# Flatten all tables into a list
ALL_ASSETS_TABLES = []
for cat_assets in ASSETS_DICT.values():
    ALL_ASSETS_TABLES.extend(list(cat_assets.keys()))

# Create a reverse lookup: table_name -> display_name
reverse_lookup = {tbl: name for cat_dict in ASSETS_DICT.values() for tbl, name in cat_dict.items()}

# For "All Assets", we want to show display names instead of table names
ALL_ASSETS_DISPLAY = [reverse_lookup[tbl] for tbl in ALL_ASSETS_TABLES]

# Create a mapping from display name back to table name for when user selects assets
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
def fetch_data_from_db(table_name: str, start_date: str, db_name: str = "historical_data.db") -> pd.DataFrame:
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
        # Convert price to float
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

def format_price(value: float) -> str:
    if value is None:
        return "-"
    abs_val = abs(value)
    if abs_val >= 1_000_000:
        return f"{value/1_000_000:.1f}M"
    elif abs_val >= 1_000:
        return f"{value/1_000:.1f}K"
    else:
        return f"{value:.2f}"

# ---------------------
# UI: Sidebar
# ---------------------
st.sidebar.image("logo.png", use_container_width=True)
st.sidebar.title("Controls")
category = st.sidebar.radio("Category", ["Currencies", "ETFs", "Rare Materials", "Crypto", "All Assets"])
period = st.sidebar.selectbox("Period", PERIOD_OPTIONS, index=4)  # Default to "1 Year"
start_date_dt = get_period_delta(period)
start_date = start_date_dt.strftime("%Y-%m-%d")

if category == "All Assets":
    # Show display names in the multiselect
    # Default selection: "S&P 500" and "Gold"
    chosen_display_assets = st.sidebar.multiselect(
        "Select Assets to Compare",
        ALL_ASSETS_DISPLAY,
        default=["S&P 500", "Gold"]
    )
    # Convert chosen display names back to table names
    chosen_assets = [display_to_table[name] for name in chosen_display_assets]
else:
    chosen_assets = list(ASSETS_DICT[category].keys())

# ---------------------
# Main Content
# ---------------------

# Add custom CSS for larger asset titles
st.markdown("""
<style>
h3.asset-title {
    font-size: 1.5em !important;
    font-weight: bold;
    margin-bottom: 0.2em;
}
</style>
""", unsafe_allow_html=True)

st.title("Financial Assets Analysis")

if category != "All Assets":
    st.header(f"{category} Overview")

    metrics_cols = st.columns(len(chosen_assets))
    df_dict = {}

    for i, asset_table in enumerate(chosen_assets):
        asset_name_display = reverse_lookup[asset_table]
        df = fetch_data_from_db(asset_table, start_date)
        df_dict[asset_name_display] = df
        latest_price, diff, pct_change = calculate_metrics(df)

        with metrics_cols[i]:
            st.markdown(f"<h3 class='asset-title'>{asset_name_display}</h3>", unsafe_allow_html=True)
            if latest_price is not None:
                formatted_price = format_price(latest_price)
                if diff is not None and pct_change is not None:
                    delta_str = f"{round(diff,2)} ({round(pct_change,2)}%)"
                    # Provide a hidden label to prevent empty label warnings
                    st.metric(label="Latest Price", value=formatted_price, delta=delta_str, label_visibility="collapsed")
                else:
                    st.metric(label="Latest Price", value=formatted_price, label_visibility="collapsed")

                # Normal plot under the asset
                normal_fig = create_normal_plot(df, asset_name_display)
                if normal_fig:
                    st.plotly_chart(normal_fig, use_container_width=True)
                else:
                    st.write("No chart data available.")
            else:
                st.write("No data for selected period.")

    # If multiple assets, show a scaled plot for comparison below all assets
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
                    formatted_price = format_price(latest_price)
                    if diff is not None and pct_change is not None:
                        delta_str = f"{round(diff,2)} ({round(pct_change,2)}%)"
                        st.metric(label="Latest Price", value=formatted_price, delta=delta_str, label_visibility="collapsed")
                    else:
                        st.metric(label="Latest Price", value=formatted_price, label_visibility="collapsed")

                    normal_fig = create_normal_plot(df, asset_name_display)
                    if normal_fig:
                        st.plotly_chart(normal_fig, use_container_width=True)
                    else:
                        st.write("No chart data available.")
                else:
                    st.write("No data for selected period.")

        # Scaled plot for multiple assets
        if len(chosen_assets) > 1:
            st.subheader("Comparative Analysis (Scaled Plot)")
            scaled_fig = create_scaled_plot(df_dict)
            if scaled_fig:
                st.plotly_chart(scaled_fig, use_container_width=True)
            else:
                st.write("No comparative data available for the selected period.")
    else:
        st.info("Please select at least one asset for comparison.")