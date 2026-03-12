# pybrisk

Python client for [SBI BRiSK](https://www.brisk.jp/) market data — OHLC, margin lending, alerts, and stock info for all TSE-listed securities.

## What is BRiSK?

BRiSK is a browser-based, real-time full order book viewer by [ArGentumCode](https://www.argentumcode.co.jp/) for all ~4,400 Tokyo Stock Exchange stocks. It's offered through SBI Securities and other Japanese brokers.

**pybrisk** wraps BRiSK's internal API so you can access this data from Python.

## Quick Start

```bash
pip install pybrisk
```

```python
import pybrisk as pb

pb.login(cookies={"session_xxx": "v2.local.xxx"})

ticker = pb.Ticker("7203")       # Toyota
df = ticker.ohlc()               # Daily OHLC candles
margin = ticker.jsfc()           # Margin lending data

market = pb.Market()
info = market.stocks_info()      # All ~4,500 TSE stocks
alerts = market.alerts()         # Market condition events
```

See [Authentication](guide/authentication.md) for login options.

## Available Data

| Method | Data | Returns |
|---|---|---|
| `Ticker(code).ohlc(interval)` | OHLC candles (5m / 1d / 1w / 1mo) | DataFrame |
| `Ticker(code).jsfc(count)` | Margin lending from JSFC | DataFrame |
| `Market().stocks_info()` | Turnover + outstanding shares for all stocks | DataFrame |
| `Market().stock_lists()` | Nikkei 225, recent IPOs | dict |
| `Market().alerts()` | Basket orders, limit up/down, volume surges | DataFrame |
| `Market().schedule()` | Trading session times and status | dict |
| `Market().watchlist()` | User's saved stock codes | list |

## Requirements

- Python 3.10+
- SBI Securities account with BRiSK subscription (330 yen/month or free with qualifying account)
- Service hours: 8:00 AM – 3:50 PM JST

## What's Coming

Real-time WebSocket streaming is in progress — see [How It Works](research/how-it-works.md) for details on the binary protocol reverse-engineering effort.
