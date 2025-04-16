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
    slippage_percentage_per_side = 0.05
    position_size_fraction = 0.01
    debug_mode = False
    modus = "both"
    cooldown_candles = 0  # Number of candles to wait after signal before trading

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
        self.entry_slippage = self.slippage_percentage_per_side / 100.0
        self.exit_slippage = self.slippage_percentage_per_side / 100.0

    def next(self):
        """
        Define the logic executed at each data point (candle).
        """

        super().next()

        # Decrement cooldown counter if active
        if self.signal_cooldown_counter > 0:
            self.signal_cooldown_counter -= 1

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
            # Check if cooldown just finished and we have a pending trade
            if self.signal_cooldown_counter == 1 and self.pending_trade_type:
                if self.pending_trade_type == "buy" and (
                    self.modus == "buy" or self.modus == "both"
                ):
                    sl_price = current_price * (1 - self.stop_loss_percentage / 100.0)
                    tp_price = current_price * (1 + self.take_profit_percentage / 100.0)
                    size_fraction = self.position_size_fraction
                    if self.debug_mode:
                        print(
                            f"DEBUG: Executing BUY after cooldown | Price: {current_price:.4f} | Size: {size_fraction*100:.1f}% equity | SL: {sl_price:.4f} | TP: {tp_price:.4f}"
                        )
                    self.buy(size=size_fraction, sl=sl_price, tp=tp_price)
                    self.pending_trade_type = None

                elif self.pending_trade_type == "sell" and (
                    self.modus == "sell" or self.modus == "both"
                ):
                    sl_price = current_price * (1 + self.stop_loss_percentage / 100.0)
                    tp_price = current_price * (1 - self.take_profit_percentage / 100.0)
                    size_fraction = self.position_size_fraction
                    if self.debug_mode:
                        print(
                            f"DEBUG: Executing SELL after cooldown | Price: {current_price:.4f} | Size: {size_fraction*100:.1f}% equity | SL: {sl_price:.4f} | TP: {tp_price:.4f}"
                        )
                    self.sell(size=size_fraction, sl=sl_price, tp=tp_price)
                    self.pending_trade_type = None

            # Check for new signals if no cooldown is active
            elif self.signal_cooldown_counter <= 0:
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
