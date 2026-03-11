# pybrisk

Python client for [SBI BRiSK](https://www.brisk.jp/) market data. Access OHLC candles, margin lending, market alerts, and stock universe data for all TSE-listed securities from Python.

## What data can you get?

| Data | Method | Description |
|---|---|---|
| OHLC candles | `Ticker.ohlc()` | 5-min, daily, weekly, monthly price data |
| Margin lending | `Ticker.jsfc()` | JSFC lending/borrowing shares, 逆日歩 fees |
| Stock universe | `Market.stocks_info()` | Turnover + shares outstanding for ~4,500 stocks |
| Stock lists | `Market.stock_lists()` | Nikkei 225 constituents, recent IPOs |
| Market alerts | `Market.alerts()` | Basket orders, limit up/down, volume surges |
| Trading schedule | `Market.schedule()` | Session times, market status |
| Watchlist | `Market.watchlist()` | Your saved stock codes |

## Installation

```bash
pip install pybrisk
```

For automated browser login (optional):

```bash
pip install 'pybrisk[browser]'
```

## Quick Start

```python
import pybrisk as pb

# Authenticate (see Authentication page for details)
pb.login(cookies={"session_xxx": "v2.local.xxx"})

# Per-stock data
ticker = pb.Ticker("7203")  # Toyota
df = ticker.ohlc()           # Daily OHLC DataFrame
margin = ticker.jsfc()       # Margin lending data

# Market-wide data
market = pb.Market()
info = market.stocks_info()  # All ~4,500 TSE stocks
```

## Requirements

- Python 3.10+
- Active SBI Securities account with BRiSK (全板) subscription
- Service hours: 8:00 AM – 3:50 PM JST
