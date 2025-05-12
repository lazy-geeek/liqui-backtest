import os
from pathlib import Path
from dynaconf import Dynaconf

# Determine the base directory of the freqtrade_app.
# This assumes ft_config_loader.py is in freqtrade_app/src/
APP_BASE_DIR = Path(__file__).resolve().parent.parent


def get_global_settings(env: str = "default") -> Dynaconf:
    """
    Loads global settings for the Freqtrade application.

    Args:
        env: The environment to load (e.g., "default", "dev").

    Returns:
        A Dynaconf object with the loaded global settings.
    """
    settings_file_path = APP_BASE_DIR / "settings.toml"
    settings = Dynaconf(
        envvar_prefix="FTAPP",  # Optional: if you want to override with env vars like FTAPP_SETTING=value
        settings_files=[settings_file_path],
        environments=True,  # Enable environment layering (e.g., default, dev, prod)
        load_dotenv=True,  # Load .env files if present
        env_switcher="FTAPP_ENV",  # Environment variable to switch environments
        current_env=env,
    )
    return settings


def get_strategy_settings(strategy_name: str, env: str = "default") -> Dynaconf:
    """
    Loads settings for a specific strategy.

    Args:
        strategy_name: The name of the strategy (e.g., "follow-the-flow").
        env: The environment to load (e.g., "default", "dev").

    Returns:
        A Dynaconf object with the loaded strategy settings.
    """
    strategy_settings_path = (
        APP_BASE_DIR / "strategies_config" / strategy_name / "settings.toml"
    )
    if not strategy_settings_path.exists():
        raise FileNotFoundError(
            f"Strategy settings file not found: {strategy_settings_path}"
        )

    settings = Dynaconf(
        settings_files=[strategy_settings_path],
        environments=True,
        env_switcher="FTAPP_STRATEGY_ENV",  # Separate env switcher for strategy if needed
        current_env=env,
    )
    return settings


if __name__ == "__main__":
    # Example usage:
    # Set environment variable FTAPP_ENV for global settings
    # os.environ["FTAPP_ENV"] = "dev"
    global_conf_default = get_global_settings(env="default")
    print("Global Settings (Default):")
    print(f"  Exchange: {global_conf_default.freqtrade_config.exchange_name}")
    print(f"  Stake Amount: {global_conf_default.freqtrade_config.stake_amount}")
    print(f"  API URL: {global_conf_default.api_settings.liquidation_api_base_url}")

    global_conf_dev = get_global_settings(env="dev")
    print("\nGlobal Settings (Dev):")
    print(f"  Exchange: {global_conf_dev.freqtrade_config.exchange_name}")
    print(f"  Timerange: {global_conf_dev.backtest_settings.timerange}")
    print(f"  API URL: {global_conf_dev.api_settings.liquidation_api_base_url}")

    # Set environment variable FTAPP_STRATEGY_ENV for strategy settings
    # os.environ["FTAPP_STRAPP_ENV"] = "dev"
    strategy_conf_default = get_strategy_settings("follow-the-flow", env="default")
    print("\nFollow-the-Flow Strategy Settings (Default):")
    print(
        f"  Multiplier: {strategy_conf_default.strategy_parameters.average_liquidation_multiplier}"
    )

    strategy_conf_dev = get_strategy_settings("follow-the-flow", env="dev")
    print("\nFollow-the-Flow Strategy Settings (Dev):")
    print(
        f"  Multiplier: {strategy_conf_dev.strategy_parameters.average_liquidation_multiplier}"
    )

    # Test non-existent strategy
    try:
        get_strategy_settings("non_existent_strategy")
    except FileNotFoundError as e:
        print(f"\nSuccessfully caught error for non-existent strategy: {e}")
