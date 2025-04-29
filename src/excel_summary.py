"""Orchestrator for generating optimization summary Excel files."""

import os

# import json # No longer needed
from datetime import datetime
from typing import List, Dict, Any

from src.excel_processing import _process_results_to_dataframe
from src.excel_formatting import _save_dataframe_to_excel

# Import Dynaconf settings and loader from optimizer_config
from src.optimizer_config import settings, load_strategy_config

import pandas as pd


def _get_backtest_params_from_config(
    active_strategy: str, active_env: str
) -> Dict[str, Any]:
    """Extract backtest and optimization parameters using Dynaconf settings.

    Args:
        active_strategy: Name of the strategy to load strategy-specific params.
        active_env: The currently active environment (e.g., 'dev', 'production').

    Returns:
        Dictionary containing all relevant parameters for Excel summaries.
    """
    # Load strategy-specific settings
    strategy_settings = load_strategy_config(active_strategy, active_env)
    # Access global settings via the imported 'settings' object
    bt_settings = settings.get("backtest_settings", {})
    opt_settings = settings.get("optimization_settings", {})
    strat_params = strategy_settings.get("strategy_parameters", {})

    return {
        "timeframe": bt_settings.get("timeframe"),
        "start_date_iso": bt_settings.get("start_date_iso"),
        "end_date_iso": bt_settings.get("end_date_iso"),
        "initial_cash": bt_settings.get("initial_cash"),
        "commission_percentage": bt_settings.get("commission_percentage"),
        "slippage_percentage_per_side": bt_settings.get("slippage_percentage_per_side"),
        "position_size_fraction": bt_settings.get("position_size_fraction"),
        "leverage": bt_settings.get("leverage"),
        "liquidation_aggregation_minutes": strat_params.get(
            "liquidation_aggregation_minutes"  # Removed default None, rely on config or Dynaconf default
        ),
        "average_lookback_period_days": strat_params.get(
            "average_lookback_period_days"  # Removed default None
        ),
        "optimize_exit_signal_if_modus_both": opt_settings.get(
            "optimize_exit_signal_if_modus_both"
        ),
        # Note: Target metrics are global, not per-strategy for this function's purpose
    }


def _get_global_backtest_params_from_config() -> Dict[str, Any]:
    """Extract only global backtest and optimization parameters using Dynaconf."""
    # Access global settings via the imported 'settings' object
    bt = settings.get("backtest_settings", {})
    opt = settings.get("optimization_settings", {})

    return {
        "timeframe": bt.get("timeframe"),
        "start_date_iso": bt.get("start_date_iso"),
        "end_date_iso": bt.get("end_date_iso"),
        "initial_cash": bt.get("initial_cash"),
        "commission_percentage": bt.get("commission_percentage"),
        "slippage_percentage_per_side": bt.get("slippage_percentage_per_side"),
        "position_size_fraction": bt.get("position_size_fraction"),
        "leverage": bt.get("leverage"),
        "optimize_exit_signal_if_modus_both": opt.get(
            "optimize_exit_signal_if_modus_both"
        ),
        "target_metrics": opt.get("target_metrics"),
    }


def _process_and_sort_results_df(
    results_list: List[Dict[str, Any]], summary_type: str
) -> pd.DataFrame:
    """
    Processes a list of result dictionaries into a DataFrame and sorts it.

    Args:
        results_list: List of result dictionaries.
        summary_type: Type of summary ('symbol', 'strategy', or 'overall') for logging.

    Returns:
        Processed and sorted DataFrame.
    """
    if not results_list:
        print(f"\nNo results for {summary_type} summary to process.")
        return pd.DataFrame()

    results_df = _process_results_to_dataframe(results_list)

    if "symbol" in results_df.columns and "Return [%]" in results_df.columns:
        results_df = results_df.sort_values(
            by=["symbol", "Return [%]"], ascending=[True, False]
        )
    elif "symbol" in results_df.columns:
        results_df = results_df.sort_values(by=["symbol"], ascending=True)
    else:
        print(
            f"WARNING: Could not sort {summary_type} summary. 'symbol' column not found."
        )

    return results_df


def _generate_excel_filepath(
    summary_type: str, active_strategy: str = None, symbol: str = None
) -> str:
    """
    Generates the Excel file path based on the summary type and context.

    Args:
        summary_type: Type of summary ('symbol', 'strategy', or 'overall').
        active_strategy: The name of the strategy (required for 'symbol' and 'strategy').
        symbol: The specific symbol (required for 'symbol').

    Returns:
        The generated Excel file path.
    """
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    if summary_type == "overall":
        output_dir = "strategies_config"
        excel_filename = f"{timestamp_str}_overall_optimization_summary.xlsx"
    elif summary_type == "strategy":
        if not active_strategy:
            raise ValueError(
                "active_strategy must be provided for strategy summary type."
            )
        output_dir = os.path.join("strategies_config", active_strategy, "results")
        excel_filename = f"{timestamp_str}_{active_strategy}_summary_.xlsx"
    elif summary_type == "symbol":
        if not active_strategy or not symbol:
            raise ValueError(
                "active_strategy and symbol must be provided for symbol summary type."
            )
        output_dir = os.path.join("strategies_config", active_strategy, "results")
        excel_filename = f"{symbol}_{timestamp_str}.xlsx"
    else:
        raise ValueError(f"Unknown summary_type: {summary_type}")

    return os.path.join(output_dir, excel_filename)


def generate_symbol_summary_excel(
    symbol_run_results: List[Dict[str, Any]],
    active_strategy: str,
    symbol: str,
) -> None:
    """
    Processes results for a single symbol and saves them to an Excel file
    in the symbol's optimization_results directory.

    Args:
        symbol_run_results: List of result dictionaries for the specific symbol.
        active_strategy: The name of the strategy being run.
        symbol: The specific symbol these results belong to.
    """
    results_df = _process_and_sort_results_df(symbol_run_results, "symbol")

    if results_df.empty:
        print(f"\nNo results for symbol {symbol} to save to Excel.")
        return

    excel_filename = _generate_excel_filepath(
        "symbol", active_strategy=active_strategy, symbol=symbol
    )

    # Get the current environment from the global settings object
    current_env = settings.current_env
    params = _get_backtest_params_from_config(active_strategy, current_env)

    _save_dataframe_to_excel(results_df, excel_filename, params)


def save_summary_to_excel(
    all_run_results: List[Dict[str, Any]],
    active_strategy: str,
    target_metrics_list: List[str],
) -> None:
    """
    Processes collected optimization results from ALL symbols and saves them
    to a single consolidated Excel file in the main strategy directory.

    Args:
        all_run_results: A list of dictionaries containing results from all symbols.
        active_strategy: The name of the strategy being run.
        target_metrics_list: The list of target metrics used for optimization.
    """
    results_df = _process_and_sort_results_df(all_run_results, "strategy")

    if results_df.empty:
        print("\nNo consolidated results to save to Excel.")
        return

    excel_filename = _generate_excel_filepath(
        "strategy", active_strategy=active_strategy
    )
    # Get the current environment from the global settings object
    current_env = settings.current_env
    params = _get_backtest_params_from_config(active_strategy, current_env)

    _save_dataframe_to_excel(results_df, excel_filename, params)


def generate_overall_summary_excel(
    all_strategies_results: List[Dict[str, Any]],
) -> None:
    """
    Processes collected optimization results from ALL strategies and symbols
    and saves them to a single consolidated Excel file in the 'strategies_config/' directory.

    Args:
        all_strategies_results: A list of dictionaries containing results
                                 from all strategies and symbols.
    """
    results_df = _process_and_sort_results_df(all_strategies_results, "overall")

    if results_df.empty:
        print("\nNo overall results to save to consolidated Excel.")
        return

    excel_filename = _generate_excel_filepath("overall")

    print(f"Saving overall summary to: {excel_filename}")
    params = _get_global_backtest_params_from_config()

    _save_dataframe_to_excel(results_df, excel_filename, params)
