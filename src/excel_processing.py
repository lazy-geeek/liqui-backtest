"""
Module for processing optimization run results into pandas DataFrames
"""

import pandas as pd
from typing import List, Dict, Any

# Define constants for requested stats to avoid repetition
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


def _process_results_to_dataframe(run_results: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Processes a list of run results into a structured Pandas DataFrame,
    dynamically including optimized parameters.

    Args:
        run_results: List of result dictionaries.

    Returns:
        A Pandas DataFrame with the processed results.
    """
    summary_data_for_excel = []
    all_best_param_keys = set()

    # First pass: Collect all unique keys from best_params across all results
    for run_result in run_results:
        best_params = run_result.get("best_params", {})
        all_best_param_keys.update(best_params.keys())

    # Sort parameter keys for consistent column order
    sorted_best_param_keys = sorted(all_best_param_keys)

    # Second pass: Build the data for the DataFrame
    for run_result in run_results:
        best_params = run_result.get("best_params", {})
        opt_stats = run_result.get("optimization_stats", {})

        flat_data = {
            "strategy_name": run_result.get("strategy_name"),
            "symbol": run_result.get("symbol"),
            "mode": run_result.get("mode"),
            "target_metric": run_result.get("target_metric"),
        }

        # Extract best params dynamically using all collected keys
        for param_key in sorted_best_param_keys:
            flat_data[param_key] = best_params.get(param_key)

        # Extract requested stats
        for stat in REQUESTED_STATS:
            flat_data[stat] = opt_stats.get(stat)

        summary_data_for_excel.append(flat_data)

    results_df = pd.DataFrame(summary_data_for_excel)

    # Define dynamic column order
    column_order = [
        "strategy_name",
        "symbol",
        "mode",
        *sorted_best_param_keys,
        "target_metric",
        *REQUESTED_STATS,
    ]

    # Ensure all expected columns exist and set order
    for col in column_order:
        if col not in results_df.columns:
            results_df[col] = pd.NA
    results_df = results_df[column_order]

    return results_df
