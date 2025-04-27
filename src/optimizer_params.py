"""Parameter grid construction for optimization."""

import sys
from typing import Dict, Any
from functools import reduce
import operator


def build_param_grid(
    strategy_config: Dict[str, Any], main_backtest_settings: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Builds the parameter grid for optimization from config.

    Args:
        strategy_config: The configuration specific to the strategy being optimized.
        main_backtest_settings: The general backtest settings from the main config.

    Returns:
        A dictionary representing the parameter grid for backtesting.py optimize method.
    """
    param_grid = {}
    optimization_ranges = strategy_config.get("optimization_ranges")
    if not optimization_ranges:
        print("Error: 'optimization_ranges' section not found in strategy config")
        sys.exit(1)

    for param_name, settings in optimization_ranges.items():
        if "values" in settings:
            # Direct list of values (e.g., for booleans)
            param_grid[param_name] = settings["values"]
        elif "start" in settings and "end" in settings and "step" in settings:
            # Range defined by start, end, step
            start, end, step = settings["start"], settings["end"], settings["step"]
            if not isinstance(step, (int, float)) or step <= 0:
                print(
                    f"Error: Invalid step value '{step}' for parameter '{param_name}' in config. Must be positive number."
                )
                sys.exit(1)

            if (
                isinstance(step, int)
                and isinstance(start, int)
                and isinstance(end, int)
            ):
                # Use Python's range for integers
                # Add step to end because range's stop is exclusive
                param_grid[param_name] = range(start, end + step, step)
            else:
                # Use list comprehension for floats to ensure hashable types
                decimals = 0
                if isinstance(step, float):
                    step_str = str(step)
                    if "." in step_str:
                        decimals = len(step_str.split(".")[-1])
                else:  # Handle potential float steps like 1.0
                    step = float(step)
                    start = float(start)
                    end = float(end)

                # Generate range using a loop and round
                current = start
                values = []
                # Use a small tolerance for float comparison
                tolerance = step / 1e6
                while current <= end + tolerance:
                    values.append(round(current, decimals if decimals > 0 else 2))
                    current += step

                param_grid[param_name] = values
        else:
            # Parameter defined but not optimizable (e.g., fixed value in strategy config)
            # We might want to handle fixed values defined here if needed,
            # but currently focusing on ranges and lists.
            pass

    # Add non-optimized parameters from strategy defaults and main backtest settings
    strategy_defaults = strategy_config.get("strategy_parameters", {})

    # Add fixed slippage and position size from main config, falling back to strategy defaults
    slippage_percentage = main_backtest_settings.get(
        "slippage_percentage_per_side",
        strategy_defaults.get(
            "slippage_percentage_per_side", 0.05
        ),  # Fallback to strategy default
    )
    param_grid["slippage_pct"] = slippage_percentage / 100.0  # Convert to decimal

    param_grid["pos_size_frac"] = main_backtest_settings.get(
        "position_size_fraction",
        strategy_defaults.get(
            "position_size_fraction", 0.01
        ),  # Fallback to strategy default
    )

    # Adjust param_grid based on modus (primarily for removing unnecessary thresholds)
    modus_list = main_backtest_settings.get(
        "modus", ["both"]
    )  # Get list from main settings
    # Note: This logic might need refinement if optimizing over multiple modes simultaneously.
    # Assuming for now we build the grid based on the *potential* modes,
    # and optimizer_run.py sets the specific 'modus' for each run.
    if "buy" in modus_list and "sell" not in modus_list:  # Only buy mode specified
        param_grid.pop(
            "sell_liquidation_threshold_usd", None
        )  # Remove sell threshold if present
    elif "sell" in modus_list and "buy" not in modus_list:  # Only sell mode specified
        param_grid.pop(
            "buy_liquidation_threshold_usd", None
        )  # Remove buy threshold if present
    # else ('both' is present or list is empty/invalid): keep both thresholds initially

    # Handle exit_on_opposite_signal optimization based on modus and strategy config flag
    # Check strategy config first for the optimization flag
    optimization_settings = strategy_config.get("optimization_settings", {})
    optimize_exit_flag = optimization_settings.get(
        "optimize_exit_signal_if_modus_both", False
    )

    # Read fixed/default value from strategy_parameters in strategy config
    fixed_exit_value = strategy_defaults.get("exit_on_opposite_signal", False)

    # Only optimize if 'both' is one of the modes being run AND the flag is set
    if "both" in modus_list and optimize_exit_flag:
        param_grid["exit_on_opposite_signal"] = [False, True]
    else:
        # Otherwise, use the fixed value (either from strategy defaults or potentially overridden)
        param_grid["exit_on_opposite_signal"] = fixed_exit_value

    return param_grid


def calculate_total_combinations(param_grid: Dict[str, Any]) -> int:
    """Calculate total number of parameter combinations."""
    lengths = []
    for v in param_grid.values():
        try:
            lengths.append(len(v))
        except TypeError:
            # Fixed values (single scalar), count as 1
            lengths.append(1)

    return reduce(operator.mul, lengths, 1)
