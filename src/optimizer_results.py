"""Processing and saving optimization results."""

import os
import json
from datetime import datetime
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional


def clean_for_json(obj: Any) -> Any:
    """Clean data for JSON serialization."""
    if isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_for_json(v) for v in obj]
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    elif isinstance(obj, pd.Timedelta):
        return str(obj)
    else:
        return obj


def process_and_save_results(
    stats: pd.Series,
    heatmap: Optional[pd.Series],
    param_grid: Dict[str, Any],
    config: Dict[str, Any],
    active_strategy: str,
    symbol: str,
    mode: str,
    target_metric: str,  # Add target_metric parameter
) -> Optional[Dict[str, Any]]:
    """
    Process optimization results and save to files. Returns the processed data on success.

    Args:
        stats: Optimization statistics
        heatmap: Optimization heatmap data
        param_grid: Parameter grid used for optimization
        config: Configuration dictionary
        active_strategy: Name of active strategy
        symbol: Trading symbol
        mode: Trading mode ('buy', 'sell', 'both')
        target_metric: Metric used for optimization

    Args:
        stats: Optimization statistics
        heatmap: Optimization heatmap data
        param_grid: Parameter grid used for optimization
        config: Configuration dictionary
        active_strategy: Name of active strategy
        symbol: Trading symbol
        mode: Trading mode ('buy', 'sell', 'both')
    """
    if stats is None:
        print(f"No results to process for {symbol} ({mode}) - optimization failed")
        return None

    best_params = stats["_strategy"]
    best_params_dict = {}

    if best_params:
        best_params_dict = {
            attr: getattr(best_params, attr)
            for attr in dir(best_params)
            if not callable(getattr(best_params, attr))
            and not attr.startswith("_")
            and attr in param_grid
        }

        for k, v in list(best_params_dict.items()):
            if isinstance(v, (np.generic, np.ndarray)):
                best_params_dict[k] = v.item()

        # Add the fixed slippage (as decimal) and position size from the grid
        best_params_dict["slippage_pct"] = param_grid.get(
            "slippage_pct", 0.0
        )  # Use .get for safety
        best_params_dict["pos_size_frac"] = param_grid.get(
            "pos_size_frac", 0.01
        )  # Use .get for safety
    else:
        print("Could not extract best parameters from strategy object.")

    if best_params_dict:

        key_metrics = [
            "Start",
            "End",
            "Duration",
            "Exposure Time [%]",
            "Equity Final [$]",
            "Equity Peak [$]",
            "Commissions [$]",
            "Return [%]",
            "Buy & Hold Return [%]",
            "Return (Ann.) [%]",
            "Volatility (Ann.) [%]",
            "CAGR [%]",
            "Sharpe Ratio",
            "Sortino Ratio",
            "Calmar Ratio",
            "Alpha [%]",
            "Beta",
            "Max. Drawdown [%]",
            "Avg. Drawdown [%]",
            "Max. Drawdown Duration",
            "Avg. Drawdown Duration",
            "# Trades",
            "Win Rate [%]",
            "Best Trade [%]",
            "Worst Trade [%]",
            "Avg. Trade [%]",
            "Max. Trade Duration",
            "Avg. Trade Duration",
            "Profit Factor",
            "Expectancy [%]",
            "SQN",
            "Kelly Criterion",
        ]

        concise_stats = {}
        for key in key_metrics:
            if key in stats:
                val = stats[key]
                if isinstance(val, float):
                    concise_stats[key] = round(val, 2)
                else:
                    concise_stats[key] = val

        combined_result = {
            "symbol": symbol,
            "mode": mode,
            "best_params": best_params_dict,
            "config": config,
            "optimization_stats": clean_for_json(concise_stats),
            "target_metric": target_metric,
        }

        return combined_result
    else:
        print("Skipping processing results as best parameters could not be extracted.")
        return None
