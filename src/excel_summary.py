"""Handles the generation of optimization summary Excel files."""

import os
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any

# Define constants for requested parameters and stats to avoid repetition
REQUESTED_BEST_PARAMS = [
    "average_liquidation_multiplier",
    "exit_on_opposite_signal",
    "stop_loss_percentage",
    "take_profit_percentage",
]
REQUESTED_STATS = [
    "Equity Final [$]",
    "Commissions [$]",
    "Return [%]",
    "Return (Ann.) [%]",
    "Max. Drawdown [%]",
    "Max. Drawdown Duration",
    "# Trades",
    "Win Rate [%]",
    "Sharpe Ratio",
    "Sortino Ratio",
    "Calmar Ratio",
    "SQN",
    "Kelly Criterion",
    "Profit Factor",
]
COLUMN_ORDER = [
    "strategy_name",
    "symbol",
    "mode",
    *REQUESTED_BEST_PARAMS,  # Unpack the list here
    "target_metric",
    *REQUESTED_STATS,  # Unpack the list here
]


def _process_results_to_dataframe(
    run_results: List[Dict[str, Any]], active_strategy: str, target_metric: str
) -> pd.DataFrame:
    """
    Processes a list of run results into a structured Pandas DataFrame.

    Args:
        run_results: List of result dictionaries.
        active_strategy: The name of the strategy being run.
        target_metric: The optimization target metric name.

    Returns:
        A Pandas DataFrame with the processed results.
    """
    summary_data_for_excel = []
    for run_result in run_results:
        # Use .get() extensively for safety
        config_data = run_result.get("config", {})
        best_params = run_result.get("best_params", {})
        opt_stats = run_result.get("optimization_stats", {})
        optimization_settings = config_data.get("optimization_settings", {})

        flat_data = {
            "strategy_name": config_data.get("active_strategy", active_strategy),
            "symbol": run_result.get("symbol"),
            "mode": run_result.get("mode"),
            "target_metric": run_result.get(
                "target_metric", target_metric
            ),  # Get target_metric from run_result
        }

        # Extract best params
        for param in REQUESTED_BEST_PARAMS:
            flat_data[param] = best_params.get(param)

        # Extract stats
        for stat in REQUESTED_STATS:
            flat_data[stat] = opt_stats.get(stat)

        summary_data_for_excel.append(flat_data)

    results_df = pd.DataFrame(summary_data_for_excel)

    # Ensure all expected columns exist and set order
    for col in COLUMN_ORDER:
        if col not in results_df.columns:
            results_df[col] = pd.NA
    results_df = results_df[COLUMN_ORDER]
    return results_df


def _save_dataframe_to_excel(dataframe: pd.DataFrame, excel_filename: str) -> None:
    """
    Saves a Pandas DataFrame to an Excel file.

    Args:
        dataframe: The DataFrame to save.
        excel_filename: The full path for the output Excel file.
    """
    try:
        # Ensure the directory exists before saving
        output_dir = os.path.dirname(excel_filename)
        os.makedirs(output_dir, exist_ok=True)

        dataframe.to_excel(excel_filename, index=False, engine="openpyxl")
        print(f"Optimization summary saved to: {excel_filename}")
    except ImportError:
        print(f"Error saving Excel file: Could not import 'openpyxl'.")
        print("Please install it: pip install openpyxl")
    except Exception as e:
        print(f"Error saving Excel file '{excel_filename}': {e}")


def generate_symbol_summary_excel(
    symbol_run_results: List[Dict[str, Any]],
    active_strategy: str,
    symbol: str,
    target_metric: str,  # Changed back to single metric
) -> None:
    """
    Processes results for a single symbol and saves them to an Excel file
    in the symbol's optimization_results directory.

    Args:
        symbol_run_results: List of result dictionaries for the specific symbol.
        active_strategy: The name of the strategy being run.
        symbol: The specific symbol these results belong to.
        target_metric: The metric used for optimization for this run.
    """
    if not symbol_run_results:
        print(f"\nNo results for symbol {symbol} to save to Excel.")
        return

    print(
        f"\n--- Saving Optimization Summary for Symbol: {symbol} ({target_metric}) ---"
    )
    results_df = _process_results_to_dataframe(
        symbol_run_results, active_strategy, target_metric
    )

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Save within the symbol's optimization_results folder
    output_dir = os.path.join(
        "strategies", active_strategy, symbol, "optimization_results"
    )
    excel_filename = os.path.join(
        output_dir,
        f"optimization_summary_{symbol}_{target_metric.replace(' ', '_')}_{timestamp_str}.xlsx",  # Include target_metric in filename
    )

    _save_dataframe_to_excel(results_df, excel_filename)


def save_summary_to_excel(
    all_run_results: List[Dict[str, Any]],
    active_strategy: str,
    target_metrics_list: List[str],  # Changed to list of metrics
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

    print("\n--- Consolidating and Saving Final Optimization Summary ---")
    # _process_results_to_dataframe already handles extracting the individual target_metric from each run_result
    results_df = _process_results_to_dataframe(
        all_run_results,
        active_strategy,
        (
            target_metrics_list[0] if target_metrics_list else "Sharpe Ratio"
        ),  # Pass the first metric as a fallback for the function signature, though it's not strictly used for data processing here
    )

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Save in the main strategy directory
    output_dir = os.path.join("strategies", active_strategy)
    excel_filename = os.path.join(
        output_dir, f"consolidated_optimization_summary_{timestamp_str}.xlsx"
    )

    _save_dataframe_to_excel(results_df, excel_filename)
