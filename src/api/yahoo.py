from __future__ import annotations

import csv
from io import StringIO
from typing import List, Optional

from yahooquery import Ticker

from api.http_client import get_json_data
from api.tradingview import tv
from constants.logger import logger
from util.afterhours import afterHours
from util.formatting import format_change

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36 Edg/110.0.1587.57"
}


async def ohlcv(ticker: str) -> dict:
    csv_text = await get_json_data(
        f"https://query1.finance.yahoo.com/v7/finance/download/{ticker}",
        headers=headers,
        text=True,
    )
    # Use StringIO to treat the CSV text as a file-like object
    csv_file = StringIO(csv_text)

    # Use csv.DictReader to parse the CSV text
    reader = csv.DictReader(csv_file)

    # Convert the parsed CSV data to a list of dictionaries
    data = [row for row in reader]

    # If there's only one row, return just that row as a dictionary
    if len(data) == 1:
        return data[0]

    # Return the list of dictionaries if there are multiple rows
    return data


async def all_info(ticker: str) -> dict:
    """
    _summary_

    Parameters
    ----------
    ticker : str
        _description_

    Returns
    -------
    dict
        _description_
    """
    data = await get_json_data(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
        headers=headers,
    )
    return data


async def yf_info(ticker: str, do_format_change: bool = True):
    # This can be blocking
    try:
        # No results when asynchronous=True
        logger.info(f"Getting Yahoo Finance data for {ticker}")
        stock_info = Ticker(ticker, asynchronous=False).price
    except Exception as e:
        logger.error(f"Error in getting Yahoo Finance data for {ticker}: {e}")
        return None

    # Test if the ticker is valid
    if not isinstance(stock_info.get(ticker), dict):
        return None

    stock_info = stock_info[ticker]
    prices = []
    changes = []

    # Helper function to format and append price data
    def append_price_data(price_key, change_key):
        price = stock_info.get(price_key)
        change = stock_info.get(change_key, 0)
        if do_format_change:
            change = format_change(change)
        if price and price != 0:
            prices.append(price)
            changes.append(change or "N/A")  # Handle None or missing change

    # Determine which price to report based on market hours
    if afterHours():
        append_price_data("preMarketPrice", "preMarketChangePercent")
    append_price_data("currentPrice", "regularMarketChangePercent")

    # Calculate volume
    volume: float = (
        stock_info.get("regularMarketVolume", 0) * prices[-1] if prices else 0
    )

    # Prepare return values
    url: str = f"https://finance.yahoo.com/quote/{ticker}"
    exchange: str = stock_info.get("exchange", [])

    return volume, url, [], prices, changes if changes else ["N/A"], ticker

    # TODO: ratelimit exception
    # except Exception as e:
    #    print(f"Error in getting Yahoo Finance data for {ticker}: {e}")

    return None


async def get_stock_info(
    ticker: str, asset_type: str = "stock", do_format_change: bool = True
) -> Optional[tuple[float, str, List[str], float, str, str]]:
    """
    Gets the volume, website, exchanges, price, and change of the stock.

    Parameters
    ----------
    ticker : str
        The ticker of the stock.
    asset_type : str
        The type of asset, this can be stock or forex.
    do_format_change : bool
        Whether to format the change or not.

    Returns
    -------
    Optional[tuple[float, str, List[str], float, str]]
        float
            The volume of the stock.
        str
            The website of the stock.
        list[str]
            The exchanges of the stock.
        float
            The price of the stock.
        str
            The 24h price change of the stock.
        str
            The ticker, to match the crypto function.
    """

    if asset_type == "stock":
        stock_info = await yf_info(ticker, do_format_change)
        if stock_info and stock_info[0] > 0:  # or price == []
            return stock_info

    # Check TradingView data
    tv_data = await tv.get_tv_data(ticker, asset_type)
    if tv_data:
        price, perc_change, volume, exchange, website = tv_data

    if do_format_change:
        perc_change = format_change(perc_change) if perc_change else "N/A"
    return (
        volume,
        website,
        exchange,
        price,
        perc_change,
        ticker,
    )
