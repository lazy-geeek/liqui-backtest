import os
from pathlib import Path
from dynaconf import Dynaconf

# Determine the base directory of the freqtrade_app.
# ft_config_loader.py is in freqtrade_app/ft_user_data/strategies/src/
# So we need to go up 4 levels to reach project root, then down to freqtrade_app/
APP_BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

# Validate we're in the correct location by checking for settings.toml
settings_path = APP_BASE_DIR / "settings.toml"
if not settings_path.exists():
    raise FileNotFoundError(
        f"Could not locate settings.toml at {settings_path}. "
        f"Current calculated base dir: {APP_BASE_DIR}"
    )


def get_global_settings(env: str = "default") -> Dynaconf:
    """
    Loads global settings for the Freqtrade application.

    Args:
        env: The environment to load (e.g., "default", "dev").

    Returns:
        A Dynaconf object with the loaded global settings.
    """
    settings_file_path = APP_BASE_DIR / "settings.toml"
    print(f"\nLoading settings from: {settings_file_path}")
    print(f"Active environment: {env}")

    settings = Dynaconf(
        envvar_prefix="FTAPP",
        settings_files=[settings_file_path],
        environments=True,
        load_dotenv=True,
        env_switcher="FTAPP_ENV",
        current_env=env,
    )

    # Verify critical settings
    print("\nLoaded freqtrade_config settings:")
    print(f"exchange_name: {settings.get('freqtrade_config.exchange_name')}")
    print(f"pair_whitelist: {settings.get('freqtrade_config.pair_whitelist')}")
    print(f"stake_currency: {settings.get('freqtrade_config.stake_currency')}")

    if not settings.get("freqtrade_config.pair_whitelist"):
        print("WARNING: No pair_whitelist found in settings!")

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
