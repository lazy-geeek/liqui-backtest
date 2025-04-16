"""Execution of the backtest optimization."""

import warnings
import time
import importlib

# import multiprocessing as mp
from typing import Dict, Tuple, Optional, Any
from backtesting import Backtest
import pandas as pd

# Import our modules
from src import data_fetcher
from src.optimizer_config import load_all_configs, get_backtest_settings
from src.optimizer_params import build_param_grid, calculate_total_combinations
from src.optimizer_results import process_and_save_results

# Ensure multiprocessing start method is 'fork'
# if mp.get_start_method(allow_none=False) != "fork":
#    mp.set_start_method("fork")

# Suppress specific warnings (optional, but can clean up output)
warnings.filterwarnings(
    "ignore", message=".*no explicit representation of timezones.*", module="bokeh.*"
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


def run_optimization(
    backtest_obj: Backtest, param_grid: Dict[str, Any], target_metric: str
) -> Tuple[Optional[pd.Series], Optional[pd.Series]]:
    """
    Run the backtest optimization with the given parameter grid.

    Args:
        backtest_obj: Initialized Backtest object
        param_grid: Dictionary of parameters to optimize
        target_metric: Metric to maximize during optimization

    Returns:
        Tuple of (stats, heatmap) or (None, None) if optimization failed
    """
    print("Running optimization (this may take a long time)...")
    start_time = time.time()

    try:
        stats, heatmap = backtest_obj.optimize(
            maximize=target_metric,
            return_heatmap=True,
            **param_grid,
        )
        optimization_successful = True
    except ValueError as e:
        print(f"\n--- Optimization ValueError ---")
        print(f"A ValueError occurred: {e}")
        print(
            "This often happens with incompatible parameter types or invalid constraints."
        )
        print("Please check strategy logic and parameter grid generation.")
        optimization_successful = False
    except Exception as e:
        print(f"\n--- Optimization Error ---")
        print(f"An unexpected error occurred during optimization: {e}")
        print(f"Error type: {type(e)}")
        print("Please check parameter ranges, data quality, and strategy logic.")
        optimization_successful = False

    if optimization_successful:
        total_time = time.time() - start_time
        print(f"\n--- Optimization Complete ---")
        print(f"Total optimization time: {total_time:.2f} seconds")
        print("-" * 30)
        return stats, heatmap
    else:
        print("-" * 30)
        return None, None


if __name__ == "__main__":
    start_time = time.time()
    print("--- Starting Parameter Optimization ---")

    # 1. Load all configurations
    configs = load_all_configs("config.json")
    config = configs["main_config"]
    strategy_config = configs["strategy_config"]
    active_strategy = configs["active_strategy"]

    # 2. Get backtest settings
    backtest_settings = get_backtest_settings(config)
    symbol = backtest_settings["symbol"]
    timeframe = backtest_settings["timeframe"]
    start_date = backtest_settings["start_date"]
    end_date = backtest_settings["end_date"]
    initial_cash = backtest_settings["initial_cash"]
    commission_pct = backtest_settings["commission_pct"]
    leverage = backtest_settings["leverage"]
    liquidation_aggregation_minutes = backtest_settings[
        "liquidation_aggregation_minutes"
    ]
    average_lookback_period_days = backtest_settings["average_lookback_period_days"]
    modus = backtest_settings["modus"]
    target_metric = backtest_settings["target_metric"]

    # Calculate margin
    try:
        lev_float = float(leverage)
        if lev_float <= 0:
            lev_float = 1.0
    except (ValueError, TypeError):
        lev_float = 1.0
    margin = 1.0 / lev_float
    commission_decimal = commission_pct / 100.0

    # Print optimization settings
    print(f"Optimization Target: {target_metric}")
    print(f"Symbol: {symbol}, Timeframe: {timeframe}")
    print(f"Period: {start_date} to {end_date}")
    print(f"Initial Cash: ${initial_cash:,.2f}, Commission: {commission_pct:.4f}%")
    print(f"Leverage: {lev_float}x (Margin: {margin:.4f})")
    print(f"Liquidation Aggregation: {liquidation_aggregation_minutes} minutes")
    print(f"Average Liquidation Lookback Period: {average_lookback_period_days} days")
    print(f"Modus: {modus}")
    print("-" * 30)

    # 3. Dynamically import the strategy class
    strategy_module_path = f"src.strategies.{active_strategy}.strategy"
    strategy_module = importlib.import_module(strategy_module_path)
    # Find the strategy class (assume only one class ending with 'Strategy')
    strategy_class = None
    for attr in dir(strategy_module):
        if attr.endswith("Strategy"):
            strategy_class = getattr(strategy_module, attr)
            break
    if strategy_class is None:
        print(f"Error: No strategy class found in {strategy_module_path}")
        exit(1)

    # 4. Fetch and prepare data
    print("Preparing data...")
    data = data_fetcher.prepare_data(
        symbol,
        timeframe,
        start_date,
        end_date,
        liquidation_aggregation_minutes=liquidation_aggregation_minutes,
        average_lookback_period_days=average_lookback_period_days,
    )

    if data.empty:
        print("No data available for optimization. Exiting.")
        exit(1)

    # Basic data validation
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

    # 5. Initialize Backtest Object
    bt = Backtest(
        data,
        strategy_class,
        cash=initial_cash,
        commission=commission_decimal,
        margin=margin,
    )

    # 6. Build parameter grid and calculate combinations
    param_grid = build_param_grid(strategy_config)
    total_combinations = calculate_total_combinations(param_grid)
    print(f"Total possible parameter combinations: {total_combinations}")
    input("Press Enter to start optimization...")
    print("-" * 30)

    # 7. Run optimization
    stats, heatmap = run_optimization(bt, param_grid, target_metric)

    # 8. Process and save results
    process_and_save_results(
        stats=stats,
        heatmap=heatmap,
        param_grid=param_grid,
        config=config,
        active_strategy=active_strategy,
        symbol=symbol,
    )

    print("--- Optimizer Finished ---")
    print("\a")
