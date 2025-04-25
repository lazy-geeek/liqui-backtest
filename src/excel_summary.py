"""Orchestrator for generating optimization summary Excel files."""

import os
from datetime import datetime
from typing import List, Dict, Any

from src.excel_processing import _process_results_to_dataframe
from src.excel_formatting import _save_dataframe_to_excel


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

    _save_dataframe_to_excel(results_df, excel_filename)


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

    _save_dataframe_to_excel(results_df, excel_filename)


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
    _save_dataframe_to_excel(results_df, excel_filename)
