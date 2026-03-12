# pybrisk

[![PyPI version](https://badge.fury.io/py/pybrisk.svg)](https://badge.fury.io/py/pybrisk)
[![Python versions](https://img.shields.io/pypi/pyversions/pybrisk.svg)](https://pypi.org/project/pybrisk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docs](https://img.shields.io/badge/docs-mkdocs-blue.svg)](https://obichan117.github.io/pybrisk/)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/obichan117/pybrisk/blob/main/examples/quickstart.ipynb)

Python client for [SBI BRiSK](https://www.brisk.jp/) market data — OHLC, margin lending, alerts, and stock info for all TSE-listed securities.

## Install

```bash
pip install pybrisk
```

## Quick Start

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

## What's available

| Method | Data | Rows |
|---|---|---|
| `Ticker(code).ohlc()` | OHLC candles (5m/1d/1w/1mo) | ~116-180 |
| `Ticker(code).jsfc()` | Margin lending (JSFC) | ~245 |
| `Market().stocks_info()` | Turnover + outstanding shares | ~4,500 |
| `Market().stock_lists()` | NK225, recent IPOs | — |
| `Market().alerts()` | Basket orders, limit up/down, volume | ~618 |
| `Market().schedule()` | Trading session times | — |
| `Market().watchlist()` | Your saved stock codes | — |

## Authentication

BRiSK authenticates via SBI Securities session cookies. Three options:

```python
# 1. Manual cookies (from browser DevTools)
pb.login(cookies={"session_bfaf77a2": "v2.local.BvaDKm5..."})

# 2. Auto-extract from Chrome (pip install pycookiecheat)
from pycookiecheat import chrome_cookies
pb.login(cookies=chrome_cookies("https://sbi.brisk.jp"))

# 3. Browser automation (pip install 'pybrisk[browser]')
pb.login("username", "password")
```

## Requirements

- Python 3.10+
- SBI Securities account with BRiSK subscription (330 yen/month or free with qualifying account)

## Documentation

Full docs: **[obichan117.github.io/pybrisk](https://obichan117.github.io/pybrisk/)**

- [API Reference](https://obichan117.github.io/pybrisk/api/ticker/) — Ticker, Market, configuration, exceptions
- [How It Works](https://obichan117.github.io/pybrisk/research/how-it-works/) — Layered explanation from basics to binary protocol
- [Architecture](https://obichan117.github.io/pybrisk/research/architecture/) — System diagrams, data pipeline, feature matrix

## License

MIT
