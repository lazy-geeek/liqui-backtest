"""Configuration handling for the optimizer."""

import os
import json
from datetime import datetime
import sys
from typing import Dict, Any
from liqui_backtester import load_config


def load_config(config_path: str) -> Dict[str, Any]:
    """Load a JSON configuration file."""
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Config file not found at {config_path}")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {config_path}")
        sys.exit(1)


def load_all_configs(config_file: str = "config.json") -> Dict[str, Any]:
    """Load main config and list of active strategies."""
    config = load_config(config_file)

    active_strategies = config.get("active_strategies")
    if not active_strategies or not isinstance(active_strategies, list):
        print("Error: 'active_strategies' not set or is not a list in config.json")
        sys.exit(1)

    return {
        "main_config": config,
        "active_strategies": active_strategies,
    }


def load_strategy_config(strategy_name: str) -> Dict[str, Any]:
    """Load the configuration for a specific strategy."""
    strategy_config_path = os.path.join(
        "strategies_config", strategy_name, "config.json"
    )
    if not os.path.exists(strategy_config_path):
        print(f"Error: Strategy config not found at {strategy_config_path}")
        sys.exit(1)
    return load_config(strategy_config_path)


def get_backtest_settings(config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and parse backtest settings from config."""
    backtest_settings = config.get("backtest_settings", {})

    try:
        start_date = datetime.fromisoformat(
            backtest_settings.get("start_date_iso", "2025-01-01T00:00:00Z").replace(
                "Z", "+00:00"
            )
        )
        end_date = datetime.fromisoformat(
            backtest_settings.get("end_date_iso", "2025-04-01T00:00:00Z").replace(
                "Z", "+00:00"
            )
        )
    except ValueError as e:
        print(f"Error parsing date strings from config: {e}")
        sys.exit(1)

    # Ensure 'symbols' is a list
    symbols_list = backtest_settings.get("symbols", ["ETHUSDT"])  # Default if missing
    if not isinstance(symbols_list, list):
        print(f"Warning: 'symbols' in config is not a list. Using default: ['ETHUSDT']")
        symbols_list = ["ETHUSDT"]
    elif not symbols_list:  # Handle empty list case
        print(f"Warning: 'symbols' list in config is empty. Using default: ['ETHUSDT']")
        symbols_list = ["ETHUSDT"]

    return {
        "symbols": symbols_list,  # Use the validated list
        "timeframe": backtest_settings.get("timeframe", "5m"),
        "start_date": start_date,
        "end_date": end_date,
        "initial_cash": backtest_settings.get("initial_cash", 10000),
        "commission_pct": backtest_settings.get("commission_percentage", 0.04),
        "leverage": backtest_settings.get("leverage", 1),
        "liquidation_aggregation_minutes": backtest_settings.get(
            "liquidation_aggregation_minutes", 5
        ),
        "average_lookback_period_days": backtest_settings.get(
            "average_lookback_period_days", 7
        ),
        "modus": backtest_settings.get("modus", "both"),
        "target_metrics": config.get("optimization_settings", {}).get(
            "target_metrics", ["Sharpe Ratio"]
        ),
        "slippage_percentage_per_side": backtest_settings.get(
            "slippage_percentage_per_side", 0.0
        ),  # Default to 0 if missing
        "position_size_fraction": backtest_settings.get(
            "position_size_fraction", 0.1
        ),  # Default to 0.1 if missing
    }
