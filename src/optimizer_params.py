"""Parameter grid construction for optimization."""

import sys
from typing import Dict, Any
from functools import reduce
import operator


def build_param_grid(config: Dict[str, Any]) -> Dict[str, Any]:
    """Builds the parameter grid for optimization from config."""
    param_grid = {}
    optimization_ranges = config.get("optimization_ranges")
    if not optimization_ranges:
        print("Error: 'optimization_ranges' section not found in config.json")
        sys.exit(1)

    print("Building Optimization Parameter Grid from config...")
    for param_name, settings in optimization_ranges.items():
        if "values" in settings:
            # Direct list of values (e.g., for booleans)
            param_grid[param_name] = settings["values"]
            print(f"  {param_name}: Using values {settings['values']}")
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
                print(
                    f"  {param_name}: Using range(start={start}, stop={end + step}, step={step})"
                )
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
                print(
                    f"  {param_name}: Using generated list (start={start}, stop={end}, step={step}) -> {len(values)} values"
                )
        else:
            print(
                f"Warning: Invalid configuration for parameter '{param_name}' in optimization_ranges. Skipping."
            )

    # Add non-optimized parameters from other config sections
    strategy_defaults = config.get("strategy_parameters", {})
    app_settings = config.get("app_settings", {})

    param_grid["slippage_percentage_per_side"] = strategy_defaults.get(
        "slippage_percentage_per_side", 0.05
    )
    param_grid["position_size_fraction"] = strategy_defaults.get(
        "position_size_fraction", 0.01
    )
    print(
        f"  slippage_percentage_per_side: {param_grid['slippage_percentage_per_side']} (fixed)"
    )
    print(f"  position_size_fraction: {param_grid['position_size_fraction']} (fixed)")

    # Adjust param_grid based on modus
    modus = config.get("backtest_settings", {}).get("modus", "both")
    if modus == "buy":
        # Remove sell threshold from optimization
        param_grid.pop("sell_liquidation_threshold_usd", None)
    elif modus == "sell":
        # Remove buy threshold from optimization
        param_grid.pop("buy_liquidation_threshold_usd", None)
    # else 'both': keep both thresholds

    # Handle exit_on_opposite_signal optimization based on modus and config flag
    optimization_settings = config.get("optimization_settings", {})
    optimize_exit_flag = optimization_settings.get(
        "optimize_exit_signal_if_modus_both", False
    )

    # Read fixed/default value from strategy_parameters
    fixed_exit_value = config.get("strategy_parameters", {}).get(
        "exit_on_opposite_signal", False
    )

    if modus == "both" and optimize_exit_flag:
        # Optimize over both True and False
        param_grid["exit_on_opposite_signal"] = [False, True]
        print("  exit_on_opposite_signal: optimizing over [False, True] (modus=both)")
    else:
        # Use fixed value
        param_grid["exit_on_opposite_signal"] = fixed_exit_value
        print(
            f"  exit_on_opposite_signal: fixed at {fixed_exit_value} (optimization disabled or modus != both)"
        )

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
