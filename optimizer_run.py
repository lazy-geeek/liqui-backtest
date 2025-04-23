"""Execution of the backtest optimization."""

import warnings
import time
import importlib
from tqdm import tqdm

# import multiprocessing as mp
from typing import Dict, Tuple, Optional, Any
from backtesting import Backtest
import os
import shutil
import pandas as pd

# Import our modules
from src import data_fetcher
from src.optimizer_config import load_all_configs, get_backtest_settings
from src.optimizer_params import build_param_grid, calculate_total_combinations
from src.optimizer_results import process_and_save_results
from src.excel_summary import (
    save_summary_to_excel,
    generate_symbol_summary_excel,
)  # Import both functions

# Ensure multiprocessing start method is 'fork'
# if mp.get_start_method(allow_none=False) != "fork":
#    mp.set_start_method("fork")

# Suppress specific warnings (optional, but can clean up output)
warnings.filterwarnings(
    "ignore", message=".*no explicit representation of timezones.*", module="bokeh.*"
)
warnings.filterwarnings(
    "ignore",
    message=".*A contingent SL/TP order would execute in the same bar.*",
    module="backtesting.*",
)
warnings.filterwarnings(
    "ignore",
    message="invalid value encountered in scalar divide",
    category=RuntimeWarning,
)
warnings.filterwarnings(
    "ignore",
    message="invalid value encountered in double_scalars",
    category=RuntimeWarning,
)
warnings.filterwarnings(
    action="ignore", message=".*Searching for best of .* configurations.*"
)


def run_optimization(
    backtest_obj: Backtest, param_grid: Dict[str, Any], target_metric: str
) -> Tuple[Optional[pd.Series], Optional[pd.Series]]:
    """
    Run the backtest optimization with the given parameter grid.

    Args:
        backtest_obj: Initialized Backtest object
        param_grid: Dictionary of parameters to optimize
        target_metric: Metric to maximize during optimization

    Returns:
        Tuple of (stats, heatmap) or (None, None) if optimization failed
    """
    # print("Running optimization (this may take a long time)...") # Removed for quieter output
    start_time = time.time()

    try:
        stats, heatmap = backtest_obj.optimize(
            maximize=target_metric,
            return_heatmap=True,
            **param_grid,
        )
        optimization_successful = True
    except ValueError as e:
        print(f"\n--- Optimization ValueError ---")
        print(f"A ValueError occurred: {e}")
        print(
            "This often happens with incompatible parameter types or invalid constraints."
        )
        print("Please check strategy logic and parameter grid generation.")
        optimization_successful = False
    except Exception as e:
        print(f"\n--- Optimization Error ---")
        print(f"An unexpected error occurred during optimization: {e}")
        print(f"Error type: {type(e)}")
        print("Please check parameter ranges, data quality, and strategy logic.")
        optimization_successful = False

    if optimization_successful:
        total_time = time.time() - start_time
        # print(f"\n--- Optimization Complete ---") # Removed for quieter output
        # print(f"Total optimization time: {total_time:.2f} seconds") # Removed for quieter output
        # print("-" * 30) # Removed for quieter output
        return stats, heatmap
    else:
        # print("-" * 30) # Removed for quieter output (kept for error case clarity if needed)
        return None, None


if __name__ == "__main__":
    start_time = time.time()
    print("--- Starting Parameter Optimization ---")

    # 1. Load all configurations
    configs = load_all_configs("config.json")
    config = configs["main_config"]
    strategy_config = configs["strategy_config"]
    active_strategy = configs["active_strategy"]

    # 2. Get backtest settings
    backtest_settings = get_backtest_settings(config)
    symbols = backtest_settings["symbols"]  # Read the list of symbols
    timeframe = backtest_settings["timeframe"]
    start_date = backtest_settings["start_date"]
    end_date = backtest_settings["end_date"]
    initial_cash = backtest_settings["initial_cash"]
    commission_pct = backtest_settings["commission_pct"]
    leverage = backtest_settings["leverage"]
    liquidation_aggregation_minutes = backtest_settings[
        "liquidation_aggregation_minutes"
    ]
    average_lookback_period_days = backtest_settings["average_lookback_period_days"]
    modus_list = backtest_settings["modus"]  # Read the list of modes
    target_metric = backtest_settings["target_metric"]

    # Calculate margin
    try:
        lev_float = float(leverage)
        if lev_float <= 0:
            lev_float = 1.0
    except (ValueError, TypeError):
        lev_float = 1.0
    margin = 1.0 / lev_float
    commission_decimal = commission_pct / 100.0

    # Print general optimization settings
    print(f"Optimization Target: {target_metric}")
    print(f"Symbols to process: {', '.join(symbols)}")
    print(f"Timeframe: {timeframe}")
    print(f"Period: {start_date} to {end_date}")
    print(f"Initial Cash: ${initial_cash:,.2f}, Commission: {commission_pct:.4f}%")
    print(f"Leverage: {lev_float}x (Margin: {margin:.4f})")
    print(f"Liquidation Aggregation: {liquidation_aggregation_minutes} minutes")
    print(f"Average Liquidation Lookback Period: {average_lookback_period_days} days")
    print(f"Modes to process: {', '.join(modus_list)}")  # Updated print statement
    print("-" * 30)

    # 3. Dynamically import the strategy class (outside the loop as it's the same for all symbols)
    strategy_module_path = f"src.strategies.{active_strategy}.strategy"
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

    # 6. Build parameter grid and calculate combinations (once before the loop)
    param_grid = build_param_grid(strategy_config)
    total_combinations = calculate_total_combinations(param_grid)
    print(f"Total possible parameter combinations: {total_combinations}")
    # Ask once before starting all symbols
    # input("Press Enter to start optimization for all symbols...") # Removed for non-interactive run
    # print("-" * 30) # Removed for non-interactive run

    all_run_results = []  # Initialize list to collect results

    # --- Symbol Loop Start ---
    for symbol in tqdm(symbols, desc="Symbols", position=0, leave=True):
        symbol_results_for_excel = []  # Initialize list for this symbol's results
        # print(f"\n--- Starting Optimization for Symbol: {symbol} ---") # Removed for quieter output
        results_dir = os.path.join(
            "strategies", active_strategy, symbol, "optimization_results"
        )
        if os.path.exists(results_dir):
            shutil.rmtree(results_dir)
        os.makedirs(results_dir, exist_ok=True)

        # 4. Fetch and prepare data for the current symbol (once per symbol)
        # print("Preparing data...") # Removed for quieter output
        data = data_fetcher.prepare_data(
            symbol,  # Use the current symbol from the loop
            timeframe,
            start_date,
            end_date,
            liquidation_aggregation_minutes=liquidation_aggregation_minutes,
            average_lookback_period_days=average_lookback_period_days,
        )

        if data.empty:
            # Handle empty data case specifically for the symbol
            print(f"No data available for optimization for symbol {symbol}. Skipping.")
            print(
                f"No data available for symbol {symbol}. Skipping all modes for this symbol."
            )
            # No progress bar update needed here for outer loop
            continue  # Skip to the next symbol

        # Basic data validation
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
        ]
        missing_cols = [col for col in required_cols if col not in data.columns]
        if missing_cols:
            print(
                f"Error: Dataframe missing required columns for optimization: {missing_cols}."
            )
            print(f"Skipping symbol {symbol} due to missing data columns.")
            # No progress bar update needed here for outer loop
            continue  # Skip to the next symbol

        # print(f"Data prepared for {symbol}. Shape: {data.shape}") # Removed for quieter output
        # print("-" * 30) # Removed for quieter output

        # --- Mode Loop Start ---
        for mode in tqdm(modus_list, desc=f"Modes ({symbol})", position=1, leave=False):
            # print(f"\n--- Starting Mode: {mode} for Symbol: {symbol} ---") # Removed for quieter output

            # 5. Initialize Backtest Object for the current symbol and mode
            # Note: We assume the strategy itself handles the 'mode' internally,
            # potentially by reading config or through optimized parameters.
            # If the strategy needs the mode explicitly, this initialization might need adjustment.
            bt = Backtest(
                data,
                strategy_class,
                cash=initial_cash,
                commission=commission_decimal,
                margin=margin,
            )

            # 6. Parameter grid is built once outside the loop

            # Create a mode-specific parameter grid
            mode_specific_param_grid = param_grid.copy()
            mode_specific_param_grid["modus"] = mode  # Set the modus for this run

            # 7. Run optimization for the current symbol and mode using the specific grid
            stats, heatmap = run_optimization(
                bt, mode_specific_param_grid, target_metric
            )

            # 8. Process and save results for the current symbol and mode, and collect data
            result_data = process_and_save_results(  # Capture return value
                stats=stats,
                heatmap=heatmap,
                param_grid=param_grid,  # Note: param_grid is the full grid, not mode-specific
                config=config,
                active_strategy=active_strategy,
                symbol=symbol,  # Pass the current symbol
                mode=mode,  # Pass the current mode
            )
            if result_data:  # Append if results were successfully processed and saved
                all_run_results.append(result_data)
                symbol_results_for_excel.append(result_data)  # Also add to symbol list
            # Inner progress bar updates automatically
            # print(f"--- Finished Mode: {mode} for Symbol: {symbol} ---") # Removed for quieter output
        # --- Mode Loop End ---

        # --- Save Symbol-Specific Excel Summary ---
        if symbol_results_for_excel:
            generate_symbol_summary_excel(
                symbol_results_for_excel, active_strategy, symbol, target_metric
            )

        # print(f"--- Finished All Modes for Symbol: {symbol} ---") # Removed for quieter output
    # --- Symbol Loop End ---

    # No need to close tqdm iterators explicitly

    # --- Save Consolidated Excel Summary ---
    save_summary_to_excel(all_run_results, active_strategy, target_metric)

    total_script_time = time.time() - start_time
    print(f"\n--- All Optimizations Finished ---")
    print(f"Total script execution time: {total_script_time:.2f} seconds")
    print("\a")
