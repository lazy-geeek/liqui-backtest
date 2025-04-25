"""Orchestrator for generating optimization summary Excel files."""

import os
import json
from datetime import datetime
from typing import List, Dict, Any

from src.excel_processing import _process_results_to_dataframe
from src.excel_formatting import _save_dataframe_to_excel


def _get_backtest_params_from_config() -> Dict[str, Any]:
    """Extract backtest and optimization parameters from config.json.
    
    Returns:
        Dictionary containing all relevant parameters from config.json
    """
    with open("config.json") as f:
        config = json.load(f)

    return {
        "timeframe": config["backtest_settings"]["timeframe"],
        "start_date_iso": config["backtest_settings"]["start_date_iso"],
        "end_date_iso": config["backtest_settings"]["end_date_iso"],
        "initial_cash": config["backtest_settings"]["initial_cash"],
        "commission_percentage": config["backtest_settings"]["commission_percentage"],
        "slippage_percentage_per_side": config["backtest_settings"][
            "slippage_percentage_per_side"
        ],
        "position_size_fraction": config["backtest_settings"]["position_size_fraction"],
        "leverage": config["backtest_settings"]["leverage"],
        "liquidation_aggregation_minutes": config["backtest_settings"][
            "liquidation_aggregation_minutes"
        ],
        "average_lookback_period_days": config["backtest_settings"][
            "average_lookback_period_days"
        ],
        "optimize_exit_signal_if_modus_both": config["optimization_settings"][
            "optimize_exit_signal_if_modus_both"
        ],
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

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join("strategies", active_strategy)
    excel_filename = os.path.join(
        output_dir,
        f"{symbol}_{timestamp_str}.xlsx",
    )

    params = _get_backtest_params_from_config()

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

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join("strategies", active_strategy)
    excel_filename = os.path.join(
        output_dir, f"{timestamp_str}_{active_strategy}_summary_.xlsx"
    )
params = _get_backtest_params_from_config()


    _save_dataframe_to_excel(results_df, excel_filename, params)


def generate_overall_summary_excel(
    all_strategies_results: List[Dict[str, Any]],
) -> None:
    """
    Processes collected optimization results from ALL strategies and symbols
    and saves them to a single consolidated Excel file in the 'strategies/' directory.

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
    output_dir = "strategies"
    excel_filename = os.path.join(
        output_dir, f"{timestamp_str}_overall_optimization_summary.xlsx"
    )

    print(f"Saving overall summary to: {excel_filename}")
    params = _get_backtest_params_from_config()

    _save_dataframe_to_excel(results_df, excel_filename, params)
