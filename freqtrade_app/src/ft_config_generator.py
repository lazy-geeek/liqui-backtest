import json
from pathlib import Path
from dynaconf import Dynaconf

# Assuming ft_config_loader is in the same directory or accessible via PYTHONPATH
from ft_config_loader import get_global_settings, APP_BASE_DIR

# Default path for the generated Freqtrade config, relative to APP_BASE_DIR
DEFAULT_GENERATED_CONFIG_PATH = APP_BASE_DIR / "ft_generated_config.json"


def generate_freqtrade_config_json(
    global_settings: Dynaconf, output_path: Path = DEFAULT_GENERATED_CONFIG_PATH
) -> Path:
    """
    Generates a Freqtrade-compatible config.json file from global settings.

    Args:
        global_settings: A Dynaconf object containing the global application settings.
        output_path: The path where the generated config.json will be saved.

    Returns:
        The path to the generated config.json file.
    """
    ft_config = global_settings.get("freqtrade_config", {})
    bt_settings = global_settings.get("backtest_settings", {})

    config_data = {
        "exchange": {
            "name": ft_config.get("exchange_name", "binance").lower(),
            "key": "",  # Placeholder, Freqtrade usually handles this via user_data_dir/config.json
            "secret": "",  # Placeholder
            "ccxt_config": {},
            "ccxt_async_config": {},
            "pair_whitelist": ft_config.get("pair_whitelist", []),
        },
        "stake_currency": ft_config.get("stake_currency", "USDT"),
        "stake_amount": ft_config.get("stake_amount", 1000),
        "dry_run": ft_config.get("dry_run", True),
        "dry_run_wallet": 1000,
        "tradable_balance_ratio": 1.0,
        "dataformat_ohlcv": ft_config.get("dataformat_ohlcv", "feather"),
        # user_data_dir should be relative to where freqtrade is run,
        # or an absolute path. If running freqtrade from freqtrade_app/,
        # then "ft_user_data" would point to "freqtrade_app/ft_user_data/"
        "user_data_dir": ft_config.get("user_data_dir", "ft_user_data"),
        "strategy": bt_settings.get(
            "strategy_name", "BaseStrategy"
        ),  # Default if not specified
        "timeframe": bt_settings.get("timeframe", "5m"),
        # Freqtrade expects timerange for backtesting directly in the config
        # or via CLI. We'll include it here.
        "timerange": bt_settings.get("timerange"),
        "max_open_trades": ft_config.get(
            "max_open_trades", 1
        ),  # Example of another common setting
        "ignore_roi_if_entry_signal": False,
        "experimental": {"use_sell_signal_for_stoploss": False},
        "use_exit_signal": True,
        "entry_pricing": {
            "price_side": "same",
            "use_order_book": True,
            "order_book_top": 1,
            "price_last_balance": 0.0,
            "check_depth_of_market": {"enabled": False, "bids_to_ask_delta": 0},
        },
        "exit_pricing": {
            "price_side": "same",
            "use_order_book": True,
            "order_book_top": 1,
            "price_last_balance": 0.0,
        },
        "exit_profit_only": False,
        # Add other essential Freqtrade configurations as needed
        # "telegram": { "enabled": False },
        # "api_server": { "enabled": False },
        "pairlists": [{"method": "StaticPairList"}],
    }

    # Remove None values for cleaner JSON, Freqtrade might not like nulls for some fields
    config_data = {k: v for k, v in config_data.items() if v is not None}

    # Ensure the output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(config_data, f, indent=4)

    return output_path


if __name__ == "__main__":
    # Example usage:
    print(f"Application base directory: {APP_BASE_DIR}")
    print(f"Default generated config path: {DEFAULT_GENERATED_CONFIG_PATH}")

    # Load settings for a specific environment, e.g., "dev"
    current_env = "dev"  # or "default"
    global_conf = get_global_settings(env=current_env)

    print(f"\nLoaded global settings for environment: '{current_env}'")
    print(f"  Exchange from settings: {global_conf.freqtrade_config.exchange_name}")
    print(
        f"  User data dir from settings: {global_conf.freqtrade_config.user_data_dir}"
    )
    print(
        f"  Strategy name from settings: {global_conf.backtest_settings.strategy_name}"
    )
    print(f"  Timerange from settings: {global_conf.backtest_settings.timerange}")

    # Generate the config.json
    generated_file_path = generate_freqtrade_config_json(global_conf)
    print(f"\nFreqtrade config.json generated successfully at: {generated_file_path}")

    # Verify content (optional)
    with open(generated_file_path, "r") as f:
        print("\nContent of generated config.json:")
        print(f.read())
