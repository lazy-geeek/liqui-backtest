import os
import pandas as pd
import numpy as np
from datetime import (
    timedelta,
    timezone,
    datetime as dt_datetime,
)  # Alias to avoid conflict

from freqtrade.strategy import (
    IStrategy,
    IntParameter,
    DecimalParameter,
    CategoricalParameter,
)

# Assuming these modules are in freqtrade_app/src and Python's import system can find them
# This might require setting PYTHONPATH or structuring as a package.
# For now, assume they are discoverable (e.g. if ft_runner.py is in freqtrade_app/ and src is in PYTHONPATH)
# Or, more robustly, use relative imports if this becomes part of a package recognized by freqtrade
# from ...src import liquidation_fetcher, liquidation_processor # Example if src is a package level up
# For now, direct import assuming PYTHONPATH is set or they are in a discoverable path
import sys
from pathlib import Path

ft_user_data_strategies = Path("ft_user_data/strategies")
sys.path.insert(0, str(ft_user_data_strategies))

from src import liquidation_fetcher
from src import liquidation_processor
from src.ft_config_loader import get_global_settings


class FollowTheFlowStrategy(IStrategy):
    # --- Strategy Parameters (Hyperoptable) ---
    # These will be loaded from the strategy's settings.toml by Freqtrade if defined there,
    # or can be optimized by Hyperopt.

    # Default values, can be overridden by config or hyperopt
    average_liquidation_multiplier = DecimalParameter(
        2.0, 8.0, default=4.0, decimals=1, space="buy", optimize=True, load=True
    )

    # Using separate stoploss/takeprofit for long/short if desired, or a general one
    stop_loss_percentage = DecimalParameter(
        0.5, 5.0, default=1.0, decimals=1, space="buy", optimize=True, load=True
    )
    take_profit_percentage = DecimalParameter(
        1.0, 10.0, default=2.0, decimals=1, space="buy", optimize=True, load=True
    )

    exit_on_opposite_signal = CategoricalParameter(
        [True, False], default=False, space="buy", optimize=True, load=True
    )
    modus = CategoricalParameter(
        ["buy", "sell", "both"], default="both", space="buy", optimize=True, load=True
    )

    # Data preparation parameters (can also be hyperoptable if desired)
    liquidation_aggregation_minutes = IntParameter(
        1, 60, default=5, space="buy", optimize=True, load=True
    )
    average_lookback_period_days = IntParameter(
        1, 30, default=14, space="buy", optimize=True, load=True
    )

    # --- Strategy Configuration ---
    timeframe = "5m"  # Default, can be overridden by Freqtrade config

    # Stoploss is defined as a percentage of current price
    # Freqtrade expects stoploss to be negative, e.g. -0.01 for 1%
    # This is handled by how it's used in `custom_stoploss` or by setting `stoploss` attribute directly.
    # We will set the `stoploss` attribute directly using the percentage.
    # stoploss = - (stop_loss_percentage.value / 100.0) # This needs to be dynamic based on loaded param

    # Minimal ROI table:
    # This means: 0% profit after 0 minutes (this is often a dummy entry if using TP from signals)
    # minimal_roi = {"0": (take_profit_percentage.value / 100.0) } # Dynamic based on loaded param

    # Trailing stop:
    # trailing_stop = False
    # trailing_stop_positive = 0.01
    # trailing_stop_positive_offset = 0.02
    # trailing_only_offset_is_reached = True

    # --- Startup Candle Count ---
    # Calculate based on the longest lookback period.
    # (average_lookback_period_days * 24 hours * (60 minutes / timeframe_in_minutes))
    # This needs to be calculated based on the default or loaded `average_lookback_period_days`
    # and `timeframe`. Freqtrade will call `bot_loop_start` where we can finalize this.

    # For now, a sufficiently large static value or calculate from defaults:
    # Example: 14 days for 5m timeframe: 14 * 24 * (60/5) = 14 * 24 * 12 = 4032
    # This will be set more dynamically in `bot_loop_start` if params are loaded.
    # startup_candle_count: int = 4032 # Placeholder, will be refined

    # API URL for liquidations - to be fetched from config or environment
    _liquidation_api_url = None

    def __init__(self, config: dict) -> None:
        super().__init__(config)

        # Dynamically set stoploss and ROI based on loaded parameters
        self.stoploss = -(self.stop_loss_percentage.value / 100.0)
        self.minimal_roi = {"0": (self.take_profit_percentage.value / 100.0)}

    @property
    def startup_candle_count(self) -> int:
        # Calculate startup_candle_count dynamically based on average_lookback_period_days
        # and the strategy's timeframe.
        timeframe_minutes = self.timeframe_to_minutes(self.timeframe)
        if timeframe_minutes == 0:  # Should not happen with valid timeframes
            return 200  # Fallback default

        # average_lookback_period_days is an IntParameter, access its value
        lookback_days = self.average_lookback_period_days.value

        # Candles per day = (24 * 60) / timeframe_minutes
        candles_per_day = (24 * 60) / timeframe_minutes
        required_candles = int(lookback_days * candles_per_day)

        # Add a small buffer, e.g., for one aggregation window
        agg_minutes = self.liquidation_aggregation_minutes.value
        agg_candles_buffer = (
            int(agg_minutes / timeframe_minutes) if timeframe_minutes > 0 else 0
        )

        return required_candles + agg_candles_buffer + 50  # Add 50 for general buffer

    def informative_pairs(self):
        # No informative pairs needed for this strategy as it's single-asset based on custom data
        return []

    def populate_indicators(
        self, dataframe: pd.DataFrame, metadata: dict
    ) -> pd.DataFrame:
        """
        Adds custom indicators to the dataframe.
        """
        if self._liquidation_api_url is None:
            print(
                f"ERROR: Liquidation API URL is not set for strategy {self.get_strategy_name()}. Cannot fetch liquidations."
            )
            # Add empty columns to prevent crashes downstream if strategy expects them
            for col in [
                "Liq_Buy_Size",
                "Liq_Sell_Size",
                "Liq_Buy_Aggregated",
                "Liq_Sell_Aggregated",
                "Avg_Liq_Buy",
                "Avg_Liq_Sell",
            ]:
                dataframe[col] = 0.0
            return dataframe

        # --- Fetch Liquidation Data ---
        symbol_for_api = metadata["pair"].replace(
            "/", ""
        )  # e.g., "BTC/USDT" -> "BTCUSDT"

        # Determine date range for fetching. Freqtrade provides data in chunks.
        # We need liquidations covering the range of the current dataframe.
        # Add a buffer to start_dt to ensure lookback data for averages is available.
        # The `startup_candle_count` should ideally handle pre-loading enough data,
        # but for processing, we fetch for the exact range of the current `dataframe`.

        # Calculate buffer needed for average_lookback_period_days
        # timeframe_delta = pd.to_timedelta(IStrategy.timeframe_to_prev_date(self.timeframe, dataframe.index[-1]) -
        #                                IStrategy.timeframe_to_prev_date(self.timeframe, dataframe.index[-2]))
        # This is complex; simpler to rely on startup_candle_count providing enough history in `dataframe`
        # and fetch liquidations for the exact range of the current `dataframe`.

        start_dt_utc = dataframe.index.min().to_pydatetime()
        end_dt_utc = dataframe.index.max().to_pydatetime()

        # Ensure they are timezone-aware (Freqtrade dataframes are UTC indexed)
        if start_dt_utc.tzinfo is None:
            start_dt_utc = start_dt_utc.replace(tzinfo=timezone.utc)
        if end_dt_utc.tzinfo is None:
            end_dt_utc = end_dt_utc.replace(tzinfo=timezone.utc)

        print(
            f"Populate indicators for {metadata['pair']}: Fetching liquidations from {start_dt_utc} to {end_dt_utc}"
        )

        raw_liq_df = liquidation_fetcher.fetch_liquidations(
            symbol=symbol_for_api,
            start_dt=start_dt_utc,
            end_dt=end_dt_utc,
            api_base_url=self._liquidation_api_url,
            # cache_dir can be default or configured if needed
        )

        # --- Process Liquidation Data ---
        strategy_params_for_processor = {
            "liquidation_aggregation_minutes": self.liquidation_aggregation_minutes.value,
            "average_lookback_period_days": self.average_lookback_period_days.value,
        }

        dataframe = liquidation_processor.process_liquidation_data(
            ohlcv_df=dataframe,
            raw_liq_df=raw_liq_df,
            strategy_params=strategy_params_for_processor,
            timeframe_str=self.timeframe,
        )

        # print(f"Dataframe after processing for {metadata['pair']} from {start_dt_utc} to {end_dt_utc}:")
        # print(dataframe[['close', 'Liq_Buy_Size', 'Liq_Sell_Size', 'Liq_Buy_Aggregated', 'Liq_Sell_Aggregated', 'Avg_Liq_Buy', 'Avg_Liq_Sell']].tail())

        return dataframe

    def populate_entry_trend(
        self, dataframe: pd.DataFrame, metadata: dict
    ) -> pd.DataFrame:
        """
        Based on TA indicators, populates the 'enter_long' and 'enter_short' columns.
        """
        # --- Entry Conditions ---
        # Ensure all required columns exist (populated by populate_indicators)
        required_cols = [
            "Avg_Liq_Buy",
            "Avg_Liq_Sell",
            "Liq_Buy_Aggregated",
            "Liq_Sell_Aggregated",
        ]
        if not all(col in dataframe.columns for col in required_cols):
            print(
                f"WARNING: Missing one or more required columns for entry logic in {metadata['pair']}. Columns: {dataframe.columns.tolist()}"
            )
            dataframe["enter_long"] = 0
            dataframe["enter_short"] = 0
            return dataframe

        buy_threshold = (
            dataframe["Avg_Liq_Buy"] * self.average_liquidation_multiplier.value
        )
        sell_threshold = (
            dataframe["Avg_Liq_Sell"] * self.average_liquidation_multiplier.value
        )

        can_buy = self.modus.value == "buy" or self.modus.value == "both"
        can_sell = (
            self.modus.value == "sell" or self.modus.value == "both"
        )  # For shorting

        # Long entry
        if can_buy:
            enter_long_condition = dataframe["Liq_Buy_Aggregated"] > buy_threshold
            dataframe.loc[enter_long_condition, ["enter_long", "enter_tag"]] = (
                1,
                "ftf_buy_signal",
            )
        else:
            dataframe["enter_long"] = 0  # Explicitly set to 0 if not buying

        # Short entry (Freqtrade needs `can_short = True` in config for this to be actioned)
        if can_sell:
            enter_short_condition = dataframe["Liq_Sell_Aggregated"] > sell_threshold
            dataframe.loc[enter_short_condition, ["enter_short", "enter_tag"]] = (
                1,
                "ftf_sell_signal",
            )
        else:
            dataframe["enter_short"] = 0  # Explicitly set to 0 if not shorting

        return dataframe

    def populate_exit_trend(
        self, dataframe: pd.DataFrame, metadata: dict
    ) -> pd.DataFrame:
        """
        Based on TA indicators, populates the 'exit_long' and 'exit_short' columns.
        """
        if not self.exit_on_opposite_signal.value:
            dataframe["exit_long"] = (
                0  # No custom exit signal if not exiting on opposite
            )
            dataframe["exit_short"] = 0
            return dataframe

        # --- Exit on Opposite Signal Logic ---
        # Ensure all required columns exist
        required_cols = [
            "Avg_Liq_Buy",
            "Avg_Liq_Sell",
            "Liq_Buy_Aggregated",
            "Liq_Sell_Aggregated",
        ]
        if not all(col in dataframe.columns for col in required_cols):
            print(
                f"WARNING: Missing one or more required columns for exit logic in {metadata['pair']}. Columns: {dataframe.columns.tolist()}"
            )
            dataframe["exit_long"] = 0
            dataframe["exit_short"] = 0
            return dataframe

        buy_threshold = (
            dataframe["Avg_Liq_Buy"] * self.average_liquidation_multiplier.value
        )
        sell_threshold = (
            dataframe["Avg_Liq_Sell"] * self.average_liquidation_multiplier.value
        )

        can_buy = self.modus.value == "buy" or self.modus.value == "both"
        can_sell = self.modus.value == "sell" or self.modus.value == "both"

        # Exit long if sell signal appears
        if can_sell:  # Check if selling is even allowed by modus
            exit_long_condition = dataframe["Liq_Sell_Aggregated"] > sell_threshold
            dataframe.loc[exit_long_condition, ["exit_long", "exit_tag"]] = (
                1,
                "exit_opposite_sell",
            )
        else:
            dataframe["exit_long"] = 0

        # Exit short if buy signal appears
        if can_buy:  # Check if buying is even allowed by modus
            exit_short_condition = dataframe["Liq_Buy_Aggregated"] > buy_threshold
            dataframe.loc[exit_short_condition, ["exit_short", "exit_tag"]] = (
                1,
                "exit_opposite_buy",
            )
        else:
            dataframe["exit_short"] = 0

        return dataframe

    # Optional: Custom stoploss (if more complex than a static percentage)
    # def custom_stoploss(self, pair: str, trade: 'Trade', current_time: 'datetime',
    #                     current_rate: float, current_profit: float, **kwargs) -> float:
    #     stoploss_pct = self.stop_loss_percentage.value / 100.0
    #     return stoploss_pct # Positive value for Freqtrade custom_stoploss

    # Optional: Custom exit conditions not covered by ROI, stoploss, or populate_exit_trend
    # def custom_exit(self, pair: str, trade: 'Trade', current_time: 'datetime', current_rate: float,
    #                 current_profit: float, **kwargs):
    #     # Example: Exit after N candles
    #     # if current_time - trade.open_date_utc > timedelta(minutes=self.hold_duration_minutes.value):
    #     #     return 'hold_timeout'
    #     pass

    # This is called when Freqtrade is shutting down.
    # def bot_loop_end(self, **kwargs) -> None:
    #     pass
