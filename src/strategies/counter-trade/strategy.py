from backtesting import Strategy


class CounterTradeStrategy(Strategy):
    """
    A trading strategy based on aggregated liquidation data.

    Requires input data to have columns: 'Liq_Buy_Size', 'Liq_Sell_Size'
    in addition to standard OHLCV columns.
    """

    # --- Strategy Parameters ---
    # These will be injected by backtesting.py from the config file.
    # Default values here are placeholders if not provided via run() or optimize().
    average_liquidation_multiplier = 4.0
    stop_loss_percentage = 1.0
    take_profit_percentage = 2.0
    exit_on_opposite_signal = False
    slippage_pct = 0.0005  # Default slippage (0.05%) as decimal, will be overridden
    pos_size_frac = 0.01  # Default position size fraction, will be overridden
    debug_mode = False
    modus = "both"
    cooldown_candles = 0  # Number of candles to wait after signal before trading
    liquidation_aggregation_minutes = (
        5  # Added missing parameter for backtesting library
    )
    average_lookback_period_days = 14  # Added missing parameter for backtesting library

    def init(self):
        """
        Initialize the strategy. Precompute indicators or series here if needed.
        """

        super().init()

        # Cooldown state tracking
        self.signal_cooldown_counter = 0
        self.pending_trade_type = None  # 'buy' or 'sell'

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

    def next(self):
        """
        Define the logic executed at each data point (candle).
        """

        super().next()

        # --- Cooldown Management ---
        trade_ready_after_cooldown = False
        if self.signal_cooldown_counter > 0:
            self.signal_cooldown_counter -= 1
            if self.signal_cooldown_counter == 0 and self.pending_trade_type:
                # Cooldown just finished, mark trade as ready
                trade_ready_after_cooldown = True

        # --- Position Check ---
        # Enforce strict single-position policy: if any position is open, do nothing
        # (Unless executing the trade that just finished cooldown)
        if self.position and not trade_ready_after_cooldown:
            return

        current_price = self.data.Close[-1]
        buy_liq_agg = self.data.Liq_Buy_Aggregated[-1]
        sell_liq_agg = self.data.Liq_Sell_Aggregated[-1]
        buy_threshold = self.avg_buy_liq[-1] * self.average_liquidation_multiplier
        sell_threshold = self.avg_sell_liq[-1] * self.average_liquidation_multiplier

        buy_signal = buy_liq_agg > buy_threshold
        sell_signal = sell_liq_agg > sell_threshold

        # --- Exit on Opposite Signal Logic ---
        if self.position and self.exit_on_opposite_signal:
            if self.position.is_long and sell_signal:
                if self.debug_mode:
                    print(
                        f"DEBUG: Exiting LONG position due to opposite (SELL) signal at {current_price:.4f}"
                    )
                self.position.close()
                # No return here, let the rest of the logic run if needed (e.g., cooldown reset)

            elif self.position.is_short and buy_signal:
                if self.debug_mode:
                    print(
                        f"DEBUG: Exiting SHORT position due to opposite (BUY) signal at {current_price:.4f}"
                    )
                self.position.close()
                # No return here

        # --- Trade Execution (After Cooldown) ---
        # Execute trade if cooldown just finished
        if trade_ready_after_cooldown:
            if self.pending_trade_type == "buy" and (
                self.modus == "buy" or self.modus == "both"
            ):
                sl_price = current_price * (1 - self.stop_loss_percentage / 100.0)
                tp_price = current_price * (1 + self.take_profit_percentage / 100.0)
                size_fraction = self.pos_size_frac  # Use the passed-in value
                if self.debug_mode:
                    print(
                        f"DEBUG: Executing BUY after cooldown | Price: {current_price:.4f} | Size: {size_fraction*100:.1f}% equity | SL: {sl_price:.4f} | TP: {tp_price:.4f}"
                    )
                self.buy(size=size_fraction, sl=sl_price, tp=tp_price)
                self.pending_trade_type = None  # Reset pending trade

            elif self.pending_trade_type == "sell" and (
                self.modus == "sell" or self.modus == "both"
            ):
                sl_price = current_price * (1 + self.stop_loss_percentage / 100.0)
                tp_price = current_price * (1 - self.take_profit_percentage / 100.0)
                size_fraction = self.pos_size_frac  # Use the passed-in value
                if self.debug_mode:
                    print(
                        f"DEBUG: Executing SELL after cooldown | Price: {current_price:.4f} | Size: {size_fraction*100:.1f}% equity | SL: {sl_price:.4f} | TP: {tp_price:.4f}"
                    )
                self.sell(size=size_fraction, sl=sl_price, tp=tp_price)
                self.pending_trade_type = None  # Reset pending trade

            # If trade executed, we are done for this candle
            return  # Important to prevent immediate new signal detection

        # --- New Signal Detection (Only if not in cooldown and no position) ---
        if not self.position and self.signal_cooldown_counter <= 0:
            # Recalculate signals only if needed (no position, no cooldown)
            buy_liq_agg = self.data.Liq_Buy_Aggregated[-1]
            sell_liq_agg = self.data.Liq_Sell_Aggregated[-1]
            buy_threshold = self.avg_buy_liq[-1] * self.average_liquidation_multiplier
            sell_threshold = self.avg_sell_liq[-1] * self.average_liquidation_multiplier
            buy_signal = buy_liq_agg > buy_threshold
            sell_signal = sell_liq_agg > sell_threshold

            if buy_signal and (self.modus == "buy" or self.modus == "both"):
                self.signal_cooldown_counter = self.cooldown_candles
                self.pending_trade_type = "buy"
                if self.debug_mode:
                    print(
                        f"DEBUG: Buy signal detected. Starting {self.cooldown_candles} candle cooldown."
                    )

            elif sell_signal and (self.modus == "sell" or self.modus == "both"):
                self.signal_cooldown_counter = self.cooldown_candles
                self.pending_trade_type = "sell"
                if self.debug_mode:
                    print(
                        f"DEBUG: Sell signal detected. Starting {self.cooldown_candles} candle cooldown."
                    )
