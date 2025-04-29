"""Execution of the backtest optimization."""

import time
import argparse  # Added import
import sys  # Added import
from datetime import timedelta

from typing import Dict, Any, List

# Import necessary modules from src
# Also import the global 'settings' object
from src.optimizer_config import settings, load_all_configs, get_backtest_settings
from src.optimizer_executor import (
    execute_optimization_loops,
    generate_and_save_overall_summary,
)
from src.utils import (
    check_dependencies,
    configure_warnings,
    print_optimization_settings,
    cleanup_previous_excel_results,
)

if __name__ == "__main__":
    import multiprocessing

    multiprocessing.set_start_method("fork")
    from backtesting import Backtest

    # Backtest.Pool = multiprocessing.Pool # Commented out to potentially disable multiprocessing pool
    start_time = time.time()
    check_dependencies()
    print("--- Starting Parameter Optimization ---")

    configure_warnings()

    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Run backtest optimization.")
    parser.add_argument(
        "--env",
        type=str,
        help="Specify the configuration environment to use (e.g., 'production', 'development'). Overrides default.",
        default=None,  # Default is None, so we only set if provided
    )
    args = parser.parse_args()

    # --- Set Dynaconf Environment if specified ---
    if args.env:
        print(f"--- Switching configuration environment to: {args.env} ---")
        try:
            settings.setenv(args.env)
        except ValueError as e:
            print(f"Error setting environment '{args.env}': {e}")
            print("Please ensure the environment exists in your settings files.")
            sys.exit(1)
    else:
        print(f"--- Using default configuration environment ---")

    # 1. Load all configurations using Dynaconf (now respects the set environment)
    configs = load_all_configs()
    config = configs["main_settings"]
    active_strategies = configs["active_strategies"]

    # 2. Get backtest settings
    backtest_settings = get_backtest_settings(config)

    # Print general optimization settings
    # Print general optimization settings
    optimization_settings = configs["main_settings"].get("optimization_settings", {})
    print_optimization_settings(backtest_settings, optimization_settings)

    # --- Delete existing Excel files ---
    cleanup_previous_excel_results()

    # Execute the main optimization loops
    all_strategies_results = execute_optimization_loops(configs, backtest_settings)

    # --- Generate Overall Summary ---
    generate_and_save_overall_summary(all_strategies_results)

    total_script_time = time.time() - start_time
    total_script_time_minutes = total_script_time / 60
    print(f"\n--- All Optimizations Finished ---")
    print(f"Total script execution time: {total_script_time_minutes:.2f} minutes")
    print("\a")
