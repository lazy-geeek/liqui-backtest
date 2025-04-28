"""Utility functions for the backtest optimizer."""

import warnings
import importlib
import os
import shutil
import glob
import time
from typing import Dict, Any, List
from datetime import timedelta  # Import timedelta

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
        with open("requirements.txt", "r") as f:
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
    backtest_settings: Dict[str, Any], active_strategies: List[str]
):
    """Print general optimization settings."""
    symbols = backtest_settings["symbols"]
    timeframe = backtest_settings["timeframe"]
    start_date = backtest_settings["start_date"]
    end_date = backtest_settings["end_date"]
    initial_cash = backtest_settings["initial_cash"]
    commission_pct = backtest_settings["commission_pct"]
    leverage = backtest_settings["leverage"]
    modus_list = backtest_settings["modus"]
    target_metrics_list = backtest_settings["target_metrics"]
    slippage_percentage_per_side = backtest_settings["slippage_percentage_per_side"]
    position_size_fraction = backtest_settings["position_size_fraction"]

    # Calculate margin
    try:
        lev_float = float(leverage)
        if lev_float <= 0:
            lev_float = 1.0
    except (ValueError, TypeError):
        lev_float = 1.0
    margin = 1.0 / lev_float

    print(f"Optimization Targets: {', '.join(target_metrics_list)}")
    print(f"Symbols to process: {', '.join(symbols)}")
    print(f"Strategies to process: {', '.join(active_strategies)}")
    print(f"Timeframe: {timeframe}")
    print(f"Period: {start_date} to {end_date}")
    print(f"Initial Cash: ${initial_cash:,.2f}, Commission: {commission_pct:.4f}%")
    print(f"Leverage: {lev_float}x (Margin: {margin:.4f})")
    print(f"Modes to process: {', '.join(modus_list)}")
    print(f"Slippage Per Side: {slippage_percentage_per_side:.4f}%")
    print(f"Position Size Fraction: {position_size_fraction:.4f}")
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
