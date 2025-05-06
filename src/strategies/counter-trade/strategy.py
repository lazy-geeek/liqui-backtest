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
    slippage_pct = 0.0005  # Default slippage (0.05%) as decimal, will be overridden
    pos_size_frac = 0.01  # Default position size fraction, will be overridden
    debug_mode = False
    modus = "both"
    cooldown_candles = 0  # Number of candles to wait after signal before trading
    liquidation_aggregation_minutes = (
        5  # Added missing parameter for backtesting library
    )
    average_lookback_period_days = 14  # Added missing parameter for backtesting library
    exit_on_opposite_signal = False  # Added missing parameter

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

        # --- Cooldown Countdown ---
        trade_ready_after_cooldown = False
        if self.signal_cooldown_counter > 0:
            self.signal_cooldown_counter -= 1
            if self.signal_cooldown_counter == 0 and self.pending_trade_type:
                trade_ready_after_cooldown = True

        # --- Handle Existing Position: Exit or Continue ---
        if self.position:
            if self.exit_on_opposite_signal:
                if self.position.is_long:
                    # CT Long entered on high SELL liquidations. Opposite is high BUY liquidations.
                    # Calculate only what's needed to detect high BUY liquidations.
                    buy_liq_agg = self.data.Liq_Buy_Aggregated[-1]
                    buy_threshold = (
                        self.avg_buy_liq[-1] * self.average_liquidation_multiplier
                    )
                    opposite_signal_for_long = (
                        buy_liq_agg > buy_threshold
                    )  # This is the "sell entry signal" for CT
                    if opposite_signal_for_long:
                        self.position.close()
                        self.pending_trade_type = None
                        self.signal_cooldown_counter = 0
                        return
                elif self.position.is_short:
                    # CT Short entered on high BUY liquidations. Opposite is high SELL liquidations.
                    # Calculate only what's needed to detect high SELL liquidations.
                    sell_liq_agg = self.data.Liq_Sell_Aggregated[-1]
                    sell_threshold = (
                        self.avg_sell_liq[-1] * self.average_liquidation_multiplier
                    )
                    opposite_signal_for_short = (
                        sell_liq_agg > sell_threshold
                    )  # This is the "buy entry signal" for CT
                    if opposite_signal_for_short:
                        self.position.close()
                        self.pending_trade_type = None
                        self.signal_cooldown_counter = 0
                        return
            # If in position, but (exit_on_opposite_signal is False OR (it's True but no opposite signal occurred)):
            return  # Do nothing further

        # --- Trade Execution (After Cooldown, if no position exists) ---
        if trade_ready_after_cooldown:  # Implies no position currently
            current_price = self.data.Close[-1]
            if self.pending_trade_type == "buy" and (
                self.modus == "buy" or self.modus == "both"
            ):
                sl_price = current_price * (1 - self.stop_loss_percentage / 100.0)
                tp_price = current_price * (1 + self.take_profit_percentage / 100.0)
                self.buy(size=self.pos_size_frac, sl=sl_price, tp=tp_price)
                self.pending_trade_type = None  # Clear pending trade
                return
            elif self.pending_trade_type == "sell" and (
                self.modus == "sell" or self.modus == "both"
            ):
                sl_price = current_price * (1 + self.stop_loss_percentage / 100.0)
                tp_price = current_price * (1 - self.take_profit_percentage / 100.0)
                self.sell(size=self.pos_size_frac, sl=sl_price, tp=tp_price)
                self.pending_trade_type = None  # Clear pending trade
                return
            self.pending_trade_type = None  # Fallback to clear pending trade

        # --- New Signal Detection (Only if no position, not in cooldown, and no trade from cooldown) ---
        if not self.position and self.signal_cooldown_counter <= 0:
            # current_price is not needed for signal detection itself, only for SL/TP if a trade is made later.
            # It will be fetched when/if a trade is actually executed from cooldown.

            can_trigger_buy_cooldown = self.modus == "buy" or self.modus == "both"
            can_trigger_sell_cooldown = self.modus == "sell" or self.modus == "both"

            # Attempt to trigger BUY cooldown if allowed and signal occurs
            if can_trigger_buy_cooldown:
                # For CT buy entry: check high SELL liquidations
                sell_liq_agg_for_buy_entry = self.data.Liq_Sell_Aggregated[-1]
                sell_threshold_for_buy_entry = (
                    self.avg_sell_liq[-1] * self.average_liquidation_multiplier
                )
                ct_buy_entry_signal = (
                    sell_liq_agg_for_buy_entry > sell_threshold_for_buy_entry
                )

                if ct_buy_entry_signal:
                    self.signal_cooldown_counter = self.cooldown_candles
                    self.pending_trade_type = "buy"
                    return  # Cooldown initiated, nothing more this candle

            # Attempt to trigger SELL cooldown if allowed, signal occurs, AND no buy cooldown was just initiated
            if (
                can_trigger_sell_cooldown and self.pending_trade_type is None
            ):  # Ensure buy cooldown wasn't just set
                # For CT sell entry: check high BUY liquidations
                buy_liq_agg_for_sell_entry = self.data.Liq_Buy_Aggregated[-1]
                buy_threshold_for_sell_entry = (
                    self.avg_buy_liq[-1] * self.average_liquidation_multiplier
                )
                ct_sell_entry_signal = (
                    buy_liq_agg_for_sell_entry > buy_threshold_for_sell_entry
                )

                if ct_sell_entry_signal:
                    self.signal_cooldown_counter = self.cooldown_candles
                    self.pending_trade_type = "sell"
                    return  # Cooldown initiated, nothing more this candle
