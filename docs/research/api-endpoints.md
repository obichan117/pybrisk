# BRiSK API Endpoints

## Hosts

| Host | Purpose |
|---|---|
| `sbi.brisk.jp` | Main API (stocks, OHLC, watchlists, auth) |
| `tfx-api.brisk.jp` | TFX futures/derivatives via gRPC-Connect |

Both serve over HTTP/3, behind Google infrastructure.

## Main API (sbi.brisk.jp)

### Bootstrap

| Method | Path | Response | Description |
|---|---|---|---|
| GET | `/api/frontend/boot` | JSON | User identity, CSRF token, API token, TFX token, SBI redirect URL |
| GET | `/api/app/boot` | JSON | Trading session schedule, WebSocket URL, master/snapshot hashes |
| GET | `/api/app/market-token` | JSON | PASETO token for real-time market data access |

### Market Data

| Method | Path | Params | Response | Description |
|---|---|---|---|---|
| GET | `/api/master/{hash}` | — | binary | Master data (all stock definitions), ~800KB |
| GET | `/api/snapshot/{hash}` | — | binary | Full market snapshot, ~29MB |
| POST | `/api/stocks_update/{series}` | `date` | binary | Delta updates for specific stocks |
| GET | `/api/markets` | `date`, `series`, `index_from`, `index_to` | JSON | Market condition events (paginated) |

### Stock Info

| Method | Path | Params | Response | Description |
|---|---|---|---|---|
| GET | `/api/stocks_info` | `date` | JSON | Turnover + shares outstanding for all stocks (~3800) |
| GET | `/api/stock_lists` | `date` | JSON | Curated lists (IPO, Nikkei 225 constituents) |
| GET | `/api/ohlc/{issue_code}` | `date` | JSON | OHLC candles: 5min, 1day, 1week, 1month |
| GET | `/api/jsfc/{issue_code}` | `count` | JSON | Margin lending/borrowing data (JSFC) |

### User Data

| Method | Path | Response | Description |
|---|---|---|---|
| GET | `/api/frontend/watchlist` | JSON | User watchlist (zlib+base64 compressed) |

### WebSocket (Real-time)

```
wss://sbi.brisk.jp/realtime/0?session={hex_token}
```

Session token from `/api/app/boot` response `ws_url` field.

## TFX API (tfx-api.brisk.jp)

Uses Connect Protocol (gRPC-Web compatible) with Protobuf.

| Method | Path | Content-Type | Description |
|---|---|---|---|
| POST | `/brisk.tfx.api.ApiService/Boot` | `application/proto` | Bootstrap: returns master/snapshot hashes |
| GET | `/data/master/{hash}` | `application/x-protobuf` | Futures contract definitions (~3KB) |
| GET | `/data/snapshot/{hash}` | `application/x-protobuf` | Futures price snapshot (~6.5KB) |
