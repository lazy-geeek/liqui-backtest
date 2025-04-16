"""Configuration handling for the optimizer."""

import os
import json
from datetime import datetime
import sys
from typing import Dict, Any
from liqui_backtester import load_config


def load_all_configs(config_file: str = "config.json") -> Dict[str, Any]:
    """Load main config and active strategy config."""
    config = load_config(config_file)

    active_strategy = config.get("active_strategy")
    if not active_strategy:
        print("Error: 'active_strategy' not set in config.json")
        sys.exit(1)

    strategy_config_path = os.path.join("strategies", active_strategy, "config.json")
    if not os.path.exists(strategy_config_path):
        print(f"Error: Strategy config not found at {strategy_config_path}")
        sys.exit(1)

    strategy_config = load_config(strategy_config_path)
    return {
        "main_config": config,
        "strategy_config": strategy_config,
        "active_strategy": active_strategy,
    }


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

    return {
        "symbol": backtest_settings.get("symbol", "SUIUSDT"),
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
        "target_metric": config.get("optimization_settings", {}).get(
            "target_metric", "Sharpe Ratio"
        ),
    }
