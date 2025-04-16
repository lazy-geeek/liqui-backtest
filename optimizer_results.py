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
) -> None:
    """
    Process optimization results and save to files.

    Args:
        stats: Optimization statistics
        heatmap: Optimization heatmap data
        param_grid: Parameter grid used for optimization
        config: Configuration dictionary
        active_strategy: Name of active strategy
        symbol: Trading symbol
    """
    if stats is None:
        print("No results to process - optimization failed")
        return

    print("\nBest Parameters Found:")
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

        # Convert numpy values to native Python types
        for k, v in list(best_params_dict.items()):
            if isinstance(v, (np.generic, np.ndarray)):
                best_params_dict[k] = v.item()

        # Add non-optimized params
        best_params_dict["slippage_percentage_per_side"] = param_grid[
            "slippage_percentage_per_side"
        ]
        best_params_dict["position_size_fraction"] = param_grid[
            "position_size_fraction"
        ]
        print(json.dumps(best_params_dict, indent=4))
    else:
        print("Could not extract best parameters from strategy object.")

    print("\nBest Performance Stats:")
    print(stats.drop("_strategy", errors="ignore"))

    # Save best parameters to JSON
    if best_params_dict:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join("strategies", active_strategy, "optimization_results")
        os.makedirs(output_dir, exist_ok=True)
        filename = os.path.join(
            output_dir, f"optimization_result_{symbol}_{timestamp_str}.json"
        )

        # Prepare key metrics to save
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
            "best_params": best_params_dict,
            "config": config,
            "optimization_stats": clean_for_json(concise_stats),
        }

        with open(filename, "w") as f:
            json.dump(combined_result, f, indent=4)
        print(f"Optimization results saved to {filename}")

        # Save heatmap if available
        if heatmap is not None and not heatmap.empty:
            base_filename = os.path.splitext(filename)[0]
            heatmap_filepath = base_filename + ".csv"
            print(f"Saving optimization heatmap to {heatmap_filepath}...")

            heatmap_df = heatmap.reset_index()
            metric_name = stats.index[
                stats.index.str.contains(
                    "Ratio|Return|Equity|Drawdown", case=False, regex=True
                )
            ].tolist()
            metric_name = metric_name[0] if metric_name else "MetricValue"
            heatmap_df.rename(
                columns={heatmap_df.columns[-1]: metric_name}, inplace=True
            )

            heatmap_df.to_csv(heatmap_filepath, index=False)
            print("Heatmap saved successfully.")
    else:
        print("Skipping saving best parameters JSON as they could not be extracted.")
