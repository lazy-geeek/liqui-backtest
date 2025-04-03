from backtesting import Strategy
from backtesting.lib import crossover


class LiquidationStrategy(Strategy):
    """
    A trading strategy based on aggregated liquidation data.

    Requires input data to have columns: 'Liq_Buy_Size', 'Liq_Sell_Size'
    in addition to standard OHLCV columns.
    """

    # --- Strategy Parameters ---
    # These can be optimized or set externally
    buy_liq_threshold = (
        5000  # Example threshold: Enter long if buy liq > $5000 in a candle
    )
    sell_liq_threshold = (
        5000  # Example threshold: Enter short if sell liq > $5000 in a candle
    )
    sl_pct = 1.0  # Example Stop Loss: 1.0%
    tp_pct = 2.0  # Example Take Profit: 2.0%
    use_opposite_signal_exit = (
        False  # Option to exit on opposite signal (not implemented yet)
    )
    slippage_pct = 0.05  # Example Slippage: 0.05% per side (0.1% round trip)

    def init(self):
        """
        Initialize the strategy. Precompute indicators or series here if needed.
        """
        # Make liquidation data easily accessible
        self.buy_liq = self.data.Liq_Buy_Size
        self.sell_liq = self.data.Liq_Sell_Size
        self.price = self.data.Close  # Use close price for calculations

        # Convert slippage percentage to decimal for calculations
        self.entry_slippage = self.slippage_pct / 100.0
        self.exit_slippage = self.slippage_pct / 100.0

        print("--- Strategy Initialized ---")
        print(f"Buy Liq Threshold: {self.buy_liq_threshold}")
        print(f"Sell Liq Threshold: {self.sell_liq_threshold}")
        print(f"SL Pct: {self.sl_pct}%")
        print(f"TP Pct: {self.tp_pct}%")
        print(f"Slippage Pct (per side): {self.slippage_pct}%")
        print(f"Use Opposite Signal Exit: {self.use_opposite_signal_exit}")
        print("---------------------------")

    def next(self):
        """
        Define the logic executed at each data point (candle).
        """
        current_price = self.price[-1]
        buy_signal = self.buy_liq[-1] > self.buy_liq_threshold
        sell_signal = self.sell_liq[-1] > self.sell_liq_threshold

        # --- Entry Logic ---
        # Only enter if not already in a position
        if not self.position:
            if buy_signal:
                # Calculate SL and TP prices considering slippage for entry
                entry_price = current_price * (1 + self.entry_slippage)
                sl_price = entry_price * (1 - self.sl_pct / 100.0)
                tp_price = entry_price * (1 + self.tp_pct / 100.0)
                self.buy(sl=sl_price, tp=tp_price)
                # print(f"{self.data.index[-1]} LONG Entry | Price: {entry_price:.4f} | Liq: {self.buy_liq[-1]:.2f} | SL: {sl_price:.4f} | TP: {tp_price:.4f}")

            elif sell_signal:
                # Calculate SL and TP prices considering slippage for entry
                entry_price = current_price * (1 - self.entry_slippage)
                sl_price = entry_price * (1 + self.sl_pct / 100.0)
                tp_price = entry_price * (1 - self.tp_pct / 100.0)
                self.sell(sl=sl_price, tp=tp_price)
                # print(f"{self.data.index[-1]} SHORT Entry | Price: {entry_price:.4f} | Liq: {self.sell_liq[-1]:.2f} | SL: {sl_price:.4f} | TP: {tp_price:.4f}")

        # --- Exit Logic ---
        # Primarily handled by sl/tp parameters in self.buy/self.sell
        # TODO: Implement optional exit based on opposite signal if self.use_opposite_signal_exit is True
        # Example (needs refinement):
        # if self.position.is_long and sell_signal and self.use_opposite_signal_exit:
        #     exit_price = current_price * (1 - self.exit_slippage)
        #     self.position.close()
        #     print(f"{self.data.index[-1]} LONG Exit (Opposite Signal) | Price: {exit_price:.4f} | Liq: {self.sell_liq[-1]:.2f}")
        # elif self.position.is_short and buy_signal and self.use_opposite_signal_exit:
        #     exit_price = current_price * (1 + self.exit_slippage)
        #     self.position.close()
        #     print(f"{self.data.index[-1]} SHORT Exit (Opposite Signal) | Price: {exit_price:.4f} | Liq: {self.buy_liq[-1]:.2f}")


# --- Example of how to potentially add more complex logic or indicators ---
# class LiquidationWithMA(LiquidationStrategy):
#     ma_period = 20 # Add another parameter
#
#     def init(self):
#         super().init() # Call parent init
#         # Add a moving average indicator
#         self.ma = self.I(lambda x: pd.Series(x).rolling(self.ma_period).mean(), self.data.Close)
#
#     def next(self):
#         # Access parent logic if needed: super().next()
#         current_price = self.price[-1]
#         buy_signal = self.buy_liq[-1] > self.buy_liq_threshold
#         sell_signal = self.sell_liq[-1] > self.sell_liq_threshold
#
#         # Combine liquidation signal with MA trend filter
#         if not self.position:
#             if buy_signal and current_price > self.ma[-1]: # Only long if above MA
#                 sl_price = current_price * (1 - self.sl_pct / 100.0)
#                 tp_price = current_price * (1 + self.tp_pct / 100.0)
#                 self.buy(sl=sl_price, tp=tp_price)
#             elif sell_signal and current_price < self.ma[-1]: # Only short if below MA
#                 sl_price = current_price * (1 + self.sl_pct / 100.0)
#                 tp_price = current_price * (1 - self.tp_pct / 100.0)
#                 self.sell(sl=sl_price, tp=tp_price)
#         # ... rest of exit logic ...
