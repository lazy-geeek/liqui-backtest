"""
Module for writing pandas DataFrames to Excel with formatting and highlighting.
"""

import os
import pandas as pd
from openpyxl.utils import get_column_letter
from openpyxl.styles import PatternFill


def _save_dataframe_to_excel(dataframe: pd.DataFrame, excel_filename: str) -> None:
    """
    Saves a Pandas DataFrame to an Excel file with formatting:
    - Auto-sized columns
    - Frozen header row
    - Auto-filter
    - Per-symbol best-value highlighting

    Args:
        dataframe: The DataFrame to save.
        excel_filename: The full path for the output Excel file.
    """
    try:
        # Ensure the directory exists before saving
        output_dir = os.path.dirname(excel_filename)
        os.makedirs(output_dir, exist_ok=True)

        with pd.ExcelWriter(excel_filename, engine="openpyxl") as writer:
            dataframe.to_excel(writer, index=False, sheet_name="Sheet1")
            worksheet = writer.sheets["Sheet1"]

            # Freeze header row
            worksheet.freeze_panes = "A2"

            # Auto-size columns
            for column_cells in worksheet.columns:
                try:
                    length = max(
                        len(str(cell.value)) if cell.value is not None else 0
                        for cell in column_cells
                    )
                except TypeError:
                    length = 10
                adjusted_width = length + 2
                col_letter = get_column_letter(column_cells[0].column)
                worksheet.column_dimensions[col_letter].width = adjusted_width

            # Enable filtering
            worksheet.auto_filter.ref = worksheet.dimensions

            # Prepare highlighting
            lime_fill = PatternFill(
                start_color="CCFFCC", end_color="CCFFCC", fill_type="solid"
            )
            highlight_cols = {
                "Equity Final [$]": "max",
                "Commissions [$]": "min",
                "Return [%]": "max",
                "Return (Ann.) [%]": "max",
                "Max. Drawdown [%]": "max",
                "Max. Drawdown Duration": "min",
                "Win Rate [%]": "max",
                "Sharpe Ratio": "max",
                "Sortino Ratio": "max",
                "Calmar Ratio": "max",
                "Profit Factor": "max",
            }

            # Map header names to column indices
            headers = {cell.value: cell.column for cell in worksheet[1]}

            # Compute best values per symbol
            best_per_symbol = {}
            symbol_col = "symbol"
            if symbol_col in dataframe.columns:
                grouped = dataframe.groupby(symbol_col)
                for col_name, criteria in highlight_cols.items():
                    if col_name in dataframe.columns:
                        best_per_symbol[col_name] = {}
                        for symbol, group in grouped:
                            numeric = pd.to_numeric(
                                group[col_name], errors="coerce"
                            ).dropna()
                            if not numeric.empty:
                                best = (
                                    numeric.max()
                                    if criteria == "max"
                                    else numeric.min()
                                )
                                best_per_symbol[col_name][symbol] = best

            symbol_idx = headers.get(symbol_col)
            if symbol_idx:
                # Apply fill for matching best values
                for col_name, criteria in highlight_cols.items():
                    if col_name not in headers:
                        continue
                    col_idx = headers[col_name]
                    col_letter = get_column_letter(col_idx)
                    for row in range(2, worksheet.max_row + 1):
                        cell = worksheet[f"{col_letter}{row}"]
                        symbol = worksheet[
                            f"{get_column_letter(symbol_idx)}{row}"
                        ].value
                        best_val = best_per_symbol.get(col_name, {}).get(symbol)
                        try:
                            val = pd.to_numeric(cell.value, errors="coerce")
                            if (
                                pd.notna(val)
                                and best_val is not None
                                and abs(val - best_val) < 1e-9
                            ):
                                cell.fill = lime_fill
                        except Exception:
                            continue
            else:
                print(
                    "Warning: 'symbol' column not found. Skipping per-symbol highlighting."
                )
    except ImportError:
        print("Error: failed to import openpyxl. Please install it.")
    except Exception as e:
        print(f"Error saving Excel file '{excel_filename}': {e}")
