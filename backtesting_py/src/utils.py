"""Utility functions for the backtest optimizer."""

import warnings
import importlib
import os
import shutil
import glob
import time
from typing import Dict, Any, List
from datetime import timedelta  # Import timedelta
from datetime import datetime  # For timestamp

# Add necessary imports for the functions being moved
import pandas as pd
from tqdm import tqdm


def check_dependencies():
    """Check if all dependencies from requirements.txt are installed and print status."""
    import_mappings = {
        "python-dotenv": "dotenv",
        "dynaconf[toml]": "dynaconf",
    }  # Mapping for packages with different import names
    try:
        with open("../requirements.txt", "r") as f:
            requirements = f.readlines()
        packages = [
            line.strip().split("==")[0]
            for line in requirements
            if line.strip() and not line.startswith("#")
        ]
        missing_packages = []
        for package in packages:
            import_name = import_mappings.get(
                package, package
            )  # Use mapped name if available
            try:
                importlib.import_module(import_name)
            except ImportError:
                missing_packages.append(package)

        if missing_packages:
            print(
                f"Missing packages: {', '.join(missing_packages)}. Please install them using 'pip install {' '.join(missing_packages)}'"
            )
            exit(1)  # Exit if any are missing
        else:
            print("All modules are available.")  # Print success message
    except FileNotFoundError:
        print("requirements.txt not found!")
        exit(1)


def configure_warnings():
    """Suppress specific warnings to clean up output."""
    warnings.filterwarnings(
        "ignore",
        message=".*no explicit representation of timezones.*",
        module="bokeh.*",
    )
    warnings.filterwarnings(
        "ignore",
        message=".*A contingent SL/TP order would execute in the same bar.*",
        module="backtesting.*",
    )
    warnings.filterwarnings(
        "ignore",
        message="invalid value encountered in scalar divide",
        category=RuntimeWarning,
    )
    warnings.filterwarnings(
        "ignore",
        message="invalid value encountered in double_scalars",
        category=RuntimeWarning,
    )
    warnings.filterwarnings(
        action="ignore", message=".*Searching for best of .* configurations.*"
    )


def print_optimization_settings(
    backtest_settings: Dict[str, Any], optimization_settings: Dict[str, Any]
):
    """Print general optimization settings."""
    # Read optimization specific settings
    active_strategies = optimization_settings.get("active_strategies", [])
    symbols = optimization_settings.get("symbols", [])
    modus_list = optimization_settings.get("modus", [])
    target_metrics_list = optimization_settings.get("target_metrics", [])

    # Read general backtest settings (still needed for printing)
    timeframe = backtest_settings.get("timeframe", "N/A")
    start_date = backtest_settings.get("start_date", "N/A")
    end_date = backtest_settings.get("end_date", "N/A")
    initial_cash = backtest_settings.get("initial_cash", "N/A")
    commission_pct = backtest_settings.get("commission_percentage", "N/A")
    leverage = backtest_settings.get("leverage", "N/A")
    slippage_percentage_per_side = backtest_settings.get(
        "slippage_percentage_per_side", "N/A"
    )
    position_size_fraction = backtest_settings.get("position_size_fraction", "N/A")

    # Calculate margin (only if leverage is a number)
    margin = "N/A"
    lev_float = None
    try:
        lev_float = float(leverage)
        if lev_float > 0:
            margin = 1.0 / lev_float
        else:
            print("Warning: Leverage must be positive for margin calculation.")
            lev_float = "N/A"  # Reset to N/A if not positive
    except (ValueError, TypeError):
        print("Warning: Invalid leverage value for margin calculation.")
        lev_float = "N/A"  # Reset to N/A if invalid

    print(f"Optimization Targets: {', '.join(target_metrics_list)}")
    print(f"Symbols to process: {', '.join(symbols)}")
    print(f"Strategies to process: {', '.join(active_strategies)}")
    print(f"Timeframe: {timeframe}")
    print(f"Period: {start_date} to {end_date}")
    print(
        (
            f"Initial Cash: ${initial_cash:,.2f}"
            if isinstance(initial_cash, (int, float))
            else f"Initial Cash: {initial_cash}"
        ),
        end="",
    )
    print(
        f", Commission: {commission_pct:.4f}%"
        if isinstance(commission_pct, (int, float))
        else f", Commission: {commission_pct}"
    )
    print(
        f"Leverage: {lev_float}x (Margin: {margin:.4f})"
        if isinstance(lev_float, (int, float))
        else f"Leverage: {lev_float}x (Margin: {margin})"
    )
    print(f"Modes to process: {', '.join(modus_list)}")
    print(
        f"Slippage Per Side: {slippage_percentage_per_side:.4f}%"
        if isinstance(slippage_percentage_per_side, (int, float))
        else f"Slippage Per Side: {slippage_percentage_per_side}"
    )
    print(
        f"Position Size Fraction: {position_size_fraction:.4f}"
        if isinstance(position_size_fraction, (int, float))
        else f"Position Size Fraction: {position_size_fraction}"
    )
    print("-" * 30)


def cleanup_previous_excel_results():
    """Delete existing Excel files in strategies_config/ subfolders."""
    excel_files = glob.glob("strategies_config/**/*.xlsx", recursive=True)
    if excel_files:
        user_input = input(
            "Found existing Excel files in 'strategies_config/' subfolders. Delete them? (y/n): "
        ).lower()

        if user_input == "y":
            print("Deleting files...")
            for file_path in excel_files:
                try:
                    os.remove(file_path)
                except OSError as e:
                    print(f"Error deleting {file_path}: {e}")
            print("Finished deleting files.")
        else:
            print("Deletion cancelled by user.")
    else:
        print("\nNo existing Excel files found in 'strategies_config/' subfolders.")
    print("-" * 30)


def archive_strategies_config(
    base_archive_dir: str = "archive", source_dir: str = "strategies_config"
):
    """
    Copies the contents of the source directory into a timestamped subfolder
    within the base archive directory. The original source directory remains unchanged.
    """
    if not os.path.exists(source_dir) or not os.listdir(source_dir):
        print(
            f"Source directory '{source_dir}' is empty or does not exist. Nothing to copy."
        )
        print("-" * 30)
        return

    if not os.path.exists(base_archive_dir):
        try:
            os.makedirs(base_archive_dir)
            print(f"Created base archive directory: '{base_archive_dir}'")
        except OSError as e:
            print(f"Error creating base archive directory '{base_archive_dir}': {e}")
            print("-" * 30)
            return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path_for_copy = os.path.join(base_archive_dir, timestamp)

    print(
        f"Copying contents of '{source_dir}' to a new archive folder inside '{base_archive_dir}' (will be named '{timestamp}')..."
    )

    try:
        shutil.copytree(source_dir, archive_path_for_copy)
        copied_items_count = len(os.listdir(source_dir))
        print(
            f"Successfully copied {copied_items_count} item(s) from '{source_dir}' to '{archive_path_for_copy}'."
        )
    except OSError as e:
        print(
            f"Error during copytree from '{source_dir}' to '{archive_path_for_copy}': {e}"
        )
    except Exception as e:
        print(
            f"An unexpected error occurred while copying '{source_dir}' to '{archive_path_for_copy}': {e}"
        )

    print("-" * 30)
