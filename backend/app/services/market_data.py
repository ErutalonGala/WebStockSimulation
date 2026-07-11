from datetime import date, timedelta


def get_historical_prices(symbol: str, days: int = 10) -> list[dict[str, str | float]]:
    """Return deterministic sample OHLC close data for a stock symbol.

    This placeholder can later be replaced with a vendor integration such as
    Yahoo Finance, Polygon, Alpha Vantage, or an internal data lake.
    """
    base_price = 100 + (sum(ord(char) for char in symbol.upper()) % 60)
    start = date.today() - timedelta(days=days - 1)
    return [
        {
            "date": (start + timedelta(days=index)).isoformat(),
            "symbol": symbol.upper(),
            "close": round(base_price + index * 1.25, 2),
        }
        for index in range(days)
    ]
