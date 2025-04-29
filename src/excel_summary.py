"""Orchestrator for generating optimization summary Excel files."""

import os

# import json # No longer needed
from datetime import datetime
from typing import List, Dict, Any

from src.excel_processing import _process_results_to_dataframe
from src.excel_formatting import _save_dataframe_to_excel

# Import Dynaconf settings and loader from optimizer_config
from src.optimizer_config import settings, load_strategy_config


def _get_backtest_params_from_config(active_strategy: str) -> Dict[str, Any]:
    """Extract backtest and optimization parameters using Dynaconf settings.

    Args:
        active_strategy: Name of the strategy to load strategy-specific params.

    Returns:
        Dictionary containing all relevant parameters for Excel summaries.
    """
    # Load strategy-specific settings
    strategy_settings = load_strategy_config(active_strategy)
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
    if not symbol_run_results:
        print(f"\nNo results for symbol {symbol} to save to Excel.")
        return

    results_df = _process_results_to_dataframe(symbol_run_results)

    if "symbol" in results_df.columns and "Return [%]" in results_df.columns:
        results_df = results_df.sort_values(
            by=["symbol", "Return [%]"], ascending=[True, False]
        )
    elif "symbol" in results_df.columns:
        results_df = results_df.sort_values(by=["symbol"], ascending=True)
    else:
        print("WARNING: Could not sort symbol summary. 'symbol' column not found.")

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join("strategies_config", active_strategy)
    excel_filename = os.path.join(
        output_dir,
        f"{symbol}_{timestamp_str}.xlsx",
    )

    params = _get_backtest_params_from_config(active_strategy)

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
    if not all_run_results:
        print("\nNo consolidated results to save to Excel.")
        return

    results_df = _process_results_to_dataframe(all_run_results)

    if "symbol" in results_df.columns and "Return [%]" in results_df.columns:
        results_df = results_df.sort_values(
            by=["symbol", "Return [%]"], ascending=[True, False]
        )
    elif "symbol" in results_df.columns:
        results_df = results_df.sort_values(by=["symbol"], ascending=True)
    else:
        print("WARNING: Could not sort strategy summary. 'symbol' column not found.")

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join("strategies_config", active_strategy)
    excel_filename = os.path.join(
        output_dir, f"{timestamp_str}_{active_strategy}_summary_.xlsx"
    )
    params = _get_backtest_params_from_config(active_strategy)

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
    if not all_strategies_results:
        print("\nNo overall results to save to consolidated Excel.")
        return

    results_df = _process_results_to_dataframe(all_strategies_results)

    if "symbol" in results_df.columns and "Return [%]" in results_df.columns:
        results_df = results_df.sort_values(
            by=["symbol", "Return [%]"], ascending=[True, False]
        )
    elif "symbol" in results_df.columns:
        results_df = results_df.sort_values(by=["symbol"], ascending=True)
    else:
        print("WARNING: Could not sort overall summary. 'symbol' column not found.")

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = "strategies_config"
    excel_filename = os.path.join(
        output_dir, f"{timestamp_str}_overall_optimization_summary.xlsx"
    )

    print(f"Saving overall summary to: {excel_filename}")
    params = _get_global_backtest_params_from_config()

    _save_dataframe_to_excel(results_df, excel_filename, params)
