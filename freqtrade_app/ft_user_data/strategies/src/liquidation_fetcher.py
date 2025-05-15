import os
import pandas as pd
import requests
from datetime import datetime, timedelta, timezone
from pathlib import Path
import time
from urllib.parse import urljoin
from tenacity import retry, stop_after_attempt, wait_exponential
import asyncio
import websockets
import json
from typing import Optional, Dict, List, Literal

# Determine the base directory of the freqtrade_app.
# This assumes liquidation_fetcher.py is in freqtrade_app/src/
APP_BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CACHE_DIR = APP_BASE_DIR / "cache" / "liquidations"


class WebSocketManager:
    """
    Manages websocket connection for real-time liquidation data.

    Attributes:
        symbol (str): Trading symbol being monitored
        websocket_url (str): URL for websocket connection
        connection (websockets.WebSocketClientProtocol): Active connection
        data_buffer (list): Buffer for incoming liquidation events
        running (bool): Flag indicating if connection is active

    Methods:
        connect(): Establish websocket connection
        disconnect(): Close connection
        listen(): Continuously process incoming messages
        _process_message(): Parse and store liquidation data
    """

    def __init__(self, symbol: str, websocket_url: str):
        self.symbol = symbol
        self.websocket_url = websocket_url
        self.connection = None
        self.data_buffer = []
        self.running = False

    async def connect(self):
        """Establish websocket connection."""
        self.connection = await websockets.connect(self.websocket_url)
        self.running = True

    async def disconnect(self):
        """Close websocket connection."""
        if self.connection:
            await self.connection.close()
            self.running = False

    async def listen(self):
        """Continuously listen for messages and process them."""
        try:
            while self.running:
                message = await self.connection.recv()
                data = json.loads(message)
                self._process_message(data)
        except Exception as e:
            print(f"WebSocket error: {e}")
            await self.disconnect()

    def _process_message(self, data: Dict):
        """Process incoming websocket message."""
        if "o" in data:  # Binance force order format
            liquidation = {
                "symbol": data["o"]["s"],
                "side": data["o"]["S"],
                "price": float(data["o"]["p"]),
                "quantity": float(data["o"]["q"]),
                "timestamp": pd.to_datetime(data["E"], unit="ms", utc=True),
                "status": data["o"]["X"],
                "type": data["o"]["o"],
                "timeInForce": data["o"]["f"],
            }
            self.data_buffer.append(liquidation)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def _fetch_data_from_api_url(
    url: str, params: dict = None, headers: dict = None
) -> list:
    """
    Helper function to fetch data from a given URL with retries.
    Assumes API returns a list of records (e.g., list of dicts).
    """
    response = requests.get(url, params=params, headers=headers, timeout=30)
    response.raise_for_status()  # Raises HTTPError for bad responses (4XX or 5XX)
    return response.json()  # Assumes API returns JSON that is a list of records


def _transform_symbol(symbol: str) -> str:
    """
    Transform Freqtrade symbol format (BTC/USDT:USDT) to API format (BTCUSDT).
    Handles both formats for backward compatibility.
    """
    if ":" in symbol:  # Freqtrade format (BTC/USDT:USDT)
        return symbol.split("/")[0] + symbol.split(":")[0].split("/")[1]
    return symbol  # Already in API format or unknown format


def fetch_liquidations(
    symbol: str,
    start_dt: datetime,
    end_dt: datetime,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    mode: Literal["backtest", "paper", "live"] = "backtest",
    websocket_url: Optional[str] = None,
    # Binance API specific parameters (example)
    limit_per_request: int = 1000,  # Max records per API call for Binance allForceOrders
) -> pd.DataFrame:
    """
    Fetches liquidation data from API and optionally websocket stream.

    Args:
        symbol: Trading symbol (e.g., "BTCUSDT" for Binance)
        start_dt: Start datetime (timezone-aware UTC)
        end_dt: End datetime (timezone-aware UTC)
        cache_dir: Directory to store cached data
        mode: Trading mode - "backtest", "paper", or "live"
        websocket_url: URL for real-time liquidation stream
        limit_per_request: Max records per API call

    Returns:
        pd.DataFrame: Historical data for backtest mode
        LiveDataFrame: Wrapper with get_latest() method for live modes

    Notes:
        - For live modes, the returned object has a get_latest() method
          to retrieve new data from the websocket stream
        - The websocket connection remains open until the returned object
          is garbage collected or explicitly disconnected
    """
    """
    Fetches liquidation data for a given symbol and date range from an API.

    Args:
        symbol: Trading symbol (e.g., "BTCUSDT" for Binance).
        start_dt: Start datetime (timezone-aware UTC).
        end_dt: End datetime (timezone-aware UTC).
        cache_dir: Directory to store and retrieve cached data.
        limit_per_request: Maximum number of records to fetch per API call (API specific).

    Returns:
        A Pandas DataFrame with liquidation data, columns:
        ['timestamp', 'side', 'price', 'quantity', 'symbol', 'origQty', 'executedQty', 'averagePrice', 'status', 'timeInForce', 'type', 'stopPrice', 'icebergQty', 'time', 'updateTime', 'isWorking', 'activatePrice', 'priceRate', 'cumQuote']
        The 'timestamp' column is 'time' from Binance API, converted to datetime64[ns, UTC].
        The 'side' column is 'side' from Binance API ('BUY' or 'SELL').
        The 'price' column is 'price' from Binance API.
        The 'quantity' column is 'origQty' from Binance API.
    """
    if start_dt.tzinfo is None or start_dt.tzinfo.utcoffset(start_dt) is None:
        raise ValueError("start_dt must be timezone-aware (UTC).")
    if end_dt.tzinfo is None or end_dt.tzinfo.utcoffset(end_dt) is None:
        raise ValueError("end_dt must be timezone-aware (UTC).")

    cache_dir.mkdir(parents=True, exist_ok=True)

    # Create a filename that is less prone to issues with special characters or length
    # Using only year-month for broader caching, specific time in filename for exact match
    start_str = start_dt.strftime("%Y%m%d%H%M%S")
    end_str = end_dt.strftime("%Y%m%d%H%M%S")
    # Transform symbol to API format and sanitize for filename
    api_symbol = _transform_symbol(symbol)
    sanitized_symbol = "".join(c if c.isalnum() else "_" for c in api_symbol)
    cache_filename = f"liq_{sanitized_symbol}_{start_str}_{end_str}.parquet"
    cache_filepath = cache_dir / cache_filename

    if cache_filepath.exists():
        try:
            df = pd.read_parquet(cache_filepath)
            # Ensure timestamp is in correct format after loading from cache
            if not df.empty:
                if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
                    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
                elif df["timestamp"].dt.tz is None:
                    df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")
            print(f"Loaded {len(df)} records from cache: {cache_filepath}")
            # For live modes, combine historical and real-time data
            if mode in ["live", "paper"] and ws_manager:
                # Get any real-time data received while fetching historical
                if ws_manager.data_buffer:
                    realtime_df = pd.DataFrame(ws_manager.data_buffer)
                    df = pd.concat([df, realtime_df], ignore_index=True)

                # Return a wrapper DataFrame that continues to receive updates
                class LiveDataFrame:
                    def __init__(self, df: pd.DataFrame, ws_manager: WebSocketManager):
                        self._df = df
                        self.ws_manager = ws_manager

                    def __getattr__(self, name):
                        return getattr(self._df, name)

                    def get_latest(self) -> pd.DataFrame:
                        """Get DataFrame with latest data including new websocket updates"""
                        if self.ws_manager.data_buffer:
                            new_data = pd.DataFrame(self.ws_manager.data_buffer)
                            self._df = pd.concat(
                                [self._df, new_data], ignore_index=True
                            )
                            self.ws_manager.data_buffer.clear()
                        return self._df

                return LiveDataFrame(df, ws_manager)

            return df
        except Exception as e:
            print(f"Error reading cache file {cache_filepath}: {e}. Fetching from API.")

    all_api_data = []
    current_start_time_ms = int(start_dt.timestamp() * 1000)
    end_time_ms = int(end_dt.timestamp() * 1000)

    # Calculate the end time for mock data generation (first 10 minutes of the initial start_dt)
    mock_data_end_time_ms = int((start_dt + timedelta(minutes=10)).timestamp() * 1000)

    api_base_url = os.getenv("LIQUIDATION_API_BASE_URL")
    if not api_base_url:
        raise ValueError("LIQUIDATION_API_BASE_URL environment variable is not set")

    # For live/paper trading, start websocket connection
    ws_manager = None
    if mode in ["live", "paper"]:
        websocket_url = f"wss://fstream.binance.com/ws/{api_symbol.lower()}@forceOrder"
        ws_manager = WebSocketManager(symbol, websocket_url)
        asyncio.get_event_loop().run_until_complete(ws_manager.connect())

        # Start websocket listener in background
        async def run_ws():
            await ws_manager.listen()

        asyncio.create_task(run_ws())
        print(f"WebSocket connection established for {symbol}")

    print(
        f"Fetching liquidations for {symbol} from {start_dt} to {end_dt} from API: {api_base_url}"
    )

    while current_start_time_ms < end_time_ms:
        params = {
            "symbol": api_symbol,
            "startTime": current_start_time_ms,
            # Binance API: If startTime and endTime are not sent, the most recent data is returned.
            # If endTime is sent, it should be less than 7 days from startTime.
            # To be safe, fetch in smaller chunks if the total range is large.
            # Let's calculate a chunk_end_time_ms that is at most 1 day from current_start_time_ms
            # or the overall end_time_ms, whichever is smaller.
            # Binance API also states "If `startTime` and `endTime` are not sent, the most recent limit datas are returned."
            # "If `startTime` and `endTime` are sent, time between startTime and endTime must be less than 7 days."
            # "If `limit` is not sent, it defaults to 500, max 1000"
        }

        # Calculate potential end of this chunk (max 1 day, or overall end_dt)
        # Binance API: "If `startTime` and `endTime` are sent, time between startTime and endTime must be less than 7 days."
        # We will fetch data iteratively. If the API supports fetching up to `limit` records starting from `startTime`
        # without an `endTime`, that's often simpler. If `endTime` is required, we manage chunks.
        # For Binance `allForceOrders`, `endTime` is optional. If not provided, it fetches `limit` records from `startTime`.
        # If `startTime` and `endTime` are provided, the interval must be <= 7 days.
        # Let's use the approach of providing startTime and fetching `limit` records, then advancing startTime.

        params["limit"] = limit_per_request

        # For Binance, the endpoint is the api_base_url itself.
        # url = api_base_url

        try:
            print(
                f"Fetching chunk for {symbol}, startTime: {datetime.fromtimestamp(current_start_time_ms/1000, tz=timezone.utc)}, limit: {limit_per_request}"
            )
            # Example: data = _fetch_data_from_api_url(api_base_url, params=params)
            # This is where you'd make the actual API call.
            # For Binance allForceOrders, the structure is:
            # [
            #   {
            #     "symbol": "BTCUSDT",
            #     "price": "40000.00",
            #     "origQty": "1.000",
            #     "executedQty": "1.000",
            #     "averagePrice": "40000.00",
            #     "status": "FILLED",
            #     "timeInForce": "IOC",
            #     "type": "LIMIT",
            #     "side": "SELL", // "BUY" for long liq, "SELL" for short liq
            #     "stopPrice": "0.00",
            #     "icebergQty": "0.00",
            #     "time": 1618982400000, // Order time
            #     "updateTime": 1618982400000,
            #     "isWorking": true,
            #     "activatePrice": "0",
            #     "priceRate": "0",
            #     "cumQuote": "40000"
            #   }, ...
            # ]
            # For this exercise, we'll use a MOCK response.
            # Replace this with actual `_fetch_data_from_api_url(api_base_url, params=params)`

            # MOCK API RESPONSE - REMOVE FOR REAL IMPLEMENTATION
            # Simulate fetching data. Return empty if current_start_time_ms is beyond the mock data window.
            if current_start_time_ms >= mock_data_end_time_ms:
                data = []
            else:
                mock_time = current_start_time_ms
                data = []
                for i in range(limit_per_request // 2):  # Mock some data points
                    # Stop generating mock data if we exceed the mock data window or the overall end_time
                    if mock_time >= mock_data_end_time_ms or mock_time >= end_time_ms:
                        break
                    data.append(
                        {
                            "symbol": api_symbol,
                            "price": str(20000 + i),
                            "origQty": str(1.0 + i * 0.1),
                            "side": "BUY" if i % 2 == 0 else "SELL",
                            "time": mock_time,
                            # Add other fields as per Binance response if they are needed downstream
                            "executedQty": str(1.0 + i * 0.1),
                            "averagePrice": str(20000 + i),
                            "status": "FILLED",
                            "timeInForce": "IOC",
                            "type": "LIMIT",
                            "stopPrice": "0.00",
                            "icebergQty": "0.00",
                            "updateTime": mock_time,
                            "isWorking": True,
                            "activatePrice": "0",
                            "priceRate": "0",
                            "cumQuote": str((20000 + i) * (1.0 + i * 0.1)),
                        }
                    )
                    mock_time += 60000  # Advance by 1 minute for mock data
            # END MOCK API RESPONSE

            if not data:
                print(
                    f"No more data from API for {symbol} at startTime {datetime.fromtimestamp(current_start_time_ms/1000, tz=timezone.utc)}"
                )
                break

            all_api_data.extend(data)

            # Advance start_time for the next fetch.
            # The Binance API for allForceOrders returns data sorted by time ascending.
            # So, the next startTime should be the time of the last record + 1ms.
            last_record_time_ms = data[-1]["time"]
            current_start_time_ms = last_record_time_ms + 1

            # Respect API rate limits
            time.sleep(
                0.2
            )  # Adjust as per API documentation (Binance is ~1200 requests/min)

        except requests.exceptions.HTTPError as e:
            print(
                f"HTTP error fetching liquidations for {symbol}: {e.response.status_code} {e.response.text}"
            )
            if e.response.status_code in [
                400,
                401,
                403,
                404,
                429,
            ]:  # Client errors or rate limit
                print(f"Client error or rate limit, stopping for {symbol}.")
                break
            # For other server errors, tenacity will retry. If retries fail, it will raise.
            raise
        except Exception as e:
            print(f"Generic error fetching liquidations for {symbol}: {e}")
            # Depending on the error, you might want to break or let tenacity handle it
            raise

    # Create DataFrame from historical API data
    if not all_api_data:
        df = pd.DataFrame()  # Return empty DataFrame if no data
    else:
        df = pd.DataFrame(all_api_data)

    # For live/paper modes, start websocket connection
    ws_manager = None
    if mode in ["live", "paper"] and websocket_url:
        try:
            ws_manager = WebSocketManager(symbol, websocket_url)
            asyncio.get_event_loop().run_until_complete(ws_manager.connect())

            # Start websocket listener in background
            async def run_ws():
                await ws_manager.listen()

            asyncio.create_task(run_ws())

            print(f"WebSocket connection established for {symbol}")
        except Exception as e:
            print(f"Failed to establish WebSocket connection: {e}")

    if not df.empty:
        # Rename 'time' to 'timestamp' and convert to datetime
        df.rename(columns={"time": "timestamp"}, inplace=True)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)

        # Ensure correct dtypes for key columns (price, quantity)
        # Binance API returns these as strings
        df["price"] = pd.to_numeric(df["price"])
        df["origQty"] = pd.to_numeric(
            df["origQty"]
        )  # This is the 'quantity' we care about
        df.rename(columns={"origQty": "quantity"}, inplace=True)

        # Select and order relevant columns (adjust as needed)
        # Standardized columns: timestamp, side, price, quantity, symbol
        # Keep other potentially useful columns from Binance if they exist
        required_cols = ["timestamp", "side", "price", "quantity", "symbol"]
        existing_cols = [col for col in required_cols if col in df.columns]

        # Add any other columns that were returned and might be useful
        other_cols = [col for col in df.columns if col not in existing_cols]
        df = df[existing_cols + other_cols]

        df = df.sort_values(by="timestamp").reset_index(drop=True)

        # Filter by the precise date range, as API might return records slightly outside
        # (especially if pagination is based on record count rather than strict time windows for each call)
        df = df[(df["timestamp"] >= start_dt) & (df["timestamp"] <= end_dt)]

        print(f"Saving {len(df)} fetched liquidation records to {cache_filepath}")
        df.to_parquet(cache_filepath, index=False)
    else:
        print(
            f"No liquidation data found for {symbol} in the given range. Creating empty cache file."
        )
        # Save empty DataFrame to cache to avoid re-fetching for known empty periods
        # Ensure schema matches if saving empty df
        empty_df_cols = [
            "timestamp",
            "side",
            "price",
            "quantity",
            "symbol",
            "executedQty",
            "averagePrice",
            "status",
            "timeInForce",
            "type",
            "stopPrice",
            "icebergQty",
            "updateTime",
            "isWorking",
            "activatePrice",
            "priceRate",
            "cumQuote",
        ]  # Match potential columns from a full response
        # Create an empty DataFrame with these columns and appropriate dtypes
        schema = {
            "timestamp": "datetime64[ns, UTC]",
            "side": "object",
            "price": "float64",
            "quantity": "float64",
            "symbol": "object",
            "executedQty": "float64",
            "averagePrice": "float64",
            "status": "object",
            "timeInForce": "object",
            "type": "object",
            "stopPrice": "float64",
            "icebergQty": "float64",
            "updateTime": "datetime64[ns, UTC]",
            "isWorking": "bool",
            "activatePrice": "object",
            "priceRate": "object",
            "cumQuote": "object",
        }
        df_empty = pd.DataFrame(columns=empty_df_cols)
        for col, dtype in schema.items():
            if col in df_empty.columns:  # Should always be true here
                df_empty[col] = df_empty[col].astype(dtype)

        df_empty.to_parquet(cache_filepath, index=False)
        df = df_empty  # Return the typed empty DataFrame

    return df
