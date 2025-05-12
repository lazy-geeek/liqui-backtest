import subprocess
import json
import os
import sys
import argparse
from pathlib import Path
import shutil

# Assuming ft_config_loader and ft_config_generator are in freqtrade_app/src/
# Adjust import paths if necessary based on execution context.
# If running `python freqtrade_app/ft_runner.py` from project root,
# `freqtrade_app` needs to be in PYTHONPATH or use relative imports carefully.

# Add freqtrade_app/src to sys.path to allow direct imports of modules within src
# This assumes ft_runner.py is in freqtrade_app/
APP_BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = APP_BASE_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

try:
    from src import ft_config_loader
    from src import ft_config_generator
except ImportError as e:
    print(f"Error importing ft_config_loader or ft_config_generator: {e}")
    print(f"Ensure that {SRC_DIR} is accessible and contains these modules.")
    print(f"Current sys.path: {sys.path}")
    sys.exit(1)


def run_subprocess_command(command_list, working_dir=None, extra_env=None):
    """Helper to run a subprocess command and print output."""
    print(f"\nExecuting command: {' '.join(command_list)}")
    try:
        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)

        process = subprocess.run(
            command_list,
            check=True,
            text=True,
            capture_output=True,  # Capture stdout/stderr
            cwd=working_dir,  # Run freqtrade commands from APP_BASE_DIR (freqtrade_app)
            env=env,  # Pass the combined environment
        )
        print("Command STDOUT:")
        print(process.stdout)
        if process.stderr:
            print("Command STDERR:")
            print(process.stderr)
        print(f"Command executed successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {' '.join(command_list)}")
        print(f"Return code: {e.returncode}")
        print("STDOUT:")
        print(e.stdout)
        print("STDERR:")
        print(e.stderr)
        return False
    except FileNotFoundError:
        print(
            f"Error: The command 'freqtrade' was not found. Is Freqtrade installed and in your PATH?"
        )
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Freqtrade Backtest Runner for FollowTheFlow Strategy"
    )
    parser.add_argument(
        "--env",
        type=str,
        default="default",
        help="Environment to load from settings.toml (e.g., default, dev). Default: 'default'.",
    )
    args = parser.parse_args()
    selected_env = args.env

    print(f"--- Freqtrade Runner Initialized for Environment: {selected_env} ---")
    print(f"Application Base Directory (APP_BASE_DIR): {APP_BASE_DIR}")

    # 1. Load Configurations
    print(f"\n1. Loading configurations for env '{selected_env}'...")
    try:
        global_settings = ft_config_loader.get_global_settings(env=selected_env)
        # Strategy settings are loaded by Freqtrade itself via its parameter handling
    except FileNotFoundError as e:
        print(f"Error: Could not load settings files. {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred during configuration loading: {e}")
        sys.exit(1)

    print("Global configurations loaded.")
    # print(f"  Loaded freqtrade_config: {global_settings.get('freqtrade_config', {})}")
    # print(f"  Loaded backtest_settings: {global_settings.get('backtest_settings', {})}")
    # print(f"  Loaded api_settings: {global_settings.get('api_settings', {})}")

    # 2. Generate Freqtrade config.json
    print("\n2. Generating Freqtrade config.json...")
    generated_config_filename = "ft_generated_config.json"
    # Output path for ft_generated_config.json should be inside APP_BASE_DIR (freqtrade_app/)
    # so Freqtrade can find it when CWD is APP_BASE_DIR.
    generated_config_path = APP_BASE_DIR / generated_config_filename
    try:
        ft_config_generator.generate_freqtrade_config_json(
            global_settings, output_path=generated_config_path
        )
        print(f"Freqtrade 'config.json' generated at: {generated_config_path}")
    except Exception as e:
        print(f"Error generating Freqtrade config.json: {e}")
        sys.exit(1)

    # 3. Set LIQUIDATION_API_BASE_URL environment variable
    print("\n3. Setting LIQUIDATION_API_BASE_URL environment variable...")
    api_base_url = global_settings.api_settings.get("liquidation_api_base_url")
    if api_base_url:
        os.environ["LIQUIDATION_API_BASE_URL"] = api_base_url
        print(f"LIQUIDATION_API_BASE_URL set to: {api_base_url}")
    else:
        print(
            "Warning: LIQUIDATION_API_BASE_URL not found in settings. Liquidation fetching in strategy might fail."
        )

    # 4. Ensure User Data Directory Structure and Copy Strategy
    print("\n4. Ensuring user data directory structure and copying strategy...")
    user_data_dir_name = global_settings.freqtrade_config.get(
        "user_data_dir", "ft_user_data"
    )
    exchange_name = global_settings.freqtrade_config.get("exchange_name", "binance")

    # Path should be relative to APP_BASE_DIR if Freqtrade is run from there
    # Freqtrade's user_data_dir in config.json is relative to CWD of freqtrade process.
    # So, if user_data_dir is "ft_user_data", it means "APP_BASE_DIR/ft_user_data"
    ft_user_data_path = APP_BASE_DIR / user_data_dir_name
    exchange_data_path = (
        ft_user_data_path / "data" / exchange_name.lower()
    )  # Freqtrade uses lowercase exchange names for dirs

    try:
        exchange_data_path.mkdir(parents=True, exist_ok=True)
        print(f"User data directory for exchange data ensured at: {exchange_data_path}")
        # Also create strategies subdir if not present, Freqtrade might need it
        strategies_path = ft_user_data_path / "strategies"
        strategies_path.mkdir(parents=True, exist_ok=True)
        print(f"User data strategies directory ensured at: {strategies_path}")

        # 4.A. Copy Strategy File to user_data/strategies
        print("\n4.A. Copying strategy file...")
        source_strategy_file = (
            APP_BASE_DIR / "src" / "strategies" / "follow-the-flow" / "strategy.py"
        )
        destination_strategy_file = strategies_path / "FollowTheFlowStrategy.py"
        shutil.copy2(source_strategy_file, destination_strategy_file)
        print(f"Strategy file copied to: {destination_strategy_file}")

    except FileNotFoundError:
        print(f"Error: Source strategy file not found at {source_strategy_file}")
        sys.exit(1)
    except Exception as e:
        print(f"Error creating user data directories or copying strategy file: {e}")
        sys.exit(1)

    # 5. Download OHLCV Data
    # The config file path for freqtrade CLI should be relative to the CWD (APP_BASE_DIR)
    # or an absolute path. Using relative path from APP_BASE_DIR.
    config_file_for_cli = generated_config_filename  # e.g., "ft_generated_config.json"

    print("\n5. Downloading OHLCV Data via Freqtrade...")
    download_command = [
        "freqtrade",
        "download-data",
        "--config",
        config_file_for_cli,  # Path relative to APP_BASE_DIR
        # "--timerange", global_settings.backtest_settings.get("timerange"), # Timerange from config is usually enough
        # Add other flags if needed, e.g., --days, --pairs
    ]
    # Prepare environment with PYTHONPATH for Freqtrade subprocesses
    python_path_addition = str(APP_BASE_DIR.parent)  # Project root
    current_pythonpath = os.environ.get("PYTHONPATH", "")
    new_pythonpath = (
        f"{python_path_addition}{os.pathsep}{current_pythonpath}"
        if current_pythonpath
        else python_path_addition
    )
    custom_env_for_freqtrade = {"PYTHONPATH": new_pythonpath}

    if not run_subprocess_command(
        download_command, working_dir=APP_BASE_DIR, extra_env=custom_env_for_freqtrade
    ):
        print("Failed to download OHLCV data. Exiting.")
        sys.exit(1)

    # 6. Run Backtest
    print("\n6. Running Backtest via Freqtrade...")
    backtest_command = [
        "freqtrade",
        "backtesting",
        "--config",
        config_file_for_cli,  # Path relative to APP_BASE_DIR
        # Strategy should be picked from config.json
        # "--strategy", global_settings.backtest_settings.get("strategy_name"),
        # Timerange from config.json is usually used by backtesting
        # "--timerange", global_settings.backtest_settings.get("timerange"),
    ]
    if not run_subprocess_command(
        backtest_command, working_dir=APP_BASE_DIR, extra_env=custom_env_for_freqtrade
    ):
        print("Backtesting failed. Exiting.")
        sys.exit(1)

    print("\n--- Freqtrade Runner Finished ---")


if __name__ == "__main__":
    main()
