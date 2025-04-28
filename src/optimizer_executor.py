"""Core execution logic for the backtest optimization."""

import time
import importlib
from tqdm import tqdm
from datetime import timedelta

from typing import Dict, Tuple, Optional, Any, List
from backtesting import Backtest
import pandas as pd

# Import necessary modules from src
from src import data_fetcher
from src.optimizer_config import (
    load_strategy_config,
)
from src.optimizer_params import build_param_grid, calculate_total_combinations
from src.optimizer_results import process_and_save_results
from src.excel_summary import (
    generate_symbol_summary_excel,
    save_summary_to_excel,
    generate_overall_summary_excel,
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


def execute_optimization_loops(
    configs: Dict[str, Any], backtest_settings: Dict[str, Any]
):
    """
    Executes the nested loops for strategies, symbols, metrics, and modes
    to run the backtest optimization.
    """
    active_strategies = configs["active_strategies"]
    symbols = backtest_settings["symbols"]
    timeframe = backtest_settings["timeframe"]
    start_date = backtest_settings["start_date"]
    end_date = backtest_settings["end_date"]
    initial_cash = backtest_settings["initial_cash"]
    commission_pct = backtest_settings["commission_pct"]
    leverage = backtest_settings["leverage"]
    modus_list = backtest_settings["modus"]
    target_metrics_list = backtest_settings["target_metrics"]
    slippage_percentage_per_side = backtest_settings["slippage_percentage_per_side"]
    position_size_fraction = backtest_settings["position_size_fraction"]

    # Calculate margin
    try:
        lev_float = float(leverage)
        if lev_float <= 0:
            lev_float = 1.0
    except (ValueError, TypeError):
        lev_float = 1.0
    margin = 1.0 / lev_float
    commission_decimal = commission_pct / 100.0

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
        # Load strategy-specific liquidation parameters
        liq_params = strategy_config.get("strategy_parameters", {})

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
        param_grid = build_param_grid(
            strategy_config, backtest_settings
        )  # Pass main backtest settings
        total_combinations = calculate_total_combinations(
            param_grid
        )  # Maybe log this per strategy?

        # --- Symbol Loop Start (Now inside Strategy loop) ---
        for symbol in tqdm(
            symbols, desc=f"Symbols ({current_strategy_name})", position=1, leave=False
        ):
            # 4. Prepare data for the current symbol using the strategy's specific logic
            # Dynamically import the strategy-specific preparation function
            prepare_data_module_path = (
                f"src.strategies.{current_strategy_name}.data_preparation"
            )
            try:
                prepare_data_module = importlib.import_module(prepare_data_module_path)
                prepare_strategy_data_func = getattr(
                    prepare_data_module, "prepare_strategy_data"
                )
            except (ModuleNotFoundError, AttributeError) as e:
                print(
                    f"\nError importing data preparation function from {prepare_data_module_path}: {e}"
                )
                print(f"Skipping symbol {symbol} for strategy {current_strategy_name}.")
                continue  # Skip to next symbol

            # Prepare data using the strategy-specific function, passing fetchers
            try:
                data = prepare_strategy_data_func(
                    fetch_ohlcv_func=data_fetcher.fetch_ohlcv,  # Pass fetcher
                    fetch_liquidations_func=data_fetcher.fetch_liquidations,  # Pass fetcher
                    strategy_params=liq_params,
                    symbol=symbol,
                    timeframe=timeframe,
                    start_dt=start_date,
                    end_dt=end_date,
                )
            except Exception as e:
                print(
                    f"\nError during data preparation for {symbol} in {current_strategy_name}: {e}"
                )
                print("Skipping symbol.")
                continue  # Skip to next symbol

            if data.empty:
                print(
                    f"\nData preparation failed or resulted in empty DataFrame for {symbol} in {current_strategy_name}. Skipping symbol."
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
                        config=configs[
                            "main_settings"
                        ],  # Pass the main settings object
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
                current_strategy_name,
                target_metrics_list,
            )

        # --- Collect results for overall summary ---
        if strategy_all_symbols_results:
            all_strategies_results.extend(strategy_all_symbols_results)

    # --- Strategy Loop End ---

    return all_strategies_results  # Return collected results


def generate_and_save_overall_summary(all_strategies_results: List[Dict[str, Any]]):
    """
    Generates and saves the overall optimization summary Excel file.
    """
    if all_strategies_results:
        print("\n--- Generating Overall Optimization Summary ---")
        generate_overall_summary_excel(all_strategies_results)
    else:
        print(
            "\nNo results collected across strategies to generate an overall summary."
        )
