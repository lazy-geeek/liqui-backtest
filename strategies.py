from backtesting import Strategy


class LiquidationStrategy(Strategy):
    """
    A trading strategy based on aggregated liquidation data.

    Requires input data to have columns: 'Liq_Buy_Size', 'Liq_Sell_Size'
    in addition to standard OHLCV columns.
    """

    # --- Strategy Parameters ---
    # These will be injected by backtesting.py from the config file.
    # Default values here are placeholders if not provided via run() or optimize().
    buy_liquidation_threshold_usd = 5000
    sell_liquidation_threshold_usd = 5000
    stop_loss_percentage = 1.0
    take_profit_percentage = 2.0
    exit_on_opposite_signal = False
    slippage_percentage_per_side = 0.05
    position_size_fraction = 0.01
    debug_mode = False
    modus = "both"

    def init(self):
        """
        Initialize the strategy. Precompute indicators or series here if needed.
        """

        super().init()

        # Make liquidation data easily accessible
        self.buy_liq = self.data.Liq_Buy_Size
        self.sell_liq = self.data.Liq_Sell_Size

        # Convert slippage percentage to decimal for calculations
        self.entry_slippage = self.slippage_percentage_per_side / 100.0
        self.exit_slippage = self.slippage_percentage_per_side / 100.0

        print("--- Strategy Initialized ---")
        print(f"Buy Liq Threshold (USD): {self.buy_liquidation_threshold_usd}")
        print(f"Sell Liq Threshold (USD): {self.sell_liquidation_threshold_usd}")
        print(f"Stop Loss: {self.stop_loss_percentage}%")
        print(f"Take Profit: {self.take_profit_percentage}%")
        print(f"Slippage (per side): {self.slippage_percentage_per_side}%")
        print(f"Exit on Opposite Signal: {self.exit_on_opposite_signal}")
        print(f"Position Size Fraction: {self.position_size_fraction}")
        print("---------------------------")

    def next(self):
        """
        Define the logic executed at each data point (candle).
        """

        super().next()

        # Enforce strict single-position policy: if any position is open, do nothing
        if self.position:
            return
        # Progress reporting

        current_price = self.data.Close[-1]
        buy_liq_agg = self.data.Liq_Buy_Aggregated[-1]
        sell_liq_agg = self.data.Liq_Sell_Aggregated[-1]
        buy_signal = buy_liq_agg > self.buy_liquidation_threshold_usd
        sell_signal = sell_liq_agg > self.sell_liquidation_threshold_usd

        # --- Entry Logic ---
        # Only enter if not already in a position AND no open trades exist
        if not self.position:
            if self.modus == "buy":
                if buy_signal:
                    sl_price = current_price * (1 - self.stop_loss_percentage / 100.0)
                    tp_price = current_price * (1 + self.take_profit_percentage / 100.0)
                    size_fraction = self.position_size_fraction
                    if self.debug_mode:
                        print(
                            f"DEBUG: Attempting BUY | Price: {current_price:.4f} | Size: {size_fraction*100:.1f}% equity | SL: {sl_price:.4f} | TP: {tp_price:.4f}"
                        )
                    self.buy(size=size_fraction, sl=sl_price, tp=tp_price)

            elif self.modus == "sell":
                if sell_signal:
                    sl_price = current_price * (1 + self.stop_loss_percentage / 100.0)
                    tp_price = current_price * (1 - self.take_profit_percentage / 100.0)
                    size_fraction = self.position_size_fraction
                    if self.debug_mode:
                        print(
                            f"DEBUG: Attempting SELL | Price: {current_price:.4f} | Size: {size_fraction*100:.1f}% equity | SL: {sl_price:.4f} | TP: {tp_price:.4f}"
                        )
                    self.sell(size=size_fraction, sl=sl_price, tp=tp_price)

            else:  # modus == "both"
                if buy_signal:
                    sl_price = current_price * (1 - self.stop_loss_percentage / 100.0)
                    tp_price = current_price * (1 + self.take_profit_percentage / 100.0)
                    size_fraction = self.position_size_fraction
                    if self.debug_mode:
                        print(
                            f"DEBUG: Attempting BUY | Price: {current_price:.4f} | Size: {size_fraction*100:.1f}% equity | SL: {sl_price:.4f} | TP: {tp_price:.4f}"
                        )
                    self.buy(size=size_fraction, sl=sl_price, tp=tp_price)

                elif sell_signal:
                    sl_price = current_price * (1 + self.stop_loss_percentage / 100.0)
                    tp_price = current_price * (1 - self.take_profit_percentage / 100.0)
                    size_fraction = self.position_size_fraction
                    if self.debug_mode:
                        print(
                            f"DEBUG: Attempting SELL | Price: {current_price:.4f} | Size: {size_fraction*100:.1f}% equity | SL: {sl_price:.4f} | TP: {tp_price:.4f}"
                        )
                    self.sell(size=size_fraction, sl=sl_price, tp=tp_price)
