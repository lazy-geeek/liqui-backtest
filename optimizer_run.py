"""Execution of the backtest optimization."""

import time
from datetime import timedelta

from typing import Dict, Any, List

# Import necessary modules from src
from src.optimizer_config import load_all_configs, get_backtest_settings
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
    start_time = time.time()
    check_dependencies()
    print("--- Starting Parameter Optimization ---")

    configure_warnings()

    # 1. Load all configurations using Dynaconf (no filename needed)
    configs = load_all_configs()
    config = configs["main_settings"]
    active_strategies = configs["active_strategies"]

    # 2. Get backtest settings
    backtest_settings = get_backtest_settings(config)

    # Print general optimization settings
    print_optimization_settings(backtest_settings, active_strategies)

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
