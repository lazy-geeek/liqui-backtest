"""Handles the generation of the consolidated optimization summary Excel file."""

import os
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any


def save_summary_to_excel(
    all_run_results: List[Dict[str, Any]], active_strategy: str, target_metric: str
) -> None:
    """
    Processes collected optimization results and saves them to a single Excel file.

    Args:
        all_run_results: A list of dictionaries, where each dictionary is the
                         'combined_result' returned by process_and_save_results.
        active_strategy: The name of the strategy being run.
        target_metric: The optimization target metric name.
    """
    if not all_run_results:
        print("\nNo optimization results were successfully collected to save to Excel.")
        return

    print("\n--- Consolidating and Saving Optimization Summary ---")
    summary_data_for_excel = []
    requested_best_params = [
        "average_liquidation_multiplier",
        "exit_on_opposite_signal",
        "stop_loss_percentage",
        "take_profit_percentage",
    ]
    requested_stats = [
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

    for run_result in all_run_results:
        # Use .get() extensively for safety, in case keys are missing in some results
        config_data = run_result.get("config", {})
        best_params = run_result.get("best_params", {})
        opt_stats = run_result.get("optimization_stats", {})
        optimization_settings = config_data.get("optimization_settings", {})

        flat_data = {
            "strategy_name": config_data.get(
                "active_strategy", active_strategy
            ),  # Use active_strategy as fallback
            "symbol": run_result.get("symbol"),
            "mode": run_result.get("mode"),
            "target_metric": optimization_settings.get(
                "target_metric", target_metric
            ),  # Use target_metric as fallback
        }

        # Extract best params
        for param in requested_best_params:
            flat_data[param] = best_params.get(param)

        # Extract stats
        for stat in requested_stats:
            flat_data[stat] = opt_stats.get(stat)

        summary_data_for_excel.append(flat_data)

    results_df = pd.DataFrame(summary_data_for_excel)

    # Define desired column order
    column_order = [
        "strategy_name",
        "symbol",
        "mode",
        "average_liquidation_multiplier",
        "exit_on_opposite_signal",
        "stop_loss_percentage",
        "take_profit_percentage",
        "target_metric",
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
    # Ensure all expected columns exist, add missing ones with None/NaN if necessary
    for col in column_order:
        if col not in results_df.columns:
            results_df[col] = pd.NA  # Use pandas NA for missing values
    results_df = results_df[column_order]  # Reorder

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join("strategies", active_strategy)
    # Ensure the base strategy directory exists
    os.makedirs(output_dir, exist_ok=True)
    excel_filename = os.path.join(
        output_dir, f"optimization_summary_{timestamp_str}.xlsx"
    )

    try:
        results_df.to_excel(excel_filename, index=False, engine="openpyxl")
        print(f"Optimization summary saved to: {excel_filename}")
    except ImportError:
        print(f"Error saving Excel file: Could not import 'openpyxl'.")
        print("Please install it: pip install openpyxl")
    except Exception as e:
        print(f"Error saving Excel file '{excel_filename}': {e}")
