import ccxt
import requests
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

# Define Cache Directory
CACHE_DIR = Path("cache")

# Define the API base URL
LIQUIDATION_API_BASE_URL = os.getenv("LIQUIDATION_API_BASE_URL")


def fetch_ohlcv(
    symbol: str, timeframe: str, start_dt: datetime, end_dt: datetime
) -> pd.DataFrame:
    """
    Fetches OHLCV data from Binance using ccxt, utilizing a local Parquet cache.

    Args:
        symbol: Trading symbol (e.g., 'SUIUSDT').
        timeframe: Timeframe string (e.g., '5m', '1h').
        start_dt: Start datetime object (timezone-aware).
        end_dt: End datetime object (timezone-aware).

    Returns:
        Pandas DataFrame with OHLCV data, indexed by datetime.
        Columns: ['Open', 'High', 'Low', 'Close', 'Volume']
    """
    # Ensure cache directory exists
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Generate cache filename
    start_ts = int(start_dt.timestamp() * 1000)
    end_ts = int(end_dt.timestamp() * 1000)
    cache_file = CACHE_DIR / f"{symbol}_{timeframe}_ohlcv_{start_ts}_{end_ts}.parquet"

    # Check cache first
    if cache_file.exists():
        try:
            print(f"Cache hit: Loading OHLCV data from {cache_file}")
            df = pd.read_parquet(cache_file)
            # Ensure index is datetime after loading from parquet
            if not pd.api.types.is_datetime64_any_dtype(df.index):
                df.index = pd.to_datetime(df.index, utc=True)
            # Filter exact date range again after loading from cache
            df = df[(df.index >= start_dt) & (df.index < end_dt)]
            print(f"Loaded {len(df)} OHLCV candles from cache.")
            return df
        except Exception as e:
            print(f"Error reading cache file {cache_file}: {e}. Fetching from API.")

    print(
        f"Cache miss: Fetching OHLCV data for {symbol} ({timeframe}) from {start_dt} to {end_dt}..."
    )
    exchange = ccxt.binance()  # Using Binance public API
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    limit = 1000  # Binance limit per request

    all_ohlcv = []
    current_ms = start_ms

    while current_ms < end_ms:
        try:
            # Fetch up to 'limit' candles starting from 'current_ms'
            ohlcv = exchange.fetch_ohlcv(
                symbol, timeframe, since=current_ms, limit=limit
            )
            if not ohlcv:
                break  # No more data available

            all_ohlcv.extend(ohlcv)
            last_timestamp_ms = ohlcv[-1][0]

            # Check if the last timestamp is beyond the end_dt or if we received less data than limit
            if last_timestamp_ms >= end_ms or len(ohlcv) < limit:
                break  # Exit loop if we've reached the end date or fetched all available data

            # Move to the next timestamp after the last one received
            current_ms = last_timestamp_ms + exchange.parse_timeframe(timeframe) * 1000

        except ccxt.NetworkError as e:
            print(f"CCXT Network Error: {e}. Retrying...")
            exchange.sleep(5000)  # Wait 5 seconds before retrying
        except ccxt.ExchangeError as e:
            print(f"CCXT Exchange Error: {e}. Stopping.")
            break
        except Exception as e:
            print(f"An unexpected error occurred during OHLCV fetch: {e}")
            break

    if not all_ohlcv:
        print("No OHLCV data fetched.")
        return pd.DataFrame()

    df = pd.DataFrame(
        all_ohlcv, columns=["Timestamp", "Open", "High", "Low", "Close", "Volume"]
    )
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], unit="ms", utc=True)
    df = df.set_index("Timestamp")
    # Filter exact date range (fetch_ohlcv 'since' might include earlier data point)
    df = df[(df.index >= start_dt) & (df.index < end_dt)]
    print(f"Fetched {len(df)} OHLCV candles from API.")
    # Save to cache
    try:
        df.to_parquet(cache_file)
        print(f"Saved OHLCV data to cache: {cache_file}")
    except Exception as e:
        print(f"Error saving OHLCV data to cache file {cache_file}: {e}")
    return df


def fetch_liquidations(
    symbol: str, timeframe: str, start_dt: datetime, end_dt: datetime
) -> pd.DataFrame:
    """
    Fetches liquidation data from the custom API, utilizing a local Parquet cache.

    Args:
        symbol: Trading symbol (e.g., 'SUIUSDT').
        timeframe: Timeframe string (e.g., '5m').
        start_dt: Start datetime object (timezone-aware).
        end_dt: End datetime object (timezone-aware).

    Returns:
        Pandas DataFrame with liquidation data.
        Columns: ['timestamp', 'timestamp_iso', 'side', 'cumulated_usd_size']
    """
    # Ensure cache directory exists
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Generate cache filename
    start_ts_ms = int(start_dt.timestamp() * 1000)
    end_ts_ms = int(end_dt.timestamp() * 1000)
    cache_file = (
        CACHE_DIR
        / f"{symbol}_{timeframe}_liquidations_{start_ts_ms}_{end_ts_ms}.parquet"
    )

    # Check cache first
    if cache_file.exists():
        try:
            print(f"Cache hit: Loading liquidation data from {cache_file}")
            df = pd.read_parquet(cache_file)
            # Ensure timestamp column is datetime after loading from parquet
            if "timestamp" in df.columns and not pd.api.types.is_datetime64_any_dtype(
                df["timestamp"]
            ):
                df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            # Filter exact date range again after loading from cache
            df = df[(df["timestamp"] >= start_dt) & (df["timestamp"] < end_dt)]
            print(f"Loaded {len(df)} liquidation records from cache.")
            return df
        except Exception as e:
            print(f"Error reading cache file {cache_file}: {e}. Fetching from API.")

    print(
        f"Cache miss: Fetching liquidation data for {symbol} ({timeframe}) from {start_dt} to {end_dt}..."
    )
    start_ts_ms = int(start_dt.timestamp() * 1000)
    end_ts_ms = int(end_dt.timestamp() * 1000)

    params = {
        "symbol": symbol,
        "timeframe": timeframe,
        "start_timestamp": start_ts_ms,
        "end_timestamp": end_ts_ms,
    }
    try:
        # Set a longer timeout (e.g., 60 seconds)
        response = requests.get(LIQUIDATION_API_BASE_URL, params=params, timeout=60)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        data = response.json()
        if not data:
            print("No liquidation data received from API.")
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        # Ensure timestamp_iso is also parsed if needed later, though we primarily use 'timestamp'
        print(f"Fetched {len(df)} liquidation records from API.")
        # Save to cache
        try:
            # Drop timestamp_iso if it exists and causes issues with parquet
            if "timestamp_iso" in df.columns:
                df_to_save = df.drop(columns=["timestamp_iso"])
            else:
                df_to_save = df
            df_to_save.to_parquet(cache_file)
            print(f"Saved liquidation data to cache: {cache_file}")
        except Exception as e:
            print(f"Error saving liquidation data to cache file {cache_file}: {e}")
        return df

    except requests.exceptions.RequestException as e:
        print(f"Error fetching liquidation data: {e}")
        return pd.DataFrame()
    except Exception as e:
        print(f"An unexpected error occurred during liquidation fetch: {e}")
        return pd.DataFrame()


def prepare_data(
    symbol: str,
    timeframe: str,
    start_dt: datetime,
    end_dt: datetime,
    liquidation_aggregation_minutes: int = 5,
) -> pd.DataFrame:
    """
    Fetches OHLCV and liquidation data, then merges them.

    Args:
        symbol: Trading symbol (e.g., 'SUIUSDT').
        timeframe: Timeframe string (e.g., '1m').
        start_dt: Start datetime object (timezone-aware).
        end_dt: End datetime object (timezone-aware).
        liquidation_aggregation_minutes: Number of minutes over which to aggregate liquidation sums.

    Returns:
        Pandas DataFrame with OHLCV data merged with aggregated liquidation sizes.
        Columns: ['Open', 'High', 'Low', 'Close', 'Volume', 'Liq_Buy_Size', 'Liq_Sell_Size',
                  'Liq_Buy_Aggregated', 'Liq_Sell_Aggregated']
    """
    ohlcv_df = fetch_ohlcv(symbol, timeframe, start_dt, end_dt)
    liq_df = fetch_liquidations(symbol, timeframe, start_dt, end_dt)

    if ohlcv_df.empty:
        print("OHLCV data is empty, cannot proceed with merge.")
        return pd.DataFrame()

    if liq_df.empty:
        print(
            "Liquidation data is empty. Returning OHLCV data with zeroed liquidation columns."
        )
        ohlcv_df["Liq_Buy_Size"] = 0.0
        ohlcv_df["Liq_Sell_Size"] = 0.0
        # Also add aggregated columns as zero
        ohlcv_df["Liq_Buy_Aggregated"] = 0.0
        ohlcv_df["Liq_Sell_Aggregated"] = 0.0
        return ohlcv_df

    # Aggregate liquidations per OHLCV candle interval
    liq_df = liq_df.set_index("timestamp")

    buy_liq = liq_df[liq_df["side"] == "BUY"]["cumulated_usd_size"]
    sell_liq = liq_df[liq_df["side"] == "SELL"]["cumulated_usd_size"]

    resample_freq = (
        timeframe.replace("m", "min") if timeframe.endswith("m") else timeframe
    )
    agg_buy = buy_liq.resample(resample_freq, label="left", closed="left").sum()
    agg_sell = sell_liq.resample(resample_freq, label="left", closed="left").sum()

    merged_df = ohlcv_df.join(agg_buy.rename("Liq_Buy_Size")).join(
        agg_sell.rename("Liq_Sell_Size")
    )

    merged_df[["Liq_Buy_Size", "Liq_Sell_Size"]] = merged_df[
        ["Liq_Buy_Size", "Liq_Sell_Size"]
    ].fillna(0.0)

    # Calculate rolling sums over the specified aggregation window (in minutes)
    window = liquidation_aggregation_minutes
    merged_df["Liq_Buy_Aggregated"] = (
        merged_df["Liq_Buy_Size"].rolling(window=window, min_periods=1).sum().fillna(0)
    )
    merged_df["Liq_Sell_Aggregated"] = (
        merged_df["Liq_Sell_Size"].rolling(window=window, min_periods=1).sum().fillna(0)
    )

    print("Data preparation complete.")
    return merged_df
