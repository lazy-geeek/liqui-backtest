import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timezone
import json
import data_fetcher  # Import our data fetching module

# --- Configuration Loading ---
CONFIG_FILE = "config.json"


def load_config(config_path: str) -> dict:
    """Loads configuration from a JSON file."""
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        st.sidebar.success(f"Configuration loaded from {config_path}")
        return config
    except FileNotFoundError:
        st.error(f"Error: Configuration file not found at {config_path}")
        return None
    except json.JSONDecodeError:
        st.error(f"Error: Could not decode JSON from {config_path}")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred loading config: {e}")
        return None


# --- Main App Logic ---
st.set_page_config(layout="wide")  # Use wide layout for better chart display
st.title("Liquidation Backtest Data Viewer")

config = load_config(CONFIG_FILE)

if config:
    # Extract settings from config (using defaults if keys are missing)
    backtest_settings = config.get("backtest_settings", {})
    symbol = backtest_settings.get("symbol", "SUIUSDT")
    timeframe = backtest_settings.get("timeframe", "5m")
    start_date_str = backtest_settings.get("start_date_iso", "2025-01-01T00:00:00Z")
    end_date_str = backtest_settings.get("end_date_iso", "2025-04-01T00:00:00Z")

    # Display parameters in sidebar
    st.sidebar.header("Data Parameters")
    st.sidebar.text(f"Symbol: {symbol}")
    st.sidebar.text(f"Timeframe: {timeframe}")
    st.sidebar.text(f"Start Date: {start_date_str}")
    st.sidebar.text(f"End Date: {end_date_str}")

    # Parse dates
    try:
        # Ensure timezone-aware datetime objects
        start_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
        end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
    except ValueError as e:
        st.error(f"Error parsing date strings from config: {e}")
        st.stop()  # Stop execution if dates are invalid

    # Fetch data using data_fetcher
    st.info(
        f"Fetching data for {symbol} ({timeframe}) from {start_date} to {end_date}..."
    )
    with st.spinner("Loading data... This might take a moment."):
        try:
            data_df = data_fetcher.prepare_data(symbol, timeframe, start_date, end_date)
        except Exception as e:
            st.error(f"An error occurred during data fetching: {e}")
            data_df = pd.DataFrame()  # Ensure data_df exists even on error

    if not data_df.empty:
        st.success("Data loaded successfully!")
        st.dataframe(data_df.head())  # Show a preview of the data

        # --- Chart Creation (Placeholder for next step) ---
        st.subheader("Liquidation Charts")
        # Create Buy Liquidations Chart
        buy_chart = px.bar(
            data_df,
            x=data_df.index,
            y="Liq_Buy_Size",
            title="Buy Liquidations (USD)",
            labels={"index": "Timestamp", "Liq_Buy_Size": "Liquidation Amount (USD)"},
            color_discrete_sequence=px.colors.qualitative.Pastel,  # Optional: Use a color scheme
        )
        buy_chart.update_layout(
            xaxis_title="Timestamp", yaxis_title="Buy Liquidation Amount (USD)"
        )
        st.plotly_chart(buy_chart, use_container_width=True)

        # Create Sell Liquidations Chart
        sell_chart = px.bar(
            data_df,
            x=data_df.index,
            y="Liq_Sell_Size",
            title="Sell Liquidations (USD)",
            labels={"index": "Timestamp", "Liq_Sell_Size": "Liquidation Amount (USD)"},
            color_discrete_sequence=px.colors.qualitative.Pastel1,  # Optional: Use a different color scheme
        )
        sell_chart.update_layout(
            xaxis_title="Timestamp", yaxis_title="Sell Liquidation Amount (USD)"
        )
        st.plotly_chart(sell_chart, use_container_width=True)

        # Charts are now generated above

    elif data_df is None:  # Handle case where prepare_data might return None on error
        st.warning("Data fetching returned None. Cannot display charts.")
    else:  # Handle empty DataFrame case
        st.warning(
            "No data available for the selected parameters. Cannot display charts."
        )

else:
    st.warning("Could not load configuration. Cannot proceed.")
