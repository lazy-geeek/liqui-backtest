import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def prepare_strategy_data(
    ohlcv_df: pd.DataFrame,
    liq_df: pd.DataFrame,
    strategy_params: dict,
    start_dt: datetime,
    end_dt: datetime,
    timeframe: str,
) -> pd.DataFrame:
    """
    Prepares data specifically for the CounterTrade strategy by merging
    OHLCV and liquidation data, calculating aggregated and average liquidations.

    Args:
        ohlcv_df: DataFrame with OHLCV data. Must cover the period from
                  start_dt - average_lookback_period_days to end_dt.
        liq_df: DataFrame with raw liquidation data. Must cover the same period.
        strategy_params: Dictionary containing strategy-specific parameters like:
            - liquidation_aggregation_minutes (int): Aggregation window.
            - average_lookback_period_days (int): Lookback for average calculation.
        start_dt: The original start datetime for the backtest period.
        end_dt: The original end datetime for the backtest period.
        timeframe: The timeframe string (e.g., '1m', '5m').

    Returns:
        Pandas DataFrame ready for the backtesting engine, filtered to the
        original start_dt and end_dt.
    """
    liquidation_aggregation_minutes = strategy_params.get(
        "liquidation_aggregation_minutes", 5
    )  # Default if not provided
    average_lookback_period_days = strategy_params.get(
        "average_lookback_period_days", 14
    )  # Default if not provided

    if ohlcv_df.empty:
        print("OHLCV data is empty, cannot proceed with merge.")
        return pd.DataFrame()

    if liq_df.empty:
        print(
            "Liquidation data is empty. Returning OHLCV data with zeroed liquidation columns."
        )
        ohlcv_df["Liq_Buy_Size"] = 0.0
        ohlcv_df["Liq_Sell_Size"] = 0.0
        ohlcv_df["Liq_Buy_Aggregated"] = 0.0
        ohlcv_df["Liq_Sell_Aggregated"] = 0.0
        ohlcv_df["Avg_Liq_Buy"] = 0.0
        ohlcv_df["Avg_Liq_Sell"] = 0.0
        # Filter to original start_dt before returning
        ohlcv_df = ohlcv_df[(ohlcv_df.index >= start_dt) & (ohlcv_df.index < end_dt)]
        return ohlcv_df.fillna(0)  # Ensure NaNs are filled

    # Ensure liq_df has a datetime index
    if "timestamp" in liq_df.columns:
        liq_df = liq_df.set_index("timestamp")
    elif not pd.api.types.is_datetime64_any_dtype(liq_df.index):
        print("Error: liq_df must have a datetime index or a 'timestamp' column.")
        # Return OHLCV with zeros, filtered
        ohlcv_df["Liq_Buy_Size"] = 0.0
        ohlcv_df["Liq_Sell_Size"] = 0.0
        ohlcv_df["Liq_Buy_Aggregated"] = 0.0
        ohlcv_df["Liq_Sell_Aggregated"] = 0.0
        ohlcv_df["Avg_Liq_Buy"] = 0.0
        ohlcv_df["Avg_Liq_Sell"] = 0.0
        ohlcv_df = ohlcv_df[(ohlcv_df.index >= start_dt) & (ohlcv_df.index < end_dt)]
        return ohlcv_df.fillna(0)

    buy_liq = liq_df[liq_df["side"] == "BUY"]["cumulated_usd_size"]
    sell_liq = liq_df[liq_df["side"] == "SELL"]["cumulated_usd_size"]

    # Determine resampling frequency based on timeframe
    resample_freq = timeframe
    if timeframe.endswith("m"):
        resample_freq = timeframe.replace("m", "min")  # Use 'min' for minutes (updated)
    elif timeframe.endswith("h"):
        resample_freq = timeframe.replace("h", "H")  # Use 'H' for hours
    elif timeframe.endswith("d"):
        resample_freq = timeframe.replace("d", "D")  # Use 'D' for days
    # Add more cases if needed (e.g., 's' for seconds)

    try:
        agg_buy = buy_liq.resample(resample_freq, label="left", closed="left").sum()
        agg_sell = sell_liq.resample(resample_freq, label="left", closed="left").sum()
    except ValueError as e:
        print(f"Error during resampling with frequency '{resample_freq}': {e}")
        print("Check if the timeframe string is compatible with pandas resampling.")
        # Return OHLCV with zeros, filtered
        ohlcv_df["Liq_Buy_Size"] = 0.0
        ohlcv_df["Liq_Sell_Size"] = 0.0
        ohlcv_df["Liq_Buy_Aggregated"] = 0.0
        ohlcv_df["Liq_Sell_Aggregated"] = 0.0
        ohlcv_df["Avg_Liq_Buy"] = 0.0
        ohlcv_df["Avg_Liq_Sell"] = 0.0
        ohlcv_df = ohlcv_df[(ohlcv_df.index >= start_dt) & (ohlcv_df.index < end_dt)]
        return ohlcv_df.fillna(0)

    # Join aggregated liquidations with OHLCV data
    # Ensure ohlcv_df index is timezone-aware (should be from fetch_ohlcv)
    if ohlcv_df.index.tz is None:
        ohlcv_df.index = ohlcv_df.index.tz_localize("UTC")  # Assuming UTC if not set

    # Ensure agg_buy/agg_sell indices are timezone-aware and match ohlcv_df
    if agg_buy.index.tz is None:
        agg_buy.index = agg_buy.index.tz_localize("UTC")
    if agg_sell.index.tz is None:
        agg_sell.index = agg_sell.index.tz_localize("UTC")

    # Align timezones if they differ (prefer UTC)
    if ohlcv_df.index.tz != agg_buy.index.tz:
        agg_buy.index = agg_buy.index.tz_convert(ohlcv_df.index.tz)
    if ohlcv_df.index.tz != agg_sell.index.tz:
        agg_sell.index = agg_sell.index.tz_convert(ohlcv_df.index.tz)

    merged_df = ohlcv_df.join(agg_buy.rename("Liq_Buy_Size"), how="left").join(
        agg_sell.rename("Liq_Sell_Size"), how="left"
    )

    merged_df[["Liq_Buy_Size", "Liq_Sell_Size"]] = merged_df[
        ["Liq_Buy_Size", "Liq_Sell_Size"]
    ].fillna(0.0)

    # Rolling sum over aggregation window (short-term)
    # Ensure window is at least 1
    window = max(1, liquidation_aggregation_minutes)
    merged_df["Liq_Buy_Aggregated"] = (
        merged_df["Liq_Buy_Size"].rolling(window=window, min_periods=1).sum()
    )
    merged_df["Liq_Sell_Aggregated"] = (
        merged_df["Liq_Sell_Size"].rolling(window=window, min_periods=1).sum()
    )

    # Rolling average over lookback period (long-term)
    # Calculate number of periods in lookback window based on timeframe frequency
    try:
        # Use pandas to infer frequency if possible, otherwise parse manually
        if hasattr(ohlcv_df.index, "freqstr") and ohlcv_df.index.freqstr:
            tf_delta = pd.Timedelta(ohlcv_df.index.freqstr)
        else:
            # Manual parsing as fallback
            if timeframe.endswith("m"):
                tf_minutes = int(timeframe[:-1])
            elif timeframe.endswith("h"):
                tf_minutes = int(timeframe[:-1]) * 60
            elif timeframe.endswith("d"):
                tf_minutes = int(timeframe[:-1]) * 60 * 24
            else:
                # Attempt to infer from median difference if no freq/suffix
                median_diff = ohlcv_df.index.to_series().diff().median()
                if pd.isna(median_diff):
                    print(
                        "Warning: Could not determine timeframe frequency reliably. Defaulting to 1 minute."
                    )
                    tf_minutes = 1
                else:
                    tf_minutes = median_diff.total_seconds() / 60
            tf_delta = timedelta(minutes=tf_minutes)

        lookback_delta = timedelta(days=average_lookback_period_days)
        # Calculate periods based on timedelta division
        lookback_periods = int(lookback_delta / tf_delta)
        lookback_periods = max(1, lookback_periods)  # Ensure at least 1 period

    except Exception as e:
        print(f"Error calculating lookback periods: {e}. Defaulting to 1 period.")
        lookback_periods = 1  # Fallback

    merged_df["Avg_Liq_Buy"] = (
        merged_df["Liq_Buy_Size"]
        .replace(0, np.nan)  # Replace 0 with NaN for mean calculation
        .rolling(window=lookback_periods, min_periods=1)
        .mean()
    )
    merged_df["Avg_Liq_Sell"] = (
        merged_df["Liq_Sell_Size"]
        .replace(0, np.nan)  # Replace 0 with NaN for mean calculation
        .rolling(window=lookback_periods, min_periods=1)
        .mean()
    )

    # Filter to the original requested date range AFTER calculations
    merged_df = merged_df[(merged_df.index >= start_dt) & (merged_df.index < end_dt)]

    # Final fillna(0) to handle any NaNs introduced by rolling/joining/replacing
    # especially for Avg columns where initial periods might be NaN
    merged_df = merged_df.fillna(0)

    return merged_df
