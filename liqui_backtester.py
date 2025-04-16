import json
import pandas as pd
from datetime import datetime
from backtesting import Backtest, Strategy
from termcolor import colored
import glob
import os
import warnings
from typing import Type  # Added for type hinting Strategy class

# Suppress Bokeh timezone warning
warnings.filterwarnings(
    "ignore", message=".*no explicit representation of timezones.*", module="bokeh.*"
)

warnings.filterwarnings(
    "ignore",
    message=".*A contingent SL/TP order would execute in the same bar.*",
    module="backtesting.*",
)

# Import our custom modules
import data_fetcher
import importlib

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
        exit(1)  # Use exit code 1 for errors
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {config_path}")
        exit(1)
    except Exception as e:
        print(f"An unexpected error occurred loading config: {e}")
        exit(1)


# --- Core Backtesting Function ---
def run_single_backtest(
    data: pd.DataFrame,
    strategy_class: Type[Strategy],
    strategy_params: dict,
    initial_cash: float,
    commission_decimal: float,
    margin: float,
) -> tuple[pd.Series, Backtest]:
    """
    Initializes and runs a single backtest instance.

    Args:
        data: DataFrame with OHLCV and strategy-specific columns.
        strategy_class: The strategy class to use (e.g., LiquidationStrategy).
        strategy_params: Dictionary of parameters to pass to the strategy.
        initial_cash: Starting cash for the backtest.
        commission_decimal: Commission per trade (e.g., 0.0004 for 0.04%).
        margin: Margin requirement (e.g., 1.0 for 1x leverage, 0.2 for 5x).

    Returns:
        A tuple containing:
            - stats: A pandas Series with backtest performance metrics.
            - bt: The Backtest object instance (useful for plotting).
    """
    print("Initializing backtest...")
    bt = Backtest(
        data,
        strategy_class,
        cash=initial_cash,
        commission=commission_decimal,
        margin=margin,
        # exclusive_orders=True, # Consider if needed
        # trade_on_close=False
    )
    print("Backtest initialized.")
    print("-" * 30)

    print("Running backtest...")
    # Pass strategy parameters loaded from config to the run method
    stats = bt.run(**strategy_params)
    print("Backtest finished.")
    print("-" * 30)

    return stats, bt


# --- Main Execution ---
if __name__ == "__main__":
    config = load_config(CONFIG_FILE)

    # Load active strategy and its config
    active_strategy = config.get("active_strategy")
    if not active_strategy:
        print("Error: 'active_strategy' not set in config.json")
        exit(1)
    strategy_config_path = os.path.join("strategies", active_strategy, "config.json")
    if not os.path.exists(strategy_config_path):
        print(f"Error: Strategy config not found at {strategy_config_path}")
        exit(1)
    strategy_config = load_config(strategy_config_path)

    # Create results directory for this strategy
    results_dir = os.path.join("strategies", active_strategy, "backtest_results")
    os.makedirs(results_dir, exist_ok=True)

    # Dynamically import the strategy class
    strategy_module_path = f"strategies.{active_strategy}.strategy"
    strategy_module = importlib.import_module(strategy_module_path)
    # Find the strategy class (assume only one class ending with 'Strategy')
    strategy_class = None
    for attr in dir(strategy_module):
        if attr.endswith("Strategy"):
            strategy_class = getattr(strategy_module, attr)
            break
    if strategy_class is None:
        print(f"Error: No strategy class found in {strategy_module_path}")
        exit(1)

    # Delete all previously generated backtest HTML files for this strategy
    print(f"Deleting old backtest HTML files from {results_dir}...")
    deleted_count = 0
    for html_file in glob.glob(os.path.join(results_dir, "backtest_*.html")):
        try:
            os.remove(html_file)
            deleted_count += 1
        except Exception as e:
            print(f"Could not delete {html_file}: {e}")
    if deleted_count > 0:
        print(f"Deleted {deleted_count} old backtest file(s).")
    print("-" * 30)

    # Extract settings from config
    backtest_settings = config.get("backtest_settings", {})
    strategy_params = strategy_config.get("strategy_parameters", {}).copy()

    # Pass modus from backtest_settings into strategy_params
    modus = backtest_settings.get("modus", "both")
    strategy_params["modus"] = modus
    app_settings = config.get("app_settings", {})

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
        exit(1)

    initial_cash = backtest_settings.get("initial_cash", 10000)
    commission_pct = backtest_settings.get("commission_percentage", 0.04)
    commission_decimal = commission_pct / 100.0  # Moved calculation here
    leverage = backtest_settings.get("leverage", 1)
    liquidation_aggregation_minutes = backtest_settings.get(
        "liquidation_aggregation_minutes", 5
    )
    average_lookback_period_days = backtest_settings.get(
        "average_lookback_period_days", 7
    )

    # Calculate margin
    try:
        lev_float = float(leverage)
        if lev_float <= 0:
            print("Warning: Leverage must be positive. Defaulting to 1x (margin=1.0).")
            lev_float = 1.0
    except (ValueError, TypeError):
        print("Warning: Invalid leverage value. Defaulting to 1x (margin=1.0).")
        lev_float = 1.0
    margin = 1.0 / lev_float

    print("--- Starting Liquidation Backtester ---")
    print(f"Symbol: {symbol}")
    print(f"Timeframe: {timeframe}")
    print(f"Period: {start_date} to {end_date}")
    print(f"Initial Cash: ${initial_cash:,.2f}")
    print(f"Commission: {commission_pct:.4f}% ({commission_decimal:.6f} decimal)")
    print(f"Leverage: {lev_float}x (Margin: {margin:.4f})")
    print(f"Liquidation Aggregation: {liquidation_aggregation_minutes} minutes")
    print(f"Strategy Params: {strategy_params}")

    # Add debug_mode from app_settings to strategy_params
    debug_mode = app_settings.get("debug_mode", False)
    strategy_params["debug_mode"] = debug_mode  # Ensure debug mode is passed
    print("-" * 30)

    # 1. Fetch and Prepare Data
    print("Preparing data...")

    data = data_fetcher.prepare_data(
        symbol,
        timeframe,
        start_date,
        end_date,
        liquidation_aggregation_minutes=liquidation_aggregation_minutes,
        average_lookback_period_days=average_lookback_period_days,
    )

    if data.empty:
        print("No data available for backtesting. Exiting.")
        exit(1)

    # Ensure data has the correct columns expected by backtesting.py and our strategy
    required_cols = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
        "Liq_Buy_Size",
        "Liq_Sell_Size",
        "Liq_Buy_Aggregated",
        "Liq_Sell_Aggregated",
        "Avg_Liq_Buy",
        "Avg_Liq_Sell",
    ]
    missing_cols = [col for col in required_cols if col not in data.columns]
    if missing_cols:
        print(
            f"Error: Dataframe missing required columns: {missing_cols}. Found: {list(data.columns)}"
        )
        exit(1)

    print(f"Data prepared. Shape: {data.shape}")
    print("-" * 30)

    # Calculate and print liquidation statistics for the setup period
    print("--- Liquidation Statistics (Setup Period) ---")
    try:
        # Using the full dataset as the setup period as requested
        buy_liq = data["Liq_Buy_Size"]
        sell_liq = data["Liq_Sell_Size"]

        # Calculate stats
        # Max includes all values (including zero)
        max_buy = buy_liq.max() if not buy_liq.isnull().all() else 0
        max_sell = sell_liq.max() if not sell_liq.isnull().all() else 0

        # Filter out zeros for avg and median calculations
        buy_liq_nonzero = buy_liq[buy_liq > 0]
        sell_liq_nonzero = sell_liq[sell_liq > 0]

        # Calculate avg and median on non-zero data, defaulting to 0 if the filtered series is empty
        avg_buy = buy_liq_nonzero.mean() if not buy_liq_nonzero.empty else 0
        med_buy = buy_liq_nonzero.median() if not buy_liq_nonzero.empty else 0
        avg_sell = sell_liq_nonzero.mean() if not sell_liq_nonzero.empty else 0
        med_sell = sell_liq_nonzero.median() if not sell_liq_nonzero.empty else 0

        # Print stats with color
        print(
            colored(
                f"Buy Liquidation  - Max: {max_buy:,.2f}, Avg: {avg_buy:,.2f}, Median: {med_buy:,.2f}",
                "green",
            )
        )
        print(
            colored(
                f"Sell Liquidation - Max: {max_sell:,.2f}, Avg: {avg_sell:,.2f}, Median: {med_sell:,.2f}",
                "red",
            )
        )

    except KeyError as e:
        print(
            colored(f"Error calculating liquidation stats: Missing column {e}", "red")
        )
    except Exception as e:
        print(
            colored(
                f"An unexpected error occurred during liquidation stat calculation: {e}",
                "red",
            )
        )
    print("-" * 30)

    # 2. Run Backtest using the refactored function
    stats, bt = run_single_backtest(
        data=data,
        strategy_class=strategy_class,
        strategy_params=strategy_params,
        initial_cash=initial_cash,
        commission_decimal=commission_decimal,
        margin=margin,
    )

    # 3. Print Results
    print("--- Backtest Results ---")
    print(stats)
    print("-" * 30)

    # 4. Save Plot (Optional)
    # Generate filename based on config settings
    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")
    base_filename = f"backtest_{symbol}_{timeframe}_{start_str}-{end_str}.html"
    plot_filename = os.path.join(results_dir, base_filename)
    print(f"Saving plot to {plot_filename}...")
    try:
        # Use the returned 'bt' object for plotting
        bt.plot(filename=plot_filename, open_browser=False, resample="1h")
        print("Plot saved successfully.")
    except Exception as e:
        print(f"Could not save plot: {e}")

    print("--- Backtester Finished ---")
