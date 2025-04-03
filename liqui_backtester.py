import pandas as pd
from datetime import datetime, timezone
from backtesting import Backtest

# Import our custom modules
import data_fetcher
from strategies import LiquidationStrategy  # Import the specific strategy class

# --- Configuration ---
SYMBOL = "SUIUSDT"
TIMEFRAME = "5m"
# Q1 2025 - Note: end_date is exclusive in fetchers, so use April 1st
START_DATE = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
END_DATE = datetime(2025, 4, 1, 0, 0, 0, tzinfo=timezone.utc)

INITIAL_CASH = 10000  # Starting capital for the backtest
COMMISSION_FEE = 0.0004  # Example commission rate for Binance Futures (Taker: 0.04%)

# Strategy parameters (can be overridden here or optimized later)
# Using defaults from LiquidationStrategy for now
STRATEGY_PARAMS = {
    # 'buy_liq_threshold': 6000, # Example override
    # 'sl_pct': 0.8,             # Example override
}

# --- Main Execution ---
if __name__ == "__main__":
    print("--- Starting Liquidation Backtester ---")
    print(f"Symbol: {SYMBOL}")
    print(f"Timeframe: {TIMEFRAME}")
    print(f"Period: {START_DATE} to {END_DATE}")
    print(f"Initial Cash: ${INITIAL_CASH:,.2f}")
    print(f"Commission: {COMMISSION_FEE*100:.4f}%")
    print(
        f"Strategy Params: {STRATEGY_PARAMS if STRATEGY_PARAMS else 'Using defaults'}"
    )
    print("-" * 30)

    # 1. Fetch and Prepare Data
    print("Preparing data...")
    data = data_fetcher.prepare_data(SYMBOL, TIMEFRAME, START_DATE, END_DATE)

    if data.empty:
        print("No data available for backtesting. Exiting.")
        exit()

    # Ensure data has the correct columns expected by backtesting.py and our strategy
    required_cols = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
        "Liq_Buy_Size",
        "Liq_Sell_Size",
    ]
    if not all(col in data.columns for col in required_cols):
        print(
            f"Error: Dataframe missing required columns. Found: {data.columns}. Required: {required_cols}"
        )
        exit()

    print(f"Data prepared. Shape: {data.shape}")
    print("-" * 30)

    # 2. Initialize Backtest
    print("Initializing backtest...")
    bt = Backtest(
        data,
        LiquidationStrategy,
        cash=INITIAL_CASH,
        commission=COMMISSION_FEE,
        # exclusive_orders=True # Consider if you want only one order type active at a time
        # trade_on_close=False # Default: trade on next bar's open. Set True to trade on current bar's close.
    )
    print("Backtest initialized.")
    print("-" * 30)

    # 3. Run Backtest
    print("Running backtest...")
    # Pass strategy parameters to the run method if any are defined
    stats = bt.run(**STRATEGY_PARAMS)
    print("Backtest finished.")
    print("-" * 30)

    # 4. Print Results
    print("--- Backtest Results ---")
    print(stats)
    print("-" * 30)

    # Optional: Print details about trades
    # print("--- Trades ---")
    # print(stats['_trades']) # Access the trades DataFrame
    # print("-" * 30)

    # 5. Save Plot (Optional)
    plot_filename = f"backtest_{SYMBOL}_{TIMEFRAME}_Q1-2025.html"
    print(f"Saving plot to {plot_filename}...")
    try:
        bt.plot(filename=plot_filename, open_browser=False)
        print("Plot saved successfully.")
    except Exception as e:
        print(f"Could not save plot: {e}")

    print("--- Backtester Finished ---")
