from backtesting import Strategy
from backtesting.lib import crossover


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

    def init(self):
        """
        Initialize the strategy. Precompute indicators or series here if needed.
        """
        # Make liquidation data easily accessible
        self.buy_liq = self.data.Liq_Buy_Size
        self.sell_liq = self.data.Liq_Sell_Size
        self.price = self.data.Close  # Use close price for calculations

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
        current_price = self.price[-1]
        buy_liq_size = self.data.Liq_Buy_Size[-1]
        sell_liq_size = self.data.Liq_Sell_Size[-1]
        buy_signal = buy_liq_size > self.buy_liquidation_threshold_usd
        sell_signal = sell_liq_size > self.sell_liquidation_threshold_usd
        # --- DEBUG PRINTS ---
        # --- DEBUG PRINTS ---
        print(
            f"{self.data.index[-1]} | "
            f"BuyLiq: {self.data.Liq_Buy_Size[-1]:,.0f}, SellLiq: {self.data.Liq_Sell_Size[-1]:,.0f} | "  # Use self.data directly
            f"BuySig: {buy_signal}, SellSig: {sell_signal} | "
            f"InPos: {bool(self.position)}"
        )
        # --- END DEBUG ---

        # --- Entry Logic ---
        # Only enter if not already in a position
        if not self.position:
            if buy_signal:
                # Calculate SL and TP prices considering slippage for entry
                # Calculate SL and TP based on current price, let broker handle execution slippage
                sl_price = current_price * (1 - self.stop_loss_percentage / 100.0)
                tp_price = current_price * (1 + self.take_profit_percentage / 100.0)
                entry_price = current_price * (
                    1 + self.entry_slippage
                )  # Keep for debug print consistency
                # Use fraction of equity for size, as expected by backtesting.py
                size_fraction = self.position_size_fraction
                # Recalculate SL and TP to ensure proper ordering
                sl_price = current_price * (1 - self.stop_loss_percentage / 100.0)
                tp_price = current_price * (1 + self.take_profit_percentage / 100.0)
                print(
                    f"DEBUG: Attempting BUY | Price: {current_price:.4f} | Size: {size_fraction*100:.1f}% equity | SL: {sl_price:.4f} | TP: {tp_price:.4f}"
                )
                self.buy(
                    size=size_fraction, limit=current_price, sl=sl_price, tp=tp_price
                )
                # print(f"{self.data.index[-1]} LONG Entry | Price: {entry_price:.4f} | Liq: {self.buy_liq[-1]:.2f} | SL: {sl_price:.4f} | TP: {tp_price:.4f}")

            elif sell_signal:
                # Calculate SL and TP prices considering slippage for entry
                # Calculate SL and TP based on current price, let broker handle execution slippage
                sl_price = current_price * (1 + self.stop_loss_percentage / 100.0)
                tp_price = current_price * (1 - self.take_profit_percentage / 100.0)
                entry_price = current_price * (
                    1 - self.entry_slippage
                )  # Keep for debug print consistency
                # Use fraction of equity for size, as expected by backtesting.py
                size_fraction = self.position_size_fraction
                print(
                    f"DEBUG: Attempting SELL | Price: {current_price:.4f} | Size: {size_fraction*100:.1f}% equity | SL: {sl_price:.4f} | TP: {tp_price:.4f}"
                )
                self.sell(size=size_fraction, sl=sl_price, tp=tp_price)
                # print(f"{self.data.index[-1]} SHORT Entry | Price: {entry_price:.4f} | Liq: {self.sell_liq[-1]:.2f} | SL: {sl_price:.4f} | TP: {tp_price:.4f}")

        # --- Exit Logic ---
        # Primarily handled by sl/tp parameters in self.buy/self.sell
        # TODO: Implement optional exit based on opposite signal if self.exit_on_opposite_signal is True
        # Example (needs refinement):
        # if self.position.is_long and sell_signal and self.exit_on_opposite_signal:
        #     exit_price = current_price * (1 - self.exit_slippage)
        #     self.position.close()
        #     print(f"{self.data.index[-1]} LONG Exit (Opposite Signal) | Price: {exit_price:.4f} | Liq: {self.sell_liq[-1]:.2f}")
        # elif self.position.is_short and buy_signal and self.exit_on_opposite_signal:
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
