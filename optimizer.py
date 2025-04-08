import json
import pandas as pd
import numpy as np
from datetime import datetime
from backtesting import Backtest
import warnings
import time  # To time the optimization
import sys  # For exiting

# Import our custom modules and refactored functions
import data_fetcher
from strategies import LiquidationStrategy
from liqui_backtester import load_config  # Use the loader from the refactored script

# --- Configuration ---
CONFIG_FILE = "config.json"
OPTIMIZATION_RESULTS_CSV = "optimization_results.csv"
OPTIMIZATION_BEST_PARAMS_JSON = (
    "optimization_best_params.json"  # File to save best params
)

# Suppress specific warnings (optional, but can clean up output)
warnings.filterwarnings(
    "ignore", message=".*no explicit representation of timezones.*", module="bokeh.*"
)
warnings.filterwarnings(
    "ignore",
    message=".*A contingent SL/TP order would execute in the same bar.*",
    module="backtesting.*",
)
# Ignore potential RuntimeWarning from numpy comparing NaN
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


# --- Helper Function to Build Parameter Grid ---
def build_param_grid(config: dict) -> dict:
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
    param_grid["debug_mode"] = app_settings.get("debug_mode", False)

    print(
        f"  slippage_percentage_per_side: {param_grid['slippage_percentage_per_side']} (fixed)"
    )
    print(f"  position_size_fraction: {param_grid['position_size_fraction']} (fixed)")
    print(f"  debug_mode: {param_grid['debug_mode']} (fixed)")

    return param_grid


# --- Main Optimization Execution ---
if __name__ == "__main__":
    start_time = time.time()
    print("--- Starting Parameter Optimization ---")

    # 1. Load Configuration
    config = load_config(CONFIG_FILE)
    backtest_settings = config.get("backtest_settings", {})
    # We don't need strategy_params from config here, as they'll be optimized
    app_settings = config.get("app_settings", {})  # Still needed for debug_mode default

    # 2. Parse Backtest Settings from Config
    symbol = backtest_settings.get("symbol", "SUIUSDT")
    timeframe = backtest_settings.get("timeframe", "5m")
    try:
        start_date_str = backtest_settings.get("start_date_iso", "2025-01-01T00:00:00Z")
        end_date_str = backtest_settings.get("end_date_iso", "2025-04-01T00:00:00Z")
        start_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
        end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
    except ValueError as e:
        print(f"Error parsing date strings from config: {e}")
        exit(1)

    initial_cash = backtest_settings.get("initial_cash", 10000)
    commission_pct = backtest_settings.get("commission_percentage", 0.04)
    commission_decimal = commission_pct / 100.0
    leverage = backtest_settings.get("leverage", 1)
    liquidation_aggregation_minutes = backtest_settings.get(
        "liquidation_aggregation_minutes", 5
    )

    # Calculate margin
    try:
        lev_float = float(leverage)
        if lev_float <= 0:
            lev_float = 1.0
    except (ValueError, TypeError):
        lev_float = 1.0
    margin = 1.0 / lev_float

    print(f"Optimization Target: Sharpe Ratio")
    print(f"Symbol: {symbol}, Timeframe: {timeframe}")
    print(f"Period: {start_date} to {end_date}")
    print(f"Initial Cash: ${initial_cash:,.2f}, Commission: {commission_pct:.4f}%")
    print(f"Leverage: {lev_float}x (Margin: {margin:.4f})")
    print(f"Liquidation Aggregation: {liquidation_aggregation_minutes} minutes")
    print("-" * 30)

    # 3. Fetch and Prepare Data (once)
    print("Preparing data...")
    data = data_fetcher.prepare_data(
        symbol,
        timeframe,
        start_date,
        end_date,
        liquidation_aggregation_minutes=liquidation_aggregation_minutes,
    )

    if data.empty:
        print("No data available for optimization. Exiting.")
        exit(1)

    # Basic data validation (ensure OHLC and required strategy columns exist)
    required_cols = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
        "Liq_Buy_Size",
        "Liq_Sell_Size",
        "Liq_Buy_Aggregated",
        "Liq_Sell_Aggregated",
    ]
    missing_cols = [col for col in required_cols if col not in data.columns]
    if missing_cols:
        print(
            f"Error: Dataframe missing required columns for optimization: {missing_cols}."
        )
        exit(1)

    print(f"Data prepared. Shape: {data.shape}")
    print("-" * 30)

    # 4. Initialize Backtest Object
    # We pass the base settings here. Strategy params are handled by optimize().
    bt = Backtest(
        data,
        LiquidationStrategy,
        cash=initial_cash,
        commission=commission_decimal,
        margin=margin,
    )

    # 5. Build Optimization Parameter Grid from Config
    param_grid = build_param_grid(config)
    print("-" * 30)

    # 6. Run Optimization
    print("Running optimization (this may take a long time)...")
    try:
        # Define a single constraint function checking all conditions
        def check_constraints(p):
            # Ensure parameters exist and are positive scalar values
            # getattr provides a default if the attribute doesn't exist during checks
            valid_tp = getattr(p, "take_profit_percentage", -1) > 0
            valid_sl = getattr(p, "stop_loss_percentage", -1) > 0
            # Add other simple checks here if needed, e.g.:
            # check_p1_gt_p2 = getattr(p, 'param1', 0) > getattr(p, 'param2', -1)
            return valid_tp and valid_sl  # and check_p1_gt_p2

        stats, heatmap = bt.optimize(
            maximize="Sharpe Ratio",
            return_heatmap=True,
            # constraint=check_constraints, # Removed constraint
            **param_grid,
        )
        optimization_successful = True
    except ValueError as e:  # Catch ValueError specifically first
        print(f"\n--- Optimization ValueError ---")
        print(f"A ValueError occurred: {e}")  # Use correct variable 'e'
        print(
            "This often happens with incompatible parameter types or invalid constraints."
        )
        print("Please check strategy logic and parameter grid generation.")
        optimization_successful = False
        stats = None
        heatmap = None
        print("-" * 30)
    except Exception as e:
        print(f"\n--- Optimization Error ---")
        print(f"An unexpected error occurred during optimization: {e}")
        print(f"Error type: {type(e)}")
        print("Please check parameter ranges, data quality, and strategy logic.")
        optimization_successful = False
        stats = None
        heatmap = None
        print("-" * 30)

    # 7. Process and Save Results
    if optimization_successful and stats is not None:
        print("\n--- Optimization Complete ---")
        total_time = time.time() - start_time
        print(f"Total optimization time: {total_time:.2f} seconds")
        print("-" * 30)

        print("Best Parameters Found:")
        best_params = stats["_strategy"]
        # print(best_params) # The strategy object contains the best params

        # Extract best params into a cleaner dictionary
        best_params_dict = {}
        if best_params:
            best_params_dict = {
                attr: getattr(best_params, attr)
                for attr in dir(best_params)
                if not callable(getattr(best_params, attr))
                and not attr.startswith("_")
                and attr in param_grid  # Only include params that were part of the grid
            }
            # Manually add non-optimized params for clarity
            best_params_dict["slippage_percentage_per_side"] = param_grid[
                "slippage_percentage_per_side"
            ]
            best_params_dict["position_size_fraction"] = param_grid[
                "position_size_fraction"
            ]
            best_params_dict["debug_mode"] = param_grid["debug_mode"]
            print(json.dumps(best_params_dict, indent=4))
        else:
            print("Could not extract best parameters from strategy object.")

        print("\nBest Performance Stats:")
        # Exclude the strategy object itself from the printed stats
        print(
            stats.drop("_strategy", errors="ignore")
        )  # Use errors='ignore' in case _strategy isn't present

        # Save best parameters to JSON
        if best_params_dict:
            try:
                with open(OPTIMIZATION_BEST_PARAMS_JSON, "w") as f:
                    json.dump(best_params_dict, f, indent=4)
                print(f"Best parameters saved to {OPTIMIZATION_BEST_PARAMS_JSON}")
            except Exception as e:
                print(f"Error saving best parameters to JSON: {e}")
        else:
            print(
                "Skipping saving best parameters JSON as they could not be extracted."
            )

        # Save heatmap
        if heatmap is not None and not heatmap.empty:
            print(f"Saving optimization heatmap to {OPTIMIZATION_RESULTS_CSV}...")
            try:
                # The heatmap is a Series with MultiIndex. Reset index to convert to DataFrame.
                heatmap_df = heatmap.reset_index()
                # Rename the value column (often 0) to the maximized metric
                metric_name = stats.index[
                    stats.index.str.contains(
                        "Ratio|Return|Equity|Drawdown", case=False, regex=True
                    )
                ].tolist()
                metric_name = (
                    metric_name[0] if metric_name else "MetricValue"
                )  # Default name if not found
                heatmap_df.rename(
                    columns={heatmap_df.columns[-1]: metric_name}, inplace=True
                )

                heatmap_df.to_csv(OPTIMIZATION_RESULTS_CSV, index=False)
                print("Heatmap saved successfully.")
            except Exception as e:
                print(f"Error saving heatmap to CSV: {e}")
        else:
            print("No heatmap data was returned or heatmap was empty.")

    else:
        print("Optimization did not complete successfully or returned no results.")

    print("--- Optimizer Finished ---")
