import pandas as pd
import numpy as np


def _timeframe_to_minutes(timeframe_str: str) -> int:
    """Converts Freqtrade timeframe string to total minutes."""
    # Simplified: '1m'=1, '5m'=5, '15m'=15, '30m'=30, '1h'=60, '4h'=240, '1d'=1440
    # A more robust solution would parse units and values.
    if "m" in timeframe_str:
        return int(timeframe_str.replace("m", ""))
    elif "h" in timeframe_str:
        return int(timeframe_str.replace("h", "")) * 60
    elif "d" in timeframe_str:
        return int(timeframe_str.replace("d", "")) * 24 * 60
    raise ValueError(f"Unsupported timeframe string format: {timeframe_str}")


def process_liquidation_data(
    ohlcv_df: pd.DataFrame,
    raw_liq_df: pd.DataFrame,
    strategy_params: dict,
    timeframe_str: str,  # e.g., "5m", "1h"
) -> pd.DataFrame:
    """
    Processes raw liquidation data and merges it with OHLCV data.

    Args:
        ohlcv_df: DataFrame with OHLCV data (DatetimeIndex UTC).
        raw_liq_df: DataFrame with raw liquidation data (cols: timestamp, side, quantity, price).
                    'timestamp' should be datetime64[ns, UTC].
        strategy_params: Dict with 'liquidation_aggregation_minutes' and 'average_lookback_period_days'.
        timeframe_str: The timeframe of the ohlcv_df (e.g., "5m").

    Returns:
        DataFrame: ohlcv_df augmented with liquidation features:
                   Liq_Buy_Size, Liq_Sell_Size,
                   Liq_Buy_Aggregated, Liq_Sell_Aggregated,
                   Avg_Liq_Buy, Avg_Liq_Sell.
    """
    if ohlcv_df.empty:
        # If no ohlcv_df, cannot proceed
        # Add empty columns expected by strategy to avoid errors later
        for col in [
            "Liq_Buy_Size",
            "Liq_Sell_Size",
            "Liq_Buy_Aggregated",
            "Liq_Sell_Aggregated",
            "Avg_Liq_Buy",
            "Avg_Liq_Sell",
        ]:
            ohlcv_df[col] = 0.0
        return ohlcv_df

    # Ensure ohlcv_df index is UTC (Freqtrade usually ensures this)
    if ohlcv_df.index.tz is None:
        ohlcv_df.index = ohlcv_df.index.tz_localize("UTC")
    elif (
        ohlcv_df.index.tz.utcoffset(ohlcv_df.index[0])
        != pd.Timestamp(0, tz="UTC").utcoffset()
    ):
        ohlcv_df.index = ohlcv_df.index.tz_convert("UTC")

    if raw_liq_df.empty:
        print("No raw liquidation data provided. Adding empty liquidation columns.")
        ohlcv_df["Liq_Buy_Size"] = 0.0
        ohlcv_df["Liq_Sell_Size"] = 0.0
        ohlcv_df["Liq_Buy_Aggregated"] = 0.0
        ohlcv_df["Liq_Sell_Aggregated"] = 0.0
        ohlcv_df["Avg_Liq_Buy"] = 0.0
        ohlcv_df["Avg_Liq_Sell"] = 0.0
        return ohlcv_df

    liq_df = raw_liq_df.copy()

    # Ensure liquidation timestamps are datetime and UTC, and set as index
    if not pd.api.types.is_datetime64_any_dtype(liq_df["timestamp"]):
        liq_df["timestamp"] = pd.to_datetime(liq_df["timestamp"], utc=True)
    elif liq_df["timestamp"].dt.tz is None:  # If datetime but not localized
        liq_df["timestamp"] = liq_df["timestamp"].dt.tz_localize("UTC")
    elif (
        liq_df["timestamp"].dt.tz.utcoffset(liq_df["timestamp"].iloc[0])
        != pd.Timestamp(0, tz="UTC").utcoffset()
    ):
        liq_df["timestamp"] = liq_df["timestamp"].dt.tz_convert("UTC")

    liq_df = liq_df.set_index("timestamp")

    # Resample liquidations to the OHLCV timeframe (e.g., "5m", "1h")
    # Freqtrade timeframe strings are directly usable by pandas resample.
    resample_rule = timeframe_str

    # Sum 'quantity' for 'BUY' and 'SELL' liquidations separately
    liq_buy_size = (
        liq_df[liq_df["side"] == "BUY"]["quantity"].resample(resample_rule).sum()
    )
    liq_sell_size = (
        liq_df[liq_df["side"] == "SELL"]["quantity"].resample(resample_rule).sum()
    )

    # Create a temporary DataFrame aligned with ohlcv_df's index to hold resampled data
    df_resampled_liq = pd.DataFrame(index=ohlcv_df.index)
    df_resampled_liq["Liq_Buy_Size"] = liq_buy_size
    df_resampled_liq["Liq_Sell_Size"] = liq_sell_size

    # Fill NaNs that result from resampling (if no liquidations in a candle) with 0
    df_resampled_liq.fillna(0.0, inplace=True)

    # Join with ohlcv_df. Use 'left' to keep all ohlcv_df rows.
    # Any timestamps in df_resampled_liq not in ohlcv_df will be dropped.
    # Any timestamps in ohlcv_df not in df_resampled_liq will have NaN, then filled.
    augmented_df = ohlcv_df.join(df_resampled_liq, how="left")
    augmented_df[["Liq_Buy_Size", "Liq_Sell_Size"]] = augmented_df[
        ["Liq_Buy_Size", "Liq_Sell_Size"]
    ].fillna(0.0)

    # Calculate aggregation windows in terms of number of candles
    candle_duration_minutes = _timeframe_to_minutes(timeframe_str)

    agg_minutes = strategy_params.get("liquidation_aggregation_minutes", 5)
    # Ensure window is at least 1
    aggregation_window_candles = max(1, int(agg_minutes / candle_duration_minutes))

    avg_lookback_days = strategy_params.get("average_lookback_period_days", 14)
    avg_lookback_minutes = avg_lookback_days * 24 * 60
    # Ensure window is at least 1
    average_window_candles = max(1, int(avg_lookback_minutes / candle_duration_minutes))

    # Calculate Aggregated Liquidations (rolling sum)
    augmented_df["Liq_Buy_Aggregated"] = (
        augmented_df["Liq_Buy_Size"]
        .rolling(window=aggregation_window_candles, min_periods=1)
        .sum()
    )
    augmented_df["Liq_Sell_Aggregated"] = (
        augmented_df["Liq_Sell_Size"]
        .rolling(window=aggregation_window_candles, min_periods=1)
        .sum()
    )

    # Calculate Average Liquidations (rolling mean)
    augmented_df["Avg_Liq_Buy"] = (
        augmented_df["Liq_Buy_Size"]
        .rolling(window=average_window_candles, min_periods=1)
        .mean()
    )
    augmented_df["Avg_Liq_Sell"] = (
        augmented_df["Liq_Sell_Size"]
        .rolling(window=average_window_candles, min_periods=1)
        .mean()
    )

    # Fill any NaNs that might have been introduced by rolling operations (at the start of the series)
    cols_to_fill = [
        "Liq_Buy_Aggregated",
        "Liq_Sell_Aggregated",
        "Avg_Liq_Buy",
        "Avg_Liq_Sell",
    ]
    augmented_df[cols_to_fill] = augmented_df[cols_to_fill].fillna(0.0)

    return augmented_df
