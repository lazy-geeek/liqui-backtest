"""Execution of the backtest optimization."""

import warnings
import time
import importlib
from tqdm import tqdm

from typing import Dict, Tuple, Optional, Any
from backtesting import Backtest
import os
import shutil
import pandas as pd
import glob


def check_dependencies():
    """Check if all dependencies from requirements.txt are installed and print status."""
    import_mappings = {
        "python-dotenv": "dotenv"
    }  # Mapping for packages with different import names
    try:
        with open("requirements.txt", "r") as f:
            requirements = f.readlines()
        packages = [
            line.strip().split("==")[0]
            for line in requirements
            if line.strip() and not line.startswith("#")
        ]
        missing_packages = []
        for package in packages:
            import_name = import_mappings.get(
                package, package
            )  # Use mapped name if available
            try:
                importlib.import_module(import_name)
            except ImportError:
                missing_packages.append(package)

        if missing_packages:
            print(
                f"Missing packages: {', '.join(missing_packages)}. Please install them using 'pip install {' '.join(missing_packages)}'"
            )
            exit(1)  # Exit if any are missing
        else:
            print("All modules are available.")  # Print success message
    except FileNotFoundError:
        print("requirements.txt not found!")
        exit(1)


# Import our modules
from src import data_fetcher
from src.optimizer_config import (
    load_all_configs,
    get_backtest_settings,
    load_strategy_config,
)
from src.optimizer_params import build_param_grid, calculate_total_combinations
from src.optimizer_results import process_and_save_results
from src.excel_summary import (
    generate_symbol_summary_excel,
    save_summary_to_excel,  # Import the consolidated summary function
    generate_overall_summary_excel,  # Add this import
)


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
        return stats, heatmap
    else:
        return None, None


if __name__ == "__main__":
    start_time = time.time()
    check_dependencies()
    print("--- Starting Parameter Optimization ---")

    # 1. Load all configurations
    configs = load_all_configs("config.json")
    config = configs["main_config"]
    active_strategies = configs[
        "active_strategies"
    ]  # Get the list of active strategies

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
    target_metrics_list = backtest_settings["target_metrics"]

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
    print(f"Optimization Targets: {', '.join(target_metrics_list)}")
    print(f"Symbols to process: {', '.join(symbols)}")
    print(
        f"Strategies to process: {', '.join(active_strategies)}"
    )  # Print active strategies
    print(f"Timeframe: {timeframe}")
    print(f"Period: {start_date} to {end_date}")
    print(f"Initial Cash: ${initial_cash:,.2f}, Commission: {commission_pct:.4f}%")
    print(f"Leverage: {lev_float}x (Margin: {margin:.4f})")
    print(f"Liquidation Aggregation: {liquidation_aggregation_minutes} minutes")
    print(f"Average Liquidation Lookback Period: {average_lookback_period_days} days")
    print(f"Modes to process: {', '.join(modus_list)}")  # Updated print statement
    print("-" * 30)

    # --- Delete existing Excel files ---
    excel_files = glob.glob("strategies/**/*.xlsx", recursive=True)
    if excel_files:
        user_input = input(
            "Found existing Excel files in 'strategies/' subfolders. Delete them? (y/n): "
        ).lower()

        if user_input == "y":
            print("Deleting files...")
            for file_path in excel_files:
                try:
                    os.remove(file_path)
                except OSError as e:
                    print(f"Error deleting {file_path}: {e}")
            print("Finished deleting files.")
        else:
            print("Deletion cancelled by user.")
    else:
        print("\nNo existing Excel files found in 'strategies/' subfolders.")
    print("-" * 30)

    # Initialize list to store results from ALL strategies
    all_strategies_results = []

    # --- Strategy Loop Start ---
    for current_strategy_name in tqdm(
        active_strategies, desc="Strategies", position=0, leave=True
    ):

        # Initialize list to store results for ALL symbols within this strategy
        strategy_all_symbols_results = []

        # Load strategy config ONCE per strategy
        strategy_config = load_strategy_config(current_strategy_name)

        # Dynamically import the strategy class ONCE per strategy
        strategy_module_path = f"src.strategies.{current_strategy_name}.strategy"
        try:
            strategy_module = importlib.import_module(strategy_module_path)
        except ModuleNotFoundError:
            print(
                f"Error: Strategy module not found at {strategy_module_path}. Skipping strategy {current_strategy_name}."
            )
            continue  # Skip to the next strategy

        # Find the strategy class ONCE per strategy
        strategy_class = None
        for attr in dir(strategy_module):
            if attr.endswith("Strategy"):
                strategy_class = getattr(strategy_module, attr)
                break
        if strategy_class is None:
            print(
                f"Error: No strategy class found in {strategy_module_path}. Skipping strategy {current_strategy_name}."
            )
            continue  # Skip to the next strategy

        # Build parameter grid ONCE per strategy
        param_grid = build_param_grid(strategy_config)
        total_combinations = calculate_total_combinations(
            param_grid
        )  # Maybe log this per strategy?

        # --- Symbol Loop Start (Now inside Strategy loop) ---
        for symbol in tqdm(
            symbols, desc=f"Symbols ({current_strategy_name})", position=1, leave=False
        ):
            # 4. Fetch and prepare data for the current symbol (once per symbol)
            data = data_fetcher.prepare_data(
                symbol,
                timeframe,
                start_date,
                end_date,
                liquidation_aggregation_minutes=liquidation_aggregation_minutes,
                average_lookback_period_days=average_lookback_period_days,
            )

            if data.empty:
                print(
                    f"\nNo data for {symbol} in {current_strategy_name}. Skipping symbol."
                )
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
                    f"\nError: Data for {symbol} missing columns: {missing_cols}. Skipping symbol for {current_strategy_name}."
                )
                continue  # Skip to the next symbol

            # Initialize list for this symbol and strategy's results
            symbol_strategy_results_for_excel = []

            # --- Target Metric Loop Start ---
            for target_metric in tqdm(
                target_metrics_list,
                desc=f"Metrics ({current_strategy_name}, {symbol})",
                position=2,
                leave=False,
            ):
                # --- Mode Loop Start ---
                for mode in tqdm(
                    modus_list,
                    desc=f"Modes ({current_strategy_name}, {symbol}, {target_metric})",
                    position=3,
                    leave=False,
                ):
                    # 5. Initialize Backtest Object
                    bt = Backtest(
                        data,
                        strategy_class,  # Use class loaded per strategy
                        cash=initial_cash,
                        commission=commission_decimal,
                        margin=margin,
                    )

                    # Create a mode-specific parameter grid
                    mode_specific_param_grid = (
                        param_grid.copy()
                    )  # Use grid built per strategy
                    mode_specific_param_grid["modus"] = mode

                    # 7. Run optimization
                    stats, heatmap = run_optimization(
                        bt, mode_specific_param_grid, target_metric
                    )

                    # 8. Process results
                    result_data = process_and_save_results(
                        stats=stats,
                        heatmap=heatmap,
                        param_grid=param_grid,  # Use grid built per strategy
                        config=config,
                        active_strategy=current_strategy_name,
                        symbol=symbol,
                        mode=mode,
                        target_metric=target_metric,
                    )
                    if result_data:
                        # Add the strategy name explicitly to the result data
                        result_data["strategy_name"] = current_strategy_name
                        symbol_strategy_results_for_excel.append(result_data)
                        strategy_all_symbols_results.append(
                            result_data
                        )  # Collect for strategy summary

                # --- Mode Loop End ---
            # --- Target Metric Loop End ---

            # --- Save Symbol Specific Excel Summary ---
            if symbol_strategy_results_for_excel:
                generate_symbol_summary_excel(
                    symbol_strategy_results_for_excel,
                    current_strategy_name,
                    symbol,
                )

        # --- Symbol Loop End ---

        # --- Save Consolidated Strategy Summary (after processing all symbols for this strategy) ---
        if strategy_all_symbols_results:
            save_summary_to_excel(
                strategy_all_symbols_results,
                current_strategy_name,  # Now correctly refers to the current strategy in the outer loop
                target_metrics_list,
            )

        # --- Collect results for overall summary ---
        if strategy_all_symbols_results:
            all_strategies_results.extend(strategy_all_symbols_results)

    # --- Strategy Loop End ---

    # --- Generate Overall Summary ---
    if all_strategies_results:
        print("\n--- Generating Overall Optimization Summary ---")
        generate_overall_summary_excel(all_strategies_results)
    else:
        print(
            "\nNo results collected across strategies to generate an overall summary."
        )

    # No need to close tqdm iterators explicitly

    total_script_time = time.time() - start_time
    total_script_time_minutes = total_script_time / 60
    print(f"\n--- All Optimizations Finished ---")
    print(f"Total script execution time: {total_script_time_minutes:.2f} minutes")
    print("\a")
