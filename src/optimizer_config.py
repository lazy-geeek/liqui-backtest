"""Configuration handling for the optimizer."""

import os
from datetime import datetime
import sys
from typing import Dict, Any
from dynaconf import Dynaconf, Validator
from pprint import pprint

# Initialize Dynaconf globally
# It will load settings from settings.toml and .secrets.toml (if exists)
# It also supports environment variables prefixed with BT_
# and loading .env files
settings = Dynaconf(
    envvar_prefix="BT",
    settings_files=["settings.toml"],
    environments=True,  # Enable environment support (e.g., [default], [production])
    load_dotenv=True,  # Load .env file if present
    default_env="default",  # Explicitly set the default environment
)

# Optional: Add validators for key settings (example)
# settings.validators.register(
#     Validator('active_strategies', must_exist=True, is_type_of=list),
#     Validator('backtest_settings.symbols', must_exist=True, is_type_of=list),
#     Validator('backtest_settings.start_date_iso', must_exist=True, is_type_of=str),
#     Validator('backtest_settings.end_date_iso', must_exist=True, is_type_of=str),
#     Validator('backtest_settings.initial_cash', must_exist=True, is_type_of=int),
# )
# try:
#     settings.validators.validate()
# except Exception as e:
#     print(f"Configuration validation error: {e}")
#     sys.exit(1)


def load_all_configs() -> Dict[str, Any]:
    """Load main config settings and list of active strategies using Dynaconf."""
    # Settings are loaded into the global 'settings' object
    active_strategies = settings.get("active_strategies")  # Use .get() for safer access
    if not active_strategies or not isinstance(active_strategies, list):
        print("Error: 'active_strategies' not set or is not a list in settings.toml")
        sys.exit(1)

    return {
        "main_settings": settings,  # Return the global settings object itself
        "active_strategies": active_strategies,
    }


def load_strategy_config(strategy_name: str) -> Dynaconf:
    """Load the configuration for a specific strategy using a separate Dynaconf instance."""
    strategy_config_path = os.path.join(
        "strategies_config",
        strategy_name,
        "settings.toml",  # Look for settings.toml now
    )
    if not os.path.exists(strategy_config_path):
        print(f"Error: Strategy config not found at {strategy_config_path}")
        sys.exit(1)

    # Create a specific Dynaconf instance for this strategy file
    # This keeps strategy settings separate from global settings
    strategy_settings = Dynaconf(
        envvar_prefix=f"BT_{strategy_name.upper()}",  # Optional: Strategy-specific env var prefix
        settings_files=[strategy_config_path],
        environments=True,  # Maintain environment awareness if needed
        default_env="default",
        # Typically, no need to load .secrets.toml or .env here, assuming they are global
    )
    return strategy_settings


def get_backtest_settings(main_settings: Dynaconf) -> Dict[str, Any]:
    """Extract and parse backtest settings from the main Dynaconf settings object."""
    # Access nested settings using dot notation or .get()
    # Using .get() provides default values if a setting is missing
    bt_settings = main_settings.get(
        "backtest_settings", {}
    )  # Get the sub-dict or empty dict

    start_date_iso = bt_settings.get("start_date_iso", "2025-01-01T00:00:00Z")
    end_date_iso = bt_settings.get("end_date_iso", "2025-04-01T00:00:00Z")

    try:
        # Ensure the values are strings before calling replace
        start_date_str = str(start_date_iso) if start_date_iso is not None else ""
        end_date_str = str(end_date_iso) if end_date_iso is not None else ""
        start_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
        end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
    except (
        ValueError,
        AttributeError,
    ) as e:  # Catch AttributeError if get returns None or non-string
        print(f"Error parsing date strings from config: {e}")
        print(
            f"Received start_date_iso: {start_date_iso}, end_date_iso: {end_date_iso}"
        )
        sys.exit(1)

    # Ensure 'symbols' is a list
    symbols_list = bt_settings.get("symbols", ["ETHUSDT"])  # Default if missing
    if not isinstance(symbols_list, list):
        print(f"Warning: 'symbols' in config is not a list. Using default: ['ETHUSDT']")
        symbols_list = ["ETHUSDT"]
    elif not symbols_list:  # Handle empty list case
        print(f"Warning: 'symbols' list in config is empty. Using default: ['ETHUSDT']")
        symbols_list = ["ETHUSDT"]

    # Access optimization settings safely
    opt_settings = main_settings.get("optimization_settings", {})
    target_metrics = opt_settings.get("target_metrics", ["Sharpe Ratio"])

    return {
        "symbols": symbols_list,
        "timeframe": bt_settings.get("timeframe", "5m"),
        "start_date": start_date,
        "end_date": end_date,
        "initial_cash": bt_settings.get("initial_cash", 10000),
        "commission_pct": bt_settings.get(
            "commission_percentage", 0.04
        ),  # Keep original key name
        "leverage": bt_settings.get("leverage", 1),
        "modus": bt_settings.get("modus", "both"),
        "target_metrics": target_metrics,
        "slippage_percentage_per_side": bt_settings.get(
            "slippage_percentage_per_side", 0.0
        ),
        "position_size_fraction": bt_settings.get("position_size_fraction", 0.1),
    }
