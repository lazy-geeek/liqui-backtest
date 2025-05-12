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
