"""Handles the generation of optimization summary Excel files."""

import os
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any

# Added import
from openpyxl.utils import get_column_letter

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
    run_results: List[Dict[str, Any]], active_strategy: str
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
                "target_metric"
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

        # Use ExcelWriter to gain more control
        with pd.ExcelWriter(excel_filename, engine="openpyxl") as writer:
            dataframe.to_excel(
                writer, index=False, sheet_name="Sheet1"
            )  # Specify sheet name

            # Access the workbook and worksheet
            # workbook = writer.book # Not strictly needed for these operations
            worksheet = writer.sheets["Sheet1"]

            # Freeze the top row (A2 is the first cell below the header)
            worksheet.freeze_panes = "A2"

            # Auto-size columns
            for column_cells in worksheet.columns:
                # Calculate max length, handle None values and header
                try:
                    # Use 0 if cell.value is None, convert others to string
                    # Include header row (index 0) in length calculation
                    length = max(
                        len(str(cell.value)) if cell.value is not None else 0
                        for cell in column_cells
                    )
                except TypeError:
                    # Fallback in case of unexpected types, though str() should handle most
                    length = 10  # Default width if calculation fails

                # Add a little padding
                adjusted_width = length + 2
                # Set column width (using column letter)
                column_letter = get_column_letter(column_cells[0].column)
                worksheet.column_dimensions[column_letter].width = adjusted_width

    except ImportError:
        print(f"Error saving Excel file: Could not import 'openpyxl'.")
        print("Please install it: pip install openpyxl")
    except Exception as e:
        print(f"Error saving Excel file '{excel_filename}': {e}")


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
        target_metric: The metric used for optimization for this run.
    """
    if not symbol_run_results:
        print(f"\nNo results for symbol {symbol} to save to Excel.")
        return

    results_df = _process_results_to_dataframe(symbol_run_results, active_strategy)

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Save within the strategy folder
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

    print("\n--- Consolidating and Saving Final Optimization Summary ---")
    # _process_results_to_dataframe already handles extracting the individual target_metric from each run_result
    results_df = _process_results_to_dataframe(
        all_run_results,
        active_strategy,
    )

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Save in the main strategy directory
    output_dir = os.path.join("strategies", active_strategy)
    excel_filename = os.path.join(
        output_dir, f"consolidated_optimization_summary_{timestamp_str}.xlsx"
    )

    _save_dataframe_to_excel(results_df, excel_filename)
