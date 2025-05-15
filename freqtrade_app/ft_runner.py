import subprocess
import json
import os
import sys
import argparse
from pathlib import Path
import shutil

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from freqtrade_app.ft_user_data.strategies.src import ft_config_loader
from freqtrade_app.ft_user_data.strategies.src import ft_config_generator


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
    parser.add_argument(
        "--mode",
        type=str,
        required=True,
        choices=["backtest", "paper", "live"],
        help="Execution mode: backtest, paper, or live trading",
    )
    args = parser.parse_args()
    selected_env = args.env
    selected_mode = args.mode

    print(f"--- Freqtrade Runner Initialized for Environment: {selected_env} ---")
    # APP_BASE_DIR is no longer needed for sys.path manipulation here
    # print(f"Application Base Directory (APP_BASE_DIR): {APP_BASE_DIR}")

    # 1. Load Configurations
    print(f"\n1. Loading configurations for env '{selected_env}'...")
    try:
        # ft_config_loader is now imported from the new location via sys.path
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
    # APP_BASE_DIR needs to be defined again here if used for paths
    APP_BASE_DIR = Path(__file__).resolve().parent
    generated_config_path = APP_BASE_DIR / generated_config_filename
    try:
        # ft_config_generator is now imported from the new location via sys.path
        ft_config_generator.generate_freqtrade_config_json(
            global_settings, output_path=generated_config_path, mode=selected_mode
        )
        print(f"Freqtrade 'config.json' generated at: {generated_config_path}")
    except Exception as e:
        print(f"Error generating Freqtrade config.json: {e}")
        sys.exit(1)

    # 4. Ensure User Data Directory Structure
    print("\n4. Ensuring user data directory structure...")
    user_data_dir_name = global_settings.get("freqtrade_config", {}).get(
        "user_data_dir", "ft_user_data"
    )
    exchange_name = global_settings.get("freqtrade_config", {}).get(
        "exchange_name", "binance"
    )

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

        # Removed: 4.A. Copy Strategy File to user_data/strategies

    except Exception as e:
        print(f"Error creating user data directories: {e}")
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
    # PYTHONPATH should now include the project root and the new strategies directory
    project_root = APP_BASE_DIR.parent
    current_pythonpath = os.environ.get("PYTHONPATH", "")
    new_pythonpath = (
        f"{project_root}{os.pathsep}{strategies_path}{os.pathsep}{current_pythonpath}"
        if current_pythonpath
        else f"{project_root}{os.pathsep}{strategies_path}"
    )
    custom_env_for_freqtrade = {
        "PYTHONPATH": new_pythonpath,
        "TRADING_MODE": selected_mode,
    }

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
