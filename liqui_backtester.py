import json
import pandas as pd
from datetime import datetime, timezone
from backtesting import Backtest

# Import our custom modules
import data_fetcher
from strategies import LiquidationStrategy  # Import the specific strategy class

# --- Configuration Loading ---
CONFIG_FILE = "config.json"


def load_config(config_path: str) -> dict:
    """Loads configuration from a JSON file."""
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        print(f"Configuration loaded successfully from {config_path}")
        return config
    except FileNotFoundError:
        print(f"Error: Configuration file not found at {config_path}")
        exit()
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {config_path}")
        exit()
    except Exception as e:
        print(f"An unexpected error occurred loading config: {e}")
        exit()


# --- Main Execution ---
if __name__ == "__main__":
    config = load_config(CONFIG_FILE)

    # Extract settings from config
    backtest_settings = config.get("backtest_settings", {})
    strategy_params = config.get("strategy_parameters", {})

    # Parse backtest settings
    symbol = backtest_settings.get("symbol", "SUIUSDT")
    timeframe = backtest_settings.get("timeframe", "5m")
    try:
        start_date_str = backtest_settings.get("start_date_iso", "2025-01-01T00:00:00Z")
        end_date_str = backtest_settings.get("end_date_iso", "2025-04-01T00:00:00Z")
        # Ensure timezone-aware datetime objects
        start_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
        end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
    except ValueError as e:
        print(f"Error parsing date strings from config: {e}")
        exit()

    initial_cash = backtest_settings.get("initial_cash", 10000)
    commission_pct = backtest_settings.get("commission_percentage", 0.04)
    # Convert commission percentage to decimal for backtesting.py
    commission_decimal = commission_pct / 100.0

    print("--- Starting Liquidation Backtester ---")
    print(f"Symbol: {symbol}")
    print(f"Timeframe: {timeframe}")
    print(f"Period: {start_date} to {end_date}")
    print(f"Initial Cash: ${initial_cash:,.2f}")
    print(f"Commission: {commission_pct:.4f}% ({commission_decimal:.6f} decimal)")
    print(f"Strategy Params: {strategy_params}")
    print("-" * 30)

    # 1. Fetch and Prepare Data
    print("Preparing data...")
    data = data_fetcher.prepare_data(symbol, timeframe, start_date, end_date)

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
        cash=initial_cash,
        commission=commission_decimal,
        # exclusive_orders=True # Consider if you want only one order type active at a time
        # trade_on_close=False # Default: trade on next bar's open. Set True to trade on current bar's close.
    )
    print("Backtest initialized.")
    print("-" * 30)

    # 3. Run Backtest
    print("Running backtest...")
    # Pass strategy parameters loaded from config to the run method
    stats = bt.run(**strategy_params)
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
    # Generate filename based on config settings
    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")
    plot_filename = f"backtest_{symbol}_{timeframe}_{start_str}-{end_str}.html"
    print(f"Saving plot to {plot_filename}...")
    try:
        bt.plot(filename=plot_filename, open_browser=False)
        print("Plot saved successfully.")
    except Exception as e:
        print(f"Could not save plot: {e}")

    print("--- Backtester Finished ---")
