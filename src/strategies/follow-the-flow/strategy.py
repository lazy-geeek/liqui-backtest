from backtesting import Strategy
import logging


class FollowTheFlowStrategy(Strategy):
    """
    A trading strategy that follows liquidation flows by entering trades in the
    direction of significant liquidation events.

    Requires input data to have columns: 'Liq_Buy_Size', 'Liq_Sell_Size',
    'Liq_Buy_Aggregated', 'Liq_Sell_Aggregated', 'Avg_Liq_Buy', 'Avg_Liq_Sell'
    in addition to standard OHLCV columns.
    """

    # --- Strategy Parameters ---
    average_liquidation_multiplier = 4.0
    stop_loss_percentage = 1.0
    take_profit_percentage = 2.0
    slippage_pct = 0.0005  # Default slippage (0.05%) as decimal, will be overridden
    pos_size_frac = 0.01  # Default position size fraction, will be overridden
    debug_mode = False
    modus = "both"  # 'buy', 'sell', or 'both'
    exit_on_opposite_signal = False  # Required for optimization compatibility
    liquidation_aggregation_minutes = (
        5  # Added missing parameter for backtesting library
    )
    average_lookback_period_days = 7  # Added missing parameter for backtesting library

    def init(self):
        """
        Initialize the strategy. Precompute indicators or series here if needed.
        """
        super().init()

        self.logger = logging.getLogger(__name__)

        # Make liquidation data easily accessible
        self.buy_liq = self.data.Liq_Buy_Size
        self.sell_liq = self.data.Liq_Sell_Size

        # Aggregated liquidation sums (short-term)
        self.buy_liq_agg = self.data.Liq_Buy_Aggregated
        self.sell_liq_agg = self.data.Liq_Sell_Aggregated

        # Average liquidation over lookback period (long-term)
        self.avg_buy_liq = self.data.Avg_Liq_Buy
        self.avg_sell_liq = self.data.Avg_Liq_Sell

        # Convert slippage percentage to decimal for calculations
        self.entry_slippage = (
            self.slippage_pct
        )  # Already a decimal from optimizer_run.py
        self.exit_slippage = (
            self.slippage_pct
        )  # Already a decimal from optimizer_run.py

        if self.debug_mode:
            self.logger.info(
                "Strategy initialized with parameters: %s",
                {
                    "average_liquidation_multiplier": self.average_liquidation_multiplier,
                    "stop_loss_percentage": self.stop_loss_percentage,
                    "take_profit_percentage": self.take_profit_percentage,
                    "modus": self.modus,
                    "slippage_pct": self.slippage_pct,
                    "pos_size_frac": self.pos_size_frac,
                    "exit_on_opposite_signal": self.exit_on_opposite_signal,
                },
            )

    def next(self):
        """
        Define the logic executed at each data point (candle).
        """
        try:
            super().next()

            # Enforce strict single-position policy: if any position is open, do nothing
            if self.position:
                return

            current_price = self.data.Close[-1]
            buy_liq_agg = self.data.Liq_Buy_Aggregated[-1]
            sell_liq_agg = self.data.Liq_Sell_Aggregated[-1]
            buy_threshold = self.avg_buy_liq[-1] * self.average_liquidation_multiplier
            sell_threshold = self.avg_sell_liq[-1] * self.average_liquidation_multiplier

            buy_signal = buy_liq_agg > buy_threshold
            sell_signal = sell_liq_agg > sell_threshold

            # --- Entry Logic ---
            if not self.position:
                if buy_signal and (self.modus == "buy" or self.modus == "both"):
                    sl_price = current_price * (1 - self.stop_loss_percentage / 100.0)
                    tp_price = current_price * (1 + self.take_profit_percentage / 100.0)
                    size_fraction = self.pos_size_frac  # Use the passed-in value
                    if self.debug_mode:
                        self.logger.info(
                            f"Executing BUY | Price: {current_price:.4f} | "
                            f"Size: {size_fraction*100:.1f}% equity | "
                            f"SL: {sl_price:.4f} | TP: {tp_price:.4f}"
                        )
                    self.buy(size=size_fraction, sl=sl_price, tp=tp_price)

                elif sell_signal and (self.modus == "sell" or self.modus == "both"):
                    sl_price = current_price * (1 + self.stop_loss_percentage / 100.0)
                    tp_price = current_price * (1 - self.take_profit_percentage / 100.0)
                    size_fraction = self.pos_size_frac  # Use the passed-in value
                    if self.debug_mode:
                        self.logger.info(
                            f"Executing SELL | Price: {current_price:.4f} | "
                            f"Size: {size_fraction*100:.1f}% equity | "
                            f"SL: {sl_price:.4f} | TP: {tp_price:.4f}"
                        )
                    self.sell(size=size_fraction, sl=sl_price, tp=tp_price)

        except Exception as e:
            if self.debug_mode:
                self.logger.error(f"Error in strategy execution: {str(e)}")
            raise
